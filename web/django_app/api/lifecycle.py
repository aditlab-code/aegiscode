"""Manajer siklus hidup server AegisCode (Zero-Zombie Lifecycle).

Memastikan seluruh sub-proses latar belakang (sesi PTY, task agen yang sedang
berjalan, dan file descriptor master/slave) dibersihkan secara deterministik saat
server dihentikan melalui antarmuka pengguna, panggilan API, maupun sinyal OS.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import signal
import sys
import threading
import time
from typing import Any, Optional, Set

logger = logging.getLogger(__name__)

class ServerLifecycleManager:
    """Pengawas siklus hidup dan pembersihan sub-proses server AegisCode."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pty_sessions: Set[Any] = set()
        self._is_shutting_down = False

    @property
    def is_shutting_down(self) -> bool:
        with self._lock:
            return self._is_shutting_down

    def register_pty(self, session: Any) -> None:
        """Daftarkan sesi PTY aktif ke registry."""
        with self._lock:
            self._pty_sessions.add(session)

    def unregister_pty(self, session: Any) -> None:
        """Hapus sesi PTY dari registry saat ditutup."""
        with self._lock:
            self._pty_sessions.discard(session)

    def active_pty_count(self) -> int:
        with self._lock:
            return len(self._pty_sessions)

    def terminate_all_subprocesses(self) -> dict[str, int]:
        """Hentikan seluruh sesi PTY dan batalkan task yang sedang berjalan."""
        with self._lock:
            self._is_shutting_down = True
            sessions = list(self._pty_sessions)
            self._pty_sessions.clear()

        # 1. Hentikan seluruh sesi PTY secara paralel (lepaskan slave/master fd dan bunuh shell process)
        terminated_ptys = 0
        if sessions:
            def _terminate_one(pty: Any) -> bool:
                try:
                    if hasattr(pty, "terminate"):
                        pty.terminate()
                        return True
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Gagal menghentikan sesi PTY: %s", exc)
                return False

            max_workers = min(len(sessions), 8)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            try:
                futures = [executor.submit(_terminate_one, p) for p in sessions]
                done, not_done = concurrent.futures.wait(futures, timeout=2.0)
                for f in done:
                    try:
                        if f.result():
                            terminated_ptys += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Error saat menunggu terminasi PTY: %s", exc)
                if not_done:
                    logger.warning(
                        "%d sesi PTY tidak selesai dalam batas timeout 2.0s",
                        len(not_done),
                    )
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
        # 2. Batalkan task agen yang sedang berjalan di GatewayService
        cancelled_tasks = 0
        try:
            from api.services import get_service

            service = get_service()
            if hasattr(service, "cancel_all_tasks"):
                cancelled_tasks = service.cancel_all_tasks()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gagal membatalkan task aktif: %s", exc)

        logger.info(
            "Terminasi sub-proses selesai: %d PTY, %d task dibatalkan.",
            terminated_ptys,
            cancelled_tasks,
        )
        return {
            "terminated_ptys": terminated_ptys,
            "cancelled_tasks": cancelled_tasks,
        }

    def trigger_server_shutdown(
        self,
        delay: float = 0.3,
        *,
        exit_process: bool = True,
    ) -> threading.Thread:
        """Jalankan thread asinkron untuk menghentikan server setelah response HTTP terkirim."""
        def _worker() -> None:
            if delay > 0:
                time.sleep(delay)
            self.terminate_all_subprocesses()

            # Bila exit_process diaktifkan dan bukan di lingkungan pengujian
            is_test = (
                bool(os.environ.get("PYTEST_CURRENT_TEST"))
                or "pytest" in sys.modules
            )
            if exit_process and not is_test:
                pid = os.getpid()
                try:
                    if hasattr(signal, "SIGTERM"):
                        os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass

                # Fallback bila proses tidak langsung berhenti
                time.sleep(1.0)
                try:
                    os._exit(0)
                except Exception:
                    pass

        thread = threading.Thread(
            target=_worker,
            name="aegis-server-shutdown",
            daemon=True,
        )
        thread.start()
        return thread


# Singleton global
_instance: Optional[ServerLifecycleManager] = None
_instance_lock = threading.Lock()


def get_lifecycle_manager() -> ServerLifecycleManager:
    """Dapatkan instance tunggal ServerLifecycleManager."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ServerLifecycleManager()
    return _instance
