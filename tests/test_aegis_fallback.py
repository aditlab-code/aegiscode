"""Unit tests verifying AegisCode runtime storage & databases."""

import tempfile
from pathlib import Path

from agent_ai.projects.aegis_store import (
    AEGIS_DIR_NAME,
    AegisProjectStore,
)
from agent_ai.llm_config.store import default_db_path


def test_aegis_store_uses_aegis_dir_when_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / AEGIS_DIR_NAME).mkdir()
        store = AegisProjectStore(root)
        assert store.aegis_dir.name == ".aegis"


def test_aegis_store_creates_aegis_dir():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = AegisProjectStore(root)
        assert store.aegis_dir.name == ".aegis"
        ok = store.ensure()
        assert ok is True
        assert (root / ".aegis").exists()
        assert (root / ".aegis" / "log").exists()
        assert (root / ".aegis" / "bible").exists()


def test_default_db_path(monkeypatch, tmp_path):
    # Setup temporary project root
    fake_project_root = tmp_path / "fake_repo"
    data_dir = fake_project_root / "data"
    data_dir.mkdir(parents=True)

    from agent_ai.config import settings

    monkeypatch.setattr(settings, "PROJECT_ROOT", str(fake_project_root))

    # Always defaults to aegis.db
    assert default_db_path().name == "aegis.db"
    (data_dir / "aegis.db").touch()
    assert default_db_path().name == "aegis.db"

def test_unified_store_auto_migrates_legacy_aether_db(monkeypatch, tmp_path):
    """Memverifikasi auto-migrasi 1-kali data/aether.db ke data/aegis.db."""
    fake_project_root = tmp_path / "fake_repo_mig"
    data_dir = fake_project_root / "data"
    data_dir.mkdir(parents=True)
    legacy_db = data_dir / "aether.db"
    legacy_db.write_text("sqlite legacy header", encoding="utf-8")

    from agent_ai.config import settings
    monkeypatch.setattr(settings, "PROJECT_ROOT", str(fake_project_root))

    from agent_ai.session.unified_store import default_db_path as unified_db_path
    resolved = unified_db_path()
    assert resolved.name == "aegis.db"
    assert (data_dir / "aegis.db").exists()
    assert (data_dir / "aegis.db").read_text(encoding="utf-8") == "sqlite legacy header"
