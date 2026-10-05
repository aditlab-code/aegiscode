"""Hybrid Retrieval Coordinator untuk menggabungkan Code Atlas dan sqlite-vec (Phase 3).

Menyediakan dual query routing:
1. Lexical keyword lookup dari Code Atlas (.aegis/map/atlas.json).
2. Semantic similarity search dari basis data vektor lokal sqlite-vec (.aegis/vectors.db).
3. Penyatuan dan pemeringkatan kandidat dengan Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.repointel.semantic.availability import is_available
from agent_ai.repointel.semantic.rrf import (
    DEFAULT_RRF_K,
    fuse_code_results,
)

PathLike = Union[str, os.PathLike[str]]


class HybridRetrievalCoordinator:
    """Koordinator pencarian kode hibrida (Dual Query Routing + RRF)."""

    def __init__(
        self,
        root: Optional[PathLike] = None,
        project_map_service: Optional[Any] = None,
        semantic_service: Optional[Any] = None,
        read_only: bool = True,
    ) -> None:
        self.root = Path(root).resolve() if root is not None else None
        self._project_map_service = project_map_service
        self._semantic_service = semantic_service
        self.read_only = read_only

    def _get_project_map_service(self) -> Any:
        if self._project_map_service is not None:
            return self._project_map_service
        from agent_ai.projects.project_map import ProjectMapService

        self._project_map_service = ProjectMapService()
        return self._project_map_service

    def _get_semantic_service(self) -> Optional[Any]:
        if self._semantic_service is not None:
            return self._semantic_service
        if self.root is not None:
            available, _ = is_available()
            if not available:
                return None
            try:
                from agent_ai.repointel.semantic.service import SemanticIndexService

                self._semantic_service = SemanticIndexService(
                    root=self.root, read_only=self.read_only
                )
                return self._semantic_service
            except Exception:
                return None
        return None

    def search(
        self,
        query: str,
        k: int = 10,
        kind: Optional[str] = None,
        path_prefix: Optional[str] = None,
        lexical_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> Dict[str, Any]:
        """Eksekusi dual query routing dan gabungkan hasil menggunakan Reciprocal Rank Fusion.

        Args:
            query: Kueri pencarian (nama simbol, fungsi, class, atau konsep logika).
            k: Batas jumlah kandidat teratas yang dikembalikan.
            kind: Filter jenis simbol opsional (any, symbol, class, function, method, module, file).
            path_prefix: Filter awalan direktori/berkas opsional.
            lexical_weight: Bobot prioritas pencarian leksikal (default: 1.0).
            semantic_weight: Bobot prioritas pencarian semantik (default: 1.0).
            rrf_k: Konstanta perataan RRF (default: 60).

        Returns:
            Dict hasil hybrid terstruktur.
        """
        clean_query = str(query or "").strip()
        if not clean_query:
            return {
                "status": "error",
                "error": "Query pencarian tidak boleh kosong.",
                "results": [],
            }

        target_k = max(1, min(int(k), 50))
        fetch_k = target_k * 2

        lexical_results: List[Dict[str, Any]] = []
        lexical_status = "ok"

        # 1. Cabang Lexical: Code Atlas Lookup
        if self.root is not None:
            try:
                from agent_ai.projects.project_map import (
                    MapInvalidError,
                    MapNotFoundError,
                )
                from agent_ai.projects.project_map_query import (
                    MapQueryError,
                    atlas_query,
                )

                map_service = self._get_project_map_service()
                atlas_res = atlas_query(
                    map_service,
                    self.root,
                    clean_query,
                    kind=kind,
                    include_relations=True,
                    max_results=fetch_k,
                )
                lexical_results = atlas_res.get("results") or []
                lexical_status = atlas_res.get("map_status", "fresh")
            except (MapNotFoundError, FileNotFoundError):
                lexical_status = "missing"
            except (MapInvalidError, MapQueryError, Exception):
                lexical_status = "unavailable"
        else:
            lexical_status = "no_root"

        # 2. Cabang Semantik: sqlite-vec VectorDB Lookup
        semantic_results: List[Dict[str, Any]] = []
        semantic_status = "ok"

        sem_available, sem_reason = is_available()
        if not sem_available:
            semantic_status = f"unavailable: {sem_reason}"
        elif self.root is None:
            semantic_status = "no_root"
        else:
            sem_service = self._get_semantic_service()
            if sem_service is None:
                semantic_status = "unavailable"
            else:
                try:
                    semantic_results = sem_service.search(
                        query=clean_query,
                        k=fetch_k,
                        path_prefix=path_prefix,
                    )
                except Exception as exc:
                    semantic_status = f"error: {exc}"

        # Filter path_prefix pada cabang lexical jika ditentukan
        if path_prefix and lexical_results:
            clean_prefix = str(path_prefix).replace("\\", "/").strip().lstrip("./")
            filtered_lex: List[Dict[str, Any]] = []
            for item in lexical_results:
                fpath = str(item.get("file") or item.get("path") or "").replace("\\", "/").lstrip("./")
                if fpath.startswith(clean_prefix):
                    filtered_lex.append(item)
            lexical_results = filtered_lex

        # Filter kind pada cabang semantik jika ditentukan
        if kind and kind not in ("any", "*", "all") and semantic_results:
            clean_kind = str(kind).lower()
            semantic_results = [
                s for s in semantic_results if str(s.get("kind") or "").lower() == clean_kind
            ]

        # Tentukan mode pencarian berdasarkan ketersediaan hasil
        if lexical_results and semantic_results:
            mode = "hybrid"
        elif lexical_results:
            mode = "lexical_only"
        elif semantic_results:
            mode = "semantic_only"
        else:
            mode = "empty"

        # 3. Fusi Reciprocal Rank Fusion (RRF)
        fused = fuse_code_results(
            lexical_results=lexical_results,
            semantic_results=semantic_results,
            k=rrf_k,
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
            max_results=target_k,
        )

        return {
            "status": "ok",
            "query": clean_query,
            "mode": mode,
            "total_results": len(fused),
            "lexical_status": lexical_status,
            "semantic_status": semantic_status,
            "results": fused,
        }


__all__ = ["HybridRetrievalCoordinator"]
