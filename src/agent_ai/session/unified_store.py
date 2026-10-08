"""Penyimpanan persisten SQLite untuk Unified Threaded Session Architecture.

Modul ini mengelola persistensi kanonikal UnifiedSession dan UnifiedTurn
pada database SQLite global (`data/aegis.db`).
Mendukung isolasi per-project, migrasi transparan dari data legacy
`data/consultant_sessions.json`, dan operasi thread-safe.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.session.unified_models import (
    TurnExecutionData,
    UnifiedSession,
    UnifiedTurn,
    new_session_id,
    new_turn_id,
)

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def default_db_path() -> Path:
    """Ambil jalur default database global AegisCode (data/aegis.db) dengan auto-migrasi legacy 1-kali."""
    try:
        from agent_ai.config import settings

        project_root = getattr(settings, "PROJECT_ROOT", None)
        data_dir = (Path(project_root) if project_root else Path(__file__).resolve().parents[3]) / "data"
    except Exception:
        data_dir = Path(__file__).resolve().parents[3] / "data"

    aegis_db = data_dir / "aegis.db"
    aether_db = data_dir / "aether.db"
    if not aegis_db.exists() and aether_db.exists():
        try:
            import shutil
            data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(aether_db), str(aegis_db))
        except Exception:
            return aether_db
    return aegis_db

def default_legacy_json_path() -> Path:
    """Ambil jalur file JSON konsultan legacy untuk migrasi."""
    try:
        from agent_ai.config.settings import PROJECT_ROOT

        return Path(PROJECT_ROOT) / "data" / "consultant_sessions.json"
    except Exception:
        return Path(__file__).resolve().parents[3] / "data" / "consultant_sessions.json"


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS unified_sessions (
        id              TEXT PRIMARY KEY,
        project_id      TEXT,
        title           TEXT NOT NULL,
        execution_state TEXT NOT NULL DEFAULT 'idle',
        active_task_id  TEXT,
        created_at      REAL NOT NULL,
        updated_at      REAL NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_unified_sessions_project ON unified_sessions (project_id, updated_at DESC);",
    """
    CREATE TABLE IF NOT EXISTS unified_turns (
        turn_id         TEXT PRIMARY KEY,
        session_id      TEXT NOT NULL,
        role            TEXT NOT NULL,
        mode            TEXT NOT NULL,
        content         TEXT NOT NULL,
        images_json     TEXT,
        execution_json  TEXT,
        created_at      REAL NOT NULL,
        FOREIGN KEY (session_id) REFERENCES unified_sessions (id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_unified_turns_session ON unified_turns (session_id, created_at ASC);",
)


class UnifiedSessionStore:
    """Penyimpanan persisten berbasis SQLite untuk Unified Sessions."""

    def __init__(
        self,
        db_path: Optional[PathLike] = None,
        auto_migrate: bool = True,
        legacy_json_path: Optional[PathLike] = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

        if auto_migrate:
            mig_path = Path(legacy_json_path) if legacy_json_path is not None else default_legacy_json_path()
            if mig_path.exists():
                try:
                    self.migrate_from_json(mig_path)
                except Exception as exc:
                    logger.warning("Gagal melakukan migrasi transparan dari %s: %s", mig_path, exc)

    def _connect(self) -> sqlite3.Connection:
        """Buka koneksi SQLite dengan konfigurasi thread-safe dan foreign keys."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode, eksplisit transaction saat perlu
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_schema(self) -> None:
        """Inisialisasi tabel dan indeks bila belum ada."""
        with self._lock:
            with self._connect() as conn:
                for stmt in _SCHEMA_STATEMENTS:
                    conn.execute(stmt)

    # ------------------------------------------------------------------ #
    # Public API: Sesi
    # ------------------------------------------------------------------ #

    def create_session(
        self,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> UnifiedSession:
        """Buat sesi baru dan simpan ke database."""
        sid = session_id or new_session_id()
        now = time.time()
        final_title = (title or "").strip() or "New Session"

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO unified_sessions
                        (id, project_id, title, execution_state, active_task_id, created_at, updated_at)
                    VALUES (?, ?, ?, 'idle', NULL, ?, ?)
                    """,
                    (sid, project_id, final_title, now, now),
                )

        return UnifiedSession(
            session_id=sid,
            project_id=project_id,
            title=final_title,
            created_at=now,
            updated_at=now,
            turns=[],
            execution_state="idle",
            active_task_id=None,
        )

    def get_session(
        self, session_id: str, project_id: Optional[str] = None
    ) -> Optional[UnifiedSession]:
        """Ambil sesi beserta seluruh turn-nya terurut waktu."""
        if not session_id:
            return None

        with self._lock:
            with self._connect() as conn:
                cur = conn.cursor()
                if project_id:
                    cur.execute(
                        "SELECT * FROM unified_sessions WHERE id = ? AND (project_id = ? OR project_id IS NULL)",
                        (session_id, project_id),
                    )
                else:
                    cur.execute("SELECT * FROM unified_sessions WHERE id = ?", (session_id,))
                s_row = cur.fetchone()
                if not s_row:
                    return None

                cur.execute(
                    "SELECT * FROM unified_turns WHERE session_id = ? ORDER BY created_at ASC",
                    (session_id,),
                )
                turn_rows = cur.fetchall()

        turns: List[UnifiedTurn] = []
        for tr in turn_rows:
            images = None
            if tr["images_json"]:
                try:
                    images = json.loads(tr["images_json"])
                except Exception:
                    images = None

            execution = None
            if tr["execution_json"]:
                try:
                    exec_dict = json.loads(tr["execution_json"])
                    execution = TurnExecutionData.from_dict(exec_dict)
                except Exception:
                    execution = None

            turns.append(
                UnifiedTurn(
                    turn_id=tr["turn_id"],
                    role=tr["role"],
                    mode=tr["mode"],
                    content=tr["content"],
                    created_at=float(tr["created_at"]),
                    images=images,
                    execution=execution,
                )
            )

        return UnifiedSession(
            session_id=s_row["id"],
            project_id=s_row["project_id"],
            title=s_row["title"],
            created_at=float(s_row["created_at"]),
            updated_at=float(s_row["updated_at"]),
            turns=turns,
            execution_state=s_row["execution_state"],
            active_task_id=s_row["active_task_id"],
        )

    def list_sessions(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Daftar metadata sesi ringan, terbaru lebih dahulu."""
        with self._lock:
            with self._connect() as conn:
                cur = conn.cursor()
                if project_id:
                    cur.execute(
                        """
                        SELECT s.*, COUNT(t.turn_id) AS turn_count
                        FROM unified_sessions s
                        LEFT JOIN unified_turns t ON s.id = t.session_id
                        WHERE s.project_id = ? OR s.project_id IS NULL
                        GROUP BY s.id
                        ORDER BY s.updated_at DESC
                        """,
                        (project_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT s.*, COUNT(t.turn_id) AS turn_count
                        FROM unified_sessions s
                        LEFT JOIN unified_turns t ON s.id = t.session_id
                        GROUP BY s.id
                        ORDER BY s.updated_at DESC
                        """
                    )
                rows = cur.fetchall()

        results = []
        for r in rows:
            results.append(
                {
                    "session_id": r["id"],
                    "project_id": r["project_id"],
                    "title": r["title"],
                    "created_at": float(r["created_at"]),
                    "updated_at": float(r["updated_at"]),
                    "execution_state": r["execution_state"],
                    "active_task_id": r["active_task_id"],
                    "turn_count": int(r["turn_count"]),
                }
            )
        return results

    def rename_session(
        self, session_id: str, new_title: str, project_id: Optional[str] = None
    ) -> Optional[UnifiedSession]:
        """Ubah judul sesi."""
        clean_title = (new_title or "").strip()
        if not clean_title:
            return self.get_session(session_id, project_id)

        now = time.time()
        with self._lock:
            with self._connect() as conn:
                cur = conn.cursor()
                if project_id:
                    cur.execute(
                        """
                        UPDATE unified_sessions
                        SET title = ?, updated_at = ?
                        WHERE id = ? AND (project_id = ? OR project_id IS NULL)
                        """,
                        (clean_title, now, session_id, project_id),
                    )
                else:
                    cur.execute(
                        "UPDATE unified_sessions SET title = ?, updated_at = ? WHERE id = ?",
                        (clean_title, now, session_id),
                    )
                if cur.rowcount == 0:
                    return None

        return self.get_session(session_id, project_id)

    def delete_session(self, session_id: str, project_id: Optional[str] = None) -> bool:
        """Hapus sesi beserta seluruh gilirannya."""
        with self._lock:
            with self._connect() as conn:
                cur = conn.cursor()
                if project_id:
                    cur.execute(
                        "DELETE FROM unified_sessions WHERE id = ? AND (project_id = ? OR project_id IS NULL)",
                        (session_id, project_id),
                    )
                else:
                    cur.execute("DELETE FROM unified_sessions WHERE id = ?", (session_id,))
                return cur.rowcount > 0

    def reset_session(self, session_id: str, project_id: Optional[str] = None) -> bool:
        """Kosongkan seluruh giliran dalam sesi tanpa menghapus metadata sesi."""
        with self._lock:
            sess = self.get_session(session_id, project_id)
            if not sess:
                return False
            now = time.time()
            with self._connect() as conn:
                conn.execute("DELETE FROM unified_turns WHERE session_id = ?", (session_id,))
                conn.execute(
                    "UPDATE unified_sessions SET updated_at = ?, execution_state = 'idle', active_task_id = NULL WHERE id = ?",
                    (now, session_id),
                )
            return True

    def update_session_state(
        self, session_id: str, execution_state: str, active_task_id: Optional[str] = None
    ) -> None:
        """Perbarui status eksekusi sesi (idle, running, cancelling) dan task aktif."""
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE unified_sessions
                    SET execution_state = ?, active_task_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (execution_state, active_task_id, now, session_id),
                )

    # ------------------------------------------------------------------ #
    # Public API: Turn
    # ------------------------------------------------------------------ #

    def append_turn(self, session_id: str, turn: UnifiedTurn) -> UnifiedTurn:
        """Tambahkan giliran baru ke dalam sesi dan perbarui timestamp sesi."""
        with self._lock:
            sess = self.get_session(session_id)
            if not sess:
                raise ValueError(f"Sesi dengan ID '{session_id}' tidak ditemukan.")

            images_json = json.dumps(turn.images) if turn.images else None
            exec_json = json.dumps(turn.execution.to_dict()) if turn.execution else None
            now = time.time()

            # Auto-title jika judul sesi masih default dan ada turn user pertama
            next_title = sess.title
            if sess.title in ("New Session", "Sesi Baru", "") and turn.role == "user" and turn.content.strip():
                next_title = self._auto_title(turn.content.strip())

            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO unified_turns
                        (turn_id, session_id, role, mode, content, images_json, execution_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.turn_id,
                        session_id,
                        turn.role,
                        turn.mode,
                        turn.content,
                        images_json,
                        exec_json,
                        turn.created_at,
                    ),
                )
                conn.execute(
                    """
                    UPDATE unified_sessions
                    SET updated_at = ?, title = ?
                    WHERE id = ?
                    """,
                    (now, next_title, session_id),
                )

        return turn

    def update_turn_execution(
        self, session_id: str, turn_id: str, execution_data: TurnExecutionData
    ) -> None:
        """Perbarui data eksekusi untuk turn yang bersangkutan."""
        exec_json = json.dumps(execution_data.to_dict())
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE unified_turns
                    SET execution_json = ?
                    WHERE turn_id = ? AND session_id = ?
                    """,
                    (exec_json, turn_id, session_id),
                )
                conn.execute(
                    "UPDATE unified_sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )

    # ------------------------------------------------------------------ #
    # Migrasi Transparan dari Legacy Consultant Sessions
    # ------------------------------------------------------------------ #

    def migrate_from_json(self, json_path: PathLike) -> int:
        """Migrasi data sesi dari consultant_sessions.json lama ke SQLite jika belum ada."""
        p = Path(json_path)
        if not p.exists():
            return 0

        with open(p, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as exc:
                logger.warning("Gagal membaca file JSON migrasi %s: %s", p, exc)
                return 0

        sessions = data.get("sessions") if isinstance(data, dict) else None
        if not isinstance(sessions, list):
            return 0

        migrated_count = 0
        with self._lock:
            with self._connect() as conn:
                cur = conn.cursor()
                for s in sessions:
                    if not isinstance(s, dict):
                        continue
                    sid = s.get("session_id")
                    if not sid:
                        continue

                    cur.execute("SELECT 1 FROM unified_sessions WHERE id = ?", (sid,))
                    if cur.fetchone():
                        continue  # Sudah ada, jangan duplikasi

                    project_id = s.get("project_id") or None
                    title = s.get("title") or "Migrated Session"
                    created_at = float(s.get("created_at") or time.time())
                    updated_at = float(s.get("updated_at") or created_at)

                    cur.execute(
                        """
                        INSERT INTO unified_sessions
                            (id, project_id, title, execution_state, active_task_id, created_at, updated_at)
                        VALUES (?, ?, ?, 'idle', NULL, ?, ?)
                        """,
                        (sid, project_id, title, created_at, updated_at),
                    )

                    turns = s.get("turns") or []
                    for t in turns:
                        if not isinstance(t, dict):
                            continue
                        tid = new_turn_id()
                        role = t.get("role") or "user"
                        content = t.get("text") or ""
                        cur.execute(
                            """
                            INSERT INTO unified_turns
                                (turn_id, session_id, role, mode, content, images_json, execution_json, created_at)
                            VALUES (?, ?, ?, 'ask', ?, NULL, NULL, ?)
                            """,
                            (tid, sid, role, content, created_at),
                        )

                    migrated_count += 1

        if migrated_count > 0:
            logger.info("Berhasil memigrasikan %d sesi dari %s ke SQLite", migrated_count, p)
        return migrated_count

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _auto_title(text: str) -> str:
        """Hasilkan judul otomatis dari teks prompt user pertama."""
        if not text:
            return "New Session"
        first_line = text.strip().split("\n", 1)[0]
        cleaned = " ".join(first_line.split())
        return cleaned[:40] if len(cleaned) <= 40 else cleaned[:37] + "..."
