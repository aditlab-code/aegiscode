"""Unit test untuk ProviderRunner dan event_reporting (Fase 2 PR-MVP-2).

Memverifikasi:
1. ProviderRunner modular standalone & delegasi via AgentOrchestrator facade.
2. Error classification (is_permanent_error) untuk berbagai skenario error.
3. Kredensial redaction & partial response extraction.
4. Backoff delay computation (exponential backoff & bounded delay).
5. Event reporting helpers stream UI/SSE (wire format 100% identik).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from agent_ai.core.loop import AgentLoop
from agent_ai.core.orchestrator import AgentOrchestrator
from agent_ai.core.orchestration.event_reporting import (
    emit_commentary,
    emit_loop_safety_abort,
    emit_observation,
    emit_observation_received,
    emit_provider_malformed,
    emit_provider_request,
    emit_provider_response,
    emit_provider_retry,
    emit_provider_retry_exhausted,
    emit_provider_retry_succeeded,
    emit_provider_truncated,
    emit_reasoning,
    emit_tool_call,
    emit_tool_completion,
    emit_tool_result,
    format_provider_response_payload,
)
from agent_ai.core.orchestration.provider_runner import (
    DEFAULT_MAX_PROVIDER_ATTEMPTS,
    ProviderRunner,
    compute_backoff_delay,
    extract_partial_response,
    is_permanent_error,
    redact_credentials,
)
from agent_ai.core.response import FinishReason, LLMResponse
from agent_ai.providers.base import GenerateOptions, GenerateResult, ProviderError


def test_redact_credentials_and_extract_partial_response():
    raw_secret = "Bearer sk-1234567890abcdef and api_key='sk-secret999'"
    redacted = redact_credentials(raw_secret)
    assert "[redacted]" in redacted
    assert "sk-1234567890abcdef" not in redacted
    assert "sk-secret999" not in redacted
    assert redact_credentials(None) == ""

    err = ProviderError("Gagal API")
    err.retryable = False
    setattr(err, "response_body", "Bearer sk-partialsecret")
    partial = extract_partial_response(err)
    assert "[redacted]" in partial
    assert "sk-partialsecret" not in partial

    # Byte body
    err2 = RuntimeError("Binary error")
    setattr(err2, "body", b"api_key=sk-bytesecret")
    partial2 = extract_partial_response(err2)
    assert "[redacted]" in partial2
    assert "sk-bytesecret" not in partial2


def test_is_permanent_error_classification():
    # Non-retryable ProviderError
    err_perm = ProviderError("Unauthorized")
    err_perm.retryable = False
    assert is_permanent_error(err_perm) is True

    # Retryable ProviderError
    err_trans = ProviderError("Rate limit")
    err_trans.retryable = True
    assert is_permanent_error(err_trans) is False

    # JSON serialization error
    assert is_permanent_error(TypeError("Object of type set is not JSON serializable")) is True
    assert is_permanent_error(ValueError("Cannot serialize payload")) is True

    # HTTP 4xx error codes
    class CustomHTTPError(Exception):
        status_code = 401

    assert is_permanent_error(CustomHTTPError("Auth failed")) is True

    class AnotherError(Exception):
        code = 403

    assert is_permanent_error(AnotherError("Forbidden")) is True

    # Standard transient error
    assert is_permanent_error(RuntimeError("Connection reset by peer")) is False
    assert is_permanent_error(TimeoutError("Read timed out")) is False


def test_compute_backoff_delay():
    assert compute_backoff_delay(1, 0.0) == 0.0
    assert compute_backoff_delay(1, 1.5, exponential=False) == 1.5
    assert compute_backoff_delay(2, 1.5, exponential=False) == 1.5
    assert compute_backoff_delay(2, 1.5, exponential=True) == 3.0
    assert compute_backoff_delay(3, 1.5, exponential=True) == 6.0
    assert compute_backoff_delay(10, 1.5, exponential=True, max_delay=10.0) == 10.0


def test_event_reporting_wire_format():
    events: List[Dict[str, Any]] = []

    def sink(event_type: str, payload: Dict[str, Any]) -> None:
        events.append({"type": event_type, **payload})

    emit_reasoning(sink, delta="thinking step", reasoning="full thought")
    emit_commentary(sink, text="doing work", iteration=1)
    emit_tool_call(sink, tool="read_file", tool_call_id="call-1", arguments={"path": "a.txt"}, target="a.txt", iteration=1)
    emit_tool_result(sink, tool="read_file", tool_call_id="call-1", success=True, output="content")
    emit_tool_completion(sink, tool="read_file", tool_call_id="call-1", success=True, target="a.txt")
    emit_observation(sink, action_id="call-1", success=True, content="content")
    emit_observation_received(sink, tool="read_file", tool_call_id="call-1", success=True, content="content")
    emit_loop_safety_abort(sink, max_steps=50, iteration=51)

    types = [e["type"] for e in events]
    assert types == [
        "agent_reasoning_delta",
        "agent_commentary",
        "tool_called",
        "tool_result",
        "tool_completed",
        "agent_observation",
        "observation_received",
        "loop_safety_abort",
    ]
    assert events[0]["delta"] == "thinking step"
    assert events[1]["text"] == "doing work"
    assert events[2]["tool"] == "read_file"
    assert events[3]["status"] == "success"
    assert events[4]["target"] == "a.txt"


def test_provider_runner_standalone():
    class DummyProvider:
        name = "dummy-prov"
        config = SimpleNamespace(model="dummy-mod")

        def generate(self, **kwargs):
            return GenerateResult(text="response text", raw={"usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    provider = DummyProvider()
    events: List[Dict[str, Any]] = []

    def sink(event_type: str, payload: Dict[str, Any]) -> None:
        events.append({"type": event_type, **payload})

    runner = ProviderRunner(
        provider=provider,
        options=GenerateOptions(model="custom-mod"),
        event_sink=sink,
    )

    loop = AgentLoop(task="test task", max_iterations=2)
    loop.start()

    res = runner.generate_with_retry(
        loop=loop,
        messages=[{"role": "user", "content": "hi"}],
        options=None,
        tools=None,
    )

    assert res is not None
    assert res.text == "response text"

    payload = runner.provider_response_payload(res)
    assert payload["provider"] == "dummy-prov"
    assert payload["model"] == "custom-mod"
    assert payload["tool_calls"] == 0
    assert payload["usage"]["prompt"] == 10


def test_orchestrator_facade_delegation_integrity():
    class DummyProvider:
        name = "mock-p"
        config = SimpleNamespace(model="mock-m")

        def generate(self, **kwargs):
            return GenerateResult(text="ok")

    orch = AgentOrchestrator(
        provider=DummyProvider(),
        use_continuous_loop=True,
    )

    # Memastikan delegasi method publik/internal tetap mengembalikan hasil yang sesuai
    retry_policy = orch._api_retry_policy()
    assert isinstance(retry_policy, tuple)
    assert len(retry_policy) == 2
    assert retry_policy == ProviderRunner(orch).api_retry_policy()
    round_no = orch._next_llm_round()
    assert round_no == 1
    assert orch._next_llm_round() == 2

    # Call provider via orchestrator facade
    res = orch._call_provider(messages=[], options=None, tools=None, round_index=round_no)
    assert res.text == "ok"
    payload = orch._provider_response_payload(res)
    assert payload["provider"] == "mock-p"
    assert payload["finish_reason"] == FinishReason.STOP.value
