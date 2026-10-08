"""Sovereign Local PIN & Stateless Session Authentication Module.

Implements sovereign local PIN authentication and stateless session JWT
management for AegisCode Web UI.
Features:
- PBKDF2-HMAC-SHA256 hashed PIN authentication stored at .aegis/auth.json.
- Environment variable override via AEGIS_PIN.
- Minting and verification of AegisCode session JWT tokens (HS256).
- Ephemeral handshake gateway token support.
- @require_auth decorator for route guarding.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.http import HttpRequest, JsonResponse
import jwt

REPO_ROOT = getattr(settings, "REPO_ROOT", Path(__file__).resolve().parent.parent.parent.parent)
EPHEMERAL_TOKEN_DIR = REPO_ROOT / ".aegis" / "run"
EPHEMERAL_TOKEN_FILE = EPHEMERAL_TOKEN_DIR / "gateway.token"
AUTH_PIN_FILE = REPO_ROOT / ".aegis" / "auth.json"

_EPHEMERAL_TOKEN: Optional[str] = None


def init_ephemeral_token() -> str:
    """Generate and persist an ephemeral handshake token with 0600 permissions."""
    global _EPHEMERAL_TOKEN
    token = secrets.token_urlsafe(32)
    EPHEMERAL_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    EPHEMERAL_TOKEN_FILE.write_text(token, encoding="utf-8")
    if os.name != "nt":
        try:
            os.chmod(EPHEMERAL_TOKEN_FILE, 0o600)
        except Exception:
            pass
    _EPHEMERAL_TOKEN = token
    return token


def get_ephemeral_token() -> Optional[str]:
    """Retrieve current ephemeral handshake token from memory or file."""
    global _EPHEMERAL_TOKEN
    if _EPHEMERAL_TOKEN is not None:
        return _EPHEMERAL_TOKEN
    if EPHEMERAL_TOKEN_FILE.is_file():
        try:
            token = EPHEMERAL_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                _EPHEMERAL_TOKEN = token
                return token
        except Exception:
            return None
    return None


def cleanup_ephemeral_token() -> None:
    """Remove ephemeral handshake token file and clear memory cache."""
    global _EPHEMERAL_TOKEN
    _EPHEMERAL_TOKEN = None
    try:
        if EPHEMERAL_TOKEN_FILE.is_file():
            EPHEMERAL_TOKEN_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify either an ephemeral handshake secret or an AegisCode session JWT."""
    if not token:
        return None

    # 1. Ephemeral token verification
    ephemeral = get_ephemeral_token()
    if ephemeral and hmac.compare_digest(token, ephemeral):
        return {
            "sub": "local-ephemeral",
            "name": "Local Ephemeral Operator",
            "email": "local@aegis",
            "is_ephemeral": True,
        }

    # 2. Session JWT verification
    return verify_aegis_session_token(token)

def hash_pin(pin: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """Hash a PIN string with PBKDF2-HMAC-SHA256 (100,000 iterations).

    Validates PIN length (4 to 12 characters).
    Returns tuple of (salt_hex, hash_hex).
    """
    if not isinstance(pin, str) or not (4 <= len(pin) <= 12):
        raise ValueError("PIN harus berupa string dengan panjang 4-12 karakter.")
    if salt is None:
        salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100_000)
    return salt.hex(), hash_bytes.hex()


def has_configured_pin() -> bool:
    """Check if a PIN has been configured via AEGIS_PIN or .aegis/auth.json."""
    env_pin = getattr(settings, "AEGIS_PIN", "") or os.getenv("AEGIS_PIN", "")
    if env_pin and env_pin.strip():
        return True
    if AUTH_PIN_FILE.is_file():
        try:
            with open(AUTH_PIN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("hash") and data.get("salt"):
                return True
        except Exception:
            return False
    return False


def verify_pin(pin: str) -> bool:
    """Verify input PIN against AEGIS_PIN environment variable or .aegis/auth.json."""
    if not pin or not isinstance(pin, str):
        return False

    env_pin = getattr(settings, "AEGIS_PIN", "") or os.getenv("AEGIS_PIN", "")
    if env_pin and env_pin.strip():
        if hmac.compare_digest(pin, env_pin.strip()):
            return True

    if AUTH_PIN_FILE.is_file():
        try:
            with open(AUTH_PIN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            salt_hex = data.get("salt")
            stored_hash = data.get("hash")
            if not salt_hex or not stored_hash:
                return False
            salt = bytes.fromhex(salt_hex)
            computed_hash = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100_000).hex()
            return hmac.compare_digest(computed_hash, stored_hash)
        except Exception:
            return False

    return False


def set_pin(pin: str) -> bool:
    """Store hashed PIN securely in .aegis/auth.json with 0600 permissions."""
    if not isinstance(pin, str) or not (4 <= len(pin) <= 12):
        raise ValueError("PIN harus berupa string dengan panjang 4-12 karakter.")

    salt_hex, hash_hex = hash_pin(pin)
    target_dir = AUTH_PIN_FILE.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "salt": salt_hex,
        "hash": hash_hex,
        "updated_at": int(time.time()),
    }
    content = json.dumps(data, indent=2)

    temp_file = target_dir / f".auth_{secrets.token_hex(4)}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        if os.name != "nt":
            try:
                os.chmod(temp_file, 0o600)
            except OSError:
                pass
        temp_file.replace(AUTH_PIN_FILE)
        if os.name != "nt":
            try:
                os.chmod(AUTH_PIN_FILE, 0o600)
            except OSError:
                pass
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass

    return True

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

    PR-SEC-1: Meniadakan loopback bypass. Semua endpoint yang dilindungi
    @require_auth selalu mewajibkan token valid (100% auth required).
    """
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

    # 3. Validasi token (ephemeral secret atau session JWT)
    if not token:
        return False, "Authentication required. Valid token is mandatory.", None

    user_info = verify_token(token)
    if user_info:
        return True, "Authenticated via token.", user_info

    return False, "Session token tidak valid atau telah kedaluwarsa.", None

def get_authenticated_user(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """Extract and verify user identity from request Authorization header or query parameter."""
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token and hasattr(request, "GET"):
        token = request.GET.get("token", "").strip()
    if not token:
        return None
    return verify_token(token)

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
