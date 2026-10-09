"""Unit test komprehensif untuk klasifikasi activity phase deterministik dan kanonisasi tool.

Memvalidasi:
1. `normalize_canonical_tool_name`: memetakan dialek Antigravity CLI, POSIX, dan alias Aegis ke nama kanonik.
2. `classify_tool_activity`: memetakan tool dan argumen (termasuk CommandLine) ke ActivityPhase.
3. `is_validation_command`: mendeteksi runner tes dan linter dari string, dict, maupun token list.
4. `AgentRuntime._event_sink`: memastikan emisi phase_changed kanonik sebelum tool_called, serta penyertaan field canonical_tool.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from agent_ai.runtime.activity import (
    ActivityPhase,
    classify_tool_activity,
    is_validation_command,
    normalize_canonical_tool_name,
)
from agent_ai.runtime.runtime import AgentRuntime


# =====================================================================
# 1. Normalisasi Nama Tool Kanonik
# =====================================================================

@pytest.mark.parametrize(
    "raw_name,expected_canonical",
    [
        # Inspecting tools
        ("read_file", "read_file"),
        ("view_file", "read_file"),
        ("READ_FILE", "read_file"),
        ("  view_file  ", "read_file"),
        ("read_symbol", "read_file"),
        ("view_symbol", "read_file"),
        ("cat", "read_file"),
        ("view_image", "view_image"),
        ("search_code", "search_code"),
        ("grep", "search_code"),
        ("grep_search", "search_code"),
        ("search_file", "search_code"),
        ("hybrid_search", "search_code"),
        ("list_files", "list_files"),
        ("list_dir", "list_files"),
        ("find_files", "list_files"),
        ("find_by_name", "list_files"),
        ("atlas_query", "atlas_query"),
        ("rig_query", "rig_query"),
        ("project_map_status", "project_map_status"),
        ("refresh_project_map", "refresh_project_map"),
        ("semantic_search", "semantic_search"),
        ("refresh_semantic_index", "refresh_semantic_index"),
        # Editing tools
        ("write_file", "write_file"),
        ("write_to_file", "write_file"),
        ("edit_file", "edit_file"),
        ("edit_file_part", "edit_file"),
        ("replace_file_content", "edit_file"),
        ("replace_content", "edit_file"),
        ("patch_file", "edit_file"),
        ("apply_patch", "edit_file"),
        ("delete_file", "delete_file"),
        ("move_file", "move_file"),
        ("create_skill", "edit_file"),
        ("delete_skill", "edit_file"),
        ("update_skill", "edit_file"),
        # Running tools
        ("run_command", "run_command"),
        ("bash", "run_command"),
        ("terminal_exec", "run_command"),
        ("execute_command", "run_command"),
        ("exec", "run_command"),
        # Passthrough unknown & empty
        ("unknown_custom_tool", "unknown_custom_tool"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_canonical_tool_name(raw_name: Any, expected_canonical: str) -> None:
    assert normalize_canonical_tool_name(raw_name) == expected_canonical


# =====================================================================
# 2. Klasifikasi Activity Phase
# =====================================================================

@pytest.mark.parametrize(
    "tool_name,arguments,expected_phase",
    [
        # Inspecting tools
        ("read_file", None, ActivityPhase.INSPECTING),
        ("view_file", {"path": "main.py"}, ActivityPhase.INSPECTING),
        ("read_symbol", {"symbol": "Agent"}, ActivityPhase.INSPECTING),
        ("search_code", {"query": "TODO"}, ActivityPhase.INSPECTING),
        ("grep", {"pattern": "def "}, ActivityPhase.INSPECTING),
        ("list_files", {"dir": "."}, ActivityPhase.INSPECTING),
        ("list_dir", {"DirectoryPath": "/src"}, ActivityPhase.INSPECTING),
        ("atlas_query", {"query": "deps"}, ActivityPhase.INSPECTING),
        ("semantic_search", {"query": "auth"}, ActivityPhase.INSPECTING),
        # Editing tools
        ("write_file", {"path": "a.txt"}, ActivityPhase.EDITING),
        ("write_to_file", {"AbsolutePath": "/a.txt"}, ActivityPhase.EDITING),
        ("edit_file", {"path": "b.py"}, ActivityPhase.EDITING),
        ("replace_file_content", {"path": "c.py"}, ActivityPhase.EDITING),
        ("patch_file", {"diff": "..."}, ActivityPhase.EDITING),
        ("delete_file", {"path": "old.py"}, ActivityPhase.EDITING),
        ("move_file", {"src": "a", "dst": "b"}, ActivityPhase.EDITING),
        # Running tools (standard operational)
        ("run_command", {"command": "git status"}, ActivityPhase.RUNNING),
        ("bash", {"command": "echo 'build'"}, ActivityPhase.RUNNING),
        ("terminal_exec", {"CommandLine": "ls -la"}, ActivityPhase.RUNNING),
        # Running tools promoted to VALIDATING via `command`
        ("run_command", {"command": "pytest tests/test_unit.py"}, ActivityPhase.VALIDATING),
        ("bash", {"command": "npm test"}, ActivityPhase.VALIDATING),
        ("run_command", {"command": "ruff check src/"}, ActivityPhase.VALIDATING),
        ("run_command", {"command": "cargo test"}, ActivityPhase.VALIDATING),
        ("run_command", {"command": "python -m unittest"}, ActivityPhase.VALIDATING),
        # Running tools promoted to VALIDATING via Antigravity `CommandLine`
        ("run_command", {"CommandLine": "pytest -v"}, ActivityPhase.VALIDATING),
        ("bash", {"CommandLine": "npm run test"}, ActivityPhase.VALIDATING),
        ("bash", {"CommandLine": "mypy src/agent_ai"}, ActivityPhase.VALIDATING),
        # Unknown tool / empty
        ("unknown_tool", None, None),
        ("", None, None),
        (None, None, None),
    ],
)
def test_classify_tool_activity(
    tool_name: Any, arguments: Any, expected_phase: Any
) -> None:
    assert classify_tool_activity(tool_name, arguments) == expected_phase


# =====================================================================
# 3. Deteksi Command Verifikasi (is_validation_command)
# =====================================================================

@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("pytest", True),
        ("pytest -q --tb=short", True),
        ("python -m pytest", True),
        ("npm test", True),
        ("yarn run test", True),
        ("pnpm test", True),
        ("cargo test", True),
        ("go test ./...", True),
        ("ruff check", True),
        ("flake8 .", True),
        ("mypy src/", True),
        ("eslint apps/", True),
        ("tsc --noEmit", True),
        ("python check_format.py", True),
        # Operational commands (should not be validation)
        ("python main.py", False),
        ("ls -la", False),
        ("cat README.md", False),
        ("git commit -m 'update'", False),
        ("npm start", False),
        # Dict formats
        ({"command": "pytest -v"}, True),
        ({"CommandLine": "jest --watchAll=false"}, True),
        ({"cmd": "ruff check"}, True),
        ({"command": "echo ok"}, False),
        # List formats
        (["pytest", "tests/"], True),
        (["npm", "run", "lint"], True),
        (["echo", "hello"], False),
        # Empty/None
        ("", False),
        (None, False),
    ],
)
def test_is_validation_command(cmd: Any, expected: bool) -> None:
    assert is_validation_command(cmd) is expected


# =====================================================================
# 4. Integrasi Event Sink di AgentRuntime
# =====================================================================

def test_runtime_event_sink_canonical_tool_and_phase_emission() -> None:
    emitted_events: List[Dict[str, Any]] = []
    provider = MagicMock()
    runtime = AgentRuntime(provider=provider)
    runtime._emit_event = lambda event_type, payload: emitted_events.append(  # type: ignore[assignment]
        {"event_type": event_type, "payload": dict(payload)}
    )

    # 1. Antigravity tool: view_file -> harus emit phase_changed (inspecting) LALU tool_called
    emitted_events.clear()
    payload_view = {"tool": "view_file", "arguments": {"AbsolutePath": "/path/to/foo.py"}}
    runtime._event_sink("tool_called", payload_view)

    assert len(emitted_events) == 2
    assert emitted_events[0]["event_type"] == "phase_changed"
    assert emitted_events[0]["payload"]["phase"] == "inspecting"

    assert emitted_events[1]["event_type"] == "tool_called"
    assert emitted_events[1]["payload"]["tool"] == "view_file"
    assert emitted_events[1]["payload"]["canonical_tool"] == "read_file"

    # 2. Antigravity tool: replace_file_content -> harus emit phase_changed (editing) LALU tool_called
    emitted_events.clear()
    payload_edit = {"tool": "replace_file_content", "arguments": {"path": "/path/to/foo.py"}}
    runtime._event_sink("tool_called", payload_edit)

    assert len(emitted_events) == 2
    assert emitted_events[0]["event_type"] == "phase_changed"
    assert emitted_events[0]["payload"]["phase"] == "editing"

    assert emitted_events[1]["event_type"] == "tool_called"
    assert emitted_events[1]["payload"]["tool"] == "replace_file_content"
    assert emitted_events[1]["payload"]["canonical_tool"] == "edit_file"

    # 3. Tool: bash dengan CommandLine pytest -> harus emit phase_changed (validating) LALU tool_called
    emitted_events.clear()
    payload_bash_val = {"tool": "bash", "arguments": {"CommandLine": "pytest tests/test_foo.py"}}
    runtime._event_sink("tool_called", payload_bash_val)

    assert len(emitted_events) == 2
    assert emitted_events[0]["event_type"] == "phase_changed"
    assert emitted_events[0]["payload"]["phase"] == "validating"

    assert emitted_events[1]["event_type"] == "tool_called"
    assert emitted_events[1]["payload"]["tool"] == "bash"
    assert emitted_events[1]["payload"]["canonical_tool"] == "run_command"

    # 4. Tool pemanggilan kedua dengan phase sama -> phase_changed dideduplikasi, hanya tool_called ter-emit
    emitted_events.clear()
    payload_bash_val_2 = {"tool": "run_command", "arguments": {"command": "npm test"}}
    runtime._event_sink("tool_called", payload_bash_val_2)

    assert len(emitted_events) == 1
    assert emitted_events[0]["event_type"] == "tool_called"
    assert emitted_events[0]["payload"]["canonical_tool"] == "run_command"
