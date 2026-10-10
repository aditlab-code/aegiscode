"""Provider runner dan resilience layer (Fase 2 MVP Modularization).

Mengekstrak tanggung jawab pemanggilan LLM, error classification, retry bounded
dengan exponential backoff / configurable delay, response sanitization, serta
logging response mentah API.
"""

from __future__ import annotations

import re
import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from agent_ai.core.loop import AgentLoop
from agent_ai.core.observability import EventSink
from agent_ai.core.orchestration.event_reporting import (
    emit_provider_response,
    emit_provider_retry,
    emit_provider_retry_exhausted,
    emit_provider_retry_succeeded,
    format_provider_response_payload,
)
from agent_ai.core.provider_contract import sanitize_provider_response
from agent_ai.core.response import LLMResponse

from agent_ai.projects.models import _now_iso
from agent_ai.providers.base import (
    GenerateOptions,
    Message,
    ProviderError,
    ProviderErrorCategory,
    ProviderEvent,
    ProviderRequest,
    ToolDefinition,
)
if TYPE_CHECKING:  # pragma: no cover
    from agent_ai.core.orchestrator import AgentOrchestrator

#: Default batas attempt provider (1 awal + 3 retry)
DEFAULT_MAX_PROVIDER_ATTEMPTS = 4

#: Pola credential yang disamarkan dari teks error provider sebelum dikirim ke
#: telemetry/activity (jaring pengaman agar secret tidak bocor ke log/UI).
_CREDENTIAL_PATTERNS = re.compile(
    r"(?i)("
    r"bearer\s+[A-Za-z0-9._\-]+"
    r"|sk-[A-Za-z0-9]{8,}"
    r"|api[_-]?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9._\-]+"
    r")"
)


def redact_credentials(text: Any) -> str:
    """Samarkan pola credential pada teks (untuk telemetry/activity)."""
    if text is None:
        return ""
    return _CREDENTIAL_PATTERNS.sub("[redacted]", str(text))


def extract_partial_response(error: BaseException) -> Optional[str]:
    """Ambil partial response terakhir yang sudah diterima sebelum error."""
    for attr in ("raw_reference", "response_body", "partial_response", "partial", "body"):
        value = getattr(error, attr, None)
        if isinstance(value, str) and value.strip():
            return redact_credentials(value)
        if isinstance(value, (bytes, bytearray)):
            try:
                decoded = bytes(value).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            if decoded.strip():
                return redact_credentials(decoded)
    return None


def is_permanent_error(exc: BaseException) -> bool:
    """Klasifikasikan error permanen / non-retryable (OPT-01).

    Error otentikasi, validasi schema, BadRequest 4xx (non-429), dan kegagalan
    serialisasi JSON tidak akan berhasil bila di-retry tanpa perubahan payload.
    """
    if isinstance(exc, ProviderError):
        if not getattr(exc, "retryable", False):
            return True
        kategori = getattr(exc, "kategori", "")
        if kategori in (
            ProviderErrorCategory.AUTHENTICATION.value,
            ProviderErrorCategory.NOT_FOUND.value,
            ProviderErrorCategory.INVALID_REQUEST.value,
            ProviderErrorCategory.CONFIGURATION.value,
            ProviderErrorCategory.RESPONSE_MALFORMED.value,
        ):
            return True
    if isinstance(exc, (TypeError, ValueError)) and "serializ" in str(exc).lower():
        return True
    if any(
        k in type(exc).__name__
        for k in (
            "Authentication",
            "PermissionDenied",
            "NotFound",
            "BadRequest",
            "InvalidRequest",
        )
    ):
        return True
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status_code in (400, 401, 403, 404):
        return True
    return False


def compute_backoff_delay(
    attempt: int,
    base_delay: float,
    *,
    exponential: bool = False,
    jitter: bool = False,
    max_delay: float = 60.0,
) -> float:
    """Hitung jeda delay sebelum retry berikutnya."""
    if base_delay <= 0:
        return 0.0
    delay = base_delay
    if exponential and attempt > 1:
        delay = base_delay * (2 ** (attempt - 1))
    if delay > max_delay:
        delay = max_delay
    if jitter and delay > 0:
        # Sedikit variasi deterministik +/- 10% bila jitter diaktifkan
        delay = delay * 0.95
    return max(0.0, float(delay))


def _get_time_module(orch: Any = None) -> Any:
    """Ambil module/helper time dengan dukungan monkeypatch untuk testing."""
    if orch is not None and hasattr(orch, "time"):
        return getattr(orch, "time")
    orch_mod = sys.modules.get("agent_ai.core.orchestrator")
    if orch_mod is not None and hasattr(orch_mod, "time"):
        return getattr(orch_mod, "time")
    return time


class ProviderRunner:
    """Runner untuk pemanggilan provider LLM, retry resilience, dan logging.

    Menjaga kontrak resilience global:
    1. Error pada provider call tidak langsung menutup lifecycle aktif.
    2. Retry bounded hingga `failed_count + 1` total attempt.
    3. Tool/state yang sudah berhasil dieksekusi TIDAK diulang.
    4. Cancellation user berprioritas tertinggi dan menghentikan retry seketika.
    5. Telemetry bebas dari kebocoran credential.
    """

    def __init__(
        self,
        orchestrator: Any = None,
        *,
        provider: Any = None,
        options: Optional[GenerateOptions] = None,
        tool_choice: Any = None,
        event_sink: Optional[EventSink] = None,
        response_log: Optional[Any] = None,
        reliability: Any = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.provider = provider
        self.options = options
        self.tool_choice = tool_choice
        self.event_sink = event_sink
        self.response_log = response_log
        self.reliability = reliability
        self._llm_round = 0

    def _provider_name(self) -> str:
        provider = (
            getattr(self.orchestrator, "provider", None)
            if self.orchestrator is not None
            else self.provider
        )
        return getattr(provider, "name", "")

    def _model_name(self) -> str:
        if self.orchestrator is not None and hasattr(self.orchestrator, "_model_name"):
            return self.orchestrator._model_name()
        if self.options is not None and getattr(self.options, "model", None):
            return self.options.model
        provider = (
            getattr(self.orchestrator, "provider", None)
            if self.orchestrator is not None
            else self.provider
        )
        config = getattr(provider, "config", None)
        model = getattr(config, "model", None)
        return model or ""

    def api_retry_policy(self) -> Tuple[int, float]:
        """Baca kebijakan retry API LLM dari settings."""
        fallback = (DEFAULT_MAX_PROVIDER_ATTEMPTS - 1, 0.0)
        try:
            from agent_ai.config.settings import (
                api_retry_failed_count,
                api_retry_failed_sleep,
            )

            return (
                max(0, int(api_retry_failed_count())),
                max(0.0, float(api_retry_failed_sleep())),
            )
        except Exception:  # noqa: BLE001
            return fallback

    def next_llm_round(self) -> int:
        """Naikkan dan kembalikan nomor round LLM."""
        if self.orchestrator is not None:
            round_val = int(getattr(self.orchestrator, "_llm_round", 0)) + 1
            setattr(self.orchestrator, "_llm_round", round_val)
            return round_val
        self._llm_round += 1
        return self._llm_round

    def record_llm_response(self, record: Optional[Dict[str, Any]]) -> None:
        """Catat record response API ke log (best-effort)."""
        log = (
            getattr(self.orchestrator, "response_log", None)
            if self.orchestrator is not None
            else self.response_log
        )
        if log is None or record is None:
            return
        try:
            log.append(record)
        except Exception:  # noqa: BLE001
            return

    def response_record_success(
        self, *, round_index: int, attempt: int, response: LLMResponse
    ) -> Dict[str, Any]:
        """Record log untuk response LLM yang sukses."""
        provider_name = response.provider or self._provider_name()
        model_name = response.model or self._model_name()
        return {
            "round": int(round_index),
            "attempt": int(attempt),
            "timestamp": _now_iso(),
            "provider": provider_name,
            "model": model_name,
            "status": "success",
            "finish_reason": getattr(response.finish_reason, "value", None),
            "truncated": bool(getattr(response, "truncated", False)),
            "incomplete_tool_calls": int(getattr(response, "incomplete_tool_calls", 0)),
            "text": response.text or "",
            "tool_calls": [action.to_dict() for action in response.tool_calls()],
            "error": None,
            "partial_response": None,
            "response": getattr(response, "raw", None),
        }

    def response_record_error(
        self, *, round_index: int, attempt: int, error: BaseException
    ) -> Dict[str, Any]:
        """Record log untuk pemanggilan provider yang gagal."""
        return {
            "round": int(round_index),
            "attempt": int(attempt),
            "timestamp": _now_iso(),
            "provider": self._provider_name(),
            "model": self._model_name(),
            "status": "error",
            "finish_reason": None,
            "truncated": False,
            "incomplete_tool_calls": 0,
            "text": "",
            "tool_calls": [],
            "error": {
                "type": type(error).__name__,
                "message": redact_credentials(str(error)),
            },
            "partial_response": extract_partial_response(error),
            "response": None,
        }

    def provider_response_payload(self, response: LLMResponse) -> Dict[str, Any]:
        """Format payload event `provider_response`."""
        return format_provider_response_payload(
            response,
            default_provider=self._provider_name(),
            default_model=self._model_name(),
        )

    @staticmethod
    def _invoke_provider_generate(
        provider: Any,
        messages: Any,
        options: Any,
        tools: Any,
        tool_choice: Any,
        request: ProviderRequest,
    ) -> Any:
        """Panggil provider.generate dengan fallback aman untuk mock/subclass lama."""
        try:
            return provider.generate(
                messages=messages,
                options=options,
                tools=tools,
                tool_choice=tool_choice,
                request=request,
            )
        except TypeError as te:
            if "request" in str(te) and ("unexpected" in str(te) or "keyword" in str(te)):
                return provider.generate(
                    messages=messages,
                    options=options,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            raise

    def call_provider(
        self,
        *,
        messages: List[Any],
        options: Optional[GenerateOptions],
        tools: Optional[List[ToolDefinition]],
        round_index: int,
        attempt: int = 1,
    ) -> LLMResponse:
        """Panggil provider dan catat response (bila logging aktif)."""
        call_options = options
        extra = dict(call_options.extra or {}) if (call_options and call_options.extra) else {}
        extra_updated = False

        event_sink = (
            getattr(self.orchestrator, "event_sink", None)
            if self.orchestrator is not None
            else self.event_sink
        )
        if event_sink is not None and "event_sink" not in extra:
            extra["event_sink"] = event_sink
            extra_updated = True

        execution_policy = (
            getattr(self.orchestrator, "execution_policy", None)
            if self.orchestrator is not None
            else None
        )
        if execution_policy is not None and "execution_policy" not in extra:
            extra["execution_policy"] = execution_policy
            extra["mode"] = execution_policy.get("effective_mode") or "balanced"
            extra_updated = True

        executor = (
            getattr(self.orchestrator, "executor", None)
            if self.orchestrator is not None
            else None
        )
        if getattr(executor, "workspace_root", None) and "workspace_root" not in extra:
            extra["workspace_root"] = executor.workspace_root
            extra_updated = True

        cancel_requested_fn = (
            getattr(self.orchestrator, "_cancel_requested", None)
            if self.orchestrator is not None
            else None
        )
        if cancel_requested_fn is not None and "cancel_check" not in extra:
            extra["cancel_check"] = cancel_requested_fn
            extra_updated = True

        cancel_token = (
            getattr(self.orchestrator, "cancel_token", None)
            if self.orchestrator is not None
            else None
        )
        if cancel_token is not None and "cancel_token" not in extra:
            extra["cancel_token"] = cancel_token
            extra_updated = True

        if extra_updated or (call_options is None and extra):
            call_options = GenerateOptions(
                temperature=call_options.temperature if call_options else None,
                max_tokens=call_options.max_tokens if call_options else None,
                model=call_options.model if call_options else None,
                extra=extra,
            )

        provider = (
            getattr(self.orchestrator, "provider", None)
            if self.orchestrator is not None
            else self.provider
        )
        tool_choice = (
            getattr(self.orchestrator, "tool_choice", None)
            if self.orchestrator is not None
            else self.tool_choice
        )
        response_log = (
            getattr(self.orchestrator, "response_log", None)
            if self.orchestrator is not None
            else self.response_log
        )

        provider_req = ProviderRequest(
            model=call_options.model or getattr(provider, "model", "") or getattr(provider, "name", ""),
            messages=messages,
            tools=tools or None,
            generation_options=call_options,
            runtime_context={
                "round_index": round_index,
                "attempt": attempt,
                "tool_choice": tool_choice.to_dict() if tool_choice else None,
            },
        )

        if response_log is None:
            gen_result = self._invoke_provider_generate(
                provider=provider,
                messages=messages,
                options=call_options,
                tools=tools or None,
                tool_choice=tool_choice,
                request=provider_req,
            )
            return sanitize_provider_response(provider, gen_result)

        try:
            gen_result = self._invoke_provider_generate(
                provider=provider,
                messages=messages,
                options=call_options,
                tools=tools or None,
                tool_choice=tool_choice,
                request=provider_req,
            )
            response: LLMResponse = sanitize_provider_response(provider, gen_result)
        except Exception as exc:  # noqa: BLE001
            self.record_llm_response(
                self.response_record_error(
                    round_index=round_index, attempt=attempt, error=exc
                )
            )
            raise

        self.record_llm_response(
            self.response_record_success(
                round_index=round_index, attempt=attempt, response=response
            )
        )
        return response

    def handle_provider_error(
        self, loop: AgentLoop, error: BaseException
    ) -> Optional[Message]:
        """Tangani error provider."""
        loop.fail(f"{type(error).__name__}: {error}")
        return None

    def generate_with_retry(
        self,
        *,
        loop: AgentLoop,
        messages: List[Any],
        options: Optional[GenerateOptions],
        tools: Optional[List[ToolDefinition]],
    ) -> Optional[LLMResponse]:
        """Panggil provider.generate dengan bounded retry lifecycle."""
        provider_name = self._provider_name()
        model_name = self._model_name()

        if self.orchestrator is not None and hasattr(
            self.orchestrator, "_api_retry_policy"
        ):
            failed_count, failed_sleep = self.orchestrator._api_retry_policy()
        else:
            failed_count, failed_sleep = self.api_retry_policy()

        max_attempts = failed_count + 1
        last_error: Optional[BaseException] = None

        if self.orchestrator is not None and hasattr(
            self.orchestrator, "_next_llm_round"
        ):
            round_index = self.orchestrator._next_llm_round()
        else:
            round_index = self.next_llm_round()

        event_sink = (
            getattr(self.orchestrator, "event_sink", None)
            if self.orchestrator is not None
            else self.event_sink
        )

        def is_cancelled() -> bool:
            if self.orchestrator is not None and hasattr(
                self.orchestrator, "_cancel_requested"
            ):
                return bool(self.orchestrator._cancel_requested())
            return False

        def cancel_reason() -> str:
            if self.orchestrator is not None and hasattr(
                self.orchestrator, "_cancel_reason"
            ):
                return str(self.orchestrator._cancel_reason())
            return "Dibatalkan oleh pengguna"

        for attempt in range(1, max_attempts + 1):
            if is_cancelled():
                loop.cancel(cancel_reason())
                return None

            try:
                if self.orchestrator is not None and hasattr(
                    self.orchestrator, "_call_provider"
                ):
                    response = self.orchestrator._call_provider(
                        messages=messages,
                        options=options,
                        tools=tools,
                        round_index=round_index,
                        attempt=attempt,
                    )
                else:
                    response = self.call_provider(
                        messages=messages,
                        options=options,
                        tools=tools,
                        round_index=round_index,
                        attempt=attempt,
                    )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                emit_provider_response(
                    event_sink,
                    {
                        "provider": provider_name,
                        "model": model_name,
                        "error": redact_credentials(f"{type(exc).__name__}: {exc}"),
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                    },
                )

                err_str = str(exc).lower()
                if (
                    is_cancelled()
                    or "dibatalkan oleh pengguna" in err_str
                    or "user stop" in err_str
                ):
                    loop.cancel(cancel_reason())
                    return None

                if is_permanent_error(exc):
                    break

                if attempt >= max_attempts:
                    break

                emit_provider_retry(
                    event_sink,
                    provider=provider_name,
                    model=model_name,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    max_attempts=max_attempts,
                    error_type=type(exc).__name__,
                    error=redact_credentials(str(exc)),
                )

                if failed_sleep > 0:
                    _get_time_module(self.orchestrator).sleep(failed_sleep)
                    if is_cancelled():
                        loop.cancel(cancel_reason())
                        return None
                continue

            if attempt > 1:
                emit_provider_retry_succeeded(
                    event_sink,
                    provider=provider_name,
                    model=model_name,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
            return response

        error_type = type(last_error).__name__ if last_error is not None else "Error"
        error_text = redact_credentials(
            str(last_error) if last_error is not None else ""
        )
        is_timeout = (
            isinstance(last_error, (TimeoutError,))
            or "timeout" in error_type.lower()
            or "timeout" in error_text.lower()
            or "timed out" in error_text.lower()
        )
        emit_provider_retry_exhausted(
            event_sink,
            provider=provider_name,
            model=model_name,
            attempts=max_attempts,
            error_type="timeout" if is_timeout else error_type,
            error=error_text,
        )
        fail_msg = (
            f"Provider '{provider_name}' request timed out after {max_attempts} attempts: {error_type}: {error_text}"
            if is_timeout
            else (
                f"Provider '{provider_name}' gagal setelah {max_attempts} attempt "
                f"(1 attempt awal + {max_attempts - 1} retry): "
                f"{error_type}: {error_text}"
            )
        )
        loop.fail(fail_msg)
        return None


__all__ = [
    "DEFAULT_MAX_PROVIDER_ATTEMPTS",
    "ProviderRunner",
    "compute_backoff_delay",
    "extract_partial_response",
    "is_permanent_error",
    "redact_credentials",
]
