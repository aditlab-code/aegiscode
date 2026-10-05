"""Unit tests untuk mekanisme terminasi server AegisCode (Zero-Zombie process tree kill).

Memverifikasi:
1. ServerLifecycleManager: pendaftaran sesi PTY, pembersihan massal, dan pembatalan task.
2. Endpoint API Gateway: POST /api/server/terminate merespons 200 dengan payload valid.
3. Supervisor Process Tree-Kill: penghentian proses anak dan eskalasi SIGTERM -> SIGKILL.
4. CLI --terminate pada scripts/install_aegis.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client

# Pastikan web/django_app dan src berada di sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
DJANGO_APP_DIR = REPO_ROOT / "web" / "django_app"
SRC_DIR = REPO_ROOT / "src"

for p in (str(DJANGO_APP_DIR), str(SRC_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from api.lifecycle import ServerLifecycleManager, get_lifecycle_manager
from scripts.install_aegis import main as installer_main, terminate_process_tree, terminate_running_server


class DummyPTY:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_lifecycle_manager_registration_and_termination() -> None:
    manager = ServerLifecycleManager()
    pty1 = DummyPTY()
    pty2 = DummyPTY()

    manager.register_pty(pty1)
    manager.register_pty(pty2)
    assert manager.active_pty_count() == 2

    manager.unregister_pty(pty1)
    assert manager.active_pty_count() == 1

    summary = manager.terminate_all_subprocesses()
    assert summary["terminated_ptys"] == 1
    assert pty2.terminated is True
    assert manager.active_pty_count() == 0
    assert manager.is_shutting_down is True


def test_lifecycle_manager_async_trigger_shutdown() -> None:
    manager = ServerLifecycleManager()
    pty = DummyPTY()
    manager.register_pty(pty)

    thread = manager.trigger_server_shutdown(delay=0.01, exit_process=False)
    thread.join(timeout=2.0)

    assert pty.terminated is True
    assert manager.is_shutting_down is True


def test_server_terminate_endpoint_contract() -> None:
    client = Client()
    response = client.post(
        "/api/server/terminate",
        data=json.dumps({"force": False}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "terminating"
    assert "pid" in data
    assert "Penghentian server AegisCode" in data.get("message", "")


def test_terminate_process_tree_kills_subprocess() -> None:
    # Spawn proses dummy sleep dalam session sendiri
    kwargs = {}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    try:
        assert proc.poll() is None
        terminate_process_tree(proc, timeout=1.0)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_terminate_running_server_inactive_port() -> None:
    # Port acak yang tidak aktif harus mengembalikan True
    result = terminate_running_server("127.0.0.1", 65431, timeout=1.0)
    assert result is True


def test_cli_terminate_argument() -> None:
    # Menjalankan installer dengan --terminate pada port yang tidak aktif
    code = installer_main(["--terminate", "--port", "65430"])
    assert code == 0
