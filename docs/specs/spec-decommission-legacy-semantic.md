# Spec: Decommissioning Total Legacy Semantic (FastEmbed & sqlite-vec)

## 1. Objective
Melakukan pembersihan total (*clean cut, zero-orphan*) terhadap seluruh modul legacy semantic indexing (`fastembed`, ONNX runtime, `sqlite-vec`, dan direktori `src/agent_ai/repointel/semantic/`) di repositori AegisCode. Repositori distandarisasi murni 100% menggunakan arsitektur deterministik **CodeGraph AST (`.aegis/codegraph.db`)** berbasis Python stdlib dan SQLite WAL tanpa dependensi eksternal yang usang.

### Acceptance Criteria:
1. Seluruh direktori `src/agent_ai/repointel/semantic/` dan berkas `src/agent_ai/tools/semantic.py` dihapus tuntas.
2. Seluruh import, registrasi tool, dan fallback ke `repointel.semantic` pada core engine (`registry.py`, `consultant`, `antigravity`, `contextbuilder`, `project_map`, `settings.py`) dibersihkan tanpa broken import.
3. Seluruh berkas uji usang (`test_fastembed_indexer.py`, `test_sqlite_vec_store.py`, `test_semantic_tools.py`, `test_semantic_chunker.py`, `test_rrf_ranker.py`) dihapus, dan berkas uji pendukung diselaraskan.
4. Audit statis `rtk grep -rn "repointel\.semantic" src/` menghasilkan 0 kecocokan.
5. Seluruh rangkaian pengujian `rtk pytest` lulus 100% (PASS, Exit Code 0).

---

## 2. Tech Stack & Commands
* **Runtime**: Python 3.11+, stdlib `sqlite3`, `ast`
* **Target Architecture**: CodeGraph AST (`src/agent_ai/codegraph/`)
* **Commands**:
  * Audit sisa impor: `rtk grep -rn "repointel\.semantic" src/`
  * Verifikasi CodeGraph: `rtk pytest tests/test_codegraph_store_extractor.py tests/test_codegraph_service_tools.py tests/test_codegraph_migration.py`
  * Verifikasi seluruh suite backend: `rtk pytest`
  * Status Git: `rtk git status`

---

## 3. Project Structure & Changes

### Files & Directories to Delete:
* `src/agent_ai/repointel/semantic/` (seluruh direktori dan isinya)
* `src/agent_ai/tools/semantic.py`
* `tests/test_fastembed_indexer.py`
* `tests/test_sqlite_vec_store.py`
* `tests/test_semantic_tools.py`
* `tests/test_semantic_chunker.py`
* `tests/test_rrf_ranker.py`

### Files to Refactor:
* `src/agent_ai/tools/registry.py`: Hapus pemanggilan `is_available` dan registrasi `build_semantic_tools`.
* `src/agent_ai/consultant/tools.py`: Hapus registrasi `build_semantic_tools`.
* `src/agent_ai/consultant/service.py`: Bersihkan helper `_build_auto_semantic_context`.
* `src/agent_ai/providers/antigravity.py`: Hapus fungsi `_resolve_semantic_search_candidates`.
* `src/agent_ai/contextbuilder/mention.py`: Bersihkan fallback `_semantic_fallback_search`.
* `src/agent_ai/tools/project_map.py`: Hapus opsi `include_hybrid` yang mengimpor `HybridSearchTool`.
* `src/agent_ai/config/settings.py`: Hapus konfigurasi legacy `EMBEDDING_MODEL`.
* `src/agent_ai/runtime/telemetry/hardware.py`: Bersihkan referensi docstring fastembed.
* `tests/test_activity_classification.py`: Sesuaikan test case yang mereferensikan `semantic_search`.
* `tests/test_antigravity_dynamic_discovery.py`: Bersihkan uji mock `_resolve_semantic_search_candidates`.

---

## 4. Code Style & Architecture
* **Pure Python stdlib**: Zero third-party dependency untuk navigasi struktur kode.
* **Zero-Orphan Policy**: Tiada berkas usang atau stub kosong tersisa.
* **Deterministic Relational Intelligence**: Navigasi relasi simbol kode dilayani murni oleh 4 canonical tools `codegraph_*` di `src/agent_ai/tools/codegraph.py`.

---

## 5. Testing Strategy
* Prapembersihan: Pastikan test baseline CodeGraph lulus.
* Pascapembersihan: Verifikasi tidak ada kegagalan impor pada core registry, consultant, dan provider.
* Akhir: Eksekusi `rtk pytest` untuk seluruh suite backend.

---

## 6. Boundaries
* **Always**: Prefix perintah dengan `rtk`.
* **Always**: Pastikan `SearchCodeTool` (lexical ripgrep) tetap utuh dan berfungsi.
* **Never**: Mengubah skema `CodeGraphStore` di `src/agent_ai/codegraph/store.py`.
* **Never**: Menyisakan impor rusak di `__init__.py`.
