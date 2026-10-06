"""External Brain Resolver untuk integrasi Antigravity Brain pengguna.

Menyediakan facade akses READ-ONLY terisolasi ke direktori brain Antigravity global
(default: `~/.gemini/antigravity-cli/brain/`), dengan guardrail keamanan:
- Strict Read-Only: tidak ada operasi tulis atau modifikasi ke direktori pengguna.
- Anti Path Traversal: memverifikasi bahwa jalur tetap berada di dalam direktori brain yang diizinkan.
- Sensitive File Blacklist: memblokir pembacaan berkas kredensial, token, atau secret.
- Bounded Context: membatasi muatan teks agar tidak membebani anggaran token LLM.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pola nama berkas yang dilarang keras dibaca
SENSITIVE_PATTERNS = (
    ".env",
    "oauth",
    "token",
    "secret",
    "key",
    "credential",
    "password",
    ".git",
    ".ssh",
)

# Ekstensi berkas memori yang diizinkan
ALLOWED_EXTENSIONS = (".md", ".json", ".txt")

# Batas maksimum karakter per berkas dan total muatan ringkasan
MAX_CHARS_PER_FILE = 4000
MAX_TOTAL_CHARS = 12000


class ExternalBrainSecurityError(Exception):
    """Dilempar ketika terdeteksi pelanggaran batas keamanan atau berkas sensitif."""


class ExternalBrainResolver:
    """Resolver aman untuk membaca memori global Antigravity di root pengguna."""

    def __init__(self, brain_root: Optional[Path | str] = None) -> None:
        if brain_root is not None:
            self._root = Path(brain_root).expanduser().resolve()
        else:
            default_path = Path("~/.gemini/antigravity-cli/brain").expanduser().resolve()
            self._root = default_path

    @property
    def root(self) -> Path:
        return self._root

    def is_available(self) -> bool:
        """Periksa apakah direktori brain Antigravity ada dan dapat diakses."""
        try:
            return self._root.exists() and self._root.is_dir() and os.access(self._root, os.R_OK)
        except OSError:
            return False

    def _validate_path(self, target: Path) -> Path:
        """Validasi bahwa target berada di dalam root brain dan bukan berkas sensitif."""
        resolved = target.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise ExternalBrainSecurityError(
                f"Path traversal terdeteksi: '{resolved}' berada di luar root brain '{self._root}'"
            ) from exc

        name_lower = resolved.name.lower()
        for pattern in SENSITIVE_PATTERNS:
            if pattern in name_lower:
                raise ExternalBrainSecurityError(
                    f"Akses ditolak: berkas '{resolved.name}' cocok dengan pola sensitif '{pattern}'"
                )

        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ExternalBrainSecurityError(
                f"Akses ditolak: ekstensi '{resolved.suffix}' tidak diizinkan"
            )

        return resolved

    def list_memory_files(self, max_files: int = 10) -> List[Path]:
        """Daftar berkas memori yang valid, diurutkan menurut modifikasi terbaru."""
        if not self.is_available():
            return []

        candidates: List[Path] = []
        try:
            for item in self._root.rglob("*"):
                if not item.is_file():
                    continue
                try:
                    valid_path = self._validate_path(item)
                    candidates.append(valid_path)
                except ExternalBrainSecurityError:
                    continue
        except OSError as exc:
            logger.warning("Gagal memindai direktori brain eksternal '%s': %s", self._root, exc)
            return []

        # Urutkan menurut waktu modifikasi terbaru
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[:max_files]

    def read_file_content(self, target_path: Path) -> Optional[str]:
        """Baca isi berkas memori secara aman dengan pembatasan ukuran."""
        valid_path = self._validate_path(target_path)
        try:
            content = valid_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_CHARS_PER_FILE:
                return content[:MAX_CHARS_PER_FILE] + "\n... [konten dipotong untuk efisiensi token]"
            return content
        except OSError as exc:
            logger.warning("Gagal membaca memori brain '%s': %s", target_path, exc)
            return None

    def get_summary_context(self) -> str:
        """Kompilasi ringkasan memori eksternal yang siap diinjeksikan ke context LLM."""
        if not self.is_available():
            return ""

        files = self.list_memory_files(max_files=5)
        if not files:
            return ""

        parts: List[str] = [
            "### [GLOBAL ANTIGRAVITY BRAIN MEMORY]",
            "Konteks memori global yang diakses aman dari direktori Antigravity pengguna:",
        ]

        total_len = sum(len(p) for p in parts)
        for f in files:
            try:
                content = self.read_file_content(f)
            except ExternalBrainSecurityError:
                continue
            if not content:
                continue

            entry_header = f"\n#### Sumber: {f.name}\n"
            if total_len + len(entry_header) + len(content) > MAX_TOTAL_CHARS:
                break

            parts.append(entry_header)
            parts.append(content)
            total_len += len(entry_header) + len(content)

        return "\n".join(parts) if len(parts) > 2 else ""
