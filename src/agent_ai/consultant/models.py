"""Model data untuk AETHER Consultant (provider-agnostic, JSON-friendly).

Model di sini HANYA representasi data; tidak menyimpan chain-of-thought dan
tidak menduplikasi model Agent/Runtime/Task yang sudah ada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Mode Consultant kanonik (harmonisasi triad: fast, balanced, deep):
#:   fast     -> percakapan cepat berbasis Project Bible, Project Map, dan
#:               simbol CodeGraph READ-ONLY (codegraph_find_references);
#:               TANPA pembacaan berkas source penuh.
#:   balanced -> investigasi moderat: Project Map + CodeGraph callers/callees
#:               (depth=2) + inspeksi berkas source spesifik (read_file/search_code).
#:   deep     -> audit arsitektur penuh: CodeGraph impact analysis (blast radius),
#:               trace API, orphan detection + inspeksi berkas + run_command.
MODE_FAST = "fast"
MODE_BALANCED = "balanced"
MODE_DEEP = "deep"

#: Alias lama (backward compatibility):
MODE_QUICK = "quick"
MODE_INVESTIGATE = "investigate"

#: Mode default Consultant (balanced).
DEFAULT_CONSULTANT_MODE = MODE_BALANCED

#: Mode Consultant kanonik yang valid.
VALID_CONSULTANT_MODES = (MODE_FAST, MODE_BALANCED, MODE_DEEP, MODE_QUICK, MODE_INVESTIGATE)

CONSULTANT_MODE_ALIASES: Dict[str, str] = {
    "quick": MODE_FAST,
    "investigate": MODE_DEEP,
    "minimal": MODE_FAST,
    "standard": MODE_BALANCED,
}


def normalize_consultant_mode(mode: Optional[str]) -> str:
    """Normalisasi mode Consultant ke kanonik atau alias yang valid.

    Menerima mode baru (fast, balanced, deep) dan mode lama (quick, investigate).
    Nilai kosong dipetakan ke default (``balanced``).
    """
    if not mode:
        return DEFAULT_CONSULTANT_MODE
    value = str(mode).strip().lower()
    if value in VALID_CONSULTANT_MODES:
        return value
    if value in CONSULTANT_MODE_ALIASES:
        return CONSULTANT_MODE_ALIASES[value]
    return DEFAULT_CONSULTANT_MODE
@dataclass
class ConsultantTurn:
    """Satu giliran percakapan konsultasi (session context)."""

    role: str  # "user" | "consultant"
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "text": self.text}


@dataclass
class ConsultantResult:
    """Hasil satu giliran konsultasi.

    Attributes:
        session_id: id sesi konsultasi (dipakai untuk konteks lintas giliran).
        reply: jawaban final Consultant (markdown teks).
        status: "done" bila selesai, "failed" bila gagal.
        error: pesan error (bila failed).
        iterations: jumlah langkah reasoning/tool yang dipakai.
        tool_events: ringkasan aktivitas tool (tool, target, success).
        task_proposal: Task Proposal siap kirim ke Agent (bila ADA).
        mode: mode Consultant yang dipakai ("quick" | "investigate").
    """

    session_id: str
    reply: str = ""
    status: str = "done"
    error: Optional[str] = None
    iterations: int = 0
    tool_events: List[Dict[str, Any]] = field(default_factory=list)
    task_proposal: Optional[str] = None
    mode: str = DEFAULT_CONSULTANT_MODE
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "reply": self.reply,
            "status": self.status,
            "error": self.error,
            "iterations": self.iterations,
            "tool_events": self.tool_events,
            "task_proposal": self.task_proposal,
            "mode": self.mode,
            "reasoning": self.reasoning,
        }
