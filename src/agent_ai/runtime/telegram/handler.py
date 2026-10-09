from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.gate import TelegramContextGate
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.security import TelegramSecurityManager
from agent_ai.runtime.telegram.views import (
    DEFAULT_SKILLS,
    render_chat_templates_view,
    render_config_llm_view,
    render_help_view,
    render_mode_view,
    render_model_list_view,
    render_ping_result_view,
    render_provider_list_view,
    render_repo_view,
    render_skill_selected_view,
)

logger = logging.getLogger("agent_ai.runtime.telegram.handler")


class TelegramUpdateHandler:
    """Router pesan dan callback query Telegram Companion berbasis Command & Callback Dispatcher."""

    def __init__(
        self,
        bot_client: TelegramBotClient,
        security_manager: TelegramSecurityManager,
        pairing_manager: PairingManager,
        on_hitl_action: Optional[Callable[[str, str], None]] = None,
        on_steer_command: Optional[Callable[..., None]] = None,
        get_runtime_status: Optional[Callable[[], str]] = None,
        get_repo_info: Optional[Callable[[], Dict[str, Any]]] = None,
        get_mode: Optional[Callable[[], str]] = None,
        set_mode: Optional[Callable[[str], str]] = None,
        get_agents: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        get_providers: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        set_provider: Optional[Callable[[str], None]] = None,
        test_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        get_models: Optional[Callable[[Optional[str]], List[Dict[str, Any]]]] = None,
        set_active_model: Optional[Callable[[str], None]] = None,
        get_skills: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        set_active_skill: Optional[Callable[[str], None]] = None,
        get_active_skill: Optional[Callable[[], Optional[str]]] = None,
        on_prompt_retry: Optional[Callable[[str, int], bool]] = None,
        on_agent_delegate: Optional[Callable[[str, int], bool]] = None,
        gate: Optional[TelegramContextGate] = None,
    ) -> None:
        self.bot_client = bot_client
        self.security_manager = security_manager
        self.pairing_manager = pairing_manager
        self.on_hitl_action = on_hitl_action
        self.on_steer_command = on_steer_command
        self.get_runtime_status = get_runtime_status
        self.get_repo_info = get_repo_info
        self.get_mode = get_mode
        self.set_mode = set_mode
        self.get_agents = get_agents
        self.get_providers = get_providers
        self.set_provider = set_provider
        self.test_provider = test_provider
        self.get_models = get_models
        self.set_active_model = set_active_model
        self.get_skills = get_skills
        self.set_active_skill = set_active_skill
        self.get_active_skill = get_active_skill
        self.on_prompt_retry = on_prompt_retry
        self.on_agent_delegate = on_agent_delegate
        self.gate = gate

        # Router Perintah Resmi
        self._command_router: Dict[str, Callable[[int, int, str, str], None]] = {
            "/repo": self._handle_repo,
            "/aegis_mode": self._handle_mode,
            "/aegis_chat": self._handle_chat,
            "/config_llm": self._handle_config_llm,
            "/help": self._handle_help,
            "/status": self._handle_status,
            "/agents": self._handle_agents,
        }

        # Router Callback Interaktif berdasarkan Prefix
        self._callback_router: List[tuple[str, Callable[[str, Optional[int], Optional[int], Dict[str, Any], str], None]]] = [
            ("hitl:", self._handle_hitl_cb),
            ("mode:", self._handle_mode_cb),
            ("config:", self._handle_config_cb),
            ("provider:", self._handle_provider_cb),
            ("model:", self._handle_model_cb),
            ("skill:", self._handle_skill_cb),
            ("prompt:retry:", self._handle_retry_cb),
            ("agent:delegate:", self._handle_delegate_cb),
        ]

    def handle_update(self, update: Dict[str, Any]) -> None:
        """Proses satu update dari Telegram Bot API."""
        if "message" in update:
            self._handle_message(update["message"])
        elif "callback_query" in update:
            self._handle_callback_query(update["callback_query"])

    def _handle_message(self, message: Dict[str, Any]) -> None:
        chat_id = message.get("chat", {}).get("id")
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        text = str(message.get("text", "")).strip()

        if not chat_id or not user_id:
            return

        # 1. Alur Khusus Pairing: /start pair_<token>
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].startswith("pair_"):
                otp_token = parts[1][len("pair_"):].strip()
                if self.pairing_manager.validate_token(otp_token):
                    username = from_user.get("username")
                    first_name = from_user.get("first_name")
                    self.security_manager.save_paired_user(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                    )
                    reply = (
                        "✅ <b>Pairing Berhasil!</b>\n\n"
                        "Akun Telegram Anda resmi terhubung ke AegisCode Workstation. "
                        "Anda kini akan menerima alert persetujuan dan dapat memantau jalannya agen."
                    )
                    self.bot_client.send_message(chat_id=chat_id, text=reply)
                    return
                else:
                    sender_username = from_user.get("username")
                    if self.security_manager.is_authorized(user_id, username=sender_username):
                        self.bot_client.send_message(
                            chat_id=chat_id,
                            text="ℹ️ Perangkat Anda sudah terhubung ke AegisCode.",
                        )
                        return
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text="❌ <b>Token Tidak Valid</b>\nToken pairing salah atau telah kedaluwarsa (maks 5 menit). Silakan scan ulang QR Code.",
                    )
                    return

        # 2. Pemeriksaan Otorisasi Pengguna (Zero-Trust Whitelist)
        sender_username = from_user.get("username")
        if not self.security_manager.is_authorized(user_id, username=sender_username):
            deny_text = (
                "⛔ <b>Akses Ditolak</b>\n\n"
                "Akun Anda tidak terdaftar dalam whitelist AegisCode. "
                "Silakan pindai QR code pairing resmi dari layar IDE atau terminal Anda."
            )
            self.bot_client.send_message(chat_id=chat_id, text=deny_text)
            return

        # 3. Router Perintah & Pesan
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower().split("@")[0]
            args = parts[1].strip() if len(parts) > 1 else ""

            handler = self._command_router.get(cmd)
            if handler:
                handler(chat_id, user_id, text, args)
            else:
                self._handle_unknown_command(chat_id, cmd)
        else:
            # Pesan teks bebas langsung diarahkan ke chat turn
            self._handle_chat(chat_id, user_id, text, args=text)

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    def _handle_repo(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        info = self.get_repo_info() if self.get_repo_info else {
            "name": "AegisCode",
            "root": "N/A",
            "branch": "main",
            "last_commit": "HEAD",
            "uncommitted_changes": 0,
            "is_dirty": False,
        }
        repo_text = render_repo_view(info)
        self.bot_client.send_message(chat_id=chat_id, text=repo_text)

    def _handle_mode(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        arg = args.lower().strip()
        if arg:
            if arg in ("ask", "agents"):
                if self.set_mode:
                    self.set_mode(arg)
                mode_display = "Ask ⏸️ (Perlu Konfirmasi)" if arg == "ask" else "Agents ⚡ (Otonom Penuh)"
                desc = (
                    "Agen akan meminta persetujuan sebelum menjalankan aksi kritis."
                    if arg == "ask"
                    else "Agen akan mengeksekusi aksi secara mandiri dan mengirimkan ringkasan audit log."
                )
                confirm_text = (
                    f"✅ <b>Mode Operasional Diperbarui!</b>\n\n"
                    f"Mode saat ini: <b>{mode_display}</b>\n\n"
                    f"{desc}"
                )
                self.bot_client.send_message(chat_id=chat_id, text=confirm_text)
            else:
                self.bot_client.send_message(
                    chat_id=chat_id,
                    text="❌ <b>Mode Tidak Valid!</b>\nGunakan <code>/aegis_mode ask</code> atau <code>/aegis_mode agents</code>.",
                )
        else:
            current_mode = self.get_mode().lower() if self.get_mode else "ask"
            mode_text, keyboard = render_mode_view(current_mode)
            self.bot_client.send_message(chat_id=chat_id, text=mode_text, reply_markup=keyboard)

    def _handle_chat(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        clean_instruction = args.strip()
        if clean_instruction:
            self._dispatch_turn(chat_id, clean_instruction)
        else:
            # Tanpa argumen: tampilkan menu template skills pemandu
            active_skill = self.get_active_skill() if self.get_active_skill else None
            skills = self.get_skills() if self.get_skills else DEFAULT_SKILLS
            view_text, keyboard = render_chat_templates_view(active_skill=active_skill, skills=skills)
            self.bot_client.send_message(chat_id=chat_id, text=view_text, reply_markup=keyboard)

    def _handle_config_llm(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        providers = self.get_providers() if self.get_providers else []
        active_provider_name = ""
        for p in providers:
            if p.get("is_active"):
                active_provider_name = p.get("name") or p.get("id", "")
                break
        if not active_provider_name and providers:
            active_provider_name = providers[0].get("name") or providers[0].get("id", "")

        models = self.get_models() if self.get_models else []
        active_model_name = ""
        for m in models:
            if m.get("is_active"):
                active_model_name = m.get("name") or m.get("id", "")
                break
        if not active_model_name and models:
            active_model_name = models[0].get("name") or models[0].get("id", "")

        view_text, keyboard = render_config_llm_view(
            active_provider=active_provider_name or "Default",
            active_model=active_model_name or "Default",
            is_ready=True,
        )
        self.bot_client.send_message(chat_id=chat_id, text=view_text, reply_markup=keyboard)

    def _handle_help(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        help_text = render_help_view()
        self.bot_client.send_message(chat_id=chat_id, text=help_text)

    def _handle_status(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        status_text = (
            self.get_runtime_status()
            if self.get_runtime_status
            else "🟢 AegisCode Aktif dan Siap."
        )
        self.bot_client.send_message(chat_id=chat_id, text=status_text)

    def _handle_agents(self, chat_id: int, user_id: int, text: str, args: str) -> None:
        agents = self.get_agents() if self.get_agents else []
        if not agents:
            agents = [
                {"name": "Zeus Orchestrator", "role": "Orchestrator & Ship Master", "status": "Standby"},
                {"name": "Athena Planner", "role": "Architect & Spec Planner", "status": "Active"},
                {"name": "Hephaestus Coder", "role": "Core Implementer & Builder", "status": "Standby"},
                {"name": "Heracles Tester", "role": "Verification & QA Tester", "status": "Standby"},
                {"name": "Hermes Scout", "role": "Explorer & Fast Scout", "status": "Standby"},
                {"name": "Themis Reviewer", "role": "Quality & Security Reviewer", "status": "Standby"},
            ]

        agent_lines = []
        for a in agents:
            status_icon = "🟢" if a.get("status") == "Active" or a.get("is_active") else "⚪"
            status_text = a.get("status", "Standby")
            agent_lines.append(
                f"{status_icon} <b>{a.get('name')}</b> ({status_text})\n"
                f"   <i>Peran:</i> {a.get('role', '-')}"
            )

        agents_text = (
            "🏛️ <b>Armada Subagen Olympus (Olympus Fleet):</b>\n\n"
            + "\n\n".join(agent_lines)
        )
        self.bot_client.send_message(chat_id=chat_id, text=agents_text)

    def _handle_unknown_command(self, chat_id: int, cmd: str) -> None:
        legacy_cmds = {"/provider", "/mode", "/steer", "/skills", "/model", "/testprovider"}
        if cmd in legacy_cmds:
            msg = (
                f"⚠️ <b>Perintah <code>{cmd}</code> Telah Diperbarui</b>\n\n"
                "Untuk menyederhanakan interaksi, AegisCode menggunakan 5 perintah terpadu:\n"
                "• <code>/repo</code> - Status repositori & git\n"
                "• <code>/aegis_mode</code> - Ganti mode Ask ⏸️ atau Agents ⚡\n"
                "• <code>/aegis_chat</code> - Konsultasi & template skill terpandu\n"
                "• <code>/config_llm</code> - Kelola provider, model, dan uji ping latensi\n"
                "• <code>/help</code> - Panduan lengkap\n\n"
                "Ketik <code>/help</code> untuk panduan lengkap."
            )
        else:
            msg = (
                f"❌ <b>Perintah Tidak Dikenal:</b> <code>{cmd}</code>\n\n"
                "Gunakan <code>/help</code> untuk melihat daftar perintah resmi yang tersedia."
            )
        self.bot_client.send_message(chat_id=chat_id, text=msg)

    def _dispatch_turn(self, chat_id: int, instruction: str) -> None:
        if not self.on_steer_command:
            logger.warning("on_steer_command tidak terkonfigurasi pada handler.")
            self.bot_client.send_message(
                chat_id=chat_id,
                text="⚠️ Layanan agen belum terhubung untuk menerima instruksi.",
            )
            return

        try:
            self.on_steer_command(instruction, chat_id=chat_id)
        except TypeError:
            self.on_steer_command(instruction)

    # =========================================================================
    # CALLBACK QUERY HANDLERS
    # =========================================================================

    def _handle_callback_query(self, cb: Dict[str, Any]) -> None:
        cb_id = cb.get("id")
        from_user = cb.get("from", {})
        user_id = from_user.get("id")
        data = str(cb.get("data", "")).strip()
        message = cb.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        if not user_id or not cb_id:
            return

        # Otorisasi Callback
        sender_username = from_user.get("username")
        if not self.security_manager.is_authorized(user_id, username=sender_username):
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text="Akses Ditolak!",
                show_alert=True,
            )
            return

        for prefix, handler in self._callback_router:
            if data.startswith(prefix):
                handler(cb_id, chat_id, message_id, message, data)
                return

        # Callback tidak dikenal
        self.bot_client.answer_callback_query(callback_query_id=cb_id, text="Aksi tidak dikenal.")

    def _handle_hitl_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        parts = data.split(":", 2)
        if len(parts) == 3:
            action = parts[1].lower()
            approval_id = parts[2]

            if self.on_hitl_action:
                self.on_hitl_action(action, approval_id)

            status_label = "✅ DISETUJUI (ALLOWED)" if action == "allow" else "❌ DITOLAK (DENIED)"
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text=f"Persetujuan dicatat: {action.upper()}",
            )

            if chat_id and message_id:
                orig_text = message.get("text", "")
                updated_text = f"{orig_text}\n\n<b>Status:</b> {status_label}"
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=updated_text,
                    reply_markup=None,
                )

    def _handle_mode_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        target_mode = data[len("mode:set:"):].lower().strip()
        if target_mode in ("ask", "agents"):
            if self.set_mode:
                self.set_mode(target_mode)
            label = "Ask ⏸️" if target_mode == "ask" else "Agents ⚡"
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text=f"Mode diubah ke: {label}",
            )
            if chat_id and message_id:
                desc = (
                    "Aksi kritis akan meminta konfirmasi user."
                    if target_mode == "ask"
                    else "Aksi dijalankan otonom dengan audit log."
                )
                updated_text = (
                    f"⚙️ <b>Kontrol Mode Operasional:</b>\n\n"
                    f"✅ Mode aktif saat ini: <b>{label}</b>\n\n"
                    f"{desc}"
                )
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=updated_text,
                    reply_markup=None,
                )

    def _handle_config_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        action = data[len("config:"):].strip()

        if action == "main":
            self.bot_client.answer_callback_query(callback_query_id=cb_id)
            if chat_id and message_id:
                providers = self.get_providers() if self.get_providers else []
                active_p = next((p.get("name") or p.get("id") for p in providers if p.get("is_active")), "Default")
                models = self.get_models() if self.get_models else []
                active_m = next((m.get("name") or m.get("id") for m in models if m.get("is_active")), "Default")

                view_text, kb = render_config_llm_view(active_p, active_m, is_ready=True)
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=view_text,
                    reply_markup=kb,
                )
        elif action == "providers":
            self.bot_client.answer_callback_query(callback_query_id=cb_id)
            if chat_id and message_id:
                providers = self.get_providers() if self.get_providers else []
                view_text, kb = render_provider_list_view(providers)
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=view_text,
                    reply_markup=kb,
                )
        elif action == "models":
            self.bot_client.answer_callback_query(callback_query_id=cb_id)
            if chat_id and message_id:
                models = self.get_models() if self.get_models else []
                view_text, kb = render_model_list_view(models)
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=view_text,
                    reply_markup=kb,
                )
        elif action == "ping":
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text="⚡ Menguji konektivitas LLM...",
            )
            if chat_id and message_id:
                res = self.test_provider() if self.test_provider else {"status": "ok", "provider": "OpenCode", "model": "zen", "latency_ms": 42.0}
                view_text, kb = render_ping_result_view(res)
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=view_text,
                    reply_markup=kb,
                )
        elif action == "skills":
            self.bot_client.answer_callback_query(callback_query_id=cb_id)
            if chat_id and message_id:
                active_skill = self.get_active_skill() if self.get_active_skill else None
                skills = self.get_skills() if self.get_skills else DEFAULT_SKILLS
                view_text, kb = render_chat_templates_view(active_skill=active_skill, skills=skills)
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=view_text,
                    reply_markup=kb,
                )

    def _handle_provider_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        provider_id = data[len("provider:set:"):].strip()
        if self.set_provider:
            self.set_provider(provider_id)
        self.bot_client.answer_callback_query(
            callback_query_id=cb_id,
            text=f"Provider aktif diubah ke: {provider_id}",
        )
        if chat_id and message_id:
            models = self.get_models(provider_id) if self.get_models else []
            if models:
                view_text, kb = render_model_list_view(models, provider_id=provider_id)
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=view_text,
                    reply_markup=kb,
                )
            else:
                updated_text = (
                    f"🤖 <b>LLM Provider Diperbarui</b>\n\n"
                    f"⭐ Provider aktif saat ini: <code>{provider_id}</code>"
                )
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=updated_text,
                    reply_markup={"inline_keyboard": [[{"text": "🔙 Kembali ke Config", "callback_data": "config:main"}]]},
                )

    def _handle_model_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        model_name = data[len("model:set:"):].strip()
        if self.set_active_model:
            self.set_active_model(model_name)
        self.bot_client.answer_callback_query(
            callback_query_id=cb_id,
            text=f"Model aktif diubah ke: {model_name}",
        )
        if chat_id and message_id:
            updated_text = (
                f"🧠 <b>Model LLM Diperbarui!</b>\n\n"
                f"✅ Model aktif saat ini: <code>{model_name}</code>"
            )
            self.bot_client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_text,
                reply_markup={"inline_keyboard": [[{"text": "🔙 Kembali ke Config", "callback_data": "config:main"}]]},
            )

    def _handle_skill_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        skill_id = data[len("skill:set:"):].strip()
        if self.set_active_skill:
            self.set_active_skill(skill_id)
        self.bot_client.answer_callback_query(
            callback_query_id=cb_id,
            text=f"Skill diaktifkan: {skill_id}",
        )
        if chat_id and message_id:
            # Cari nama skill & template dari DEFAULT_SKILLS
            skills = self.get_skills() if self.get_skills else DEFAULT_SKILLS
            found = next((s for s in skills if s.get("id") == skill_id), None)
            skill_name = found.get("name", skill_id) if found else skill_id
            template_prompt = (
                found.get("template")
                if found and found.get("template")
                else f"Gunakan skill {skill_name} untuk membantu saya mengerjakan: <tulis kebutuhan>"
            )

            view_text, kb = render_skill_selected_view(skill_id, skill_name, template_prompt)
            self.bot_client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=view_text,
                reply_markup=kb,
            )

    def _handle_retry_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        cache_id = data[len("prompt:retry:"):].strip()
        target_chat = chat_id or (message.get("from", {}).get("id"))
        if self.on_prompt_retry and target_chat:
            handled = self.on_prompt_retry(cache_id, target_chat)
            if handled:
                self.bot_client.answer_callback_query(
                    callback_query_id=cb_id,
                    text="🔄 Mencoba kembali instruksi...",
                )
            else:
                self.bot_client.answer_callback_query(
                    callback_query_id=cb_id,
                    text="⚠️ Cache percobaan ulang sudah kedaluwarsa.",
                    show_alert=True,
                )
        else:
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text="Fitur retry belum tersedia.",
                show_alert=True,
            )

    def _handle_delegate_cb(
        self,
        cb_id: str,
        chat_id: Optional[int],
        message_id: Optional[int],
        message: Dict[str, Any],
        data: str,
    ) -> None:
        sess_id = data[len("agent:delegate:"):].strip()
        target_chat = chat_id or (message.get("from", {}).get("id"))
        if self.on_agent_delegate and target_chat:
            handled = self.on_agent_delegate(sess_id, target_chat)
            if handled:
                self.bot_client.answer_callback_query(
                    callback_query_id=cb_id,
                    text="🚀 Tugas berhasil didelegasikan ke Agen IDE!",
                )
            else:
                self.bot_client.answer_callback_query(
                    callback_query_id=cb_id,
                    text="⚠️ Sesi tidak ditemukan atau gagal didelegasikan.",
                    show_alert=True,
                )
        else:
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text="Fitur delegasi belum tersedia.",
                show_alert=True,
            )
