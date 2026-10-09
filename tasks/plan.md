# Implementation Plan: Decommissioning Total Legacy Semantic (Clean Cut, Zero-Orphan)

## Context & Objectives
Menggantikan seluruh sisa modul legacy vector/semantic indexing (`fastembed`, `sqlite-vec`, `src/agent_ai/repointel/semantic/`, `src/agent_ai/tools/semantic.py`) dengan arsitektur deterministik **CodeGraph AST** (`.aegis/codegraph.db`) sesuai spesifikasi [`docs/specs/spec-decommission-legacy-semantic.md`](../docs/specs/spec-decommission-legacy-semantic.md).

---

## Dependency Graph & Architecture

```
CodeGraph AST (.aegis/codegraph.db) [CANONICAL INTEL]
      ▲
      │ (4 Canonical Tools: callers, callees, references, impact)
      │
Core Engine Subsystems
  ├── ToolRegistry (src/agent_ai/tools/registry.py)
  ├── Consultant Tools (src/agent_ai/consultant/tools.py)
  ├── Consultant Service (src/agent_ai/consultant/service.py)
  ├── Provider Antigravity (src/agent_ai/providers/antigravity.py)
  ├── ContextBuilder Mention (src/agent_ai/contextbuilder/mention.py)
  ├── ProjectMap Tools (src/agent_ai/tools/project_map.py)
  └── Settings & Telemetry (src/agent_ai/config/settings.py)
      │
      └── [PURGED] Legacy Semantic Pipeline
              ├── src/agent_ai/tools/semantic.py (DELETED)
              ├── src/agent_ai/repointel/semantic/ (DELETED)
              └── 5 Legacy Test Suites (DELETED)
```

---

## Detailed Task Breakdown

### Task 1: Uncouple Consumers & Callers in Core Engine
- Hapus impor dan pemanggilan `is_available` serta registrasi `build_semantic_tools` di `src/agent_ai/tools/registry.py` dan `src/agent_ai/consultant/tools.py`.
- Bersihkan fallback `_build_auto_semantic_context` di `src/agent_ai/consultant/service.py`.
- Hapus fungsi `_resolve_semantic_search_candidates` di `src/agent_ai/providers/antigravity.py`.
- Bersihkan fallback `_semantic_fallback_search` di `src/agent_ai/contextbuilder/mention.py`.
- Hapus parameter `include_hybrid` dan import `HybridSearchTool` di `src/agent_ai/tools/project_map.py`.
- Bersihkan konfigurasi `EMBEDDING_MODEL` dan telemetri fastembed di `src/agent_ai/config/settings.py` dan `src/agent_ai/runtime/telemetry/hardware.py`.

### Task 2: Delete Legacy Semantic Directory & Tool Files
- Hapus file `src/agent_ai/tools/semantic.py`.
- Hapus seluruh isi direktori `src/agent_ai/repointel/semantic/`.
- Verifikasi bahwa direktori `src/agent_ai/repointel/semantic/` telah hilang dan tidak ada broken import di `src/`.

### Task 3: Remove Usang Test Suites & Align Integration Tests
- Hapus 5 berkas test legacy:
  - `tests/test_fastembed_indexer.py`
  - `tests/test_sqlite_vec_store.py`
  - `tests/test_semantic_tools.py`
  - `tests/test_semantic_chunker.py`
  - `tests/test_rrf_ranker.py`
- Perbarui test integration pendukung:
  - `tests/test_activity_classification.py`: bersihkan test cases untuk tool `semantic_search` & `refresh_semantic_index`.
  - `tests/test_antigravity_dynamic_discovery.py`: bersihkan mock test `_resolve_semantic_search_candidates`.

### Task 4: Full Regression & Zero-Orphan Verification Gate
- Jalankan static analysis grep untuk memastikan 0 referensi `repointel.semantic` tersisa di `src/`.
- Jalankan `rtk pytest tests/test_codegraph_*.py` untuk memastikan CodeGraph tetap berfungsi optimal.
- Jalankan full `rtk pytest` backend regression suite (Exit Code 0).
