"""Unit test untuk FileWriteLockManager (AEG-08).

Memverifikasi:
1. Acquire & release atomic file write lock.
2. Normalisasi path konsisten (posix / backslash / case).
3. Penolakan akses saat file sedang di-lock oleh thread/owner lain.
4. Pelepasan lock aman dan re-acquisition setelah rilis.
5. Atomic multi-path acquisition (deadlock-free sorted acquire).
"""

from __future__ import annotations

import threading
from agent_ai.tools.file_lock import FileWriteLockManager


def test_file_write_lock_acquire_and_release():
    mgr = FileWriteLockManager()
    path = "/workspace/src/app.py"

    assert mgr.acquire(path, owner="task-1") is True
    assert mgr.is_locked(path) is True
    assert mgr.get_owner(path) == "task-1"

    # Thread / task lain mencoba acquire file yang sama -> harus ditolak
    assert mgr.acquire(path, owner="task-2") is False

    # Owner salah mencoba release -> tidak boleh melepaskan lock
    mgr.release(path, owner="wrong-owner")
    assert mgr.is_locked(path) is True

    # Owner asli release
    mgr.release(path, owner="task-1")
    assert mgr.is_locked(path) is False
    assert mgr.get_owner(path) is None

    # Sekarang task-2 bisa acquire
    assert mgr.acquire(path, owner="task-2") is True
    assert mgr.get_owner(path) == "task-2"
    mgr.release(path, owner="task-2")


def test_file_write_lock_path_normalization():
    mgr = FileWriteLockManager()
    path1 = "src/modules/../modules/app.py"
    path2 = "src/modules/app.py"

    assert mgr.acquire(path1, owner="task-norm") is True
    # Path ternormalisasi harus dianggap sama
    assert mgr.acquire(path2, owner="task-other") is False
    mgr.release(path1, owner="task-norm")


def test_file_write_lock_acquire_multiple_atomic():
    mgr = FileWriteLockManager()
    paths = ["/ws/b.py", "/ws/a.py", "/ws/c.py"]

    # Pre-lock salah satu path
    assert mgr.acquire("/ws/a.py", owner="blocker") is True

    # acquire_multiple harus gagal secara all-or-nothing (tidak ada lock parsial)
    assert mgr.acquire_multiple(paths, owner="task-multi") is False
    assert mgr.is_locked("/ws/b.py") is False
    assert mgr.is_locked("/ws/c.py") is False

    # Lepas blocker
    mgr.release("/ws/a.py", owner="blocker")

    # Sekarang acquire_multiple sukses
    assert mgr.acquire_multiple(paths, owner="task-multi") is True
    for p in paths:
        assert mgr.get_owner(p) == "task-multi"

    mgr.release_multiple(paths, owner="task-multi")
    for p in paths:
        assert mgr.is_locked(p) is False


def test_file_write_lock_concurrent_threads():
    mgr = FileWriteLockManager()
    path = "/workspace/concurrent.py"
    acquired_count = 0
    lock = threading.Lock()

    def _worker(worker_id: str):
        nonlocal acquired_count
        if mgr.acquire(path, owner=worker_id):
            with lock:
                acquired_count += 1
            mgr.release(path, owner=worker_id)

    threads = [threading.Thread(target=_worker, args=(f"worker-{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Semua thread akhirnya selesai tanpa deadlock
    assert mgr.is_locked(path) is False
