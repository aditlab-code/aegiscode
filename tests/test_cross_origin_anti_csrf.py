"""Tests for Cross-Origin Boundary & Anti-CSRF Protection (PR-SEC-2b).

Menguji:
1. Penolakan ketat request mutatif (POST/PUT/PATCH/DELETE) dari origin berbahaya (evil.com, null).
2. Penolakan request dengan header Sec-Fetch-Site: cross-site.
3. Penolakan request dengan Referer lintas-asal jahat saat Origin absen.
4. Penerimaan request mutatif dari origin sah (localhost, 127.0.0.1, tauri://localhost, tauri.localhost).
5. Ketersediaan akses programmatic CLI tanpa header browser (Origin/Referer/Sec-Fetch-Site).
6. Izin metode aman (GET/HEAD/OPTIONS) terlepas dari Origin.
7. Verifikasi unit untuk is_safe_origin dan validate_cross_origin_boundary.
8. Verifikasi integrasi WebSocket Channels origin boundary.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Pastikan path modul terdaftar
django_dir = Path(__file__).resolve().parent.parent / "web" / "django_app"
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(django_dir) not in sys.path:
    sys.path.insert(0, str(django_dir))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.test import Client, RequestFactory

try:
    django.setup()
except RuntimeError:
    pass

from channels.testing import WebsocketCommunicator
from api.auth import (
    create_aegis_session_token,
    get_ephemeral_token,
    is_safe_origin,
    validate_cross_origin_boundary,
)
from config.asgi import application


@pytest.fixture
def valid_token() -> str:
    user_payload = {
        "sub": "user_csrf_test_456",
        "email": "tester@example.com",
        "name": "Aegis Anti-CSRF Tester",
        "picture": "",
    }
    return create_aegis_session_token(user_payload, expiry_seconds=3600)


@pytest.fixture
def auth_headers(valid_token: str) -> Dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {valid_token}"}


@pytest.fixture
def client() -> Client:
    return Client()


# ===========================================================================
# 1. Unit Tests: is_safe_origin
# ===========================================================================


def test_is_safe_origin_empty_or_none() -> None:
    """Origin kosong atau None dianggap aman di layer is_safe_origin."""
    assert is_safe_origin(None) is True
    assert is_safe_origin("") is True
    assert is_safe_origin("   ") is True


def test_is_safe_origin_null_origin() -> None:
    """Origin 'null' dari sandboxed iframe atau redirect exploit wajib ditolak."""
    assert is_safe_origin("null") is False
    assert is_safe_origin("Null") is False
    assert is_safe_origin("NULL") is False


def test_is_safe_origin_tauri_schemes() -> None:
    """Skema tauri native desktop diizinkan."""
    assert is_safe_origin("tauri://localhost") is True
    assert is_safe_origin("tauri://main-window") is True
    assert is_safe_origin("http://tauri.localhost") is True
    assert is_safe_origin("https://tauri.localhost") is True


def test_is_safe_origin_local_hosts() -> None:
    """Origin localhost, loopback IP 127.0.0.1, ::1, dan testserver diizinkan."""
    assert is_safe_origin("http://localhost:5173") is True
    assert is_safe_origin("http://localhost:8000") is True
    assert is_safe_origin("http://127.0.0.1:5173") is True
    assert is_safe_origin("http://127.0.0.1:8000") is True
    assert is_safe_origin("http://[::1]:8000") is True
    assert is_safe_origin("http://testserver") is True


def test_is_safe_origin_external_malicious() -> None:
    """Origin situs eksternal berbahaya wajib ditolak."""
    assert is_safe_origin("https://evil.com") is False
    assert is_safe_origin("http://evil.com:8000") is False
    assert is_safe_origin("https://subdomain.attacker.org") is False
    assert is_safe_origin("http://not-localhost.com") is False
    assert is_safe_origin("javascript:alert(1)") is False


# ===========================================================================
# 2. Unit Tests: validate_cross_origin_boundary
# ===========================================================================


def test_validate_cross_origin_boundary_safe_methods() -> None:
    """Metode aman GET/HEAD/OPTIONS selalu diizinkan terlepas dari Origin."""
    rf = RequestFactory()
    get_req = rf.get("/api/projects", HTTP_ORIGIN="https://evil.com")
    is_valid, reason = validate_cross_origin_boundary(get_req)
    assert is_valid is True
    assert reason == ""

    head_req = rf.head("/api/projects", HTTP_ORIGIN="https://evil.com")
    is_valid, reason = validate_cross_origin_boundary(head_req)
    assert is_valid is True

    options_req = rf.options("/api/projects", HTTP_ORIGIN="https://evil.com")
    is_valid, reason = validate_cross_origin_boundary(options_req)
    assert is_valid is True


def test_validate_cross_origin_boundary_sec_fetch_site_rejection() -> None:
    """Sec-Fetch-Site: cross-site langsung ditolak sebelum memeriksa Origin."""
    rf = RequestFactory()
    req = rf.post(
        "/api/tasks",
        HTTP_SEC_FETCH_SITE="cross-site",
        HTTP_ORIGIN="http://localhost:5173",
    )
    is_valid, reason = validate_cross_origin_boundary(req)
    assert is_valid is False
    assert "Sec-Fetch-Site" in reason


def test_validate_cross_origin_boundary_referer_fallback() -> None:
    """Jika Origin kosong, fallback memeriksa Referer."""
    rf = RequestFactory()
    req = rf.post("/api/tasks", HTTP_REFERER="https://evil.com/exploit.html")
    is_valid, reason = validate_cross_origin_boundary(req)
    assert is_valid is False
    assert "Referer" in reason
    assert "evil.com" in reason


def test_validate_cross_origin_boundary_cli_request() -> None:
    """Request CLI tanpa Origin/Referer/Sec-Fetch-Site diizinkan lolos."""
    rf = RequestFactory()
    req = rf.post("/api/tasks")
    is_valid, reason = validate_cross_origin_boundary(req)
    assert is_valid is True
    assert req._origin_boundary_verified is True


# ===========================================================================
# 3. HTTP Integration Tests: Penolakan Cross-Origin & Anti-CSRF
# ===========================================================================


def test_terminal_run_rejects_evil_origin(client: Client, auth_headers: Dict[str, str]) -> None:
    """POST /api/terminal/run dengan Origin https://evil.com ditolak 403 Forbidden."""
    resp = client.post(
        "/api/terminal/run",
        data=json.dumps({"command": "id"}),
        content_type="application/json",
        HTTP_ORIGIN="https://evil.com",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "evil.com" in data["error"]["message"]


def test_tasks_rejects_evil_origin(client: Client, auth_headers: Dict[str, str]) -> None:
    """POST /api/tasks dengan Origin https://evil.com ditolak 403 Forbidden."""
    resp = client.post(
        "/api/tasks",
        data=json.dumps({"task": "Exploit task"}),
        content_type="application/json",
        HTTP_ORIGIN="https://evil.com",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "evil.com" in data["error"]["message"]


def test_projects_rejects_evil_origin(client: Client, auth_headers: Dict[str, str]) -> None:
    """POST /api/projects dengan Origin https://evil.com ditolak 403 Forbidden."""
    resp = client.post(
        "/api/projects",
        data=json.dumps({"name": "Malicious Project", "path": "/tmp"}),
        content_type="application/json",
        HTTP_ORIGIN="https://evil.com",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "evil.com" in data["error"]["message"]


def test_sessions_rejects_evil_origin(client: Client, auth_headers: Dict[str, str]) -> None:
    """POST /api/sessions dengan Origin https://evil.com ditolak 403 Forbidden."""
    resp = client.post(
        "/api/sessions",
        data=json.dumps({"title": "Malicious Session"}),
        content_type="application/json",
        HTTP_ORIGIN="https://evil.com",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "evil.com" in data["error"]["message"]


def test_post_rejects_sec_fetch_site_cross_site(client: Client, auth_headers: Dict[str, str]) -> None:
    """Request dengan Sec-Fetch-Site: cross-site ditolak 403 Forbidden."""
    resp = client.post(
        "/api/tasks",
        data=json.dumps({"task": "Cross-site task"}),
        content_type="application/json",
        HTTP_SEC_FETCH_SITE="cross-site",
        HTTP_ORIGIN="http://localhost:5173",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "Sec-Fetch-Site" in data["error"]["message"]


def test_post_rejects_null_origin(client: Client, auth_headers: Dict[str, str]) -> None:
    """Request dengan Origin: null (sandbox iframe exploit) ditolak 403 Forbidden."""
    resp = client.post(
        "/api/tasks",
        data=json.dumps({"task": "Null origin task"}),
        content_type="application/json",
        HTTP_ORIGIN="null",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "null" in data["error"]["message"]


def test_post_rejects_evil_referer_fallback(client: Client, auth_headers: Dict[str, str]) -> None:
    """Request tanpa Origin tetapi memiliki Referer jahat ditolak 403 Forbidden."""
    resp = client.post(
        "/api/tasks",
        data=json.dumps({"task": "Evil referer task"}),
        content_type="application/json",
        HTTP_REFERER="https://evil.com/attacker.html",
        **auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "Referer" in data["error"]["message"]


# ===========================================================================
# 4. HTTP Integration Tests: Penerimaan Request Sah
# ===========================================================================


def test_post_accepts_localhost_vite_origin(client: Client, auth_headers: Dict[str, str], tmp_path: Path) -> None:
    """Request sah dari Vite dev server (http://localhost:5173) diizinkan."""
    proj_dir = tmp_path / "vite_proj"
    proj_dir.mkdir()
    resp = client.post(
        "/api/projects",
        data=json.dumps({"name": "Vite Project", "path": str(proj_dir)}),
        content_type="application/json",
        HTTP_ORIGIN="http://localhost:5173",
        **auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Vite Project"


def test_post_accepts_loopback_ip_origin(client: Client, auth_headers: Dict[str, str], tmp_path: Path) -> None:
    """Request sah dari http://127.0.0.1:8000 diizinkan."""
    proj_dir = tmp_path / "loopback_proj"
    proj_dir.mkdir()
    resp = client.post(
        "/api/projects",
        data=json.dumps({"name": "Loopback Project", "path": str(proj_dir)}),
        content_type="application/json",
        HTTP_ORIGIN="http://127.0.0.1:8000",
        **auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Loopback Project"


def test_post_accepts_tauri_origin(client: Client, auth_headers: Dict[str, str], tmp_path: Path) -> None:
    """Request sah dari desktop Tauri (tauri://localhost) diizinkan."""
    proj_dir = tmp_path / "tauri_proj"
    proj_dir.mkdir()
    resp = client.post(
        "/api/projects",
        data=json.dumps({"name": "Tauri Project", "path": str(proj_dir)}),
        content_type="application/json",
        HTTP_ORIGIN="tauri://localhost",
        **auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Tauri Project"


def test_post_accepts_programmatic_cli_without_browser_headers(
    client: Client, auth_headers: Dict[str, str], tmp_path: Path
) -> None:
    """Request programmatic CLI (curl/test runner tanpa header browser) diizinkan lolos ke auth/handler."""
    proj_dir = tmp_path / "cli_proj"
    proj_dir.mkdir()
    resp = client.post(
        "/api/projects",
        data=json.dumps({"name": "CLI Project", "path": str(proj_dir)}),
        content_type="application/json",
        **auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "CLI Project"


def test_get_request_allowed_regardless_of_origin(client: Client) -> None:
    """Request metode aman (GET) tetap diizinkan terlepas dari Origin (read-only)."""
    resp = client.get(
        "/api/projects",
        HTTP_ORIGIN="https://evil.com",
    )
    assert resp.status_code == 200
    assert "projects" in resp.json()


# ===========================================================================
# 5. WebSocket Integration Tests: Origin Boundary
# ===========================================================================


def test_websocket_accepts_tauri_origin(valid_token: str) -> None:
    """WebSocket dari origin tauri://localhost diizinkan terhubung."""
    async def _run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/terminal/?token={valid_token}",
            headers=[
                (b"host", b"testserver"),
                (b"origin", b"tauri://localhost"),
            ],
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    asyncio.run(_run())


def test_websocket_accepts_localhost_origin(valid_token: str) -> None:
    """WebSocket dari origin http://localhost:5173 diizinkan terhubung."""
    async def _run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/terminal/?token={valid_token}",
            headers=[
                (b"host", b"testserver"),
                (b"origin", b"http://localhost:5173"),
            ],
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    asyncio.run(_run())


def test_websocket_rejects_evil_origin(valid_token: str) -> None:
    """WebSocket dari origin https://evil.com ditolak dengan close code 4003."""
    async def _run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/terminal/?token={valid_token}",
            headers=[
                (b"host", b"testserver"),
                (b"origin", b"https://evil.com"),
            ],
        )
        connected, _ = await communicator.connect()
        assert connected
        msg = await communicator.receive_from()
        assert "Origin" in msg
        close_frame = await communicator.receive_output()
        assert close_frame["type"] == "websocket.close"
        assert close_frame["code"] == 4003

    asyncio.run(_run())


def test_websocket_rejects_null_origin(valid_token: str) -> None:
    """WebSocket dengan Origin: null ditolak dengan close code 4003."""
    async def _run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/terminal/?token={valid_token}",
            headers=[
                (b"host", b"testserver"),
                (b"origin", b"null"),
            ],
        )
        connected, _ = await communicator.connect()
        assert connected
        msg = await communicator.receive_from()
        assert "Origin" in msg
        close_frame = await communicator.receive_output()
        assert close_frame["type"] == "websocket.close"
        assert close_frame["code"] == 4003

    asyncio.run(_run())
