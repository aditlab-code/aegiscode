"""Project-local `.aegis` store: AI Project Bible + Task Log.

Struktur yang dikelola (di ROOT project target):

    <root project target>/
        .aegis/
            bible/
                index.md          # manifest/navigation (dibaca LLM)
                architecture.md
                ui.md
                conventions.md
                decisions.md
                facts.md
                learnings.md
                problems.md
            log/
                <task_id>.log     # log task (JSON Lines)
            skills/
                <skill_id>/
                    skill.md
                    references/   # referensi tambahan Skill
            ENVIRONMENT.md        # Environment Context (deteksi OS/shell/runtime)

Prinsip:
    - Project-local: semua ditulis di dalam root project target, tidak di
      workspace AegisCode.
    - AI-oriented: Bible ditulis sebagai markdown terstruktur (marker +
      key-value) yang padat & tidak ambigu untuk dibaca LLM.
    - Best-effort untuk Task Log: kegagalan menulis log TIDAK boleh
      menggagalkan eksekusi task.
    - Tidak ada dependency baru; tanpa DB/vektor/embeddings.
    - Idempotent: `ensure()` aman dipanggil berulang.

Modul ini adalah SATU-SATUNYA tempat penulisan `<root>/.aegis/`. ProjectBrain/
ProjectIntelligence membaca & menulis Bible hanya lewat sini.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.projects.models import (
    BIBLE_CATEGORIES,
    CATEGORY_ALIASES,
    IntelligenceEntry,
    _now_iso,
)

#: Nama folder root metadata project AegisCode.
AEGIS_DIR_NAME = ".aegis"
#: Nama folder root knowledge Antigravity native.
BRAIN_DIR_NAME = ".brain"
#: Subfolder log task.
LOG_DIR_NAME = "log"
#: Subfolder (di dalam `log/`) untuk log response mentah API LLM per task.
RESPONSE_LOG_DIR_NAME = "response"
#: Suffix file log response API LLM (satu file per task).
RESPONSE_LOG_SUFFIX = ".json"
#: Subfolder AI Project Bible.
BIBLE_DIR_NAME = "bible"
#: Nama file manifest Bible.
BIBLE_INDEX_NAME = "index.md"
#: Nama file Environment Context (didokumentasikan di environment.py).
ENVIRONMENT_FILE_NAME = "ENVIRONMENT.md"
#: Subfolder Skill di dalam bible (generic, project-local) — reuse pola Bible.
BIBLE_SKILLS_DIR_NAME = "skills"
#: Nama file skill utama.
SKILL_FILE_NAME = "skill.md"
#: Subfolder references untuk tiap skill.
SKILL_REFERENCES_DIR_NAME = "references"
#: Versi format file Bible (marker kompatibilitas).
BIBLE_FORMAT = "entry-v1"
#: Marker awal satu entri di file kategori Bible.
ENTRY_MARKER = "## entry"

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_TASK_ID_LEN = 96

#: Penjelasan tiap kategori Bible + kapan harus dibaca (untuk index.md).
_CATEGORY_GUIDE = (
    ("architecture", "struktur & layer utama project; baca sebelum mengubah struktur"),
    ("ui", "kontrak UI/frontend (komponen, layout, alur layar); baca sebelum menyentuh UI"),
    ("conventions", "aturan & konvensi coding project; baca sebelum menulis kode baru"),
    ("decisions", "keputusan teknis penting beserta alasannya; baca sebelum mengubah pendekatan"),
    ("facts", "fakta project (stack, dependency, versi, entry point); baca selalu"),
    ("learnings", "pelajaran dari task sebelumnya (termasuk yang gagal); baca untuk hindari kesalahan sama"),
    ("problems", "masalah/known-issue yang belum selesai; baca sebelum menyimpulkan selesai"),
    ("known_bugs", "bug/masalah yang sudah ditemukan/terverifikasi (BUG-xxx); baca sebelum memperbaiki"),
    ("known_gaps", "kekurangan/fitur yang belum tersedia tetapi bukan bug (GAP-xxx); baca sebelum menambah fitur"),
)


def new_task_id() -> str:
    """Buat task_id unik (bila execution tidak membawa task_id)."""
    return uuid.uuid4().hex


def safe_task_id(value: Any) -> str:
    """Normalisasi task_id menjadi nama file yang aman (tanpa path traversal).

    Mengembalikan string kosong bila `value` kosong / tidak menghasilkan
    karakter aman (pemanggil dapat memakai `new_task_id()`).
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Buang komponen path (cocok untuk '/' dan '\').
    text = text.replace("\\", "/").split("/")[-1]
    text = _SAFE_ID_RE.sub("_", text).strip("._-")
    if not text:
        return ""
    return text[:_MAX_TASK_ID_LEN]


def canonical_bible_category(category: str) -> str:
    """Petakan kategori (termasuk alias lama) ke nama kanonik Bible."""
    if category in BIBLE_CATEGORIES:
        return category
    return CATEGORY_ALIASES.get(category, category)


def _atomic_write(path: Path, text: str) -> None:
    """Tulis file secara atomik (temp + os.replace) agar tidak ada file parsial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".aegis_tmp_", suffix=".swp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


class AegisProjectStore:
    """Resolver path + pembuatan struktur `<root>/.aegis/` (idempotent).

    Args:
        root: root project target (folder project yang dikerjakan AegisCode).
    """

    def __init__(self, root: Union[str, Path], use_brain: bool = False) -> None:
        self.root = Path(root).resolve()
        target_dir = self.root / AEGIS_DIR_NAME
        self.aegis_dir = target_dir
        self.log_dir = target_dir / LOG_DIR_NAME
        self.response_log_dir = self.log_dir / RESPONSE_LOG_DIR_NAME

        # Auto-migrasi 1-kali dari legacy .aether bila .aegis belum ada
        self._auto_migrate_legacy_aether()

        brain_path = self.root / BRAIN_DIR_NAME
        aegis_path = target_dir / BIBLE_DIR_NAME

        # Layered Discovery untuk Knowledge/Bible:
        # Tier 1 (Antigravity Native / Explicit Brain): <root>/.brain/
        # Tier 2 (Aegis Default): <root>/.aegis/bible/
        if use_brain or brain_path.exists():
            self.bible_dir = brain_path
        else:
            self.bible_dir = aegis_path

    def _auto_migrate_legacy_aether(self) -> None:
        """Migrasi otomatis 1-kali jika folder .aether ada namun .aegis belum ada."""
        legacy_dir = self.root / ".aether"
        if legacy_dir.exists() and not self.aegis_dir.exists():
            try:
                import shutil
                shutil.copytree(str(legacy_dir), str(self.aegis_dir), dirs_exist_ok=True)
            except Exception:
                pass
    def ensure(self) -> bool:
        """Pastikan `.aegis/`, `.aegis/log/`, `.aegis/bible/` ada.

        Returns:
            True bila struktur siap, False bila gagal (tidak melempar error).
        """
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.bible_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False

    def log_path(self, task_id: Any) -> Path:
        """Path log task untuk `task_id` (task_id dibuat bila kosong)."""
        name = safe_task_id(task_id) or new_task_id()
        return self.log_dir / f"{name}.log"

    def response_log_path(self, task_id: Any) -> Path:
        """Path log response API LLM untuk `task_id` (task_id dibuat bila kosong).

        Satu file per task: `<root>/.aegis/log/response/<task_id>.json`.
        """
        name = safe_task_id(task_id) or new_task_id()
        return self.response_log_dir / f"{name}{RESPONSE_LOG_SUFFIX}"

    def bible_path(self, category: str) -> Path:
        """Path file kategori Bible (alias dinormalisasi) dengan 3-tier fallback."""
        cat_file = f"{canonical_bible_category(category)}.md"
        primary = self.bible_dir / cat_file
        if primary.exists():
            return primary
        for cand in [
            self.root / BRAIN_DIR_NAME / cat_file,
            self.root / AEGIS_DIR_NAME / BIBLE_DIR_NAME / cat_file,
        ]:
            if cand.exists():
                return cand
        return primary

    def index_path(self) -> Path:
        """Path file manifest Bible (`index.md`) dengan 3-tier fallback."""
        primary = self.bible_dir / BIBLE_INDEX_NAME
        if primary.exists():
            return primary
        for cand in [
            self.root / BRAIN_DIR_NAME / BIBLE_INDEX_NAME,
            self.root / AEGIS_DIR_NAME / BIBLE_DIR_NAME / BIBLE_INDEX_NAME,
        ]:
            if cand.exists():
                return cand
        return primary
    def environment_path(self) -> Path:
        """Path file Environment Context (`<root>/.aegis/ENVIRONMENT.md`)."""
        return self.aegis_dir / ENVIRONMENT_FILE_NAME

    def skills_dir(self) -> Path:
        """Directory `<root>/.aegis/bible/skills` (project-local Skill store)."""
        return self.bible_dir / BIBLE_SKILLS_DIR_NAME

    def skill_dir(self, skill_id: str) -> Path:
        """Directory skill `<root>/.aegis/bible/skills/<skill_id>`."""
        from agent_ai.projects.skills import validate_skill_id
        return self.skills_dir() / validate_skill_id(skill_id)

    def skill_path(self, skill_id: str) -> Path:
        """Path file `skill.md` untuk sebuah Skill."""
        return self.skill_dir(skill_id) / SKILL_FILE_NAME

    def __repr__(self) -> str:  # pragma: no cover - bantuan debug
        return f"<AegisProjectStore root={self.root}>"

    # ------------------------------------------------------------------ #
    # Task Log Discovery
    # ------------------------------------------------------------------ #
    def list_task_logs(self) -> List[Path]:
        """Daftar semua file log task di `.aegis/log/`.

        Returns:
            Daftar Path file .log, terurut terbaru ke terlama
            (berdasarkan mtime file).
        """
        if not self.log_dir.exists():
            return []
        return sorted(
            [p for p in self.log_dir.glob("*.log") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )


class TaskLog:
    """Writer log task project-local (append-only JSON Lines, best-effort).

    Satu file per task: `<root>/.aegis/log/<task_id>.log`. Semua kegagalan
    (folder tidak bisa dibuat, disk penuh, dsb.) ditelan dan hanya menghasilkan
    `False` agar TIDAK pernah menggagalkan eksekusi task.
    """

    def __init__(self, root: Union[str, Path, AegisProjectStore], task_id: Any = None) -> None:
        self.store = root if isinstance(root, AegisProjectStore) else AegisProjectStore(root)
        self.task_id = safe_task_id(task_id) or new_task_id()
        self.store.ensure()
        self.path = self.store.log_path(self.task_id)

    @staticmethod
    def resolve_task_id(task_id: Any) -> str:
        """Gunakan task_id yang ada, atau buat baru bila kosong/tidak valid."""
        return safe_task_id(task_id) or new_task_id()

    def append(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Tambahkan satu event ke log (best-effort). Returns True bila tertulis."""
        record: Dict[str, Any] = {
            "timestamp": _now_iso(),
            "task_id": self.task_id,
            "event": str(event_type),
        }
        if payload:
            record["data"] = payload
        # Sanitasi (tanpa secret) memakai helper observability existing.
        # Batas string SPESIFIK EVENT dipakai agar event yang membawa hasil tool
        # (mis. `observation_received`) tidak kehilangan payload diagnostik,
        # sementara payload lain tetap dibatasi seperti sebelumnya.
        try:
            from agent_ai.core.observability import sanitize_event_payload

            event_type = str(event_type)
            record["event"] = event_type
            record = sanitize_event_payload(event_type, record)
        except Exception:  # noqa: BLE001 - sanitasi gagal -> tetap catat
            pass
        try:
            self.store.ensure()
            line = json.dumps(record, ensure_ascii=False, default=str)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return True
        except Exception:  # noqa: BLE001 - log tidak boleh menggagalkan task
            return False


class ResponseLog:
    """Writer log response mentah API LLM per task (best-effort).

    Satu file per task: `<root>/.aegis/log/response/<task_id>.json`. File
    berisi SATU objek JSON dengan kunci `responses` = daftar record untuk
    SETIAP round/request LLM dalam task tersebut (append-only secara semantik;
    record lama dipertahankan).

    Tujuan: mencatat APA yang benar-benar diterima AegisCode dari API LLM —
    termasuk response yang diterima sebelum error (partial response bila
    tersedia) — sehingga kasus API terputus dapat dianalisis dari file log.

    Layout file::

        {
          "task_id": "<task_id>",
          "created_at": "<iso>",
          "updated_at": "<iso>",
          "responses": [ { "round": 1, "provider": ..., ... }, ... ]
        }

    Semua kegagalan (folder tidak bisa dibuat, disk penuh, JSON tidak valid,
    dsb.) ditelan dan hanya menghasilkan `False` agar logging TIDAK pernah
    menggagalkan eksekusi task. Directory `.aegis/log/response/` dibuat
    otomatis saat diperlukan.
    """

    def __init__(self, root: Union[str, Path, AegisProjectStore], task_id: Any = None) -> None:
        self.store = root if isinstance(root, AegisProjectStore) else AegisProjectStore(root)
        self.task_id = safe_task_id(task_id) or new_task_id()
        self.store.ensure()
        self.path = self.store.response_log_path(self.task_id)
        self._loaded = False
        self._created_at: Optional[str] = None
        self._responses: List[Dict[str, Any]] = []

    @staticmethod
    def resolve_task_id(task_id: Any) -> str:
        """Gunakan task_id yang ada, atau buat baru bila kosong/tidak valid."""
        return safe_task_id(task_id) or new_task_id()

    def _load(self) -> None:
        """Muat record yang sudah ada (sekali) agar append tidak menghilangkan data."""
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - file rusak -> mulai dari kosong
            return
        if isinstance(data, dict):
            created = data.get("created_at")
            if isinstance(created, str) and created:
                self._created_at = created
            responses = data.get("responses")
            if isinstance(responses, list):
                self._responses = [r for r in responses if isinstance(r, dict)]
        elif isinstance(data, list):  # toleran terhadap format array lama
            self._responses = [r for r in data if isinstance(r, dict)]

    def append(self, record: Dict[str, Any]) -> bool:
        """Tambahkan SATU record response ke file task (best-effort, disanitasi).

        Returns:
            True bila tertulis, False bila gagal (tidak pernah melempar).
        """
        try:
            self._load()
            if not isinstance(record, dict):
                return False
            from agent_ai.core.observability import sanitize_payload

            clean_record = sanitize_payload(record, max_string_len=100_000)
            if self._created_at is None:
                self._created_at = _now_iso()
            self._responses.append(dict(clean_record))
            payload: Dict[str, Any] = {
                "task_id": self.task_id,
                "created_at": self._created_at,
                "updated_at": _now_iso(),
                "responses": self._responses,
            }
            _atomic_write(
                self.path,
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
            return True
        except Exception:  # noqa: BLE001 - log tidak boleh menggagalkan task
            return False


class BibleStore:
    """Storage AI Project Bible berbasis markdown project-local.

    Kategori dipetakan ke file `<kategori>.md` di `<root>/.aegis/bible/`.
    Format berorientasi LLM: header marker + blok entri key-value (lihat
    `BIBLE_FORMAT`). Append-only secara semantik (knowledge lama dipertahankan).
    """

    categories = BIBLE_CATEGORIES

    def __init__(self, root: Union[str, Path, AegisProjectStore], use_brain: bool = False) -> None:
        if isinstance(root, AegisProjectStore):
            self.store = root
        else:
            self.store = AegisProjectStore(root, use_brain=use_brain)
    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def ensure(self) -> bool:
        """Buat folder + file kategori + index bila belum ada (idempotent)."""
        if not self.store.ensure():
            return False
        try:
            index = self.store.index_path()
            if not index.exists():
                _atomic_write(index, self._index_text())
            for category in BIBLE_CATEGORIES:
                path = self.store.bible_path(category)
                if not path.exists():
                    _atomic_write(path, self._header(category))
            return True
        except OSError:
            return False

    @property
    def root(self) -> Path:
        return self.store.root

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def read_category(self, category: str) -> List[IntelligenceEntry]:
        """Baca semua entri satu kategori (toleran terhadap file rusak)."""
        path = self.store.bible_path(category)
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        return self._parse(text)

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def add_entry(self, category: str, entry: IntelligenceEntry) -> IntelligenceEntry:
        """Tambahkan entri ke kategori (append; knowledge lama dipertahankan)."""
        self.ensure()
        entries = self.read_category(category)
        entries.append(entry)
        self._write_category(category, entries)
        return entry

    def update_entry(
        self,
        category: str,
        entry_id: str,
        **changes: Any,
    ) -> IntelligenceEntry:
        """Update entri berdasarkan id (raise EntryNotFoundError bila tidak ada)."""
        from agent_ai.projects.intelligence import EntryNotFoundError

        entries = self.read_category(category)
        for entry in entries:
            if entry.id == entry_id:
                for key, value in changes.items():
                    if hasattr(entry, key):
                        setattr(entry, key, value)
                entry.updated_at = _now_iso()
                self._write_category(category, entries)
                return entry
        raise EntryNotFoundError(f"Entry '{entry_id}' tidak ditemukan di kategori '{category}'.")

    def get_entry(self, category: str, entry_id: str) -> Optional[IntelligenceEntry]:
        """Ambil entri berdasarkan id (None bila tidak ada)."""
        for entry in self.read_category(category):
            if entry.id == entry_id:
                return entry
        return None

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def _header(self, category: str) -> str:
        return (
            f"# bible:{category}\n"
            f"<!-- AEGIS BIBLE (machine-readable). format={BIBLE_FORMAT}. -->\n"
            f"<!-- Setiap entri dimulai dengan marker '{ENTRY_MARKER}'. -->\n"
            "<!-- Tambahkan knowledge lewat ProjectBrain/AegisCode; jangan edit manual. -->\n"
            "\n"
        )

    def _write_category(self, category: str, entries: List[IntelligenceEntry]) -> None:
        blocks = [self._header(category).rstrip("\n")]
        for entry in entries:
            blocks.append(self._serialize_entry(entry))
        _atomic_write(self.store.bible_path(category), "\n\n".join(blocks) + "\n")

    @staticmethod
    def _serialize_entry(entry: IntelligenceEntry) -> str:
        content = json.dumps(entry.content, ensure_ascii=False, default=str)
        return "\n".join(
            [
                ENTRY_MARKER,
                f"- id: {entry.id}",
                f"- source: {entry.source}",
                f"- confidence: {entry.confidence}",
                f"- created_at: {entry.created_at}",
                f"- updated_at: {entry.updated_at}",
                f"- content: {content}",
            ]
        )

    @staticmethod
    def _parse(text: str) -> List[IntelligenceEntry]:
        """Parse file kategori menjadi entri (toleran; bagian rusak dilewati)."""
        raw_entries: List[Dict[str, str]] = []
        current: Optional[Dict[str, str]] = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == ENTRY_MARKER:
                if current is not None:
                    raw_entries.append(current)
                current = {}
                continue
            if current is None or not stripped.startswith("- "):
                continue
            body = stripped[2:]
            if ": " in body:
                key, value = body.split(": ", 1)
            elif body.endswith(":"):
                key, value = body[:-1], ""
            else:
                continue
            current[key.strip()] = value
        if current is not None:
            raw_entries.append(current)

        entries: List[IntelligenceEntry] = []
        for raw in raw_entries:
            content = BibleStore._parse_content(raw.get("content"))
            if content is None:
                continue
            if isinstance(content, str) and not content.strip():
                continue
            entries.append(
                IntelligenceEntry(
                    id=raw.get("id") or uuid.uuid4().hex,
                    content=content,
                    source=raw.get("source", "ai"),
                    confidence=_parse_confidence(raw.get("confidence")),
                    created_at=raw.get("created_at") or _now_iso(),
                    updated_at=raw.get("updated_at") or _now_iso(),
                )
            )
        return entries

    @staticmethod
    def _parse_content(value: Optional[str]) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value  # fallback: pakai teks mentah

    def _index_text(self) -> str:
        lines = [
            "# Project Bible",
            "",
            "<!-- AEGIS BIBLE index (machine-readable). Manifest/navigation. -->",
            "<!-- Knowledge project untuk agen AI. Baca kategori relevan sebelum",
            "     bekerja; tulis lewat ProjectBrain/AegisCode, jangan edit manual. -->",
            "",
            "## categories",
        ]
        for category, guide in _CATEGORY_GUIDE:
            lines.append(f"- {category} (file: {category}.md) — {guide}")
        lines.append("")
        lines.append("## format")
        lines.append(f"- {BIBLE_FORMAT}; satu entri dipisah marker '{ENTRY_MARKER}'")
        lines.append("- field: id, source, confidence, created_at, updated_at, content")
        lines.append("")
        return "\n".join(lines)


def _parse_confidence(value: Optional[str]) -> float:
    """Parse confidence dari teks; fallback 1.0 bila tidak valid."""
    if value is None:
        return 1.0
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 1.0
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return confidence


class TaskLogReader:
    """Reader log task project-local (read-only, JSON Lines).

    Membaca file `.aegis/log/<task_id>.log` yang sudah ada.
    Tidak menulis atau memodifikasi log apa pun.

    Args:
        root: root project target (string atau Path).
        task_id: identifier task.
    """

    def __init__(self, root: Union[str, Path, AegisProjectStore], task_id: Any = None) -> None:
        self.store = root if isinstance(root, AegisProjectStore) else AegisProjectStore(root)
        self.task_id = safe_task_id(task_id) or new_task_id()
        self.path = self.store.log_path(self.task_id)

    def _read_lines(self) -> List[str]:
        """Baca semua baris dari file log (best-effort, toleran terhadap error)."""
        if not self.path.exists():
            return []
        try:
            text = self.path.read_text(encoding="utf-8")
            return [line for line in text.splitlines() if line.strip()]
        except OSError:
            return []

    def load_events(self) -> List[Dict[str, Any]]:
        """Baca semua event dari log task, parse JSON, abaikan baris rusak.

        Returns:
            Daftar event terurut chronological (sesuai urutan penulisan).
            Setiap event adalah dict dengan kunci: timestamp, task_id, event, data.
            Baris yang tidak valid secara JSON dilewati tanpa merusak event lain.
        """
        events: List[Dict[str, Any]] = []
        for line in self._read_lines():
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(event, dict):
                continue
            events.append(event)
        return events

    def read_events(self) -> List[Dict[str, Any]]:
        """Alias untuk load_events() demi kompatibilitas pemanggil."""
        return self.load_events()

    def get_task_info(self) -> Optional[Dict[str, Any]]:
        """Ambil ringkasan task dari log (task_id, first/last timestamp, status, prompt).

        Returns:
            Dict dengan task_id, first_timestamp, last_timestamp, status, task (prompt).
            None bila log tidak ditemukan atau kosong.
        """
        events = self.load_events()
        if not events:
            return None

        first_ts = events[0].get("timestamp")
        last_ts = events[-1].get("timestamp")

        # Cari status terminal dan prompt.
        status = "incomplete"
        prompt = ""
        result = None
        error = None
        has_active_work = False

        for ev in events:
            evt = ev.get("event", "")
            data = ev.get("data", {}) or {}
            if evt == "task_requested":
                prompt = data.get("prompt", "")
            elif evt == "task_renamed":
                prompt = data.get("title") or data.get("prompt") or prompt
                has_active_work = True
            elif evt in ("task_started", "tool_called", "tool_completed", "agent_reasoning_delta", "agent_commentary"):
                has_active_work = True
            elif evt == "task_completed":
                status = "completed"
                result = data.get("result")
            elif evt == "task_failed":
                status = "failed"
                error = data.get("error")
            elif evt == "task_cancelled":
                status = "cancelled"
            elif evt == "task_finished":
                # task_finished bisa jadi fallback status; gunakan bila belum ada status terminal.
                if status not in ("completed", "failed", "cancelled"):
                    status = data.get("status", "incomplete")
                    if data.get("result") is not None and result is None:
                        result = data.get("result")
                    if data.get("error") is not None and error is None:
                        error = data.get("error")

        if status == "incomplete" and has_active_work:
            status = "running"

        return {
            "task_id": self.task_id,
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
            "status": status,
            "task": prompt,
            "result": result,
            "error": error,
        }

    def get_activity(self, event_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Ambil seluruh activity chronological untuk task ini.

        Args:
            event_types: daftar tipe event yang relevan untuk activity.
                Bila None, semua event termasuk tool activity ikut diambil.

        Returns:
            Daftar event terurut chronological berdasarkan timestamp.
        """
        events = self.load_events()
        if event_types is not None:
            events = [e for e in events if e.get("event") in event_types]
        return events

    def get_report(self) -> Optional[str]:
        """Ambil final Agent Report dari task_completed atau task_finished.

        Source utama: task_completed.data.result.
        Fallback: task_finished.data.result.

        Returns:
            Teks report final atau None bila tidak ditemukan.
        """
        events = self.load_events()
        for ev in reversed(events):
            evt = ev.get("event", "")
            data = ev.get("data", {}) or {}
            if evt == "task_completed" and "result" in data:
                return data["result"]
            if evt == "task_finished" and "result" in data:
                return data["result"]
        return None

