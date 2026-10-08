"""Unit tests for transparent legacy vector migration and zero-orphan decommissioning (PR-CG-3)."""

from __future__ import annotations

from pathlib import Path

from agent_ai.codegraph.migration import migrate_legacy_vectors
from agent_ai.codegraph.service import CodeGraphService


def test_migrate_legacy_vectors_decommissioning(tmp_path: Path):
    aegis_dir = tmp_path / ".aegis"
    aegis_dir.mkdir(parents=True)

    # Simulate legacy vector DB files
    vec_db = aegis_dir / "vectors.db"
    vec_wal = aegis_dir / "vectors.db-wal"
    vec_db.write_text("dummy-vector-binary-content", encoding="utf-8")
    vec_wal.write_text("dummy-wal-content", encoding="utf-8")

    assert vec_db.exists()
    assert vec_wal.exists()

    # Perform migration
    res = migrate_legacy_vectors(tmp_path)
    assert res["migrated"] is True
    assert "vectors.db" in res["removed_files"]
    assert "vectors.db-wal" in res["removed_files"]
    assert not vec_db.exists()
    assert not vec_wal.exists()

    # Check audit log in .aegis/log/
    log_file = aegis_dir / "log" / "codegraph_migration.log"
    assert log_file.exists()
    log_content = log_file.read_text(encoding="utf-8")
    assert "Legacy vector database detected" in log_content
    assert "Successfully removed legacy vector files" in log_content

    # Idempotent second run
    res2 = migrate_legacy_vectors(tmp_path)
    assert res2["migrated"] is False


def test_service_transparent_auto_migration(tmp_path: Path):
    aegis_dir = tmp_path / ".aegis"
    aegis_dir.mkdir(parents=True)

    legacy_db = aegis_dir / "vectors.db"
    legacy_db.write_text("legacy-sqlite-vec-data", encoding="utf-8")

    # Initializing CodeGraphService must trigger auto-migration transparently
    service = CodeGraphService(project_root=tmp_path)
    try:
        assert not legacy_db.exists()
        assert (aegis_dir / "codegraph.db").exists()
        assert (aegis_dir / "log" / "codegraph_migration.log").exists()
    finally:
        service.close()
