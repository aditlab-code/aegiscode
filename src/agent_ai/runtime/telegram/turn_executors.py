from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Callable, Optional, Tuple

from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.gate import TelegramContextGate
from agent_ai.runtime.telegram.stream_relay import (
    TelegramStreamRelay,
    sanitize_telegram_html,
)

logger = logging.getLogger("agent_ai.runtime.telegram.turn_executors")


def should_offer_delegation(reply: str, active_skill: Optional[str] = None) -> bool:
    """Cek apakah balasan asisten cocok untuk menawarkan tombol delegasi ke agen IDE."""
    active_s = (active_skill or "").lower()
    if active_s in ("interview-me", "spec-driven-development", "planning-and-task-breakdown"):
        return True
    reply_lower = (reply or "").lower()
    keywords = ["q:", "guess:", "outcome:", "restate", "ringkasan", "spesifikasi", "kesimpulan"]
    return any(k in reply_lower for k in keywords)


class TaskMonitor:
    """Logika pemantauan siklus hidup task di IDE hingga selesai/timeout/error."""

    @staticmethod
    def poll_task_until_done(
        svc: Any,
        task_id: str,
        relay: TelegramStreamRelay,
        max_wait: int = 300,
        status_interval: int = 15,
        poll_interval: float = 3.0,
    ) -> Tuple[str, str]:
        """Pantau status task secara berkala hingga selesai atau batas waktu maksimal tercapai.

        Returns:
            Tuple[final_status, report_text]
        """
        t0 = time.time()
        final_status = "running"
        last_status_update = t0

        relay.set_status("⚡", f"Menjalankan task <code>{task_id[:8]}</code> di IDE...")

        while time.time() - t0 < max_wait:
            time.sleep(poll_interval)
            elapsed = int(time.time() - t0)
            try:
                curr_task = svc.get_task(task_id)
                st = (curr_task or {}).get("status", "running")
                if st in ("completed", "done", "success"):
                    final_status = "completed"
                    break
                elif st in ("failed", "error", "cancelled"):
                    final_status = st
                    break
            except Exception as poll_err:
                logger.warning("Error saat polling status task %s: %s", task_id, poll_err)

            # Kirim status update berkala
            if time.time() - last_status_update >= status_interval:
                relay.set_status("⏳", f"Agen IDE sedang memproses task... ({elapsed}s)")
                last_status_update = time.time()

        if final_status == "running":
            final_status = "timeout"

        report_text = ""
        try:
            report_res = svc.get_task_report(task_id) or {}
            report_text = report_res.get("summary") or report_res.get("report") or ""
        except Exception as rpt_err:
            logger.warning("Gagal membaca task report untuk task %s: %s", task_id, rpt_err)

        if not report_text:
            if final_status == "timeout":
                report_text = (
                    f"⏰ Task <code>{task_id[:12]}</code> masih berjalan setelah {max_wait}s. "
                    f"Silakan periksa progresnya di workstation IDE."
                )
            else:
                report_text = f"Tugas <code>{task_id[:12]}</code> selesai dengan status: <b>{final_status}</b>."

        return final_status, report_text


class AskModeTurnExecutor:
    """Eksekutor giliran untuk Ask Mode (konsultatif & bantuan interaktif)."""

    def __init__(
        self,
        bot_client: TelegramBotClient,
        gate: Optional[TelegramContextGate] = None,
        get_active_skill: Optional[Callable[[], Optional[str]]] = None,
        save_retry_prompt: Optional[Callable[[str, str, int, str], None]] = None,
    ) -> None:
        self.bot_client = bot_client
        self.gate = gate
        self.get_active_skill = get_active_skill
        self._save_retry_prompt_cb = save_retry_prompt

    def _record_retry_prompt(self, instruction: str, chat_id: int, error_msg: str) -> str:
        cache_id = f"retry-{uuid.uuid4().hex[:8]}"
        if self.gate:
            self.gate.save_retry_prompt(cache_id, instruction, chat_id, error_msg)
        elif self._save_retry_prompt_cb:
            self._save_retry_prompt_cb(cache_id, instruction, chat_id, error_msg)
        return cache_id

    def execute(self, instruction: str, chat_id: int, svc: Any) -> None:
        """Jalankan turn konsultasi Ask Mode dengan indikator typing native Telegram."""
        turn_id = f"ASK-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        logger.info("[ASK-MODE] [START] Turn %s started for chat_id=%s", turn_id, chat_id)

        stop_typing = threading.Event()

        def _typing_worker():
            while not stop_typing.is_set():
                try:
                    if hasattr(self.bot_client, "send_chat_action"):
                        self.bot_client.send_chat_action(chat_id=chat_id, action="typing")
                except Exception as ex:
                    logger.debug("Failed sending chat action typing: %s", ex)
                stop_typing.wait(4.0)

        typing_thread = threading.Thread(target=_typing_worker, name=f"Typing-{turn_id}", daemon=True)
        typing_thread.start()

        try:
            res = svc.dispatch_remote_turn(content=instruction, mode="ask")
        except Exception as exc:
            stop_typing.set()
            if typing_thread.is_alive():
                typing_thread.join(timeout=0.5)

            logger.error("[ASK-MODE] [ERROR] Turn %s failed: %s", turn_id, exc, exc_info=True)
            cache_id = self._record_retry_prompt(instruction, chat_id, str(exc))
            error_text = (
                f"❌ <b>Terjadi Kesalahan Saat Menghubungi LLM</b>\n\n"
                f"<i>Detail:</i> {sanitize_telegram_html(str(exc))}\n\n"
                f"Gunakan tombol di bawah untuk mencoba kembali:"
            )
            retry_markup = {
                "inline_keyboard": [
                    [{"text": "🔄 Coba Lagi", "callback_data": f"prompt:retry:{cache_id}"}]
                ]
            }
            self.bot_client.send_message(chat_id=chat_id, text=error_text, reply_markup=retry_markup)
            return

        stop_typing.set()
        if typing_thread.is_alive():
            typing_thread.join(timeout=0.5)

        consult_res = (res or {}).get("consultant_result") or {}
        asst_turn = (res or {}).get("assistant_turn") or {}
        reply = (
            consult_res.get("reply")
            or asst_turn.get("content")
            or "Respons selesai diterima dari agen."
        )

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info("[ASK-MODE] [FINISH] Turn %s completed in %d ms", turn_id, duration_ms)

        rendered_text = f"🤖 <b>Aegis Agent:</b>\n\n{sanitize_telegram_html(reply)}"
        if len(rendered_text) > 4000:
            rendered_text = rendered_text[:3980] + "\n\n<i>...(dipotong)</i>"

        reply_markup = None
        session_id = (res or {}).get("session_id")
        active_skill = self.get_active_skill() if self.get_active_skill else None
        if session_id and should_offer_delegation(reply, active_skill=active_skill):
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🚀 Delegasikan ke Agen IDE",
                            "callback_data": f"agent:delegate:{session_id}",
                        }
                    ]
                ]
            }

        self.bot_client.send_message(
            chat_id=chat_id,
            text=rendered_text,
            reply_markup=reply_markup,
        )


class AgentsModeTurnExecutor:
    """Eksekutor giliran untuk Agents Mode (eksekusi otonom mandiri dengan validasi ketat task_id)."""

    def __init__(
        self,
        bot_client: TelegramBotClient,
        gate: TelegramContextGate,
        max_wait: int = 300,
        status_interval: int = 15,
        poll_interval: float = 3.0,
    ) -> None:
        self.bot_client = bot_client
        self.gate = gate
        self.max_wait = max_wait
        self.status_interval = status_interval
        self.poll_interval = poll_interval

    def execute(self, instruction: str, chat_id: int, svc: Any) -> None:
        """Jalankan turn Agents Mode secara otonom dengan streaming relay.

        Validasi ketat: Jika task_id tidak ada, langsung fail-fast tanpa silent fallback.
        """
        turn_id = f"AGENTS-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        logger.info("[AGENTS-MODE] [START] Turn %s started for chat_id=%s", turn_id, chat_id)

        relay = TelegramStreamRelay(
            bot_client=self.bot_client,
            chat_id=chat_id,
            initial_status="⚡ <i>Menyiapkan eksekusi tugas otonom di IDE...</i>",
        )

        task_id = None
        try:
            res = svc.dispatch_remote_turn(content=instruction, mode="agent")
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "[AGENTS-MODE] [ERROR] Turn %s dispatch error in %d ms: %s",
                turn_id,
                duration_ms,
                exc,
                exc_info=True,
            )
            cache_id = f"retry-{uuid.uuid4().hex[:8]}"
            self.gate.save_retry_prompt(cache_id, instruction, chat_id, str(exc))
            relay.error(
                f"Gagal memulai tugas otonom: {exc}\n\n"
                f"<i>ID Retry:</i> <code>{cache_id}</code>"
            )
            return

        task_info = (res or {}).get("task") or {}
        task_id = task_info.get("task_id")

        # VALIDASI KETAT TASK ID: Fail-fast bila task_id tidak ada
        if not task_id:
            err_msg = "Gagal memulai tugas otonom: task ID tidak ditemukan dalam respons backend."
            logger.error(
                "[AGENTS-MODE] [FAIL-FAST] Turn %s: %s (keys=%s)",
                turn_id,
                err_msg,
                list((res or {}).keys()),
            )
            cache_id = f"retry-{uuid.uuid4().hex[:8]}"
            self.gate.save_retry_prompt(cache_id, instruction, chat_id, err_msg)
            relay.error(f"{err_msg}\n\n<i>ID Retry:</i> <code>{cache_id}</code>")
            return

        session_id = (res or {}).get("session_id")
        self.gate.register_task(chat_id, task_id, session_id=session_id)

        try:
            final_status, report_text = TaskMonitor.poll_task_until_done(
                svc=svc,
                task_id=task_id,
                relay=relay,
                max_wait=self.max_wait,
                status_interval=self.status_interval,
                poll_interval=self.poll_interval,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "[AGENTS-MODE] [FINISH] Turn %s completed in %d ms (task=%s, status=%s)",
                turn_id,
                duration_ms,
                task_id,
                final_status,
            )
            relay.finalize(report_text, success=(final_status == "completed"))
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "[AGENTS-MODE] [ERROR] Turn %s monitoring error in %d ms: %s",
                turn_id,
                duration_ms,
                exc,
                exc_info=True,
            )
            relay.error(f"Terjadi kesalahan saat memantau tugas: {exc}")
        finally:
            self.gate.complete_task(chat_id, task_id)
