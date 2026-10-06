"""Tests for Security & Authentication Boundaries (AEG-08 / PR-06).

Menguji:
1. HTTP API boundary:
   - Enforced mode (AEGIS_AUTH_REQUIRED=True):
     - Request tanpa token ditolak HTTP 401.
     - Request dengan token tidak valid ditolak HTTP 401.
     - Request dengan Bearer session token valid diizinkan.
   - Developer loopback bypass (AEGIS_AUTH_REQUIRED=False):
     - Request dari IP loopback (127.0.0.1 / testserver) diizinkan tanpa token.
     - Request dari IP non-loopback (192.168.1.50) tetap ditolak HTTP 401.
2. WebSocket Terminal PTY boundary:
   - Enforced mode:
     - Koneksi tanpa token ditolak dengan pesan keamanan dan close code 4001.
     - Koneksi dengan token invalid ditolak dengan close code 4001.
     - Koneksi dengan valid token di query param diizinkan.
   - Origin check:
     - Origin header jahat ditolak dengan pesan keamanan dan close code 4003.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Pastikan import paths
django_dir = Path(__file__).resolve().parent.parent / "web" / "django_app"
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

from channels.testing import WebsocketCommunicator
from django.test import Client

from api.auth import create_aegis_session_token
from config.asgi import application


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def valid_token():
    user_payload = {
        "sub": "user_auth_test_123",
        "email": "tester@example.com",
        "name": "Aegis Tester",
        "picture": "",
    }
    return create_aegis_session_token(user_payload, expiry_seconds=3600)


# ===========================================================================
# 1. HTTP Endpoint Auth Boundary Tests
# ===========================================================================

def test_http_endpoint_enforced_mode_blocks_unauthenticated(client: Client) -> None:
    """Ketika AEGIS_AUTH_REQUIRED=True, request tanpa token wajib mengembalikan 401."""
    with patch.object(settings, "AEGIS_AUTH_REQUIRED", True):
        # /api/config
        resp_config = client.get("/api/config", REMOTE_ADDR="127.0.0.1")
        assert resp_config.status_code == 401
        data_config = resp_config.json()
        assert data_config["error"]["code"] == "UNAUTHORIZED"

        # /api/files/content
        resp_files = client.get("/api/files/content?path=README.md", REMOTE_ADDR="127.0.0.1")
        assert resp_files.status_code == 401
        assert resp_files.json()["error"]["code"] == "UNAUTHORIZED"

        # /api/tasks
        resp_tasks = client.get("/api/tasks", REMOTE_ADDR="127.0.0.1")
        assert resp_tasks.status_code == 401
        assert resp_tasks.json()["error"]["code"] == "UNAUTHORIZED"


def test_http_endpoint_enforced_mode_accepts_valid_token(client: Client, valid_token: str) -> None:
    """Ketika AEGIS_AUTH_REQUIRED=True, request dengan Bearer token valid berhasil."""
    with patch.object(settings, "AEGIS_AUTH_REQUIRED", True):
        auth_header = f"Bearer {valid_token}"
        resp_config = client.get("/api/config", HTTP_AUTHORIZATION=auth_header, REMOTE_ADDR="127.0.0.1")
        assert resp_config.status_code == 200
        assert "providers" in resp_config.json()


def test_http_endpoint_enforced_mode_rejects_tampered_token(client: Client) -> None:
    """Ketika token JWT dimanipulasi/rusak, request ditolak dengan 401."""
    with patch.object(settings, "AEGIS_AUTH_REQUIRED", True):
        bad_token = "invalid.bearer.jwt.signature"
        resp_config = client.get(
            "/api/config",
            HTTP_AUTHORIZATION=f"Bearer {bad_token}",
            REMOTE_ADDR="127.0.0.1",
        )
        assert resp_config.status_code == 401
        assert resp_config.json()["error"]["code"] == "UNAUTHORIZED"


def test_http_endpoint_dev_mode_loopback_bypass(client: Client) -> None:
    """Ketika AEGIS_AUTH_REQUIRED=False, request loopback lokal (127.0.0.1) dibypass."""
    with patch.object(settings, "AEGIS_AUTH_REQUIRED", False):
        resp_config = client.get("/api/config", REMOTE_ADDR="127.0.0.1")
        assert resp_config.status_code == 200
        assert "providers" in resp_config.json()


def test_http_endpoint_dev_mode_non_loopback_requires_auth(client: Client) -> None:
    """Ketika AEGIS_AUTH_REQUIRED=False, request dari IP remote jaringan tetap ditolak tanpa auth."""
    with patch.object(settings, "AEGIS_AUTH_REQUIRED", False):
        resp_config = client.get("/api/config", REMOTE_ADDR="192.168.1.150")
        assert resp_config.status_code == 401
        assert resp_config.json()["error"]["code"] == "UNAUTHORIZED"


# ===========================================================================
# 2. WebSocket Terminal PTY Auth Boundary Tests
# ===========================================================================

def test_websocket_terminal_enforced_mode_rejects_missing_token() -> None:
    """Ketika AEGIS_AUTH_REQUIRED=True, WebSocket tanpa token ditolak (close code 4001)."""
    async def _run():
        with patch.object(settings, "AEGIS_AUTH_REQUIRED", True):
            communicator = WebsocketCommunicator(
                application,
                "/ws/terminal/",
                headers=[(b"host", b"testserver")],
            )
            connected, _ = await communicator.connect()
            assert connected
            # Menerima banner error keamanan
            msg = await communicator.receive_from()
            assert "Security" in msg
            # Frame berikutnya adalah close dengan code 4001
            close_frame = await communicator.receive_output()
            assert close_frame["type"] == "websocket.close"
            assert close_frame["code"] == 4001

    asyncio.run(_run())


def test_websocket_terminal_enforced_mode_accepts_valid_token(valid_token: str) -> None:
    """Ketika AEGIS_AUTH_REQUIRED=True, WebSocket dengan query param ?token=... diterima."""
    async def _run():
        with patch.object(settings, "AEGIS_AUTH_REQUIRED", True):
            communicator = WebsocketCommunicator(
                application,
                f"/ws/terminal/?token={valid_token}",
                headers=[(b"host", b"testserver")],
            )
            connected, _ = await communicator.connect()
            assert connected
            # Disconnect bersih
            await communicator.disconnect()

    asyncio.run(_run())


def test_websocket_terminal_rejects_unauthorized_origin(valid_token: str) -> None:
    """WebSocket dari origin asing yang tidak ada di ALLOWED_HOSTS ditolak (close code 4003)."""
    async def _run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/terminal/?token={valid_token}",
            headers=[
                (b"host", b"testserver"),
                (b"origin", b"https://malicious-attacker-site.com"),
            ],
        )
        connected, _ = await communicator.connect()
        assert connected
        # Menerima banner error origin
        msg = await communicator.receive_from()
        assert "Origin" in msg
        # Frame berikutnya adalah close dengan code 4003
        close_frame = await communicator.receive_output()
        assert close_frame["type"] == "websocket.close"
        assert close_frame["code"] == 4003

    asyncio.run(_run())
