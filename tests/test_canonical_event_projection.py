"""Test proyeksi kanonik bersama Queue, Activity, History, dan Reasoning (Fase 1 Roadmap).

Memverifikasi:
- Queue, Activity, History, dan Report diproyeksikan dari event log dan lifecycle yang sama.
- Tidak ada parsing struktur JSON mentah vendor LLM per view.
- Reasoning diproyeksikan murni dari event canonical `agent_reasoning_delta`.
"""

import json
from pathlib import Path
from agent_ai.projects.aegis_store import AegisProjectStore, TaskLog, TaskLogReader
from api.services import GatewayService, TaskRecord
from agent_ai.runtime.lifecycle import TaskLifecycleManager, TaskLifecycleState


def test_canonical_event_projection_to_history_and_activity(tmp_path: Path):
    """Event log kanonik diproyeksikan secara deterministik ke History, Activity, dan Report."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    task_id = "canonical-task-001"

    task_log = TaskLog(project_root, task_id=task_id)
    # Tulis runtutan event lifecycle kanonik
    task_log.append("task_requested", {"prompt": "Implement canonical event projection"})
    task_log.append("task_started", {"task": "Implement canonical event projection"})
    task_log.append("tool_called", {"tool": "read_file", "target": "src/core.py"})
    task_log.append("tool_completed", {"tool": "read_file", "target": "src/core.py", "success": True})
    task_log.append("agent_reasoning_delta", {"delta": "Analyzing requirements...", "reasoning": "Analyzing requirements..."})
    task_log.append("agent_commentary", {"text": "I will proceed with the update.", "iteration": 1})
    task_log.append("task_completed", {"result": "Task completed successfully with all projections intact."})

    store = AegisProjectStore(project_root)
    reader = TaskLogReader(store, task_id=task_id)

    # 1. Proyeksi History (get_task_info)
    info = reader.get_task_info()
    assert info is not None
    assert info["task_id"] == task_id
    assert info["task"] == "Implement canonical event projection"
    assert info["status"] == "completed"
    assert "Task completed successfully" in info["result"]
    assert info["error"] is None

    # 2. Proyeksi Activity (get_activity)
    activities = reader.get_activity()
    assert len(activities) == 7
    event_names = [e["event"] for e in activities]
    assert event_names == [
        "task_requested",
        "task_started",
        "tool_called",
        "tool_completed",
        "agent_reasoning_delta",
        "agent_commentary",
        "task_completed",
    ]

    # Reasoning event harus kanonik bebas vendor payload
    reasoning_ev = [e for e in activities if e["event"] == "agent_reasoning_delta"][0]
    assert "delta" in reasoning_ev["data"]
    assert "reasoning" in reasoning_ev["data"]
    assert "candidates" not in reasoning_ev["data"]
    assert "choices" not in reasoning_ev["data"]

    # 3. Proyeksi Report (get_report)
    report = reader.get_report()
    assert report == "Task completed successfully with all projections intact."


def test_queue_and_lifecycle_projection_consistency():
    """Status antrian queue dan lifecycle state terikat secara deterministik."""
    service = GatewayService(auto_execute=False)
    task_id = "queue-task-001"
    record = TaskRecord(
        task_id=task_id,
        session_id="session-001",
        task="Test queue projection",
        status="pending",
        queue_state="pending",
    )
    lifecycle_mgr = TaskLifecycleManager(task_id=task_id, initial_state=TaskLifecycleState.PENDING.value)

    with service._lock:
        service._tasks[task_id] = record
        service._task_lifecycles[task_id] = lifecycle_mgr

    # Verifikasi status antrian awal
    queue = service.list_queue()
    matching = [t for t in queue if t["task_id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "pending"
    assert matching[0]["queue_state"] == "pending"

    # Transisi ke running
    service._update_task_status(task_id, "running")
    queue = service.list_queue()
    matching = [t for t in queue if t["task_id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "running"
    assert matching[0]["queue_state"] == "running"
    assert lifecycle_mgr.current_state == "running"

    # Transisi terminal completed
    service._update_task_status(task_id, "completed", result="All done")
    assert record.status == "completed"
    assert record.queue_state == "done"
    assert lifecycle_mgr.current_state == "completed"
    assert lifecycle_mgr.is_terminal is True

    # Di list_queue aktif, task yang sudah done tidak lagi muncul
    queue = service.list_queue()
    assert all(t["task_id"] != task_id for t in queue)
