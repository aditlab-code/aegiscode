"""SQLite-backed CodeGraph storage with Recursive CTE navigation (stdlib only)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.codegraph.models import CodeSymbol, FileFingerprint, RelationType, SymbolRelation


class CodeGraphStore:
    """Deterministic, high-performance SQLite storage for CodeGraph symbols and relations."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None or str(db_path) == ":memory:":
            self._db_path = ":memory:"
        else:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(p)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit mode for explicit transactions
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            if self._db_path != ":memory:":
                cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA foreign_keys=ON;")

            cur.executescript("""
                CREATE TABLE IF NOT EXISTS graph_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS file_fingerprints (
                    file_path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    symbol_count INTEGER DEFAULT 0,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS symbols (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    language TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    signature TEXT,
                    docstring TEXT,
                    body_hash TEXT NOT NULL,
                    git_commit TEXT,
                    last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
                CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
                CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type);

                CREATE TABLE IF NOT EXISTS symbol_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    target_id TEXT,
                    target_name TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES symbols(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_relations_source ON symbol_relations(source_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target ON symbol_relations(target_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target_name ON symbol_relations(target_name);
                CREATE INDEX IF NOT EXISTS idx_relations_type ON symbol_relations(relation_type);
            """)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def save_file_fingerprint(self, fp: FileFingerprint) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO file_fingerprints (file_path, sha256, mtime, symbol_count, indexed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(file_path) DO UPDATE SET
                    sha256=excluded.sha256,
                    mtime=excluded.mtime,
                    symbol_count=excluded.symbol_count,
                    indexed_at=CURRENT_TIMESTAMP
                """,
                (fp.file_path, fp.sha256, fp.mtime, fp.symbol_count),
            )

    def get_file_fingerprint(self, file_path: str) -> Optional[FileFingerprint]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT file_path, sha256, mtime, symbol_count, indexed_at FROM file_fingerprints WHERE file_path = ?",
                (file_path,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return FileFingerprint(
                file_path=row["file_path"],
                sha256=row["sha256"],
                mtime=row["mtime"],
                symbol_count=row["symbol_count"],
                indexed_at=row["indexed_at"],
            )

    def is_file_dirty(self, file_path: str, mtime: float, sha256: str) -> bool:
        fp = self.get_file_fingerprint(file_path)
        if fp is None:
            return True
        if fp.mtime != mtime or fp.sha256 != sha256:
            return True
        return False

    def delete_file_data(self, file_path: str) -> None:
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION;")
            try:
                # symbols deletion automatically cascades to symbol_relations via ON DELETE CASCADE
                self._conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
                self._conn.execute("DELETE FROM file_fingerprints WHERE file_path = ?", (file_path,))
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise

    def insert_symbols(self, symbols: List[CodeSymbol]) -> None:
        if not symbols:
            return
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION;")
            try:
                self._conn.executemany(
                    """
                    INSERT INTO symbols (id, name, type, file_path, language, start_line, end_line, signature, docstring, body_hash, git_commit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        type=excluded.type,
                        language=excluded.language,
                        start_line=excluded.start_line,
                        end_line=excluded.end_line,
                        signature=excluded.signature,
                        docstring=excluded.docstring,
                        body_hash=excluded.body_hash,
                        git_commit=excluded.git_commit,
                        last_indexed_at=CURRENT_TIMESTAMP
                    """,
                    [
                        (
                            s.id, s.name, s.type, s.file_path, s.language,
                            s.start_line, s.end_line, s.signature, s.docstring,
                            s.body_hash, s.git_commit
                        )
                        for s in symbols
                    ],
                )
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise

    def insert_relations(self, relations: List[SymbolRelation]) -> None:
        if not relations:
            return
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION;")
            try:
                self._conn.executemany(
                    """
                    INSERT INTO symbol_relations (source_id, target_id, target_name, relation_type, file_path, line_number)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            r.source_id,
                            r.target_id,
                            r.target_name,
                            r.relation_type.value if isinstance(r.relation_type, RelationType) else str(r.relation_type),
                            r.file_path,
                            r.line_number,
                        )
                        for r in relations
                    ],
                )
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise

    def resolve_relation_targets(self) -> int:
        """Resolve unlinked target_id using known symbol names across indexed files."""
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE symbol_relations
                SET target_id = (
                    SELECT s.id FROM symbols s
                    WHERE s.name = symbol_relations.target_name
                    LIMIT 1
                )
                WHERE target_id IS NULL
                  AND EXISTS (
                      SELECT 1 FROM symbols s WHERE s.name = symbol_relations.target_name
                  )
                """
            )
            return cur.rowcount

    def find_symbol(self, name: str) -> List[CodeSymbol]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM symbols WHERE name = ? ORDER BY file_path, start_line",
                (name,),
            )
            return [self._row_to_symbol(r) for r in cur.fetchall()]

    def get_symbol_by_id(self, symbol_id: str) -> Optional[CodeSymbol]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
            row = cur.fetchone()
            return self._row_to_symbol(row) if row else None

    def get_symbols_in_file(self, file_path: str) -> List[CodeSymbol]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM symbols WHERE file_path = ? ORDER BY start_line",
                (file_path,),
            )
            return [self._row_to_symbol(r) for r in cur.fetchall()]

    def get_callers(self, symbol_name_or_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Find functions/callers calling the target symbol via Recursive CTE."""
        with self._lock:
            cur = self._conn.execute(
                """
                WITH RECURSIVE caller_cte(edge_id, source_id, target_id, target_name, relation_type, file_path, line_number, depth) AS (
                    SELECT id, source_id, target_id, target_name, relation_type, file_path, line_number, 1
                    FROM symbol_relations
                    WHERE (target_name = :sym OR target_id = :sym)
                      AND relation_type IN ('calls', 'api_call')
                    UNION ALL
                    SELECT r.id, r.source_id, r.target_id, r.target_name, r.relation_type, r.file_path, r.line_number, c.depth + 1
                    FROM symbol_relations r
                    JOIN caller_cte c ON (r.target_id = c.source_id OR r.target_name = (SELECT name FROM symbols WHERE id = c.source_id))
                    WHERE c.depth < :max_depth
                      AND r.relation_type IN ('calls', 'api_call')
                )
                SELECT DISTINCT c.edge_id, c.source_id, c.target_id, c.target_name, c.relation_type,
                                c.file_path, c.line_number, c.depth,
                                s.name AS caller_name, s.type AS caller_type, s.file_path AS caller_file
                FROM caller_cte c
                LEFT JOIN symbols s ON c.source_id = s.id
                ORDER BY c.depth ASC, c.file_path ASC
                """,
                {"sym": symbol_name_or_id, "max_depth": depth},
            )
            return [dict(r) for r in cur.fetchall()]

    def get_callees(self, symbol_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Find functions called by the target symbol via Recursive CTE."""
        with self._lock:
            cur = self._conn.execute(
                """
                WITH RECURSIVE callee_cte(edge_id, source_id, target_id, target_name, relation_type, file_path, line_number, depth) AS (
                    SELECT id, source_id, target_id, target_name, relation_type, file_path, line_number, 1
                    FROM symbol_relations
                    WHERE source_id = :sym
                      AND relation_type IN ('calls', 'api_call')
                    UNION ALL
                    SELECT r.id, r.source_id, r.target_id, r.target_name, r.relation_type, r.file_path, r.line_number, c.depth + 1
                    FROM symbol_relations r
                    JOIN callee_cte c ON r.source_id = c.target_id
                    WHERE c.depth < :max_depth
                      AND c.target_id IS NOT NULL
                      AND r.relation_type IN ('calls', 'api_call')
                )
                SELECT DISTINCT c.edge_id, c.source_id, c.target_id, c.target_name, c.relation_type,
                                c.file_path, c.line_number, c.depth,
                                s.name AS callee_name, s.type AS callee_type, s.file_path AS callee_file
                FROM callee_cte c
                LEFT JOIN symbols s ON c.target_id = s.id
                ORDER BY c.depth ASC, c.file_path ASC
                """,
                {"sym": symbol_id, "max_depth": depth},
            )
            return [dict(r) for r in cur.fetchall()]

    def get_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all usage references and imports of a symbol."""
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT r.id, r.source_id, r.target_id, r.target_name, r.relation_type,
                       r.file_path, r.line_number, s.name AS source_name
                FROM symbol_relations r
                LEFT JOIN symbols s ON r.source_id = s.id
                WHERE r.target_name = ? OR r.target_id = ?
                ORDER BY r.file_path, r.line_number
                """,
                (symbol_name, symbol_name),
            )
            return [dict(r) for r in cur.fetchall()]

    def impact_analysis(self, target: str, depth: int = 3) -> Dict[str, Any]:
        """Compute structural impact and blast radius for a symbol or file."""
        with self._lock:
            cur = self._conn.execute(
                """
                WITH RECURSIVE impact_cte(symbol_id, symbol_name, file_path, relation_type, depth) AS (
                    SELECT id, name, file_path, 'root', 0
                    FROM symbols
                    WHERE id = :target OR name = :target OR file_path = :target
                    UNION
                    SELECT s.id, s.name, s.file_path, r.relation_type, i.depth + 1
                    FROM symbol_relations r
                    JOIN impact_cte i ON (r.target_id = i.symbol_id OR r.target_name = i.symbol_name)
                    JOIN symbols s ON r.source_id = s.id
                    WHERE i.depth < :max_depth
                )
                SELECT DISTINCT symbol_id, symbol_name, file_path, relation_type, depth
                FROM impact_cte
                ORDER BY depth ASC
                """,
                {"target": target, "max_depth": depth},
            )
            rows = [dict(r) for r in cur.fetchall()]
            affected_symbols = [r for r in rows if r["depth"] > 0]
            affected_files = sorted(list({r["file_path"] for r in rows}))
            return {
                "target": target,
                "max_depth": depth,
                "affected_symbols_count": len(affected_symbols),
                "affected_files": affected_files,
                "impact_chain": rows,
            }

    def set_meta(self, key: str, value: str) -> None:
        """Set a metadata key-value pair."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO graph_meta (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def get_meta(self, key: str) -> Optional[str]:
        """Retrieve a metadata value by key."""
        with self._lock:
            cur = self._conn.execute("SELECT value FROM graph_meta WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else None

    def clear_all(self) -> None:
        """Purge all stored CodeGraph data."""
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION;")
            try:
                self._conn.execute("DELETE FROM symbol_relations;")
                self._conn.execute("DELETE FROM symbols;")
                self._conn.execute("DELETE FROM file_fingerprints;")
                self._conn.execute("DELETE FROM graph_meta;")
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise

    def get_all_fingerprints(self) -> Dict[str, FileFingerprint]:
        """Fetch all stored file fingerprints mapped by file_path."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT file_path, sha256, mtime, symbol_count, indexed_at FROM file_fingerprints"
            )
            res: Dict[str, FileFingerprint] = {}
            for row in cur.fetchall():
                res[row["file_path"]] = FileFingerprint(
                    file_path=row["file_path"],
                    sha256=row["sha256"],
                    mtime=row["mtime"],
                    symbol_count=row["symbol_count"],
                    indexed_at=row["indexed_at"],
                )
            return res

    def find_orphans(self) -> List[CodeSymbol]:
        """Find defined functions and classes that are never called or referenced."""
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT s.*
                FROM symbols s
                WHERE s.type IN ('function', 'method', 'class')
                  AND NOT EXISTS (
                      SELECT 1 FROM symbol_relations r
                      WHERE (r.target_id = s.id OR r.target_name = s.name)
                        AND r.source_id != s.id
                  )
                ORDER BY s.file_path, s.start_line
                """
            )
            return [self._row_to_symbol(r) for r in cur.fetchall()]

    def get_related_files(self, file_path: str) -> List[str]:
        """Find distinct files connected to file_path via imports or call relations."""
        with self._lock:
            cur = self._conn.execute(
                """
                WITH file_syms AS (
                    SELECT id, name FROM symbols WHERE file_path = :fp
                )
                SELECT DISTINCT file_path FROM (
                    -- Files referenced by symbols in file_path
                    SELECT s.file_path
                    FROM symbol_relations r
                    JOIN symbols s ON (r.target_id = s.id OR r.target_name = s.name)
                    WHERE r.file_path = :fp AND s.file_path != :fp
                    UNION
                    -- Files that reference symbols in file_path
                    SELECT r.file_path
                    FROM symbol_relations r
                    JOIN file_syms fs ON (r.target_id = fs.id OR r.target_name = fs.name)
                    WHERE r.file_path != :fp
                )
                ORDER BY file_path ASC
                """,
                {"fp": file_path},
            )
            return [row["file_path"] for row in cur.fetchall()]


    def get_stats(self) -> Dict[str, Any]:
        """Return basic database statistics."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM symbols;")
            symbol_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM symbol_relations;")
            relation_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM file_fingerprints;")
            file_count = cur.fetchone()[0]
            return {
                "symbol_count": symbol_count,
                "relation_count": relation_count,
                "file_count": file_count,
            }
    @staticmethod

    def _row_to_symbol(row: sqlite3.Row) -> CodeSymbol:
        return CodeSymbol(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            file_path=row["file_path"],
            language=row["language"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            signature=row["signature"],
            docstring=row["docstring"],
            body_hash=row["body_hash"],
            git_commit=row["git_commit"],
            last_indexed_at=row["last_indexed_at"],
        )
