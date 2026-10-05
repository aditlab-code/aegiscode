"""Unit tests untuk SQLite vector store and tables (Phase 2.1)."""

import tempfile
from pathlib import Path

from agent_ai.repointel.semantic.paths import (
    resolve_model_cache,
    resolve_vectors_db,
)
from agent_ai.repointel.semantic.store import (
    BruteForceVectorStore,
    FingerprintTable,
    IndexMetaTable,
    cosine_similarity,
    deserialize_float32,
    open_connection,
    serialize_float32,
)


class MockEmbedding:
    """Mock deterministik embedding: vektor 3D."""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        if text in self.mapping:
            return self.mapping[text]
        # Vektor berbasis panjang string dan karakter pertama
        v1 = float(len(text))
        v2 = float(ord(text[0])) if text else 0.0
        v3 = 1.0
        # Normalisasi
        norm = (v1 * v1 + v2 * v2 + v3 * v3) ** 0.5
        return [v1 / norm, v2 / norm, v3 / norm]


def test_cosine_similarity_math():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert round(cosine_similarity(v1, v2), 4) == 1.0

    v3 = [0.0, 1.0, 0.0]
    assert round(cosine_similarity(v1, v3), 4) == 0.0

    v4 = [-1.0, 0.0, 0.0]
    assert round(cosine_similarity(v1, v4), 4) == -1.0

    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_serialize_deserialize_float32():
    original = [0.123456, -0.987654, 3.141592, 0.0]
    serialized = serialize_float32(original)
    assert isinstance(serialized, bytes)
    assert len(serialized) == len(original) * 4

    deserialized = deserialize_float32(serialized)
    for a, b in zip(original, deserialized):
        assert abs(a - b) < 1e-5


def test_index_meta_and_fingerprints():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_meta.db"
        conn, backend = open_connection(db_path)
        assert backend in ("sqlite-vec", "bruteforce")

        meta = IndexMetaTable(conn)
        meta.set("schema_version", "2.1")
        meta.set("model_name", "test-model")
        assert meta.get("schema_version") == "2.1"
        assert meta.get("model_name") == "test-model"
        assert meta.get("non_existent", "default") == "default"
        all_meta = meta.all()
        assert all_meta["schema_version"] == "2.1"

        fp = FingerprintTable(conn)
        fp.upsert("src/main.py", "hash1", 5)
        fp.upsert("src/utils.py", "hash2", 3)

        assert fp.get("src/main.py")["sha256"] == "hash1"
        assert fp.get("src/main.py")["chunk_count"] == 5
        assert len(fp.all()) == 2

        fp.delete("src/main.py")
        assert fp.get("src/main.py") is None
        assert len(fp.all()) == 1

        fp.clear()
        assert len(fp.all()) == 0


def test_bruteforce_vector_store_crud():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_vec.db"
        conn, _ = open_connection(db_path)
        embedder = MockEmbedding(
            mapping={
                "apple fruit red": [1.0, 0.0, 0.0],
                "banana fruit yellow": [0.9, 0.1, 0.0],
                "car vehicle engine": [0.0, 1.0, 0.0],
            }
        )
        store = BruteForceVectorStore(conn, embedder)
        assert store.count() == 0

        # Insert documents
        texts = ["apple fruit red", "banana fruit yellow", "car vehicle engine"]
        metas = [
            {"path": "fruits/apple.py", "kind": "food"},
            {"path": "fruits/banana.py", "kind": "food"},
            {"path": "vehicles/car.py", "kind": "machine"},
        ]
        inserted_ids = store.add_texts(texts, metas)
        assert len(inserted_ids) == 3
        assert store.count() == 3

        # Similarity search
        results = store.similarity_search_with_score("apple fruit red", k=2)
        assert len(results) == 2
        # Hasil teratas harus apple
        top_meta, top_score = results[0]
        assert top_meta["path"] == "fruits/apple.py"
        assert round(top_score, 4) == 1.0

        # Path prefix filter
        filtered = store.similarity_search_with_score(
            "fruit", k=5, path_prefix="vehicles"
        )
        assert len(filtered) == 1
        assert filtered[0][0]["path"] == "vehicles/car.py"

        # Delete by path
        deleted = store.delete_by_path("fruits/apple.py")
        assert deleted == 1
        assert store.count() == 2

        # Clear
        store.clear()
        assert store.count() == 0


def test_resolve_vectors_db_fallback():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()

        # 1. Kasus awal: keduanya belum ada -> .aegis/vectors.db
        resolved = resolve_vectors_db(root)
        assert resolved == root / ".aegis" / "vectors.db"


        # 2. Hanya .aether/vectors.db yang ada -> fallback ke .aether
        aether_dir = root / ".aether"
        aether_dir.mkdir()
        (aether_dir / "vectors.db").write_text("dummy")
        resolved = resolve_vectors_db(root)
        assert resolved == root / ".aether" / "vectors.db"

        # 3. .aegis/vectors.db dibuat -> .aegis menjadi prioritas primer
        aegis_dir = root / ".aegis"
        aegis_dir.mkdir()
        (aegis_dir / "vectors.db").write_text("dummy_primary")
        resolved = resolve_vectors_db(root)
        assert resolved == root / ".aegis" / "vectors.db"


def test_resolve_model_cache_env(monkeypatch, tmp_path):
    # Default cache
    default_cache = resolve_model_cache()
    assert default_cache.name == "models"
    assert "data" in str(default_cache)

    # Override via settings
    custom_dir = tmp_path / "custom_models"
    monkeypatch.setattr("agent_ai.repointel.semantic.paths.EMBED_CACHE", str(custom_dir))
    assert resolve_model_cache() == custom_dir
