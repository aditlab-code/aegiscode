"""Tests for Google OAuth 2.0 Identity Gateway and Stateless Session Auth.

Covers:
- Signed JWT anti-CSRF state token generation and verification
- State expiration and tampering defense
- Google Token code exchange mocking
- Google id_token signature verification
- AETHER session JWT creation and verification
- Django API endpoints:
    GET  /api/auth/google/url
    POST /api/auth/google/callback
    GET  /api/auth/me
    POST /api/auth/logout
- @require_auth view decorator
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from django.http import HttpRequest, JsonResponse

from api.auth import (
    STATE_EXPIRY_SECONDS,
    create_aether_session_token,
    exchange_google_code,
    generate_signed_state,
    get_authenticated_user,
    require_auth,
    verify_aether_session_token,
    verify_google_id_token,
    verify_signed_state,
)


@pytest.fixture
def client():
    return Client()


def test_generate_and_verify_signed_state():
    """Verify that generated state is a valid signed JWT containing timestamp and nonce."""
    redirect_uri = "http://localhost:8478/auth/callback"
    state = generate_signed_state(redirect_uri=redirect_uri)
    assert isinstance(state, str)
    assert len(state) > 20

    verified = verify_signed_state(state)
    assert verified is not None
    assert verified.get("redirect_uri") == redirect_uri
    assert "timestamp" in verified
    assert "nonce" in verified


def test_verify_signed_state_expired():
    """Ensure state tokens older than 300 seconds are rejected."""
    expired_payload = {
        "timestamp": int(time.time()) - (STATE_EXPIRY_SECONDS + 10),
        "nonce": "testnonce123",
        "redirect_uri": "http://localhost:8478/auth/callback",
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm="HS256")
    assert verify_signed_state(expired_token) is None


def test_verify_signed_state_tampered():
    """Ensure tampered signature or invalid tokens return None."""
    payload = {"timestamp": int(time.time()), "nonce": "abc"}
    wrong_key_token = jwt.encode(
        payload, "wrong-secret-key-that-is-at-least-32-chars-long", algorithm="HS256"
    )
    assert verify_signed_state(wrong_key_token) is None
    assert verify_signed_state("not-a-token") is None
    assert verify_signed_state("") is None


def test_exchange_google_code_success():
    """Verify code exchange POST with mocked Google token API."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "access_token": "ya29.mock_access_token",
        "id_token": "mock_id_token_jwt",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = exchange_google_code(
            code="test_auth_code",
            redirect_uri="http://localhost:8478/auth/callback",
            client_id="mock_client_id.apps.googleusercontent.com",
            client_secret="mock_secret",
        )
        assert result["access_token"] == "ya29.mock_access_token"
        assert result["id_token"] == "mock_id_token_jwt"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["data"]["code"] == "test_auth_code"
        assert kwargs["data"]["grant_type"] == "authorization_code"


def test_exchange_google_code_failure():
    """Verify code exchange raises descriptive ValueError on Google API error."""
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.text = '{"error": "redirect_uri_mismatch"}'

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(ValueError, match="Google Token Exchange Failed"):
            exchange_google_code(
                code="bad_code",
                redirect_uri="http://localhost:8478/auth/callback",
                client_id="cid",
                client_secret="sec",
            )


def test_verify_google_id_token():
    """Verify Google ID token extraction with google.oauth2.id_token mock."""
    mock_payload = {
        "sub": "google-user-12345",
        "email": "developer@aether.ai",
        "name": "Aether Developer",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }
    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_payload):
        user_info = verify_google_id_token("mock.jwt.token", client_id="cid")
        assert user_info["email"] == "developer@aether.ai"
        assert user_info["sub"] == "google-user-12345"


def test_aether_session_token_roundtrip():
    """Verify minting and verification of AETHER session token."""
    user_info = {
        "sub": "sub-999",
        "email": "user@example.com",
        "name": "Test User",
        "picture": "https://avatar.url",
    }
    token = create_aether_session_token(user_info, expiry_seconds=3600)
    assert isinstance(token, str)

    decoded = verify_aether_session_token(token)
    assert decoded is not None
    assert decoded["email"] == "user@example.com"
    assert decoded["sub"] == "sub-999"
    assert decoded["name"] == "Test User"

    # Expired token test
    expired_token = create_aether_session_token(user_info, expiry_seconds=-10)
    assert verify_aether_session_token(expired_token) is None


def test_auth_url_endpoint(client):
    """GET /api/auth/google/url returns consent URL with signed state when configured."""
    with patch.object(settings, "GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com"):
        response = client.get("/api/auth/google/url?redirect_uri=http://localhost:8478/auth/callback")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state" in data
        assert "accounts.google.com" in data["auth_url"]
        assert "state=" in data["auth_url"]

    # When not configured
    with patch.object(settings, "GOOGLE_OAUTH_CLIENT_ID", ""):
        res_unconfigured = client.get("/api/auth/google/url")
        assert res_unconfigured.status_code == 400
        assert res_unconfigured.json()["error"]["code"] == "GOOGLE_OAUTH_NOT_CONFIGURED"


def test_auth_dev_login(client):
    """POST /api/auth/dev-login issues a valid session token for local testing."""
    response = client.post(
        "/api/auth/dev-login",
        data={"email": "aditwicaksono34@gmail.com", "name": "Adit Wicaksono"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["email"] == "aditwicaksono34@gmail.com"



def test_auth_callback_endpoint_full_flow(client):
    """POST /api/auth/google/callback with valid state and code exchanges token and returns session."""
    redirect_uri = "http://localhost:8478/auth/callback"
    state = generate_signed_state(redirect_uri=redirect_uri)

    mock_token_data = {"access_token": "ya29.xyz", "id_token": "mock_id_jwt"}
    mock_user_data = {
        "sub": "user_id_001",
        "email": "adit@example.com",
        "name": "Adit Wicaksono",
        "picture": "https://lh3.google.com/pic.jpg",
    }

    with patch("api.auth.exchange_google_code", return_value=mock_token_data), \
         patch("api.auth.verify_google_id_token", return_value=mock_user_data):
        response = client.post(
            "/api/auth/google/callback",
            data={"code": "sample_auth_code", "state": state, "redirect_uri": redirect_uri},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "adit@example.com"
        assert data["user"]["name"] == "Adit Wicaksono"

        # Verify issued token
        decoded = verify_aether_session_token(data["token"])
        assert decoded["email"] == "adit@example.com"


def test_auth_callback_invalid_state(client):
    """POST /api/auth/google/callback with forged state returns 400."""
    response = client.post(
        "/api/auth/google/callback",
        data={"code": "some_code", "state": "invalid_forged_state"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_STATE"


def test_auth_me_endpoint(client):
    """GET /api/auth/me enforces authentication status."""
    # Unauthenticated
    resp_unauth = client.get("/api/auth/me")
    assert resp_unauth.status_code == 401

    # Authenticated with Bearer token
    user_info = {"sub": "123", "email": "dev@aether.ai", "name": "Dev"}
    token = create_aether_session_token(user_info)
    resp_auth = client.get("/api/auth/me", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp_auth.status_code == 200
    assert resp_auth.json()["authenticated"] is True
    assert resp_auth.json()["user"]["email"] == "dev@aether.ai"


def test_require_auth_decorator():
    """Verify that @require_auth blocks unauthenticated requests and permits valid Bearer tokens."""
    @require_auth
    def protected_view(request):
        return JsonResponse({"msg": "secret", "user": request.user_info["email"]})

    # Test without auth
    req_bad = HttpRequest()
    res_bad = protected_view(req_bad)
    assert res_bad.status_code == 401

    # Test with valid token
    req_good = HttpRequest()
    token = create_aether_session_token({"sub": "77", "email": "auth@user.com", "name": "Auth"})
    req_good.headers = {"Authorization": f"Bearer {token}"}
    res_good = protected_view(req_good)
    assert res_good.status_code == 200
