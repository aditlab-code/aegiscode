"""Service terpadu untuk pencarian semantik dan manajemen lifecycle indeks vektor."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.config.settings import EMBED_MODEL
from agent_ai.repointel.semantic.embeddings import build_embeddings
from agent_ai.repointel.semantic.indexer import IndexStats, SemanticIndexer
from agent_ai.repointel.semantic.paths import resolve_vectors_db
from agent_ai.repointel.semantic.store import (
    IndexMetaTable,
    build_vector_store,
    open_connection,
)

PathLike = Union[str, os.PathLike[str]]

# Kunci sinkronisasi thread per direktori workspace root
_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def _get_root_lock(root_str: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        if root_str not in _LOCKS:
            _LOCKS[root_str] = threading.Lock()
        return _LOCKS[root_str]


class SemanticIndexService:
    """Facade utama layanan pencarian semantik kode dan pengindeksan repositori.

    Mendukung dua mode:
    - Mode Agent (`read_only=False`): Dapat memicu re-indexing otomatis saat status stale.
    - Mode Consultant (`read_only=True`): Hanya membaca basis data vektor tanpa mutasi filesystem.
    """

    def __init__(
        self,
        root: PathLike,
        embeddings: Optional[Any] = None,
        read_only: bool = False,
    ) -> None:
        self.root = Path(root).resolve()
        self.read_only = read_only
        self._lock = _get_root_lock(str(self.root))

        self.db_path = resolve_vectors_db(self.root)
        self.conn, self.backend = open_connection(self.db_path)

        if embeddings is not None:
            self.embeddings = embeddings
        else:
            try:
                self.embeddings = build_embeddings()
            except Exception:
                self.embeddings = None

        self.store = (
            build_vector_store(
                conn=self.conn,
                backend=self.backend,
                embedding=self.embeddings,
            )
            if self.embeddings is not None
            else None
        )

        self.indexer = (
            SemanticIndexer(
                root=self.root,
                vector_store=self.store,
                conn=self.conn,
                backend=self.backend,
                model_name=EMBED_MODEL,
            )
            if self.store is not None
            else None
        )

    def status(self) -> Dict[str, Any]:
        """Ambil status kelengkapan dan kesegaran indeks semantik saat ini."""
        with self._lock:
            exists = self.db_path.exists()
            total_chunks = self.store.count() if (self.store and hasattr(self.store, "count")) else 0
            fps_count = (
                len(self.indexer.fingerprints.all())
                if (self.indexer and self.indexer.fingerprints)
                else 0
            )
            is_stale = self.indexer.is_stale() if self.indexer else True
            meta = IndexMetaTable(self.conn).all()

            return {
                "db_path": str(self.db_path),
                "exists": exists,
                "is_stale": is_stale,
                "backend": self.backend,
                "model_name": meta.get("model_name", EMBED_MODEL),
                "total_chunks": total_chunks,
                "files_indexed": fps_count,
                "read_only": self.read_only,
            }

    def refresh(self, full: bool = False) -> IndexStats:
        """Segarkan indeks kode semantik secara inkremental atau menyeluruh."""
        if self.read_only:
            raise PermissionError(
                "SemanticIndexService beroperasi dalam mode read-only; operasi refresh ditolak."
            )

        if not self.indexer:
            raise RuntimeError(
                "Layanan embedding tidak aktif atau paket dependensi belum terpasang."
            )

        with self._lock:
            return self.indexer.run(full=full)

    def search(
        self,
        query: str,
        k: int = 8,
        path_prefix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lakukan pencarian kode berbasis kemiripan semantik."""
        if not self.store:
            raise RuntimeError(
                "Vector store belum diinisialisasi atau model embedding belum tersedia."
            )

        with self._lock:
            # Pada mode Agent, jika indeks basi atau belum ada data, lakukan refresh inkremental
            if not self.read_only and self.indexer:
                if self.indexer.is_stale():
                    self.indexer.run(full=False)

            raw_results = self.store.similarity_search_with_score(
                query=query,
                k=k,
                path_prefix=path_prefix,
            )

        formatted: List[Dict[str, Any]] = []
        for meta, score in raw_results:
            text = meta.get("text", "")
            # Batasi panjang snippet maksimal 40 baris agar hemat token
            snippet_lines = text.splitlines()[:40]
            snippet = "\n".join(snippet_lines)

            formatted.append(
                {
                    "path": meta.get("path"),
                    "symbol": meta.get("symbol"),
                    "kind": meta.get("kind"),
                    "start_line": meta.get("start_line"),
                    "end_line": meta.get("end_line"),
                    "score": round(float(score), 4),
                    "snippet": snippet,
                }
            )

        return formatted

    def close(self) -> None:
        """Tutup koneksi basis data SQLite dan lepas file lock."""
        with self._lock:
            if self.conn is not None:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None

    def __enter__(self) -> "SemanticIndexService":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


__all__ = ["SemanticIndexService"]

