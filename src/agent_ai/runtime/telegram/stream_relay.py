"""Telegram Stream Relay.

Mengelola pembaruan pesan progresif (streaming) ke Telegram dengan throttling
adaptif (~800ms) untuk mencegah pembatasan rate limit Telegram API (HTTP 429).

TIDAK ada silent exception swallowing — setiap error dilog di level yang sesuai.
"""

from __future__ import annotations

import html
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def sanitize_telegram_html(text: str) -> str:
    """Sanitasi teks polos ke format HTML aman untuk Telegram."""
    if not text:
        return ""
    return html.escape(text)


class TelegramStreamRelay:
    """Relay pembaruan pesan streaming bertahap ke Telegram."""

    def __init__(
        self,
        bot_client: Any,
        chat_id: int,
        throttle_interval: float = 0.8,
        initial_status: str = "💭 <i>Agen sedang memproses...</i>",
    ):
        self.bot_client = bot_client
        self.chat_id = chat_id
        self.throttle_interval = throttle_interval
        self.message_id: Optional[int] = None
        self.buffer = ""
        self.status_icon = "💭"
        self.status_label = "Agen sedang memproses..."
        self.last_update_time = 0.0
        self.is_completed = False

        # Kirim pesan placeholder awal
        if initial_status and self.bot_client:
            try:
                res = self.bot_client.send_message(
                    chat_id=self.chat_id,
                    text=initial_status,
                )
                if isinstance(res, dict):
                    if "message_id" in res:
                        self.message_id = res["message_id"]
                    elif "result" in res and isinstance(res["result"], dict):
                        self.message_id = res["result"].get("message_id")
                    logger.debug("StreamRelay: pesan awal terkirim, message_id=%s", self.message_id)
            except Exception as e:
                logger.error("StreamRelay: GAGAL mengirim pesan awal ke chat_id=%s: %s", self.chat_id, e)

    def set_status(self, icon: str, label: str) -> None:
        """Perbarui status ikon (misal 💭 -> ⚡)."""
        self.status_icon = icon
        self.status_label = label
        now = time.time()
        if now - self.last_update_time >= self.throttle_interval:
            self._flush()

    def append_chunk(self, chunk: str) -> None:
        """Tambahkan potongan teks token ke buffer dan flush jika jeda mencukupi."""
        if not chunk or self.is_completed:
            return
        self.buffer += chunk
        now = time.time()
        if now - self.last_update_time >= self.throttle_interval:
            self._flush()

    def set_content(self, text: str) -> None:
        """Ganti konten buffer secara langsung."""
        if self.is_completed:
            return
        self.buffer = text
        now = time.time()
        if now - self.last_update_time >= self.throttle_interval:
            self._flush()

    def _flush(self, final: bool = False) -> None:
        """Edit pesan di Telegram dengan isi buffer saat ini."""
        if not self.message_id or not self.bot_client:
            return

        now = time.time()
        self.last_update_time = now

        content = self.buffer.strip()
        if final:
            if not content:
                rendered_text = f"{self.status_icon} <b>{self.status_label}</b>"
            else:
                rendered_text = f"🤖 <b>Aegis Agent:</b>\n\n{sanitize_telegram_html(content)}"
        else:
            if not content:
                rendered_text = f"{self.status_icon} <i>{self.status_label}</i>"
            else:
                rendered_text = (
                    f"{self.status_icon} <i>{self.status_label}</i>\n\n"
                    f"{sanitize_telegram_html(content)}"
                )

        # Telegram batas karakter 4096
        if len(rendered_text) > 4000:
            rendered_text = rendered_text[:3980] + "\n\n<i>...(dipotong)</i>"

        try:
            self.bot_client.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=rendered_text,
            )
        except Exception as e:
            err_str = str(e).lower()
            if "not modified" in err_str:
                # Telegram menolak edit karena isi sama — bukan error nyata
                logger.debug("StreamRelay _flush: pesan tidak berubah, skip (chat_id=%s)", self.chat_id)
            else:
                logger.warning(
                    "StreamRelay _flush: edit_message_text gagal (chat_id=%s, message_id=%s): %s",
                    self.chat_id, self.message_id, e,
                )

    def finalize(self, final_text: Optional[str] = None, success: bool = True) -> None:
        """Selesaikan stream dan kirim hasil final."""
        if self.is_completed:
            return
        self.is_completed = True
        if final_text is not None:
            self.buffer = final_text
        self.status_icon = "✅" if success else "❌"
        self.status_label = "Selesai" if success else "Gagal"
        self._flush(final=True)

    def finalize_with_delegation(
        self,
        final_text: str,
        session_id: str,
        button_label: str = "🚀 Delegasikan ke Agen IDE",
    ) -> None:
        """Selesaikan stream dengan menyertakan tombol inline delegasi ke agen IDE."""
        if self.is_completed:
            return
        self.is_completed = True
        self.buffer = final_text
        self.status_icon = "🎯"
        self.status_label = "Siap Didelegasikan"

        content = self.buffer.strip()
        rendered_text = f"🤖 <b>Aegis Agent:</b>\n\n{sanitize_telegram_html(content)}"
        if len(rendered_text) > 4000:
            rendered_text = rendered_text[:3980] + "\n\n<i>...(dipotong)</i>"

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": button_label,
                        "callback_data": f"agent:delegate:{session_id}",
                    }
                ]
            ]
        }

        if self.message_id and self.bot_client:
            try:
                self.bot_client.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=rendered_text,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(
                    "StreamRelay finalize_with_delegation: GAGAL mengedit pesan (chat_id=%s): %s",
                    self.chat_id, e,
                )

    def error(self, error_message: str) -> None:
        """Laporkan error pada stream."""
        if self.is_completed:
            return
        self.is_completed = True
        err_display = sanitize_telegram_html(error_message)
        rendered = f"❌ <b>Terjadi Kesalahan:</b>\n\n<code>{err_display}</code>"
        if self.message_id and self.bot_client:
            try:
                self.bot_client.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=rendered,
                )
            except Exception as e:
                logger.error(
                    "StreamRelay error: GAGAL mengirim pesan error ke chat_id=%s: %s",
                    self.chat_id, e,
                )

    def error_with_retry(
        self,
        error_message: str,
        retry_callback_data: str,
        warning_header: str = "⚠️ <b>Gagal Menghubungi LLM</b>",
    ) -> None:
        """Laporkan error pada stream dengan tombol inline retry."""
        if self.is_completed:
            return
        self.is_completed = True
        err_display = sanitize_telegram_html(error_message)
        rendered = (
            f"{warning_header}\n\n"
            f"<b>Detail:</b> <code>{err_display}</code>\n\n"
            f"<i>Silakan periksa koneksi atau klik tombol di bawah untuk mencoba kembali.</i>"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "🔄 Coba Lagi",
                        "callback_data": retry_callback_data,
                    }
                ]
            ]
        }
        if self.message_id and self.bot_client:
            try:
                self.bot_client.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=rendered,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(
                    "StreamRelay error_with_retry: GAGAL mengedit pesan (chat_id=%s): %s",
                    self.chat_id, e,
                )
