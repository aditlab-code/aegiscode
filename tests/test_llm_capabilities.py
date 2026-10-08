"""Tests for Structured LLM Capabilities Contract (AEG-16 / PR-07).

Menguji:
1. ModelConfig Dataclass & Serialization:
   - Default values (context_window=128000, supports_thinking=False, reasoning_budget=None, timeout=60).
   - to_dict() dan from_dict() roundtrip.
   - from_row() toleran terhadap schema lama (backward compatibility).
2. Store SQLite Schema & Auto-migration:
   - Tabel llm_models memuat kolom baru.
   - create_model, update_model, get_model, list_models menyimpan dan memuat kapabilitas.
   - Auto-migration menambahkan kolom ke database legacy tanpa menghapus data.
3. LLMConfigService & Runtime Config Resolution:
   - resolve_runtime_config meneruskan metadata kapabilitas model ke dict runtime.
4. Provider Factory & Base Provider Integration:
   - build_provider_from_config memasang supports_thinking, reasoning_budget, dan context_window.
5. Gateway Service & API Views:
   - Endpoint HTTP POST /api/llm/models dan PUT /api/llm/models/<id> menyimpan kapabilitas.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Pastikan import paths
django_dir = Path(__file__).resolve().parent.parent / "apps" / "django_app"
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(django_dir) not in sys.path:
    sys.path.insert(0, str(django_dir))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.conf import settings
import django

try:
    django.setup()
except RuntimeError:
    pass

from django.test import Client

from agent_ai.llm_config.models import ModelConfig, ProviderInstance
from agent_ai.llm_config.service import LLMConfigService
from agent_ai.llm_config.store import LLMConfigStore
from agent_ai.providers.factory import build_provider_from_config
from api.services import GatewayService


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_aegis.db"


@pytest.fixture
def temp_env(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=sk-or-v1-testkey1234567890\n")
    return env_file


# ===========================================================================
# 1. ModelConfig Dataclass Tests
# ===========================================================================

def test_model_config_defaults_and_serialization() -> None:
    """ModelConfig memiliki default yang aman dan roundtrip dict yang presisi."""
    mc = ModelConfig(provider_id="prov_1", model_name="anthropic/claude-3-opus")
    assert mc.context_window == 128000
    assert mc.supports_thinking is False
    assert mc.reasoning_budget is None
    assert mc.timeout == 60

    d = mc.to_dict()
    assert d["context_window"] == 128000
    assert d["supports_thinking"] is False
    assert d["reasoning_budget"] is None
    assert d["timeout"] == 60

    # Custom capability roundtrip
    mc_custom = ModelConfig(
        provider_id="prov_1",
        model_name="deepseek/deepseek-r1",
        context_window=64000,
        supports_thinking=True,
        reasoning_budget=16384,
        timeout=180,
    )
    d_custom = mc_custom.to_dict()
    restored = ModelConfig.from_dict(d_custom)
    assert restored.context_window == 64000
    assert restored.supports_thinking is True
    assert restored.reasoning_budget == 16384
    assert restored.timeout == 180


def test_model_config_from_row_legacy_fallback() -> None:
    """from_row menangani baris database lawas tanpa error."""
    mock_row = {
        "id": "model_legacy_1",
        "provider_id": "prov_1",
        "model_name": "gpt-4o",
        "enabled": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    # Mocking dict row tanpa atribut kolom baru
    mc = ModelConfig.from_row(mock_row)
    assert mc.model_name == "gpt-4o"
    assert mc.context_window == 128000
    assert mc.supports_thinking is False
    assert mc.reasoning_budget is None
    assert mc.timeout == 60


# ===========================================================================
# 2. SQLite Store & Auto-Migration Tests
# ===========================================================================

def test_store_crud_with_capabilities(temp_db: Path) -> None:
    """Store SQLite menyimpan dan memuat kapabilitas model secara presisi."""
    store = LLMConfigStore(temp_db)
    inst = store.create_provider_instance(
        name="Test Provider",
        provider_type="openrouter",
        api_key_env="OPENROUTER_API_KEY",
    )

    created = store.create_model(
        provider_id=inst.id,
        model_name="deepseek-r1",
        enabled=True,
        context_window=65536,
        supports_thinking=True,
        reasoning_budget=8192,
        timeout=120,
    )
    assert created.context_window == 65536
    assert created.supports_thinking is True
    assert created.reasoning_budget == 8192
    assert created.timeout == 120

    loaded = store.get_model(created.id)
    assert loaded is not None
    assert loaded.context_window == 65536
    assert loaded.supports_thinking is True
    assert loaded.reasoning_budget == 8192
    assert loaded.timeout == 120

    # Update kapabilitas
    updated = store.update_model(
        created.id,
        {
            "context_window": 131072,
            "supports_thinking": False,
            "reasoning_budget": None,
            "timeout": 90,
        },
    )
    assert updated is not None
    assert updated.context_window == 131072
    assert updated.supports_thinking is False
    assert updated.reasoning_budget is None
    assert updated.timeout == 90


def test_store_auto_migration_on_legacy_db(temp_db: Path) -> None:
    """Tabel legacy tanpa kolom kapabilitas otomatis dimigrasi saat store dibuka."""
    # Buat tabel legacy secara manual
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        """
        CREATE TABLE llm_provider_instances (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            provider_type TEXT NOT NULL,
            api_url TEXT NOT NULL DEFAULT '',
            api_key_env TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE llm_models (
            id TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO llm_provider_instances VALUES
        ('inst_legacy', 'Legacy Provider', 'openai', '', '', 1, 'now', 'now')
        """
    )
    conn.execute(
        """
        INSERT INTO llm_models VALUES
        ('model_legacy', 'inst_legacy', 'gpt-3.5-turbo', 1, 'now', 'now')
        """
    )
    conn.commit()
    conn.close()

    # Inisialisasi LLMConfigStore (akan memicu _migrate_schema)
    store = LLMConfigStore(temp_db)
    legacy_model = store.get_model("model_legacy")
    assert legacy_model is not None
    assert legacy_model.model_name == "gpt-3.5-turbo"
    assert legacy_model.context_window == 128000
    assert legacy_model.supports_thinking is False
    assert legacy_model.reasoning_budget is None
    assert legacy_model.timeout == 60


# ===========================================================================
# 3. LLMConfigService & Runtime Config Propagation Tests
# ===========================================================================

def test_service_resolve_runtime_config_propagates_capabilities(
    temp_db: Path, temp_env: Path
) -> None:
    """resolve_runtime_config meneruskan seluruh metadata kapabilitas model ke runtime."""
    svc = LLMConfigService(temp_db, temp_env)
    inst = svc.create_provider_instance(
        name="OpenRouter Production",
        provider_type="openrouter",
        api_key_env="OPENROUTER_API_KEY",
    )

    m1 = svc.add_model(
        inst.id,
        "deepseek/deepseek-r1",
        enabled=True,
        context_window=64000,
        supports_thinking=True,
        reasoning_budget=16384,
        timeout=150,
    )

    # 1. Resolve via model_id eksplisit
    runtime_cfg = svc.resolve_runtime_config(inst.id, model_id=m1.id)
    assert runtime_cfg["model"] == "deepseek/deepseek-r1"
    assert runtime_cfg["context_window"] == 64000
    assert runtime_cfg["supports_thinking"] is True
    assert runtime_cfg["reasoning_budget"] == 16384
    assert runtime_cfg["timeout"] == 150

    # 2. Resolve via model_name
    runtime_cfg_name = svc.resolve_runtime_config(
        inst.id, model_name="deepseek/deepseek-r1"
    )
    assert runtime_cfg_name["supports_thinking"] is True
    assert runtime_cfg_name["reasoning_budget"] == 16384

    # 3. Update via service
    svc.update_model(
        m1.id,
        context_window=100000,
        supports_thinking=False,
        reasoning_budget=None,
    )
    updated_cfg = svc.resolve_runtime_config(inst.id, model_id=m1.id)
    assert updated_cfg["context_window"] == 100000
    assert updated_cfg["supports_thinking"] is False
    assert updated_cfg["reasoning_budget"] is None


# ===========================================================================
# 4. Factory & BaseProvider Integration Tests
# ===========================================================================

def test_factory_build_provider_attaches_capabilities() -> None:
    """build_provider_from_config memasang kapabilitas pada instance provider."""
    runtime_config = {
        "provider_type": "openrouter",
        "api_url": "https://openrouter.ai/api/v1",
        "api_key": "sk-or-v1-mock-key",
        "model": "deepseek/deepseek-r1",
        "timeout": 120,
        "context_window": 64000,
        "supports_thinking": True,
        "reasoning_budget": 8192,
    }

    provider = build_provider_from_config(runtime_config)
    assert provider.supports_thinking is True
    assert provider.reasoning_budget == 8192
    assert provider.context_window == 64000


# ===========================================================================
# 5. Gateway API View Endpoints Tests
# ===========================================================================

def test_api_view_create_and_update_model_capabilities(temp_db: Path, temp_env: Path) -> None:
    """POST /api/llm/models dan PUT /api/llm/models/<id> menyimpan kapabilitas."""
    client = Client()
    # Pastikan GatewayService memakai temporary db
    gateway_service = GatewayService()
    gateway_service.llm_config_service = LLMConfigService(temp_db, temp_env)

    from unittest.mock import patch

    with patch("api.views.get_service", return_value=gateway_service):
        inst = gateway_service.create_llm_provider(
            name="API Test Provider",
            provider_type="openrouter",
            api_key_env="OPENROUTER_API_KEY",
        )

        # POST /api/llm/models
        post_resp = client.post(
            "/api/llm/models",
            data={
                "provider_id": inst["id"],
                "model_name": "qwen/qwen-2.5-coder-32b",
                "enabled": True,
                "context_window": 32768,
                "supports_thinking": True,
                "reasoning_budget": 4096,
                "timeout": 90,
            },
            content_type="application/json",
        )
        assert post_resp.status_code == 201
        created_data = post_resp.json()
        assert created_data["model_name"] == "qwen/qwen-2.5-coder-32b"
        assert created_data["context_window"] == 32768
        assert created_data["supports_thinking"] is True
        assert created_data["reasoning_budget"] == 4096
        assert created_data["timeout"] == 90

        model_id = created_data["id"]

        # PUT /api/llm/models/<id>
        put_resp = client.put(
            f"/api/llm/models/{model_id}",
            data={
                "context_window": 65536,
                "supports_thinking": False,
                "reasoning_budget": None,
                "timeout": 60,
            },
            content_type="application/json",
        )
        assert put_resp.status_code == 200
        updated_data = put_resp.json()
        assert updated_data["context_window"] == 65536
        assert updated_data["supports_thinking"] is False
        assert updated_data["reasoning_budget"] is None
        assert updated_data["timeout"] == 60
