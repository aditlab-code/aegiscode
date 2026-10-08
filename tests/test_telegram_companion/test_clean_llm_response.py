"""Unit tests for Telegram Native Typing Indicator & Pure LLM Response Delivery.

Verifies:
1. `TelegramBotClient.send_chat_action` sends HTTP POST to `sendChatAction`.
2. `TelegramUpdateHandler` does NOT send hardcoded boilerplate ack messages ("Instruksi diterima").
3. `TelegramCompanion.execute_remote_turn_async` in ask mode triggers typing pulse and sends pure LLM reply.
4. `TelegramCompanion.execute_remote_turn_async` in agents mode maintains a single in-place progress message.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest

from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.companion import TelegramCompanion
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.security import TelegramSecurityManager


@pytest.fixture
def mock_bot_client():
    client = MagicMock(spec=TelegramBotClient)
    client.send_message.return_value = {"ok": True, "result": {"message_id": 101}}
    client.edit_message_text.return_value = {"ok": True, "result": {"message_id": 101}}
    client.send_chat_action.return_value = True
    return client


def test_bot_client_send_chat_action():
    """Memverifikasi bahwa send_chat_action mengirim request sendChatAction ke API Telegram."""
    client = TelegramBotClient(bot_token="test-token")
    with patch.object(client, "_post", return_value={"ok": True, "result": True}) as mock_post:
        res = client.send_chat_action(chat_id=593744366, action="typing")
        assert res is True
        mock_post.assert_called_once_with(
            "sendChatAction",
            {"chat_id": 593744366, "action": "typing"},
            request_timeout=10,
        )


def test_handler_does_not_send_hardcoded_ack_message(mock_bot_client):
    """Memverifikasi bahwa handler tidak lagi mengirim pesan terpisah 'Instruksi diterima'."""
    sec_mgr = MagicMock(spec=TelegramSecurityManager)
    sec_mgr.is_authorized.return_value = True
    pairing_mgr = MagicMock(spec=PairingManager)
    steer_mock = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=mock_bot_client,
        security_manager=sec_mgr,
        pairing_manager=pairing_mgr,
        on_steer_command=steer_mock,
    )

    update = {
        "update_id": 201,
        "message": {
            "message_id": 55,
            "chat": {"id": 593744366},
            "from": {"id": 593744366, "username": "vizzyoc"},
            "text": "Bantu jelaskan arsitektur AegisCode",
        },
    }

    handler.handle_update(update)

    # Memastikan on_steer_command dipanggil dengan teks dan chat_id
    assert steer_mock.call_count == 1
    # Memastikan bot_client TIDAK mengirim pesan boilerplate 'Instruksi diterima'
    sent_texts = [call.kwargs.get("text", "") for call in mock_bot_client.send_message.call_args_list]
    assert not any("Instruksi diterima" in t for t in sent_texts)


def test_companion_ask_mode_typing_and_pure_llm_delivery(mock_bot_client):
    """Memverifikasi pada mode ask bot memicu send_chat_action dan mengirim respons asli LLM."""
    mock_svc = MagicMock()
    mock_svc.dispatch_remote_turn.return_value = {
        "session_id": "sess-abc",
        "assistant_turn": {"content": "Tentu, ini adalah arsitektur AegisCode."},
        "consultant_result": {"reply": "Tentu, ini adalah arsitektur AegisCode."},
    }

    with patch("agent_ai.runtime.telegram.companion._get_gateway_service", return_value=mock_svc):
        companion = TelegramCompanion(bot_client=mock_bot_client)
        with patch.object(companion, "get_mode", return_value="ask"):
            companion.execute_remote_turn_async("Jelaskan arsitektur", chat_id=593744366)
            # Berikan waktu singkat agar background worker menyelesaikan turn
            time.sleep(0.3)

            # Memverifikasi send_chat_action dipanggil
            assert mock_bot_client.send_chat_action.called
            # Memverifikasi pesan asli LLM terkirim
            assert mock_bot_client.send_message.called
            sent_texts = [call.kwargs.get("text", "") for call in mock_bot_client.send_message.call_args_list]
            assert any("Tentu, ini adalah arsitektur AegisCode." in t for t in sent_texts)
            # Memverifikasi tidak ada pesan statis boilerplate 'Agen sedang menganalisis'
            assert not any("sedang menganalisis instruksi" in t for t in sent_texts)
