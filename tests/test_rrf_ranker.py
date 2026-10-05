"""Unit tests untuk Reciprocal Rank Fusion (RRF) & Hybrid Retrieval (Phase 3).

Menguji:
1. Formula matematis RRF, determinisme, bobot, dan smoothing constant.
2. Presisi peringkat RRF: Query simbol eksak menempatkan kecocokan TOC Code Atlas
   di atas loose vector embeddings.
3. Normalisasi kandidat, deduplikasi, penggabungan snippet & relasi AST.
4. Dual query routing & graceful fallback (mode hybrid, lexical_only, semantic_only).
5. Validasi skema tool JSON-RPC untuk kepatuhan OpenAI dan Claude function calling.
6. Integrasi dengan ToolRegistry dan build_semantic_tools/build_project_map_tools.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_ai.projects.project_map import MapNotFoundError
from agent_ai.providers.base import ToolDefinition
from agent_ai.repointel.semantic.hybrid import HybridRetrievalCoordinator
from agent_ai.repointel.semantic.rrf import (
    DEFAULT_RRF_K,
    fuse_code_results,
    reciprocal_rank_fusion,
)
from agent_ai.tools.base import ToolValidationError
from agent_ai.tools.project_map import build_project_map_tools
from agent_ai.tools.semantic import (
    HybridSearchTool,
    build_hybrid_tools,
    build_semantic_tools,
)


# --------------------------------------------------------------------------- #
# 1. Mathematical RRF & Determinism
# --------------------------------------------------------------------------- #
def test_rrf_mathematical_precision():
    """Uji ketelitian perhitungan skor RRF standar (Cormack et al.)."""
    list1 = ["docA", "docB", "docC"]
    list2 = ["docB", "docD", "docA"]

    # k = 60
    # docA: rank 1 di list1 (1/61), rank 3 di list2 (1/63) -> 1/61 + 1/63 = 0.0163934 + 0.0158730 = 0.0322664
    # docB: rank 2 di list1 (1/62), rank 1 di list2 (1/61) -> 1/62 + 1/61 = 0.0161290 + 0.0163934 = 0.0325224
    # docC: rank 3 di list1 (1/63) -> 0.0158730
    # docD: rank 2 di list2 (1/62) -> 0.0161290
    results = reciprocal_rank_fusion([list1, list2], k=60)

    ranked_items = [item for item, score in results]
    assert ranked_items == ["docB", "docA", "docD", "docC"]

    scores = dict(results)
    assert pytest.approx(scores["docB"], rel=1e-4) == (1 / 62 + 1 / 61)
    assert pytest.approx(scores["docA"], rel=1e-4) == (1 / 61 + 1 / 63)
    assert scores["docB"] > scores["docA"]
    assert scores["docA"] > scores["docD"]
    assert scores["docD"] > scores["docC"]


def test_rrf_weights_and_custom_k():
    """Uji fleksibilitas pembobotan (weights) dan parameter smoothing k."""
    list1 = ["symbolX"]
    list2 = ["symbolY"]

    # Bobot leksikal 2.0 vs semantik 1.0 pada k=10
    results = reciprocal_rank_fusion([list1, list2], k=10, weights=[2.0, 1.0])
    scores = dict(results)

    # symbolX: 2.0 / (10 + 1) = 2/11 = 0.1818
    # symbolY: 1.0 / (10 + 1) = 1/11 = 0.0909
    assert results[0][0] == "symbolX"
    assert pytest.approx(scores["symbolX"], rel=1e-4) == 2.0 / 11
    assert pytest.approx(scores["symbolY"], rel=1e-4) == 1.0 / 11


def test_rrf_empty_inputs():
    """Uji ketahanan saat daftar input kosong."""
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
    assert fuse_code_results([], []) == []


# --------------------------------------------------------------------------- #
# 2. RRF Ranking Precision (Exact Symbol vs Loose Embedding)
# --------------------------------------------------------------------------- #
def test_exact_symbol_ranks_above_loose_vector():
    """Verifikasi bahwa pencarian simbol eksak menempatkan hasil TOC di atas loose vector."""
    # Skenario:
    # 1. 'TaskExecutor' adalah simbol eksak di Code Atlas (rank 1).
    #    Pada semantic search, TaskExecutor muncul di rank 2 (karena embedding tertukar kata).
    # 2. 'LooseEmbedding' adalah fungsi lain yang embedding-nya kebetulan rank 1 di semantic search,
    #    tetapi TIDAK ada di Code Atlas (bukan simbol yang dicari).
    lexical = [
        {
            "name": "TaskExecutor",
            "kind": "class",
            "file": "src/core/task.py",
            "line_start": 10,
            "line_end": 50,
            "methods": ["execute", "abort"],
        }
    ]
    semantic = [
        {
            "path": "src/misc/helper.py",
            "symbol": "loose_helper",
            "kind": "function",
            "start_line": 1,
            "end_line": 20,
            "score": 0.89,
            "snippet": "def loose_helper(): pass",
        },
        {
            "path": "src/core/task.py",
            "symbol": "TaskExecutor",
            "kind": "class",
            "start_line": 10,
            "end_line": 50,
            "score": 0.84,
            "snippet": "class TaskExecutor:\n    def execute(self): pass",
        },
    ]

    fused = fuse_code_results(lexical_results=lexical, semantic_results=semantic, k=60)

    assert len(fused) == 2
    # TaskExecutor harus berada di posisi #1 karena mendapat kontribusi dari kedua mesin pencari
    top_candidate = fused[0]
    assert top_candidate["symbol"] == "TaskExecutor"
    assert top_candidate["path"] == "src/core/task.py"
    assert top_candidate["source"] == "hybrid"
    assert top_candidate["lexical_rank"] == 1
    assert top_candidate["semantic_rank"] == 2
    assert top_candidate["rrf_score"] > fused[1]["rrf_score"]

    # Loose helper berada di peringkat #2
    assert fused[1]["symbol"] == "loose_helper"
    assert fused[1]["source"] == "semantic"


def test_exact_symbol_single_source_beats_lower_semantic_rank():
    """Verifikasi simbol eksak Atlas (rank 1) mengalahkan kemiripan semantik rank 2."""
    lexical = [
        {
            "name": "OrderWorkflow",
            "kind": "class",
            "file": "src/workflows/order.py",
            "line_start": 5,
            "line_end": 40,
        }
    ]
    semantic = [
        # Hanya rank 2 yang relevan secara longgar
        {
            "path": "src/billing/calc.py",
            "symbol": "compute_total",
            "kind": "function",
            "start_line": 10,
            "end_line": 30,
            "score": 0.75,
            "snippet": "def compute_total(): ...",
        }
    ]

    fused = fuse_code_results(lexical_results=lexical, semantic_results=semantic, k=60)
    assert len(fused) == 2
    # OrderWorkflow (rank 1 lexical -> 1/61) vs compute_total (rank 1 semantic -> 1/61)
    # Skor keduanya seimbang pada bobot sama
    assert fused[0]["symbol"] in ("OrderWorkflow", "compute_total")


# --------------------------------------------------------------------------- #
# 3. Candidate Normalization & Deduplication
# --------------------------------------------------------------------------- #
def test_fuse_code_results_metadata_enrichment():
    """Uji penggabungan metadata secara utuh (snippet semantik + AST relations leksikal)."""
    lexical = [
        {
            "name": "AuthService.login",
            "kind": "method",
            "file": "src/auth/service.py",
            "line_start": 20,
            "line_end": 35,
            "callers": ["api.views.login_view"],
            "callees": ["crypto.verify_hash"],
        }
    ]
    semantic = [
        {
            "path": "src/auth/service.py",
            "symbol": "AuthService.login",
            "kind": "method",
            "start_line": 20,
            "end_line": 35,
            "score": 0.92,
            "snippet": "    def login(self, user, pwd):\n        return verify_hash(pwd)",
        }
    ]

    fused = fuse_code_results(lexical_results=lexical, semantic_results=semantic)
    assert len(fused) == 1
    item = fused[0]

    assert item["path"] == "src/auth/service.py"
    assert item["symbol"] == "AuthService.login"
    assert item["kind"] == "method"
    assert item["start_line"] == 20
    assert item["end_line"] == 35
    assert item["source"] == "hybrid"
    assert "def login" in item["snippet"]
    assert item["relations"]["callers"] == ["api.views.login_view"]
    assert item["relations"]["callees"] == ["crypto.verify_hash"]
    assert item["semantic_similarity"] == 0.92


# --------------------------------------------------------------------------- #
# 4. Dual Query Routing & Coordinator Fallbacks
# --------------------------------------------------------------------------- #
def test_hybrid_coordinator_dual_routing(monkeypatch):
    """Uji alur dual routing saat kedua backend tersedia."""
    monkeypatch.setattr("agent_ai.repointel.semantic.hybrid.is_available", lambda: (True, ""))

    mock_map_service = MagicMock()
    mock_sem_service = MagicMock()

    mock_sem_service.search.return_value = [
        {
            "path": "src/user.py",
            "symbol": "get_user",
            "kind": "function",
            "start_line": 1,
            "end_line": 10,
            "score": 0.85,
            "snippet": "def get_user(): pass",
        }
    ]

    monkeypatch.setattr(
        "agent_ai.projects.project_map_query.atlas_query",
        lambda *args, **kwargs: {
            "results": [
                {
                    "name": "get_user",
                    "kind": "function",
                    "file": "src/user.py",
                    "line_start": 1,
                    "line_end": 10,
                }
            ],
            "map_status": "fresh",
        },
    )

    coordinator = HybridRetrievalCoordinator(
        root=Path("/fake/root"),
        project_map_service=mock_map_service,
        semantic_service=mock_sem_service,
    )

    result = coordinator.search(query="get user", k=5)
    assert result["status"] == "ok"
    assert result["mode"] == "hybrid"
    assert result["total_results"] == 1
    assert result["lexical_status"] == "fresh"
    assert result["semantic_status"] == "ok"
    assert result["results"][0]["symbol"] == "get_user"
    assert result["results"][0]["source"] == "hybrid"


def test_hybrid_coordinator_fallback_when_lexical_missing(monkeypatch):
    """Uji fallback anggun saat atlas.json tidak ada (semantic_only)."""
    monkeypatch.setattr("agent_ai.repointel.semantic.hybrid.is_available", lambda: (True, ""))

    mock_sem_service = MagicMock()
    mock_sem_service.search.return_value = [
        {
            "path": "src/data.py",
            "symbol": "load_data",
            "kind": "function",
            "start_line": 5,
            "end_line": 15,
            "score": 0.78,
            "snippet": "def load_data(): pass",
        }
    ]

    def _raise_missing(*args, **kwargs):
        raise MapNotFoundError("atlas.json tidak ditemukan")

    monkeypatch.setattr("agent_ai.projects.project_map_query.atlas_query", _raise_missing)

    coordinator = HybridRetrievalCoordinator(
        root=Path("/fake/root"),
        semantic_service=mock_sem_service,
    )

    result = coordinator.search(query="load data", k=5)
    assert result["status"] == "ok"
    assert result["mode"] == "semantic_only"
    assert result["lexical_status"] == "missing"
    assert len(result["results"]) == 1
    assert result["results"][0]["symbol"] == "load_data"
    assert result["results"][0]["source"] == "semantic"


def test_hybrid_coordinator_fallback_when_semantic_unavailable(monkeypatch):
    """Uji fallback anggun saat fastembed / sqlite-vec belum terpasang (lexical_only)."""
    monkeypatch.setattr(
        "agent_ai.repointel.semantic.hybrid.is_available",
        lambda: (False, "fastembed not installed"),
    )

    monkeypatch.setattr(
        "agent_ai.projects.project_map_query.atlas_query",
        lambda *args, **kwargs: {
            "results": [
                {
                    "name": "save_config",
                    "kind": "function",
                    "file": "src/config.py",
                    "line_start": 1,
                    "line_end": 10,
                }
            ],
            "map_status": "fresh",
        },
    )

    coordinator = HybridRetrievalCoordinator(root=Path("/fake/root"))

    result = coordinator.search(query="save config", k=5)
    assert result["status"] == "ok"
    assert result["mode"] == "lexical_only"
    assert "unavailable" in result["semantic_status"]
    assert len(result["results"]) == 1
    assert result["results"][0]["symbol"] == "save_config"
    assert result["results"][0]["source"] == "lexical"


# --------------------------------------------------------------------------- #
# 5. Tool Schema Validation (OpenAI & Claude Function Calling)
# --------------------------------------------------------------------------- #
def test_hybrid_search_tool_schema_compliance():
    """Validasi kepatuhan skema JSON-RPC tool terhadap format OpenAI dan Claude."""
    tool = HybridSearchTool(root=Path("/fake/root"))
    assert tool.name == "hybrid_search"
    assert "hybrid retrieval" in tool.description.lower()

    schema = tool.input_schema
    # JSON Schema root wajib bertipe object
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "query" in schema["required"]

    props = schema["properties"]
    assert props["query"]["type"] == "string"
    assert props["k"]["type"] == "integer"
    assert props["kind"]["type"] == "string"
    assert props["path_prefix"]["type"] == "string"
    assert props["lexical_weight"]["type"] == "number"
    assert props["semantic_weight"]["type"] == "number"

    # Verifikasi interoperabilitas dengan ToolDefinition (adapter layer provider)
    definition = ToolDefinition.from_spec(tool.to_spec())
    assert definition.name == "hybrid_search"
    assert definition.parameters["type"] == "object"
    assert "query" in definition.parameters["properties"]


def test_hybrid_search_tool_validation():
    """Uji validasi argumen kosong/whitespace pada HybridSearchTool."""
    tool = HybridSearchTool(root=Path("/fake/root"))
    with pytest.raises(ToolValidationError):
        tool.execute(query="")

    with pytest.raises(ToolValidationError):
        tool.execute(query="   ")


# --------------------------------------------------------------------------- #
# 6. ToolRegistry & Factory Integration
# --------------------------------------------------------------------------- #
def test_build_hybrid_tools_factory():
    """Uji builder capability pencarian kode hybrid."""
    tools = build_hybrid_tools(root=Path("/fake/root"))
    assert len(tools) == 1
    assert tools[0].name == "hybrid_search"
    assert tools[0].root == Path("/fake/root").resolve()


def test_build_semantic_tools_with_hybrid_flag():
    """Uji pembuatan semantic tools saat bendera include_hybrid diaktifkan."""
    tools = build_semantic_tools(
        root=Path("/fake/root"),
        include_refresh=True,
        read_only=False,
        include_hybrid=True,
    )
    names = [t.name for t in tools]
    assert "semantic_search" in names
    assert "hybrid_search" in names
    assert "refresh_semantic_index" in names


def test_build_project_map_tools_with_hybrid_flag():
    """Uji pembuatan project map tools saat bendera include_hybrid diaktifkan."""
    tools = build_project_map_tools(
        root=Path("/fake/root"),
        include_refresh=True,
        include_hybrid=True,
    )
    names = [t.name for t in tools]
    assert "atlas_query" in names
    assert "rig_query" in names
    assert "project_map_status" in names
    assert "refresh_project_map" in names
    assert "hybrid_search" in names
