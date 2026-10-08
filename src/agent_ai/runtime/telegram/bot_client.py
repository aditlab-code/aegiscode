from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import requests

logger = logging.getLogger("agent_ai.runtime.telegram.bot_client")


class TelegramBotClient:
    """Klien HTTP untuk berinteraksi dengan Telegram Bot API."""

    def __init__(self, bot_token: str, timeout: int = 30):
        self.bot_token = bot_token.strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = timeout
        self._offset = 0
        self._polling_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _post(self, method: str, payload: Dict[str, Any], request_timeout: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{method}"
        to = request_timeout or (self.timeout + 5)
        try:
            resp = requests.post(url, json=payload, timeout=to)
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Telegram API error for %s: %s", method, data.get("description"))
            return data
        except Exception as e:
            logger.error("HTTP error during %s: %s", method, str(e))
            return {"ok": False, "description": str(e)}

    def get_me(self) -> Dict[str, Any]:
        """Dapatkan profil bot Telegram saat ini."""
        res = self._post("getMe", {}, request_timeout=10)
        if res.get("ok"):
            return res.get("result", {})
        return {}

    def get_updates(self) -> List[Dict[str, Any]]:
        """Lakukan long-polling getUpdates ke Telegram Bot API."""
        payload = {
            "offset": self._offset,
            "timeout": self.timeout,
        }
        res = self._post("getUpdates", payload, request_timeout=self.timeout + 5)
        if not res.get("ok"):
            return []
        updates = res.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """Kirim pesan teks ke chat_id dengan opsi inline keyboard."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        res = self._post("sendMessage", payload, request_timeout=10)
        return res.get("result", {}) if res.get("ok") else {}

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """Perbarui isi pesan teks yang sudah terkirim."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        res = self._post("editMessageText", payload, request_timeout=10)
        return res.get("result", {}) if res.get("ok") else {}

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> bool:
        """Kirim konfirmasi bahwa callback query (tombol inline) telah diterima."""
        payload: Dict[str, Any] = {
            "callback_query_id": callback_query_id,
        }
        if text:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
        res = self._post("answerCallbackQuery", payload, request_timeout=10)
        return bool(res.get("ok", False))

    def set_my_commands(self, commands: Optional[List[Dict[str, str]]] = None) -> bool:
        """Daftarkan menu perintah '/' bot agar muncul di tombol menu Telegram."""
        if commands is None:
            commands = [
                {"command": "status", "description": "Cek status aktif agen dan gateway"},
                {"command": "repo", "description": "Inspeksi repositori & git branch aktif"},
                {"command": "mode", "description": "Ganti mode HITL (ask vs agents)"},
                {"command": "agents", "description": "Lihat armada subagen Olympus aktif"},
                {"command": "skills", "description": "Pilih active skill pemandu agen"},
                {"command": "provider", "description": "Pilih/ganti provider LLM aktif"},
                {"command": "model", "description": "Pilih model LLM terkonfigurasi di IDE"},
                {"command": "testprovider", "description": "Uji latensi koneksi provider aktif"},
                {"command": "steer", "description": "Kirim instruksi pengarah ke Agen"},
                {"command": "help", "description": "Panduan penggunaan Aegis Companion"},
            ]
        res = self._post("setMyCommands", {"commands": commands}, request_timeout=10)
        return bool(res.get("ok", False))

    def start_polling(self, on_update: Callable[[Dict[str, Any]], None]) -> None:
        """Jalankan background long-polling loop di daemon thread."""
        if self.is_polling():
            return

        self._stop_event.clear()
        try:
            self.set_my_commands()
        except Exception:
            pass

        def _loop():
            while not self._stop_event.is_set():
                try:
                    updates = self.get_updates()
                    for update in updates:
                        if self._stop_event.is_set():
                            break
                        try:
                            on_update(update)
                        except Exception as ex:
                            logger.error("Error in on_update handler: %s", str(ex))
                except Exception as ex:
                    logger.error("Polling loop exception: %s", str(ex))
                    time.sleep(2)

        self._polling_thread = threading.Thread(target=_loop, name="TelegramPoller", daemon=True)
        self._polling_thread.start()

    def stop_polling(self) -> None:
        """Hentikan background long-polling loop."""
        self._stop_event.set()
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=2.0)
        self._polling_thread = None

    def is_polling(self) -> bool:
        """Cek apakah background polling sedang aktif."""
        return self._polling_thread is not None and self._polling_thread.is_alive()
