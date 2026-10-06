"""Tests untuk Provider-Aware 3-Tier Brain/Bible Discovery (Opsi 2).

Memastikan:
1. Pemisahan knowledge (.brain/) dan runtime log (.aegis/log/).
2. Layered discovery: .brain/ -> .aegis/bible/ -> .aether/bible/.
3. Provider Antigravity secara otomatis memprioritaskan .brain/.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agent_ai.projects.aegis_store import AegisProjectStore, BibleStore, BRAIN_DIR_NAME
from agent_ai.projects.brain import ProjectBrain
from agent_ai.projects.intelligence import ProjectIntelligence
from agent_ai.projects.models import IntelligenceEntry
from agent_ai.providers.antigravity import AntigravityConfig, AntigravityProvider, _format_antigravity_policy_directive


def test_brain_store_defaults_to_brain_when_directory_exists(tmp_path: Path) -> None:
    """Bila <root>/.brain/ ada di filesystem, BibleStore otomatis memakainya."""
    brain_dir = tmp_path / BRAIN_DIR_NAME
    brain_dir.mkdir(parents=True)
    (brain_dir / "architecture.md").write_text(
        "# bible:architecture\n\n## entry\n- id: arch-1\n- source: test\n- confidence: 1.0\n- created_at: 2026-01-01T00:00:00\n- updated_at: 2026-01-01T00:00:00\n- content: {\"summary\": \"Modular Layer\"}\n",
        encoding="utf-8",
    )

    store = AegisProjectStore(tmp_path)
    assert store.bible_dir == brain_dir.resolve()

    bible = BibleStore(tmp_path)
    entries = bible.read_category("architecture")
    assert len(entries) == 1
    assert entries[0].id == "arch-1"
    assert entries[0].content["summary"] == "Modular Layer"


def test_antigravity_provider_activates_brain_store(tmp_path: Path) -> None:
    """ProjectBrain dengan provider antigravity mengarahkan knowledge ke .brain/."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    provider = AntigravityProvider(config=cfg)

    brain = ProjectBrain.for_project(tmp_path, provider=provider)
    assert brain.intelligence.uses_bible
    # Pastikan target direktori mengarah ke .brain
    assert brain.intelligence._bible.store.bible_dir == (tmp_path / BRAIN_DIR_NAME).resolve()

    # Simpan entri baru dan pastikan tersimpan di .brain/
    entry = IntelligenceEntry(content={"runtime": "Python 3.12"}, source="test")
    brain.intelligence._bible.add_entry("facts", entry)

    assert (tmp_path / ".brain" / "facts.md").exists()
    # Pastikan folder log runtime tetap terisolasi di .aegis/log
    assert not (tmp_path / ".brain" / "log").exists()


def test_layered_fallback_to_aegis_and_aether(tmp_path: Path) -> None:
    """Fallback transparan membaca knowledge dari .aegis/bible/ dan .aether/bible/."""
    # 1. Fallback ke .aegis/bible
    aegis_bible = tmp_path / ".aegis" / "bible"
    aegis_bible.mkdir(parents=True)
    (aegis_bible / "conventions.md").write_text(
        "# bible:conventions\n\n## entry\n- id: conv-1\n- source: test\n- confidence: 1.0\n- created_at: 2026-01-01\n- updated_at: 2026-01-01\n- content: {\"rule\": \"PEP8\"}\n",
        encoding="utf-8",
    )

    store = AegisProjectStore(tmp_path)
    assert store.bible_dir == aegis_bible.resolve()
    bible = BibleStore(tmp_path)
    entries = bible.read_category("conventions")
    assert len(entries) == 1
    assert entries[0].id == "conv-1"

    # 2. Fallback ke legacy .aether/bible bila .aegis/bible tidak ada
    with tempfile.TemporaryDirectory() as td2:
        tmp2 = Path(td2).resolve()
        aether_bible = tmp2 / ".aether" / "bible"
        aether_bible.mkdir(parents=True)
        (aether_bible / "decisions.md").write_text(
            "# bible:decisions\n\n## entry\n- id: dec-1\n- source: test\n- confidence: 1.0\n- created_at: 2026-01-01\n- updated_at: 2026-01-01\n- content: {\"decision\": \"SQLite\"}\n",
            encoding="utf-8",
        )
        bible2 = BibleStore(tmp2)
        assert bible2.store.bible_dir == aether_bible
        entries2 = bible2.read_category("decisions")
        assert len(entries2) == 1
        assert entries2[0].id == "dec-1"


def test_antigravity_policy_directive_workspace_focus() -> None:
    """Direktif prompt Antigravity melarang directory traversal dan eksplorasi folder metadata."""
    directive = _format_antigravity_policy_directive("balanced")
    assert "STRICT LOG FILE PROHIBITION" in directive
    assert "WORKSPACE BOUNDARY INTEGRITY" in directive
    assert "WORKSPACE FOCUS" in directive
    assert ".aegis/log/" in directive
