"""Unit and integration tests for 3-layer smart mention resolution."""

from pathlib import Path
import pytest

from agent_ai.contextbuilder.mention import (
    extract_mention_paths,
    resolve_file_mentions,
    _find_fuzzy_file,
)


def test_extract_mention_paths_bracket_and_standard() -> None:
    text = "Review @[docs/architecture.md] and also @src/index.js please"
    paths = extract_mention_paths(text)
    assert "docs/architecture.md" in paths
    assert "src/index.js" in paths


def test_extract_mention_paths_bracket_clean() -> None:
    text = "Check @[docs/future-roadmap/future_roadmap.md] now"
    paths = extract_mention_paths(text)
    assert paths == ["docs/future-roadmap/future_roadmap.md"]


def test_fuzzy_workspace_file_lookup(tmp_path: Path) -> None:
    # Structure:
    # tmp_path/
    #   docs/
    #     architecture.md
    #   src/
    #     core/
    #       engine.py
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    arch_file = docs_dir / "architecture.md"
    arch_file.write_text("# High Level Architecture\nLayered system.", encoding="utf-8")

    src_dir = tmp_path / "src" / "core"
    src_dir.mkdir(parents=True)
    engine_file = src_dir / "engine.py"
    engine_file.write_text("def start_engine(): pass", encoding="utf-8")

    # 1. Fuzzy match by basename
    found = _find_fuzzy_file("architecture.md", tmp_path)
    assert found is not None
    assert found == arch_file

    # 2. Fuzzy match engine.py
    found_engine = _find_fuzzy_file("engine.py", tmp_path)
    assert found_engine is not None
    assert found_engine == engine_file


def test_resolve_file_mentions_fuzzy_attaches_subdirectory_file(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    arch_file = docs_dir / "architecture.md"
    arch_file.write_text("# High Level Architecture\nLayered system.", encoding="utf-8")

    # User only types @architecture.md without docs/
    prompt = "Tolong jelaskan @architecture.md"
    enriched, attachments = resolve_file_mentions(prompt, tmp_path)

    assert len(attachments) == 1
    assert attachments[0]["path"] == "docs/architecture.md"
    assert "High Level Architecture" in attachments[0]["content"]
    assert "## File: docs/architecture.md" in enriched


def test_resolve_file_mentions_bracket_syntax(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    arch_file = docs_dir / "architecture.md"
    arch_file.write_text("# High Level Architecture", encoding="utf-8")

    prompt = "Tolong periksa @[docs/architecture.md]"
    enriched, attachments = resolve_file_mentions(prompt, tmp_path)

    assert len(attachments) == 1
    assert attachments[0]["path"] == "docs/architecture.md"
    assert "High Level Architecture" in attachments[0]["content"]


def test_fuzzy_excludes_internal_agent_and_git_directories(tmp_path: Path) -> None:
    # Create file inside .aegis/bible/architecture.md and docs/architecture.md
    aegis_bible = tmp_path / ".aegis" / "bible"
    aegis_bible.mkdir(parents=True)
    fake_bible_arch = aegis_bible / "architecture.md"
    fake_bible_arch.write_text("# bible:architecture template", encoding="utf-8")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    real_arch = docs_dir / "architecture.md"
    real_arch.write_text("# Real Docs Architecture", encoding="utf-8")

    # Must resolve to real_arch, NOT the internal Bible file!
    found = _find_fuzzy_file("architecture.md", tmp_path)
    assert found == real_arch


def test_directory_mention_resolves_index_or_readme(tmp_path: Path) -> None:
    roadmap_dir = tmp_path / "docs" / "future-roadmap"
    roadmap_dir.mkdir(parents=True)
    readme = roadmap_dir / "README.md"
    readme.write_text("# Roadmap Overview", encoding="utf-8")

    prompt = "Baca @[docs/future-roadmap] sekarang"
    enriched, attachments = resolve_file_mentions(prompt, tmp_path)

    assert len(attachments) == 1
    assert attachments[0]["path"] == "docs/future-roadmap/README.md"
    assert "Roadmap Overview" in attachments[0]["content"]
