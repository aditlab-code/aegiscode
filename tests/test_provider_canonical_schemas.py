"""Unit tests untuk skema kanonik ProviderRequest, ProviderEvent, dan ProviderError.

Memvalidasi Fase 3: Normalisasi Boundary Provider:
1. ProviderRequest: model, messages, tools, generation_options, runtime_context
2. ProviderEvent: text, reasoning, tool_call, usage, error, done
3. ProviderError: kategori, retryable, provider, raw_reference
4. Subclass ProviderError: ProviderNotConfiguredError, ProviderUnavailableError, ProviderAPIError, ProviderResponseError
5. Konversi legacy dan resolusi request di BaseProvider & provider_runner.
"""

from __future__ import annotations

import pytest

from agent_ai.core.orchestration.provider_runner import is_permanent_error
from agent_ai.core.response import FinishReason, LLMResponse
from agent_ai.providers.base import (
    BaseProvider,
    GenerateOptions,
    GenerateResult,
    Message,
    ProviderAPIError,
    ProviderError,
    ProviderErrorCategory,
    ProviderEvent,
    ProviderEventType,
    ProviderNotConfiguredError,
    ProviderRequest,
    ProviderResponseError,
    ProviderUnavailableError,
    ToolChoice,
    ToolDefinition,
    build_provider_api_error,
)


class DummyMockProvider(BaseProvider):
    name = "dummy"

    def __init__(self) -> None:
        self.last_request: ProviderRequest | None = None

    def generate(
        self,
        prompt: str | None = None,
        messages: list[Message] | None = None,
        options: GenerateOptions | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: ToolChoice | None = None,
        request: ProviderRequest | None = None,
    ) -> GenerateResult:
        self.last_request = self._resolve_request(
            prompt=prompt,
            messages=messages,
            options=options,
            tools=tools,
            tool_choice=tool_choice,
            request=request,
        )
        return GenerateResult(
            text="dummy response",
            model=self.last_request.model,
            provider=self.name,
        )


# =====================================================================
# 1. Tests untuk ProviderRequest
# =====================================================================


def test_provider_request_instantiation_defaults() -> None:
    req = ProviderRequest()
    assert req.model == ""
    assert req.messages == []
    assert req.tools is None
    assert req.generation_options is None
    assert req.runtime_context is None


def test_provider_request_explicit_fields() -> None:
    msg = Message(role="user", content="Halo")
    tool = ToolDefinition(name="read_file", description="Baca berkas")
    opts = GenerateOptions(temperature=0.7, max_tokens=100)
    ctx = {"session_id": "sess-123", "mode": "deep"}

    req = ProviderRequest(
        model="gemini-3.8-flash",
        messages=[msg],
        tools=[tool],
        generation_options=opts,
        runtime_context=ctx,
    )
    assert req.model == "gemini-3.8-flash"
    assert len(req.messages) == 1
    assert req.messages[0].content == "Halo"
    assert len(req.tools or []) == 1
    assert req.generation_options.temperature == 0.7
    assert req.runtime_context["session_id"] == "sess-123"


def test_provider_request_from_legacy_prompt() -> None:
    opts = GenerateOptions(model="gpt-4o", extra={"workspace_root": "/workspace"})
    tc = ToolChoice(mode="specific", name="search_code")

    req = ProviderRequest.from_legacy(
        prompt="Analisis kode ini",
        options=opts,
        tool_choice=tc,
        default_model="fallback-model",
    )
    assert req.model == "gpt-4o"
    assert len(req.messages) == 1
    assert req.messages[0].role == "user"
    assert req.messages[0].content == "Analisis kode ini"
    assert req.runtime_context is not None
    assert req.runtime_context["tool_choice"] == {"mode": "specific", "name": "search_code"}
    assert req.runtime_context["workspace_root"] == "/workspace"


def test_provider_request_to_legacy_kwargs() -> None:
    msg = Message(role="system", content="Anda adalah asisten")
    opts = GenerateOptions(temperature=0.0)
    req = ProviderRequest(
        model="claude-3-7-sonnet",
        messages=[msg],
        generation_options=opts,
    )
    kwargs = req.to_legacy_kwargs()
    assert kwargs["prompt"] is None
    assert kwargs["messages"] == [msg]
    assert kwargs["options"] == opts
    assert kwargs["tools"] is None


# =====================================================================
# 2. Tests untuk ProviderEvent
# =====================================================================


def test_provider_event_variants() -> None:
    # Text event
    ev_text = ProviderEvent.text_event("Halo dunia")
    assert ev_text.event_type == ProviderEventType.TEXT.value
    assert ev_text.text == "Halo dunia"
    assert ev_text.done is False

    # Reasoning event
    ev_reason = ProviderEvent.reasoning_event("Sedang merencanakan...")
    assert ev_reason.event_type == ProviderEventType.REASONING.value
    assert ev_reason.reasoning == "Sedang merencanakan..."

    # Tool call event
    call_payload = {"name": "read_file", "arguments": {"path": "main.py"}}
    ev_tc = ProviderEvent.tool_call_event(call_payload)
    assert ev_tc.event_type == ProviderEventType.TOOL_CALL.value
    assert ev_tc.tool_call == call_payload

    # Usage event
    usage_info = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    ev_usage = ProviderEvent.usage_event(usage_info)
    assert ev_usage.event_type == ProviderEventType.USAGE.value
    assert ev_usage.usage == usage_info

    # Error event
    ev_err = ProviderEvent.error_event("Koneksi terputus")
    assert ev_err.event_type == ProviderEventType.ERROR.value
    assert ev_err.error == "Koneksi terputus"

    # Done event
    ev_done = ProviderEvent.done_event()
    assert ev_done.event_type == ProviderEventType.DONE.value
    assert ev_done.done is True


def test_provider_event_to_dict() -> None:
    ev = ProviderEvent.text_event("sample text", raw={"finish_reason": "stop"})
    d = ev.to_dict()
    assert d["event_type"] == "text"
    assert d["text"] == "sample text"
    assert d["raw"] == {"finish_reason": "stop"}
    assert d["done"] is False


# =====================================================================
# 3. Tests untuk ProviderError & Subclasses
# =====================================================================


def test_provider_error_canonical_attributes() -> None:
    err = ProviderError(
        "Koneksi gagal",
        kategori=ProviderErrorCategory.NETWORK_UNAVAILABLE.value,
        retryable=True,
        provider="ollama",
        raw_reference="http://localhost:11434",
    )
    assert str(err) == "Koneksi gagal"
    assert err.kategori == "network_unavailable"
    assert err.category == "network_unavailable"
    assert err.retryable is True
    assert err.provider == "ollama"
    assert err.raw_reference == "http://localhost:11434"


def test_provider_not_configured_error() -> None:
    err = ProviderNotConfiguredError(
        "API key kosong",
        provider="openai",
        raw_reference="env:OPENAI_API_KEY",
    )
    assert err.kategori == "configuration"
    assert err.category == "configuration"
    assert err.retryable is False
    assert err.provider == "openai"
    assert err.raw_reference == "env:OPENAI_API_KEY"


def test_provider_unavailable_error() -> None:
    err = ProviderUnavailableError(
        "Host tidak merespons",
        provider="deepseek",
        raw_reference="https://api.deepseek.com",
    )
    assert err.kategori == "network_unavailable"
    assert err.retryable is True
    assert err.provider == "deepseek"
    assert err.raw_reference == "https://api.deepseek.com"


def test_provider_api_error_auto_categorization() -> None:
    # 401 Authentication
    err_401 = ProviderAPIError("Unauthorized", status_code=401, endpoint="/chat", provider="antigravity")
    assert err_401.kategori == "authentication"
    assert err_401.retryable is False
    assert err_401.provider == "antigravity"
    assert err_401.raw_reference == "/chat"

    # 404 Not Found
    err_404 = ProviderAPIError("Model not found", status_code=404, endpoint="/chat", provider="ollama")
    assert err_404.kategori == "not_found"
    assert err_404.retryable is False

    # 429 Rate Limit
    err_429 = ProviderAPIError("Too Many Requests", status_code=429, endpoint="/chat", provider="openai")
    assert err_429.kategori == "rate_limit"
    assert err_429.retryable is True

    # 500 Server Error
    err_500 = ProviderAPIError("Internal Error", status_code=500, endpoint="/chat", provider="openrouter")
    assert err_500.kategori == "server_error"
    assert err_500.retryable is True

    # 400 Invalid Request
    err_400 = ProviderAPIError("Bad Request", status_code=400, endpoint="/chat", provider="custom")
    assert err_400.kategori == "invalid_request"
    assert err_400.retryable is False


def test_provider_response_error() -> None:
    err = ProviderResponseError(
        "JSON korup",
        provider="ollama",
        raw_reference="partial payload {",
    )
    assert err.kategori == "response_malformed"
    assert err.retryable is False
    assert err.provider == "ollama"
    assert err.raw_reference == "partial payload {"


def test_build_provider_api_error_populates_canonical_fields() -> None:
    err = build_provider_api_error(
        "ollama",
        404,
        method="POST",
        url="http://localhost:11434/api/chat",
        body_limit=100,
    )
    assert err.provider == "ollama"
    assert err.kategori == "not_found"
    assert err.retryable is False
    assert err.endpoint == "http://localhost:11434/api/chat"
    assert err.raw_reference == "http://localhost:11434/api/chat"


# =====================================================================
# 4. Tests untuk Integrasi BaseProvider & Provider Runner
# =====================================================================


def test_base_provider_resolve_request_direct() -> None:
    provider = DummyMockProvider()
    req = ProviderRequest(model="test-model", messages=[Message(role="user", content="Tes")])
    res = provider.generate(request=req)
    assert res.text == "dummy response"
    assert provider.last_request is not None
    assert provider.last_request.model == "test-model"
    assert len(provider.last_request.messages) == 1


def test_base_provider_resolve_request_from_legacy() -> None:
    provider = DummyMockProvider()
    res = provider.generate(
        prompt="Pertanyaan singkat",
        options=GenerateOptions(model="custom-model"),
    )
    assert res.text == "dummy response"
    assert provider.last_request is not None
    assert provider.last_request.model == "custom-model"
    assert provider.last_request.messages[0].content == "Pertanyaan singkat"


def test_is_permanent_error_with_canonical_categories() -> None:
    # Error konfigurasi non-retryable
    err_cfg = ProviderError("Config missing", kategori="configuration", retryable=False)
    assert is_permanent_error(err_cfg) is True

    # Error otentikasi
    err_auth = ProviderAPIError("Auth fail", status_code=401)
    assert is_permanent_error(err_auth) is True

    # Error server sementara (retryable)
    err_server = ProviderAPIError("Server overloaded", status_code=500)
    assert is_permanent_error(err_server) is False
