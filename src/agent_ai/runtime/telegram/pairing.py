from __future__ import annotations

import io
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

try:
    import qrcode
    import qrcode.image.svg
    _HAS_QRCODE = True
except ImportError:
    _HAS_QRCODE = False


@dataclass
class PairingSession:
    """Sesi pairing akun Telegram dengan token OTP berumur terbatas."""

    token: str
    bot_username: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300

    @property
    def deep_link(self) -> str:
        return f"https://t.me/{self.bot_username}?start=pair_{self.token}"

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class PairingManager:
    """Pengelola siklus sesi dan validasi token pairing Telegram."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._current_session: Optional[PairingSession] = None

    def create_session(self, bot_username: str) -> PairingSession:
        token = uuid.uuid4().hex[:8]
        self._current_session = PairingSession(
            token=token,
            bot_username=bot_username.strip().lstrip("@"),
            created_at=time.time(),
            ttl_seconds=self.ttl_seconds,
        )
        return self._current_session

    def get_active_session(self) -> Optional[PairingSession]:
        if self._current_session is None:
            return None
        if self._current_session.is_expired():
            self._current_session = None
            return None
        return self._current_session

    def validate_token(self, token: str) -> bool:
        """Validasi token; jika valid, konsumsi token sekali pakai (single-use)."""
        active = self.get_active_session()
        if active is None:
            return False
        if active.token == token.strip():
            self._current_session = None  # Konsumsi token
            return True
        return False


def generate_qr_svg(data: str) -> str:
    """Hasilkan string XML SVG QR code valid untuk Web UI."""
    if _HAS_QRCODE:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(data, image_factory=factory)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode("utf-8")
    # Fallback minimalis SVG jika modul qrcode belum terpasang
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<rect width="100" height="100" fill="white"/>'
        f'<text x="10" y="50" font-size="8" fill="black">QR: {data}</text>'
        f'</svg>'
    )


def generate_qr_ascii(data: str) -> str:
    """Hasilkan string ASCII / Unicode blocks QR code untuk terminal CLI."""
    if _HAS_QRCODE:
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf)
        return buf.getvalue()
    return f"[QR CODE: {data}]"
