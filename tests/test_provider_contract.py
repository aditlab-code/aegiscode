"""Unit tests untuk provider_contract.py."""

from agent_ai.core.provider_contract import (
    normalize_tool_call_arguments,
    sanitize_provider_response,
)
from agent_ai.core.response import ActionType, LLMAction, LLMResponse
from agent_ai.providers.base import GenerateResult


def test_normalize_tool_call_arguments() -> None:
    # 1. Dict
    assert normalize_tool_call_arguments({"a": 1}) == {"a": 1}

    # 2. Empty / None
    assert normalize_tool_call_arguments(None) == {}
    assert normalize_tool_call_arguments("") == {}

    # 3. Valid JSON string
    assert normalize_tool_call_arguments('{"key": "value"}') == {"key": "value"}

    # 4. Malformed JSON string
    res = normalize_tool_call_arguments("{broken json")
    assert "_parse_error" in res
    assert res["_raw_string"] == "{broken json"


def test_sanitize_provider_response_with_llm_response() -> None:
    raw_action = LLMAction(id="", name="test_tool", arguments='{"param": 123}')
    orig = LLMResponse(text="", actions=[raw_action])

    sanitized = sanitize_provider_response(None, orig)
    assert len(sanitized.actions) == 1
    act = sanitized.actions[0]
    assert act.name == "test_tool"
    assert act.id != ""  # Auto-generated call ID
    assert act.arguments == {"param": 123}


def test_sanitize_provider_response_with_generate_result() -> None:
    gen = GenerateResult(
        text="Selesai analisis",
        model="gemini-3.8-flash",
        provider="antigravity",
        reasoning="Alur penalaran",
    )
    sanitized = sanitize_provider_response(None, gen)
    assert sanitized.is_final is True
    assert sanitized.text == "Selesai analisis"
    assert sanitized.reasoning == "Alur penalaran"
