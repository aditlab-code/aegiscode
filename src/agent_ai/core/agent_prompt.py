"""Dynamic System Prompt Loader untuk Aegis Agent.

Tidak ada hardcode prompt string di Python (.py). Semua instruksi prompt sistem
dimuat secara dinamis dari direktori sentral AegisCode:
    `agents/<persona>.md` dan `skills/<skill>/SKILL.md`

Direktori sentral di root AegisCode melayani semua repositori proyek tanpa perlu
duplikasi per repo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

#: Nilai mode execution policy Agent yang valid (fast / balanced / deep).
MODE_FAST = "fast"
MODE_BALANCED = "balanced"
MODE_DEEP = "deep"
DEFAULT_MODE = MODE_BALANCED

#: Alias mode lama/eksternal yang dipetakan ke mode kanonik.
MODE_ALIASES: dict[str, str] = {
    "minimal": MODE_FAST,
}

DEFAULT_PERSONA = "zeus-orchestrator"


def get_aegis_central_dir() -> Path:
    """Temukan direktori sentral AegisCode yang memuat folder agents/ dan skills/."""
    custom_dir = os.environ.get("AEGIS_CENTRAL_DIR")
    if custom_dir:
        p = Path(custom_dir).resolve()
        if (p / ".agents" / "agents").is_dir() or (p / "agents").is_dir():
            return p

    # Cari dari path file ini ke atas
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".agents" / "agents").is_dir() and (parent / ".agents" / "skills").is_dir():
            return parent
        if (parent / "agents").is_dir() and (parent / "skills").is_dir():
            return parent

    # Fallback ke parent level 3 (root AegisCode)
    return current.parents[3] if len(current.parents) > 3 else current.parent


def _normalize_mode(value: Any, default: str = DEFAULT_MODE) -> str:
    valid_modes = {MODE_FAST, MODE_BALANCED, MODE_DEEP}
    fallback = str(default).strip().lower()
    if fallback not in valid_modes:
        fallback = DEFAULT_MODE
    if value is None:
        return fallback
    raw = getattr(value, "value", value)
    text = str(raw).strip().lower() if raw is not None else ""
    if not text:
        return fallback
    text = MODE_ALIASES.get(text, text)
    return text if text in valid_modes else fallback


def directive_prompt_for_mode(mode: Any) -> str:
    """Prompt arahan direktif kerja per mode (Fast, Balanced, Deep)."""
    norm = _normalize_mode(mode, DEFAULT_MODE)
    if norm == MODE_FAST:
        return (
            "[EXECUTION POLICY: FAST MODE ACTIVE]\n"
            "You are operating under FAST execution policy:\n"
            "- Goal: Rapid, surgical resolution with minimal latency and minimal token consumption.\n"
            "- Code Navigation: Prioritize CodeGraph tools ('codegraph_find_references', 'codegraph_find_callers') and 'search_code' to pinpoint exact symbols before reading files.\n"
            "- Minimal Planning: Do not construct verbose multi-step planning lists. Directly apply surgical changes.\n"
            "- Targeted Verification: Validate syntax and verify only the modified files.\n"
            "- Escalation: If you discover this task genuinely requires architecture-wide refactoring, invoke the 'request_policy_escalation' tool with target_mode='balanced'."
        )
    if norm == MODE_DEEP:
        return (
            "[EXECUTION POLICY: DEEP MODE ACTIVE]\n"
            "You are operating under DEEP execution policy:\n"
            "- Goal: Thorough investigation, high-assurance architecture validation, and complete regression safety.\n"
            "- Code Navigation: Unrestricted exploration allowed. Proactively utilize CodeGraph tools ('codegraph_impact_analysis', 'codegraph_trace_api', 'codegraph_find_orphans') for structural architecture navigation.\n"
            "- Planning: Formulate detailed multi-phase plans.\n"
            "- Full Verification: Run broad regression test suites and inspect cross-module impact."
        )
    # Default Balanced
    return (
        "[EXECUTION POLICY: BALANCED MODE ACTIVE]\n"
        "You are operating under BALANCED execution policy (Standard):\n"
        "- Goal: Optimal balance between execution velocity, code correctness, and token efficiency.\n"
        "- Code Navigation: Moderate exploration. Use CodeGraph tools ('codegraph_find_callers', 'codegraph_find_callees') to inspect direct caller/callee relations before editing.\n"
        "- Standard Verification: Run tests and checkers targeted to modified and related modules.\n"
        "- Escalation: If you encounter widespread ripple effects requiring exhaustive repository-wide search, invoke 'request_policy_escalation' with target_mode='deep'."
    )


def load_persona_prompt(persona_name: str = DEFAULT_PERSONA) -> str:
    """Muat teks prompt sistem langsung dari berkas markdown persona di agents/."""
    central_dir = get_aegis_central_dir()
    agents_dir = central_dir / ".agents" / "agents"
    if not agents_dir.is_dir():
        agents_dir = central_dir / "agents"

    # Cek kandidat path: agents/<persona>.md atau agents/<persona>/agent.md
    candidates = [
        agents_dir / f"{persona_name}.md",
        agents_dir / persona_name / "agent.md",
        agents_dir / f"{DEFAULT_PERSONA}.md",
    ]

    for candidate in candidates:
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8")
                # Ekstrak body markdown setelah YAML frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        return parts[2].strip()
                return content.strip()
            except Exception:
                continue

    # Fallback minimal bila berkas fisik tidak dapat dibaca
    return "Anda adalah Aegis Agent: coding agent yang mengerjakan tugas menggunakan tools dan CodeGraph AST yang tersedia."


def build_agent_system_prompt(
    mode: Optional[str] = None,
    persona: str = DEFAULT_PERSONA,
) -> str:
    """Bangun system prompt dinamis dari berkas sentral agents/ tanpa hardcode string di Python.

    Args:
        mode: Mode eksekusi opsional ("fast" | "balanced" | "deep").
        persona: Nama persona yang dimuat dari agents/<persona>.md (default: zeus-orchestrator).

    Returns:
        System prompt Agent yang dimuat dinamis dari markdown.
    """
    body = load_persona_prompt(persona)
    lines: List[str] = [
        body,
        "",
        "## 4 Aturan Inti Efisiensi Output (Action-First)",
        "1. Aksi Terlebih Dahulu (Lead with the next action): Baris pertama respons wajib berupa aksi nyata (perintah CLI, file path, atau snippet kode target). Hindari narasi bertele-tele.",
        "2. Langkah Bernomor & Terukur (Number multi-step tasks): Tugas multi-tahap wajib disusun dalam daftar bernomor ringkas (1, 2, 3).",
        "3. Lugas & Faktual Menangani Error (Matter-of-fact tone for errors): Sebutkan kegagalan, penyebab teknis langsung, dan langkah perbaikan secara objektif.",
        "4. Tanpa Basa-Basi & Tanpa Rekapitulasi (No preamble, no recap): Dilarang pembuka klise, dilarang rekapitulasi ulang pekerjaan yang sudah selesai.",
        "",
        "## Alur kerja (RETRIEVAL -> BERHENTI RETRIEVAL -> IMPLEMENTASI -> VALIDASI)",
        "1. RETRIEVAL (terarah & secukupnya): temukan LOKASI yang relevan via search_code / read_file; JANGAN pakai run_command hanya untuk membaca source.",
        "2. CUKUP? -> BERHENTI RETRIEVAL: begitu informasi yang dibutuhkan sudah ada, JANGAN meminta ulang file/rentang yang sama.",
        "3. IMPLEMENTASI: setelah konteks cukup, LANJUTKAN ke perubahan nyata (edit_file/write_file).",
        "4. VALIDASI: jalankan test/build/checker yang relevan lewat run_command.",
        "",
        "## State Sumber Informasi (penting)",
        "- `already_available` / `already_read` (read_file): isi file/rentang/symbol yang diminta SUDAH ADA di percakapan ini. JANGAN meminta ulang rentang yang sama.",
        "- `already_searched` (search_code): hasil pencarian sudah ada di percakapan. JANGAN mengulang query itu.",
        "- Panggil read_file dengan `force=true` bila isi mentah harus dikirim ulang. JANGAN beralih ke run_command hanya karena read_file mengembalikan `already_available`.",
    ]

    if mode is not None:
        directive = directive_prompt_for_mode(mode)
        if directive:
            lines.extend(["", "## Direktif Eksekusi Mode", directive])

    return "\n".join(lines)


#: System prompt default Agent (dimuat dinamis dari agents/zeus-orchestrator.md).
AGENT_SYSTEM_PROMPT = build_agent_system_prompt()

__all__ = [
    "AGENT_SYSTEM_PROMPT",
    "DEFAULT_MODE",
    "DEFAULT_PERSONA",
    "MODE_ALIASES",
    "MODE_BALANCED",
    "MODE_DEEP",
    "MODE_FAST",
    "build_agent_system_prompt",
    "directive_prompt_for_mode",
    "get_aegis_central_dir",
    "load_persona_prompt",
]
