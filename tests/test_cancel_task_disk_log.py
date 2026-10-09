"""Tests: Pembatalan task dari disk log (stale task cancellation).

Memverifikasi:
1. TaskLogReader memiliki metode read_events() sebagai alias dari load_events().
2. AgentService.cancel_task() dapat membatalkan task yang tidak ada di in-memory _tasks
   tetapi ada di file log .aegis/log/<task_id>.log tanpa AttributeError.
3. Event task_cancelled tercatat di disk log setelah pembatalan task stale.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
DJANGO_DIR = Path(__file__).resolve().parent.parent / "apps" / "django_app"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(DJANGO_DIR) not in sys.path:
    sys.path.insert(0, str(DJANGO_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

from agent_ai.projects.aegis_store import AegisProjectStore, TaskLog, TaskLogReader
from api.services import GatewayService


def test_task_log_reader_read_events_alias(tmp_path: Path):
    store = AegisProjectStore(tmp_path)
    store.ensure()
    task_id = "test-task-123"

    writer = TaskLog(store, task_id)
    writer.append("task_requested", {"prompt": "Halo dunia"})
    writer.append("task_started")

    reader = TaskLogReader(store, task_id)
    assert hasattr(reader, "read_events")
    events_load = reader.load_events()
    events_read = reader.read_events()

    assert len(events_read) == 2
    assert events_read == events_load
    assert events_read[0]["event"] == "task_requested"


def test_gateway_service_cancel_stale_task_from_disk(tmp_path: Path):
    project_root = tmp_path / "my_project"
    project_root.mkdir()
    store = AegisProjectStore(project_root)
    store.ensure()

    task_id = "stale-task-456"
    writer = TaskLog(store, task_id)
    writer.append("task_requested", {"prompt": "Tugas berjalan lama"})
    writer.append("task_started")

    # Inisialisasi GatewayService
    service = GatewayService()
    # Daftarkan project agar _find_log_file bisa menemukan lognya
    service.create_project(name="My Project", path=str(project_root))

    # Pastikan task TIDAK ada di in-memory _tasks
    assert task_id not in service._tasks

    # Panggil cancel_task
    result = service.cancel_task(task_id)

    assert result["task_id"] == task_id
    assert result["status"] == "cancelled"
    assert result["prompt"] == "Tugas berjalan lama"

    # Verifikasi bahwa event task_cancelled tercatat di disk log
    reader = TaskLogReader(store, task_id)
    events = reader.load_events()
    assert any(e.get("event") == "task_cancelled" for e in events)
