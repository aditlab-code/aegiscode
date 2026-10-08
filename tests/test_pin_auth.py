"""Tests for Sovereign Local PIN Auth and Stateless Session Token Management.

Replaces legacy Google OAuth suite with local PIN cryptography and endpoint tests.
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
    has_configured_pin,
    hash_pin,
    require_auth,
    set_pin,
    verify_aegis_session_token,
    verify_pin,
)


@pytest.fixture
def client():
    return Client(HTTP_AUTHORIZATION="")


@pytest.fixture(autouse=True)
def clean_pin_environment(tmp_path):
    """Isolate auth.json and AEGIS_PIN for every test."""
    temp_auth_file = tmp_path / "auth.json"
    with patch("api.auth.AUTH_PIN_FILE", temp_auth_file), \
         patch.dict(os.environ, {"AEGIS_PIN": ""}, clear=False):
        yield temp_auth_file


def test_hash_and_verify_pin():
    """Verify PBKDF2 hashing, unique salts, length constraints, and verification."""
    salt_hex, hash_hex = hash_pin("123456")
    assert isinstance(salt_hex, str) and len(salt_hex) == 32
    assert isinstance(hash_hex, str) and len(hash_hex) == 64

    # Unique salts per generation
    salt_2, hash_2 = hash_pin("123456")
    assert salt_hex != salt_2
    assert hash_hex != hash_2

    # Length constraints
    with pytest.raises(ValueError):
        hash_pin("123")  # Too short (<4)
    with pytest.raises(ValueError):
        hash_pin("1234567890123")  # Too long (>12)

    # Set and verify
    assert set_pin("654321") is True
    assert verify_pin("654321") is True
    assert verify_pin("000000") is False
    assert verify_pin("") is False


def test_pin_env_override():
    """Verify that AEGIS_PIN environment variable overrides or serves as fallback."""
    with patch.dict(os.environ, {"AEGIS_PIN": "998877"}, clear=False):
        assert has_configured_pin() is True
        assert verify_pin("998877") is True
        assert verify_pin("111111") is False


def test_pin_setup_endpoint(client, clean_pin_environment):
    """POST /api/auth/pin/setup creates auth.json with 0600 permissions and issues session token."""
    response = client.post(
        "/api/auth/pin/setup",
        data=json.dumps({"pin": "1234", "confirm_pin": "1234"}),
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


def test_pin_setup_mismatch(client):
    """POST /api/auth/pin/setup with mismatched PIN returns HTTP 400."""
    response = client.post(
        "/api/auth/pin/setup",
        data=json.dumps({"pin": "1234", "confirm_pin": "4321"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PIN_MISMATCH"


def test_pin_setup_invalid_length(client):
    """POST /api/auth/pin/setup with invalid length returns HTTP 400."""
    response = client.post(
        "/api/auth/pin/setup",
        data=json.dumps({"pin": "12", "confirm_pin": "12"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PIN_LENGTH"


def test_pin_setup_already_configured_rejected(client):
    """POST /api/auth/pin/setup rejects reconfiguration when unauthenticated."""
    assert set_pin("1234") is True

    response = client.post(
        "/api/auth/pin/setup",
        data=json.dumps({"pin": "9999", "confirm_pin": "9999"}),
        content_type="application/json",
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PIN_ALREADY_CONFIGURED"


def test_pin_login_endpoint_success(client):
    """POST /api/auth/pin with correct PIN returns session JWT and user profile."""
    assert set_pin("556677") is True

    response = client.post(
        "/api/auth/pin",
        data=json.dumps({"pin": "556677"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["sub"] == "local-operator"
    assert data["user"]["email"] == "operator@aegis.local"


def test_pin_login_endpoint_failure(client):
    """POST /api/auth/pin with wrong PIN returns HTTP 401."""
    assert set_pin("556677") is True

    response = client.post(
        "/api/auth/pin",
        data=json.dumps({"pin": "wrongpin"}),
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_PIN"


def test_auth_status_endpoint(client):
    """GET /api/auth/status returns has_pin and authenticated states accurately."""
    # 1. First run: no pin configured
    resp1 = client.get("/api/auth/status")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["configured"] is True
    assert data1["has_pin"] is False
    assert data1["authenticated"] is False
    assert data1["user"] is None

    # 2. Pin configured, not authenticated
    set_pin("1234")
    resp2 = client.get("/api/auth/status")
    data2 = resp2.json()
    assert data2["has_pin"] is True
    assert data2["authenticated"] is False

    # 3. Authenticated with session JWT
    token = create_aegis_session_token({"sub": "local-operator", "name": "Local Operator"})
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    resp3 = client.get("/api/auth/status")
    data3 = resp3.json()
    assert data3["has_pin"] is True
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
