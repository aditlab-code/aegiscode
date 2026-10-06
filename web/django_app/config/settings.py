"""Django settings untuk Aegis Gateway (#50).

Konfigurasi minimal. Gateway tipis: TIDAK memakai database ORM, DRF, Celery,
Redis, atau Channels. Django hanya HTTP layer menuju Aegis.

Hardening (#57): SECRET_KEY, DEBUG, ALLOWED_HOSTS, dan konfigurasi keamanan
production dibaca dari environment. Default development tetap mudah dipakai,
tetapi production TIDAK diam-diam memakai konfigurasi development yang tidak
aman (lihat `_is_production`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# config/settings.py -> config/ -> django_app/ -> web/ -> repo root
DJANGO_APP_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = DJANGO_APP_DIR.parent.parent

# Pastikan package AegisCode (src/) dapat diimpor oleh gateway.
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Muat .env (bila ada) agar konfigurasi deployment konsisten dengan Aegis core.
# override=False: variabel environment yang sudah ada tidak tertimpa.
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
except Exception:  # noqa: BLE001 - dotenv opsional; env tetap dibaca dari OS
    pass


# ---------------------------------------------------------------------------
# Helper environment
# ---------------------------------------------------------------------------
def _env(key: str, default: str = "") -> str:
    """Ambil nilai string dari environment (di-strip)."""
    value = os.getenv(key, default)
    return value.strip() if isinstance(value, str) else default


def _env_bool(key: str, default: bool) -> bool:
    """Ambil nilai boolean dari environment (1/true/yes/on)."""
    raw = _env(key)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _env_list(key: str, default: list[str]) -> list[str]:
    """Ambil daftar (dipisah koma) dari environment."""
    raw = _env(key)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Environment mode
# ---------------------------------------------------------------------------
# AEGIS_ENV: "production" | "development" (default development).
# Production juga dapat ditandai lewat DJANGO_DEBUG=false.
AEGIS_ENV = (_env("AEGIS_ENV") or "development").lower()
IS_PRODUCTION = AEGIS_ENV in ("production", "prod")

# ---------------------------------------------------------------------------
# Core (dari environment; default development yang aman)
# ---------------------------------------------------------------------------
# SECRET_KEY: WAJIB diisi di production. Default dev hanya untuk lokal.
# `or` (bukan default os.getenv): variabel yang diset-kosong ("") HARUS jatuh ke
# fallback — Django melempar ImproperlyConfigured saat SECRET_KEY kosong ketika
# membangun halaman error 404/500 (lihat LazySettings.__getattr__).
_DEV_SECRET_KEY = "aegis-gateway-dev-key-not-for-production"
SECRET_KEY = _env("DJANGO_SECRET_KEY") or _DEV_SECRET_KEY

# DEBUG: default True di development, False di production.
DEBUG = _env_bool("DJANGO_DEBUG", default=not IS_PRODUCTION)

# ALLOWED_HOSTS: default localhost di development; WAJIB diisi di production.
ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost"] if not IS_PRODUCTION else [],
)
if not IS_PRODUCTION and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

# ---------------------------------------------------------------------------
# Production safety guard (#57)
# ---------------------------------------------------------------------------
# Jangan biarkan production diam-diam memakai konfigurasi development yang
# tidak aman. Gagal cepat (fail-fast) dengan pesan jelas.
if IS_PRODUCTION:
    if not SECRET_KEY or SECRET_KEY == _DEV_SECRET_KEY:
        raise RuntimeError(
            "DJANGO_SECRET_KEY wajib diisi di production (AEGIS_ENV=production)."
        )
    if DEBUG:
        raise RuntimeError(
            "DEBUG harus false di production (set DJANGO_DEBUG=false)."
        )
    if not ALLOWED_HOSTS:
        raise RuntimeError(
            "DJANGO_ALLOWED_HOSTS wajib diisi di production (daftar host, dipisah koma)."
        )

INSTALLED_APPS = [
    "daphne",
    "channels",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "api",
]

ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

MIDDLEWARE = [
    *(["django.middleware.security.SecurityMiddleware"] if IS_PRODUCTION else []),
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database: TIDAK dipakai (gateway tipis, tanpa ORM).
# ---------------------------------------------------------------------------
DATABASES = {}

# ---------------------------------------------------------------------------
# i18n / tz
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"

# ---------------------------------------------------------------------------
# Frontend production build (#57)
# ---------------------------------------------------------------------------
# Hasil `npm run build` (web/frontend/dist) dapat disajikan oleh Django.
# Hanya diaktifkan bila direktori build benar-benar ada (tidak mengubah dev).
FRONTEND_DIST_DIR = REPO_ROOT / "web" / "frontend" / "dist"
FRONTEND_DIST_EXISTS = FRONTEND_DIST_DIR.is_dir()
STATICFILES_DIRS = [FRONTEND_DIST_DIR] if FRONTEND_DIST_EXISTS else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Security hardening (#57) - hanya diaktifkan di production.
# ---------------------------------------------------------------------------
# Nilai dapat di-override lewat environment. Default aman untuk production.
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", default=IS_PRODUCTION)
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", default=IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(_env("DJANGO_SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=IS_PRODUCTION)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=IS_PRODUCTION)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Proxy header (bila di belakang reverse proxy TLS).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PRODUCTION else None

# ---------------------------------------------------------------------------
# Gateway config (bukan logic agent; hanya batas HTTP).
# ---------------------------------------------------------------------------
# Batas ukuran body request (bytes) untuk mencegah payload tanpa batas.
AEGIS_GATEWAY_MAX_BODY_BYTES = int(_env("AEGIS_GATEWAY_MAX_BODY_BYTES") or "1000000")

# ---------------------------------------------------------------------------
# Google OAuth & Identity Gateway (docs/Oauth-Google.md, Phase 0)
# ---------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = _env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = _env("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_OAUTH_REDIRECT_URI = _env("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8478/auth/callback")
AEGIS_AUTH_TOKEN_EXPIRY = int(_env("AEGIS_AUTH_TOKEN_EXPIRY") or "604800")  # 7 days in seconds

# ---------------------------------------------------------------------------
# Authentication Boundary Guard (AEG-08)
# ---------------------------------------------------------------------------
AEGIS_AUTH_REQUIRED = _env_bool("AEGIS_AUTH_REQUIRED", default=IS_PRODUCTION)

