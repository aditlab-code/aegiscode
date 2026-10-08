"""Comprehensive unit and performance tests for CodeGraph Store and Extractors (PR-CG-1)."""

import time
from pathlib import Path
import pytest

from agent_ai.codegraph import (
    CodeGraphStore,
    CodeSymbol,
    FileFingerprint,
    LightweightRegexExtractor,
    PythonASTExtractor,
    RelationType,
    SymbolRelation,
    extract_file,
)


@pytest.fixture
def store(tmp_path):
    db_file = tmp_path / "test_codegraph.db"
    s = CodeGraphStore(db_file)
    yield s
    s.close()


def test_models_serialization():
    sym = CodeSymbol(
        id="src/a.py::Foo",
        name="Foo",
        type="class",
        file_path="src/a.py",
        language="python",
        start_line=1,
        end_line=10,
        body_hash="abc",
        docstring="Doc",
    )
    d = sym.to_dict()
    assert d["id"] == "src/a.py::Foo"
    assert d["name"] == "Foo"
    assert d["docstring"] == "Doc"

    rel = SymbolRelation(
        source_id="src/a.py::bar",
        target_name="Foo",
        relation_type=RelationType.CALLS,
        file_path="src/a.py",
        line_number=5,
    )
    rd = rel.to_dict()
    assert rd["relation_type"] == "calls"
    assert rd["target_name"] == "Foo"


def test_store_crud_and_fingerprints(store):
    fp = FileFingerprint(file_path="src/core.py", sha256="hash123", mtime=100.0, symbol_count=5)
    store.save_file_fingerprint(fp)

    loaded_fp = store.get_file_fingerprint("src/core.py")
    assert loaded_fp is not None
    assert loaded_fp.sha256 == "hash123"
    assert not store.is_file_dirty("src/core.py", 100.0, "hash123")
    assert store.is_file_dirty("src/core.py", 101.0, "hash123")
    assert store.is_file_dirty("src/core.py", 100.0, "diffhash")

    sym = CodeSymbol(
        id="src/core.py::run",
        name="run",
        type="function",
        file_path="src/core.py",
        language="python",
        start_line=1,
        end_line=5,
        body_hash="hash_run",
    )
    store.insert_symbols([sym])
    assert len(store.find_symbol("run")) == 1
    assert store.get_symbol_by_id("src/core.py::run") is not None

    store.delete_file_data("src/core.py")
    assert store.get_file_fingerprint("src/core.py") is None
    assert len(store.find_symbol("run")) == 0


def test_recursive_cte_callers_and_callees(store):
    syms = [
        CodeSymbol("a.py::entry", "entry", "function", "a.py", "python", 1, 5, "h1"),
        CodeSymbol("b.py::mid", "mid", "function", "b.py", "python", 1, 5, "h2"),
        CodeSymbol("c.py::leaf", "leaf", "function", "c.py", "python", 1, 5, "h3"),
    ]
    store.insert_symbols(syms)

    rels = [
        SymbolRelation("a.py::entry", "mid", RelationType.CALLS, "a.py", 2, target_id="b.py::mid"),
        SymbolRelation("b.py::mid", "leaf", RelationType.CALLS, "b.py", 2, target_id="c.py::leaf"),
    ]
    store.insert_relations(rels)

    # Callers of leaf up to depth 2
    callers = store.get_callers("leaf", depth=2)
    caller_names = [c["caller_name"] for c in callers]
    assert "mid" in caller_names
    assert "entry" in caller_names

    # Callees of entry up to depth 2
    callees = store.get_callees("a.py::entry", depth=2)
    callee_names = [c["callee_name"] for c in callees]
    assert "mid" in callee_names
    assert "leaf" in callee_names


def test_impact_analysis(store):
    syms = [
        CodeSymbol("service.py::AuthService", "AuthService", "class", "service.py", "python", 1, 20, "h1"),
        CodeSymbol("views.py::login_view", "login_view", "function", "views.py", "python", 1, 10, "h2"),
    ]
    store.insert_symbols(syms)
    rels = [
        SymbolRelation("views.py::login_view", "AuthService", RelationType.CALLS, "views.py", 5, target_id="service.py::AuthService")
    ]
    store.insert_relations(rels)

    impact = store.impact_analysis("AuthService", depth=2)
    assert impact["affected_symbols_count"] >= 1
    assert "views.py" in impact["affected_files"]


def test_python_ast_extractor():
    code = '''"""Module doc."""
import os
from sys import argv

class Worker(BaseWorker):
    """Worker class."""
    def run(self, timeout: int = 10) -> bool:
        """Runs task."""
        helper()
        return True
'''
    extractor = PythonASTExtractor()
    syms, rels = extractor.extract(code, "worker.py")

    assert any(s.type == "module" for s in syms)
    assert len([s for s in syms if s.type != "module"]) == 2  # Worker, Worker.run
    cls_sym = next(s for s in syms if s.type == "class")
    assert cls_sym.name == "Worker"
    assert cls_sym.docstring == "Worker class."

    fn_sym = next(s for s in syms if s.type == "method")
    assert fn_sym.name == "run"
    assert "timeout" in (fn_sym.signature or "")

    import_rels = [r for r in rels if r.relation_type == RelationType.IMPORTS]
    assert len(import_rels) >= 2
    call_rels = [r for r in rels if r.relation_type == RelationType.CALLS]
    assert any(r.target_name == "helper" for r in call_rels)
    extend_rels = [r for r in rels if r.relation_type == RelationType.EXTENDS]
    assert any(r.target_name == "BaseWorker" for r in extend_rels)


def test_regex_extractor():
    js_code = """
import { ref } from 'vue';
import axios from 'axios';

export async function fetchUsers(query) {
    const res = await axios.get('/api/users');
    return res.data;
}
"""
    extractor = LightweightRegexExtractor()
    syms, rels = extractor.extract(js_code, "api.js")
    assert any(s.name == "fetchUsers" for s in syms)
    assert any(r.relation_type == RelationType.API_CALL for r in rels)


def test_extract_file_and_performance(tmp_path):
    f = tmp_path / "speed_test.py"
    # Generate 150 functions
    lines = ["import math\n"]
    for i in range(150):
        lines.append(f"def func_{i}(x: int) -> int:\n    return math.sqrt(x) + {i}\n")
    f.write_text("\n".join(lines), encoding="utf-8")

    t0 = time.perf_counter()
    syms, rels = extract_file(f, tmp_path)
    dur = time.perf_counter() - t0

    assert len([s for s in syms if s.type == "function"]) == 150
    assert dur < 1.0  # indexing SLA < 1 detik terpenuhi

