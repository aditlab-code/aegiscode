"""Olympus Lifecycle State Machine & Persona-Skill Assignment.

Menghubungkan 6 tahapan makro Olympus Framework dengan:
- Persona Yunani resmi (.agents/agents/)
- Skill Addy Osmani (.agents/skills/)
- Stop-gate verifikasi transisi
- State persisten project-local (.aegis/lifecycle_state.json)
- Harmonisasi dengan ActivityPhase UI timeline (planning, inspecting, editing, running, validating)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from agent_ai.runtime.activity import ActivityPhase


class OlympusPhase(str, Enum):
    """6 Tahapan Makro Olympus Lifecycle."""

    DEFINE = "DEFINE"
    PLAN = "PLAN"
    BUILD = "BUILD"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    SHIP = "SHIP"


#: Pemetaan paten tiap tahapan ke Persona primer, Persona pendukung, dan Skill wajib.
OLYMPUS_ASSIGNMENTS: Dict[OlympusPhase, Dict[str, Any]] = {
    OlympusPhase.DEFINE: {
        "persona": "athena-planner",
        "partners": [],
        "skills": ["interview-me", "spec-driven-development"],
        "ui_activity": ActivityPhase.PLANNING,
        "description": "Ekstraksi intensi kebutuhan, wawancara mendalam, dan perumusan PRD/Spesifikasi.",
    },
    OlympusPhase.PLAN: {
        "persona": "athena-planner",
        "partners": ["hermes-scout"],
        "skills": ["planning-and-task-breakdown"],
        "ui_activity": ActivityPhase.PLANNING,
        "description": "Pemetaan struktur CodeGraph AST dan pemecahan tugas menjadi langkah atomik.",
    },
    OlympusPhase.BUILD: {
        "persona": "hephaestus-coder",
        "partners": [],
        "skills": ["incremental-implementation", "code-simplification"],
        "ui_activity": ActivityPhase.EDITING,
        "description": "Implementasi kode per-irisan tipis yang terverifikasi dan penyederhanaan refactoring.",
    },
    OlympusPhase.VERIFY: {
        "persona": "heracles-tester",
        "partners": ["test-engineer"],
        "skills": ["test-driven-development"],
        "ui_activity": ActivityPhase.VALIDATING,
        "description": "Penegakan pengujian Prove-It pattern (red-green-refactor) dengan target 100% tes hijau.",
    },
    OlympusPhase.REVIEW: {
        "persona": "themis-reviewer",
        "partners": ["code-reviewer", "security-auditor"],
        "skills": ["code-review-and-quality", "constraint-driven-development"],
        "ui_activity": ActivityPhase.INSPECTING,
        "description": "Penilaian kualitas multi-axis 5 dimensi dan verifikasi zero-orphan gate.",
    },
    OlympusPhase.SHIP: {
        "persona": "zeus-orchestrator",
        "partners": ["test-engineer", "code-reviewer", "security-auditor"],
        "skills": ["shipping-and-launch"],
        "ui_activity": ActivityPhase.VALIDATING,
        "description": "Sintesis parallel fan-out merge, checklist pre-launch, dan kesiapan rilis produksi.",
    },
}

LIFECYCLE_STATE_FILENAME = "lifecycle_state.json"
AEGIS_DIRNAME = ".aegis"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseTransitionLog:
    phase: str
    entered_at: str
    status: str = "completed"
    notes: str = ""


@dataclass
class LifecycleGates:
    define_passed: bool = False
    plan_passed: bool = False
    build_passed: bool = False
    verify_passed: bool = False
    review_passed: bool = False
    ship_passed: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)


@dataclass
class LifecycleArtifacts:
    spec_file: Optional[str] = None
    plan_file: Optional[str] = None
    test_report: Optional[str] = None
    review_report: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return asdict(self)


@dataclass
class LifecycleState:
    version: str = "1.0"
    current_phase: str = OlympusPhase.DEFINE.value
    active_persona: str = "athena-planner"
    active_skills: List[str] = field(
        default_factory=lambda: ["interview-me", "spec-driven-development"]
    )
    phase_history: List[Dict[str, Any]] = field(default_factory=list)
    gates: Dict[str, bool] = field(
        default_factory=lambda: LifecycleGates().to_dict()
    )
    artifacts: Dict[str, Optional[str]] = field(
        default_factory=lambda: LifecycleArtifacts().to_dict()
    )
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LifecycleState:
        return cls(
            version=data.get("version", "1.0"),
            current_phase=data.get("current_phase", OlympusPhase.DEFINE.value),
            active_persona=data.get("active_persona", "athena-planner"),
            active_skills=data.get(
                "active_skills", ["interview-me", "spec-driven-development"]
            ),
            phase_history=data.get("phase_history", []),
            gates=data.get("gates", LifecycleGates().to_dict()),
            artifacts=data.get("artifacts", LifecycleArtifacts().to_dict()),
            updated_at=data.get("updated_at", _now_iso()),
        )


def get_state_file_path(root: Union[str, Path]) -> Path:
    """Temukan path .aegis/lifecycle_state.json untuk root project."""
    return Path(root).resolve() / AEGIS_DIRNAME / LIFECYCLE_STATE_FILENAME


def load_lifecycle_state(root: Union[str, Path]) -> LifecycleState:
    """Muat state lifecycle dari disk; inisialisasi default bila belum ada."""
    state_path = get_state_file_path(root)
    if not state_path.is_file():
        state = LifecycleState()
        save_lifecycle_state(root, state)
        return state

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return LifecycleState.from_dict(data)
    except Exception:
        state = LifecycleState()
        save_lifecycle_state(root, state)
        return state


def save_lifecycle_state(root: Union[str, Path], state: LifecycleState) -> bool:
    """Simpan state lifecycle ke .aegis/lifecycle_state.json secara atomik."""
    state_path = get_state_file_path(root)
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state.updated_at = _now_iso()
        content = json.dumps(state.to_dict(), indent=2) + "\n"
        temp_file = state_path.with_suffix(".tmp")
        temp_file.write_text(content, encoding="utf-8")
        temp_file.replace(state_path)
        return True
    except OSError:
        return False


def get_phase_assignment(phase: Union[str, OlympusPhase]) -> Dict[str, Any]:
    """Kembalikan persona, partners, dan skills untuk sebuah fase."""
    norm = phase.value if isinstance(phase, OlympusPhase) else str(phase).upper()
    try:
        enum_val = OlympusPhase(norm)
    except ValueError:
        enum_val = OlympusPhase.DEFINE
    return OLYMPUS_ASSIGNMENTS[enum_val]


def advance_lifecycle_phase(
    root: Union[str, Path],
    target_phase: Union[str, OlympusPhase],
    bypass_gate: bool = False,
) -> Tuple[bool, str, LifecycleState]:
    """Pindahkan alur lifecycle ke fase target dengan pengecekan stop-gate.

    Args:
        root: Root project.
        target_phase: Fase tujuan.
        bypass_gate: Izinkan lewati stop-gate secara paksa (opsi darurat).

    Returns:
        (success, message, state)
    """
    state = load_lifecycle_state(root)
    norm = target_phase.value if isinstance(target_phase, OlympusPhase) else str(target_phase).upper()
    try:
        target_enum = OlympusPhase(norm)
    except ValueError:
        return False, f"Fase tidak dikenal: '{target_phase}'", state

    current_enum = OlympusPhase(state.current_phase)
    if current_enum == target_enum:
        return True, f"Fase saat ini sudah {target_enum.value}", state

    # Stop-gate checks
    if not bypass_gate:
        # Jika ingin masuk ke BUILD dari DEFINE/PLAN: pastikan define_passed atau ada spec
        if target_enum in (OlympusPhase.BUILD, OlympusPhase.VERIFY, OlympusPhase.REVIEW, OlympusPhase.SHIP):
            if current_enum == OlympusPhase.DEFINE and not state.gates.get("define_passed"):
                # Cek apakah ada file spesifikasi di workspace
                spec_cand = [Path(root) / "SPEC.md", Path(root) / "PRD.md", Path(root) / "spec.md"]
                if not any(p.is_file() for p in spec_cand):
                    return False, "STOP-GATE: Tahap DEFINE belum selesai (berkas SPEC.md / PRD.md belum ditemukan).", state
                state.gates["define_passed"] = True

        # Jika ingin masuk ke REVIEW atau SHIP: pastikan VERIFY sudah lewat
        if target_enum in (OlympusPhase.REVIEW, OlympusPhase.SHIP):
            if not state.gates.get("verify_passed") and current_enum == OlympusPhase.BUILD:
                return False, "STOP-GATE: Anda tidak boleh langsung loncat ke REVIEW/SHIP sebelum tahap VERIFY (Prove-It pattern) lulus.", state

    # Lolos stop-gate: catat riwayat
    state.phase_history.append({
        "phase": state.current_phase,
        "completed_at": _now_iso(),
    })

    # Update fase baru dan penugasan
    assignment = get_phase_assignment(target_enum)
    state.current_phase = target_enum.value
    state.active_persona = assignment["persona"]
    state.active_skills = list(assignment["skills"])

    save_lifecycle_state(root, state)
    return True, f"Sukses berpindah ke fase {target_enum.value} ({state.active_persona})", state


def map_olympus_to_ui_activity(phase: Union[str, OlympusPhase]) -> ActivityPhase:
    """Petakan tahapan makro Olympus ke enum mikro ActivityPhase UI timeline."""
    assignment = get_phase_assignment(phase)
    return assignment.get("ui_activity", ActivityPhase.PLANNING)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    root = Path.cwd()
    if not args or args[0] == "status":
        state = load_lifecycle_state(root)
        print(json.dumps(state.to_dict(), indent=2))
    elif args[0] == "advance" and len(args) > 1:
        target = args[1]
        bypass = "--bypass" in args
        ok, msg, st = advance_lifecycle_phase(root, target, bypass_gate=bypass)
        print(f"[{'OK' if ok else 'BLOCKED'}] {msg}")
        sys.exit(0 if ok else 1)
    elif args[0] == "gate" and len(args) > 2:
        gate_name = args[1]
        val = args[2].lower() in ("1", "true", "yes", "passed")
        st = load_lifecycle_state(root)
        st.gates[gate_name] = val
        save_lifecycle_state(root, st)
        print(f"[OK] Gate '{gate_name}' diatur ke {val}")
    else:
        print("Penggunaan:")
        print("  python -m agent_ai.runtime.olympus_workflow status")
        print("  python -m agent_ai.runtime.olympus_workflow advance <DEFINE|PLAN|BUILD|VERIFY|REVIEW|SHIP> [--bypass]")
        print("  python -m agent_ai.runtime.olympus_workflow gate <define_passed|verify_passed|...> <true|false>")
