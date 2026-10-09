from collections import deque
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import requests

from agent_ai.runtime.telegram.lock import TelegramPollerLock

logger = logging.getLogger("agent_ai.runtime.telegram.bot_client")


class TelegramBotClient:
    """Klien HTTP untuk berinteraksi dengan Telegram Bot API."""

    def __init__(self, bot_token: str, timeout: int = 30, offset_path: Optional[Path] = None):
        self.bot_token = bot_token.strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = timeout
        self._offset_path = offset_path or Path(".aegis/run/telegram_offset.json")
        self._offset = self._load_persisted_offset()
        self._processed_update_ids: set[int] = set()
        self._recent_update_ids: deque[int] = deque(maxlen=2000)
        self._polling_thread: Optional[threading.Thread] = None
        self._polling_generation = 0
        self._stop_event = threading.Event()
        self._lock = TelegramPollerLock()
        self._lock_held = False

    def _load_persisted_offset(self) -> int:
        """Muat offset update Telegram terakhir yang tersimpan di disk jika ada."""
        try:
            if self._offset_path.is_file():
                data = json.loads(self._offset_path.read_text(encoding="utf-8"))
                return int(data.get("offset", 0))
        except Exception as ex:
            logger.debug("Tidak dapat memuat offset tersimpan: %s", ex)
        return 0

    def _persist_offset(self, offset: int) -> None:
        """Simpan offset update Telegram terbaru ke disk secara aman."""
        try:
            self._offset_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._offset_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps({"offset": offset}), encoding="utf-8")
            temp_path.replace(self._offset_path)
        except Exception as ex:
            logger.debug("Tidak dapat menyimpan offset: %s", ex)

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
        """Lakukan long-polling getUpdates ke Telegram Bot API dengan deduplikasi ketat."""
        payload = {
            "offset": self._offset,
            "timeout": self.timeout,
        }
        res = self._post("getUpdates", payload, request_timeout=self.timeout + 5)
        if not res.get("ok"):
            return []
        raw_updates = res.get("result", [])
        if not raw_updates:
            return []

        # Perbarui offset berdasarkan update_id tertinggi yang diterima
        max_update_id = max(u.get("update_id", 0) for u in raw_updates)
        if max_update_id >= self._offset:
            self._offset = max_update_id + 1
            self._persist_offset(self._offset)

        # Saring update yang sudah pernah diproses untuk mencegah eksekusi duplikat
        new_updates: List[Dict[str, Any]] = []
        for update in raw_updates:
            uid = update.get("update_id")
            if uid is None:
                continue
            if uid in self._processed_update_ids:
                logger.warning("Duplikasi update_id %s terdeteksi dan diabaikan.", uid)
                continue
            self._processed_update_ids.add(uid)
            self._recent_update_ids.append(uid)
            new_updates.append(update)

        if len(self._processed_update_ids) > 2500:
            self._processed_update_ids = set(self._recent_update_ids)

        return new_updates

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
    def send_chat_action(
        self,
        chat_id: int | str,
        action: str = "typing",
    ) -> bool:
        """Kirim indikator status chat action (misal: 'typing', 'upload_document')."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "action": action,
        }
        res = self._post("sendChatAction", payload, request_timeout=10)
        return bool(res.get("ok", False))

    def set_my_commands(self, commands: Optional[List[Dict[str, str]]] = None) -> bool:
        """Daftarkan menu perintah '/' bot agar muncul di tombol menu Telegram."""
        if commands is None:
            commands = [
                {"command": "repo", "description": "Status repositori, branch aktif & commit"},
                {"command": "aegis_mode", "description": "Ganti mode Ask (konfirmasi) vs Agents (otonom)"},
                {"command": "aegis_chat", "description": "Arahkan agen atau pilih template skills"},
                {"command": "config_llm", "description": "Konfigurasi LLM (provider, model, test ping)"},
                {"command": "help", "description": "Panduan resmi perintah Aegis Companion"},
                {"command": "status", "description": "Status gateway runtime & branch git"},
                {"command": "agents", "description": "Lihat armada subagen Olympus aktif"},
            ]
        res = self._post("setMyCommands", {"commands": commands}, request_timeout=10)
        return bool(res.get("ok", False))

    def get_my_commands(self) -> List[Dict[str, str]]:
        """Ambil daftar menu perintah bot yang terdaftar di Telegram."""
        res = self._post("getMyCommands", {}, request_timeout=10)
        if res.get("ok"):
            return res.get("result", [])
        return []

    def start_polling(self, on_update: Callable[[Dict[str, Any]], None]) -> bool:
        """Jalankan background long-polling loop di daemon thread dengan generation check dan lock."""
        if self.is_polling():
            return True

        if not self._lock.acquire():
            logger.warning("Poller lock tidak dapat diperoleh (ada instansi/proses poller lain aktif).")
            return False
        self._lock_held = True

        self._polling_generation += 1
        current_gen = self._polling_generation
        self._stop_event.clear()

        try:
            self.set_my_commands()
        except Exception:
            pass

        def _loop(gen: int):
            try:
                while not self._stop_event.is_set() and gen == self._polling_generation:
                    try:
                        updates = self.get_updates()
                        if self._stop_event.is_set() or gen != self._polling_generation:
                            break
                        for update in updates:
                            if self._stop_event.is_set() or gen != self._polling_generation:
                                break
                            try:
                                on_update(update)
                            except Exception as ex:
                                logger.error("Error in on_update handler: %s", str(ex))
                    except Exception as ex:
                        if not self._stop_event.is_set() and gen == self._polling_generation:
                            logger.error("Polling loop exception: %s", str(ex))
                            time.sleep(2)
            finally:
                if gen == self._polling_generation and self._lock_held:
                    self._lock.release()
                    self._lock_held = False

        self._polling_thread = threading.Thread(
            target=_loop,
            args=(current_gen,),
            name=f"TelegramPoller-gen{current_gen}",
            daemon=True,
        )
        self._polling_thread.start()
        return True

    def stop_polling(self) -> None:
        """Hentikan background long-polling loop secara bersih tanpa zombie thread."""
        self._stop_event.set()
        self._polling_generation += 1  # Invalidate thread yang sedang berjalan seketika
        if self._lock_held:
            self._lock.release()
            self._lock_held = False
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=0.5)
        self._polling_thread = None

    def is_polling(self) -> bool:
        """Cek apakah background polling sedang aktif."""
        return self._polling_thread is not None and self._polling_thread.is_alive()

