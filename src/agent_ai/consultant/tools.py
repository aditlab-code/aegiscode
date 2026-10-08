"""Tool yang tersedia untuk AegisCode Consultant (Aegis Reasoning Layer).

Boundary Consultant: READ-ONLY terhadap CODE PROJECT, READ+UPDATE terhadap
Project Bible. Registry Consultant DIKURASI secara struktural sesuai 3 Mode Kanonik:

    mode "fast"     (alias: "quick")
        -> Percakapan cepat berbasis Project Bible, Project Map (atlas_query,
           rig_query, project_map_status), dan simbol CodeGraph READ-ONLY
           (codegraph_*).
           TANPA tool pembacaan berkas source penuh (read_file/search_code/list_files)
           dan TANPA run_command.
    mode "balanced" (default standard)
        -> Investigasi terarah: Project Map + CodeGraph Relational Intelligence
           + pembacaan berkas source terarah (read_file, search_code, list_files)
           dengan deduplikasi retrieval cache. TANPA tool eksekusi command.
    mode "deep"     (alias: "investigate")
        -> Audit arsitektur penuh: Project Map + CodeGraph suite lengkap
           (impact analysis, trace API, orphan detection, callers/callees)
           + inspeksi berkas source + diagnostik read-only run_command
           (git status/diff, pytest, npm test).

Skill System memakai mekanisme yang sama (SkillStore) dengan Agent:
catalog ringan + progressive loading via SkillStore existing.

Tool tulis/hapus/pindah (`write_file`, `edit_file`, `delete_file`, `move_file`)
SENGAJA tidak pernah didaftarkan agar Consultant tidak memodifikasi source code.
Demikian pula `refresh_project_map` TIDAK pernah didaftarkan: Consultant tetap
read-only terhadap Project Map (hanya query, tanpa modifikasi disk).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from agent_ai.consultant.models import (
    DEFAULT_CONSULTANT_MODE,
    MODE_FAST,
    MODE_BALANCED,
    MODE_DEEP,
    MODE_INVESTIGATE,
    MODE_QUICK,
    normalize_consultant_mode,
)
from agent_ai.tools.base import BaseTool, ToolValidationError
from agent_ai.tools.terminal import RunCommandTool, _split_command

if TYPE_CHECKING:  # pragma: no cover - hanya untuk type hint, hindari import cycle
    from agent_ai.consultant.guard import ConsultantRetrievalGuard


# --------------------------------------------------------------------------- #
# Guard command (best-effort; boundary utama = registry tanpa tool tulis)
# --------------------------------------------------------------------------- #
# Subcommand `git` yang MENGUBAH repository (write/destructive) -> ditolak.
_DESTRUCTIVE_GIT_SUBCOMMANDS = frozenset(
    {
        "commit",
        "push",
        "reset",
        "checkout",
        "clean",
        "revert",
        "rm",
        "mv",
        "stash",
        "merge",
        "rebase",
        "cherry-pick",
        "apply",
        "am",
        "switch",
        "restore",
        "gc",
        "prune",
        "filter-branch",
        "update-ref",
        "config",  # git config dapat mengubah state; tolak demi aman
    }
)

# Command yang memodifikasi file/directory (Windows CMD builtins + Unix).
_FILE_MUTATING_COMMANDS = frozenset(
    {
        # Windows CMD
        "del",
        "erase",
        "rmdir",
        "rd",
        "move",
        "ren",
        "rename",
        "md",
        "mkdir",
        "copy",
        "xcopy",
        "robocopy",
        "mklink",
        "attrib",
        "replace",
        # Unix (seharusnya tidak dipakai di Windows, ditolak untuk aman)
        "rm",
        "mv",
        "cp",
        "touch",
        "chmod",
        "chown",
        "truncate",
        "ln",
        "dd",
        "tee",
        "sed",
        "patch",
        "install",
    }
)

# Interpreter skrip dan flag evaluasi inline yang berpotensi mengeksekusi mutasi file
_SCRIPT_INTERPRETERS = frozenset(
    {"python", "python3", "py", "node", "perl", "ruby", "bash", "sh", "zsh"}
)
_INLINE_EVAL_FLAGS = frozenset({"-c", "-e", "--eval"})


def _has_redirect_outside_quotes(command: str) -> bool:
    """True bila command memuat redirect `>`/`>>` di luar string kutip.

    Redirect menulis file; tidak diizinkan untuk Consultant (memodifikasi
    project). Quote-aware agar `python -c "print('a>b')"` tidak salah ditolak.
    """
    n = len(command)
    i = 0
    quote: Optional[str] = None
    while i < n:
        ch = command[i]
        if quote is not None:
            if ch == quote:
                nxt = command[i + 1] if i + 1 < n else ""
                if nxt == "" or nxt.isspace():
                    quote = None
            i += 1
            continue
        if ch == ">":
            return True
        if ch in ('"', "'"):
            quote = ch
        i += 1
    return False


def consultant_command_violation(command: str) -> Optional[str]:
    """Kembalikan alasan bila `command` dilarang untuk Consultant, else None.

    Deterministik & best-effort: menolak operasi yang jelas mengubah/menghapus
    project (git write, file mutating commands, redirect). Bukan sandbox penuh.
    """
    text = (command or "").strip()
    if not text:
        return "command kosong"

    if _has_redirect_outside_quotes(text):
        return "redirect '>' menulis file (modifikasi project)"

    try:
        tokens = _split_command(text)
    except ToolValidationError:
        return None
    if not tokens:
        return "command kosong"

    first = tokens[0].lower()
    if first.endswith(".exe"):
        first = first[:-4]
    if first in _FILE_MUTATING_COMMANDS:
        return f"command '{first}' memodifikasi/menghapus file"

    if first == "git" and len(tokens) >= 2:
        sub = tokens[1].lower()
        if sub in _DESTRUCTIVE_GIT_SUBCOMMANDS:
            return f"git {sub} mengubah repository (git write)"

    # Deteksi interpreter skrip dengan evaluasi kode inline yang berpotensi mutatif
    if first in _SCRIPT_INTERPRETERS:
        for tok in tokens[1:]:
            if tok in _INLINE_EVAL_FLAGS:
                return (
                    f"evaluasi kode inline '{first} {tok}' berpotensi memodifikasi file; "
                    "jalankan file skrip pengujian/diagnostik atau beralih ke mode Agent"
                )

    return None


class ConsultantRunCommandTool(RunCommandTool):
    """run_command untuk Consultant: diagnosis/validasi, bukan modifikasi.

    Mewarisi RunCommandTool existing (routing Windows-aware, timeout, output
    terstruktur) dan menambahkan guard anti-destruktif. Command yang ditolak
    dikembalikan sebagai tool error (loop Consultant tetap berjalan).
    """

    name = "run_command"
    description = (
        "[Consultant] Menjalankan command DIAGNOSTIK/VALIDASI di dalam project "
        "dan menangkap output (contoh: git status, git diff, git log, pytest, "
        "python checker.py, npm run build). INI BUKAN alat baca source: JANGAN "
        "pakai run_command untuk menampilkan isi file (mis. cat/type/Get-Content/"
        "Select-String) — untuk membaca source gunakan read_file/search_code/"
        "list_files. READ-ONLY terhadap source code: command yang memodifikasi/"
        "menghapus/memindahkan file (del/rmdir/move/ren/copy/mkdir/redirect '>') "
        "atau git write (commit/push/reset/clean/checkout) DITOLAK. Pada Windows "
        "gunakan executable native (python, git, node, pytest) atau CMD builtins; "
        "JANGAN pakai command Unix. Gunakan cwd untuk working directory; jangan "
        "pakai 'cd' di dalam command."
    )

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        command = arguments.get("command")
        reason = consultant_command_violation(str(command or ""))
        if reason:
            raise ToolValidationError(
                f"Consultant run_command menolak perintah ({reason}). "
                "Consultant bersifat READ-ONLY terhadap source project; gunakan "
                "command diagnostik/validasi atau tool read-only."
            )
        return super().execute(**arguments)


class ConsultantBibleTool(BaseTool):
    """Simpan knowledge terverifikasi ke AI Project Bible (Project Knowledge).

    Ini SATU-SATUNYA jalur Consultant menulis: ke Project Bible project-local
    (`<root>/.aegis/bible/<kategori>.md`), bukan ke source code. Memakai
    IntelligenceLearner/BibleStore yang sudah ada (bukan store baru).
    """

    name = "update_project_bible"
    description = (
        "Menyimpan knowledge project yang sudah TERVERIFIKASI ke AI Project "
        "Bible (persistent Project Knowledge untuk konsultasi berikutnya). "
        "Gunakan hanya untuk fakta/keputusan/pelajaran nyata tentang project - "
        "jangan mengarang. Kategori: architecture, ui, conventions, decisions, "
        "facts, learnings, problems, known_bugs, known_gaps."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": (
                    "Kategori Bible: architecture | ui | conventions | decisions | "
                    "facts | learnings | problems | known_bugs | known_gaps"
                ),
            },
            "content": {
                "type": "string",
                "description": "Knowledge faktual & ringkas tentang project.",
            },
            "confidence": {
                "type": "number",
                "description": "Tingkat keyakinan 0..1 (opsional, default 1.0).",
            },
        },
        "required": ["category", "content"],
    }

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root).resolve() if root else None

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        if self.root is None:
            raise ToolValidationError(
                "Project root tidak tersedia; Project Bible tidak dapat diperbarui."
            )

        category = arguments.get("category")
        content = arguments.get("content")
        if not category or not str(category).strip():
            raise ToolValidationError("Argumen 'category' wajib diisi.")
        if content is None or (isinstance(content, str) and not content.strip()):
            raise ToolValidationError("Argumen 'content' wajib diisi.")

        confidence = arguments.get("confidence", 1.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            raise ToolValidationError("Argumen 'confidence' harus berupa angka 0..1.")
        if not (0.0 <= confidence <= 1.0):
            raise ToolValidationError("Argumen 'confidence' harus berada di 0..1.")

        from agent_ai.projects.intelligence import ProjectIntelligence
        from agent_ai.projects.learning import IntelligenceLearner, LearningError

        intelligence = ProjectIntelligence.for_project(self.root)
        learner = IntelligenceLearner(intelligence)
        try:
            entry = learner.add_verified(
                str(category).strip(), content, confidence=confidence, source="consultant"
            )
        except LearningError as exc:
            raise ToolValidationError(str(exc)) from exc

        return {
            "saved": entry is not None,
            "duplicate": entry is None,
            "category": str(category).strip(),
        }


class ConsultantBoundedMapTool(BaseTool):
    """Wrapper READ-ONLY tool Project Map dengan bound retrieval Consultant.

    Mendelegasikan eksekusi ke tool map existing (atlas_query/rig_query) TANPA
    mengubahnya, tetapi menegakkan safety/control layer Consultant lewat
    `ConsultantRetrievalGuard`:

        - sebelum eksekusi  -> `guard.reserve(tool, args)`. Bila query harus
          DIBLOKIR (berulang / melewati batas / pencarian map sudah dihentikan),
          query TIDAK dieksekusi dan dikembalikan ToolResult "bound" yang jelas;
        - setelah eksekusi  -> `guard.record(tool, args, result)` (counter +
          deteksi zero-result beruntun).

    Ini murni boundary: wrapper TIDAK menalar jawaban. Nama/description/schema
    tool tetap identik dengan tool asli sehingga LLM melihat tool yang sama.
    """

    def __init__(self, inner: BaseTool, guard: "ConsultantRetrievalGuard") -> None:
        self._inner = inner
        self._guard = guard
        # Ekspos kontrak tool persis seperti tool asli (name/description/schema).
        self.name = inner.name
        self.description = inner.description
        self.input_schema = inner.input_schema

    def validate(self, arguments: Dict[str, Any]) -> None:
        # Delegasi validasi ke tool asli agar kontrak argumen tidak berubah.
        self._inner.validate(arguments)

    def execute(self, **arguments: Any) -> Any:
        decision = self._guard.reserve(self.name, dict(arguments or {}))
        if decision is not None:
            # Query diblokir oleh bound: JANGAN eksekusi tool asli.
            return decision
        result = self._inner.execute(**arguments)
        self._guard.record(self.name, dict(arguments or {}), result)
        return result


def build_consultant_registry(
    root: Optional[Path] = None,
    provider: Any = None,
    options: Any = None,
    mode: str = DEFAULT_CONSULTANT_MODE,
    guard: Optional["ConsultantRetrievalGuard"] = None,
):
    """Bangun ToolRegistry Consultant (kurasi READ-ONLY + Bible) sesuai mode.

    Tool yang TIDAK didaftarkan benar-benar tidak tersedia bagi LLM (arsitektur
    Native Tool Calling hanya menawarkan tool dari registry), jadi pembatasan
    mode bersifat struktural — bukan sekadar instruksi prompt.

    Args:
        root: root project target (opsional). Bila diisi, semua tool dibatasi
            ke root tersebut. Bila None, tool memakai default root-nya.
        provider/options: tidak dipakai saat ini (disediakan untuk ekstensi),
            dipertahankan agar signature stabil.
        mode: mode kanonik ("fast" | "balanced" | "deep") atau alias lama ("quick" | "investigate").
            - fast       : Project Map READ-ONLY + CodeGraph symbols + Skill System
                           + update_project_bible. TANPA pembacaan berkas source penuh
                           atau run_command.
            - balanced   : capability Fast + inspeksi berkas source (read_file, search_code,
                           list_files) dengan deduplikasi per giliran. TANPA run_command.
            - deep       : capability Balanced + full CodeGraph relational intelligence
                           (impact analysis, trace API, orphan detection) + run_command
                           diagnostik proyek (git read, pytest, build check).
        guard: bound retrieval opsional (ConsultantRetrievalGuard). Bila diisi,
            tool PENCARIAN map (atlas_query/rig_query) DAN tool investigasi
            (read_file/search_code/list_files/run_command) dibungkus
            `ConsultantBoundedMapTool` sehingga tool yang melewati batas jumlah
            pemanggilan diblokir. Bila None, perilaku identik dengan sebelumnya
            (backward compatible).
    Returns:
        ToolRegistry berisi tool yang AMAN untuk Consultant (tanpa tool tulis).
    """
    from agent_ai.tools.registry import ToolRegistry

    resolved = Path(root).resolve() if root is not None else None
    normalized = normalize_consultant_mode(mode)

    registry = ToolRegistry()

    # Project Map READ-ONLY tersedia di SEMUA mode Consultant (quick maupun
    # investigate): atlas_query, rig_query, project_map_status. `include_refresh
    # =False` -> `refresh_project_map` TIDAK pernah tersedia untuk Consultant,
    # sehingga Consultant tetap read-only terhadap Project Map (boleh query,
    # tidak boleh regenerate/menulis). Quick memakai map tanpa boleh membaca
    # source.
    #
    # Bound retrieval (opsional): tool PENCARIAN map dibungkus agar query
    # berulang / melewati batas / zero-result runaway dihentikan secara graceful.
    # `project_map_status` TIDAK dibungkus (bukan pencarian).
    from agent_ai.tools.project_map import build_project_map_tools

    for tool in build_project_map_tools(root=resolved, include_refresh=False):
        if guard is not None and guard.is_map_query_tool(tool.name):
            registry.register(ConsultantBoundedMapTool(tool, guard))
        else:
            registry.register(tool)

    # Skill System (Consultant): SATU mekanisme Skill yang sama dengan Agent
    # (catalog ringan + progressive loading di atas SkillStore existing).
    # Tersedia di SEMUA mode (quick & investigate). Thin adapter, tidak ada
    # heuristic/selector, tidak menambah write capability Consultant.
    from agent_ai.tools.skills import build_skill_tools as _build_skill_tools

    for tool in _build_skill_tools(root=resolved):
        registry.register(tool)

    # Semantic Search READ-ONLY (Phase 2.1): semantic_search (tanpa refresh_semantic_index).
    # Tersedia di SEMUA mode (quick & investigate). Read-only terhadap basis data vektor.
    from agent_ai.repointel.semantic.availability import is_available
    import os as _os

    if is_available()[0] or _os.environ.get("AEGIS_ENABLE_SEMANTIC_TOOLS") == "1":
        from agent_ai.tools.semantic import build_semantic_tools as _build_semantic_tools

        for tool in _build_semantic_tools(
            root=resolved, include_refresh=False, read_only=True, include_hybrid=True
        ):
            registry.register(tool)

    # CodeGraph Relational Intelligence (Fase 2.5 & Triad Harmonization):
    # Seluruh 6 tool CodeGraph bersifat READ-ONLY dan aman untuk Consultant.
    from agent_ai.tools.codegraph import build_codegraph_tools as _build_codegraph_tools

    for tool in _build_codegraph_tools(root=resolved):
        registry.register(tool)
    # Source inspection tools:
    if normalized in (MODE_BALANCED, "standard", MODE_DEEP, MODE_INVESTIGATE):
        from agent_ai.tools.filesystem import (
            ListFilesTool,
            ReadFileTool,
            SearchCodeTool,
        )
        from agent_ai.tools.read_cache import ToolReadCache

        read_cache = ToolReadCache()
        _investigation_tools = [
            ListFilesTool(root=resolved),
            ReadFileTool(root=resolved, read_cache=read_cache),
            SearchCodeTool(root=resolved, read_cache=read_cache),
        ]
        if normalized in (MODE_DEEP, MODE_INVESTIGATE):
            _investigation_tools.append(ConsultantRunCommandTool(root=resolved))

        for tool in _investigation_tools:
            if guard is not None and guard.is_map_query_tool(tool.name):
                registry.register(ConsultantBoundedMapTool(tool, guard))
            else:
                registry.register(tool)
    # Project Bible update tersedia di SEMUA mode (satu-satunya jalur tulis
    # Consultant). Project Bible READ dilakukan via konteks system message.
    registry.register(ConsultantBibleTool(root=resolved))
    return registry
