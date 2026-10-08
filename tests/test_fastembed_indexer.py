"""Unit dan integrasi tests untuk SemanticIndexer inkremental (Phase 2.1)."""

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from agent_ai.repointel.semantic.indexer import SemanticIndexer
from agent_ai.repointel.semantic.paths import resolve_vectors_db
from agent_ai.repointel.semantic.store import (
    BruteForceVectorStore,
    IndexMetaTable,
    open_connection,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mock_repo"


class DeterministicMockEmbedding:
    """Mock embedding deterministik 384 dimensi (setara bge-small)."""

    def __init__(self, size: int = 384):
        self.size = size

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        length = float(len(text))
        first_char = float(ord(text[0])) if text else 1.0
        vec = [0.0] * self.size
        vec[0] = length / (length + 10.0)
        vec[1] = first_char / 255.0
        vec[2] = 1.0
        # Normalisasi
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec]


@pytest.fixture
def mock_workspace(tmp_path):
    """Fixture yang menyalin mock repo ke direktori sementara."""
    ws = tmp_path / "test_project"
    ws.mkdir()
    for f in FIXTURES_DIR.glob("*"):
        if f.is_file():
            shutil.copy2(f, ws / f.name)
    return ws


def test_semantic_indexer_incremental_lifecycle(mock_workspace):
    db_path = resolve_vectors_db(mock_workspace)
    conn, backend = open_connection(db_path)
    embedder = DeterministicMockEmbedding(size=384)
    store = BruteForceVectorStore(conn, embedder)

    indexer = SemanticIndexer(
        root=mock_workspace,
        vector_store=store,
        conn=conn,
        backend=backend,
        model_name="mock-model",
    )

    # 1. Pengecekan awal: indeks belum pernah dibuat -> is_stale harus True
    assert indexer.is_stale() is True

    # 2. Pengindeksan pertama (full initial run)
    stats1 = indexer.run()
    assert stats1.scanned == 4  # billing.py, utils.js, api.ts, broken.py
    assert stats1.indexed == 4
    assert stats1.skipped == 0
    assert stats1.removed == 0
    assert stats1.total_chunks > 0

    # Setelah run pertama, tidak boleh stale
    assert indexer.is_stale() is False

    # 3. Pengindeksan kedua tanpa perubahan berkas -> semua harus di-skip
    stats2 = indexer.run()
    assert stats2.scanned == 4
    assert stats2.indexed == 0
    assert stats2.skipped == 4
    assert stats2.removed == 0

    # 4. Modifikasi satu berkas (billing.py)
    billing_file = mock_workspace / "billing.py"
    content = billing_file.read_text(encoding="utf-8")
    billing_file.write_text(content + "\n# Modified comment line\n", encoding="utf-8")
    new_time = billing_file.stat().st_mtime + 2.0
    os.utime(str(billing_file), (new_time, new_time))
    assert indexer.is_stale() is True

    stats3 = indexer.run()
    assert stats3.scanned == 4
    assert stats3.indexed == 1  # Hanya billing.py yang diindeks ulang
    assert stats3.skipped == 3  # Berkas lain dilewati
    assert stats3.removed == 0

    assert indexer.is_stale() is False

    # 5. Hapus satu berkas (broken.py)
    broken_file = mock_workspace / "broken.py"
    broken_file.unlink()

    assert indexer.is_stale() is True

    stats4 = indexer.run()
    assert stats4.scanned == 3
    assert stats4.indexed == 0
    assert stats4.skipped == 3
    assert stats4.removed == 1  # broken.py dihapus dari indeks

    assert indexer.is_stale() is False

    # 6. Ganti model name di metadata -> memicu rebuild penuh
    meta = IndexMetaTable(conn)
    meta.set("model_name", "different-model-v2")

    assert indexer.is_stale() is True

    stats5 = indexer.run()
    assert stats5.indexed == 3
    assert stats5.skipped == 0


@pytest.mark.skipif(
    os.getenv("AEGIS_RUN_EMBED_E2E") != "1",
    reason="Pengujian E2E model nyata dilewati (aktifkan dengan AEGIS_RUN_EMBED_E2E=1)",
)
def test_fastembed_e2e_real_model(mock_workspace):
    """Pengujian E2E integrasi model BAAI/bge-small-en-v1.5 nyata."""
    pytest.importorskip("fastembed")
    from agent_ai.repointel.semantic.embeddings import build_embeddings
    from agent_ai.repointel.semantic.service import SemanticIndexService

    embeddings = build_embeddings(model_name="BAAI/bge-small-en-v1.5")
    service = SemanticIndexService(root=mock_workspace, embeddings=embeddings)

    # Jalankan pencarian semantik (memicu auto-indexing)
    results = service.search("kalkulasi total faktur diskon pajak", k=3)
    assert len(results) > 0

    # Hasil teratas harus mengarah ke billing.py / calculate_total
    top = results[0]
    assert "billing.py" in top["path"]
    assert top["symbol"] in ("InvoiceService.calculate_total", "InvoiceService")
