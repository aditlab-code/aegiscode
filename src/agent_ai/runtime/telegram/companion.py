from __future__ import annotations

import html
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent_ai.permission.approval import (
    ApprovalCoordinator,
    ApprovalStatus,
)
from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.diff_formatter import (
    GitFileDiffStat,
    format_diff_summary,
)
from agent_ai.runtime.telegram.gate import TelegramContextGate
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.security import TelegramSecurityManager
from agent_ai.runtime.telegram.turn_executors import (
    AgentsModeTurnExecutor,
    AskModeTurnExecutor,
    TaskMonitor,
)

logger = logging.getLogger("agent_ai.runtime.telegram.companion")


def _get_gateway_service():
    """Import GatewayService dengan bootstrap path Django yang aman."""
    import sys
    from pathlib import Path

    p = Path(__file__).resolve()
    django_app_path = None
    for parent in p.parents:
        cand = parent / "apps" / "django_app"
        if cand.is_dir():
            django_app_path = str(cand)
            break
    if django_app_path and django_app_path not in sys.path:
        sys.path.insert(0, django_app_path)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django

        django.setup()
    except Exception as exc:
        logger.error("Gagal memuat GatewayService (django.setup): %s", exc, exc_info=True)
        return None
    try:
        from api.services import get_service

        return get_service()
    except Exception as exc:
        logger.error("Gagal memuat GatewayService (get_service): %s", exc, exc_info=True)
        return None


class TelegramCompanion:
    """Jembatan runtime gateway antara Telegram Bot dan AegisCode HITL Approval."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        bot_client: Optional[TelegramBotClient] = None,
        security_manager: Optional[TelegramSecurityManager] = None,
        pairing_manager: Optional[PairingManager] = None,
        coordinator: Optional[ApprovalCoordinator] = None,
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
        gate: Optional[TelegramContextGate] = None,
    ):
        token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.bot_token = token.strip()
        self.bot_client = bot_client or TelegramBotClient(self.bot_token)
        self.security_manager = security_manager or TelegramSecurityManager()
        self.pairing_manager = pairing_manager or PairingManager()
        self.coordinator = coordinator

        # Function Gate Tunggal
        self.gate = gate or TelegramContextGate(security_manager=self.security_manager)

        self._custom_get_repo_info = get_repo_info
        self._custom_get_mode = get_mode
        self._custom_set_mode = set_mode
        self._custom_get_agents = get_agents
        self._custom_get_providers = get_providers
        self._custom_set_provider = set_provider
        self._custom_test_provider = test_provider
        self._custom_get_models = get_models
        self._custom_set_active_model = set_active_model
        self._custom_get_skills = get_skills
        self._custom_set_active_skill = set_active_skill
        self._custom_get_active_skill = get_active_skill
        self._custom_facade = None
        self._custom_get_changed_files = None
        self._custom_list_projects = None
        self._custom_set_active_project = None

        self.handler = TelegramUpdateHandler(
            bot_client=self.bot_client,
            security_manager=self.security_manager,
            pairing_manager=self.pairing_manager,
            on_hitl_action=self.handle_hitl_action,
            on_steer_command=self.handle_steer_command,
            on_prompt_retry=self.handle_prompt_retry,
            on_agent_delegate=self.handle_agent_delegate,
            get_runtime_status=self.get_runtime_status,
            get_repo_info=self.get_repo_info,
            get_changed_files=self.get_changed_files,
            on_repo_accept=self.accept_repo_changes,
            on_repo_discard=self.discard_repo_changes,
            on_repo_init=self.init_repo,
            list_projects=self.list_projects,
            set_active_project=self.set_active_project,
            get_mode=self.get_mode,
            set_mode=self.set_mode,
            get_agents=self.get_agents,
            get_providers=self.get_providers,
            set_provider=self.set_provider,
            test_provider=self.test_provider,
            get_models=self.get_models,
            set_active_model=self.set_active_model,
            get_skills=self.get_skills,
            set_active_skill=self.set_active_skill,
            get_active_skill=self.get_active_skill,
            gate=self.gate,
        )

    def list_projects(self) -> List[Dict[str, Any]]:
        if getattr(self, "_custom_list_projects", None):
            return self._custom_list_projects()
        svc = _get_gateway_service()
        if svc and hasattr(svc, "project_store"):
            try:
                return svc.project_store.list_projects()
            except Exception as exc:
                logger.warning("Error list_projects: %s", exc)
        return []

    def set_active_project(self, project_id: str) -> bool:
        if getattr(self, "_custom_set_active_project", None):
            return self._custom_set_active_project(project_id)
        svc = _get_gateway_service()
        if svc:
            try:
                if hasattr(svc, "set_active_project"):
                    svc.set_active_project(project_id)
                    return True
                if hasattr(svc, "project_store"):
                    svc.project_store.set_active_project(project_id)
                    return True
            except Exception as exc:
                logger.warning("Error set_active_project: %s", exc)
        return False

    def init_repo(self) -> Dict[str, Any]:
        facade = getattr(self, "_custom_facade", None)
        if not facade:
            svc = _get_gateway_service()
            active = svc.get_active_project() if svc else None
            if not active or not active.get("path"):
                return {"ok": False, "error": "Tidak ada project aktif di Aegis IDE."}
            from agent_ai.git.repository import GitRepositoryFacade
            facade = GitRepositoryFacade(root=Path(active["path"]))
        return facade.init()

    def get_changed_files(self) -> List[Dict[str, Any]]:
        if getattr(self, "_custom_facade", None):
            return self._custom_facade.get_changed_files_summary()
        if getattr(self, "_custom_get_changed_files", None):
            return self._custom_get_changed_files()
        svc = _get_gateway_service()
        active = svc.get_active_project() if svc else None
        if not active or not active.get("path"):
            return []
        from agent_ai.git.repository import GitRepositoryFacade
        facade = GitRepositoryFacade(root=Path(active["path"]))
        if not facade.is_repository():
            return []
        try:
            return facade.get_changed_files_summary()
        except Exception as exc:
            logger.warning("Error get_changed_files_summary: %s", exc)
            return []

    def discard_repo_changes(self) -> Dict[str, Any]:
        facade = getattr(self, "_custom_facade", None)
        if not facade:
            svc = _get_gateway_service()
            active = svc.get_active_project() if svc else None
            if not active or not active.get("path"):
                return {"ok": False, "error": "Tidak ada project aktif di Aegis IDE."}
            from agent_ai.git.repository import GitRepositoryFacade
            facade = GitRepositoryFacade(root=Path(active["path"]))
        if not facade.is_repository():
            return {"ok": False, "error": "Project aktif bukan repositori Git."}
        try:
            res = facade.discard(None)
            ok = res.get("ok", True) if isinstance(res, dict) else bool(res)
            return {"ok": ok, "message": "Semua perubahan berhasil dibatalkan."}
        except Exception as exc:
            logger.error("Error discard_repo_changes: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _generate_commit_message(self, changes: List[Dict[str, Any]]) -> str:
        summary_lines = [f"- {c.get('path')} ({c.get('status')}, {c.get('lines')} line)" for c in changes]
        summary_text = "\n".join(summary_lines)
        prompt = (
            f"Berdasarkan daftar perubahan Git berikut:\n{summary_text}\n\n"
            "Tuliskan TEPAT SATU BARIS conventional commit message yang singkat dan jelas (contoh: 'feat: update repo' atau 'fix: broken imports'). "
            "Keluarkan HANYA pesan commit tanpa tanda kutip atau penjelasan tambahan."
        )
        svc = _get_gateway_service()
        if svc:
            try:
                turn_res = svc.dispatch_remote_turn(content=prompt, mode="ask")
                raw_msg = turn_res.get("response", "").strip()
                clean = raw_msg.splitlines()[0].strip().strip('"`')
                if clean:
                    return clean
            except Exception as exc:
                logger.warning("Gagal men-generate commit message via LLM: %s", exc)
        primary = changes[0]["path"] if changes else "files"
        return f"chore: update {primary} and related files"

    def accept_repo_changes(self) -> Dict[str, Any]:
        facade = getattr(self, "_custom_facade", None)
        if not facade:
            svc = _get_gateway_service()
            active = svc.get_active_project() if svc else None
            if not active or not active.get("path"):
                return {"ok": False, "error": "Tidak ada project aktif di Aegis IDE."}
            from agent_ai.git.repository import GitRepositoryFacade
            facade = GitRepositoryFacade(root=Path(active["path"]))
        if not facade.is_repository():
            return {"ok": False, "error": "Project aktif bukan repositori Git."}

        changes = facade.get_changed_files_summary()
        if not changes:
            return {"ok": False, "error": "Tidak ada perubahan berkas untuk di-commit."}

        msg = self._generate_commit_message(changes)
        try:
            commit_res = facade.commit(message=msg, stage_all=True)
            if commit_res.get("ok"):
                return {
                    "ok": True,
                    "commit": commit_res.get("commit", "HEAD"),
                    "message": msg,
                }
            return {"ok": False, "error": commit_res.get("error", "Gagal commit")}
        except Exception as exc:
            logger.error("Error accept_repo_changes commit: %s", exc)
            return {"ok": False, "error": str(exc)}

    def get_repo_info(self) -> Dict[str, Any]:
        if self._custom_get_repo_info:
            return self._custom_get_repo_info()
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.get_active_repository_info()
            except Exception as exc:
                logger.warning("Error get_active_repository_info: %s", exc)
        return {
            "name": "AegisCode",
            "root": "-",
            "branch": "main",
            "last_commit": "-",
            "uncommitted_changes": 0,
            "is_dirty": False,
            "is_repo": True,
        }

    def get_mode(self) -> str:
        if self._custom_get_mode:
            return self._custom_get_mode()
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.get_operational_mode()
            except Exception as exc:
                logger.warning("Error get_operational_mode: %s", exc)
        return "ask"

    def set_mode(self, mode: str) -> str:
        if self._custom_set_mode:
            return self._custom_set_mode(mode)
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.set_operational_mode(mode)
            except Exception as exc:
                logger.warning("Error set_operational_mode: %s", exc)
        return mode

    def get_agents(self) -> List[Dict[str, Any]]:
        if self._custom_get_agents:
            return self._custom_get_agents()
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.get_subagents_fleet()
            except Exception as exc:
                logger.warning("Error get_subagents_fleet: %s", exc)
        return []

    def get_providers(self) -> List[Dict[str, Any]]:
        if self._custom_get_providers:
            return self._custom_get_providers()
        svc = _get_gateway_service()
        if svc:
            try:
                res = svc.get_providers_status()
                if res:
                    return res
            except Exception as exc:
                logger.warning("Error get_providers_status: %s", exc)
        return [
            {
                "id": "c34bd3e5098e4cf08a716d0a8a44c714",
                "name": "Google Antigravity",
                "provider_type": "antigravity",
                "model": "gemini-3.1-pro-high",
                "is_active": True,
            },
            {
                "id": "openai-default",
                "name": "OpenAI",
                "provider_type": "openai",
                "model": "gpt-4o",
                "is_active": False,
            },
            {
                "id": "anthropic-default",
                "name": "Anthropic",
                "provider_type": "anthropic",
                "model": "claude-3-5-sonnet",
                "is_active": False,
            },
            {
                "id": "ollama-default",
                "name": "Ollama Local",
                "provider_type": "ollama",
                "model": "llama3.2",
                "is_active": False,
            },
        ]

    def set_provider(self, provider_id: str) -> None:
        if self._custom_set_provider:
            self._custom_set_provider(provider_id)
            return
        svc = _get_gateway_service()
        if svc:
            try:
                svc.set_active_provider(provider_id)
            except Exception as exc:
                logger.warning("Error set_active_provider: %s", exc)

    def test_provider(self) -> Dict[str, Any]:
        if self._custom_test_provider:
            return self._custom_test_provider()
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.test_active_provider()
            except Exception as e:
                return {"status": "error", "message": str(e), "latency_ms": 0.0}
        return {"status": "error", "message": "Service unavailable", "latency_ms": 0.0}

    def get_models(self, provider_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self._custom_get_models:
            return self._custom_get_models(provider_id)
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.get_models_for_provider(provider_id)
            except Exception as e:
                logger.error("Error get_models_for_provider: %s", str(e))
        return [
            {"id": "claude-sonnet-4-6", "name": "claude-sonnet-4-6", "is_active": True},
            {"id": "claude-opus-4-6", "name": "claude-opus-4-6", "is_active": False},
            {"id": "gemini-3.8-flash-medium", "name": "gemini-3.8-flash-medium", "is_active": False},
            {"id": "gemini-3.1-pro-high", "name": "gemini-3.1-pro-high", "is_active": False},
        ]

    def set_active_model(self, model_name: str) -> None:
        if self._custom_set_active_model:
            self._custom_set_active_model(model_name)
            return
        svc = _get_gateway_service()
        if svc:
            try:
                svc.set_active_model(model_name)
            except Exception as e:
                logger.error("Error set_active_model: %s", str(e))

    def get_skills(self) -> List[Dict[str, Any]]:
        if self._custom_get_skills:
            return self._custom_get_skills()
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.get_available_skills()
            except Exception as e:
                logger.error("Error get_available_skills: %s", str(e))
        return [
            {"id": "spec-driven-development", "name": "Spec-Driven Dev", "description": "Tulis spesifikasi sebelum coding", "is_active": False},
            {"id": "planning-and-task-breakdown", "name": "Plan & Breakdown", "description": "Pecah tugas ke unit terukur", "is_active": False},
            {"id": "incremental-implementation", "name": "Incremental Build", "description": "Eksekusi slice per slice", "is_active": False},
            {"id": "test-driven-development", "name": "Test-Driven Dev", "description": "Kembangkan logika dengan TDD", "is_active": False},
            {"id": "code-review-and-quality", "name": "Code Review", "description": "Evaluasi kualitas multi-dimensi", "is_active": False},
            {"id": "code-simplification", "name": "Code Simplifier", "description": "Sederhanakan kode tanpa ubah perilaku", "is_active": False},
            {"id": "interview-me", "name": "Interview Me", "description": "Ekstraksi kebutuhan mendalam", "is_active": False},
            {"id": "shipping-and-launch", "name": "Ship & Launch", "description": "Persiapan rilis dan verifikasi akhir", "is_active": False},
        ]

    def set_active_skill(self, skill_name: str) -> None:
        if self._custom_set_active_skill:
            self._custom_set_active_skill(skill_name)
            return
        svc = _get_gateway_service()
        if svc:
            try:
                svc.set_active_skill(skill_name)
            except Exception as e:
                logger.error("Error set_active_skill: %s", str(e))

    def get_active_skill(self) -> Optional[str]:
        if self._custom_get_active_skill:
            return self._custom_get_active_skill()
        svc = _get_gateway_service()
        if svc:
            try:
                return svc.get_active_skill()
            except Exception as exc:
                logger.warning("Error get_active_skill: %s", exc)
        return None

    def attach_coordinator(self, coordinator: ApprovalCoordinator) -> None:
        """Hubungkan ApprovalCoordinator ke companion."""
        self.coordinator = coordinator

    def send_audit_log(self, tool_name: str, target: str = "", reason: str = "") -> bool:
        """Kirim real-time audit log ke pengguna terdaftar saat di mode agents."""
        recipient_id = self.gate.resolve_chat_id()
        if recipient_id is None:
            logger.warning("Tidak ada user Telegram terdaftar untuk menerima audit log.")
            return False

        target_display = target if target else "workspace"
        reason_display = f"\n<i>Alasan:</i> {reason}" if reason else ""
        text = (
            f"⚡ <b>[AUDIT LOG]</b> Subagent auto-executed tool '<b>{tool_name}</b>' on '<code>{target_display}</code>'"
            f"{reason_display}"
        )
        try:
            self.bot_client.send_message(chat_id=recipient_id, text=text)
            return True
        except Exception as exc:
            logger.error("Gagal mengirim audit log Telegram: %s", exc)
            return False

    def on_approval_event(self, session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        """Sink listener untuk event approval dari ApprovalCoordinator."""
        if event_type == "auto_approval_audit":
            tool_name = payload.get("tool") or payload.get("action_name", "Unknown Action")
            target_path = payload.get("target") or payload.get("target_path", "")
            description = payload.get("reason") or payload.get("description", "")
            self.send_audit_log(tool_name, target_path, description)
            return

        if event_type != "approval_requested":
            return

        # Jika operational mode saat ini adalah 'agents', auto-allow dan kirim audit log
        current_mode = self.get_mode().lower()
        if current_mode == "agents":
            approval_id = payload.get("request_id") or payload.get("approval_id", "")
            action_name = payload.get("tool") or payload.get("action_name", "Unknown Action")
            description = payload.get("reason") or payload.get("description", "")
            target_path = payload.get("target") or payload.get("target_path", "")
            if self.coordinator and approval_id:
                self.coordinator.resolve(approval_id, allow=True)
            self.send_audit_log(action_name, target_path, description)
            return

        recipient_id = self.gate.resolve_chat_id()
        if recipient_id is None:
            logger.warning("Tidak ada user Telegram terdaftar untuk menerima permintaan approval.")
            return

        approval_id = payload.get("request_id") or payload.get("approval_id", "")
        action_name = payload.get("tool") or payload.get("action_name", "Unknown Action")
        description = payload.get("reason") or payload.get("description", "")
        target_path = payload.get("target") or payload.get("target_path", "")

        files: list[GitFileDiffStat] = []
        if target_path:
            files.append(GitFileDiffStat(path=target_path, insertions=1, deletions=0))

        summary_text = format_diff_summary(
            action_name=action_name,
            description=description,
            files=files,
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Setujui (Allow)", "callback_data": f"hitl:allow:{approval_id}"},
                    {"text": "❌ Tolak (Deny)", "callback_data": f"hitl:deny:{approval_id}"},
                ]
            ]
        }

        self.bot_client.send_message(
            chat_id=recipient_id,
            text=summary_text,
            reply_markup=reply_markup,
        )

    def handle_hitl_action(self, action: str, approval_id: str) -> None:
        """Selesaikan status approval di ApprovalCoordinator berdasarkan keputusan user."""
        if self.coordinator is None:
            logger.error("ApprovalCoordinator belum dihubungkan ke TelegramCompanion.")
            return

        is_allowed = action.lower() == "allow"
        self.coordinator.resolve(approval_id, allow=is_allowed)

    def handle_steer_command(self, instruction: str, chat_id: Optional[int] = None) -> None:
        """Teruskan arahan teks dari user ke sesi agen aktif dan jalankan turn secara asinkron."""
        logger.info("Steering instruction received from Telegram: %s", instruction)
        recipient_id = self.gate.resolve_chat_id(explicit_chat_id=chat_id)
        if recipient_id:
            self.execute_remote_turn_async(instruction, recipient_id)

    def handle_prompt_retry(self, cache_id: str, chat_id: int) -> bool:
        """Picu eksekusi ulang turn dari cache untuk kegagalan sebelumnya."""
        entry = self.gate.pop_retry_prompt(cache_id)
        if not entry:
            return False

        instruction = entry.get("instruction", "")
        target_chat_id = entry.get("chat_id") or chat_id
        if not instruction:
            return False

        self.execute_remote_turn_async(instruction, target_chat_id)
        return True

    def handle_agent_delegate(self, session_id: str, chat_id: int) -> bool:
        """Picu delegasi sesi asinkron ke Task Runner di IDE menggunakan TaskMonitor."""
        from agent_ai.runtime.telegram.stream_relay import TelegramStreamRelay

        turn_id = f"DELEGATE-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        relay = TelegramStreamRelay(
            bot_client=self.bot_client,
            chat_id=chat_id,
            initial_status="🚀 <i>Mendelegasikan tugas ke Agen IDE...</i>",
        )

        def _worker():
            logger.info(
                "[DELEGATE-THREAD] [START] Delegation %s started for session_id=%s chat_id=%s",
                turn_id,
                session_id,
                chat_id,
            )
            svc = _get_gateway_service()
            if not svc:
                relay.error("Layanan Gateway Aegis tidak tersedia.")
                return

            try:
                relay.set_status("⚡", "Membuat Task otonom di IDE...")
                res = svc.delegate_session_to_agent_task(session_id=session_id)
                task_info = (res or {}).get("task") or {}
                task_id = task_info.get("task_id")

                if not task_id:
                    err_msg = "Gagal mendelegasikan tugas ke IDE: task ID tidak ditemukan dalam respons backend."
                    logger.error("[DELEGATE-THREAD] %s: keys=%s", err_msg, list((res or {}).keys()))
                    relay.error(err_msg)
                    return

                self.gate.register_task(chat_id, task_id, session_id=session_id)
                try:
                    final_status, report_text = TaskMonitor.poll_task_until_done(
                        svc=svc,
                        task_id=task_id,
                        relay=relay,
                    )
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.info(
                        "[DELEGATE-THREAD] [FINISH] Delegation %s completed in %d ms (task=%s, status=%s)",
                        turn_id,
                        duration_ms,
                        task_id,
                        final_status,
                    )
                    relay.finalize(report_text, success=(final_status == "completed"))
                finally:
                    self.gate.complete_task(chat_id, task_id)
            except Exception as ex:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    "[DELEGATE-THREAD] [ERROR] Delegation %s failed in %d ms: %s",
                    turn_id,
                    duration_ms,
                    ex,
                    exc_info=True,
                )
                relay.error(f"Gagal mendelegasikan tugas: {ex}")

        t = threading.Thread(target=_worker, name=f"DelegateThread-{turn_id}", daemon=True)
        t.start()
        return True

    def execute_remote_turn_async(self, instruction: str, chat_id: int) -> None:
        """Jalankan turn pada sesi terpadu secara asinkron dengan kontrol Gate id_task ketat."""
        turn_id = f"TURN-{uuid.uuid4().hex[:8]}"
        mode = self.get_mode().lower()

        # Daftarkan id_task aktif ke Gate sebelum memicu thread
        self.gate.register_task(chat_id, turn_id)

        def _worker():
            try:
                svc = _get_gateway_service()
                if not svc:
                    logger.error("[TURN-THREAD] Turn %s failed: GatewayService unavailable", turn_id)
                    self.bot_client.send_message(
                        chat_id=chat_id,
                        text="❌ <b>Layanan Gateway Aegis tidak tersedia.</b>",
                    )
                    return

                if mode == "ask":
                    ask_executor = AskModeTurnExecutor(
                        bot_client=self.bot_client,
                        gate=self.gate,
                        get_active_skill=self.get_active_skill,
                    )
                    ask_executor.execute(instruction, chat_id, svc)
                else:
                    agents_executor = AgentsModeTurnExecutor(
                        bot_client=self.bot_client,
                        gate=self.gate,
                    )
                    agents_executor.execute(instruction, chat_id, svc)
            except Exception as ex:
                logger.error("[TURN-THREAD] Turn %s unhandled exception: %s", turn_id, ex, exc_info=True)
                self.bot_client.send_message(
                    chat_id=chat_id,
                    text=f"❌ <b>Terjadi kesalahan saat mengeksekusi instruksi:</b> {html.escape(str(ex))}",
                )
            finally:
                self.gate.complete_task(chat_id, turn_id)

        t = threading.Thread(target=_worker, name=f"TurnThread-{turn_id}", daemon=True)
        t.start()

    def get_runtime_status(self) -> str:
        """Format ringkasan status AegisCode untuk respon /status."""
        paired_user = self.security_manager.load_paired_user()
        if paired_user and paired_user.username:
            user_label = f"@{paired_user.username}"
        elif self.security_manager.env_allowed_usernames:
            user_label = f"@{list(self.security_manager.env_allowed_usernames)[0]}"
        elif paired_user and paired_user.user_id:
            user_label = f"ID: {paired_user.user_id}"
        else:
            user_label = "None"

        mode = self.get_mode().lower()
        mode_label = "Agents ⚡ (Otonom)" if mode == "agents" else "Aktif (Ask Mode)"

        repo_info = self.get_repo_info()
        repo_name = repo_info.get("name", "AegisCode")
        branch = repo_info.get("branch", "main")
        dirty = " ⚠️ dirty" if repo_info.get("is_dirty") else ""

        return (
            "🟢 <b>AegisCode Gateway Online</b>\n\n"
            f"• <b>Repo:</b> <code>{repo_name}</code> (branch: <code>{branch}</code>{dirty})\n"
            "• <b>Status Agen:</b> Siap Menerima Tugas (Idle)\n"
            f"• <b>Mode HITL:</b> {mode_label}\n"
            f"• <b>User Terhubung:</b> {user_label}\n"
            "• <b>Koneksi:</b> Long-Polling Outbound OK\n\n"
            "Kirim pesan teks apa saja untuk memberikan instruksi pengarah (*steering*) ke Agen."
        )

    def start(self) -> bool:
        """Mulai long-polling companion jika bot token tersedia."""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN belum disetel.")
            return False
        return bool(self.bot_client.start_polling(self.handler.handle_update))

    def stop(self) -> None:
        """Hentikan background companion."""
        self.bot_client.stop_polling()


if __name__ == "__main__":
    import time
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("  AegisCode Remote Companion Gateway (Telegram Poller)")
    print("=" * 60)

    companion = TelegramCompanion()
    bot_info = companion.bot_client.get_me()
    if not bot_info:
        print("[ERROR] Gagal menghubungi Telegram Bot API. Periksa TELEGRAM_BOT_TOKEN di .env.")
        exit(1)

    print(f"[OK] Terhubung ke Bot Telegram: @{bot_info.get('username')}")
    sec_mgr = companion.security_manager
    status = sec_mgr.get_status()
    allowed_display = list(sec_mgr.env_allowed_usernames) + [str(i) for i in sec_mgr.env_allowed_ids]
    print(f"[AUTH] Whitelist Allowed: {', '.join(allowed_display) if allowed_display else 'None (Scan QR)'}")

    if companion.start():
        print("[GATEWAY] Long-polling aktif! Menunggu interaksi dari Telegram...")
        print("Silakan chat ke bot Anda di Telegram. Tekan Ctrl+C untuk menghentikan.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[STOP] Menghentikan gateway...")
            companion.stop()
