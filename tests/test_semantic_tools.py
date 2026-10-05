"""Unit tests untuk semantic tools (SemanticSearchTool, RefreshSemanticIndexTool)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_ai.repointel.semantic.indexer import IndexStats
from agent_ai.tools.base import ToolValidationError
from agent_ai.tools.semantic import (
    RefreshSemanticIndexTool,
    SemanticSearchTool,
    build_semantic_tools,
)


def test_semantic_search_tool_schema():
    tool = SemanticSearchTool()
    assert tool.name == "semantic_search"
    schema = tool.input_schema
    assert schema["type"] == "object"
    assert "query" in schema["properties"]
    assert "k" in schema["properties"]
    assert "path_prefix" in schema["properties"]
    assert "query" in schema["required"]


def test_refresh_semantic_index_tool_schema():
    tool = RefreshSemanticIndexTool()
    assert tool.name == "refresh_semantic_index"
    schema = tool.input_schema
    assert schema["type"] == "object"
    assert "full" in schema["properties"]


def test_semantic_search_tool_validation(monkeypatch):
    monkeypatch.setattr("agent_ai.tools.semantic.is_available", lambda: (True, ""))
    tool = SemanticSearchTool(root=Path("/fake/root"))
    # Kosong -> ToolValidationError
    with pytest.raises(ToolValidationError):
        tool.execute(query="")

    with pytest.raises(ToolValidationError):
        tool.execute(query="   ")



def test_semantic_tools_unavailable_when_missing_deps(monkeypatch):
    monkeypatch.setattr(
        "agent_ai.tools.semantic.is_available",
        lambda: (False, "fastembed not found"),
    )
    search_tool = SemanticSearchTool(root=Path("/fake/root"))
    res = search_tool.execute(query="find something")
    assert res["status"] == "unavailable"
    assert "fastembed not found" in res["reason"]

    refresh_tool = RefreshSemanticIndexTool(root=Path("/fake/root"))
    r_res = refresh_tool.execute(full=True)
    assert r_res["status"] == "unavailable"


def test_semantic_search_tool_execution(monkeypatch):
    monkeypatch.setattr("agent_ai.tools.semantic.is_available", lambda: (True, ""))

    mock_service = MagicMock()
    mock_service.search.return_value = [
        {
            "path": "auth.py",
            "symbol": "login",
            "kind": "function",
            "start_line": 1,
            "end_line": 5,
            "score": 0.95,
            "snippet": "def login(): pass",
        }
    ]
    mock_service.status.return_value = {"backend": "bruteforce"}

    tool = SemanticSearchTool(root=Path("/fake/root"), service=mock_service)
    result = tool.execute(query="login function", k=5, path_prefix="auth")

    assert result["status"] == "ok"
    assert result["total_results"] == 1
    assert result["backend"] == "bruteforce"
    assert len(result["results"]) == 1
    mock_service.search.assert_called_once_with(
        query="login function", k=5, path_prefix="auth"
    )


def test_refresh_semantic_index_tool_execution(monkeypatch):
    monkeypatch.setattr("agent_ai.tools.semantic.is_available", lambda: (True, ""))

    mock_service = MagicMock()
    mock_stats = IndexStats(
        scanned=10,
        indexed=2,
        skipped=8,
        removed=0,
        total_chunks=25,
        backend="sqlite-vec",
        elapsed_sec=0.15,
    )
    mock_service.refresh.return_value = mock_stats

    tool = RefreshSemanticIndexTool(root=Path("/fake/root"), service=mock_service)
    result = tool.execute(full=True)

    assert result["status"] == "ok"
    assert result["full"] is True
    assert result["stats"]["scanned"] == 10
    assert result["stats"]["indexed"] == 2
    mock_service.refresh.assert_called_once_with(full=True)


def test_build_semantic_tools_agent_vs_consultant():
    agent_tools = build_semantic_tools(
        root=Path("/fake/root"), include_refresh=True, read_only=False
    )
    assert len(agent_tools) == 2
    names = [t.name for t in agent_tools]
    assert "semantic_search" in names
    assert "refresh_semantic_index" in names

    consultant_tools = build_semantic_tools(
        root=Path("/fake/root"), include_refresh=False, read_only=True
    )
    assert len(consultant_tools) == 1
    assert consultant_tools[0].name == "semantic_search"
    assert consultant_tools[0].read_only is True
