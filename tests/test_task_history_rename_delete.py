import os
import shutil
import tempfile
from pathlib import Path
import pytest

from agent_ai.projects.aegis_store import AegisProjectStore, TaskLog, TaskLogReader
from api.services import GatewayService, NotFoundError, ValidationError


@pytest.fixture
def temp_project():
    d = tempfile.mkdtemp(prefix="test_aegis_task_hist_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_task_log_reader_respects_task_renamed(temp_project):
    store = AegisProjectStore(temp_project)
    task_id = "test-task-123"
    task_log = TaskLog(temp_project, task_id=task_id)

    task_log.append("task_requested", {"prompt": "Initial Prompt"})
    task_log.append("task_started", {})
    task_log.append("task_completed", {"result": "Done"})

    reader = TaskLogReader(temp_project, task_id=task_id)
    info = reader.get_task_info()
    assert info is not None
    assert info["task"] == "Initial Prompt"
    assert info["status"] == "completed"

    # Append rename event
    task_log.append("task_renamed", {"title": "Updated Custom Title"})

    reader2 = TaskLogReader(temp_project, task_id=task_id)
    info2 = reader2.get_task_info()
    assert info2 is not None
    assert info2["task"] == "Updated Custom Title"
    assert info2["status"] == "completed"


def test_gateway_service_rename_and_delete_task_history(temp_project):
    service = GatewayService()
    task_id = "task-hist-456"

    # Create dummy project log
    store = AegisProjectStore(temp_project)
    task_log = TaskLog(temp_project, task_id=task_id)
    task_log.append("task_requested", {"prompt": "Original prompt message"})
    task_log.append("task_completed", {"result": "ok"})

    # Rename via service with project_id as root path
    res = service.rename_task_history(task_id, "New Renamed Task", project_id=str(temp_project))
    assert res["task_id"] == task_id
    assert res["task"] == "New Renamed Task"
    assert res["renamed"] is True

    # Check reading back task history
    hist = service.get_task_history(task_id, project_id=str(temp_project))
    assert hist["task"] == "New Renamed Task"

    # Validation error on empty title
    with pytest.raises(ValidationError):
        service.rename_task_history(task_id, "   ", project_id=str(temp_project))

    # Delete task history
    del_res = service.delete_task_history(task_id, project_id=str(temp_project))
    assert del_res["task_id"] == task_id
    assert del_res["deleted"] is True

    # Re-reading or renaming deleted task raises NotFoundError
    with pytest.raises(NotFoundError):
        service.rename_task_history(task_id, "Another Title", project_id=str(temp_project))
