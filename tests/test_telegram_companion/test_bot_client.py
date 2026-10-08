from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from agent_ai.runtime.telegram.bot_client import TelegramBotClient


def test_get_me_success():
    client = TelegramBotClient(bot_token="test_token_123")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": {"id": 98765, "is_bot": True, "username": "AegisCompanion_bot", "first_name": "Aegis"},
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        info = client.get_me()
        assert info["username"] == "AegisCompanion_bot"
        assert info["id"] == 98765
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token_123/getMe",
            json={},
            timeout=10,
        )


def test_get_updates_tracks_offset():
    client = TelegramBotClient(bot_token="test_token_123", timeout=5)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {"update_id": 100, "message": {"message_id": 1, "text": "hello"}},
            {"update_id": 101, "message": {"message_id": 2, "text": "world"}},
        ],
    }

    with patch("requests.post", return_value=mock_resp):
        updates = client.get_updates()
        assert len(updates) == 2
        assert client._offset == 102


def test_send_message_with_keyboard():
    client = TelegramBotClient(bot_token="test_token_123")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 42}}

    reply_markup = {
        "inline_keyboard": [[{"text": "Allow", "callback_data": "allow_1"}]]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = client.send_message(
            chat_id=12345,
            text="Need approval",
            reply_markup=reply_markup,
        )
        assert res["message_id"] == 42
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token_123/sendMessage",
            json={
                "chat_id": 12345,
                "text": "Need approval",
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            },
            timeout=10,
        )


def test_answer_callback_query():
    client = TelegramBotClient(bot_token="test_token_123")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": True}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client.answer_callback_query(callback_query_id="cb_99", text="Action received")
        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottest_token_123/answerCallbackQuery",
            json={"callback_query_id": "cb_99", "text": "Action received"},
            timeout=10,
        )


def test_background_polling_starts_and_stops():
    client = TelegramBotClient(bot_token="test_token_123", timeout=1)
    updates_received = []

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": [{"update_id": 500, "message": {"text": "ping"}}],
    }

    with patch("requests.post", return_value=mock_resp):
        client.start_polling(on_update=lambda u: updates_received.append(u))
        assert client.is_polling() is True
        time.sleep(0.1)
        client.stop_polling()
        assert client.is_polling() is False
        assert len(updates_received) >= 1
