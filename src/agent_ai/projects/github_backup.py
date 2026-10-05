"""Project-local GitHub Backup metadata: `<root>/.aegis/github/`.

Menyimpan metadata PRIVATE AegisCode untuk fitur GitHub Backup per project:

    <root project target>/
        .aegis/
            bible/            # AI Project Bible (dikelola aegis_store.py)
            log/              # Task log (dikelola aegis_store.py)
            github/           # GitHub Backup metadata (dikelola modul ini)
                config.json   # NON-SECRET: enabled/repository/branch/exclude
                credential.enc# token terenkripsi (opaque bytes, bukan plaintext)

Prinsip:
    - Project-local: semua ditulis di dalam root project target, tidak di
      workspace AegisCode. Konfigurasi project A TIDAK boleh tercampur project B.
    - Token TIDAK pernah ditulis plaintext ke `config.json`. Nilai token hanya
      melewati modul ini sebagai bytes yang SUDAH terenkripsi (proteksi
      credential dilakukan di layer gateway, lihat api/github_backup.py).
    - Additive: modul ini HANYA menambah subfolder `.aegis/github/`; ia tidak
      mengubah penulisan Bible/log yang sudah ada.
    - Idempotent + atomic write: tidak ada file parsial.
    - Tidak ada dependency baru; tanpa DB/vektor/embeddings.

Modul ini juga menyediakan `ensure_aegis_ignored()`: memastikan `.gitignore`
project SELALU memuat `.aegis/` tanpa menimpa isi existing.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

#: Nama folder root metadata project.
AEGIS_DIR_NAME = ".aegis"
#: Subfolder metadata GitHub Backup.
GITHUB_DIR_NAME = "github"
#: Nama file konfigurasi non-secret.
CONFIG_FILE_NAME = "config.json"
#: Nama file credential terenkripsi (opaque bytes).
CREDENTIAL_FILE_NAME = "credential.enc"

#: Rule mandatory yang WAJIB ada di `.gitignore` project.
MANDATORY_IGNORE_RULE = ".aegis/"
#: Baris-baris yang dianggap sudah mewakili `.aegis/` (agar tidak dobel tulis).
_AEGIS_IGNORE_EQUIVALENTS = {".aegis/", ".aegis", "/.aegis/", "/.aegis"}


def _normalize_exclude(exclude: Optional[Union[List[str], str]]) -> List[str]:
    """Normalisasi daftar exclude menjadi list of str (deterministik)."""
    if exclude is None:
        return []
    if isinstance(exclude, str):
        items = exclude.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    elif isinstance(exclude, (list, tuple)):
        items = [str(x) for x in exclude]
    else:
        return []
    result: List[str] = []
    for raw in items:
        text = str(raw).strip()
        if not text or text.startswith("#"):
            continue
        result.append(text)
    return result


@dataclass
class GithubBackupConfig:
    """Konfigurasi GitHub Backup sebuah project (NON-SECRET).

    Attributes:
        enabled: apakah backup diaktifkan user.
        repository: URL repository Git (mis. https://github.com/u/r.git).
        branch: branch tujuan push.
        exclude: pola file/folder yang TIDAK ikut backup (opsional).
    """

    enabled: bool = True
    repository: str = ""
    branch: str = "main"
    exclude: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "repository": self.repository or "",
            "branch": self.branch or "",
            "exclude": list(self.exclude),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GithubBackupConfig":
        if not isinstance(data, dict):
            data = {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            repository=str(data.get("repository", "") or ""),
            branch=str(data.get("branch", "main") or "main"),
            exclude=_normalize_exclude(data.get("exclude")),
        )


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Tulis bytes secara atomik (temp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".aegis_tmp_", suffix=".swp"
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class GithubBackupStore:
    """Store project-local `<root>/.aegis/github/`.

    Args:
        root: root project target.
    """

    def __init__(self, root: Union[str, Path]) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    @property
    def github_dir(self) -> Path:
        return self.root / AEGIS_DIR_NAME / GITHUB_DIR_NAME

    @property
    def config_path(self) -> Path:
        return self.github_dir / CONFIG_FILE_NAME

    @property
    def credential_path(self) -> Path:
        return self.github_dir / CREDENTIAL_FILE_NAME

    # ------------------------------------------------------------------ #
    # Config (non-secret)
    # ------------------------------------------------------------------ #
    def load_config(self) -> Optional[GithubBackupConfig]:
        """Muat konfigurasi (None bila belum ada / tidak valid)."""
        path = self.config_path
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(raw, dict):
            return None
        return GithubBackupConfig.from_dict(raw)

    def save_config(self, config: GithubBackupConfig) -> GithubBackupConfig:
        """Simpan konfigurasi non-secret (token TIDAK pernah masuk sini)."""
        data = json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n"
        _atomic_write_bytes(self.config_path, data.encode("utf-8"))
        return config

    # ------------------------------------------------------------------ #
    # Credential (opaque, SUDAH terenkripsi)
    # ------------------------------------------------------------------ #
    def has_credential(self) -> bool:
        return self.credential_path.is_file()

    def save_credential(self, encrypted: bytes) -> None:
        """Simpan bytes credential yang SUDAH terenkripsi."""
        if not isinstance(encrypted, (bytes, bytearray)) or not encrypted:
            raise ValueError("Credential terenkripsi tidak boleh kosong.")
        _atomic_write_bytes(self.credential_path, bytes(encrypted))

    def load_credential(self) -> Optional[bytes]:
        """Muat bytes credential terenkripsi (None bila belum ada)."""
        path = self.credential_path
        if not path.is_file():
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def delete_credential(self) -> bool:
        """Hapus file credential. Returns True bila ada yang dihapus."""
        path = self.credential_path
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError:
            return False
        return True

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def is_configured(self) -> bool:
        """True bila repository + branch + credential tersedia."""
        config = self.load_config()
        if config is None:
            return False
        return bool(config.repository and config.branch) and self.has_credential()

    def status(self) -> Dict[str, Any]:
        """Ringkasan status (TANPA token)."""
        config = self.load_config()
        credential_set = self.has_credential()
        if config is None:
            return {
                "configured": False,
                "enabled": False,
                "repository": "",
                "branch": "",
                "exclude": [],
                "credential_set": credential_set,
            }
        return {
            "configured": bool(config.repository and config.branch) and credential_set,
            "enabled": bool(config.enabled),
            "repository": config.repository,
            "branch": config.branch,
            "exclude": list(config.exclude),
            "credential_set": credential_set,
        }


def ensure_git_exclude_ignored(root: Union[str, Path]) -> bool:
    """Pastikan `.git/info/exclude` project memuat metadata internal Aegis/Aether.

    Ini sangat penting terutama ketika folder proyek berada di luar folder root,
    sehingga Git secara lokal mengabaikan metadata internal tanpa memodifikasi
    atau mengotori `.gitignore` publik repositori.
    """
    root_path = Path(root)
    git_dir = root_path / ".git"
    if not git_dir.exists():
        return False
    if git_dir.is_file():
        try:
            content = git_dir.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                git_dir = (root_path / content[7:].strip()).resolve()
        except Exception:
            return False
    exclude_file = git_dir / "info" / "exclude"
    try:
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
        rules = [
            ".aegis/",
            ".aether/",
            ".aegis_tmp_*",
            ".aether_tmp_*",
            "*.swp",
            "data/aegis.db",
            "data/aether.db",
        ]
        to_add = [r for r in rules if r not in existing]
        if not to_add:
            return False
        addition = ("\n" if existing and not existing.endswith("\n") else "")
        addition += "# AegisCode local repository metadata ignore\n"
        addition += "\n".join(to_add) + "\n"
        with open(exclude_file, "a", encoding="utf-8") as f:
            f.write(addition)
        return True
    except Exception:
        return False


def ensure_aegis_ignored(root: Union[str, Path]) -> bool:
    """Pastikan `.gitignore` dan `.git/info/exclude` project memuat rule mandatory `.aegis/`.

    Perilaku:
        - Selalu memastikan `.git/info/exclude` di repo Git terisi agar tidak bocor.
        - Bila `.gitignore` belum ada -> dibuat dengan perubahan minimal.
        - Bila sudah ada -> isi existing TIDAK di-overwrite; rule `.aegis/`
          ditambahkan HANYA bila belum ada.
        - Rule ini tidak bisa dihapus lewat UI exclude (exclude tidak pernah
          ditulis ke `.gitignore` oleh AegisCode).

    Returns:
        True bila file `.gitignore` diubah, False bila rule sudah ada.
    """
    ensure_git_exclude_ignored(root)
    root_path = Path(root)
    gitignore = root_path / ".gitignore"

    if not gitignore.exists():
        content = (
            "# AegisCode private metadata (mandatory; jangan dihapus)\n"
            f"{MANDATORY_IGNORE_RULE}\n"
        )
        _atomic_write_bytes(gitignore, content.encode("utf-8"))
        return True

    try:
        existing = gitignore.read_text(encoding="utf-8")
    except OSError:
        return False

    for line in existing.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip() in _AEGIS_IGNORE_EQUIVALENTS:
            return False

    # Tambahkan rule tanpa menimpa isi existing.
    addition = "" if existing.endswith("\n") or existing == "" else "\n"
    addition += "\n# AegisCode private metadata (mandatory; jangan dihapus)\n"
    addition += f"{MANDATORY_IGNORE_RULE}\n"
    _atomic_write_bytes(gitignore, (existing + addition).encode("utf-8"))
    return True


def aegis_is_ignored(root: Union[str, Path]) -> bool:
    """True bila `.gitignore` project sudah memuat rule mandatory `.aegis/`."""
    gitignore = Path(root) / ".gitignore"
    if not gitignore.is_file():
        return False
    try:
        existing = gitignore.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in existing.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip() in _AEGIS_IGNORE_EQUIVALENTS:
            return True
    return False

