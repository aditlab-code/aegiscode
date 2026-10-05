"""Reciprocal Rank Fusion (RRF) untuk penggabungan pencarian leksikal dan semantik (Phase 3).

Menyediakan algoritma Reciprocal Rank Fusion deterministik untuk
menginterleave dan menormalkan kandidat dari berbagai sumber ranking
(misalnya Code Atlas TOC dan sqlite-vec VectorDB).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Hashable, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")

#: Default smoothing parameter RRF konvensional (Cormack et al., 2009).
DEFAULT_RRF_K: int = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[T]],
    k: int = DEFAULT_RRF_K,
    weights: Optional[Sequence[float]] = None,
    key_fn: Optional[Callable[[T], Hashable]] = None,
) -> List[Tuple[T, float]]:
    """Hitung skor Reciprocal Rank Fusion (RRF) atas sejumlah daftar peringkat.

    Formula:
        RRF_Score(d) = sum_{m in M} ( w_m / (k + r_m(d)) )
        dengan r_m(d) adalah 1-based rank elemen d pada sistem ranking m.

    Args:
        rankings: Sekuens daftar item yang sudah diurutkan (0-indexed rank).
        k: Parameter smoothing konstan (default: 60).
        weights: Bobot pengali per sistem ranking (default: 1.0 untuk setiap sistem).
        key_fn: Fungsi pemetaan unik identitas kandidat (default: identitas item).

    Returns:
        Daftar tuple (item, score) terurut menurun berdasarkan skor RRF.
    """
    if not rankings:
        return []

    smooth_k = max(1, int(k))
    num_rankers = len(rankings)
    system_weights = (
        [float(w) for w in weights]
        if weights is not None and len(weights) == num_rankers
        else [1.0] * num_rankers
    )

    get_key = key_fn if key_fn is not None else (lambda x: x)

    scores: Dict[Hashable, float] = {}
    items: Dict[Hashable, T] = {}

    for ranker_idx, ranked_list in enumerate(rankings):
        weight = system_weights[ranker_idx]
        for zero_rank, item in enumerate(ranked_list):
            item_key = get_key(item)
            if item_key not in items:
                items[item_key] = item
            # 1-based rank: zero_rank + 1
            rank_1based = zero_rank + 1
            item_score = weight / (smooth_k + rank_1based)
            scores[item_key] = scores.get(item_key, 0.0) + item_score

    # Deterministic sort: score desc, kemudian representasi string key asc
    sorted_keys = sorted(
        scores.keys(),
        key=lambda key: (-scores[key], str(key)),
    )

    return [(items[k], scores[k]) for k in sorted_keys]


def _extract_canonical_key(item: Dict[str, Any]) -> str:
    """Ekstraksi identitas kanonikal untuk deduplikasi kandidat kode."""
    raw_path = item.get("path") or item.get("file") or ""
    path = str(raw_path).replace("\\", "/").strip().lstrip("./")

    kind = str(item.get("kind") or "").lower()
    raw_sym = item.get("symbol") or (item.get("name") if kind not in ("file", "module") else "")
    symbol = str(raw_sym or "").strip()

    line_start = item.get("start_line") or item.get("line_start")
    line = int(line_start) if line_start is not None else 0

    if path and symbol:
        return f"{path}::{symbol}"
    if path and line:
        return f"{path}::{line}"
    return path or str(sorted(item.items()))


def fuse_code_results(
    lexical_results: List[Dict[str, Any]],
    semantic_results: List[Dict[str, Any]],
    k: int = DEFAULT_RRF_K,
    lexical_weight: float = 1.0,
    semantic_weight: float = 1.0,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Gabungkan dan normalisasi hasil pencarian leksikal (Atlas) dan semantik (VectorDB).

    Menyusun ulang metadata (snippet, baris, relasi pemanggil/dipanggil)
    secara terpadu ke dalam struktur kandidat hasil yang ringkas dan kaya konteks.

    Args:
        lexical_results: Hasil dari Code Atlas TOC lookup (atlas_query).
        semantic_results: Hasil dari pencarian kemiripan vektor (semantic_search).
        k: Smoothing constant RRF (default: 60).
        lexical_weight: Bobot prioritas ranking leksikal (default: 1.0).
        semantic_weight: Bobot prioritas ranking semantik (default: 1.0).
        max_results: Batas jumlah hasil teratas yang dikembalikan.

    Returns:
        Daftar kandidat hasil hybrid terurut menurun berdasarkan skor RRF.
    """
    if not lexical_results and not semantic_results:
        return []

    # Map rank 1-based awal per sumber
    lexical_rank_map: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    for idx, item in enumerate(lexical_results):
        key = _extract_canonical_key(item)
        if key not in lexical_rank_map:
            lexical_rank_map[key] = (idx + 1, item)

    semantic_rank_map: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    for idx, item in enumerate(semantic_results):
        key = _extract_canonical_key(item)
        if key not in semantic_rank_map:
            semantic_rank_map[key] = (idx + 1, item)

    all_keys = list(dict.fromkeys(list(lexical_rank_map.keys()) + list(semantic_rank_map.keys())))

    smooth_k = max(1, int(k))
    scored_candidates: List[Tuple[float, str, Dict[str, Any]]] = []

    for key in all_keys:
        lex_entry = lexical_rank_map.get(key)
        sem_entry = semantic_rank_map.get(key)

        rrf_score = 0.0
        lex_rank: Optional[int] = None
        sem_rank: Optional[int] = None
        lex_item: Dict[str, Any] = {}
        sem_item: Dict[str, Any] = {}

        if lex_entry:
            lex_rank, lex_item = lex_entry
            rrf_score += float(lexical_weight) / (smooth_k + lex_rank)

        if sem_entry:
            sem_rank, sem_item = sem_entry
            rrf_score += float(semantic_weight) / (smooth_k + sem_rank)

        # Tentukan sumber kandidat
        if lex_entry and sem_entry:
            source = "hybrid"
        elif lex_entry:
            source = "lexical"
        else:
            source = "semantic"

        # Gabungkan metadata secara kaya
        raw_path = sem_item.get("path") or lex_item.get("file") or lex_item.get("path") or ""
        path = str(raw_path).replace("\\", "/").strip().lstrip("./")

        kind = (
            sem_item.get("kind")
            or lex_item.get("kind")
            or "symbol"
        )
        if kind == "symbol" and lex_item.get("kind") in ("class", "function", "method"):
            kind = lex_item.get("kind")

        symbol = (
            sem_item.get("symbol")
            or lex_item.get("name")
            or ""
        )

        start_line = (
            sem_item.get("start_line")
            if sem_item.get("start_line") is not None
            else lex_item.get("line_start")
        )
        end_line = (
            sem_item.get("end_line")
            if sem_item.get("end_line") is not None
            else lex_item.get("line_end")
        )

        snippet = sem_item.get("snippet") or ""

        # Kumpulkan relasi struktural dari Code Atlas jika tersedia
        relations: Dict[str, Any] = {}
        for rel_key in ("callers", "callees", "inherits", "inherited_by", "imports", "methods"):
            if rel_key in lex_item:
                relations[rel_key] = lex_item[rel_key]

        candidate: Dict[str, Any] = {
            "path": path,
            "symbol": symbol,
            "kind": kind,
            "start_line": start_line,
            "end_line": end_line,
            "score": round(rrf_score, 6),
            "rrf_score": round(rrf_score, 6),
            "source": source,
            "lexical_rank": lex_rank,
            "semantic_rank": sem_rank,
        }
        if "score" in sem_item:
            candidate["semantic_similarity"] = sem_item["score"]
        if snippet:
            candidate["snippet"] = snippet
        if relations:
            candidate["relations"] = relations

        scored_candidates.append((rrf_score, key, candidate))

    # Urutkan secara deterministik
    scored_candidates.sort(
        key=lambda entry: (
            -entry[0],
            entry[2].get("lexical_rank") or 9999,
            entry[2].get("semantic_rank") or 9999,
            entry[1],
        )
    )

    limit = max(1, int(max_results))
    return [candidate for _, _, candidate in scored_candidates[:limit]]


__all__ = [
    "DEFAULT_RRF_K",
    "reciprocal_rank_fusion",
    "fuse_code_results",
]
