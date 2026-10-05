"""Penyimpanan vektor lokal berbasis SQLite.

Mendukung mesin ganda (dual-engine):
1. `sqlite-vec` (via sqlean.py atau ekstensi native SQLite) untuk akselerasi ANN/kNN.
2. `BruteForceVectorStore` (fallback komparasi kosinus native) bila modul ekstensi C tidak dapat dimuat.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

PathLike = Union[str, os.PathLike[str]]

TABLE_CHUNKS = "aegis_chunks"
TABLE_FINGERPRINTS = "file_fingerprints"
TABLE_META = "index_meta"


def serialize_float32(vector: List[float]) -> bytes:
    """Serialisasi list float ke bytes float32 IEEE 754."""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_float32(data: bytes) -> List[float]:
    """Deserialisasi bytes float32 IEEE 754 ke list float."""
    count = len(data) // 4
    return list(struct.unpack(f"{count}f", data))


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Hitung kemiripan kosinus antara dua vektor secara deterministik murni."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def open_connection(db_path: PathLike) -> Tuple[Any, str]:
    """Buka koneksi SQLite dengan prioritas sqlite-vec lalu fallback ke bruteforce.

    Returns:
        Tuple (connection, backend_name), di mana backend_name adalah 'sqlite-vec' atau 'bruteforce'.
    """
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Coba gunakan sqlean.py terlebih dahulu (mendukung extension loading di semua OS)
    conn = None
    backend = "bruteforce"

    try:
        import sqlean as sqlean_db
        import sqlite_vec

        c = sqlean_db.connect(str(path))
        c.enable_load_extension(True)
        sqlite_vec.load(c)
        c.enable_load_extension(False)
        conn = c
        backend = "sqlite-vec"
    except Exception:
        pass

    # 2. Bila sqlean gagal, coba sqlite3 stdlib dengan sqlite-vec
    if conn is None:
        try:
            import sqlite_vec

            c = sqlite3.connect(str(path))
            if hasattr(c, "enable_load_extension"):
                c.enable_load_extension(True)
                sqlite_vec.load(c)
                c.enable_load_extension(False)
                conn = c
                backend = "sqlite-vec"
        except Exception:
            pass

    # 3. Fallback murni: sqlite3 standar tanpa ekstensi C
    if conn is None:
        conn = sqlite3.connect(str(path))
        backend = "bruteforce"

    # Optimasi konkurensi dan kecepatan baca/tulis
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn, backend


class IndexMetaTable:
    """Manajer tabel metadata index_meta untuk menyimpan konfigurasi skema dan model."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self.conn:
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE_META} (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute(f"SELECT value FROM {TABLE_META} WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                f"INSERT OR REPLACE INTO {TABLE_META} (key, value) VALUES (?, ?)",
                (key, str(value)),
            )

    def all(self) -> Dict[str, str]:
        cur = self.conn.cursor()
        cur.execute(f"SELECT key, value FROM {TABLE_META}")
        return dict(cur.fetchall())


class FingerprintTable:
    """Manajer tabel cache sidik jari berkas file_fingerprints (SHA-256)."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self.conn:
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE_FINGERPRINTS} (
                    path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    indexed_at REAL NOT NULL
                );
                """
            )

    def get(self, path: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT path, sha256, chunk_count, indexed_at FROM {TABLE_FINGERPRINTS} WHERE path = ?",
            (path,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "path": row[0],
            "sha256": row[1],
            "chunk_count": row[2],
            "indexed_at": row[3],
        }

    def all(self) -> Dict[str, Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT path, sha256, chunk_count, indexed_at FROM {TABLE_FINGERPRINTS}"
        )
        results = {}
        for row in cur.fetchall():
            results[row[0]] = {
                "path": row[0],
                "sha256": row[1],
                "chunk_count": row[2],
                "indexed_at": row[3],
            }
        return results

    def upsert(self, path: str, sha256: str, chunk_count: int) -> None:
        with self.conn:
            self.conn.execute(
                f"""
                INSERT OR REPLACE INTO {TABLE_FINGERPRINTS} (path, sha256, chunk_count, indexed_at)
                VALUES (?, ?, ?, ?)
                """,
                (path, sha256, chunk_count, time.time()),
            )

    def delete(self, path: str) -> None:
        with self.conn:
            self.conn.execute(
                f"DELETE FROM {TABLE_FINGERPRINTS} WHERE path = ?", (path,)
            )

    def clear(self) -> None:
        with self.conn:
            self.conn.execute(f"DELETE FROM {TABLE_FINGERPRINTS}")


class BruteForceVectorStore:
    """Implementasi VectorStore SQLite tanpa dependensi native ekstensi C.

    Menyimpan embedding sebagai BLOB float32 dan menghitung kemiripan kosinus murni.
    Sangat andal untuk repositori hingga puluhan ribu potongan kode.
    """

    def __init__(
        self,
        connection: Any,
        embedding: Any,
        table: str = TABLE_CHUNKS,
    ) -> None:
        self.conn = connection
        self.embedding = embedding
        self.table = table
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self.conn:
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    text_embedding BLOB NOT NULL
                );
                """
            )
            # Indeks JSON path untuk pembersihan inkremental cepat
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table}_path
                ON {self.table}(json_extract(metadata, '$.path'));
                """
            )

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[int]:
        """Sisipkan teks beserta embedding ke dalam basis data."""
        if not texts:
            return []

        if embeddings is None:
            embeddings = self.embedding.embed_documents(texts)

        if metadatas is None:
            metadatas = [{} for _ in texts]

        inserted_ids: List[int] = []
        with self.conn:
            cur = self.conn.cursor()
            for text, meta, emb in zip(texts, metadatas, embeddings):
                blob = serialize_float32(emb)
                meta_json = json.dumps(meta, ensure_ascii=False)
                cur.execute(
                    f"INSERT INTO {self.table} (text, metadata, text_embedding) VALUES (?, ?, ?)",
                    (text, meta_json, blob),
                )
                inserted_ids.append(cur.lastrowid)

        return inserted_ids

    def delete_by_path(self, path: str) -> int:
        """Hapus seluruh potongan kode yang berasal dari path berkas tertentu."""
        with self.conn:
            cur = self.conn.cursor()
            cur.execute(
                f"DELETE FROM {self.table} WHERE json_extract(metadata, '$.path') = ?",
                (path,),
            )
            return cur.rowcount

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 8,
        path_prefix: Optional[str] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Cari potongan teks yang paling mirip dengan query dan kembalikan beserta skornya."""
        query_embedding = self.embedding.embed_query(query)
        cur = self.conn.cursor()

        if path_prefix:
            cur.execute(
                f"""
                SELECT rowid, text, metadata, text_embedding FROM {self.table}
                WHERE json_extract(metadata, '$.path') LIKE ?
                """,
                (f"{path_prefix}%",),
            )
        else:
            cur.execute(f"SELECT rowid, text, metadata, text_embedding FROM {self.table}")

        candidates = []
        for row in cur.fetchall():
            rowid, text, meta_json, blob = row
            try:
                emb = deserialize_float32(blob)
                score = cosine_similarity(query_embedding, emb)
                meta = json.loads(meta_json)
                meta["rowid"] = rowid
                meta["text"] = text
                candidates.append((meta, score))
            except Exception:
                continue

        # Urutkan berdasarkan skor kemiripan tertinggi
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:k]

    def count(self) -> int:
        """Hitung jumlah potongan kode yang tersimpan."""
        cur = self.conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {self.table}")
        row = cur.fetchone()
        return row[0] if row else 0

    def clear(self) -> None:
        """Kosongkan seluruh tabel potongan."""
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.table}")


def get_sqlite_vec_class():
    """Import dinamis SQLiteVec dari langchain_community bila terpasang."""
    from langchain_community.vectorstores import SQLiteVec

    class AegisSQLiteVec(SQLiteVec):
        """Subclass SQLiteVec LangChain dengan kemampuan penghapusan inkremental per-berkas."""

        def delete_by_path(self, path: str) -> int:
            cur = self._connection.cursor()
            # Hapus dari tabel virtual vec0 dan tabel penyimpanan
            cur.execute(
                f"""
                DELETE FROM {self._table}_vec WHERE rowid IN (
                    SELECT rowid FROM {self._table} WHERE json_extract(metadata, '$.path') = ?
                )
                """,
                (path,),
            )
            cur.execute(
                f"DELETE FROM {self._table} WHERE json_extract(metadata, '$.path') = ?",
                (path,),
            )
            self._connection.commit()
            return cur.rowcount

        def count(self) -> int:
            cur = self._connection.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            row = cur.fetchone()
            return row[0] if row else 0

    return AegisSQLiteVec


def build_vector_store(
    conn: Any,
    backend: str,
    embedding: Any,
    table: str = TABLE_CHUNKS,
) -> Any:
    """Pabrik pembuatan vector store sesuai ketersediaan backend ekstensi."""
    if backend == "sqlite-vec":
        try:
            vec_cls = get_sqlite_vec_class()
            return vec_cls(
                table=table,
                connection=conn,
                embedding=embedding,
            )
        except Exception:
            # Fallback otomatis ke bruteforce bila inisialisasi class gagal
            pass

    return BruteForceVectorStore(
        connection=conn,
        embedding=embedding,
        table=table,
    )


__all__ = [
    "TABLE_CHUNKS",
    "TABLE_FINGERPRINTS",
    "TABLE_META",
    "serialize_float32",
    "deserialize_float32",
    "cosine_similarity",
    "open_connection",
    "IndexMetaTable",
    "FingerprintTable",
    "BruteForceVectorStore",
    "build_vector_store",
]
