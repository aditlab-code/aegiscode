"""Transparent auto-migration and decommissioning of legacy vector databases (PR-CG-3).

Safely detects and removes legacy `.aegis/vectors.db` while preserving audit trails
in `<project_root>/.aegis/log/codegraph_migration.log`.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union


def migrate_legacy_vectors(project_root: Optional[Union[str, Path]]) -> Dict[str, Any]:
    """Detect and safely remove legacy `.aegis/vectors.db` to maintain zero-orphan policy.

    Args:
        project_root: Workspace root directory.

    Returns:
        Dict describing migration status and actions taken.
    """
    if not project_root:
        return {"migrated": False, "reason": "no_project_root"}

    root = Path(project_root).resolve()
    aegis_dir = root / ".aegis"
    if not aegis_dir.exists():
        return {"migrated": False, "reason": "no_aegis_dir"}

    vector_db_path = aegis_dir / "vectors.db"
    related_files = [
        vector_db_path,
        aegis_dir / "vectors.db-wal",
        aegis_dir / "vectors.db-shm",
    ]

    existing_legacy_files = [p for p in related_files if p.exists()]
    if not existing_legacy_files:
        return {"migrated": False, "reason": "no_legacy_vectors"}

    log_dir = aegis_dir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "codegraph_migration.log"

    removed_files = []
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for p in existing_legacy_files:
        try:
            p.unlink()
            removed_files.append(str(p.name))
        except OSError:
            pass

    log_entry = (
        f"[{timestamp}] INFO: Legacy vector database detected in {aegis_dir}. "
        f"Successfully removed legacy vector files: {', '.join(removed_files)}. "
        f"Decommissioned ONNX/sqlite-vec pipeline in favor of deterministic CodeGraph (.aegis/codegraph.db).\n"
    )

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except OSError:
        pass

    return {
        "migrated": True,
        "removed_files": removed_files,
        "log_path": str(log_file),
        "status": "ok",
    }
