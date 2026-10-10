"""Legacy plan-based execution runner (Fase 2 PR-MVP-3).

Karantina loop lama berbasis plan (step-oriented execution dengan heuristic completion).
Dipertahankan semata untuk backward-compatibility dan pengujian legacy.
Alur produksi modern AegisCode menggunakan ContinuousRunner (Native Tool Calling).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from agent_ai.core.loop import AgentLoop, MaxIterationsExceeded
from agent_ai.core.models import AgentObservation
from agent_ai.core.observability import emit as emit_event
from agent_ai.core.orchestration.contracts import OrchestratorResult
from agent_ai.core.response import ActionType, LLMResponse, extract_reasoning_and_content
from agent_ai.providers.base import Message



if TYPE_CHECKING:  # pragma: no cover
    from agent_ai.core.orchestrator import AgentOrchestrator


class LegacyRunner:
    """Runner terisolasi untuk eksekusi berbasis plan lama."""

    # Penanda mutasi workspace
    MUTATION_MARKERS = ("written", "edited", "deleted", "moved")

    # Keyword dan pola requirement teks task
    VALIDATION_KEYWORDS = (
        "test", "tests", "testing", "debug", "validate", "validation",
        "validasi", "verifikasi", "verify", "lulus", "pytest", "unit test",
        "uji", "spec",
    )
    NO_VALIDATION_PHRASES = (
        "jangan test", "jangan debug", "jangan uji", "jangan validasi",
        "tanpa test", "tanpa debug", "tanpa uji", "tanpa verifikasi",
        "tidak perlu test", "tidak perlu debug", "tidak usah test",
        "tidak usah debug", "no test", "no tests", "no debug", "no validation",
        "skip test", "skip tests", "don't test", "dont test",
        "without test", "without tests",
    )
    TARGET_FILE_RE = re.compile(
        r"[A-Za-z0-9_\-./\\]+\.(?:py|js|jsx|ts|tsx|html|htm|css|scss|json|md|"
        r"txt|yml|yaml|toml|ini|cfg|sh|bat|ps1|java|c|h|cpp|hpp|go|rb|php|"
        r"vue|sql|xml|csv|env)"
    )
    REQUIREMENT_FEATURES = {
        "auth": ("login", "log in", "signin", "sign in", "auth",
                 "authenticate", "authentication", "autentikasi"),
        "session": ("session", "sessions", "cookie", "cookies"),
        "redirect": ("redirect", "alihkan", "arahkan"),
        "credential": ("credential", "credentials", "password", "kata sandi"),
    }
    CRUD_WORDS = ("create", "read", "update", "delete")
    CRUD_FEATURES = {
        "create": ("create", "insert", "add", "tambah", "buat"),
        "read": ("read", "get", "list", "fetch", "lihat", "tampil"),
        "update": ("update", "edit", "modify", "ubah", "perbarui"),
        "delete": ("delete", "remove", "destroy", "hapus"),
    }

    def __init__(self, orchestrator: Any) -> None:
        self.orchestrator = orchestrator

    @staticmethod
    def observation_to_message(observation: AgentObservation) -> Message:
        if observation.success:
            content = f"[tool result] {observation.content}"
        else:
            content = f"[tool error] {observation.error}"
        return Message(role="user", content=content)

    @staticmethod
    def action_signature(action: Any) -> str:
        name = getattr(action, "name", "") or ""
        args = getattr(action, "arguments", {}) or {}
        try:
            args_repr = json.dumps(args, sort_keys=True, default=str)
        except (TypeError, ValueError):
            args_repr = str(args)
        return f"{name}:{args_repr}"

    @staticmethod
    def observation_signature(observation: AgentObservation) -> str:
        if observation.success:
            payload = str(observation.content)
        else:
            payload = f"error:{observation.error}"
        digest = hashlib.sha1(payload.encode("utf-8", "replace")).hexdigest()[:12]
        return digest

    @staticmethod
    def observation_outcome(observation: AgentObservation) -> str:
        if not observation.success:
            return "execution_error"
        meta = observation.metadata or {}
        if meta.get("command_failure"):
            return "command_failure"
        return "success"

    @classmethod
    def task_requires_validation(cls, task: str) -> bool:
        text = (task or "").lower()
        if any(phrase in text for phrase in cls.NO_VALIDATION_PHRASES):
            return False
        return any(keyword in text for keyword in cls.VALIDATION_KEYWORDS)

    @classmethod
    def task_target_files(cls, task: str) -> Set[str]:
        targets = set()
        for match in cls.TARGET_FILE_RE.findall(task or ""):
            base = match.replace("\\", "/").split("/")[-1].strip().lower()
            if base:
                targets.add(base)
        return targets

    @staticmethod
    def step_targets(step: Any) -> Set[str]:
        arguments = getattr(getattr(step, "action", None), "arguments", None) or {}
        targets = set()
        for key in ("path", "file", "filename", "target", "source", "destination"):
            value = arguments.get(key)
            if value:
                targets.add(str(value).replace("\\", "/").split("/")[-1].strip().lower())
        targets.discard("")
        return targets

    @staticmethod
    def contains_word(text: str, word: str) -> bool:
        return re.search(
            rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text
        ) is not None

    @classmethod
    def task_requirement_features(cls, task: str) -> Dict[str, tuple]:
        text = (task or "").lower()
        features: Dict[str, tuple] = {}
        for name, aliases in cls.REQUIREMENT_FEATURES.items():
            if any(cls.contains_word(text, alias) for alias in aliases):
                features[name] = aliases
        crud_words = [word for word in cls.CRUD_WORDS if cls.contains_word(text, word)]
        if cls.contains_word(text, "crud") or len(crud_words) >= 2:
            for word in crud_words:
                features[f"crud_{word}"] = cls.CRUD_FEATURES[word]
        return features

    @staticmethod
    def step_evidence(step: Any) -> str:
        arguments = getattr(getattr(step, "action", None), "arguments", None) or {}
        parts = []
        for value in arguments.values():
            if isinstance(value, str):
                parts.append(value)
            elif value is not None:
                parts.append(str(value))
        return " ".join(parts)

    @classmethod
    def is_change_observation(cls, observation: AgentObservation) -> bool:
        content = observation.content
        return (
            observation.success
            and isinstance(content, dict)
            and any(marker in content for marker in cls.MUTATION_MARKERS)
        )

    @staticmethod
    def is_failure_observation(observation: Optional[AgentObservation]) -> bool:
        if observation is None:
            return False
        meta = observation.metadata or {}
        if not observation.success:
            return True
        if meta.get("tool_error") or meta.get("command_failure"):
            return True
        content = observation.content
        if isinstance(content, dict):
            if content.get("outcome") in ("command_failure", "timeout", "spawn_error"):
                return True
            if content.get("success") is False:
                return True
        return False

    @classmethod
    def is_validation_observation(cls, observation: AgentObservation) -> bool:
        if not observation.success or cls.is_failure_observation(observation):
            return False
        if (observation.metadata or {}).get("exit_code") is not None:
            return True
        content = observation.content
        return isinstance(content, dict) and content.get("exit_code") is not None

    @staticmethod
    def completion_signal(response: LLMResponse) -> Optional[str]:
        if response.is_final:
            return response.text
        for action in response.actions:
            if action.type == ActionType.FINAL:
                answer = (action.arguments or {}).get("answer")
                return response.text or (str(answer) if answer is not None else "")
        return None

    def completion_detected(self, loop: AgentLoop) -> bool:
        task = loop.state.task or ""
        needs_validation = self.task_requires_validation(task)
        required_targets = self.task_target_files(task)
        required_features = self.task_requirement_features(task)

        change_applied = False
        validation_after_change = False
        satisfied_targets: Set[str] = set()
        evidence_parts: List[str] = []
        last: Optional[AgentObservation] = None

        for step in loop.state.steps:
            observation = step.observation
            if observation is None:
                continue
            last = observation
            if self.is_change_observation(observation):
                change_applied = True
                validation_after_change = False
            elif self.is_validation_observation(observation):
                validation_after_change = True
            if observation.success:
                satisfied_targets.update(self.step_targets(step))
                evidence_parts.append(self.step_evidence(step))

        if not change_applied:
            return False
        if last is None or self.is_failure_observation(last):
            return False
        if needs_validation and not validation_after_change:
            return False
        if required_targets and not required_targets.issubset(satisfied_targets):
            return False
        if required_features:
            evidence = " ".join(evidence_parts).lower()
            for aliases in required_features.values():
                if not any(self.contains_word(evidence, alias) for alias in aliases):
                    return False
        return True

    @staticmethod
    def completion_result() -> str:
        return (
            "Task selesai: perubahan diterapkan dan requirement task terpenuhi "
            "(completion terdeteksi sebelum iteration limit)."
        )

    @staticmethod
    def recovery_message(decision: Any) -> Message:
        events = ", ".join(getattr(e, "value", str(e)) for e in getattr(decision, "events", [])) or "unknown"
        return Message(
            role="user",
            content=(
                "[reliability] Terdeteksi pola bermasalah: "
                f"{events}. {decision.reason} "
                "Ubah pendekatan: jangan ulangi action yang sama tanpa informasi baru. "
                "Jika task sudah selesai, berikan jawaban final."
            ),
        )

    @staticmethod
    def truncation_message() -> Message:
        return Message(
            role="user",
            content=(
                "[provider] Respons sebelumnya TERPOTONG (finish_reason=length) "
                "sehingga tool-call tidak lengkap dan DIBATALKAN — tidak ada file "
                "parsial yang ditulis. Jangan menggabungkan beberapa file besar ke "
                "dalam satu respons. Tulis SATU file per turn (satu tool call per "
                "respons). Bila satu file sangat besar, tulis secara bertahap: buat "
                "bagian awal lebih dulu, lalu lanjutkan dengan tool berikutnya pada "
                "turn selanjutnya. Lanjutkan task dari langkah terakhir yang sudah "
                "berhasil."
            ),
        )

    def record_and_decide(
        self,
        loop: AgentLoop,
        action: Any,
        observation: AgentObservation,
    ) -> Optional[Any]:
        return None

    def run(
        self,
        task: str,
        *,
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> OrchestratorResult:
        orch = self.orchestrator
        loop = AgentLoop(task=task, max_iterations=orch.max_iterations)
        loop.start()

        history: List[Message] = []
        provider_error = False
        truncation_recoveries = 0

        orch.begin_bible_context_scope()
        brain_context = orch._bible_context_message_for_task(task)
        if brain_context is not None:
            history.append(brain_context)

        while not loop.is_finished:
            if orch._cancel_requested():
                loop.cancel(orch._cancel_reason())
                break

            messages = orch._build_messages(task, history, user_parts=user_parts)
            tools = orch._tool_definitions()
            emit_event(
                orch.event_sink,
                "provider_request",
                {
                    "provider": getattr(orch.provider, "name", ""),
                    "model": orch._model_name(),
                    "iteration": loop.iteration,
                    "tool_count": len(tools),
                    **orch._policy_event_fields(),
                },
            )
            try:
                response = orch._call_provider(
                    messages=messages,
                    options=orch.options,
                    tools=tools,
                    round_index=orch._next_llm_round(),
                    attempt=1,
                )
            except Exception as exc:  # noqa: BLE001
                provider_error = True
                emit_event(
                    orch.event_sink,
                    "provider_response",
                    {
                        "provider": getattr(orch.provider, "name", ""),
                        "model": orch._model_name(),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                recovery = orch._handle_provider_error(loop, exc)
                if recovery is None:
                    break
                history.append(recovery)
                continue

            emit_event(
                orch.event_sink,
                "provider_response",
                orch._provider_response_payload(response),
            )

            truncated = bool(getattr(response, "truncated", False))
            if truncated:
                truncation_recoveries += 1
            else:
                truncation_recoveries = 0
            completion = self.completion_signal(response)
            is_final_turn = bool(response.is_final and not truncated)

            commentary = orch._extract_commentary(response)
            if commentary:
                clean_commentary, _ = extract_reasoning_and_content(commentary)
                clean_comp, _ = extract_reasoning_and_content(completion or "")
                if not (is_final_turn and clean_commentary.strip() == clean_comp.strip()):
                    emit_event(
                        orch.event_sink,
                        "agent_commentary",
                        {"text": clean_commentary, "iteration": loop.iteration},
                    )

            if is_final_turn:
                clean_completion, reasoning_text = extract_reasoning_and_content(completion or "")
                extracted_reasoning = reasoning_text or getattr(response, "reasoning", None)
                orch._last_reasoning = extracted_reasoning
                if extracted_reasoning:
                    emit_event(
                        orch.event_sink,
                        "agent_reasoning_delta",
                        {"delta": extracted_reasoning, "reasoning": extracted_reasoning},
                    )

                allow_empty = bool(
                    orch.options
                    and getattr(orch.options, "extra", None)
                    and isinstance(orch.options.extra, dict)
                    and orch.options.extra.get("allow_empty_response", False)
                )
                if not allow_empty and not (clean_completion or "").strip() and not (extracted_reasoning or "").strip():
                    provider_name = (
                        getattr(response, "provider", None)
                        or getattr(orch.provider, "name", "")
                        or "unknown"
                    )
                    emit_event(
                        orch.event_sink,
                        "provider_malformed_response",
                        {
                            "provider": provider_name,
                            "model": response.model or orch._model_name(),
                            "error": "empty_content_and_tools",
                            "iteration": loop.iteration,
                        },
                    )
                    loop.fail("Provider menghasilkan respons kosong tanpa konten teks maupun tool call (malformed response).")
                    break

                loop.finish(result=clean_completion)
                break

            if truncated:
                emit_event(
                    orch.event_sink,
                    "provider_response_truncated",
                    {
                        "provider": response.provider or getattr(orch.provider, "name", ""),
                        "model": response.model or orch._model_name(),
                        "finish_reason": response.finish_reason.value,
                        "completed_tool_calls": len(response.tool_calls()),
                        "incomplete_tool_calls": int(
                            getattr(response, "incomplete_tool_calls", 0)
                        ),
                        "recovery": truncation_recoveries,
                    },
                )

            try:
                for action in response.tool_calls():
                    if orch._cancel_requested():
                        loop.cancel(orch._cancel_reason())
                        break
                    loop.record_action(orch.executor.to_agent_action(action))
                    emit_event(
                        orch.event_sink,
                        "tool_called",
                        {
                            "tool": action.name,
                            "arguments": dict(action.arguments or {}),
                            "target": orch._tool_target(action.arguments or {}),
                            "iteration": loop.iteration,
                        },
                    )
                    observation = orch.executor.execute_action(action)
                    loop.record_observation(observation)
                    emit_event(
                        orch.event_sink,
                        "tool_completed",
                        {
                            "tool": action.name,
                            "success": observation.success,
                            "error": observation.error,
                            "target": orch._tool_target(action.arguments or {}),
                            "metadata": dict(observation.metadata or {}),
                        },
                    )
                    emit_event(
                        orch.event_sink,
                        "tool_result",
                        {
                            "tool": action.name,
                            "tool_call_id": action.id,
                            "success": observation.success,
                            "status": "success" if observation.success else "error",
                            "output": observation.content,
                            "error": observation.error,
                        },
                    )
                    emit_event(
                        orch.event_sink,
                        "agent_observation",
                        {
                            "action_id": observation.action_id,
                            "success": observation.success,
                            "error": observation.error,
                            "content": observation.content,
                            "metadata": {
                                "tool": action.name,
                                **dict(observation.metadata or {}),
                            },
                        },
                    )
                    emit_event(
                        orch.event_sink,
                        "observation_received",
                        {
                            "tool": action.name,
                            "success": observation.success,
                            "content": observation.content,
                        },
                    )
                    history.append(self.observation_to_message(observation))

                    if not loop.is_finished and self.completion_detected(loop):
                        loop.finish(result=self.completion_result())
                        break

                    decision = self.record_and_decide(loop, action, observation)
                    if decision is None:
                        continue
                    if decision.action == DecisionAction.RECOVER:
                        history.append(self.recovery_message(decision))
                    elif decision.action == DecisionAction.STOP:
                        loop.fail(f"Dihentikan oleh reliability: {decision.reason}")
                        break
                    elif decision.action == DecisionAction.FAIL:
                        loop.fail(f"Gagal oleh reliability: {decision.reason}")
                        break

                if truncated:
                    if not loop.is_finished:
                        history.append(self.truncation_message())
                    if loop.is_finished:
                        break
                    continue
                if completion is not None and not loop.is_finished:
                    loop.finish(result=completion)
                    break
                if loop.is_finished:
                    break
            except MaxIterationsExceeded:
                if self.completion_detected(loop):
                    loop.state.error = None
                    loop.finish(result=self.completion_result())
                break

        learning = orch._learn_from_run(task, loop)

        return OrchestratorResult(
            status=loop.status,
            result=loop.state.result,
            error=loop.state.error,
            iterations=loop.iteration,
            steps=loop.to_dict()["steps"],
            learning=learning,
            provider_error=provider_error,
            reasoning=getattr(orch, "_last_reasoning", None),
        )


__all__ = [
    "LegacyRunner",
]
