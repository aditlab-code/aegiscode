"""Comprehensive unit tests for CodeGraphService and canonical tools (PR-CG-2)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agent_ai.codegraph.service import CodeGraphService
from agent_ai.codegraph.store import CodeGraphStore
from agent_ai.consultant.tools import build_consultant_registry
from agent_ai.tools.codegraph import (
    CodeGraphFindCalleesTool,
    CodeGraphFindCallersTool,
    CodeGraphFindOrphansTool,
    CodeGraphFindReferencesTool,
    CodeGraphImpactAnalysisTool,
    CodeGraphTraceAPITool,
    build_codegraph_tools,
)
from agent_ai.providers.base import BaseProvider, GenerateOptions, GenerateResult
from agent_ai.runtime.runtime import AgentRuntime
from agent_ai.task.models import PreparedTask
from agent_ai.tools.registry import build_registry


@pytest.fixture
def sample_project(tmp_path: Path):
    """Create a temporary multi-file project with Python and JS/Vue sources."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    web_dir = tmp_path / "web"
    web_dir.mkdir(parents=True)

    # File 1: utils.py
    (src_dir / "utils.py").write_text(
        """def compute_hash(data: str) -> str:
    \"\"\"Compute SHA-256 hash.\"\"\"
    return f"hash_{data}"

def unused_orphan_helper():
    \"\"\"Orphan function.\"\"\"
    return 42
""",
        encoding="utf-8",
    )

    # File 2: service.py
    (src_dir / "service.py").write_text(
        """from src.utils import compute_hash

def process_transaction(user_id: str):
    \"\"\"Process user transaction.\"\"\"
    token = compute_hash(user_id)
    return token

def notify_user(user_id: str):
    \"\"\"Send notification.\"\"\"
    return True
""",
        encoding="utf-8",
    )

    # File 3: controller.py
    (src_dir / "controller.py").write_text(
        """from src.service import process_transaction

class MockRouter:
    def get(self, path):
        def dec(fn):
            return fn
        return dec

app = MockRouter()

@app.get("/api/transaction/{id}")
def handle_request(req):
    \"\"\"Handle API request.\"\"\"
    return process_transaction(req.user_id)
""",
        encoding="utf-8",
    )

    # File 4: frontend api.js
    (web_dir / "api.js").write_text(
        """export async function fetchTransaction(id) {
    const res = await fetch(`/api/transaction/${id}`);
    return res.json();
}
""",
        encoding="utf-8",
    )

    return tmp_path


def test_service_full_resync_and_queries(sample_project: Path):
    service = CodeGraphService(project_root=sample_project)
    try:
        # Full Resync
        res = service.full_resync()
        assert res["status"] == "ok"
        assert res["mode"] == "full_resync"
        assert res["files_indexed"] >= 4
        assert res["symbols_indexed"] > 0
        assert res["elapsed_ms"] < 2000.0

        # Query: find_symbol
        syms = service.find_symbol("compute_hash")
        assert len(syms) == 1
        assert syms[0]["name"] == "compute_hash"
        assert "src/utils.py" in syms[0]["file_path"]

        # Query: get_callers (process_transaction calls compute_hash)
        callers = service.get_callers("compute_hash", depth=1)
        assert any(c.get("caller_name") == "process_transaction" for c in callers)

        # Multi-hop callers: handle_request -> process_transaction -> compute_hash
        callers_depth2 = service.get_callers("compute_hash", depth=2)
        caller_names = [c.get("caller_name") for c in callers_depth2]
        assert "process_transaction" in caller_names
        assert "handle_request" in caller_names

        # Query: get_callees
        callees = service.get_callees("process_transaction", depth=1)
        assert any(c.get("callee_name") == "compute_hash" for c in callees)

        # Query: get_references
        refs = service.get_references("compute_hash")
        assert len(refs) >= 1

        # Query: get_related_files
        related = service.get_related_files("src/service.py")
        assert any("utils.py" in f for f in related)
        assert any("controller.py" in f for f in related)

        # Query: find_orphans
        orphans = service.find_orphans()
        orphan_names = [o["name"] for o in orphans]
        assert "unused_orphan_helper" in orphan_names

        # Query: impact_analysis
        impact = service.impact_analysis("compute_hash", depth=2)
        assert impact["affected_symbols_count"] >= 2
        assert any("service.py" in f for f in impact["affected_files"])
        assert any("controller.py" in f for f in impact["affected_files"])
    finally:
        service.close()


def test_service_incremental_sync_and_dirty_detection(sample_project: Path):
    service = CodeGraphService(project_root=sample_project)
    try:
        service.full_resync()

        # Incremental sync with no changes -> fast no-op (< 50ms)
        inc1 = service.incremental_sync()
        assert inc1["status"] == "ok"
        assert inc1["updated_files"] == 0

        # Modify a file
        new_file = sample_project / "src" / "new_module.py"
        new_file.write_text(
            """def new_awesome_feature():
    return 100
""",
            encoding="utf-8",
        )

        inc2 = service.incremental_sync()
        assert inc2["status"] == "ok"
        assert inc2["updated_files"] == 1

        syms = service.find_symbol("new_awesome_feature")
        assert len(syms) == 1

        # Delete file
        new_file.unlink()
        inc3 = service.incremental_sync()
        assert inc3["status"] == "ok"
        assert len(service.find_symbol("new_awesome_feature")) == 0

    finally:
        service.close()


def test_ensure_graph_fresh_guardrail(sample_project: Path):
    service = CodeGraphService(project_root=sample_project)
    try:
        service.full_resync()

        # Within max_stale_seconds: instant True
        fresh = service.ensure_graph_fresh(max_stale_seconds=5.0)
        assert fresh is True

        # Test scoped area
        fresh_area = service.ensure_graph_fresh(area="src", max_stale_seconds=0.0)
        assert fresh_area is True
    finally:
        service.close()


def test_canonical_tools_execution_and_token_compression(sample_project: Path):
    service = CodeGraphService(project_root=sample_project)
    try:
        service.full_resync()
        tools = build_codegraph_tools(sample_project, service=service)
        assert len(tools) == 6

        tool_map = {t.name: t for t in tools}
        assert "codegraph_find_callers" in tool_map
        assert "codegraph_find_callees" in tool_map
        assert "codegraph_find_references" in tool_map
        assert "codegraph_impact_analysis" in tool_map
        assert "codegraph_trace_api" in tool_map
        assert "codegraph_find_orphans" in tool_map

        # Test callers tool
        res_callers = tool_map["codegraph_find_callers"].execute(symbol="compute_hash", depth=2)
        assert res_callers["caller_count"] >= 2
        # Verify compact JSON < 500 tokens (~2000 chars)
        assert len(json.dumps(res_callers)) < 2000

        # Test callees tool
        res_callees = tool_map["codegraph_find_callees"].execute(symbol="process_transaction", depth=1)
        assert res_callees["callee_count"] >= 1
        assert len(json.dumps(res_callees)) < 2000

        # Test references tool
        res_refs = tool_map["codegraph_find_references"].execute(symbol="compute_hash")
        assert res_refs["reference_count"] >= 1
        assert len(json.dumps(res_refs)) < 2000

        # Test impact tool
        res_impact = tool_map["codegraph_impact_analysis"].execute(target="compute_hash", depth=2)
        assert res_impact["affected_symbols_count"] >= 2
        assert len(json.dumps(res_impact)) < 2000

        # Test trace API tool (frontend API call -> backend route endpoint)
        res_trace = tool_map["codegraph_trace_api"].execute(component_or_endpoint="/api/transaction")
        assert res_trace["query"] == "/api/transaction"
        assert res_trace["trace_count"] >= 1
        assert len(json.dumps(res_trace)) < 2000

        # Test find orphans tool (dead code detection)
        res_orphans = tool_map["codegraph_find_orphans"].execute(limit=10)
        assert res_orphans["orphan_count"] >= 1
        orphan_names = [o["name"] for o in res_orphans["orphans"]]
        assert "unused_orphan_helper" in orphan_names
        assert len(json.dumps(res_orphans)) < 2000
    finally:
        service.close()


def test_registry_integration(sample_project: Path):
    reg = build_registry(root=sample_project)
    # Check that all 6 tools are registered
    assert reg.get("codegraph_find_callers") is not None
    assert reg.get("codegraph_find_callees") is not None
    assert reg.get("codegraph_find_references") is not None
    assert reg.get("codegraph_impact_analysis") is not None
    assert reg.get("codegraph_trace_api") is not None
    assert reg.get("codegraph_find_orphans") is not None

    # Check consultant registry
    c_reg = build_consultant_registry(root=sample_project)
    assert c_reg.get("codegraph_find_callers") is not None
    assert c_reg.get("codegraph_find_callees") is not None
    assert c_reg.get("codegraph_find_references") is not None
    assert c_reg.get("codegraph_impact_analysis") is not None
    assert c_reg.get("codegraph_trace_api") is not None
    assert c_reg.get("codegraph_find_orphans") is not None


class _MockScriptedProvider(BaseProvider):
    """Simple dummy provider to test AgentRuntime initialization and guardrails."""

    name: str = "mock"

    def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[Any] = None,
        options: Optional[GenerateOptions] = None,
        tools: Optional[Any] = None,
        tool_choice: Optional[Any] = None,
    ) -> GenerateResult:
        return GenerateResult(text="Done", tool_calls=[])

def test_agent_runtime_codegraph_freshness_guardrail(sample_project: Path):
    """Verify that AgentRuntime automatically runs ensure_graph_fresh guardrail."""
    provider = _MockScriptedProvider()
    runtime = AgentRuntime(
        provider=provider,
        project_root=str(sample_project),
    )

    task = PreparedTask(task="Inspect repository architecture")
    result = runtime.run(task)

    assert result is not None
    assert runtime.codegraph_service is not None
    stats = runtime.codegraph_service.store.get_stats()
    assert stats["symbol_count"] > 0
    assert stats["file_count"] >= 4
    runtime.codegraph_service.close()
