from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path
from django.test import RequestFactory

# Pastikan DJANGO_SETTINGS_MODULE diatur jika belum
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from api import telegram_views


@pytest.fixture
def rf():
    return RequestFactory()


def test_telegram_status_unconfigured(rf):
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}):
        req = rf.get("/api/telegram/status")
        resp = telegram_views.telegram_status(req)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["configured"] is False
        assert data["is_paired"] is False


def test_telegram_status_configured_and_paired(rf, tmp_path: Path):
    storage_path = tmp_path / "paired.json"
    from agent_ai.runtime.telegram.security import TelegramSecurityManager
    sec = TelegramSecurityManager(storage_path=storage_path)
    sec.save_paired_user(user_id=12345, username="adit_test")

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token_123"}), \
         patch("api.telegram_views.get_security_manager", return_value=sec), \
         patch("api.telegram_views.get_bot_username", return_value="Aegis_bot"):

        req = rf.get("/api/telegram/status")
        resp = telegram_views.telegram_status(req)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["configured"] is True
        assert data["is_paired"] is True
        assert data["bot_username"] == "Aegis_bot"
        assert data["paired_user"]["user_id"] == 12345
        assert data["paired_user"]["username"] == "adit_test"


def test_telegram_pairing_qr_endpoint(rf):
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token_123"}), \
         patch("api.telegram_views.get_bot_username", return_value="Aegis_bot"):

        req = rf.get("/api/telegram/pairing-qr")
        resp = telegram_views.telegram_pairing_qr(req)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "deep_link" in data
        assert "Aegis_bot" in data["deep_link"]
        assert "<svg" in data["qr_svg"]
        assert data["expires_in"] == 300


def test_telegram_unlink_endpoint(rf, tmp_path: Path):
    storage_path = tmp_path / "paired.json"
    from agent_ai.runtime.telegram.security import TelegramSecurityManager
    sec = TelegramSecurityManager(storage_path=storage_path)
    sec.save_paired_user(user_id=12345)

    with patch("api.telegram_views.get_security_manager", return_value=sec):
        req = rf.post("/api/telegram/unlink")
        resp = telegram_views.telegram_unlink(req)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["success"] is True
        assert sec.is_authorized(12345) is False
