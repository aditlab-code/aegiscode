"""Tests for Dual-Entity Synchronization (Queue/Task vs Unified Threads)."""

import time
import pytest
from agent_ai.session.unified_models import UnifiedTurn, new_turn_id
from agent_ai.session.unified_store import UnifiedSessionStore
from apps.django_app.api.services import GatewayService


def test_dual_entity_turn_sync(tmp_path) -> None:
    db_path = str(tmp_path / "test_aegis.db")
    u_store = UnifiedSessionStore(db_path=db_path)

    # Inisialisasi session baru
    session_id = "test-session-sync"
    u_store.create_session(session_id=session_id, title="Test Thread")

    service = GatewayService(
        auto_execute=False,
        unified_session_store=u_store,
    )

    # Buat agent turn via create_unified_turn
    turn_res = service.create_unified_turn(
        session_id=session_id,
        content="Fix failing test",
        mode="agent",
    )

    task_info = turn_res.get("task")
    assert task_info is not None
    task_id = task_info["task_id"]

    # Pastikan task masuk ke queue dan thread tercatat dengan task_id
    sess = u_store.get_session(session_id)
    assert sess is not None
    assert sess.execution_state == "running"
    assert sess.active_task_id == task_id

    # Temukan assistant turn
    asst_turn = None
    for turn in sess.turns:
        if turn.execution and turn.execution.task_id == task_id:
            asst_turn = turn
            break
    assert asst_turn is not None
    assert asst_turn.execution.status in ("prepared", "pending", "running", "created")

    # Update status task ke completed via service
    service._update_task_status(task_id, "completed", result="All tests passed")

    # Pastikan UnifiedSessionStore terupdate secara sinkron
    sess_after = u_store.get_session(session_id)
    assert sess_after.execution_state == "idle"
    assert sess_after.active_task_id is None

    updated_turn = None
    for turn in sess_after.turns:
        if turn.execution and turn.execution.task_id == task_id:
            updated_turn = turn
            break
    assert updated_turn is not None
    assert updated_turn.execution.status == "completed"
    assert updated_turn.execution.report == "All tests passed"
