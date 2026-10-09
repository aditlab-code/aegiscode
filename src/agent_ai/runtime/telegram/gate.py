from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent_ai.runtime.telegram.security import TelegramSecurityManager

logger = logging.getLogger("agent_ai.runtime.telegram.gate")


@dataclass
class GateDecision:
    """Hasil evaluasi izin giliran inbound Telegram."""

    allowed: bool
    reason: Optional[str] = None
    active_task_id: Optional[str] = None
    session_id: Optional[str] = None


class TelegramContextGate:
    """Pintu gerbang tunggal (Single Source of Truth) untuk resolusi chat_id,

    pelacakan task_id aktif, pemetaan sesi, dan cache retry prompt.
    """

    def __init__(self, security_manager: Optional[TelegramSecurityManager] = None) -> None:
        self.security_manager = security_manager or TelegramSecurityManager()
        self._lock = threading.RLock()
        self._active_tasks: Dict[int, Dict[str, Any]] = {}
        self._retry_cache: Dict[str, Dict[str, Any]] = {}

    def resolve_chat_id(self, explicit_chat_id: Optional[int] = None) -> Optional[int]:
        """Mengambil chat_id target dari parameter eksplisit, user berpasangan

        di TelegramSecurityManager, atau daftar env_allowed_ids.
        """
        if explicit_chat_id is not None:
            return int(explicit_chat_id)

        paired = self.security_manager.load_paired_user()
        if paired and paired.user_id:
            return paired.user_id

        if self.security_manager.env_allowed_ids:
            return sorted(list(self.security_manager.env_allowed_ids))[0]

        return None

    def register_task(
        self,
        chat_id: int,
        task_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Mendaftarkan tugas otonom yang sedang berjalan untuk chat terkait."""
        with self._lock:
            self._active_tasks[int(chat_id)] = {
                "task_id": task_id,
                "session_id": session_id,
                "started_at": time.time(),
            }
            logger.info("Task %s registered for chat %s", task_id, chat_id)

    def get_active_task(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Membaca metadata task aktif untuk chat tertentu."""
        with self._lock:
            task = self._active_tasks.get(int(chat_id))
            if task:
                return dict(task)
            return None

    def complete_task(self, chat_id: int, task_id: str) -> None:
        """Menghapus binding task setelah selesai/gagal."""
        with self._lock:
            active = self._active_tasks.get(int(chat_id))
            if active and active.get("task_id") == task_id:
                self._active_tasks.pop(int(chat_id), None)
                logger.info("Task %s completed and removed for chat %s", task_id, chat_id)
            elif active:
                # Jika task_id berbeda, tetap hapus jika diminta paksa
                logger.warning(
                    "Task ID mismatch during completion for chat %s (expected %s, got %s)",
                    chat_id,
                    active.get("task_id"),
                    task_id,
                )
                self._active_tasks.pop(int(chat_id), None)

    def gate_inbound_turn(
        self,
        chat_id: int,
        content: str,
        username: Optional[str] = None,
    ) -> GateDecision:
        """Memeriksa otorisasi pengguna dan apakah ada task otonom yang sedang berjalan."""
        if not self.security_manager.is_authorized(chat_id, username=username):
            return GateDecision(
                allowed=False,
                reason="Unauthorized user",
            )

        with self._lock:
            active = self._active_tasks.get(int(chat_id))
            if active:
                return GateDecision(
                    allowed=False,
                    reason="Task is currently running",
                    active_task_id=active.get("task_id"),
                    session_id=active.get("session_id"),
                )

        return GateDecision(allowed=True)

    def save_retry_prompt(
        self,
        cache_id: str,
        instruction: str,
        chat_id: int,
        error: str = "",
    ) -> None:
        """Manajemen cache retry prompt dengan TTL 10 menit (600 detik)."""
        with self._lock:
            self._retry_cache[cache_id] = {
                "cache_id": cache_id,
                "instruction": instruction,
                "chat_id": int(chat_id),
                "error": error,
                "created_at": time.time(),
            }
            logger.debug("Saved retry prompt %s for chat %s", cache_id, chat_id)

    def pop_retry_prompt(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """Mengambil dan membersihkan entri retry cache jika belum kedaluwarsa."""
        with self._lock:
            entry = self._retry_cache.pop(cache_id, None)
            if not entry:
                return None
            if time.time() - entry.get("created_at", 0) > 600:
                logger.debug("Retry prompt %s expired", cache_id)
                return None
            return entry
