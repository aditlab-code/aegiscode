"""Unit and integration tests for ASYNC-01, ASYNC-08, and ASYNC-10 fixes.

Validates:
1. EventType contract includes WARNING and AGENT_REASONING_DELTA.
2. Runtime._emit_event does not fallback to PHASE_CHANGED for unknown events.
3. response_usage agnostically parses input_tokens and output_tokens from Antigravity usage.
4. AntigravityProvider does not emit duplicate provider_response events.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import sys
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from agent_ai.core.response import response_usage
from agent_ai.providers import antigravity
from agent_ai.runtime.runtime import AgentRuntime
from agent_ai.session.events import EventType
from agent_ai.session.store import InMemorySessionStore


def test_event_type_contract_has_warning_and_reasoning_delta() -> None:
    """ASYNC-01: Verifies EventType enum defines WARNING and AGENT_REASONING_DELTA."""
    assert EventType.WARNING.value == "warning"
    assert EventType.AGENT_REASONING_DELTA.value == "agent_reasoning_delta"


def test_runtime_emit_event_drops_unknown_events_cleanly() -> None:
    from unittest.mock import MagicMock
    from agent_ai.providers.base import BaseProvider

    store = InMemorySessionStore()
    session = store.create_session()
    provider = MagicMock(spec=BaseProvider)
    runtime = AgentRuntime(
        provider=provider,
        executor=None,
        session_store=store,
        session_id=session.session_id,
    )

    # Emit unknown event
    runtime._emit_event("unknown_custom_provider_event", {"some": "data"})

    # Session store must NOT contain a bogus phase_changed event
    events = store.get_events(session.session_id)
    assert len(events) == 0, f"Expected 0 events recorded, but got {len(events)}"

    # Emit known event (warning)
    runtime._emit_event("warning", {"message": "Rate limit nearing"})
    events_after = store.get_events(session.session_id)
    assert len(events_after) == 1
    assert events_after[0].event_type == EventType.WARNING
    assert events_after[0].payload.get("message") == "Rate limit nearing"


def test_response_usage_extracts_input_and_output_tokens() -> None:
    """ASYNC-08: response_usage extracts input_tokens and output_tokens from Antigravity raw usage."""
    raw_payload = {
        "status": "SUCCESS",
        "usage": {
            "input_tokens": 1250,
            "output_tokens": 340,
            "total_tokens": 1590,
        },
    }

    usage = response_usage(raw_payload)
    assert usage is not None
    assert usage["prompt"] == 1250
    assert usage["completion"] == 340
    assert usage["total"] == 1590


def test_antigravity_provider_does_not_emit_manual_provider_response() -> None:
    """ASYNC-08: AntigravityProvider source must not invoke event_sink('provider_response')."""
    src = inspect.getsource(antigravity)
    assert 'event_sink("provider_response"' not in src, (
        "AntigravityProvider still contains manual event_sink('provider_response') emission"
    )
