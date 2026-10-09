from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agent_ai.runtime.telegram.lock")


class TelegramPollerLock:
    """Process-level lock untuk memastikan hanya SATU poller thread/process yang aktif."""

    def __init__(self, lock_path: Optional[Path] = None) -> None:
        self.lock_path = lock_path or Path(".aegis/run/telegram_poller.lock")
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        """Coba acquire lock non-blocking. Kembalikan True jika berhasil, False jika proses lain memegang lock."""
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (ImportError, AttributeError):
                # Fallback di environment tanpa fcntl (misal Windows)
                pass
            except (BlockingIOError, OSError) as lock_err:
                logger.warning("Poller lock sudah dipegang proses lain: %s", lock_err)
                os.close(fd)
                return False

            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
            self._fd = fd
            return True
        except Exception as ex:
            logger.warning("Gagal mengelola file lock poller: %s", ex)
            return True  # Fallback toleran jika ada permission issue pada filesystem

    def release(self) -> None:
        """Lepaskan file lock."""
        if self._fd is not None:
            try:
                try:
                    import fcntl

                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
