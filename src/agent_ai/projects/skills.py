"""Skill System — Foundation & Storage (Task 01) + Progressive Loading (Task 03).

Fondasi Skill System AegisCode sebagai kemampuan generik untuk menyimpan dan
mengelola Skill. Task 01 : storage, Task 02 : catalog/discovery, Task 03 :
progressive loading dengan context safety.

Fokus Task 03 hanya pada:
    - generic load_skill(skill_id)  -> skill.md
    - generic load_skill_reference(skill_id, reference) -> references/<reference>
    - catalog tetap ringan (metadata saja)
    - reuse SkillStore / SkillCatalogEntry
    - tidak membuat storage subsystem baru
    - tidak mengubah compression.enabled (harus tetap false)
    - tidak melakukan truncation/compression otomatis

Struktur project-level yang dikelola (di ROOT project target)::

    <root project target>/
        .aegis/
            bible/
                skills/
                    <skill_id>/
                        skill.md
                        references/   # opsional, untuk referensi tambahan

Alur progressive loading::

    Catalog (metadata ringan)
      ↓
    LLM memilih skill_id
      ↓
    load_skill(skill_id) -> skill.md (content + metadata)
      ↓
    jika diperlukan -> load_skill_reference(skill_id, reference) -> references/<reference>

Prinsip (reuse Bible):
    - Project-local: semua ditulis di dalam root project target, tidak di
      workspace AETHER (single source of truth).
    - File lifecycle memakai pola Bible: _atomic_write, safe_id, ensure
      idempotent, best-effort yang tidak menggagalkan task, toleran terhadap
      file rusak (skip, bukan crash).
    - Tidak ada dependency baru; tanpa DB/vektor/embeddings.
    - Generic: Core hanya memahami skill, skill_id, name, description, scope,
      location. Nama directory Skill bersifat dynamic, tidak di-hardcode.
    - Persistence via filesystem (markdown + frontmatter).
    - Progressive: catalog tidak berisi skill.md / reference content.
      load_skill hanya membaca skill.md yang diminta (dynamic).
      reference hanya dibaca bila diminta eksplisit via nama/path.
    - Context safety: tidak membuat compression/truncation baru,
      tidak memotong context demi hemat token, tidak memaksa reread bila
      informasi sudah ada di context (pemanggil dapat memanfaatkan cache
      existing), tujuan progressive adalah menghindari load yang tidak perlu.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.projects.aegis_store import (
    AEGIS_DIR_NAME,
    AegisProjectStore,
    BIBLE_SKILLS_DIR_NAME,
    SKILL_FILE_NAME,
    SKILL_REFERENCES_DIR_NAME,
    _atomic_write,
)
from agent_ai.projects.models import (
    SKILL_SCOPE_PROJECT,
    SKILL_SCOPES,
    Skill,
    SkillCatalogEntry,
    _now_iso,
)

# Skill id: hanya alfanumerik + . _ - , panjang 1..64, tidak ada path separator.
_SAFE_SKILL_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_SKILL_ID_LEN = 64
_VALID_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

#: Kandidat nama berkas skill (SKILL.md kapital standar Addy Osmani / Antigravity, skill.md legacy).
SKILL_FILE_CANDIDATES = ("SKILL.md", "skill.md")


def _find_skill_file(skill_dir: Path) -> Optional[Path]:
    """Cari SKILL.md atau skill.md di dalam direktori skill.

    Returns:
        Path berkas jika ditemukan dan merupakan file, None jika tidak ada.
    """
    if not skill_dir.is_dir():
        return None
    for name in SKILL_FILE_CANDIDATES:
        p = skill_dir / name
        if p.is_file():
            return p
    return None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class SkillError(Exception):
    """Base error untuk Skill System."""


class InvalidSkillIdError(SkillError):
    """skill_id tidak valid (kosong / karakter ilegal / terlalu panjang)."""


class SkillNotFoundError(SkillError):
    """Skill tidak ditemukan."""


class SkillAlreadyExistsError(SkillError):
    """Skill sudah ada (create duplikat)."""


class SkillReferenceNotFoundError(SkillError):
    """Reference file tidak ditemukan untuk Skill yang diminta."""


# ---------------------------------------------------------------------------
# Helpers — safe id & validation (reuse pola safe_task_id)
# ---------------------------------------------------------------------------
def safe_skill_id(value: Any) -> str:
    """Normalisasi skill_id menjadi nama directory yang aman.

    Mengembalikan string kosong bila `value` kosong / tidak menghasilkan
    karakter aman. Tidak melakukan lowercasing — case dipertahankan agar
    generic.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Buang komponen path (cocok untuk '/' dan '\\').
    text = text.replace("\\", "/").split("/")[-1]
    text = _SAFE_SKILL_ID_RE.sub("-", text).strip("._-")
    if not text:
        return ""
    return text[:_MAX_SKILL_ID_LEN]


def validate_skill_id(skill_id: str) -> str:
    """Validasi skill_id strict; raise InvalidSkillIdError bila tidak valid.

    Returns:
        skill_id yang sudah di-strip (tanpa normalisasi agresif).
    """
    if not isinstance(skill_id, str):
        raise InvalidSkillIdError("skill_id harus berupa string.")
    raw = skill_id.strip()
    if not raw:
        raise InvalidSkillIdError("skill_id tidak boleh kosong.")
    if len(raw) > _MAX_SKILL_ID_LEN:
        raise InvalidSkillIdError(
            f"skill_id terlalu panjang (max {_MAX_SKILL_ID_LEN} karakter)."
        )
    if "/" in raw or "\\" in raw:
        raise InvalidSkillIdError("skill_id tidak boleh mengandung path separator.")
    if not _VALID_SKILL_ID_RE.match(raw):
        raise InvalidSkillIdError(
            "skill_id hanya boleh berisi huruf, angka, '.', '_', '-'."
        )
    # Normalisasi via safe_skill_id harus round-trip identik (menolak karakter aneh).
    normalized = safe_skill_id(raw)
    if normalized != raw:
        raise InvalidSkillIdError(
            f"skill_id '{raw}' mengandung karakter tidak valid (normalisasi -> '{normalized}')."
        )
    return raw


def canonical_skill_scope(scope: str) -> str:
    """Normalisasi scope Skill.

    Saat ini hanya 'project' yang didukung (Task 01). Desain tetap generic
    untuk ekstensi masa depan — nilai selain yang dikenal akan ditolak.
    """
    if scope in SKILL_SCOPES:
        return scope
    raise SkillError(
        f"Scope '{scope}' tidak dikenal. Tersedia: {', '.join(SKILL_SCOPES)}"
    )


def _validate_reference_name(reference: str) -> str:
    """Validasi nama/path reference generic (tanpa heuristic bahasa/framework).

    Reference dipilih berdasarkan nama/path yang diberikan pemanggil, bukan
    heuristic. Validasi hanya memastikan:
      - bukan kosong
      - bukan absolute path
      - tidak mengandung path traversal (..)
      - tidak mengandung null byte

    Mengembalikan reference yang sudah di-strip (normalisasi slash ke /,
    buang leading ./).
    Raises SkillError bila tidak valid.
    """
    if not isinstance(reference, str):
        raise SkillError("reference harus berupa string.")
    raw = reference.strip()
    if not raw:
        raise SkillError("reference tidak boleh kosong.")
    if "\x00" in raw:
        raise SkillError("reference tidak boleh mengandung null byte.")
    # Normalisasi backslash
    raw = raw.replace("\\", "/")
    # Tolak absolute path (unix / windows)
    if raw.startswith("/") or raw.startswith("\\"):
        raise SkillError(f"reference '{reference}' tidak boleh absolute path.")
    # Tolak drive letter pattern (C:/, C:\)
    if len(raw) >= 2 and raw[1] == ":":
        raise SkillError(f"reference '{reference}' tidak boleh absolute path.")
    # Buang leading ./ berulang
    while raw.startswith("./"):
        raw = raw[2:]
    if not raw:
        raise SkillError("reference tidak boleh kosong setelah normalisasi.")
    # Cek komponen path traversal
    parts = raw.split("/")
    for part in parts:
        if part == "..":
            raise SkillError(f"reference '{reference}' tidak boleh mengandung '..' (path traversal).")
        # Empty part indicates // — tolak agar tidak ambigu
        if part == "" and raw != "":
            # allow trailing slash? we treat as directory — but reference should be file
            # reject empty segment in the middle
            # e.g. a//b
            if "//" in raw:
                raise SkillError(f"reference '{reference}' mengandung path kosong '//'.")
    # Reject reference = "." or "./"
    if raw == ".":
        raise SkillError("reference tidak boleh '.'")
    return raw


# ---------------------------------------------------------------------------
# Frontmatter helpers (tanpa dependency YAML — simple key: value)
# ---------------------------------------------------------------------------
def _parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    """Parse skill.md menjadi (frontmatter dict, body).

    Format yang didukung::

        ---
        name: My Skill
        description: ...
        scope: project
        ---
        <body markdown>

    Jika tidak ada frontmatter, kembalikan dict kosong dan body = text.
    Toleran: baris tanpa ': ' diabaikan, key di-strip.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    # Cari penutup '---' kedua
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        # Tidak ada penutup — anggap tidak ada frontmatter
        return {}, text
    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :])
    fm: Dict[str, str] = {}
    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ": " in stripped:
            key, value = stripped.split(": ", 1)
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
            value = value.strip()
        val = value.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        fm[key.strip()] = val
    return fm, body


def _serialize_frontmatter(skill: Skill) -> str:
    """Serialisasi Skill menjadi teks skill.md (frontmatter + body)."""
    # Frontmatter minimal: name, description, scope. Tambahkan created_at/updated_at
    # untuk lifecycle; location tidak disimpan di frontmatter (derived dari path).
    fm_lines = [
        "---",
        f"name: {skill.name}",
        f"description: {skill.description}",
        f"scope: {skill.scope}",
        f"skill_id: {skill.skill_id}",
        f"created_at: {skill.created_at}",
        f"updated_at: {skill.updated_at}",
        "---",
        "",
    ]
    body = skill.content or ""
    # Pastikan body diakhiri newline
    if body and not body.endswith("\n"):
        body += "\n"
    return "\n".join(fm_lines) + body


def _skill_from_file(skill_id: str, path: Path) -> Optional[Skill]:
    """Baca satu skill.md menjadi Skill; None bila file rusak/tidak bisa dibaca."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, body = _parse_frontmatter(text)
    # Frontmatter bersifat opsional — bila kosong, gunakan default generik
    name = fm.get("name") or skill_id
    description = fm.get("description") or ""
    scope_raw = fm.get("scope") or SKILL_SCOPE_PROJECT
    try:
        scope = canonical_skill_scope(scope_raw)
    except SkillError:
        scope = SKILL_SCOPE_PROJECT
    created_at = fm.get("created_at") or _now_iso()
    updated_at = fm.get("updated_at") or created_at
    # skill_id di frontmatter harus konsisten dengan directory; directory menang
    return Skill(
        skill_id=skill_id,
        name=name,
        description=description,
        scope=scope,
        content=body,
        location=str(path.resolve()),
        created_at=created_at,
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# SkillStore — storage project-local (reuse pola BibleStore)
# ---------------------------------------------------------------------------
class SkillStore:
    """Storage Skill berbasis filesystem native & project-local.

    Mendukung auto-discovery native berkas `SKILL.md` (Addy Osmani / Antigravity spec)
    maupun `skill.md` pada struktur folder:
      1. `<root>/.agents/skills/<skill_id>/SKILL.md`
      2. `<root>/skills/<skill_id>/SKILL.md`
      3. `<root>/.aegis/bible/skills/<skill_id>/skill.md` (backward-compatibility fallback)
      4. `<aegis_central_dir>/skills/<skill_id>/SKILL.md` (on-demand lintas proyek di IDE bila include_central aktif)

    Args:
        root: root project target (string/Path) atau instance ``AegisProjectStore``.
        include_central: apakah menyertakan direktori sentral AegisCode saat mencari skill
            (default False untuk isolasi per proyek/test, True saat diakses di level IDE).
    """

    def __init__(
        self,
        root: Union[str, Path, AegisProjectStore],
        include_central: Optional[bool] = None,
    ) -> None:
        self.store = root if isinstance(root, AegisProjectStore) else AegisProjectStore(root)
        if include_central is None:
            import os
            self.include_central = os.environ.get("AEGIS_INCLUDE_CENTRAL_SKILLS", "").strip().lower() in ("1", "true", "yes")
        else:
            self.include_central = bool(include_central)

    # ------------------------------------------------------------------ #
    # Layout helpers & Multi-directory Discovery
    # ------------------------------------------------------------------ #
    @property
    def root(self) -> Path:
        return self.store.root

    @property
    def candidate_skills_dirs(self) -> List[Path]:
        """Daftar direktori pencarian skills terurut prioritas."""
        dirs: List[Path] = [
            self.root / ".agents" / "skills",
            self.root / "skills",
            self.store.bible_dir / BIBLE_SKILLS_DIR_NAME,
        ]
        try:
            from agent_ai.core.agent_prompt import get_aegis_central_dir
            central = get_aegis_central_dir()
            if self.include_central and central.resolve() != self.root.resolve():
                dirs.append(central / ".agents" / "skills")
                dirs.append(central / "skills")
        except Exception:
            pass
        return dirs

    @property
    def primary_skills_dir(self) -> Path:
        """Direktori utama untuk penulisan/pembuatan skill baru."""
        dot_agents = self.root / ".agents" / "skills"
        if dot_agents.is_dir():
            return dot_agents
        plain_skills = self.root / "skills"
        if plain_skills.is_dir():
            return plain_skills
        return dot_agents

    @property
    def skills_dir(self) -> Path:
        """Direktori skills yang aktif (kompatibilitas backward)."""
        for d in self.candidate_skills_dirs:
            if d.is_dir():
                return d
        return self.primary_skills_dir

    def skill_dir(self, skill_id: str) -> Path:
        """Direktori untuk sebuah Skill (lokasi yang ada atau primary)."""
        sid = validate_skill_id(skill_id)
        for d in self.candidate_skills_dirs:
            target = d / sid
            if _find_skill_file(target) is not None:
                return target
        return self.primary_skills_dir / sid

    def skill_path(self, skill_id: str) -> Path:
        """Path file SKILL.md/skill.md untuk sebuah Skill."""
        sid = validate_skill_id(skill_id)
        for d in self.candidate_skills_dirs:
            target = d / sid
            found = _find_skill_file(target)
            if found is not None:
                return found
        return self.primary_skills_dir / sid / "SKILL.md"

    def references_dir(self, skill_id: str) -> Path:
        """Directory references untuk sebuah Skill."""
        return self.skill_dir(skill_id) / SKILL_REFERENCES_DIR_NAME

    # ------------------------------------------------------------------ #
    # ensure — idempotent
    # ------------------------------------------------------------------ #
    def ensure(self) -> bool:
        """Pastikan struktur direktori skills ada."""
        try:
            self.store.ensure()
            self.primary_skills_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------ #
    # Discovery — list semua Skill (native multi-directory, toleran)
    # ------------------------------------------------------------------ #
    def list_skills(self) -> List[Skill]:
        """Daftar semua Skill di project ini (dan sentral bila diaktifkan).

        Returns:
            Daftar Skill terurut alfabetis berdasarkan skill_id (deterministik).
        """
        skills_map: Dict[str, Skill] = {}
        for d in self.candidate_skills_dirs:
            if not d.exists() or not d.is_dir():
                continue
            try:
                entries = sorted(
                    [p for p in d.iterdir() if p.is_dir()],
                    key=lambda p: p.name.lower(),
                )
            except OSError:
                continue
            for entry in entries:
                skill_id = entry.name
                try:
                    validate_skill_id(skill_id)
                except InvalidSkillIdError:
                    continue
                if skill_id in skills_map:
                    continue
                file_path = _find_skill_file(entry)
                if file_path is None:
                    continue
                skill = _skill_from_file(skill_id, file_path)
                if skill is not None:
                    skills_map[skill_id] = skill

        return [skills_map[k] for k in sorted(skills_map.keys())]

    def list_skill_ids(self) -> List[str]:
        """Daftar skill_id saja (lebih ringan dari list_skills)."""
        return [s.skill_id for s in self.list_skills()]

    # ------------------------------------------------------------------ #
    # Skill Catalog / Discovery (Task 02) — metadata ringan, dynamic
    # ------------------------------------------------------------------ #
    def get_catalog(self) -> List[SkillCatalogEntry]:
        """Skill Catalog ringan untuk discovery LLM.

        Catalog hanya berisi metadata (skill_id, name, description, scope,
        location) tanpa isi skill.md / references / Bible. Deterministik
        (terurut alfabetis berdasarkan skill_id) dan dynamic — membaca
        langsung dari storage via ``list_skills()`` sehingga create/delete
        otomatis tercermin tanpa daftar hardcode.

        Tidak melakukan auto-selection, scoring, atau ranking — hanya
        menyediakan informasi agar LLM yang memilih 0/1/beberapa Skill.

        Returns:
            Daftar ``SkillCatalogEntry`` terurut (deterministik). List kosong
            bila belum ada Skill.
        """
        return [_to_catalog_entry(s) for s in self.list_skills()]

    def get_catalog_entry(self, skill_id: str) -> Optional[SkillCatalogEntry]:
        """Metadata catalog untuk satu Skill berdasarkan skill_id.

        Validasi skill_id tetap dilakukan (InvalidSkillIdError bila ilegal).

        Args:
            skill_id: identifier Skill.

        Returns:
            ``SkillCatalogEntry`` bila ada, ``None`` bila tidak ditemukan.
            Tidak memuat isi skill.md (content).
        """
        skill = self.get_skill(skill_id)
        if skill is None:
            return None
        return _to_catalog_entry(skill)

    # ``skill_exists`` sudah memenuhi kebutuhan \"mengecek apakah Skill
    # tersedia\" sehingga tidak dibuat duplicate API. Reuse apa yang ada.

    # ------------------------------------------------------------------ #
    # Read — get single Skill
    # ------------------------------------------------------------------ #
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Ambil Skill berdasarkan id; None bila tidak ada.

        Validasi skill_id tetap dilakukan (InvalidSkillIdError bila ilegal).
        """
        sid = validate_skill_id(skill_id)
        for d in self.candidate_skills_dirs:
            target = d / sid
            file_path = _find_skill_file(target)
            if file_path is not None:
                return _skill_from_file(sid, file_path)
        return None

    def skill_exists(self, skill_id: str) -> bool:
        """True bila Skill dengan id tersebut ada."""
        sid = validate_skill_id(skill_id)
        for d in self.candidate_skills_dirs:
            target = d / sid
            if _find_skill_file(target) is not None:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Progressive Loading (Task 03) — generic, dynamic, on-demand
    # ------------------------------------------------------------------ #
    def load_skill(self, skill_id: str) -> Skill:
        """Load ``skill.md`` untuk ``skill_id`` yang diminta (progressive).

        Generic & dynamic: ``skill_id`` adalah identifier directory Skill
        (tidak hardcode). Hanya membaca ``skill.md`` milik Skill tersebut —
        tidak memuat isi ``references/`` atau Skill lain.

        Args:
            skill_id: identifier Skill (dynamic, validasi strict).

        Returns:
            ``Skill`` berisi content (body markdown) + metadata (skill_id,
            name, description, scope, location, timestamps).

        Raises:
            InvalidSkillIdError: bila skill_id ilegal.
            SkillNotFoundError: bila Skill tidak ditemukan — error jelas
                dengan pesan ``Skill '<id>' tidak ditemukan.``
        """
        sid = validate_skill_id(skill_id)
        skill = self.get_skill(sid)
        if skill is None:
            raise SkillNotFoundError(f"Skill '{sid}' tidak ditemukan.")
        return skill

    def list_references(self, skill_id: str) -> List[str]:
        """Daftar reference yang tersedia untuk sebuah Skill (tanpa memuat isi).

        Hanya mengembalikan nama/path relatif file di ``references/``
        (terurut alfabetis, deterministik). Tidak membaca isi file — pemanggil
        dapat memilih reference spesifik lalu memuatnya via
        ``load_skill_reference``.

        Args:
            skill_id: identifier Skill.

        Returns:
            Daftar path relatif (posix) terhadap ``references/``. List kosong
            bila tidak ada references/ atau belum ada file.

        Raises:
            InvalidSkillIdError: bila skill_id ilegal.
            SkillNotFoundError: bila Skill tidak ditemukan.
        """
        sid = validate_skill_id(skill_id)
        if not self.skill_exists(sid):
            raise SkillNotFoundError(f"Skill '{sid}' tidak ditemukan.")
        refs_dir = self.references_dir(sid)
        if not refs_dir.exists() or not refs_dir.is_dir():
            return []
        try:
            files: List[str] = []
            for path in refs_dir.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(refs_dir).as_posix()
                    files.append(rel)
            files.sort()
            return files
        except OSError:
            return []

    def reference_exists(self, skill_id: str, reference: str) -> bool:
        """True bila reference spesifik ada untuk Skill tersebut.

        Tidak memuat isi, hanya cek keberadaan file. Reference dipilih
        berdasarkan nama/path yang diberikan (generic, tanpa heuristic).
        """
        sid = validate_skill_id(skill_id)
        ref_name = _validate_reference_name(reference)
        refs_dir = self.references_dir(sid)
        target = refs_dir / ref_name
        # Pastikan target tetap di dalam refs_dir (anti traversal)
        try:
            target_resolved = target.resolve()
            refs_resolved = refs_dir.resolve()
            target_resolved.relative_to(refs_resolved)
        except ValueError:
            return False
        except OSError:
            return False
        return target.is_file()

    def load_skill_reference(self, skill_id: str, reference: str) -> str:
        """Load satu reference spesifik untuk Skill (progressive, on-demand).

        Generic: ``reference`` adalah nama/path relatif terhadap
        ``references/`` yang diberikan pemanggil (LLM). Tidak ada heuristic
        khusus bahasa/framework; pemilihan mutlak berdasarkan ``reference``
        yang diminta. Tidak otomatis membaca seluruh isi ``references/`` —
        hanya file yang diminta.

        Args:
            skill_id: identifier Skill (dynamic).
            reference: nama/path relatif file di ``references/``
                (mis. ``api.md`` atau ``guides/vue.md``). Tidak boleh
                mengandung ``..`` atau absolute path.

        Returns:
            Isi teks file reference (utf-8).

        Raises:
            InvalidSkillIdError: bila skill_id ilegal.
            SkillError: bila reference ilegal (kosong, traversal, absolute).
            SkillNotFoundError: bila Skill tidak ditemukan.
            SkillReferenceNotFoundError: bila reference tidak ditemukan —
                error jelas ``Reference '<ref>' tidak ditemukan untuk skill '<id>'.``
        """
        sid = validate_skill_id(skill_id)
        ref_name = _validate_reference_name(reference)
        # Pastikan skill ada dulu — error skill lebih prioritas daripada reference
        if not self.skill_exists(sid):
            raise SkillNotFoundError(f"Skill '{sid}' tidak ditemukan.")
        refs_dir = self.references_dir(sid)
        target = refs_dir / ref_name
        # Anti path-traversal: resolved target harus di dalam refs_dir
        try:
            # Jika refs_dir belum ada, resolve akan tetap cek — tapi is_file akan False
            target_resolved = target.resolve()
            refs_resolved = refs_dir.resolve()
            # relative_to raises ValueError bila di luar
            target_resolved.relative_to(refs_resolved)
        except ValueError:
            raise SkillError(f"reference '{ref_name}' di luar directory references.")
        except OSError as exc:
            raise SkillError(f"Gagal memvalidasi reference '{ref_name}': {exc}") from exc

        if not target.is_file():
            raise SkillReferenceNotFoundError(
                f"Reference '{ref_name}' tidak ditemukan untuk skill '{sid}'."
            )
        try:
            return target.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillError(f"Gagal membaca reference '{ref_name}': {exc}") from exc

    # Alias generic untuk kenyamanan — tetap on-demand, bukan auto-load
    def load_reference(self, skill_id: str, reference: str) -> str:
        """Alias ``load_skill_reference``."""
        return self.load_skill_reference(skill_id, reference)

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def create_skill(
        self,
        skill_id: str,
        name: str,
        description: str = "",
        content: str = "",
        scope: str = SKILL_SCOPE_PROJECT,
    ) -> Skill:
        """Buat Skill baru.

        Args:
            skill_id: identifier directory Skill (unik per project).
            name: nama tampilan Skill.
            description: deskripsi singkat.
            content: isi markdown Skill (body di luar frontmatter).
            scope: cakupan Skill (saat ini hanya 'project').

        Raises:
            InvalidSkillIdError: bila skill_id ilegal.
            SkillAlreadyExistsError: bila Skill sudah ada.
            SkillError: bila name kosong atau scope tidak dikenal.
        """
        sid = validate_skill_id(skill_id)
        if not isinstance(name, str) or not name.strip():
            raise SkillError("Field 'name' tidak boleh kosong.")
        scope = canonical_skill_scope(scope)
        if self.skill_exists(sid):
            raise SkillAlreadyExistsError(f"Skill '{sid}' sudah ada.")

        self.ensure()
        now = _now_iso()
        skill = Skill(
            skill_id=sid,
            name=name.strip(),
            description=description.strip() if isinstance(description, str) else str(description),
            scope=scope,
            content=content if isinstance(content, str) else str(content),
            location=str((self.primary_skills_dir / sid / "SKILL.md").resolve()),
            created_at=now,
            updated_at=now,
        )
        # Buat directory + references/
        target_dir = self.primary_skills_dir / sid
        refs_dir = target_dir / SKILL_REFERENCES_DIR_NAME
        try:
            refs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SkillError(f"Gagal membuat directory Skill '{sid}': {exc}") from exc

        target_file = target_dir / "SKILL.md"
        text = _serialize_frontmatter(skill)
        _atomic_write(target_file, text)
        # Update location ke path absolut yang sebenarnya (setelah write)
        skill.location = str(target_file.resolve())
        return skill

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update_skill(
        self,
        skill_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> Skill:
        """Update Skill yang sudah ada (partial update).

        Hanya field yang diberikan (tidak None) yang diubah. Field lain
        dipertahankan. ``updated_at`` selalu diperbarui.

        Raises:
            SkillNotFoundError: bila Skill tidak ada.
            InvalidSkillIdError: bila skill_id ilegal.
            SkillError: bila validasi field gagal.
        """
        sid = validate_skill_id(skill_id)
        existing = self.get_skill(sid)
        if existing is None:
            raise SkillNotFoundError(f"Skill '{sid}' tidak ditemukan.")

        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise SkillError("Field 'name' tidak boleh kosong.")
            existing.name = name.strip()
        if description is not None:
            existing.description = description.strip() if isinstance(description, str) else str(description)
        if content is not None:
            existing.content = content if isinstance(content, str) else str(content)
        if scope is not None:
            existing.scope = canonical_skill_scope(scope)
        existing.updated_at = _now_iso()
        # location selalu derived dari path aktual
        existing.location = str(self.skill_path(sid).resolve())

        text = _serialize_frontmatter(existing)
        _atomic_write(self.skill_path(sid), text)
        return existing

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete_skill(self, skill_id: str) -> None:
        """Hapus Skill beserta directory-nya (termasuk references/).

        Raises:
            SkillNotFoundError: bila Skill tidak ada.
            InvalidSkillIdError: bila skill_id ilegal.
        """
        sid = validate_skill_id(skill_id)
        if not self.skill_exists(sid):
            raise SkillNotFoundError(f"Skill '{sid}' tidak ditemukan.")
        skill_dir = self.skill_dir(sid)
        try:
            shutil.rmtree(skill_dir)
        except OSError as exc:
            raise SkillError(f"Gagal menghapus Skill '{sid}': {exc}") from exc

    # ------------------------------------------------------------------ #
    # Convenience — read content directly (reuse pola BibleStore.read_category)
    # ------------------------------------------------------------------ #
    def read_skill_content(self, skill_id: str) -> Optional[str]:
        """Baca body markdown Skill (tanpa frontmatter); None bila tidak ada."""
        skill = self.get_skill(skill_id)
        if skill is None:
            return None
        return skill.content


# ---------------------------------------------------------------------------
# Catalog helpers — konversi Skill -> metadata ringan (tanpa content)
# ---------------------------------------------------------------------------
def _to_catalog_entry(skill: Skill) -> SkillCatalogEntry:
    """Proyeksikan Skill menjadi metadata katalog (tanpa content/references)."""
    return SkillCatalogEntry(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        scope=skill.scope,
        location=skill.location,
    )


# ---------------------------------------------------------------------------
# Module-level generic helpers (Task 03 contract)
# ---------------------------------------------------------------------------
def load_skill(root: Union[str, Path, AegisProjectStore], skill_id: str) -> Skill:
    """Helper generic progressive loading di level module.

    Wrapper di atas ``SkillStore(root).load_skill(skill_id)`` agar LLM/tool
    dapat memanggil ``load_skill(skill_id)`` tanpa menginstansiasi Store
    manual. ``skill_id`` tetap dynamic.

    Args:
        root: root project atau AegisProjectStore.
        skill_id: identifier Skill.

    Returns:
        Skill (content + metadata).

    Raises:
        InvalidSkillIdError / SkillNotFoundError sesuai SkillStore.load_skill.
    """
    return SkillStore(root).load_skill(skill_id)


def load_skill_reference(
    root: Union[str, Path, AegisProjectStore], skill_id: str, reference: str
) -> str:
    """Helper generic untuk memuat satu reference spesifik.

    Wrapper di atas ``SkillStore(root).load_skill_reference(...)``.
    Generic, tidak heuristic, hanya memuat reference yang diminta.

    Args:
        root: root project atau AegisProjectStore.
        skill_id: identifier Skill.
        reference: nama/path relatif di references/.

    Returns:
        Isi teks reference.

    Raises:
        SkillError / SkillNotFoundError / SkillReferenceNotFoundError sesuai
        SkillStore.load_skill_reference.
    """
    return SkillStore(root).load_skill_reference(skill_id, reference)


def load_reference(
    root: Union[str, Path, AegisProjectStore], skill_id: str, reference: str
) -> str:
    """Alias module-level untuk ``load_skill_reference``."""
    return load_skill_reference(root, skill_id, reference)
