"""Dedicated test suite for Telegram Remote Skill Delegation Bridge to IDE Agents.

Non-redundant tests focusing strictly on the delegation flow between Telegram and IDE backend.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
try:
    import django
    django.setup()
except Exception:
    pass

from agent_ai.runtime.telegram.stream_relay import TelegramStreamRelay
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.companion import TelegramCompanion


def test_stream_relay_finalize_with_delegation():
    """Memverifikasi finalize_with_delegation menyertakan tombol inline delegasi ke agen IDE."""
    bot_client = MagicMock()
    bot_client.send_message.return_value = {"ok": True, "result": {"message_id": 201}}

    relay = TelegramStreamRelay(
        bot_client=bot_client,
        chat_id=12345,
        throttle_interval=0.5,
    )

    relay.finalize_with_delegation("Kesimpulan sesi: bangun fitur auth", "sess-test-888")

    assert relay.is_completed is True
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Kesimpulan sesi: bangun fitur auth" in kwargs["text"]
    assert "reply_markup" in kwargs
    buttons = kwargs["reply_markup"]["inline_keyboard"]
    assert len(buttons) == 1
    assert buttons[0][0]["text"] == "🚀 Delegasikan ke Agen IDE"
    assert buttons[0][0]["callback_data"] == "agent:delegate:sess-test-888"


def test_handler_agent_delegate_callback_success():
    """Memverifikasi handler callback agent:delegate meneruskan session_id ke on_agent_delegate."""
    bot_client = MagicMock()
    sec_manager = MagicMock()
    sec_manager.is_authorized.return_value = True
    pairing_mgr = MagicMock()

    delegate_mock = MagicMock(return_value=True)

    handler = TelegramUpdateHandler(
        bot_client=bot_client,
        security_manager=sec_manager,
        pairing_manager=pairing_mgr,
        on_agent_delegate=delegate_mock,
    )

    update = {
        "update_id": 50,
        "callback_query": {
            "id": "cb_del_1",
            "from": {"id": 12345},
            "message": {"message_id": 202, "chat": {"id": 12345}, "text": "Hasil Wawancara"},
            "data": "agent:delegate:sess-xyz-99",
        },
    }

    handler.handle_update(update)

    delegate_mock.assert_called_once_with("sess-xyz-99", 12345)
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_del_1",
        text="🚀 Tugas berhasil didelegasikan ke Agen IDE!",
    )


def test_handler_agent_delegate_callback_failure():
    """Memverifikasi feedback alert saat on_agent_delegate gagal menemukan sesi."""
    bot_client = MagicMock()
    sec_manager = MagicMock()
    sec_manager.is_authorized.return_value = True
    pairing_mgr = MagicMock()

    delegate_mock = MagicMock(return_value=False)

    handler = TelegramUpdateHandler(
        bot_client=bot_client,
        security_manager=sec_manager,
        pairing_manager=pairing_mgr,
        on_agent_delegate=delegate_mock,
    )

    update = {
        "update_id": 51,
        "callback_query": {
            "id": "cb_del_2",
            "from": {"id": 12345},
            "message": {"message_id": 203, "chat": {"id": 12345}, "text": "Hasil Wawancara"},
            "data": "agent:delegate:sess-notfound",
        },
    }

    handler.handle_update(update)

    delegate_mock.assert_called_once_with("sess-notfound", 12345)
    bot_client.answer_callback_query.assert_called_once_with(
        callback_query_id="cb_del_2",
        text="⚠️ Sesi tidak ditemukan atau gagal didelegasikan.",
        show_alert=True,
    )


def test_gateway_delegate_session_to_agent_task():
    """Memverifikasi GatewayService.delegate_session_to_agent_task membuat task mode agent."""
    from api.services import GatewayService

    gw = GatewayService.__new__(GatewayService)
    gw._unified_session_store = MagicMock()
    gw.get_active_provider = MagicMock(return_value="prov-test")
    gw.get_active_model = MagicMock(return_value="model-test")
    gw.create_unified_turn = MagicMock(return_value={"task": {"task_id": "TASK-123"}})

    # Mock Session dengan turns
    turn1 = MagicMock()
    turn1.role = "user"
    turn1.content = "Buatkan arsitektur cache Redis"
    turn2 = MagicMock()
    turn2.role = "assistant"
    turn2.content = "Rancangan cache Redis telah disepakati"

    sess_mock = MagicMock()
    sess_mock.project_id = "proj-1"
    sess_mock.turns = [turn1, turn2]
    gw.unified_session_store.get_session.return_value = sess_mock

    res = gw.delegate_session_to_agent_task("sess-1")

    assert res["task"]["task_id"] == "TASK-123"
    gw.create_unified_turn.assert_called_once()
    _, kwargs = gw.create_unified_turn.call_args
    assert kwargs["session_id"] == "sess-1"
    assert kwargs["mode"] == "agent"
    assert "Implementasikan kesepakatan" in kwargs["content"]
    assert "Buatkan arsitektur cache Redis" in kwargs["content"]


def test_companion_should_offer_delegation():
    """Memverifikasi companion._should_offer_delegation mendeteksi Q&A / summary kesimpulan."""
    companion = TelegramCompanion.__new__(TelegramCompanion)
    companion.get_active_skill = MagicMock(return_value="interview-me")

    assert companion._should_offer_delegation("Q: Apa targetnya? GUESS: Meningkatkan performa") is True
    assert companion._should_offer_delegation("Berikut ringkasan spesifikasi yang telah disepakati") is True

    companion.get_active_skill = MagicMock(return_value=None)
    assert companion._should_offer_delegation("Halo, selamat pagi") is False
    assert companion._should_offer_delegation("Outcome: Fitur checkout dipercepat") is True
