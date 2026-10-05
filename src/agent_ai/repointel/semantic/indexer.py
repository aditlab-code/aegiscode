"""Pengindeks semantik inkremental berbasis hash SHA-256 dan deteksi bahasa."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agent_ai.codeindex.indexer import CodeIndexer
from agent_ai.codeindex.languages import LanguageRegistry
from agent_ai.config.settings import EMBED_MODEL
from agent_ai.repointel.semantic.chunker import chunk_file
from agent_ai.repointel.semantic.store import (
    FingerprintTable,
    IndexMetaTable,
)

SCHEMA_VERSION = "2.1"
SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
}


@dataclass(frozen=True)
class IndexStats:
    """Statistik hasil eksekusi pengindeksan semantik.

    Attributes:
        scanned: Jumlah berkas kode yang dipindai di workspace.
        indexed: Jumlah berkas baru atau yang mengalami perubahan dan diindeks ulang.
        skipped: Jumlah berkas yang dilewati karena hash SHA-256 identik.
        removed: Jumlah berkas yang dihapus dari indeks karena berkas aslinya telah hilang.
        total_chunks: Total potongan kode yang saat ini tersimpan di vector store.
        backend: Nama mesin penyimpanan ('sqlite-vec' atau 'bruteforce').
        elapsed_sec: Waktu total pemrosesan dalam detik.
    """

    scanned: int
    indexed: int
    skipped: int
    removed: int
    total_chunks: int
    backend: str
    elapsed_sec: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanned": self.scanned,
            "indexed": self.indexed,
            "skipped": self.skipped,
            "removed": self.removed,
            "total_chunks": self.total_chunks,
            "backend": self.backend,
            "elapsed_sec": round(self.elapsed_sec, 3),
        }


class SemanticIndexer:
    """Orkestrator pengindeksan kode semantik deterministik dan inkremental."""

    def __init__(
        self,
        root: Path,
        vector_store: Any,
        conn: Any,
        backend: str,
        model_name: Optional[str] = None,
        languages: Optional[LanguageRegistry] = None,
        ignored_dirs: Optional[Set[str]] = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.store = vector_store
        self.conn = conn
        self.backend = backend
        self.model_name = model_name or EMBED_MODEL
        self.languages = languages or LanguageRegistry.default()
        self.ignored_dirs = ignored_dirs

        self.meta = IndexMetaTable(self.conn)
        self.fingerprints = FingerprintTable(self.conn)

    def _should_full_rebuild(self) -> bool:
        """Evaluasi apakah basis data vektor harus dibersihkan total dan dibangun ulang."""
        saved_schema = self.meta.get("schema_version")
        saved_model = self.meta.get("model_name")
        if saved_schema != SCHEMA_VERSION:
            return True
        if saved_model != self.model_name:
            return True
        return False

    def is_stale(self) -> bool:
        """Pemeriksaan cepat apakah repositori memiliki berkas yang belum diindeks atau berubah."""
        if self._should_full_rebuild():
            return True

        scanned_files = self._collect_supported_files()
        known_fps = self.fingerprints.all()

        scanned_rel_set = set(scanned_files.keys())
        known_rel_set = set(known_fps.keys())

        # Ada berkas yang baru ditambah atau dihapus
        if scanned_rel_set != known_rel_set:
            return True

        # Periksa st_mtime dan hash berkas yang mungkin berubah
        for rel, abs_path in scanned_files.items():
            fp = known_fps.get(rel)
            if not fp:
                return True
            try:
                stat = abs_path.stat()
                # Bila mtime lebih baru dari waktu indexed_at, lakukan verifikasi hash
                if stat.st_mtime > fp["indexed_at"]:
                    data = abs_path.read_bytes()
                    current_hash = hashlib.sha256(data).hexdigest()
                    if current_hash != fp["sha256"]:
                        return True
            except OSError:
                return True

        return False

    def _collect_supported_files(self) -> Dict[str, Path]:
        """Kumpulkan seluruh berkas sumber yang didukung bahasa semantik."""
        indexer = CodeIndexer(
            root=self.root,
            languages=self.languages,
            ignored_dirs=self.ignored_dirs,
        )
        supported_files: Dict[str, Path] = {}
        for path in indexer._iter_source_files():
            rel = path.relative_to(self.root).as_posix()
            lang = self.languages.detect(rel)
            if lang and lang.name in SUPPORTED_LANGUAGES:
                supported_files[rel] = path
        return supported_files

    def run(self, full: bool = False) -> IndexStats:
        """Jalankan proses pengindeksan semantik (inkremental atau penuh)."""
        start_time = time.time()
        need_rebuild = full or self._should_full_rebuild()

        if need_rebuild:
            if hasattr(self.store, "clear"):
                self.store.clear()
            self.fingerprints.clear()
            self.meta.set("schema_version", SCHEMA_VERSION)
            self.meta.set("model_name", self.model_name)
            self.meta.set("backend", self.backend)

        scanned_files = self._collect_supported_files()
        existing_fps = self.fingerprints.all()

        indexed_count = 0
        skipped_count = 0
        removed_count = 0

        # 1. Hapus berkas yang sudah tidak ada di filesystem
        for rel_path in list(existing_fps.keys()):
            if rel_path not in scanned_files:
                self.store.delete_by_path(rel_path)
                self.fingerprints.delete(rel_path)
                removed_count += 1

        # 2. Proses berkas yang dipindai
        for rel_path, abs_path in scanned_files.items():
            try:
                data = abs_path.read_bytes()
                sha256 = hashlib.sha256(data).hexdigest()
            except OSError:
                continue

            fp = existing_fps.get(rel_path)
            if fp and fp["sha256"] == sha256 and not need_rebuild:
                skipped_count += 1
                continue

            # Berkas baru atau berubah: hapus potongan lama terlebih dahulu
            self.store.delete_by_path(rel_path)

            try:
                source_text = data.decode("utf-8", errors="replace")
            except Exception:
                continue

            lang = self.languages.detect(rel_path)
            lang_name = lang.name if lang else "generic"

            chunks = chunk_file(rel_path, lang_name, source_text)
            if chunks:
                texts = [c.contextual_text() for c in chunks]
                metadatas = [
                    {
                        "path": c.path,
                        "language": c.language,
                        "symbol": c.symbol,
                        "kind": c.kind,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "sha256": sha256,
                    }
                    for c in chunks
                ]
                self.store.add_texts(texts, metadatas=metadatas)

            self.fingerprints.upsert(rel_path, sha256, len(chunks))
            indexed_count += 1

        total_chunks = self.store.count() if hasattr(self.store, "count") else 0
        elapsed = time.time() - start_time

        return IndexStats(
            scanned=len(scanned_files),
            indexed=indexed_count,
            skipped=skipped_count,
            removed=removed_count,
            total_chunks=total_chunks,
            backend=self.backend,
            elapsed_sec=elapsed,
        )


__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_LANGUAGES",
    "IndexStats",
    "SemanticIndexer",
]
