from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from pathlib import Path

from agent_ai.runtime.telegram.security import TelegramSecurityManager
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler


@pytest.fixture
def test_setup(tmp_path: Path):
    bot_client = MagicMock()
    sec_manager = TelegramSecurityManager(storage_path=tmp_path / "paired.json", env_whitelist="")
    pairing_mgr = PairingManager(ttl_seconds=300)
    hitl_callback = MagicMock()
    steer_callback = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=bot_client,
        security_manager=sec_manager,
        pairing_manager=pairing_mgr,
        on_hitl_action=hitl_callback,
        on_steer_command=steer_callback,
        get_runtime_status=lambda: "🟢 AegisCode Aktif (branch: main)",
    )
    return handler, bot_client, sec_manager, pairing_mgr, hitl_callback, steer_callback


def test_handle_pairing_success(test_setup):
    handler, bot_client, sec_manager, pairing_mgr, _, _ = test_setup
    session = pairing_mgr.create_session("MyAegis_bot")

    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": 12345},
            "from": {"id": 12345, "username": "adit", "first_name": "Adit"},
            "text": f"/start pair_{session.token}",
        },
    }

    handler.handle_update(update)

    assert sec_manager.is_authorized(12345) is True
    bot_client.send_message.assert_called_once()
    args, kwargs = bot_client.send_message.call_args
    assert kwargs["chat_id"] == 12345
    assert "Pairing Berhasil" in kwargs["text"]


def test_handle_unauthorized_user_message(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup

    update = {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "chat": {"id": 99999},
            "from": {"id": 99999, "username": "stranger"},
            "text": "format hard drive",
        },
    }

    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    args, kwargs = bot_client.send_message.call_args
    assert kwargs["chat_id"] == 99999
    assert "Akses Ditolak" in kwargs["text"]


def test_handle_authorized_status_command(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)

    update = {
        "update_id": 3,
        "message": {
            "message_id": 12,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/status",
        },
    }

    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    args, kwargs = bot_client.send_message.call_args
    assert "AegisCode Aktif" in kwargs["text"]


def test_handle_authorized_steer_command(test_setup):
    handler, bot_client, sec_manager, _, _, steer_callback = test_setup
    sec_manager.save_paired_user(user_id=12345)

    update = {
        "update_id": 4,
        "message": {
            "message_id": 13,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "tolong tambahkan unit test untuk security",
        },
    }

    handler.handle_update(update)

    try:
        steer_callback.assert_called_once_with("tolong tambahkan unit test untuk security", chat_id=12345)
    except AssertionError:
        steer_callback.assert_called_once_with("tolong tambahkan unit test untuk security")
    # Handler mengarahkan instruksi ke steer_callback tanpa mengirim pesan teks boilerplate ganda
    assert steer_callback.call_count == 1


def test_handle_hitl_callback_query(test_setup):
    handler, bot_client, sec_manager, _, hitl_callback, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)

    update = {
        "update_id": 5,
        "callback_query": {
            "id": "cb_123",
            "from": {"id": 12345},
            "message": {"message_id": 55, "chat": {"id": 12345}, "text": "Approval Diperlukan"},
            "data": "hitl:allow:req_abc",
        },
    }

    handler.handle_update(update)

    hitl_callback.assert_called_once_with("allow", "req_abc")
    bot_client.answer_callback_query.assert_called_once_with(callback_query_id="cb_123", text="Persetujuan dicatat: ALLOW")
    bot_client.edit_message_text.assert_called_once()
    args, kwargs = bot_client.edit_message_text.call_args
    assert "DISETUJUI" in kwargs["text"]


def test_handle_repo_command_clean(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_repo_info = MagicMock(return_value={
        "name": "MyProject",
        "root": "/workspace/my_project",
        "branch": "feature/aegis",
        "last_commit": "abc1234 Initial feature",
        "uncommitted_changes": 0,
        "is_dirty": False,
        "is_repo": True,
    })

    update = {
        "update_id": 6,
        "message": {
            "message_id": 20,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/repo",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "MyProject" in kwargs["text"]
    assert "feature/aegis" in kwargs["text"]
    assert "abc1234 Initial feature" in kwargs["text"]
    assert "Clean (bersih)" in kwargs["text"]


def test_handle_repo_command_dirty(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_repo_info = MagicMock(return_value={
        "name": "AegisCode",
        "root": "/workspace/aegis",
        "branch": "main",
        "last_commit": "def5678 Update tests",
        "uncommitted_changes": 3,
        "is_dirty": True,
        "is_repo": True,
    })

    update = {
        "update_id": 7,
        "message": {
            "message_id": 21,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/repo",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "3 perubahan belum di-commit" in kwargs["text"]


def test_handle_repo_command_fallback_when_none(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_repo_info = None

    update = {
        "update_id": 8,
        "message": {
            "message_id": 22,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/repo",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Repositori Aktif" in kwargs["text"]


def test_handle_mode_command_show_menu(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_mode = MagicMock(return_value="ask")

    update = {
        "update_id": 9,
        "message": {
            "message_id": 23,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/mode",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Kontrol Mode Operasional" in kwargs["text"]
    assert "Ask ⏸️" in kwargs["text"]
    reply_markup = kwargs.get("reply_markup", {})
    keyboard = reply_markup.get("inline_keyboard", [])
    assert len(keyboard) > 0
    callback_datas = [btn["callback_data"] for row in keyboard for btn in row]
    assert "mode:set:ask" in callback_datas
    assert "mode:set:agents" in callback_datas


def test_handle_mode_command_direct_ask(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_mode = MagicMock(return_value="ask")

    update = {
        "update_id": 10,
        "message": {
            "message_id": 24,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/mode ask",
        },
    }
    handler.handle_update(update)

    handler.set_mode.assert_called_once_with("ask")
    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Ask ⏸️" in kwargs["text"]


def test_handle_mode_command_direct_agents(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_mode = MagicMock(return_value="agents")

    update = {
        "update_id": 11,
        "message": {
            "message_id": 25,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/mode agents",
        },
    }
    handler.handle_update(update)

    handler.set_mode.assert_called_once_with("agents")
    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Agents ⚡" in kwargs["text"]


def test_handle_mode_command_invalid_argument(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)

    update = {
        "update_id": 12,
        "message": {
            "message_id": 26,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/mode invalid_arg",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Mode Tidak Valid" in kwargs["text"]


def test_handle_mode_callback_query(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_mode = MagicMock(return_value="agents")

    update = {
        "update_id": 13,
        "callback_query": {
            "id": "cb_mode_1",
            "from": {"id": 12345},
            "message": {"message_id": 60, "chat": {"id": 12345}, "text": "Pilih mode:"},
            "data": "mode:set:agents",
        },
    }
    handler.handle_update(update)

    handler.set_mode.assert_called_once_with("agents")
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_mode_1", text="Mode diubah ke: Agents ⚡"
    )
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Agents ⚡" in kwargs["text"]


def test_handle_agents_command_with_fleet(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_agents = MagicMock(return_value=[
        {"persona_id": "zeus-orchestrator", "name": "Zeus Orchestrator", "role": "Orchestrator & Ship Master", "status": "Standby"},
        {"persona_id": "athena-planner", "name": "Athena Planner", "role": "Architect & Spec Planner", "status": "Active"},
        {"persona_id": "hephaestus-coder", "name": "Hephaestus Coder", "role": "Core Implementer & Builder", "status": "Standby"},
        {"persona_id": "heracles-tester", "name": "Heracles Tester", "role": "Verification & QA Tester", "status": "Standby"},
        {"persona_id": "hermes-scout", "name": "Hermes Scout", "role": "Explorer & Fast Scout", "status": "Standby"},
        {"persona_id": "themis-reviewer", "name": "Themis Reviewer", "role": "Quality & Security Reviewer", "status": "Standby"},
    ])

    update = {
        "update_id": 14,
        "message": {
            "message_id": 27,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/agents",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Armada Subagen Olympus" in kwargs["text"]
    assert "Zeus Orchestrator" in kwargs["text"]
    assert "Athena Planner" in kwargs["text"]
    assert "Hephaestus Coder" in kwargs["text"]
    assert "Heracles Tester" in kwargs["text"]
    assert "Hermes Scout" in kwargs["text"]
    assert "Themis Reviewer" in kwargs["text"]


def test_handle_provider_command_list(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_providers = MagicMock(return_value=[
        {"id": "prov_gemini", "name": "Google Gemini", "model": "gemini-1.5-pro", "is_active": True},
        {"id": "prov_openai", "name": "OpenAI", "model": "gpt-4o", "is_active": False},
        {"id": "prov_ollama", "name": "Ollama Local", "model": "llama3", "is_active": False},
    ])

    update = {
        "update_id": 15,
        "message": {
            "message_id": 28,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/provider",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Google Gemini" in kwargs["text"]
    assert "⭐ (Aktif)" in kwargs["text"]
    assert "OpenAI" in kwargs["text"]
    reply_markup = kwargs.get("reply_markup", {})
    keyboard = reply_markup.get("inline_keyboard", [])
    callback_datas = [btn["callback_data"] for row in keyboard for btn in row]
    assert "provider:set:prov_gemini" in callback_datas
    assert "provider:set:prov_openai" in callback_datas


def test_handle_provider_command_direct_switch(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_provider = MagicMock()

    update = {
        "update_id": 16,
        "message": {
            "message_id": 29,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/provider prov_ollama",
        },
    }
    handler.handle_update(update)

    handler.set_provider.assert_called_once_with("prov_ollama")
    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Provider LLM Aktif Diubah" in kwargs["text"]
    assert "prov_ollama" in kwargs["text"]


def test_handle_provider_callback_query(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_provider = MagicMock()

    update = {
        "update_id": 17,
        "callback_query": {
            "id": "cb_prov_1",
            "from": {"id": 12345},
            "message": {"message_id": 65, "chat": {"id": 12345}, "text": "Pilih provider:"},
            "data": "provider:set:prov_anthropic",
        },
    }
    handler.handle_update(update)

    handler.set_provider.assert_called_once_with("prov_anthropic")
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_prov_1", text="Provider aktif diubah ke: prov_anthropic"
    )
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "prov_anthropic" in kwargs["text"]


def test_handle_testprovider_command_success(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.test_provider = MagicMock(return_value={
        "status": "ok",
        "provider": "OpenAI Direct",
        "model": "gpt-4o",
        "latency_ms": 128.4,
        "detail": "Connection OK",
    })

    update = {
        "update_id": 18,
        "message": {
            "message_id": 30,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/testprovider",
        },
    }
    handler.handle_update(update)

    assert bot_client.send_message.call_count == 2
    second_call = bot_client.send_message.call_args_list[1]
    _, kwargs = second_call
    assert "Uji Konektivitas Berhasil" in kwargs["text"]
    assert "OpenAI Direct" in kwargs["text"]
    assert "gpt-4o" in kwargs["text"]
    assert "128.4 ms" in kwargs["text"]


def test_handle_testprovider_command_error(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.test_provider = MagicMock(return_value={
        "status": "error",
        "provider": "Local Ollama",
        "model": "llama3",
        "latency_ms": 1500.0,
        "detail": "Connection refused on port 11434",
    })

    update = {
        "update_id": 19,
        "message": {
            "message_id": 31,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/testprovider",
        },
    }
    handler.handle_update(update)

    assert bot_client.send_message.call_count == 2
    second_call = bot_client.send_message.call_args_list[1]
    _, kwargs = second_call
    assert "Uji Konektivitas Gagal" in kwargs["text"]
    assert "Connection refused" in kwargs["text"]


def test_handle_help_contains_new_commands(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)

    update = {
        "update_id": 20,
        "message": {
            "message_id": 32,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/help",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    text = kwargs["text"]
    assert "/repo" in text
    assert "/mode" in text
    assert "/agents" in text
    assert "/provider" in text
    assert "/testprovider" in text


def test_mode_endpoint_get_and_post(tmp_path: Path):
    import json
    import os
    from unittest.mock import patch
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    try:
        django.setup()
    except Exception:
        pass
    from django.test import RequestFactory
    from api import views
    from api.project_store import ProjectStore
    from api.services import GatewayService

    rf = RequestFactory()
    store = ProjectStore(tmp_path / "aegis.db")
    service = GatewayService(project_store=store)

    with patch("api.views.get_service", return_value=service):
        # 1. GET /api/mode -> default "ask"
        get_req = rf.get("/api/mode")
        get_resp = views.mode_view(get_req)
        assert get_resp.status_code == 200
        get_data = json.loads(get_resp.content)
        assert get_data == {"status": "ok", "mode": "ask"}

        # 2. POST /api/mode -> set to "agents"
        post_req = rf.post(
            "/api/mode",
            data=json.dumps({"mode": "agents"}),
            content_type="application/json",
        )
        post_resp = views.mode_view(post_req)
        assert post_resp.status_code == 200
        post_data = json.loads(post_resp.content)
        assert post_data == {"status": "ok", "mode": "agents"}
        assert service.get_operational_mode() == "agents"

        # 3. POST /api/mode -> invalid mode returns 400
        invalid_req = rf.post(
            "/api/mode",
            data=json.dumps({"mode": "invalid"}),
            content_type="application/json",
        )
        invalid_resp = views.mode_view(invalid_req)
        assert invalid_resp.status_code == 400


def test_handle_model_command_with_models(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_models = MagicMock(return_value=[
        {"name": "claude-sonnet-4-6", "is_active": True},
        {"name": "gemini-3.1-pro-high", "is_active": False},
    ])

    update = {
        "update_id": 21,
        "message": {
            "message_id": 40,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/model",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Daftar Model Terkonfigurasi di IDE" in kwargs["text"]
    assert "claude-sonnet-4-6" in kwargs["text"]
    reply_markup = kwargs.get("reply_markup", {})
    assert "inline_keyboard" in reply_markup
    buttons = reply_markup["inline_keyboard"]
    assert len(buttons) == 2
    assert buttons[0][0]["callback_data"] == "model:set:claude-sonnet-4-6"
    assert buttons[1][0]["callback_data"] == "model:set:gemini-3.1-pro-high"


def test_handle_model_callback(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_active_model = MagicMock()

    update = {
        "update_id": 22,
        "callback_query": {
            "id": "cb_mod_1",
            "from": {"id": 12345},
            "message": {"message_id": 66, "chat": {"id": 12345}, "text": "Pilih model:"},
            "data": "model:set:claude-sonnet-4-6",
        },
    }
    handler.handle_update(update)

    handler.set_active_model.assert_called_once_with("claude-sonnet-4-6")
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_mod_1", text="Model aktif diubah ke: claude-sonnet-4-6"
    )
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Model LLM Diperbarui" in kwargs["text"]
    assert "claude-sonnet-4-6" in kwargs["text"]


def test_handle_skills_command(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.get_skills = MagicMock(return_value=[
        {"id": "code-review-and-quality", "name": "Code Review & Quality", "description": "Review code", "is_active": True},
        {"id": "test-driven-development", "name": "Test Driven Development", "description": "TDD loop", "is_active": False},
    ])

    update = {
        "update_id": 23,
        "message": {
            "message_id": 41,
            "chat": {"id": 12345},
            "from": {"id": 12345},
            "text": "/skills",
        },
    }
    handler.handle_update(update)

    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert "Daftar Skills Resmi AegisCode" in kwargs["text"]
    assert "Code Review & Quality" in kwargs["text"]
    reply_markup = kwargs.get("reply_markup", {})
    assert "inline_keyboard" in reply_markup
    buttons = reply_markup["inline_keyboard"]
    assert len(buttons) == 2
    assert buttons[0][0]["callback_data"] == "skill:set:code-review-and-quality"
    assert buttons[1][0]["callback_data"] == "skill:set:test-driven-development"


def test_handle_skill_callback(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_active_skill = MagicMock()

    update = {
        "update_id": 24,
        "callback_query": {
            "id": "cb_skl_1",
            "from": {"id": 12345},
            "message": {"message_id": 67, "chat": {"id": 12345}, "text": "Pilih skill:"},
            "data": "skill:set:spec-driven-development",
        },
    }
    handler.handle_update(update)

    handler.set_active_skill.assert_called_once_with("spec-driven-development")
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_skl_1", text="Skill aktif diubah ke: spec-driven-development"
    )
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Active Skill Diperbarui" in kwargs["text"]
    assert "spec-driven-development" in kwargs["text"]


def test_handle_provider_callback_chained_models(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.set_provider = MagicMock()
    handler.get_models = MagicMock(return_value=[
        {"name": "claude-sonnet-4-6", "is_active": True},
        {"name": "gemini-3.1-pro-high", "is_active": False},
    ])

    update = {
        "update_id": 25,
        "callback_query": {
            "id": "cb_prov_chain",
            "from": {"id": 12345},
            "message": {"message_id": 68, "chat": {"id": 12345}, "text": "Pilih provider:"},
            "data": "provider:set:antigravity",
        },
    }
    handler.handle_update(update)

    handler.set_provider.assert_called_once_with("antigravity")
    handler.get_models.assert_called_once_with("antigravity")
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_prov_chain", text="Provider aktif diubah ke: antigravity"
    )
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "antigravity" in kwargs["text"]
    assert "Silakan pilih model aktif" in kwargs["text"]
    buttons = kwargs["reply_markup"]["inline_keyboard"]
    assert buttons[0][0]["callback_data"] == "model:set:claude-sonnet-4-6"


def test_handle_prompt_retry_callback_success(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.on_prompt_retry = MagicMock(return_value=True)

    update = {
        "update_id": 26,
        "callback_query": {
            "id": "cb_retry_1",
            "from": {"id": 12345},
            "message": {"message_id": 99, "chat": {"id": 12345}, "text": "Error"},
            "data": "prompt:retry:abc12345",
        },
    }
    handler.handle_update(update)

    handler.on_prompt_retry.assert_called_once_with("abc12345", 12345)
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_retry_1", text="🔄 Mencoba kembali instruksi..."
    )


def test_handle_prompt_retry_callback_expired(test_setup):
    handler, bot_client, sec_manager, _, _, _ = test_setup
    sec_manager.save_paired_user(user_id=12345)
    handler.on_prompt_retry = MagicMock(return_value=False)

    update = {
        "update_id": 27,
        "callback_query": {
            "id": "cb_retry_2",
            "from": {"id": 12345},
            "message": {"message_id": 100, "chat": {"id": 12345}, "text": "Error"},
            "data": "prompt:retry:expired99",
        },
    }
    handler.handle_update(update)

    handler.on_prompt_retry.assert_called_once_with("expired99", 12345)
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_retry_2", text="⚠️ Cache percobaan ulang sudah kedaluwarsa.", show_alert=True
    )

