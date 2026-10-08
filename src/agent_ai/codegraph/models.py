"""Data models for CodeGraph relational code intelligence (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RelationType(str, Enum):
    """Canonical relation types for CodeGraph directed edges."""
    IMPORTS = "imports"
    CALLS = "calls"
    DEFINES = "defines"
    REFERENCES = "references"
    EXTENDS = "extends"
    API_ENDPOINT = "api_endpoint"
    API_CALL = "api_call"


@dataclass
class CodeSymbol:
    """Representation of an extracted code symbol (class, function, method, endpoint)."""
    id: str
    name: str
    type: str  # 'function', 'class', 'method', 'endpoint', 'variable'
    file_path: str  # workspace-relative path
    language: str  # 'python', 'javascript', 'typescript', 'vue'
    start_line: int
    end_line: int
    body_hash: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    git_commit: Optional[str] = None
    last_indexed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "file_path": self.file_path,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "docstring": self.docstring,
            "body_hash": self.body_hash,
            "git_commit": self.git_commit,
            "last_indexed_at": self.last_indexed_at,
        }


@dataclass
class SymbolRelation:
    """Directed edge between two symbols or a symbol and target name."""
    source_id: str
    target_name: str
    relation_type: RelationType
    file_path: str
    line_number: int
    target_id: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        rel_val = self.relation_type.value if isinstance(self.relation_type, RelationType) else str(self.relation_type)
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "relation_type": rel_val,
            "file_path": self.file_path,
            "line_number": self.line_number,
        }


@dataclass
class FileFingerprint:
    """File metadata for incremental sync and dirty detection."""
    file_path: str
    sha256: str
    mtime: float
    symbol_count: int = 0
    indexed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "sha256": self.sha256,
            "mtime": self.mtime,
            "symbol_count": self.symbol_count,
            "indexed_at": self.indexed_at,
        }
