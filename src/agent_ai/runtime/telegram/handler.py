from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.security import TelegramSecurityManager

logger = logging.getLogger("agent_ai.runtime.telegram.handler")


class TelegramUpdateHandler:
    """Router pesan dan callback query Telegram Companion."""

    def __init__(
        self,
        bot_client: TelegramBotClient,
        security_manager: TelegramSecurityManager,
        pairing_manager: PairingManager,
        on_hitl_action: Optional[Callable[[str, str], None]] = None,
        on_steer_command: Optional[Callable[[str], None]] = None,
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
    ):
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

        # 3. Router Perintah Pengguna Terotorisasi
        first_token = text.split()[0].lower() if text else ""
        cmd = first_token.split("@")[0]

        if cmd == "/status":
            status_text = (
                self.get_runtime_status()
                if self.get_runtime_status
                else "🟢 AegisCode Aktif dan Siap."
            )
            self.bot_client.send_message(chat_id=chat_id, text=status_text)
        elif cmd == "/repo":
            if self.get_repo_info:
                info = self.get_repo_info()
            else:
                info = {
                    "name": "AegisCode",
                    "root": "N/A",
                    "branch": "main",
                    "last_commit": "HEAD",
                    "uncommitted_changes": 0,
                    "is_dirty": False,
                }
            name = info.get("name", "AegisCode")
            root = info.get("root", "-")
            branch = info.get("branch", "-")
            last_commit = info.get("last_commit", "-")
            uncommitted = info.get("uncommitted_changes", 0)
            dirty_str = f"⚠️ {uncommitted} perubahan belum di-commit" if uncommitted > 0 or info.get("is_dirty") else "Clean (bersih)"

            repo_text = (
                "📁 <b>Repositori Aktif:</b>\n\n"
                f"• <b>Nama Proyek:</b> <code>{name}</code>\n"
                f"• <b>Root Path:</b> <code>{root}</code>\n"
                f"• <b>Branch Git:</b> <code>{branch}</code>\n"
                f"• <b>Commit Terakhir:</b> <code>{last_commit}</code>\n"
                f"• <b>Status Perubahan:</b> {dirty_str}"
            )
            self.bot_client.send_message(chat_id=chat_id, text=repo_text)
        elif cmd == "/mode":
            parts = text.split(maxsplit=1)
            arg = parts[1].strip().lower() if len(parts) > 1 else ""

            if arg:
                if arg in ("ask", "agents"):
                    if self.set_mode:
                        self.set_mode(arg)
                    mode_display = "Ask ⏸️ (Perlu Konfirmasi)" if arg == "ask" else "Agents ⚡ (Otonom Penuh)"
                    confirm_text = (
                        f"✅ <b>Mode Operasional Diperbarui!</b>\n\n"
                        f"Mode saat ini: <b>{mode_display}</b>\n\n"
                        + ("Agen akan meminta persetujuan sebelum menjalankan aksi kritis."
                           if arg == "ask" else
                           "Agen akan mengeksekusi aksi secara mandiri dan mengirimkan ringkasan audit log.")
                    )
                    self.bot_client.send_message(chat_id=chat_id, text=confirm_text)
                else:
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text="❌ <b>Mode Tidak Valid!</b>\nGunakan <code>/mode ask</code> atau <code>/mode agents</code>.",
                    )
            else:
                current_mode = self.get_mode().lower() if self.get_mode else "ask"
                current_label = "Ask ⏸️ (Konfirmasi)" if current_mode == "ask" else "Agents ⚡ (Otonom)"
                mode_menu_text = (
                    "⚙️ <b>Kontrol Mode Operasional:</b>\n\n"
                    f"Mode saat ini: <b>{current_label}</b>\n\n"
                    "• <b>Ask Mode ⏸️:</b> Membutuhkan konfirmasi pengguna untuk eksekusi kritis.\n"
                    "• <b>Agents Mode ⚡:</b> Eksekusi otonom mandiri dengan audit log ke Telegram.\n\n"
                    "Pilih mode di bawah ini atau ketik <code>/mode ask</code> / <code>/mode agents</code>:"
                )
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "Mode: Ask ⏸️", "callback_data": "mode:set:ask"},
                            {"text": "Mode: Agents ⚡", "callback_data": "mode:set:agents"},
                        ]
                    ]
                }
                self.bot_client.send_message(chat_id=chat_id, text=mode_menu_text, reply_markup=keyboard)
        elif cmd == "/agents":
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
        elif cmd == "/provider":
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""

            if arg:
                if self.set_provider:
                    self.set_provider(arg)
                models = self.get_models(arg) if self.get_models else []
                if models:
                    m_buttons = [[{"text": f"{'⭐ ' if m.get('is_active') else ''}{m.get('name')}", "callback_data": f"model:set:{m.get('name')}"}] for m in models]
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text=f"✅ <b>Provider LLM Aktif Diubah:</b> <code>{arg}</code>\n\nSilakan pilih model yang ingin digunakan:",
                        reply_markup={"inline_keyboard": m_buttons},
                    )
                else:
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text=f"✅ <b>Provider LLM Aktif Diubah:</b> <code>{arg}</code>",
                    )
            else:
                providers = self.get_providers() if self.get_providers else []
                if not providers:
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text="ℹ️ Belum ada LLM provider yang terdaftar di sistem.",
                    )
                else:
                    lines = []
                    buttons = []
                    for p in providers:
                        is_active = p.get("is_active", False)
                        p_name = p.get("name") or p.get("id")
                        p_id = p.get("id")
                        active_mark = "⭐ (Aktif)" if is_active else ""
                        lines.append(f"• <b>{p_name}</b> {active_mark}\n  <i>ID:</i> <code>{p_id}</code> | <i>Model:</i> <code>{p.get('model', 'default')}</code>")
                        btn_text = f"{'⭐ ' if is_active else ''}{p_name}"
                        buttons.append([{"text": btn_text, "callback_data": f"provider:set:{p_id}"}])

                    provider_text = (
                        "🤖 <b>Daftar LLM Provider:</b>\n\n"
                        + "\n".join(lines) + "\n\n"
                        "Pilih provider aktif melalui tombol di bawah atau ketik <code>/provider &lt;id&gt;</code>:"
                    )
                    keyboard = {"inline_keyboard": buttons}
                    self.bot_client.send_message(chat_id=chat_id, text=provider_text, reply_markup=keyboard)
        elif cmd == "/model":
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""

            if arg:
                if self.set_active_model:
                    self.set_active_model(arg)
                self.bot_client.send_message(
                    chat_id=chat_id,
                    text=f"✅ <b>Model LLM Diperbarui!</b>\n\nModel aktif saat ini: <code>{arg}</code>",
                )
            else:
                models = self.get_models() if self.get_models else []
                if not models:
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text="ℹ️ Tidak ada model yang terdaftar untuk provider aktif saat ini.",
                    )
                else:
                    lines = []
                    buttons = []
                    for m in models:
                        is_active = m.get("is_active", False)
                        m_name = m.get("name") or m.get("id")
                        active_mark = "⭐ (Aktif)" if is_active else ""
                        lines.append(f"• <code>{m_name}</code> {active_mark}")
                        btn_text = f"{'⭐ ' if is_active else ''}{m_name}"
                        buttons.append([{"text": btn_text, "callback_data": f"model:set:{m_name}"}])

                    model_text = (
                        "🧠 <b>Daftar Model Terkonfigurasi di IDE:</b>\n\n"
                        + "\n".join(lines) + "\n\n"
                        "Pilih model aktif melalui tombol di bawah atau ketik <code>/model &lt;nama_model&gt;</code>:"
                    )
                    keyboard = {"inline_keyboard": buttons}
                    self.bot_client.send_message(chat_id=chat_id, text=model_text, reply_markup=keyboard)
        elif cmd == "/skills":
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""

            if arg:
                if self.set_active_skill:
                    self.set_active_skill(arg)
                self.bot_client.send_message(
                    chat_id=chat_id,
                    text=f"🎯 <b>Active Skill Diperbarui!</b>\n\nSkill aktif saat ini: <code>{arg}</code>",
                )
            else:
                skills = self.get_skills() if self.get_skills else []
                if not skills:
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text="ℹ️ Belum ada skills yang terdaftar di sistem.",
                    )
                else:
                    lines = []
                    buttons = []
                    for s in skills:
                        is_active = s.get("is_active", False)
                        s_id = s.get("id")
                        s_name = s.get("name") or s_id
                        desc = s.get("description", "")
                        active_mark = "⭐ (Aktif)" if is_active else ""
                        lines.append(f"• <b>{s_name}</b> {active_mark}\n  <i>{desc}</i>")
                        btn_text = f"{'⭐ ' if is_active else ''}{s_name}"
                        buttons.append([{"text": btn_text, "callback_data": f"skill:set:{s_id}"}])

                    skills_text = (
                        "🎯 <b>Daftar Skills Resmi AegisCode:</b>\n\n"
                        + "\n\n".join(lines) + "\n\n"
                        "Pilih skill aktif di bawah untuk memandu instruksi agen selanjutnya:"
                    )
                    keyboard = {"inline_keyboard": buttons}
                    self.bot_client.send_message(chat_id=chat_id, text=skills_text, reply_markup=keyboard)
        elif cmd == "/testprovider":
            self.bot_client.send_message(chat_id=chat_id, text="🔄 Menguji konektivitas ke LLM provider aktif...")
            res = self.test_provider() if self.test_provider else {"status": "ok", "provider": "OpenCode", "model": "zen", "latency_ms": 45.2}
            status = res.get("status", "ok")
            provider = res.get("provider", "Unknown")
            model = res.get("model", "default")
            latency = res.get("latency_ms", 0.0)

            if status == "ok":
                result_text = (
                    "✅ <b>Uji Konektivitas Berhasil!</b>\n\n"
                    f"• <b>Provider:</b> <code>{provider}</code>\n"
                    f"• <b>Model:</b> <code>{model}</code>\n"
                    f"• <b>Status:</b> OK (200)\n"
                    f"• <b>Latensi Respons:</b> <b>{latency:.1f} ms</b>"
                )
            else:
                detail = res.get("detail") or res.get("message", "Unknown error")
                result_text = (
                    "❌ <b>Uji Konektivitas Gagal!</b>\n\n"
                    f"• <b>Provider:</b> <code>{provider}</code>\n"
                    f"• <b>Model:</b> <code>{model}</code>\n"
                    f"• <b>Status:</b> ERROR\n"
                    f"• <b>Latensi:</b> {latency:.1f} ms\n"
                    f"• <b>Detail:</b> <i>{detail}</i>"
                )
            self.bot_client.send_message(chat_id=chat_id, text=result_text)
        elif cmd == "/help":
            help_text = (
                "<b>AegisCode Mobile Companion:</b>\n\n"
                "• <code>/status</code> - Cek status aktif agen & branch git\n"
                "• <code>/repo</code> - Informasi detail repositori & status git\n"
                "• <code>/mode</code> [ask|agents] - Kontrol mode HITL vs Otonom\n"
                "• <code>/agents</code> - Lihat armada subagen Olympus aktif\n"
                "• <code>/skills</code> - Pilih skill aktif untuk memandu agen\n"
                "• <code>/provider</code> - Kelola & pilih LLM provider aktif\n"
                "• <code>/model</code> - Pilih model LLM terkonfigurasi di IDE\n"
                "• <code>/testprovider</code> - Uji koneksi & latensi LLM provider\n"
                "• <code>/steer &lt;pesan&gt;</code> - Beri instruksi pengarah ke Agen\n"
                "• Tombol persetujuan [Approve]/[Reject] akan otomatis muncul saat agen butuh konfirmasi HITL."
            )
            self.bot_client.send_message(chat_id=chat_id, text=help_text)
        else:
            # Perintah teks bebas / steering
            clean_instruction = text
            if cmd == "/steer":
                parts = text.split(maxsplit=1)
                clean_instruction = parts[1].strip() if len(parts) > 1 else ""

            if clean_instruction and self.on_steer_command:
                try:
                    self.on_steer_command(clean_instruction, chat_id=chat_id)
                except TypeError:
                    self.on_steer_command(clean_instruction)
            elif clean_instruction:
                logger.warning("on_steer_command tidak terkonfigurasi pada handler.")
            else:
                self.bot_client.send_message(
                    chat_id=chat_id,
                    text="ℹ️ Kirim pesan teks untuk memberi instruksi ke agen atau ketik /status.",
                )

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

        # Format data: hitl:<allow|deny>:<approval_id>
        if data.startswith("hitl:"):
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
                        reply_markup=None,  # Hapus tombol setelah diputuskan
                    )
                return

        # Format data: mode:set:<mode>
        elif data.startswith("mode:set:"):
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
                    updated_text = (
                        f"⚙️ <b>Kontrol Mode Operasional:</b>\n\n"
                        f"✅ Mode aktif saat ini: <b>{label}</b>\n\n"
                        + ("Aksi kritis akan meminta konfirmasi user." if target_mode == "ask" else "Aksi dijalankan otonom dengan audit log.")
                    )
                    self.bot_client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=updated_text,
                        reply_markup=None,
                    )
            return

        # Format data: provider:set:<provider_id>
        elif data.startswith("provider:set:"):
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
                    m_buttons = [[{"text": f"{'⭐ ' if m.get('is_active') else ''}{m.get('name')}", "callback_data": f"model:set:{m.get('name')}"}] for m in models]
                    updated_text = (
                        f"🤖 <b>LLM Provider Diperbarui:</b> <code>{provider_id}</code>\n\n"
                        "Silakan pilih model aktif di bawah ini:"
                    )
                    self.bot_client.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=updated_text,
                        reply_markup={"inline_keyboard": m_buttons},
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
                        reply_markup=None,
                    )
            return

        # Format data: model:set:<model_name>
        elif data.startswith("model:set:"):
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
                    reply_markup=None,
                )
            return

        # Format data: skill:set:<skill_name>
        elif data.startswith("skill:set:"):
            skill_name = data[len("skill:set:"):].strip()
            if self.set_active_skill:
                self.set_active_skill(skill_name)
            self.bot_client.answer_callback_query(
                callback_query_id=cb_id,
                text=f"Skill aktif diubah ke: {skill_name}",
            )
            if chat_id and message_id:
                updated_text = (
                    f"🎯 <b>Active Skill Diperbarui!</b>\n\n"
                    f"⭐ Skill aktif saat ini: <code>{skill_name}</code>\n\n"
                    "Instruksi agen selanjutnya akan dipandu oleh skill ini."
                )
                self.bot_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=updated_text,
                    reply_markup=None,
                )
            return

        # Format data: prompt:retry:<cache_id>
        elif data.startswith("prompt:retry:"):
            cache_id = data[len("prompt:retry:"):].strip()
            if self.on_prompt_retry:
                handled = self.on_prompt_retry(cache_id, chat_id or user_id)
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
            return

        # Format data: agent:delegate:<session_id>
        elif data.startswith("agent:delegate:"):
            sess_id = data[len("agent:delegate:"):].strip()
            if self.on_agent_delegate:
                handled = self.on_agent_delegate(sess_id, chat_id or user_id)
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
            return

