"""Pengujian komprehensif untuk Olympus Lifecycle State Machine, Alur Hooks, dan Penyelarasan Timeline UI."""

import json
import subprocess
from pathlib import Path
import pytest

from agent_ai.runtime.activity import ActivityPhase
from agent_ai.runtime.olympus_workflow import (
    OlympusPhase,
    OLYMPUS_ASSIGNMENTS,
    LifecycleState,
    load_lifecycle_state,
    save_lifecycle_state,
    advance_lifecycle_phase,
    map_olympus_to_ui_activity,
)


def test_olympus_phases_assignments_mapping() -> None:
    # 1. Pastikan 6 fase terdefinisi lengkap
    phases = [p.value for p in OlympusPhase]
    assert phases == ["DEFINE", "PLAN", "BUILD", "VERIFY", "REVIEW", "SHIP"]

    # 2. Periksa persona dan skill wajib untuk setiap fase
    define_assign = OLYMPUS_ASSIGNMENTS[OlympusPhase.DEFINE]
    assert define_assign["persona"] == "athena-planner"
    assert "interview-me" in define_assign["skills"]
    assert "spec-driven-development" in define_assign["skills"]

    plan_assign = OLYMPUS_ASSIGNMENTS[OlympusPhase.PLAN]
    assert plan_assign["persona"] == "athena-planner"
    assert "hermes-scout" in plan_assign["partners"]
    assert "planning-and-task-breakdown" in plan_assign["skills"]

    build_assign = OLYMPUS_ASSIGNMENTS[OlympusPhase.BUILD]
    assert build_assign["persona"] == "hephaestus-coder"
    assert "incremental-implementation" in build_assign["skills"]

    verify_assign = OLYMPUS_ASSIGNMENTS[OlympusPhase.VERIFY]
    assert verify_assign["persona"] == "heracles-tester"
    assert "test-driven-development" in verify_assign["skills"]

    review_assign = OLYMPUS_ASSIGNMENTS[OlympusPhase.REVIEW]
    assert review_assign["persona"] == "themis-reviewer"
    assert "code-review-and-quality" in review_assign["skills"]

    ship_assign = OLYMPUS_ASSIGNMENTS[OlympusPhase.SHIP]
    assert ship_assign["persona"] == "zeus-orchestrator"
    assert "shipping-and-launch" in ship_assign["skills"]


def test_olympus_to_ui_activity_mapping() -> None:
    assert map_olympus_to_ui_activity(OlympusPhase.DEFINE) == ActivityPhase.PLANNING
    assert map_olympus_to_ui_activity(OlympusPhase.PLAN) == ActivityPhase.PLANNING
    assert map_olympus_to_ui_activity(OlympusPhase.BUILD) == ActivityPhase.EDITING
    assert map_olympus_to_ui_activity(OlympusPhase.VERIFY) == ActivityPhase.VALIDATING
    assert map_olympus_to_ui_activity(OlympusPhase.REVIEW) == ActivityPhase.INSPECTING
    assert map_olympus_to_ui_activity(OlympusPhase.SHIP) == ActivityPhase.VALIDATING


def test_lifecycle_state_persistence(tmp_path: Path) -> None:
    # 1. Inisialisasi awal pada direktori kosong
    state = load_lifecycle_state(tmp_path)
    assert state.current_phase == "DEFINE"
    assert state.active_persona == "athena-planner"

    # 2. Modifikasi dan simpan
    state.current_phase = "PLAN"
    state.active_persona = "athena-planner"
    state.gates["define_passed"] = True
    ok = save_lifecycle_state(tmp_path, state)
    assert ok is True

    # 3. Muat ulang dan verifikasi integritas
    reloaded = load_lifecycle_state(tmp_path)
    assert reloaded.current_phase == "PLAN"
    assert reloaded.gates["define_passed"] is True


def test_advance_lifecycle_phase_stop_gates(tmp_path: Path) -> None:
    # Coba lompat dari DEFINE ke BUILD tanpa spec -> harus terblokir
    ok, msg, st = advance_lifecycle_phase(tmp_path, OlympusPhase.BUILD)
    assert ok is False
    assert "STOP-GATE" in msg

    # Buat SPEC.md di workspace
    (tmp_path / "SPEC.md").write_text("# Feature Spec\nTargeting user need.", encoding="utf-8")
    ok, msg, st = advance_lifecycle_phase(tmp_path, OlympusPhase.BUILD)
    assert ok is True
    assert st.current_phase == "BUILD"
    assert st.active_persona == "hephaestus-coder"

    # Coba lompat dari BUILD ke REVIEW sebelum VERIFY lulus -> harus terblokir
    ok, msg, st = advance_lifecycle_phase(tmp_path, OlympusPhase.REVIEW)
    assert ok is False
    assert "STOP-GATE" in msg

    # Berpindah ke VERIFY terlebih dahulu
    ok, msg, st = advance_lifecycle_phase(tmp_path, OlympusPhase.VERIFY)
    assert ok is True
    assert st.current_phase == "VERIFY"
    assert st.active_persona == "heracles-tester"

    # Tandai verify_passed lalu masuk ke REVIEW
    st.gates["verify_passed"] = True
    save_lifecycle_state(tmp_path, st)
    ok, msg, st = advance_lifecycle_phase(tmp_path, OlympusPhase.REVIEW)
    assert ok is True
    assert st.current_phase == "REVIEW"
    assert st.active_persona == "themis-reviewer"


def test_pre_invocation_hook_script() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / ".agents" / "hooks" / "pre-invocation.sh"
    if not script_path.is_file():
        script_path = repo_root / "hooks" / "pre-invocation.sh"
    assert script_path.is_file()

    proc = subprocess.run(
        [str(script_path)],
        input=json.dumps({"invocationNum": 1}),
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "injectSteps" in payload
    assert len(payload["injectSteps"]) >= 1
    ephemeral = payload["injectSteps"][0]["ephemeralMessage"]
    assert "[OLYMPUS WORKFLOW:" in ephemeral
    assert "PERSONA:" in ephemeral
    assert "ACTIVE SKILLS:" in ephemeral


def test_pre_tool_use_hook_script() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / ".agents" / "hooks" / "pre-tool-use.sh"
    if not script_path.is_file():
        script_path = repo_root / "hooks" / "pre-tool-use.sh"
    assert script_path.is_file()

    # 1. read_file harus diizinkan
    proc_read = subprocess.run(
        [str(script_path)],
        input=json.dumps({"toolCall": {"name": "read_file", "args": {"path": "src/main.py"}}}),
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert proc_read.returncode == 0
    res_read = json.loads(proc_read.stdout)
    assert res_read["decision"] == "allow"

    # 2. Database/env dilindungi
    proc_db = subprocess.run(
        [str(script_path)],
        input=json.dumps({"toolCall": {"name": "write_to_file", "args": {"TargetFile": "database.sqlite"}}}),
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert proc_db.returncode == 0
    res_db = json.loads(proc_db.stdout)
    assert res_db["decision"] == "deny"


def test_stop_guard_hook_script() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / ".agents" / "hooks" / "stop-guard.sh"
    if not script_path.is_file():
        script_path = repo_root / "hooks" / "stop-guard.sh"
    assert script_path.is_file()

    proc = subprocess.run(
        [str(script_path)],
        input=json.dumps({"executionNum": 1, "terminationReason": "model_stop"}),
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] in ("allow", "continue")
