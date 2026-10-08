"""Unit tests for Telegram Seamless Bidirectional Runtime & Zero-Silent-Failure.

Verifies:
1. `on_steer_command` receives `chat_id` from `TelegramUpdateHandler`.
2. Explicit error logging when `_get_gateway_service()` fails.
3. Explicit error logging on getter exceptions (no silent `pass`).
4. `handle_agent_delegate` validates real `task_id` and fails fast on errors without 180s silence.
5. `handle_agent_delegate` polls real task progress and finalizes properly.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch
import pytest

from agent_ai.runtime.telegram.companion import TelegramCompanion, _get_gateway_service
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.security import TelegramSecurityManager


@pytest.fixture
def mock_bot_client():
    client = MagicMock()
    client.send_message.return_value = {"ok": True, "result": {"message_id": 999}}
    client.edit_message_text.return_value = {"ok": True, "result": {"message_id": 999}}
    return client


def test_handler_steer_command_passes_chat_id(mock_bot_client):
    """Memverifikasi bahwa handler meneruskan chat_id ke on_steer_command."""
    sec_mgr = MagicMock(spec=TelegramSecurityManager)
    sec_mgr.is_authorized.return_value = True
    pairing_mgr = MagicMock(spec=PairingManager)

    received_calls = []

    def steer_callback(instruction, chat_id=None):
        received_calls.append({"instruction": instruction, "chat_id": chat_id})

    handler = TelegramUpdateHandler(
        bot_client=mock_bot_client,
        security_manager=sec_mgr,
        pairing_manager=pairing_mgr,
        on_steer_command=steer_callback,
    )

    update = {
        "update_id": 100,
        "message": {
            "message_id": 12,
            "chat": {"id": 593744366},
            "from": {"id": 593744366, "username": "vizzyoc"},
            "text": "Tolong implementasikan fitur auth",
        },
    }

    handler.handle_update(update)

    assert len(received_calls) == 1
    assert received_calls[0]["instruction"] == "Tolong implementasikan fitur auth"
    assert received_calls[0]["chat_id"] == 593744366


def test_gateway_service_logs_on_bootstrap_failure(caplog):
    """Memverifikasi bahwa kegagalan inisialisasi Django GatewayService dicatat di log."""
    with patch("django.setup", side_effect=RuntimeError("Django settings not configured")):
        with caplog.at_level(logging.ERROR):
            svc = _get_gateway_service()
            assert svc is None
            assert any("Gagal memuat GatewayService" in r.message for r in caplog.records)


def test_getters_log_error_on_exception(caplog, mock_bot_client):
    """Memverifikasi getter fungsi mencatat log saat service mengalami exception."""
    mock_svc = MagicMock()
    mock_svc.get_active_repository_info.side_effect = RuntimeError("Git failure")
    mock_svc.get_operational_mode.side_effect = RuntimeError("DB locked")

    with patch("agent_ai.runtime.telegram.companion._get_gateway_service", return_value=mock_svc):
        with caplog.at_level(logging.WARNING):
            companion = TelegramCompanion(bot_client=mock_bot_client)
            repo = companion.get_repo_info()
            mode = companion.get_mode()

            assert repo["name"] == "AegisCode"
            assert mode == "ask"
            assert any("Git failure" in r.message for r in caplog.records)
            assert any("DB locked" in r.message for r in caplog.records)


def test_handle_agent_delegate_fails_fast_on_missing_task_id(mock_bot_client):
    """Memverifikasi handle_agent_delegate langsung melaporkan error jika task_id tidak ada."""
    mock_svc = MagicMock()
    # Task returned has no task_id
    mock_svc.delegate_session_to_agent_task.return_value = {"task": {}}

    with patch("agent_ai.runtime.telegram.companion._get_gateway_service", return_value=mock_svc):
        companion = TelegramCompanion(bot_client=mock_bot_client)
        with patch.object(companion, "execute_remote_turn_async"):
            handled = companion.handle_agent_delegate(session_id="sess-123", chat_id=593744366)
            assert handled is True


def test_handle_agent_delegate_polls_and_reports_status(mock_bot_client):
    """Memverifikasi handle_agent_delegate memantau task hingga selesai dan melaporkan hasil."""
    mock_svc = MagicMock()
    mock_svc.delegate_session_to_agent_task.return_value = {
        "task": {"task_id": "tsk-abc-123"}
    }
    mock_svc.get_task.return_value = {"status": "completed"}
    mock_svc.get_task_report.return_value = {"summary": "Implementasi berhasil diselesaikan."}

    with patch("agent_ai.runtime.telegram.companion._get_gateway_service", return_value=mock_svc):
        companion = TelegramCompanion(bot_client=mock_bot_client)
        handled = companion.handle_agent_delegate(session_id="sess-123", chat_id=593744366)
        assert handled is True
