# Task List: Decommissioning Total Legacy Semantic

- [x] Task 1: Uncouple Consumers & Callers in Core Engine
  - Acceptance: Tidak ada import `repointel.semantic` atau `tools.semantic` di seluruh `src/` core engine
  - Verify: `rtk grep -rn "repointel\.semantic" src/agent_ai/tools/ src/agent_ai/consultant/ src/agent_ai/providers/` menghasilkan 0 matches
  - Files: `src/agent_ai/tools/registry.py`, `src/agent_ai/consultant/tools.py`, `src/agent_ai/consultant/service.py`, `src/agent_ai/providers/antigravity.py`, `src/agent_ai/contextbuilder/mention.py`, `src/agent_ai/tools/project_map.py`, `src/agent_ai/config/settings.py`, `src/agent_ai/runtime/telemetry/hardware.py`

- [x] Task 2: Delete Legacy Semantic Directory & Tool Files
  - Acceptance: Seluruh direktori `src/agent_ai/repointel/semantic/` dan file `src/agent_ai/tools/semantic.py` terhapus bersih
  - Verify: `rtk ls src/agent_ai/tools/semantic.py` -> Not found; `rtk grep -rn "repointel\.semantic" src/` -> 0 matches
  - Files: `src/agent_ai/tools/semantic.py`, `src/agent_ai/repointel/semantic/`

- [x] Task 3: Remove Usang Test Suites & Align Integration Tests
  - Acceptance: 5 file test legacy terhapus; test integration yang tersisa disesuaikan dan lulus 100%
  - Verify: `rtk pytest tests/test_activity_classification.py tests/test_antigravity_dynamic_discovery.py`
  - Files: `tests/test_fastembed_indexer.py`, `tests/test_sqlite_vec_store.py`, `tests/test_semantic_tools.py`, `tests/test_semantic_chunker.py`, `tests/test_rrf_ranker.py`, `tests/test_activity_classification.py`, `tests/test_antigravity_dynamic_discovery.py`

- [x] Task 4: Full Regression & Zero-Orphan Verification Gate
  - Acceptance: Seluruh test suite pytest backend lulus 100% tanpa error
  - Verify: `rtk pytest tests/test_codegraph_*.py` && `rtk pytest`
  - Files: Seluruh test suite backend
