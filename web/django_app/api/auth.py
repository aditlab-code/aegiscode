"""Google OAuth 2.0 & Stateless Session Authentication Module.

Implements the stateless signed-state authentication pattern described in
docs/Oauth-Google.md (Phase 0 Hotfix).
Features:
- Anti-CSRF stateless JWT signed state tokens (300s expiration, no Django session required).
- Server-to-server authorization code exchange with Google Token API.
- Cryptographic verification of Google id_token via google-auth library.
- Minting and verification of AegisCode session JWT tokens (HS256).
- @require_auth decorator for route guarding.
"""

from __future__ import annotations

import functools
import os
import time
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import jwt
import requests

STATE_EXPIRY_SECONDS = 300  # 5 minutes anti-CSRF validity window


def generate_signed_state(redirect_uri: str = "") -> str:
    """Generate tamper-proof signed JWT state to prevent CSRF without server session."""
    payload = {
        "timestamp": int(time.time()),
        "nonce": os.urandom(16).hex(),
        "redirect_uri": redirect_uri or getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", ""),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_signed_state(state: str) -> Optional[Dict[str, Any]]:
    """Validate signed state token signature and ensure it is not expired.
    
    Returns:
        dict: The decoded payload if valid and fresh.
        None: If signature is invalid, tampered, or expired (>300 seconds).
    """
    if not state:
        return None
    try:
        decoded = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
        timestamp = decoded.get("timestamp", 0)
        if int(time.time()) - timestamp > STATE_EXPIRY_SECONDS:
            return None
        return decoded
    except Exception:
        return None


def exchange_google_code(
    code: str,
    redirect_uri: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """Exchange authorization code for access_token and id_token with Google Token API."""
    cid = client_id or getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    secret = client_secret or getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not cid or not secret:
        raise ValueError("Google OAuth Client ID and Secret must be configured in settings/.env")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": cid,
        "client_secret": secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, data=payload, timeout=10)
    if not response.ok:
        raise ValueError(f"Google Token Exchange Failed: {response.text}")
    return response.json()


def verify_google_id_token(
    token_str: str,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify cryptographic signature and extract authenticated user identity from Google id_token."""
    cid = client_id or getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    # google.oauth2.id_token automatically fetches Google's public certificates
    # and validates audience and issuer.
    return id_token.verify_oauth2_token(
        token_str,
        google_requests.Request(),
        cid if cid else None,
    )


def create_aegis_session_token(
    user_info: Dict[str, Any],
    expiry_seconds: Optional[int] = None,
) -> str:
    """Issue a signed AegisCode session JWT for the authenticated user."""
    ttl = expiry_seconds or getattr(settings, "AEGIS_AUTH_TOKEN_EXPIRY", 604800)
    now = int(time.time())
    payload = {
        "sub": str(user_info.get("sub", "")),
        "email": str(user_info.get("email", "")),
        "name": str(user_info.get("name", "")),
        "picture": str(user_info.get("picture", "")),
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_aegis_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify an AegisCode session token. Returns payload or None."""
    if not token:
        return None
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def is_loopback_address(ip: Optional[str]) -> bool:
    """Periksa apakah IP client adalah loopback lokal."""
    ip_clean = (ip or "").strip().lower()
    return ip_clean in ("127.0.0.1", "::1", "localhost", "testserver", "testclient")


def is_auth_required_for_request(request: HttpRequest) -> bool:
    """Evaluasi apakah request ini wajib diautentikasi.

    Jika AEGIS_AUTH_REQUIRED bernilai True, autentikasi selalu wajib (mode production/enterprise).
    Jika AEGIS_AUTH_REQUIRED bernilai False (default lokal development), request dari
    IP loopback lokal (127.0.0.1 / ::1 / testserver) diizinkan melewati pemeriksaan.
    Request dari alamat IP non-loopback tetap wajib diautentikasi.
    """
    auth_required = getattr(settings, "AEGIS_AUTH_REQUIRED", False)
    if auth_required:
        return True

    remote_ip = request.META.get("REMOTE_ADDR", "")
    if is_loopback_address(remote_ip):
        return False

    return True


def verify_websocket_auth(scope: Dict[str, Any]) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    """Verifikasi autentikasi dan origin untuk koneksi WebSocket Channels.

    Returns:
        tuple (is_allowed: bool, reason: str, user_info: dict | None)
    """
    headers = dict(scope.get("headers", []))
    origin_bytes = headers.get(b"origin")
    origin = origin_bytes.decode("utf-8") if origin_bytes else ""

    # 1. Validasi Origin bila header origin dikirim browser
    if origin:
        from urllib.parse import urlparse

        parsed_origin = urlparse(origin)
        origin_host = parsed_origin.hostname or ""
        allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
        is_origin_allowed = (
            origin_host in allowed_hosts
            or is_loopback_address(origin_host)
            or "*" in allowed_hosts
        )
        if not is_origin_allowed:
            return False, f"Origin '{origin}' tidak diizinkan.", None

    # 2. Periksa IP client
    client_info = scope.get("client")
    client_ip = client_info[0] if (client_info and len(client_info) > 0) else ""
    is_client_loopback = is_loopback_address(client_ip) or (client_info is None)

    # 3. Ekstrak token dari query string (?token=...) atau header Authorization
    token = ""
    query_string = scope.get("query_string", b"").decode("utf-8")
    if query_string:
        from urllib.parse import parse_qs

        qs_dict = parse_qs(query_string)
        token_list = qs_dict.get("token")
        if token_list and token_list[0]:
            token = token_list[0].strip()

    if not token:
        auth_hdr = headers.get(b"authorization", b"").decode("utf-8")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()

    # 4. Validasi token bila ada
    user_info = None
    if token:
        user_info = verify_aegis_session_token(token)

    auth_required = getattr(settings, "AEGIS_AUTH_REQUIRED", False)

    if user_info:
        return True, "Authenticated via session token.", user_info

    # Jika token dikirim tetapi tidak valid: tolak
    if token and not user_info:
        return False, "Session token tidak valid atau telah kedaluwarsa.", None

    # Jika token tidak ada: periksa apakah boleh bypass untuk local loopback
    if not auth_required and is_client_loopback:
        return True, "Loopback local developer bypass.", {"sub": "local-dev", "name": "Local Developer"}

    return False, "Authentication required. WebSocket connection rejected.", None


def get_authenticated_user(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """Extract and verify user identity from request Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    return verify_aegis_session_token(token)


def require_auth(view_func: Callable) -> Callable:
    """Decorator to enforce mandatory authentication on gateway API endpoints.

    Supports transparent loopback bypass when AEGIS_AUTH_REQUIRED=False.
    """
    @functools.wraps(view_func)
    def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        user_info = get_authenticated_user(request)
        if user_info:
            request.user_info = user_info
            return view_func(request, *args, **kwargs)

        if not is_auth_required_for_request(request):
            request.user_info = {"sub": "local-dev", "name": "Local Developer", "email": "local@aegis"}
            return view_func(request, *args, **kwargs)

        return JsonResponse(
            {
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required. Please sign in or provide a valid Bearer token.",
                }
            },
            status=401,
        )

    return _wrapped
