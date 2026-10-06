"""Unit tests untuk ExternalBrainResolver dan integrasi ProjectBrain."""

from pathlib import Path
import pytest

from agent_ai.projects.brain import ProjectBrain
from agent_ai.projects.external_brain import (
    ExternalBrainResolver,
    ExternalBrainSecurityError,
)
from agent_ai.projects.intelligence import ProjectIntelligence


def test_external_brain_unavailable_path(tmp_path: Path) -> None:
    non_existent = tmp_path / "non_existent_brain_dir"
    resolver = ExternalBrainResolver(brain_root=non_existent)
    assert resolver.is_available() is False
    assert resolver.list_memory_files() == []
    assert resolver.get_summary_context() == ""


def test_external_brain_reads_valid_memories(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    mem1 = brain_dir / "notes.md"
    mem1.write_text("# Arsitektur Sistem\nSistem memakai Django dan Vue.", encoding="utf-8")

    mem2 = brain_dir / "session.json"
    mem2.write_text('{"summary": "Sesi pengujian selesai"}', encoding="utf-8")

    resolver = ExternalBrainResolver(brain_root=brain_dir)
    assert resolver.is_available() is True

    files = resolver.list_memory_files()
    assert len(files) == 2

    summary = resolver.get_summary_context()
    assert "GLOBAL ANTIGRAVITY BRAIN MEMORY" in summary
    assert "Arsitektur Sistem" in summary
    assert "Sesi pengujian selesai" in summary


def test_external_brain_blocks_sensitive_files(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    env_file = brain_dir / ".env"
    env_file.write_text("SECRET_KEY=12345", encoding="utf-8")

    oauth_file = brain_dir / "oauth_creds.json"
    oauth_file.write_text('{"token": "xyz"}', encoding="utf-8")

    valid_file = brain_dir / "valid_note.md"
    valid_file.write_text("Catatan valid", encoding="utf-8")

    resolver = ExternalBrainResolver(brain_root=brain_dir)
    files = resolver.list_memory_files()

    # Hanya valid_note.md yang lolos; berkas sensitif diblokir
    assert len(files) == 1
    assert files[0].name == "valid_note.md"

    with pytest.raises(ExternalBrainSecurityError):
        resolver.read_file_content(env_file)

    with pytest.raises(ExternalBrainSecurityError):
        resolver.read_file_content(oauth_file)


def test_external_brain_blocks_path_traversal(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    outside_file = tmp_path / "secret_outside.md"
    outside_file.write_text("Rahasia luar", encoding="utf-8")

    resolver = ExternalBrainResolver(brain_root=brain_dir)

    with pytest.raises(ExternalBrainSecurityError):
        resolver.read_file_content(outside_file)


def test_project_brain_integration_with_external_brain(tmp_path: Path) -> None:
    proj_root = tmp_path / "project"
    proj_root.mkdir()

    brain_dir = tmp_path / "global_brain"
    brain_dir.mkdir()
    (brain_dir / "workflow.md").write_text("Aturan workflow global", encoding="utf-8")

    ext_resolver = ExternalBrainResolver(brain_root=brain_dir)
    intel = ProjectIntelligence.for_project(proj_root)
    brain = ProjectBrain(intel, external_brain=ext_resolver)

    ctx = brain.get_context()
    assert "GLOBAL ANTIGRAVITY BRAIN MEMORY" in ctx.text
    assert "Aturan workflow global" in ctx.text
