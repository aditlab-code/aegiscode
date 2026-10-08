from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from pathlib import Path

from agent_ai.permission.approval import (
    ApprovalCoordinator,
    ApprovalStatus,
)
from agent_ai.runtime.telegram.companion import TelegramCompanion
from agent_ai.runtime.telegram.security import TelegramSecurityManager
from agent_ai.runtime.telegram.pairing import PairingManager


def test_companion_hitl_full_cycle(tmp_path: Path):
    bot_client = MagicMock()
    sec_manager = TelegramSecurityManager(storage_path=tmp_path / "paired.json", env_whitelist="")
    sec_manager.save_paired_user(user_id=12345, username="adit")
    pairing_mgr = PairingManager()

    # Siapkan companion
    companion = TelegramCompanion(
        bot_token="fake_token_123",
        bot_client=bot_client,
        security_manager=sec_manager,
        pairing_manager=pairing_mgr,
    )

    # Hubungkan ApprovalCoordinator ke sink milik companion
    coordinator = ApprovalCoordinator(sink=companion.on_approval_event, timeout=5.0)
    companion.attach_coordinator(coordinator)

    # 1. Agen memicu request approval (seperti ToolExecutor di ASK mode)
    req = coordinator.request(
        tool="write_to_file",
        reason="Modify database config",
        target="config/db.py",
        session_id="sess_1",
    )

    # Verifikasi bahwa Telegram bot mengirim pesan ke user yang terdaftar
    bot_client.send_message.assert_called_once()
    args, kwargs = bot_client.send_message.call_args
    assert kwargs["chat_id"] == 12345
    assert "Approval Diperlukan: write_to_file" in kwargs["text"]
    assert "config/db.py" in kwargs["text"]
    assert "reply_markup" in kwargs
    inline_kb = kwargs["reply_markup"]["inline_keyboard"]
    assert inline_kb[0][0]["callback_data"] == f"hitl:allow:{req.request_id}"
    assert inline_kb[0][1]["callback_data"] == f"hitl:deny:{req.request_id}"

    # 2. Simulasikan user menekan tombol [Allow] di Telegram
    companion.handle_hitl_action(action="allow", approval_id=req.request_id)

    # 3. Coordinator wait() harus mengembalikan ApprovalStatus.ALLOWED
    res = coordinator.wait(req.request_id)
    assert res == ApprovalStatus.ALLOWED
    assert coordinator.status(req.request_id) == ApprovalStatus.ALLOWED


def test_companion_hitl_deny_cycle(tmp_path: Path):
    bot_client = MagicMock()
    sec_manager = TelegramSecurityManager(storage_path=tmp_path / "paired.json", env_whitelist="")
    sec_manager.save_paired_user(user_id=12345)
    pairing_mgr = PairingManager()

    companion = TelegramCompanion(
        bot_token="fake_token_123",
        bot_client=bot_client,
        security_manager=sec_manager,
        pairing_manager=pairing_mgr,
    )

    coordinator = ApprovalCoordinator(sink=companion.on_approval_event, timeout=5.0)
    companion.attach_coordinator(coordinator)

    req = coordinator.request(
        tool="rm_file",
        reason="Delete file",
        target="secret.txt",
    )

    # Simulasikan user menolak
    companion.handle_hitl_action(action="deny", approval_id=req.request_id)

    res = coordinator.wait(req.request_id)
    assert res == ApprovalStatus.DENIED
    assert coordinator.status(req.request_id) == ApprovalStatus.DENIED


def test_companion_agents_mode_auto_allows_and_sends_audit_log(tmp_path: Path):
    bot_client = MagicMock()
    sec_manager = TelegramSecurityManager(storage_path=tmp_path / "paired.json", env_whitelist="")
    sec_manager.save_paired_user(user_id=12345, username="adit")
    pairing_mgr = PairingManager()

    companion = TelegramCompanion(
        bot_token="fake_token_123",
        bot_client=bot_client,
        security_manager=sec_manager,
        pairing_manager=pairing_mgr,
        get_mode=lambda: "agents",
    )

    coordinator = ApprovalCoordinator(sink=companion.on_approval_event, timeout=5.0)
    companion.attach_coordinator(coordinator)

    # Agen memicu approval saat di mode agents
    req = coordinator.request(
        tool="edit_file",
        reason="Automated refactor",
        target="src/main.py",
        session_id="sess_agents_1",
    )

    # Status harus langsung ALLOWED tanpa perlu wait()
    assert coordinator.status(req.request_id) == ApprovalStatus.ALLOWED

    # Verifikasi audit log terkirim ke Telegram Companion
    bot_client.send_message.assert_called_once()
    _, kwargs = bot_client.send_message.call_args
    assert kwargs["chat_id"] == 12345
    assert "[AUDIT LOG]" in kwargs["text"]
    assert "edit_file" in kwargs["text"]
    assert "src/main.py" in kwargs["text"]
    assert "Automated refactor" in kwargs["text"]


def test_make_approval_gate_agents_mode_non_blocking_with_audit_sink():
    from agent_ai.permission.approval import make_approval_gate

    coordinator = ApprovalCoordinator()
    audit_sink = MagicMock()

    gate = make_approval_gate(
        coordinator,
        task_id="task_001",
        session_id="sess_001",
        mode_getter=lambda: "agents",
        audit_sink=audit_sink,
    )

    allowed = gate({
        "tool": "run_shell",
        "target": "npm test",
        "reason": "Run test suite",
    })

    assert allowed is True
    audit_sink.assert_called_once()
    payload = audit_sink.call_args[0][0]
    assert payload["tool"] == "run_shell"
    assert payload["target"] == "npm test"
    assert payload["auto_approved"] is True


def test_make_approval_gate_ask_mode_blocking():
    import threading
    import time
    from agent_ai.permission.approval import make_approval_gate

    coordinator = ApprovalCoordinator(timeout=2.0)
    gate = make_approval_gate(
        coordinator,
        task_id="task_ask_1",
        session_id="sess_ask_1",
        mode_getter=lambda: "ask",
    )

    result_container = []

    def run_gate():
        res = gate({"tool": "write_file", "target": "foo.py", "reason": "write"})
        result_container.append(res)

    t = threading.Thread(target=run_gate)
    t.start()

    time.sleep(0.1)
    # Harus ada pending approval
    pending = coordinator.pending("task_ask_1")
    assert len(pending) == 1
    req_id = pending[0].request_id

    # Resolve allow
    coordinator.resolve(req_id, allow=True)
    t.join(timeout=1.0)

    assert result_container == [True]


def test_send_audit_log_without_paired_user_returns_false(tmp_path: Path):
    bot_client = MagicMock()
    sec_manager = TelegramSecurityManager(storage_path=tmp_path / "paired.json", env_whitelist="")
    companion = TelegramCompanion(
        bot_token="token",
        bot_client=bot_client,
        security_manager=sec_manager,
    )

    res = companion.send_audit_log("write_file", "secret.txt", "testing")
    assert res is False
    bot_client.send_message.assert_not_called()


def test_send_audit_log_handles_bot_exception_gracefully(tmp_path: Path):
    bot_client = MagicMock()
    bot_client.send_message.side_effect = RuntimeError("Telegram connection failed")
    sec_manager = TelegramSecurityManager(storage_path=tmp_path / "paired.json", env_whitelist="")
    sec_manager.save_paired_user(user_id=999)

    companion = TelegramCompanion(
        bot_token="token",
        bot_client=bot_client,
        security_manager=sec_manager,
    )

    res = companion.send_audit_log("bash", "rm", "delete")
    assert res is False


def test_gateway_service_operational_mode_and_approval_gate(tmp_path: Path):
    from api.project_store import ProjectStore
    from api.services import GatewayService

    store = ProjectStore(tmp_path / "aegis.db")
    service = GatewayService(project_store=store)

    # Operational mode
    assert service.get_operational_mode() == "ask"
    service.set_operational_mode("agents")
    assert service.get_operational_mode() == "agents"

    # Active provider
    assert service.get_active_provider() is None
    service.set_active_provider("anthropic_claude")
    assert service.get_active_provider() == "anthropic_claude"

    # Active repository info
    repo_info = service.get_active_repository_info()
    assert "name" in repo_info
    assert "root" in repo_info
    assert "branch" in repo_info
    assert "uncommitted_changes" in repo_info

    # Subagents fleet
    fleet = service.get_subagents_fleet()
    assert len(fleet) == 6
    persona_ids = [a["persona_id"] for a in fleet]
    assert "zeus-orchestrator" in persona_ids
    assert "athena-planner" in persona_ids
    assert "hephaestus-coder" in persona_ids
    assert "heracles-tester" in persona_ids
    assert "hermes-scout" in persona_ids
    assert "themis-reviewer" in persona_ids

    # Approval gate in agents mode auto-allows
    gate = service.approval_gate_for(task_id="t_gate_1", session_id="s_gate_1")
    allowed = gate({"tool": "write", "target": "demo.py", "reason": "auto"})
    assert allowed is True
