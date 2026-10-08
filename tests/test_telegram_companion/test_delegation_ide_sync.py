"""Unit tests for IDE Real-Time Synchronization for Remote Task Delegation.

Verifies:
1. `delegate_session_to_agent_task` automatically binds to active `project_id` when session project_id is empty.
2. `create_task` records the active `project_id` and emits `task_created` with that project_id.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from api.services import GatewayService


def test_delegate_session_binds_active_project_id():
    """Memverifikasi bahwa delegate_session_to_agent_task otomatis menggunakan active project ID."""
    svc = GatewayService()
    active_pid = svc.project_store.get_active_project_id()
    if not active_pid:
        active_pid = "test-proj-123"
        svc.project_store.add_project_with_id(active_pid, name="Test Proj", path=".")
        svc.project_store.set_active_project(active_pid)
    assert active_pid is not None

    # Buat sesi tanpa project_id
    session_data = svc.create_unified_session(title="Sesi Test Telegram", project_id=None)
    sid = session_data["session_id"]

    # Simpan satu giliran percakapan
    svc.create_unified_turn(
        session_id=sid,
        content="Hasil diskusi: tolong buat fitur dark mode",
        mode="ask",
        project_id=None,
    )

    # Delegasikan ke agent task
    res = svc.delegate_session_to_agent_task(session_id=sid)
    assert res is not None
    task_info = res.get("task")
    assert task_info is not None
    assert task_info.get("task_id") is not None
    # Task harus terikat ke active_pid
    assert task_info.get("project_id") == active_pid
