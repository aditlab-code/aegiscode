"""Tests for Sovereign Local Password Auth and Stateless Session Token Management.

Replaces legacy Google OAuth suite with local password cryptography and endpoint tests.
Enforces minimum 6 characters password policy.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from unittest.mock import patch

import pytest

# Ensure PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "django_app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

from django.conf import settings
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"] + list(settings.ALLOWED_HOSTS)

import django
try:
    django.setup()
except RuntimeError:
    pass

import jwt
from django.test import Client
from django.http import HttpResponse

import api.auth
from api.auth import (
    create_aegis_session_token,
    has_configured_password,
    hash_password,
    require_auth,
    set_password,
    verify_aegis_session_token,
    verify_password,
)


@pytest.fixture
def client():
    return Client(HTTP_AUTHORIZATION="")


@pytest.fixture(autouse=True)
def clean_pin_environment(tmp_path):
    """Isolate auth.json, AEGIS_PASSWORD, and AEGIS_PIN for every test."""
    temp_auth_file = tmp_path / "auth.json"
    real_auth_file = Path(settings.REPO_ROOT) / ".aegis" / "auth.json"
    had_real = real_auth_file.exists()
    real_content = real_auth_file.read_bytes() if had_real else None

    try:
        with patch("api.auth.AUTH_PIN_FILE", temp_auth_file), \
             patch("api.auth.AUTH_PASSWORD_FILE", temp_auth_file), \
             patch.dict(os.environ, {"AEGIS_PASSWORD": "", "AEGIS_PIN": ""}, clear=False):
            yield temp_auth_file
    finally:
        # Guarantee no test artifact pollutes user's real .aegis/auth.json
        if not had_real and real_auth_file.exists():
            try:
                real_auth_file.unlink()
            except OSError:
                pass
        elif had_real and real_content is not None:
            try:
                real_auth_file.write_bytes(real_content)
            except OSError:
                pass


def test_hash_and_verify_password():
    """Verify PBKDF2 hashing, unique salts, minimum 6 characters, and verification."""
    salt_hex, hash_hex = hash_password("secret123")
    assert isinstance(salt_hex, str) and len(salt_hex) == 32
    assert isinstance(hash_hex, str) and len(hash_hex) == 64

    # Unique salts per generation
    salt_2, hash_2 = hash_password("secret123")
    assert salt_hex != salt_2
    assert hash_hex != hash_2

    # Length constraints (min 6 characters)
    with pytest.raises(ValueError):
        hash_password("12345")  # Too short (<6)
    with pytest.raises(ValueError):
        hash_password("a" * 129)  # Too long (>128)

    # Set and verify
    assert set_password("mypassword") is True
    assert verify_password("mypassword") is True
    assert verify_password("wrongpass") is False
    assert verify_password("") is False


def test_password_env_override():
    """Verify that AEGIS_PASSWORD and AEGIS_PIN environment variables override or serve as fallback."""
    with patch.dict(os.environ, {"AEGIS_PASSWORD": "envpassword123"}, clear=False):
        assert has_configured_password() is True
        assert verify_password("envpassword123") is True
        assert verify_password("wrongpass") is False


def test_password_setup_endpoint(client, clean_pin_environment):
    """POST /api/auth/setup creates auth.json with 0600 permissions and issues session token."""
    response = client.post(
        "/api/auth/setup",
        data=json.dumps({"password": "securepass123", "confirm_password": "securepass123"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert data["user"]["sub"] == "local-operator"

    # Verify file was written
    assert clean_pin_environment.is_file()
    if os.name != "nt":
        mode = stat.S_IMODE(os.stat(clean_pin_environment).st_mode)
        assert mode == 0o600

    # Verify session token is valid
    verified = verify_aegis_session_token(data["token"])
    assert verified is not None
    assert verified["sub"] == "local-operator"


def test_password_setup_mismatch(client):
    """POST /api/auth/setup with mismatched password returns HTTP 400."""
    response = client.post(
        "/api/auth/setup",
        data=json.dumps({"password": "secretpass1", "confirm_password": "secretpass2"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_MISMATCH"


def test_password_setup_invalid_length(client):
    """POST /api/auth/setup with password under 6 characters returns HTTP 400."""
    response = client.post(
        "/api/auth/setup",
        data=json.dumps({"password": "12345", "confirm_password": "12345"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PASSWORD_LENGTH"


def test_password_setup_already_configured_rejected(client):
    """POST /api/auth/setup rejects reconfiguration when unauthenticated."""
    assert set_password("initialpass") is True

    response = client.post(
        "/api/auth/setup",
        data=json.dumps({"password": "newpass123", "confirm_password": "newpass123"}),
        content_type="application/json",
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PASSWORD_ALREADY_CONFIGURED"


def test_password_login_endpoint_success(client):
    """POST /api/auth/login with correct password returns session JWT and user profile."""
    assert set_password("correctpass123") is True

    response = client.post(
        "/api/auth/login",
        data=json.dumps({"password": "correctpass123"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["sub"] == "local-operator"
    assert data["user"]["email"] == "operator@aegis.local"


def test_password_login_endpoint_failure(client):
    """POST /api/auth/login with wrong password returns HTTP 401."""
    assert set_password("correctpass123") is True

    response = client.post(
        "/api/auth/login",
        data=json.dumps({"password": "wrongpassword"}),
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_PASSWORD"


def test_auth_status_endpoint(client):
    """GET /api/auth/status returns has_password and authenticated states accurately."""
    # 1. First run: no password configured
    resp1 = client.get("/api/auth/status")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["configured"] is True
    assert data1["has_password"] is False
    assert data1["authenticated"] is False
    assert data1["user"] is None

    # 2. Password configured, not authenticated
    set_password("configuredpass")
    resp2 = client.get("/api/auth/status")
    data2 = resp2.json()
    assert data2["has_password"] is True
    assert data2["authenticated"] is False

    # 3. Authenticated with session JWT
    token = create_aegis_session_token({"sub": "local-operator", "name": "Local Operator"})
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    resp3 = client.get("/api/auth/status")
    data3 = resp3.json()
    assert data3["has_password"] is True
    assert data3["authenticated"] is True
    assert data3["user"]["sub"] == "local-operator"


def test_auth_me_endpoint(client):
    """GET /api/auth/me enforces authentication and returns user identity."""
    # Unauthenticated
    resp_unauth = client.get("/api/auth/me")
    assert resp_unauth.status_code == 401
    assert resp_unauth.json()["error"]["code"] == "UNAUTHORIZED"

    # Authenticated
    token = create_aegis_session_token({"sub": "operator-01", "email": "operator@aegis.local", "name": "Operator"})
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    resp_auth = client.get("/api/auth/me")
    assert resp_auth.status_code == 200
    assert resp_auth.json()["authenticated"] is True
    assert resp_auth.json()["user"]["email"] == "operator@aegis.local"


def test_auth_logout_endpoint(client):
    """POST /api/auth/logout succeeds statelessly."""
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_aegis_session_token_roundtrip():
    """Verify minting and verification of AegisCode session JWT."""
    user = {"sub": "operator-xyz", "name": "Lead Operator", "email": "lead@aegis.local"}
    token = create_aegis_session_token(user, expiry_seconds=3600)
    assert isinstance(token, str)

    payload = verify_aegis_session_token(token)
    assert payload is not None
    assert payload["sub"] == "operator-xyz"
    assert payload["name"] == "Lead Operator"

    # Expired token
    expired_token = create_aegis_session_token(user, expiry_seconds=-10)
    assert verify_aegis_session_token(expired_token) is None


def test_require_auth_decorator():
    """Verify that @require_auth blocks unauthenticated calls and permits valid tokens."""
    @require_auth
    def dummy_view(request):
        return HttpResponse("OK")

    unauth_client = Client(HTTP_AUTHORIZATION="")
    # Missing token -> 401
    res_unauth = dummy_view(unauth_client.get("/dummy").wsgi_request)
    assert res_unauth.status_code == 401

    # Valid token -> 200
    token = create_aegis_session_token({"sub": "test-user"})
    req_good = unauth_client.get("/dummy", HTTP_AUTHORIZATION=f"Bearer {token}").wsgi_request
    res_good = dummy_view(req_good)
    assert res_good.status_code == 200
