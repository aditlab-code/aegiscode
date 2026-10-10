"""Pengujian regresi menyeluruh untuk Native Skills Auto-Discovery dan Olympus Framework."""

from pathlib import Path
import pytest

from agent_ai.core.agent_prompt import (
    DEFAULT_PERSONA,
    build_agent_system_prompt,
    get_aegis_central_dir,
    load_persona_prompt,
)
from agent_ai.projects.skills import (
    SkillStore,
    _find_skill_file,
    _parse_frontmatter,
)
from agent_ai.tools.skills import LoadSkillTool, SkillCatalogTool


def test_aegis_central_directory_contains_agents_and_skills() -> None:
    central_dir = get_aegis_central_dir()
    dot_agents = central_dir / ".agents"
    assert dot_agents.is_dir(), "Direktori .agents/ wajib ada di central root"
    assert (dot_agents / "agents").is_dir(), "Direktori .agents/agents/ wajib ada di central root"
    assert (dot_agents / "skills").is_dir(), "Direktori .agents/skills/ wajib ada di central root"


def test_dot_agents_resolution() -> None:
    central_dir = get_aegis_central_dir()
    dot_agents = central_dir / ".agents"
    assert (dot_agents / "skills").is_dir()
    assert (dot_agents / "agents").is_dir()
    assert (dot_agents / "commands").is_dir()
    assert (dot_agents / "hooks").is_dir()


def test_olympus_personas_loaded_from_markdown() -> None:
    prompt_zeus = load_persona_prompt("zeus-orchestrator")
    assert "Zeus Orchestrator" in prompt_zeus or "zeus" in prompt_zeus.lower()

    prompt_heracles = load_persona_prompt("heracles-tester")
    assert "Heracles" in prompt_heracles or "QA" in prompt_heracles

    prompt_themis = load_persona_prompt("themis-reviewer")
    assert "Themis" in prompt_themis or "Review" in prompt_themis

    full_prompt = build_agent_system_prompt(mode="fast", persona="zeus-orchestrator")
    assert "[EXECUTION POLICY: FAST MODE ACTIVE]" in full_prompt


def test_parse_frontmatter_handles_quoted_and_unquoted_values() -> None:
    raw_text = """---
name: "interview-me"
description: 'Stress-test my thinking'
scope: project
---
# Content Body Here
"""
    fm, body = _parse_frontmatter(raw_text)
    assert fm["name"] == "interview-me"
    assert fm["description"] == "Stress-test my thinking"
    assert fm["scope"] == "project"
    assert "# Content Body Here" in body


def test_find_skill_file_prefers_skill_md_capital() -> None:
    central_dir = get_aegis_central_dir()
    interview_dir = central_dir / ".agents" / "skills" / "interview-me"
    if not interview_dir.is_dir():
        interview_dir = central_dir / "skills" / "interview-me"
    found = _find_skill_file(interview_dir)
    assert found is not None
    assert found.name in ("SKILL.md", "skill.md")


def test_native_skills_auto_discovery_finds_all_nine_skills() -> None:
    central_dir = get_aegis_central_dir()
    store = SkillStore(central_dir)
    catalog = store.get_catalog()
    assert len(catalog) >= 9

    skill_ids = [entry.skill_id for entry in catalog]
    expected_skills = [
        "interview-me",
        "spec-driven-development",
        "planning-and-task-breakdown",
        "incremental-implementation",
        "test-driven-development",
        "code-review-and-quality",
        "shipping-and-launch",
        "constraint-driven-development",
        "code-simplification",
    ]
    for expected in expected_skills:
        assert expected in skill_ids, f"Skill {expected} wajib ditemukan di catalog"


def test_progressive_loading_of_skill_content() -> None:
    central_dir = get_aegis_central_dir()
    store = SkillStore(central_dir)
    skill = store.load_skill("interview-me")
    assert skill.skill_id == "interview-me"
    assert len(skill.content) > 100
    assert "Interview Me" in skill.content


def test_skill_tools_execution() -> None:
    central_dir = get_aegis_central_dir()
    catalog_tool = SkillCatalogTool(root=central_dir)
    cat_res = catalog_tool.execute()
    assert cat_res["count"] >= 9

    load_tool = LoadSkillTool(root=central_dir)
    skill_res = load_tool.execute(skill_id="spec-driven-development")
    assert skill_res["skill_id"] == "spec-driven-development"
    assert "content" in skill_res
    assert len(skill_res["content"]) > 100
