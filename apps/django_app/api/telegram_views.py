from __future__ import annotations

import os
from dataclasses import asdict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.companion import TelegramCompanion
from agent_ai.runtime.telegram.pairing import PairingManager, generate_qr_svg
from agent_ai.runtime.telegram.security import TelegramSecurityManager

_security_manager: TelegramSecurityManager | None = None
_pairing_manager: PairingManager | None = None
_cached_bot_username: str | None = None
_companion: TelegramCompanion | None = None

def get_security_manager() -> TelegramSecurityManager:
    global _security_manager
    if _security_manager is None:
        _security_manager = TelegramSecurityManager()
    return _security_manager


def get_pairing_manager() -> PairingManager:
    global _pairing_manager
    if _pairing_manager is None:
        _pairing_manager = PairingManager(ttl_seconds=300)
    return _pairing_manager


def get_companion() -> TelegramCompanion | None:
    global _companion
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return None
    if _companion is None:
        _companion = TelegramCompanion(
            bot_token=token,
            security_manager=get_security_manager(),
            pairing_manager=get_pairing_manager(),
        )
    return _companion
def get_bot_username(token: str) -> str:
    global _cached_bot_username
    if _cached_bot_username:
        return _cached_bot_username
    if not token:
        return ""
    try:
        client = TelegramBotClient(bot_token=token)
        me = client.get_me()
        uname = me.get("username", "")
        if uname:
            _cached_bot_username = uname
        return uname
    except Exception:
        return ""


def telegram_status(request):
    """GET /api/telegram/status: Kembalikan status konfigurasi dan akun Telegram terhubung."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return JsonResponse({
            "configured": False,
            "is_paired": False,
            "bot_username": "",
            "paired_user": None,
            "is_running": False,
        })

    sec = get_security_manager()
    status = sec.get_status()
    bot_username = get_bot_username(token)

    paired_user_data = asdict(status.paired_user) if status.paired_user else None

    return JsonResponse({
        "configured": True,
        "is_paired": status.is_paired,
        "bot_username": bot_username,
        "paired_user": paired_user_data,
        "is_running": bool(_companion and _companion.bot_client and _companion.bot_client.is_polling()),
    })


def telegram_pairing_qr(request):
    """GET /api/telegram/pairing-qr: Bangun sesi pairing baru & render QR code SVG."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return JsonResponse(
            {"error": "TELEGRAM_BOT_TOKEN belum disetel di .env"},
            status=400,
        )

    # Pastikan companion bot aktif mendengarkan saat QR code digenerate
    comp = get_companion()
    if comp and not (comp.bot_client and comp.bot_client.is_polling()):
        comp.start()

    bot_username = get_bot_username(token)
    if not bot_username:
        bot_username = "AegisCode_bot"

    pm = get_pairing_manager()
    session = pm.create_session(bot_username)
    svg_content = generate_qr_svg(session.deep_link)

    return JsonResponse({
        "token": session.token,
        "deep_link": session.deep_link,
        "qr_svg": svg_content,
        "expires_in": session.ttl_seconds,
    })


@csrf_exempt
def telegram_unlink(request):
    """POST /api/telegram/unlink: Putuskan hubungan akun Telegram dari sistem."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    sec = get_security_manager()
    success = sec.unlink()
    global _companion
    if _companion:
        try:
            _companion.stop()
        except Exception:
            pass
    return JsonResponse({"success": success})


@csrf_exempt
def telegram_start_poller(request):
    """POST /api/telegram/start-poller: Aktifkan background companion bot secara eksplisit."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    comp = get_companion()
    if not comp:
        return JsonResponse(
            {"error": "TELEGRAM_BOT_TOKEN belum disetel di .env", "is_running": False},
            status=400,
        )

    success = comp.start()
    is_running = bool(comp.bot_client and comp.bot_client.is_polling())
    return JsonResponse({"success": success, "is_running": is_running})


@csrf_exempt
def telegram_stop_poller(request):
    """POST /api/telegram/stop-poller: Hentikan background companion bot secara eksplisit."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    global _companion
    if _companion:
        _companion.stop()
    return JsonResponse({"success": True, "is_running": False})
