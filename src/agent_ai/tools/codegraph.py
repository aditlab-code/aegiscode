"""Canonical CodeGraph relational intelligence tools (Fase 2.5).

Provides 6 lightweight, deterministic structural navigation tools:
- codegraph_find_callers
- codegraph_find_callees
- codegraph_find_references
- codegraph_impact_analysis
- codegraph_trace_api
- codegraph_find_orphans
All tool outputs are compressed to < 500 tokens to preserve the < 4,000 token split-brain budget.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_ai.codegraph.service import CodeGraphService
from agent_ai.tools.base import BaseTool


def _format_compact_callers(symbol: str, callers: List[Dict[str, Any]], depth: int) -> Dict[str, Any]:
    """Format callers result compactly to ensure < 500 tokens output."""
    items = []
    for c in callers[:20]:  # limit to top 20 to strictly respect token budget
        items.append({
            "caller": c.get("caller_name") or c.get("source_id"),
            "file": c.get("caller_file") or c.get("file_path"),
            "line": c.get("line_number"),
            "depth": c.get("depth"),
        })
    return {
        "target": symbol,
        "depth": depth,
        "caller_count": len(callers),
        "callers": items,
    }


def _format_compact_callees(symbol: str, callees: List[Dict[str, Any]], depth: int) -> Dict[str, Any]:
    """Format callees result compactly to ensure < 500 tokens output."""
    items = []
    for c in callees[:20]:
        items.append({
            "callee": c.get("callee_name") or c.get("target_name"),
            "file": c.get("callee_file") or c.get("file_path"),
            "line": c.get("line_number"),
            "depth": c.get("depth"),
        })
    return {
        "target": symbol,
        "depth": depth,
        "callee_count": len(callees),
        "callees": items,
    }


def _format_compact_references(symbol: str, refs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Format references result compactly to ensure < 500 tokens output."""
    items = []
    for r in refs[:25]:
        items.append({
            "source": r.get("source_name") or r.get("source_id"),
            "relation": r.get("relation_type"),
            "file": r.get("file_path"),
            "line": r.get("line_number"),
        })
    return {
        "target": symbol,
        "reference_count": len(refs),
        "references": items,
    }


def _format_compact_impact(report: Dict[str, Any]) -> Dict[str, Any]:
    """Format blast radius impact report compactly."""
    chain = report.get("impact_chain", [])
    items = []
    for step in chain[:20]:
        items.append({
            "symbol": step.get("symbol_name"),
            "file": step.get("file_path"),
            "relation": step.get("relation_type"),
            "depth": step.get("depth"),
        })
    return {
        "target": report.get("target"),
        "max_depth": report.get("max_depth"),
        "affected_symbols_count": report.get("affected_symbols_count"),
        "affected_files": report.get("affected_files", [])[:10],
        "impact_chain": items,
    }


def _format_compact_trace_api(query: str, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Format frontend to backend API trace compactly to ensure < 500 tokens output."""
    items = []
    for t in traces[:25]:
        items.append({
            "source": t.get("source_name") or t.get("source_id"),
            "relation": t.get("relation_type"),
            "target": t.get("target_name"),
            "file": t.get("file_path"),
            "line": t.get("line_number"),
        })
    return {
        "query": query,
        "trace_count": len(traces),
        "traces": items,
    }


def _format_compact_orphans(orphans: List[Dict[str, Any]], limit: int = 25) -> Dict[str, Any]:
    """Format dead code orphan symbols compactly to ensure < 500 tokens output."""
    items = []
    for o in orphans[:limit]:
        items.append({
            "name": o.get("name"),
            "type": o.get("type"),
            "file": o.get("file_path"),
            "line": o.get("start_line"),
        })
    return {
        "orphan_count": len(orphans),
        "orphans": items,
    }


class CodeGraphFindCallersTool(BaseTool):
    """Tool to locate functions, methods, or components calling the target symbol."""

    name: str = "codegraph_find_callers"
    description: str = (
        "Find callers that invoke or call the target symbol across the repository. "
        "Useful for understanding who depends on a function or endpoint."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Target symbol name or canonical ID to find callers for.",
            },
            "depth": {
                "type": "integer",
                "description": "Call graph traversal depth (default 1, max 3).",
                "default": 1,
            },
        },
        "required": ["symbol"],
    }

    def __init__(self, service: CodeGraphService) -> None:
        self.service = service

    def execute(self, **arguments: Any) -> Any:
        symbol = str(arguments.get("symbol", "")).strip()
        if not symbol:
            return {"error": "Parameter 'symbol' is required"}
        depth = min(max(int(arguments.get("depth", 1)), 1), 3)

        self.service.ensure_graph_fresh()
        callers = self.service.get_callers(symbol, depth=depth)
        return _format_compact_callers(symbol, callers, depth)


class CodeGraphFindCalleesTool(BaseTool):
    """Tool to locate symbols or functions called inside the target symbol body."""

    name: str = "codegraph_find_callees"
    description: str = (
        "Find symbols or functions invoked by the target symbol. "
        "Useful for analyzing downstream calls and implementation dependencies."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Target symbol name or canonical ID.",
            },
            "depth": {
                "type": "integer",
                "description": "Call graph traversal depth (default 1, max 3).",
                "default": 1,
            },
        },
        "required": ["symbol"],
    }

    def __init__(self, service: CodeGraphService) -> None:
        self.service = service

    def execute(self, **arguments: Any) -> Any:
        symbol = str(arguments.get("symbol", "")).strip()
        if not symbol:
            return {"error": "Parameter 'symbol' is required"}
        depth = min(max(int(arguments.get("depth", 1)), 1), 3)

        self.service.ensure_graph_fresh()
        callees = self.service.get_callees(symbol, depth=depth)
        return _format_compact_callees(symbol, callees, depth)


class CodeGraphFindReferencesTool(BaseTool):
    """Tool to locate all references, usages, and imports of a symbol."""

    name: str = "codegraph_find_references"
    description: str = (
        "Locate all references, usages, and imports of a symbol across codebase. "
        "Useful before refactoring or renaming symbols."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Target symbol name to find references for.",
            },
        },
        "required": ["symbol"],
    }

    def __init__(self, service: CodeGraphService) -> None:
        self.service = service

    def execute(self, **arguments: Any) -> Any:
        symbol = str(arguments.get("symbol", "")).strip()
        if not symbol:
            return {"error": "Parameter 'symbol' is required"}

        self.service.ensure_graph_fresh()
        refs = self.service.get_references(symbol)
        return _format_compact_references(symbol, refs)


class CodeGraphImpactAnalysisTool(BaseTool):
    """Tool to compute structural blast radius before editing code."""

    name: str = "codegraph_impact_analysis"
    description: str = (
        "Perform blast radius impact analysis on a symbol or file before making code modifications. "
        "Returns affected symbols and affected files across multiple traversal hops."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Target symbol name, canonical ID, or relative file path.",
            },
            "depth": {
                "type": "integer",
                "description": "Impact graph traversal depth (default 2, max 3).",
                "default": 2,
            },
        },
        "required": ["target"],
    }

    def __init__(self, service: CodeGraphService) -> None:
        self.service = service

    def execute(self, **arguments: Any) -> Any:
        target = str(arguments.get("target", "")).strip()
        if not target:
            return {"error": "Parameter 'target' is required"}
        depth = min(max(int(arguments.get("depth", 2)), 1), 3)

        self.service.ensure_graph_fresh()
        report = self.service.impact_analysis(target, depth=depth)
        return _format_compact_impact(report)



class CodeGraphTraceAPITool(BaseTool):
    """Tool to trace relations between frontend API calls and backend route definitions."""

    name: str = "codegraph_trace_api"
    description: str = (
        "Trace fullstack relations between frontend API calls (fetch/axios) and backend route endpoints. "
        "Useful for understanding how frontend components communicate with backend APIs."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "component_or_endpoint": {
                "type": "string",
                "description": "Frontend component name, API endpoint path (e.g. /api/users), or method name.",
            },
        },
        "required": ["component_or_endpoint"],
    }

    def __init__(self, service: CodeGraphService) -> None:
        self.service = service

    def execute(self, **arguments: Any) -> Any:
        target = str(arguments.get("component_or_endpoint", "")).strip()
        if not target:
            return {"error": "Parameter 'component_or_endpoint' is required"}

        self.service.ensure_graph_fresh()
        traces = self.service.trace_frontend_to_backend(target)
        return _format_compact_trace_api(target, traces)


class CodeGraphFindOrphansTool(BaseTool):
    """Tool to detect dead code or unreferenced symbols across the repository."""

    name: str = "codegraph_find_orphans"
    description: str = (
        "Find orphaned code symbols (functions, classes, methods) defined in the codebase "
        "but never called or referenced anywhere. Useful for dead code elimination and cleanup."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of orphan symbols to return (default 25, max 50).",
                "default": 25,
            },
        },
    }

    def __init__(self, service: CodeGraphService) -> None:
        self.service = service

    def execute(self, **arguments: Any) -> Any:
        limit = min(max(int(arguments.get("limit", 25)), 1), 50)
        self.service.ensure_graph_fresh()
        orphans = self.service.find_orphans()
        return _format_compact_orphans(orphans, limit=limit)

def build_codegraph_tools(
    root: Optional[Union[str, Path]] = None,
    service: Optional[CodeGraphService] = None,
) -> List[BaseTool]:
    """Construct all 6 canonical CodeGraph tools using a shared CodeGraphService instance."""
    svc = service if service is not None else CodeGraphService(project_root=root)
    return [
        CodeGraphFindCallersTool(svc),
        CodeGraphFindCalleesTool(svc),
        CodeGraphFindReferencesTool(svc),
        CodeGraphImpactAnalysisTool(svc),
        CodeGraphTraceAPITool(svc),
        CodeGraphFindOrphansTool(svc),
    ]



__all__ = [
    "CodeGraphFindCallersTool",
    "CodeGraphFindCalleesTool",
    "CodeGraphFindReferencesTool",
    "CodeGraphImpactAnalysisTool",
    "CodeGraphTraceAPITool",
    "CodeGraphFindOrphansTool",
    "build_codegraph_tools",
]
