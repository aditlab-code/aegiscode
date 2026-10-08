"""Isolasi state Extension proses-wide antar-test.

Integrasi Extension -> Agent (Task: Playwright) memakai state proses-wide:

* registry tool Extension bersama
  (``agent_ai.tools.registry.get_extension_tool_registry``) yang dibaca oleh
  ``build_registry()`` agar tool Extension ENABLED muncul pada toolset Agent;
* manager Extension singleton (``agent_ai.extensions.agent_bridge``) yang
  memuat Extension sekali per proses.

Keduanya SENGAJA proses-wide pada produksi (satu proses Django: UI Extension dan
jalur eksekusi Agent berbagi state yang sama). Namun untuk TEST, state ini
di-reset sebelum/sesudah setiap test agar hasil test tidak bergantung urutan —
mis. ``build_registry()`` di satu test tidak "mewarisi" tool Extension yang
ter-load oleh test sebelumnya.
"""

from __future__ import annotations

import pytest


def _reset_extension_process_state() -> None:
    try:
        import agent_ai.extensions.agent_bridge as _bridge

        _bridge._manager = None
    except Exception:
        pass
    try:
        from agent_ai.tools.registry import get_extension_tool_registry

        get_extension_tool_registry()._tools.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_extension_process_state():
    _reset_extension_process_state()
    try:
        yield
    finally:
        _reset_extension_process_state()

@pytest.fixture(autouse=True)
def _isolate_data_and_sessions(tmp_path, monkeypatch, request):
    """Isolasi penuh data/aegis.db dan data/consultant_sessions.json selama pytest."""
    fake_data = tmp_path / "data"
    fake_data.mkdir(parents=True, exist_ok=True)
    fake_json = fake_data / "consultant_sessions.json"
    fake_json.write_text('{"sessions": []}', encoding="utf-8")
    fake_db = fake_data / "aegis.db"

    try:
        from agent_ai.consultant import store as consultant_store_mod
        original_init = consultant_store_mod.ConsultantSessionStore.__init__

        def _safe_consultant_init(self, path=None):
            if path is None:
                path = str(fake_json)
            original_init(self, path)

        monkeypatch.setattr(consultant_store_mod.ConsultantSessionStore, "__init__", _safe_consultant_init)
    except Exception:
        pass

    try:
        from agent_ai.session import unified_store as unified_store_mod
        if request.node.name != "test_unified_store_auto_migrates_legacy_aether_db":
            monkeypatch.setattr(unified_store_mod, "default_db_path", lambda: fake_db)
            monkeypatch.setattr(unified_store_mod, "default_legacy_json_path", lambda: fake_json)
    except Exception:
        pass

    try:
        from api import project_store as project_store_mod
        monkeypatch.setattr(project_store_mod, "_default_db_path", lambda: fake_db)
    except Exception:
        pass

    try:
        from agent_ai.projects import registry as registry_mod
        orig_registry_init = registry_mod.ProjectRegistry.__init__

        def _safe_registry_init(self, workspace=None):
            if workspace is None:
                workspace = tmp_path / "projects"
            orig_registry_init(self, workspace)

        monkeypatch.setattr(registry_mod.ProjectRegistry, "__init__", _safe_registry_init)
    except Exception:
        pass
    yield
