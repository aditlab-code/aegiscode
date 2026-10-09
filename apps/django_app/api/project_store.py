"""SQLite store untuk Project Launcher & Active Project (layer gateway).

Persistence MINIMAL di layer web/gateway (bukan Aegis Core). Menyimpan:
    - daftar project yang pernah ditambahkan (untuk Project Launcher),
    - state active project (single-user local app; bukan login/session user).

PENTING:
    - TIDAK ada database server / dependency tambahan (hanya sqlite3 stdlib).
    - TIDAK menghapus filesystem project. Delete hanya menghapus record.
    - TIDAK menduplikasi ProjectRegistry Aegis: registry tetap sumber
      kebenaran struktur project (project.json + intelligence). Store ini
      hanya menyimpan metadata launcher + active project state.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_ai.projects.models import _now_iso


def _default_db_path() -> Path:
    """Lokasi default database AegisCode: <repo>/data/aegis.db."""
    # api/project_store.py -> api/ -> django_app/ -> web/ -> repo root
    repo_root = Path(__file__).resolve().parents[3]
    base = repo_root / "data"
    return base / "aegis.db"


class ProjectStore:
    """Store SQLite untuk project launcher + active project state.

    Args:
        db_path: lokasi file SQLite (default: <repo>/data/aegis.db).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Connection / schema
    # ------------------------------------------------------------------ #
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_opened_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # Projects
    # ------------------------------------------------------------------ #
    def add_project_with_id(self, project_id: str, name: str, path: str) -> Dict[str, Any]:
        """Simpan metadata launcher dengan id eksplisit (id dari registry Aegis).

        Id diselaraskan dengan ProjectRegistry Aegis agar satu identitas
        project (tidak ada registry kedua). Tidak menyentuh filesystem.
        """
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects"
                " (id, name, path, created_at, updated_at, last_opened_at)"
                " VALUES (?, ?, ?,"
                " COALESCE((SELECT created_at FROM projects WHERE id = ?), ?), ?, ?)",
                (project_id, name, path, project_id, now, now, now),
            )
            conn.commit()
        return self.get_project(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        """Daftar project, terbaru dibuka/diubah lebih dulu."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects"
                " ORDER BY COALESCE(last_opened_at, updated_at) DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Ambil project berdasarkan id (None bila tidak ada)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_project(self, project_id: str) -> bool:
        """Hapus RECORD project dari SQLite. TIDAK menghapus filesystem.

        Returns:
            True bila ada record yang dihapus, False bila tidak ditemukan.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            deleted = cur.rowcount > 0
            # Bersihkan active project bila menunjuk ke project yang dihapus.
            if deleted:
                active = conn.execute(
                    "SELECT value FROM app_state WHERE key = 'active_project_id'"
                ).fetchone()
                if active and active["value"] == project_id:
                    conn.execute(
                        "DELETE FROM app_state WHERE key = 'active_project_id'"
                    )
                    conn.commit()
        return deleted

    def touch_opened(self, project_id: str) -> None:
        """Update last_opened_at + updated_at sebuah project."""
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE projects SET last_opened_at = ?, updated_at = ? WHERE id = ?",
                (now, now, project_id),
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # Active project state
    # ------------------------------------------------------------------ #
    def set_active_project(self, project_id: str) -> None:
        """Simpan active project id (persistent)."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES ('active_project_id', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (project_id,),
            )
            conn.commit()

    def get_active_project_id(self) -> Optional[str]:
        """Ambil active project id (None bila tidak ada)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = 'active_project_id'"
            ).fetchone()
        return row["value"] if row else None

    def clear_active_project(self) -> None:
        """Hapus active project state (Close Project)."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM app_state WHERE key = 'active_project_id'")
            conn.commit()

    # ------------------------------------------------------------------ #
    # Operational mode state (ask vs agents)
    # ------------------------------------------------------------------ #
    def get_operational_mode(self, default: str = "ask") -> str:
        """Ambil operational mode saat ini ('ask' atau 'agents')."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = 'operational_mode'"
            ).fetchone()
        return row["value"] if row and row["value"] else default

    def set_operational_mode(self, mode: str) -> str:
        """Simpan operational mode ('ask' atau 'agents').

        Raises:
            ValueError: jika mode bukan 'ask' atau 'agents'.
        """
        clean_mode = str(mode).strip().lower()
        if clean_mode not in ("ask", "agents"):
            raise ValueError(f"Operational mode tidak valid: '{mode}'. Harus 'ask' atau 'agents'.")
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES ('operational_mode', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (clean_mode,),
            )
            conn.commit()
        return clean_mode

    # ------------------------------------------------------------------ #
    # Active LLM provider state
    # ------------------------------------------------------------------ #
    def get_active_provider(self) -> Optional[str]:
        """Ambil active provider id (None bila tidak ada)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = 'active_provider_id'"
            ).fetchone()
        return row["value"] if row else None

    def set_active_provider(self, provider_id: str) -> None:
        """Simpan active provider id."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES ('active_provider_id', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (provider_id,),
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # Active LLM model state
    # ------------------------------------------------------------------ #
    def get_active_model(self) -> Optional[str]:
        """Ambil active model id/name (None bila tidak ada)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = 'active_model_id'"
            ).fetchone()
        return row["value"] if row else None

    def set_active_model(self, model_name: str) -> None:
        """Simpan active model id/name."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES ('active_model_id', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (model_name.strip(),),
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # Active Skill state
    # ------------------------------------------------------------------ #
    def get_active_skill(self) -> Optional[str]:
        """Ambil active skill name (None bila tidak ada)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = 'active_skill'"
            ).fetchone()
        return row["value"] if row else None

    def set_active_skill(self, skill_name: str) -> None:
        """Simpan active skill name."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES ('active_skill', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (skill_name.strip(),),
            )
            conn.commit()

