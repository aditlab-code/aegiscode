"""Activity Phase (UI-facing) — aktivitas NYATA yang sedang dilakukan Agent.

Konsep ini SENGAJA dipisahkan dari `TaskPhase` internal runtime
(preparation/planning/execution/tool_execution/validation/finalization, lihat
`agent_ai.task.models.TaskPhase`). `TaskPhase` menggambarkan tahap eksekusi
runtime; `ActivityPhase` menggambarkan AKTIVITAS Agent yang ingin ditampilkan
ke frontend lewat event `phase_changed`.

    internal runtime phase  !=  UI activity phase

Terminal task status (completed/failed/cancelled) BUKAN activity phase.

Klasifikasi bersifat DETERMINISTIK dari aktivitas nyata (tool call aktual),
BUKAN dari timer atau tebakan. Modul ini tidak membuat subsystem baru: ia hanya
memetakan nama tool AETHER yang sudah ada menjadi aktivitas.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Mapping, Optional


class ActivityPhase(str, Enum):
    """Aktivitas Agent yang dikirim ke frontend (bukan `TaskPhase` internal)."""

    PLANNING = "planning"
    INSPECTING = "inspecting"
    EDITING = "editing"
    RUNNING = "running"
    VALIDATING = "validating"


#: Pemetaan nama tool dari berbagai provider/dialek ke nama tool kanonik Aegis.
_CANONICAL_TOOL_MAP: Mapping[str, str] = {
    # --- Inspecting (retrieval / pemahaman project) ---
    "read_file": "read_file",
    "view_file": "read_file",
    "read_symbol": "read_file",
    "view_symbol": "read_file",
    "cat": "read_file",
    "view_image": "view_image",
    "search_code": "search_code",
    "grep": "search_code",
    "grep_search": "search_code",
    "search_file": "search_code",
    "hybrid_search": "search_code",
    "list_files": "list_files",
    "list_dir": "list_files",
    "find_files": "list_files",
    "find_by_name": "list_files",
    "atlas_query": "atlas_query",
    "rig_query": "rig_query",
    "project_map_status": "project_map_status",
    "refresh_project_map": "refresh_project_map",
    "semantic_search": "semantic_search",
    "refresh_semantic_index": "refresh_semantic_index",

    # --- Editing (mutasi workspace) ---
    "write_file": "write_file",
    "write_to_file": "write_file",
    "edit_file": "edit_file",
    "edit_file_part": "edit_file",
    "replace_file_content": "edit_file",
    "replace_content": "edit_file",
    "patch_file": "edit_file",
    "apply_patch": "edit_file",
    "delete_file": "delete_file",
    "move_file": "move_file",
    "create_skill": "edit_file",
    "delete_skill": "edit_file",
    "update_skill": "edit_file",

    # --- Running (terminal / shell) ---
    "run_command": "run_command",
    "bash": "run_command",
    "terminal_exec": "run_command",
    "execute_command": "run_command",
    "exec": "run_command",
}

#: Nama tool AKTUAL & ALIAS -> activity phase.
#:
#: - Inspecting = memahami/mencari informasi project (read-only knowledge).
#: - Editing    = mengubah workspace (mutasi file).
#: - Running    = menjalankan command/process operasional lewat terminal.
#:
#: `run_command` dipetakan ke `RUNNING` sebagai default; ia bisa dipromosikan
#: ke `VALIDATING` oleh `classify_tool_activity` bila command-nya jelas
#: merupakan verifikasi hasil kerja (lihat `is_validation_command`).
_TOOL_ACTIVITY: Mapping[str, ActivityPhase] = {
    # --- Inspecting ---
    "read_file": ActivityPhase.INSPECTING,
    "view_file": ActivityPhase.INSPECTING,
    "read_symbol": ActivityPhase.INSPECTING,
    "view_symbol": ActivityPhase.INSPECTING,
    "cat": ActivityPhase.INSPECTING,
    "view_image": ActivityPhase.INSPECTING,
    "search_code": ActivityPhase.INSPECTING,
    "grep": ActivityPhase.INSPECTING,
    "grep_search": ActivityPhase.INSPECTING,
    "search_file": ActivityPhase.INSPECTING,
    "hybrid_search": ActivityPhase.INSPECTING,
    "list_files": ActivityPhase.INSPECTING,
    "list_dir": ActivityPhase.INSPECTING,
    "find_files": ActivityPhase.INSPECTING,
    "find_by_name": ActivityPhase.INSPECTING,
    "atlas_query": ActivityPhase.INSPECTING,
    "rig_query": ActivityPhase.INSPECTING,
    "project_map_status": ActivityPhase.INSPECTING,
    "refresh_project_map": ActivityPhase.INSPECTING,
    "semantic_search": ActivityPhase.INSPECTING,
    "refresh_semantic_index": ActivityPhase.INSPECTING,

    # --- Editing ---
    "write_file": ActivityPhase.EDITING,
    "write_to_file": ActivityPhase.EDITING,
    "edit_file": ActivityPhase.EDITING,
    "edit_file_part": ActivityPhase.EDITING,
    "replace_file_content": ActivityPhase.EDITING,
    "replace_content": ActivityPhase.EDITING,
    "patch_file": ActivityPhase.EDITING,
    "apply_patch": ActivityPhase.EDITING,
    "delete_file": ActivityPhase.EDITING,
    "move_file": ActivityPhase.EDITING,
    "create_skill": ActivityPhase.EDITING,
    "delete_skill": ActivityPhase.EDITING,
    "update_skill": ActivityPhase.EDITING,

    # --- Running ---
    "run_command": ActivityPhase.RUNNING,
    "bash": ActivityPhase.RUNNING,
    "terminal_exec": ActivityPhase.RUNNING,
    "execute_command": ActivityPhase.RUNNING,
    "exec": ActivityPhase.RUNNING,
}


#: Token command yang menandakan VERIFIKASI hasil pekerjaan. Dipakai HANYA
#: untuk membedakan `run_command` running vs validating pada activity phase.
#:
#: Ini BUKAN subsystem validation baru: runtime validation existing
#: (`validation_started`/`validation_completed`) tetap menjadi sumber resmi
#: bila aktif. Heuristik ini hanya memberi sinyal activity dari aktivitas nyata
#: saat command yang jelas memverifikasi (test/lint/type-check/check script)
#: dijalankan. Deterministik dari string command (bukan tebakan bebas).
_VALIDATION_COMMAND_PATTERNS = (
    # Test runners.
    r"\bpytest\b",
    r"\bpy\.test\b",
    r"\bunittest\b",
    r"\bnose2?\b",
    r"\btox\b",
    r"\bjest\b",
    r"\bvitest\b",
    r"\bmocha\b",
    r"\b(?:npm|yarn|pnpm)\s+(?:run\s+)?test\b",
    r"\b(?:go|cargo|mvn|gradle)\s+test\b",
    # Linter / type-checker.
    r"\bruff\b",
    r"\bflake8\b",
    r"\bpylint\b",
    r"\bmypy\b",
    r"\bpyright\b",
    r"\beslint\b",
    r"\bstylelint\b",
    r"\btsc\b",
    r"\b(?:npm|yarn|pnpm)\s+run\s+lint\b",
    r"\blint\b",
    r"\btypecheck\b",
    r"\btype-check\b",
    # Compile/check (verifikasi hasil pekerjaan).
    r"\bpy_compile\b",
    r"\bcompileall\b",
    r"\bcheck[_\-][a-z0-9_\-]+\.(?:py|sh|bat|ps1|js|mjs|cjs|ts)\b",
)

_VALIDATION_COMMAND_RE = re.compile(
    "|".join(_VALIDATION_COMMAND_PATTERNS), re.IGNORECASE
)


def is_validation_command(command: Any) -> bool:
    """True bila command `run_command` jelas merupakan verifikasi hasil kerja.

    Heuristik deterministik pada string command (test/lint/type-check/check
    script). BUKAN subsystem validation baru: source utama tetap event
    `validation_started`/`validation_completed` milik runtime (bila aktif).
    Mendukung argumen string, dictionary (command/CommandLine/cmd), maupun list token.
    """
    if isinstance(command, Mapping):
        command = command.get("command") or command.get("CommandLine") or command.get("cmd")
    elif isinstance(command, (list, tuple)):
        command = " ".join(str(c) for c in command)
    text = str(command or "").strip()
    if not text:
        return False
    return _VALIDATION_COMMAND_RE.search(text) is not None


def normalize_canonical_tool_name(tool_name: Optional[str]) -> str:
    """Normalisasi nama tool dari dialek apa pun ke nama kanonik Aegis."""
    if not tool_name:
        return ""
    clean = str(tool_name).strip().lower()
    return _CANONICAL_TOOL_MAP.get(clean, clean)


def classify_tool_activity(
    tool_name: Optional[str], arguments: Optional[Mapping[str, Any]] = None
) -> Optional[ActivityPhase]:
    """Tentukan activity phase dari sebuah tool call (deterministik).

    Args:
        tool_name: nama tool AKTUAL atau dialek provider (mis. "read_file", "view_file"). Case-insensitive.
        arguments: argumen tool. Dipakai khusus untuk `run_command` / `bash`
            (membedakan running vs validating dari string `command` atau `CommandLine`).

    Returns:
        `ActivityPhase` bila tool dikenali; `None` bila tool tidak
        diklasifikasikan (mis. tool yang tidak memetakan ke aktivitas UI).
    """
    if not tool_name:
        return None
    canonical = normalize_canonical_tool_name(tool_name)
    phase = _TOOL_ACTIVITY.get(canonical) or _TOOL_ACTIVITY.get(str(tool_name).strip().lower())
    if phase is None:
        return None
    if phase is ActivityPhase.RUNNING:
        command = None
        if isinstance(arguments, Mapping):
            command = arguments.get("command") or arguments.get("CommandLine") or arguments.get("cmd")
        elif isinstance(arguments, (str, list, tuple)):
            command = arguments
        if is_validation_command(command):
            return ActivityPhase.VALIDATING
    return phase


__all__ = [
    "ActivityPhase",
    "classify_tool_activity",
    "is_validation_command",
    "normalize_canonical_tool_name",
]
