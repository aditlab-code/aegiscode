"""Unit tests untuk sanitasi kredensial penuh dan guardrail workspace (Fase 4)."""

import json
from pathlib import Path
import pytest

from agent_ai.session.events import EventType, make_event
from agent_ai.projects.aegis_store import ResponseLog, AegisProjectStore
from agent_ai.tools.workspace import _resolve_write_path, ToolValidationError


def test_make_event_sanitizes_credentials_in_payload():
    """make_event wajib menyamarkan kredensial sensitif dalam payload."""
    raw_payload = {
        "api_key": "sk-proj-supersecret123",
        "auth_token": "bearer-token-abc",
        "password": "my-secret-password",
        "user": "developer",
        "nested": {
            "secret_key": "secret-value-xyz",
            "normal_field": "safe_data",
        },
    }
    evt = make_event(
        session_id="sess-phase4",
        event_type=EventType.TOOL_CALLED,
        payload=raw_payload,
    )
    payload = evt.payload
    assert payload["api_key"] == "[redacted]"
    assert payload["auth_token"] == "[redacted]"
    assert payload["password"] == "[redacted]"
    assert payload["user"] == "developer"
    assert payload["nested"]["secret_key"] == "[redacted]"
    assert payload["nested"]["normal_field"] == "safe_data"


def test_response_log_append_sanitizes_secrets_on_disk(tmp_path: Path):
    """ResponseLog.append wajib menyamarkan data rahasia sebelum disimpan ke disk."""
    store = AegisProjectStore(tmp_path)
    logger = ResponseLog(store, task_id="task-audit-secret")
    record = {
        "round": 1,
        "token": "ghp_1234567890abcdef",
        "response": {
            "text": "Hello world",
            "api_key": "AIzaSySecretKey",
        },
    }
    ok = logger.append(record)
    assert ok is True

    # Baca langsung berkas JSON mentah dari disk
    log_file = tmp_path / ".aegis" / "log" / "response" / "task-audit-secret.json"
    assert log_file.exists()
    content = json.loads(log_file.read_text(encoding="utf-8"))
    responses = content["responses"]
    assert len(responses) == 1
    assert responses[0]["token"] == "[redacted]"
    assert responses[0]["response"]["api_key"] == "[redacted]"
    assert responses[0]["response"]["text"] == "Hello world"


def test_resolve_write_path_strictly_blocks_outside_workspace(tmp_path: Path):
    """_resolve_write_path wajib menolak mutasi di luar root workspace."""
    workspace = tmp_path / "my_project"
    workspace.mkdir()

    # Valid write inside workspace
    valid_target = _resolve_write_path("src/app.py", workspace)
    assert valid_target.is_relative_to(workspace.resolve())

    # Path traversal ../
    with pytest.raises(ToolValidationError, match="di luar project root"):
        _resolve_write_path("../outside.py", workspace)

    # Path traversal jauh ../../../
    with pytest.raises(ToolValidationError, match="di luar project root"):
        _resolve_write_path("../../../etc/passwd", workspace)

    # Absolute path di luar workspace
    outside_file = tmp_path / "outside_secret.txt"
    with pytest.raises(ToolValidationError, match="di luar project root"):
        _resolve_write_path(str(outside_file), workspace)
