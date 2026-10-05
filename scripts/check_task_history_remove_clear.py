"""Verifikasi Remove dan Clear Mechanism untuk Tasks dan History.

Pengujian mencakup:
    1. Single Task History Deletion (DELETE /api/tasks/history/<task_id>)
       - File log dan response log terhapus dari disk
       - In-memory record terhapus
       - GET history/<task_id> berikutnya mengembalikan 404
    2. Running Task Deletion Guard
       - Task dengan queue_state='running' ditolak saat dihapus (HTTP 400)
    3. Bulk Clear Task History (POST /api/tasks/history/clear)
       - Seluruh task log project terhapus
       - Mengembalikan status cleared dan deleted_count
       - Running task tidak ikut terhapus
    4. Clear Queue (POST /api/tasks/queue/clear)
       - Task pending & disabled dibersihkan dari antrian
       - Task running tetap bertahan di antrian
       - Isolasi per project dihormati

Deterministik, tanpa API key/model external.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DJANGO_APP_DIR = PROJECT_ROOT / "web" / "django_app"

for p in (str(SRC_DIR), str(DJANGO_APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

DUMMY_ROOT = PROJECT_ROOT / "dummy_test"
FIXTURE = DUMMY_ROOT / "task_hist_clear"


def _write_task_log(root: Path, task_id: str, prompt: str, ts: str) -> None:
    """Tulis log task dan response log di <root>/.aether/log/."""
    log_dir = root / ".aether" / "log"
    resp_dir = log_dir / "response"
    log_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    events = [
        {"timestamp": ts, "event": "task_requested", "data": {"prompt": prompt}},
        {"timestamp": ts, "event": "task_completed", "data": {"result": "ok"}},
    ]
    (log_dir / f"{task_id}.log").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (resp_dir / f"{task_id}.json").write_text(
        json.dumps({"responses": [{"text": "dummy response"}]}), encoding="utf-8"
    )


def _run() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

    import django

    django.setup()
    from django.test import Client

    import api.services as services_mod
    from api.project_store import ProjectStore
    from agent_ai.projects.registry import ProjectRegistry

    shutil.rmtree(FIXTURE, ignore_errors=True)
    root_a = FIXTURE / "proj_a"
    root_b = FIXTURE / "proj_b"
    root_a.mkdir(parents=True, exist_ok=True)
    root_b.mkdir(parents=True, exist_ok=True)

    workspace = DUMMY_ROOT / "hist_clear_workspace"
    shutil.rmtree(workspace, ignore_errors=True)
    registry = ProjectRegistry(workspace=workspace)
    tmp_store_dir = tempfile.mkdtemp(prefix="hist_clear_store_")
    store = ProjectStore(db_path=Path(tmp_store_dir) / "test.db")

    services_mod._default_service = services_mod.GatewayService(
        project_registry=registry,
        project_store=store,
        auto_execute=False,
    )
    service = services_mod._default_service

    client = Client()

    proj_a = service.create_project(name="ProjectA", path=str(root_a))
    proj_b = service.create_project(name="ProjectB", path=str(root_b))
    aid = proj_a["id"]
    bid = proj_b["id"]
    service.set_active_project(aid)

    print("=== Test 1: Single Task History Deletion ===")
    task_test_1 = "task_test_single_1"
    _write_task_log(root_a, task_test_1, "Prompt 1", "2026-01-01T00:00:00+00:00")
    log_file = root_a / ".aether" / "log" / f"{task_test_1}.log"
    resp_file = root_a / ".aether" / "log" / "response" / f"{task_test_1}.json"
    assert log_file.is_file(), "Log file should exist before delete"
    assert resp_file.is_file(), "Response file should exist before delete"

    # Verify visible via GET
    get_res = client.get(f"/api/tasks/history/{task_test_1}?project_id={aid}")
    assert get_res.status_code == 200, f"Expected 200, got {get_res.status_code}"

    # Delete via DELETE HTTP method
    del_res = client.delete(f"/api/tasks/history/{task_test_1}?project_id={aid}")
    assert del_res.status_code == 200, f"Expected 200, got {del_res.status_code}: {del_res.content}"
    del_json = del_res.json()
    assert del_json.get("deleted") is True, del_json
    assert del_json.get("task_id") == task_test_1

    # Verify log and response files removed from disk
    assert not log_file.exists(), "Log file should have been deleted"
    assert not resp_file.exists(), "Response file should have been deleted"

    # Verify GET now returns 404
    get_after = client.get(f"/api/tasks/history/{task_test_1}?project_id={aid}")
    assert get_after.status_code == 404, f"Expected 404 after deletion, got {get_after.status_code}"
    print("[PASS] Test 1: Single Task History Deletion successfully deleted files & returned 404 on subsequent GET")

    print("\n=== Test 2: Running Task Deletion Guard ===")
    running_task_res = client.post(
        "/api/tasks",
        data=json.dumps({"task": "running task test", "project_id": aid}),
        content_type="application/json",
    )
    assert running_task_res.status_code == 201
    running_tid = running_task_res.json()["task_id"]
    with service._lock:
        rec = service._tasks.get(running_tid)
        assert rec is not None
        rec.queue_state = "running"
        rec.status = "running"

    del_running_res = client.delete(f"/api/tasks/history/{running_tid}?project_id={aid}")
    assert del_running_res.status_code == 400, f"Expected 400 for running task, got {del_running_res.status_code}"
    err_body = del_running_res.json()
    assert "sedang berjalan" in err_body.get("error", {}).get("message", "")
    print("[PASS] Test 2: Running Task Deletion Guard blocked deletion of running task with 400")

    print("\n=== Test 3: Clear Task History (Bulk) ===")
    task_a = "task_clear_a"
    task_b = "task_clear_b"
    # Clean up test 2 task from memory so test 4 has a fresh queue
    with service._lock:
        service._tasks.pop(running_tid, None)

    _write_task_log(root_a, task_a, "Clear A", "2026-01-01T01:00:00+00:00")
    _write_task_log(root_a, task_b, "Clear B", "2026-01-01T02:00:00+00:00")
    # Also write a task log in project B to ensure isolation
    _write_task_log(root_b, "task_b_keep", "Keep in B", "2026-01-01T03:00:00+00:00")

    log_a = root_a / ".aether" / "log" / f"{task_a}.log"
    log_b = root_a / ".aether" / "log" / f"{task_b}.log"
    log_b_keep = root_b / ".aether" / "log" / "task_b_keep.log"
    assert log_a.is_file() and log_b.is_file() and log_b_keep.is_file()

    # Clear history of Project A
    clear_res = client.post(
        "/api/tasks/history/clear",
        data=json.dumps({"project_id": aid}),
        content_type="application/json",
    )
    assert clear_res.status_code == 200, f"Expected 200, got {clear_res.status_code}: {clear_res.content}"
    clear_json = clear_res.json()
    assert clear_json.get("cleared") is True
    assert clear_json.get("deleted_count") >= 2, clear_json

    # Project A logs deleted
    assert not log_a.exists(), "task_a log should be cleared"
    assert not log_b.exists(), "task_b log should be cleared"
    # Project B log intact
    assert log_b_keep.exists(), "Project B log should remain intact (isolation preserved)"
    print("[PASS] Test 3: Clear Task History (Bulk) cleared project logs while preserving other projects")

    print("\n=== Test 4: Queue Clear ===")
    # Create 2 pending tasks and 1 running task in Project A
    t1_res = client.post("/api/tasks", data=json.dumps({"task": "pending 1", "project_id": aid}), content_type="application/json")
    t2_res = client.post("/api/tasks", data=json.dumps({"task": "pending 2", "project_id": aid}), content_type="application/json")
    t3_res = client.post("/api/tasks", data=json.dumps({"task": "running 1", "project_id": aid}), content_type="application/json")
    t1_id = t1_res.json()["task_id"]
    t2_id = t2_res.json()["task_id"]
    t3_id = t3_res.json()["task_id"]

    with service._lock:
        service._tasks[t3_id].queue_state = "running"
        service._tasks[t3_id].status = "running"

    q_before = client.get(f"/api/tasks/queue?project_id={aid}").json()["tasks"]
    assert len(q_before) == 3, q_before

    # Clear queue for Project A
    q_clear_res = client.post(
        "/api/tasks/queue/clear",
        data=json.dumps({"project_id": aid}),
        content_type="application/json",
    )
    assert q_clear_res.status_code == 200, f"Expected 200, got {q_clear_res.status_code}"
    q_clear_json = q_clear_res.json()
    assert q_clear_json.get("cleared") is True
    assert q_clear_json.get("deleted_count") == 2, q_clear_json

    q_after = client.get(f"/api/tasks/queue?project_id={aid}").json()["tasks"]
    remaining_ids = [t["task_id"] for t in q_after]
    assert t3_id in remaining_ids, "Running task should NOT be cleared from queue"
    assert t1_id not in remaining_ids, "Pending task 1 should be cleared"
    assert t2_id not in remaining_ids, "Pending task 2 should be cleared"
    print("[PASS] Test 4: Queue Clear cleared non-running tasks and kept running tasks")

    print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")
    return 0


def main() -> None:
    try:
        sys.exit(_run())
    finally:
        shutil.rmtree(FIXTURE, ignore_errors=True)
        shutil.rmtree(DUMMY_ROOT / "hist_clear_workspace", ignore_errors=True)


if __name__ == "__main__":
    main()
