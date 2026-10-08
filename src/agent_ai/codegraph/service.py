"""High-level CodeGraph service facade with incremental synchronization engine (stdlib only)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from agent_ai.codegraph.extractor import compute_content_hash, extract_file
from agent_ai.codegraph.migration import migrate_legacy_vectors
from agent_ai.codegraph.models import CodeSymbol, FileFingerprint
from agent_ai.codegraph.store import CodeGraphStore


IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    ".aegis",
    ".gemini",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "coverage",
}

SUPPORTED_EXTENSIONS: Set[str] = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".vue",
}


class CodeGraphService:
    """Service facade connecting AI Agent and Studio runtime with deterministic CodeGraph storage."""

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        store: Optional[CodeGraphStore] = None,
    ) -> None:
        self.project_root = Path(project_root).resolve() if project_root else None

        if store is not None:
            self.store = store
        elif self.project_root:
            db_dir = self.project_root / ".aegis"
            db_dir.mkdir(parents=True, exist_ok=True)
            migrate_legacy_vectors(self.project_root)
            self.store = CodeGraphStore(db_dir / "codegraph.db")
        else:
            self.store = CodeGraphStore(":memory:")


    def close(self) -> None:
        """Close database connection."""
        self.store.close()

    def _scan_files(self, area: Optional[str] = None) -> List[Path]:
        """Scan project workspace for candidate source code files."""
        if not self.project_root or not self.project_root.exists():
            return []

        base_scan_dir = self.project_root
        if area:
            target_area = (self.project_root / area).resolve()
            if target_area.exists():
                base_scan_dir = target_area

        candidates: List[Path] = []
        for root, dirs, files in os.walk(base_scan_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    candidates.append(Path(root) / f)
        return candidates

    def _process_file(
        self, file_path: Path
    ) -> Optional[Tuple[str, List[CodeSymbol], List[Any], FileFingerprint]]:
        """Extract symbols, relations, and compute fingerprint for a single file."""
        try:
            rel_path = (
                str(file_path.relative_to(self.project_root))
                if self.project_root
                else file_path.name
            )
            content = file_path.read_text(encoding="utf-8", errors="replace")
            sha256 = compute_content_hash(content)
            mtime = file_path.stat().st_mtime
            symbols, relations = extract_file(file_path, self.project_root)
            fingerprint = FileFingerprint(
                file_path=rel_path,
                sha256=sha256,
                mtime=mtime,
                symbol_count=len(symbols),
            )
            return rel_path, symbols, relations, fingerprint
        except Exception:
            return None

    def full_resync(self) -> Dict[str, Any]:
        """Perform full resync of the workspace: purge all and re-index all files deterministically."""
        start_time = time.perf_counter()
        self.store.clear_all()

        files = self._scan_files()
        total_symbols = 0
        total_relations = 0

        for file_path in files:
            processed = self._process_file(file_path)
            if not processed:
                continue
            rel_path, symbols, relations, fingerprint = processed
            self.store.save_file_fingerprint(fingerprint)
            self.store.insert_symbols(symbols)
            self.store.insert_relations(relations)
            total_symbols += len(symbols)
            total_relations += len(relations)

        # Resolve unlinked foreign keys
        self.store.resolve_relation_targets()
        self.store.set_meta("last_sync_timestamp", str(time.time()))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "status": "ok",
            "mode": "full_resync",
            "files_indexed": len(files),
            "symbols_indexed": total_symbols,
            "relations_indexed": total_relations,
            "elapsed_ms": round(elapsed_ms, 2),
        }

    def incremental_sync(self, dirty_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fast incremental sync updating only modified, new, or deleted files."""
        start_time = time.perf_counter()
        if not self.project_root:
            return {"status": "ok", "mode": "incremental_sync", "updated_files": 0, "elapsed_ms": 0.0}

        known_fps = self.store.get_all_fingerprints()
        current_disk_files = self._scan_files()
        current_disk_rel_paths = set()

        files_to_reindex: List[Path] = []

        if dirty_files is not None:
            for df in dirty_files:
                p = (self.project_root / df).resolve()
                if p.exists():
                    files_to_reindex.append(p)
                else:
                    self.store.delete_file_data(df)
        else:
            # Detect dirty and new files
            for p in current_disk_files:
                rel_path = str(p.relative_to(self.project_root))
                current_disk_rel_paths.add(rel_path)
                mtime = p.stat().st_mtime
                fp = known_fps.get(rel_path)
                if fp is None or fp.mtime != mtime:
                    files_to_reindex.append(p)

            # Detect deleted files
            for rel_path in known_fps:
                if rel_path not in current_disk_rel_paths:
                    self.store.delete_file_data(rel_path)

        updated_symbols = 0
        updated_relations = 0

        for file_path in files_to_reindex:
            processed = self._process_file(file_path)
            if not processed:
                continue
            rel_path, symbols, relations, fingerprint = processed
            self.store.delete_file_data(rel_path)
            self.store.save_file_fingerprint(fingerprint)
            self.store.insert_symbols(symbols)
            self.store.insert_relations(relations)
            updated_symbols += len(symbols)
            updated_relations += len(relations)

        if files_to_reindex:
            self.store.resolve_relation_targets()

        self.store.set_meta("last_sync_timestamp", str(time.time()))
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "status": "ok",
            "mode": "incremental_sync",
            "updated_files": len(files_to_reindex),
            "updated_symbols": updated_symbols,
            "updated_relations": updated_relations,
            "elapsed_ms": round(elapsed_ms, 2),
        }

    def on_demand_refresh(self, area: str) -> Dict[str, Any]:
        """Scoped refresh on specific sub-path / module."""
        start_time = time.perf_counter()
        if not self.project_root:
            return {"status": "ok", "mode": "on_demand_refresh", "updated_files": 0, "elapsed_ms": 0.0}

        target_area = (self.project_root / area).resolve()
        if not target_area.exists():
            return {
                "status": "error",
                "message": f"Area '{area}' does not exist",
                "updated_files": 0,
            }

        scanned = self._scan_files(area=area)
        for p in scanned:
            processed = self._process_file(p)
            if not processed:
                continue
            rel_path, symbols, relations, fingerprint = processed
            self.store.delete_file_data(rel_path)
            self.store.save_file_fingerprint(fingerprint)
            self.store.insert_symbols(symbols)
            self.store.insert_relations(relations)

        self.store.resolve_relation_targets()
        self.store.set_meta("last_sync_timestamp", str(time.time()))
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0


        return {
            "status": "ok",
            "mode": "on_demand_refresh",
            "area": area,
            "updated_files": len(scanned),
            "elapsed_ms": round(elapsed_ms, 2),
        }

    def ensure_graph_fresh(
        self,
        area: Optional[str] = None,
        max_stale_seconds: float = 2.0,
    ) -> bool:
        """Deterministic guardrail verifying CodeGraph freshness before agent decision.

        Runs sub-millisecond check if synced within max_stale_seconds, otherwise performs
        fast incremental sync.
        """
        try:
            last_sync_raw = self.store.get_meta("last_sync_timestamp")
            if last_sync_raw:
                last_sync = float(last_sync_raw)
                if (time.time() - last_sync) < max_stale_seconds:
                    return True

            if area:
                self.on_demand_refresh(area)
            else:
                self.incremental_sync()
            return True
        except Exception:
            # Defensive: ensure_graph_fresh never blocks agent execution
            return True

    # -------------------------------------------------------------------------
    # Query API Facade
    # -------------------------------------------------------------------------

    def find_symbol(self, name: str) -> List[Dict[str, Any]]:
        """Find symbol definitions by name."""
        symbols = self.store.find_symbol(name)
        return [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "file_path": s.file_path,
                "language": s.language,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "signature": s.signature,
                "docstring": s.docstring,
            }
            for s in symbols
        ]

    def get_callers(self, symbol: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Get callers that call the target symbol up to specified depth."""
        return self.store.get_callers(symbol, depth=depth)

    def get_callees(self, symbol: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Get callees called by target symbol up to specified depth."""
        # Find symbol ID if symbol is a raw name
        target_id = symbol
        if "::" not in symbol:
            matches = self.store.find_symbol(symbol)
            if matches:
                target_id = matches[0].id
        return self.store.get_callees(target_id, depth=depth)

    def get_references(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all references and usages of the symbol."""
        return self.store.get_references(symbol)

    def get_related_files(self, file_path: str) -> List[str]:
        """Get files directly related via imports or function calls."""
        # Normalize relative path if given absolute
        if self.project_root and file_path.startswith(str(self.project_root)):
            file_path = str(Path(file_path).relative_to(self.project_root))
        return self.store.get_related_files(file_path)

    def trace_frontend_to_backend(self, component_or_endpoint: str) -> List[Dict[str, Any]]:
        """Trace relations between frontend API calls and backend route definitions."""
        with self.store._lock:
            cur = self.store._conn.execute(
                """
                SELECT r.id, r.source_id, r.target_name, r.relation_type, r.file_path, r.line_number,
                       s.name AS source_name, s.type AS source_type
                FROM symbol_relations r
                JOIN symbols s ON r.source_id = s.id
                WHERE (r.relation_type IN ('api_call', 'api_endpoint')
                       AND (r.target_name LIKE ? OR s.name LIKE ? OR r.file_path LIKE ?))
                ORDER BY r.file_path, r.line_number
                """,
                (f"%{component_or_endpoint}%", f"%{component_or_endpoint}%", f"%{component_or_endpoint}%"),
            )
            return [dict(row) for row in cur.fetchall()]

    def find_orphans(self) -> List[Dict[str, Any]]:
        """Find dead code symbols defined but never referenced or called."""
        orphans = self.store.find_orphans()
        return [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "file_path": s.file_path,
                "start_line": s.start_line,
            }
            for s in orphans
        ]

    def impact_analysis(self, target: str, depth: int = 2) -> Dict[str, Any]:
        """Compute blast radius and affected files before modifying code."""
        return self.store.impact_analysis(target, depth=depth)

    def get_stats(self) -> Dict[str, Any]:
        """Return CodeGraph storage statistics."""
        return self.store.get_stats()
