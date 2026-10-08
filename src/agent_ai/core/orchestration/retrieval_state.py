"""Pelacakan state retrieval dan sinkronisasi ToolReadCache (Fase 2 PR-MVP-3).

Modul ini bertanggung jawab untuk:
- Mengekstrak identitas retrieval (`read_file`, `search_code`) untuk observability repeat detection.
- Mengekstrak rentang baris (`read_result_span`) dan key pencarian (`search_result_key`).
- Menyelaraskan status ketersediaan pada `ToolReadCache` dengan pesan yang benar-benar
  masuk ke dalam konteks LLM setelah context compaction.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from agent_ai.core.history import ConversationHistory


def retrieval_identity(
    tool_name: str, arguments: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Identitas satu retrieval untuk deteksi repeat (OBSERVABILITY SAJA).

    Hanya tool retrieval yang diamati (`read_file`, `search_code`); tool lain
    mengembalikan None. Murni untuk emit event observasi repeat.
    """
    if tool_name == "read_file":
        path = arguments.get("path")
        if not path:
            return None
        symbol = arguments.get("symbol")
        start = arguments.get("start_line")
        end = arguments.get("end_line")
        if symbol:
            rng = str(symbol)
        elif start is None and end is None:
            rng = "full"
        else:
            rng = "{}-{}".format(
                "start" if start is None else start,
                "end" if end is None else end,
            )
        return {
            "path": str(path),
            "range": rng,
            "mode": str(arguments.get("mode") or "default"),
            "force": bool(arguments.get("force", False)),
        }
    if tool_name == "search_code":
        query = arguments.get("query")
        if query is None:
            return None
        return {
            "path": str(arguments.get("path") or "."),
            "range": str(query),
            "mode": "search",
            "force": False,
        }
    return None


def read_result_span(content: Optional[str]) -> Optional[Tuple[str, int, int]]:
    """Ekstrak (path, start, end) dari hasil read_file yang MEMUAT isi."""
    if not content:
        return None
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "content" not in data:
        return None
    path = data.get("path")
    if not path:
        return None
    total = data.get("total_lines")
    start = data.get("start_line")
    end = data.get("end_line")
    if start is None and end is None:
        if isinstance(total, int) and total > 0:
            start, end = 1, total
        else:
            return None
    else:
        start = 1 if start is None else int(start)
        if end is None:
            if isinstance(total, int) and total > 0:
                end = total
            else:
                return None
        else:
            end = int(end)
    if start < 1 or end < start:
        return None
    return (str(path), start, end)


def search_result_key(content: Optional[str]) -> Optional[Tuple[str, str, int]]:
    """Ekstrak (query, path, context_lines) dari hasil search_code berisi."""
    if not content:
        return None
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "matches" not in data:
        return None
    query = data.get("query")
    if query is None:
        return None
    path = data.get("path") or "."
    try:
        context_lines = int(data.get("context_lines", 0) or 0)
    except (TypeError, ValueError):
        context_lines = 0
    return (str(query), str(path), context_lines)


def sync_retrieval_cache(
    executor: Any,
    history: ConversationHistory,
    compiled: List[Any],
    stats: Optional[Dict[str, int]] = None,
) -> None:
    """Selaraskan cache retrieval dengan pesan yang BENAR-BENAR dikirim.

    Bila context compaction membuang detail hasil read_file/search_code dari
    konteks yang dikirim ke LLM, cache dedup HARUS berhenti mengklaim sumber
    itu 'sudah tersedia'.
    """
    registry = getattr(executor, "registry", None) if executor is not None else None
    cache = getattr(registry, "read_cache", None)
    if cache is None:
        return
    if stats is not None:
        stats["context_spans_visible"] = 0
        stats["context_spans_hidden"] = 0
        stats["context_paths_visible"] = 0
        stats["context_paths_hidden"] = 0

    originals = {
        message.tool_call_id: message.content
        for message in history.messages
        if message.role == "tool" and message.tool_call_id
    }
    present_ids = {
        message.tool_call_id
        for message in compiled
        if getattr(message, "role", None) == "tool" and message.tool_call_id
    }
    compacted_ids: Set[str] = set()
    for message in compiled:
        if getattr(message, "role", None) != "tool" or not message.tool_call_id:
            continue
        before = originals.get(message.tool_call_id)
        if before is None:
            continue
        if (message.content or "") != (before or ""):
            compacted_ids.add(message.tool_call_id)

    available: Dict[str, List[Tuple[int, int]]] = {}
    seen_paths: Set[str] = set()
    for message in history.messages:
        if message.role != "tool" or (message.name or "") != "read_file":
            continue
        span = read_result_span(message.content)
        if span is None:
            continue
        path, start, end = span
        seen_paths.add(path)
        visible = (
            message.tool_call_id in present_ids
            and message.tool_call_id not in compacted_ids
        )
        if visible:
            available.setdefault(path, []).append((start, end))
            if stats is not None:
                stats["context_spans_visible"] += 1
        elif stats is not None:
            stats["context_spans_hidden"] += 1

    if stats is not None:
        stats["context_paths_visible"] = len(available)
        stats["context_paths_hidden"] = len(
            {p for p in seen_paths if p not in available}
        )
    cache.sync_from_context(available, seen_paths)

    latest_search_gone: Dict[Tuple[str, str, int], bool] = {}
    for message in history.messages:
        if message.role != "tool" or (message.name or "") != "search_code":
            continue
        key = search_result_key(message.content)
        if key is None:
            continue
        visible = (
            message.tool_call_id in present_ids
            and message.tool_call_id not in compacted_ids
        )
        latest_search_gone[key] = not visible

    for (query, path, context_lines), gone in latest_search_gone.items():
        if gone:
            cache.forget_search(query, path, context_lines)


class RetrievalStateManager:
    """Manager untuk memantau state retrieval pada orchestrator."""

    def __init__(self, orchestrator: Any = None) -> None:
        self.orchestrator = orchestrator

    def retrieval_identity(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return retrieval_identity(tool_name, arguments)

    def read_result_span(
        self, content: Optional[str]
    ) -> Optional[Tuple[str, int, int]]:
        return read_result_span(content)

    def search_result_key(
        self, content: Optional[str]
    ) -> Optional[Tuple[str, str, int]]:
        return search_result_key(content)

    def sync_retrieval_cache(
        self,
        history: ConversationHistory,
        compiled: List[Any],
        stats: Optional[Dict[str, int]] = None,
    ) -> None:
        executor = (
            getattr(self.orchestrator, "executor", None)
            if self.orchestrator is not None
            else None
        )
        sync_retrieval_cache(executor, history, compiled, stats=stats)


__all__ = [
    "RetrievalStateManager",
    "read_result_span",
    "retrieval_identity",
    "search_result_key",
    "sync_retrieval_cache",
]
