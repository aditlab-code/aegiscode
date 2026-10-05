"""Integration test for AntigravityProvider multi-turn agent activity & phase transitions.

Validates that AntigravityProvider correctly:
1. Injects tool schemas into the CLI bridge prompt.
2. Normalizes multi-turn Markdown tool calls into structured actions.
3. Drives the runtime loop across multiple turns (inspect -> edit -> finish).
4. Transitions activity phases from "planning" -> "inspecting" -> "editing".
5. Emits agent commentary, tool_called, and tool_completed events cleanly.
6. Does not get stuck on iteration 1.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from agent_ai.config.settings import AntigravityConfig
from agent_ai.core.executor import ToolExecutor
from agent_ai.providers.antigravity import AntigravityProvider
from agent_ai.runtime.models import RuntimeStatus
from agent_ai.runtime.runtime import AgentRuntime
from agent_ai.session.store import InMemorySessionStore
from agent_ai.task.models import PreparedTask
from agent_ai.tools.registry import build_registry


def test_antigravity_multi_turn_activity_phases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Setup workspace with sample file
    greeting_file = tmp_path / "greeting.txt"
    greeting_file.write_text("hello", encoding="utf-8")

    # 2. Configure AntigravityProvider with mock CLI bridge
    cfg = AntigravityConfig(cli_path="/bin/agy_mock", model="gemini-3.8-flash-medium")
    provider = AntigravityProvider(config=cfg)
    monkeypatch.setattr(provider, "_resolve_cli_path", lambda: "/bin/agy_mock")

    # 3. Define 3-turn responses
    responses = [
        # Turn 1: Inspect greeting.txt
        json.dumps({
            "status": "SUCCESS",
            "response": (
                "Inspecting file\n"
                "```tool_call\n"
                '{"name": "read_file", "arguments": {"path": "greeting.txt"}}\n'
                "```"
            ),
        }),
        # Turn 2: Edit greeting.txt
        json.dumps({
            "status": "SUCCESS",
            "response": (
                "Updating file\n"
                "```tool_call\n"
                '{"name": "write_file", "arguments": {"path": "greeting.txt", "content": "hello world"}}\n'
                "```"
            ),
        }),
        # Turn 3: Final completion
        json.dumps({
            "status": "SUCCESS",
            "response": "File updated successfully",
        }),
    ]
    call_count = 0
    prompts_captured: List[str] = []

    def fake_run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        prompts_captured.append(cmd[2])
        resp = responses[call_count] if call_count < len(responses) else responses[-1]
        call_count += 1
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=resp,
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    # 4. Setup session store, tool registry, executor, and runtime
    store = InMemorySessionStore()
    session = store.create_session()
    registry = build_registry(root=tmp_path)
    executor = ToolExecutor(registry)
    runtime = AgentRuntime(
        provider=provider,
        executor=executor,
        session_store=store,
        session_id=session.session_id,
    )

    # 5. Execute task
    prepared = PreparedTask(task="Update greeting.txt to say hello world")
    result = runtime.run(prepared)

    # 6. Assertions
    # Status and file modifications
    assert result.status == RuntimeStatus.COMPLETED
    assert greeting_file.read_text(encoding="utf-8") == "hello world"
    assert call_count == 3, f"Expected 3 turns, but got {call_count}"

    # Prompt verification: Turn 1 contained tool descriptions
    assert "## Available Tools" in prompts_captured[0]
    assert "### `read_file`" in prompts_captured[0]
    assert "### `write_file`" in prompts_captured[0]

    # Turn 2 contained tool result from read_file
    assert "[TOOL RESULT for read_file]:" in prompts_captured[1]

    # Turn 3 contained tool result from write_file
    assert "[TOOL RESULT for write_file]:" in prompts_captured[2]

    # Event stream verification
    events = store.get_events(session_id=session.session_id)
    event_types = [e.event_type.value for e in events]

    assert "task_started" in event_types
    assert "task_completed" in event_types
    assert "agent_commentary" in event_types
    assert "tool_called" in event_types
    assert "tool_completed" in event_types
    assert "phase_changed" in event_types

    # Activity phase transitions: planning -> inspecting -> editing
    phases = [e.payload.get("phase") for e in events if e.event_type.value == "phase_changed"]
    assert "planning" in phases
    assert "inspecting" in phases
    assert "editing" in phases

    planning_idx = phases.index("planning")
    inspecting_idx = phases.index("inspecting")
    editing_idx = phases.index("editing")
    assert planning_idx < inspecting_idx < editing_idx, f"Phase order wrong: {phases}"

    # Agent commentary verification
    commentaries = [e.payload.get("text") for e in events if e.event_type.value == "agent_commentary"]
    assert any("Inspecting file" in c for c in commentaries)
    assert any("Updating file" in c for c in commentaries)

    # Tool calls & completions verification
    tools_called = [e.payload.get("tool") for e in events if e.event_type.value == "tool_called"]
    assert tools_called == ["read_file", "write_file"]

    tools_completed = [e.payload.get("tool") for e in events if e.event_type.value == "tool_completed"]
    assert tools_completed == ["read_file", "write_file"]
