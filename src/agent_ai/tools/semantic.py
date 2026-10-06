"""Tools pencarian semantik kode dan manajemen indeks vektor (Phase 2.1).

Menyediakan kemampuan pencarian berbasis makna (semantic search) dan
pembaharuan indeks vektor lokal untuk Agent dan Consultant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_ai.repointel.semantic.availability import is_available
from agent_ai.tools.base import BaseTool, ToolValidationError



class _SemanticToolBase(BaseTool):
    """Base class untuk tool semantik dengan resolusi workspace root dan service."""

    def __init__(
        self,
        root: Optional[Any] = None,
        service: Optional[Any] = None,
        read_only: bool = False,
    ) -> None:
        self.root = Path(root).resolve() if root is not None else None
        self._service = service
        self.read_only = read_only

    def _get_service(self) -> Optional[Any]:
        if self._service is not None:
            return self._service
        if self.root is not None:
            from agent_ai.repointel.semantic.service import SemanticIndexService

            self._service = SemanticIndexService(root=self.root, read_only=self.read_only)
            return self._service
        return None


    def _require_root(self) -> Path:
        if self.root is None:
            raise ToolValidationError(
                "Root project tidak ditentukan. Tool semantik memerlukan target workspace."
            )
        return self.root


class SemanticSearchTool(_SemanticToolBase):
    """Pencarian potongan kode berbasis kemiripan semantik / vektor lokal."""

    name = "semantic_search"
    description = (
        "Melakukan pencarian semantik atas basis kode proyek (Python, JavaScript, TypeScript) "
        "menggunakan representasi vektor lokal. Mengembalikan potongan fungsi, kelas, atau metode "
        "yang relevan secara makna dan konsep meskipun tidak memuat kecocokan kata kunci eksak."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Deskripsi atau kueri fungsionalitas kode yang dicari.",
            },
            "k": {
                "type": "integer",
                "description": "Jumlah hasil paling relevan yang dikembalikan (1-20, default 8).",
                "default": 8,
            },
            "path_prefix": {
                "type": "string",
                "description": "Filter awalan path berkas opsional untuk membatasi ruang pencarian.",
            },
        },
        "required": ["query"],
    }

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        available, reason = is_available()
        if not available:
            return {
                "status": "unavailable",
                "reason": reason,
                "hint": "Jalankan: pip install aegis-agent[semantic] untuk mengaktifkan pencarian semantik.",
                "results": [],
            }

        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ToolValidationError("Argumen 'query' wajib diisi dan tidak boleh kosong.")

        k_val = arguments.get("k", 8)
        try:
            k = max(1, min(int(k_val), 20))
        except (ValueError, TypeError):
            k = 8

        path_prefix = arguments.get("path_prefix")
        if path_prefix:
            path_prefix = str(path_prefix).strip()

        self._require_root()
        service = self._get_service()
        if not service:
            return {
                "status": "error",
                "error": "Layanan semantik tidak dapat diinisialisasi.",
                "results": [],
            }

        try:
            results = service.search(query=query, k=k, path_prefix=path_prefix)
            status_info = service.status()
            return {
                "status": "ok",
                "query": query,
                "total_results": len(results),
                "backend": status_info.get("backend", "unknown"),
                "results": results,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "results": [],
            }


class RefreshSemanticIndexTool(_SemanticToolBase):
    """Memperbarui atau membangun ulang indeks vektor semantik (.aegis/vectors.db)."""

    name = "refresh_semantic_index"
    description = (
        "Memperbarui atau membangun ulang indeks semantik repositori (.aegis/vectors.db). "
        "Gunakan secara manual bila terjadi perubahan berkas massal. Mode default (full=false) "
        "melakukan pembaruan inkremental cepat berbasis SHA-256."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "full": {
                "type": "boolean",
                "description": "Bila true, bangun ulang seluruh indeks dari awal. Default: false (inkremental).",
                "default": False,
            }
        },
    }

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        available, reason = is_available()
        if not available:
            return {
                "status": "unavailable",
                "reason": reason,
                "hint": "Jalankan: pip install aegis-agent[semantic] untuk mengaktifkan pengindeksan semantik.",
            }

        full = bool(arguments.get("full", False))
        self._require_root()
        service = self._get_service()
        if not service:
            return {
                "status": "error",
                "error": "Layanan semantik tidak dapat diinisialisasi.",
            }

        try:
            stats = service.refresh(full=full)
            return {
                "status": "ok",
                "full": full,
                "stats": stats.to_dict(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


class HybridSearchTool(_SemanticToolBase):
    """Pencarian kode hibrida menggabungkan Code Atlas (leksikal) dan sqlite-vec (vektor) via RRF (Phase 3)."""

    name = "hybrid_search"
    description = (
        "Melakukan pencarian kode hibrida (hybrid retrieval) yang memadukan pencarian "
        "leksikal eksak (Code Atlas) dan kemiripan semantik (VectorDB) menggunakan "
        "algoritma Reciprocal Rank Fusion (RRF). Sangat presisi untuk menemukan definisi simbol, "
        "fungsi, kelas, maupun konsep kode yang relevan secara bersamaan."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Nama simbol, class, function, method, atau konsep logika kode yang dicari.",
            },
            "k": {
                "type": "integer",
                "description": "Jumlah hasil paling relevan yang dikembalikan (1-30, default 10).",
                "default": 10,
            },
            "kind": {
                "type": "string",
                "description": "Filter tipe simbol opsional: any | symbol | class | function | method | module | file (default: any).",
            },
            "path_prefix": {
                "type": "string",
                "description": "Filter awalan path berkas opsional untuk membatasi ruang pencarian.",
            },
            "lexical_weight": {
                "type": "number",
                "description": "Bobot prioritas pencarian leksikal Code Atlas (default: 1.0).",
                "default": 1.0,
            },
            "semantic_weight": {
                "type": "number",
                "description": "Bobot prioritas pencarian semantik vektor (default: 1.0).",
                "default": 1.0,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        root: Optional[Any] = None,
        service: Optional[Any] = None,
        coordinator: Optional[Any] = None,
        read_only: bool = False,
    ) -> None:
        super().__init__(root=root, service=service, read_only=read_only)
        self._coordinator = coordinator

    def _get_coordinator(self) -> Any:
        if self._coordinator is not None:
            return self._coordinator
        from agent_ai.repointel.semantic.hybrid import HybridRetrievalCoordinator

        self._coordinator = HybridRetrievalCoordinator(
            root=self.root,
            semantic_service=self._get_service(),
            read_only=self.read_only,
        )
        return self._coordinator

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ToolValidationError("Argumen 'query' wajib diisi dan tidak boleh kosong.")

        k_val = arguments.get("k", 10)
        try:
            k = max(1, min(int(k_val), 30))
        except (ValueError, TypeError):
            k = 10

        kind = arguments.get("kind")
        if kind is not None:
            kind = str(kind).strip().lower()
            if kind in ("", "any", "all", "*"):
                kind = None

        path_prefix = arguments.get("path_prefix")
        if path_prefix:
            path_prefix = str(path_prefix).strip()

        try:
            lexical_weight = float(arguments.get("lexical_weight", 1.0))
        except (ValueError, TypeError):
            lexical_weight = 1.0

        try:
            semantic_weight = float(arguments.get("semantic_weight", 1.0))
        except (ValueError, TypeError):
            semantic_weight = 1.0

        self._require_root()
        coordinator = self._get_coordinator()
        try:
            return coordinator.search(
                query=query,
                k=k,
                kind=kind,
                path_prefix=path_prefix,
                lexical_weight=lexical_weight,
                semantic_weight=semantic_weight,
            )
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "results": [],
            }


def build_semantic_tools(
    root: Optional[Any] = None,
    service: Optional[SemanticIndexService] = None,
    include_refresh: bool = False,
    read_only: bool = False,
    include_hybrid: bool = False,
) -> List[BaseTool]:
    """Bangun daftar capability pencarian semantik (satu sumber konstruksi tool).

    Dipakai oleh registry Agent (include_refresh=True, read_only=False)
    dan registry Consultant (include_refresh=False, read_only=True).
    """
    tools: List[BaseTool] = [
        SemanticSearchTool(root=root, service=service, read_only=read_only),
    ]
    if include_hybrid:
        tools.append(HybridSearchTool(root=root, service=service, read_only=read_only))
    if include_refresh and not read_only:
        tools.append(RefreshSemanticIndexTool(root=root, service=service, read_only=False))
    return tools


def build_hybrid_tools(
    root: Optional[Any] = None,
    service: Optional[Any] = None,
    read_only: bool = False,
) -> List[BaseTool]:
    """Bangun capability pencarian kode hybrid."""
    return [HybridSearchTool(root=root, service=service, read_only=read_only)]


__all__ = [
    "SemanticSearchTool",
    "RefreshSemanticIndexTool",
    "HybridSearchTool",
    "build_semantic_tools",
    "build_hybrid_tools",
]

