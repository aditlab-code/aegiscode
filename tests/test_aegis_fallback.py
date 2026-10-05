"""Unit tests verifying backward-compatible fallback for AegisCode runtime storage & databases."""

import tempfile
from pathlib import Path

from agent_ai.projects.aether_store import (
    AEGIS_DIR_NAME,
    AETHER_DIR_NAME,
    AegisProjectStore,
    AetherProjectStore,
)
from agent_ai.llm_config.store import default_db_path


def test_aegis_store_uses_aegis_dir_when_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / AEGIS_DIR_NAME).mkdir()
        store = AegisProjectStore(root)
        assert store.aegis_dir.name == ".aegis"
        assert store.aether_dir.name == ".aegis"


def test_aegis_store_falls_back_to_aether_dir_when_only_aether_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / AETHER_DIR_NAME).mkdir()
        store = AegisProjectStore(root)
        assert store.aegis_dir.name == ".aether"
        assert store.aether_dir.name == ".aether"


def test_aegis_store_creates_aegis_dir_when_neither_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = AegisProjectStore(root)
        assert store.aegis_dir.name == ".aegis"
        ok = store.ensure()
        assert ok is True
        assert (root / ".aegis").exists()
        assert (root / ".aegis" / "log").exists()
        assert (root / ".aegis" / "bible").exists()


def test_default_db_path_fallback_logic(monkeypatch, tmp_path):
    # Setup temporary project root
    fake_project_root = tmp_path / "fake_repo"
    data_dir = fake_project_root / "data"
    data_dir.mkdir(parents=True)

    from agent_ai.config import settings

    monkeypatch.setattr(settings, "PROJECT_ROOT", str(fake_project_root))

    # Case 1: Neither exists -> default to aegis.db
    assert default_db_path().name == "aegis.db"

    # Case 2: Only aether.db exists -> fallback to aether.db
    (data_dir / "aether.db").touch()
    assert default_db_path().name == "aether.db"

    # Case 3: aegis.db exists -> prioritize aegis.db
    (data_dir / "aegis.db").touch()
    assert default_db_path().name == "aegis.db"
