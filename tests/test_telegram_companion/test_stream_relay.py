from __future__ import annotations

import time
from unittest.mock import MagicMock
import pytest

from agent_ai.runtime.telegram.stream_relay import TelegramStreamRelay, sanitize_telegram_html


def test_sanitize_telegram_html():
    assert sanitize_telegram_html("Hello <world>") == "Hello &lt;world&gt;"
    assert sanitize_telegram_html("a & b") == "a &amp; b"
    assert sanitize_telegram_html("") == ""


def test_stream_relay_initialization():
    bot_client = MagicMock()
    bot_client.send_message.return_value = {"ok": True, "result": {"message_id": 999}}

    relay = TelegramStreamRelay(
        bot_client=bot_client,
        chat_id=12345,
        throttle_interval=0.5,
        initial_status="💭 Sedang berpikir...",
    )

    bot_client.send_message.assert_called_once_with(
        chat_id=12345,
        text="💭 Sedang berpikir...",
    )
    assert relay.message_id == 999


def test_stream_relay_throttling():
    bot_client = MagicMock()
    bot_client.send_message.return_value = {"ok": True, "result": {"message_id": 100}}

    relay = TelegramStreamRelay(
        bot_client=bot_client,
        chat_id=12345,
        throttle_interval=0.5,
    )

    # First chunk immediately triggers edit if last_update_time was 0
    relay.append_chunk("Halo ")
    assert bot_client.edit_message_text.call_count == 1

    # Second chunk immediately following (delta time < 0.5s) should NOT trigger edit
    relay.append_chunk("dunia!")
    assert bot_client.edit_message_text.call_count == 1

    # After waiting throttle interval, setting content or finalizing will flush
    time.sleep(0.55)
    relay.append_chunk(" Lagi.")
    assert bot_client.edit_message_text.call_count == 2


def test_stream_relay_finalize():
    bot_client = MagicMock()
    bot_client.send_message.return_value = {"ok": True, "result": {"message_id": 101}}

    relay = TelegramStreamRelay(
        bot_client=bot_client,
        chat_id=12345,
        throttle_interval=0.5,
    )

    relay.finalize("Jawaban lengkap dari agen.")
    assert relay.is_completed is True
    assert bot_client.edit_message_text.call_count == 1
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Jawaban lengkap dari agen." in kwargs["text"]
    assert "Aegis Agent" in kwargs["text"]


def test_stream_relay_error():
    bot_client = MagicMock()
    bot_client.send_message.return_value = {"ok": True, "result": {"message_id": 102}}

    relay = TelegramStreamRelay(
        bot_client=bot_client,
        chat_id=12345,
        throttle_interval=0.5,
    )

    relay.error("Koneksi LLM terputus")
    assert relay.is_completed is True
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Terjadi Kesalahan" in kwargs["text"]
    assert "Koneksi LLM terputus" in kwargs["text"]


def test_stream_relay_error_with_retry():
    bot_client = MagicMock()
    bot_client.send_message.return_value = {"ok": True, "result": {"message_id": 103}}

    relay = TelegramStreamRelay(
        bot_client=bot_client,
        chat_id=12345,
        throttle_interval=0.5,
    )

    relay.error_with_retry("Model tidak merespons", "prompt:retry:abc12345")
    assert relay.is_completed is True
    bot_client.edit_message_text.assert_called_once()
    _, kwargs = bot_client.edit_message_text.call_args
    assert "Gagal Menghubungi LLM" in kwargs["text"]
    assert "Model tidak merespons" in kwargs["text"]
    assert "reply_markup" in kwargs
    buttons = kwargs["reply_markup"]["inline_keyboard"]
    assert len(buttons) == 1
    assert buttons[0][0]["text"] == "🔄 Coba Lagi"
    assert buttons[0][0]["callback_data"] == "prompt:retry:abc12345"
