from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from agent_ai.permission.approval import ApprovalCoordinator
from agent_ai.runtime.telegram.bot_client import TelegramBotClient
from agent_ai.runtime.telegram.companion import TelegramCompanion
from agent_ai.runtime.telegram.diff_formatter import (
    GitFileDiffStat,
    format_diff_summary,
)
from agent_ai.runtime.telegram.gate import GateDecision, TelegramContextGate
from agent_ai.runtime.telegram.handler import TelegramUpdateHandler
from agent_ai.runtime.telegram.pairing import PairingManager
from agent_ai.runtime.telegram.security import TelegramSecurityManager
from agent_ai.runtime.telegram.stream_relay import (
    TelegramStreamRelay,
    sanitize_telegram_html,
)
from agent_ai.runtime.telegram.turn_executors import (
    AgentsModeTurnExecutor,
    AskModeTurnExecutor,
    TaskMonitor,
    should_offer_delegation,
)
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


# =============================================================================
# 1. SECURITY & PAIRING GATE
# =============================================================================


def test_pairing_and_authorization_gate():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_file = Path(tmpdir) / "paired.json"
        sec = TelegramSecurityManager(storage_path=storage_file, env_whitelist="100,200")
        pairing = PairingManager()
        # Generate pairing token
        session = pairing.create_session("aegis_test_bot")
        token = session.token
        assert len(token) == 8
        # Unauthorized user
        assert not sec.is_authorized(user_id=999)
        assert sec.is_authorized(user_id=100)

        # Validate token and save user
        assert pairing.validate_token(token)
        paired_user = sec.save_paired_user(user_id=999, username="john_doe", first_name="John")
        assert paired_user.user_id == 999
        assert sec.is_authorized(user_id=999)

        # Token cannot be reused (one-time OTP)
        assert not pairing.validate_token(token)

        # Unlink user
        assert sec.unlink()
        assert not sec.is_authorized(user_id=999)


# =============================================================================
# 2. TELEGRAM CONTEXT GATE
# =============================================================================


def test_context_gate_chat_and_task_tracking():
    with tempfile.TemporaryDirectory() as tmpdir:
        sec = TelegramSecurityManager(
            storage_path=Path(tmpdir) / "paired.json",
            env_whitelist="500",
        )
        gate = TelegramContextGate(security_manager=sec)

        # Chat ID resolution: explicit vs paired vs env
        assert gate.resolve_chat_id(explicit_chat_id=777) == 777
        assert gate.resolve_chat_id() == 500

        sec.save_paired_user(user_id=888, username="alice")
        assert gate.resolve_chat_id() == 888

        # Inbound turn authorization check
        unauth_dec = gate.gate_inbound_turn(chat_id=999, content="hello")
        assert not unauth_dec.allowed
        assert unauth_dec.reason == "Unauthorized user"

        auth_dec = gate.gate_inbound_turn(chat_id=888, content="hello")
        assert auth_dec.allowed

        # Active task registration and gating
        gate.register_task(chat_id=888, task_id="task-xyz", session_id="sess-xyz")
        active = gate.get_active_task(888)
        assert active is not None
        assert active["task_id"] == "task-xyz"
        assert active["session_id"] == "sess-xyz"

        # Gated turn while task is active
        busy_dec = gate.gate_inbound_turn(chat_id=888, content="another turn")
        assert not busy_dec.allowed
        assert busy_dec.active_task_id == "task-xyz"

        # Complete task and verify release
        gate.complete_task(chat_id=888, task_id="task-xyz")
        assert gate.get_active_task(888) is None
        assert gate.gate_inbound_turn(chat_id=888, content="now free").allowed

        # Retry prompt cache with TTL
        gate.save_retry_prompt("retry-key-1", "instruction 1", 888, error="LLM Timeout")
        cached = gate.pop_retry_prompt("retry-key-1")
        assert cached is not None
        assert cached["instruction"] == "instruction 1"
        assert cached["error"] == "LLM Timeout"

        # Popped entry is removed
        assert gate.pop_retry_prompt("retry-key-1") is None


# =============================================================================
# 3. COMMAND DISPATCHER
# =============================================================================


def test_command_dispatcher_repo():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        get_repo_info=lambda: {
            "name": "AegisCode-Core",
            "root": "/workspace/aegis",
            "branch": "feat/tele-restructure",
            "last_commit": "abcdef1",
            "uncommitted_changes": 3,
            "is_dirty": True,
        },
    )

    update = {"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/repo"}}
    handler.handle_update(update)

    assert bot.send_message.called
    text = bot.send_message.call_args[1]["text"]
    assert "AegisCode-Core" in text
    assert "feat/tele-restructure" in text
    assert "3 perubahan belum di-commit" in text


def test_command_dispatcher_aegis_mode():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()
    current_mode = ["ask"]

    def _set_mode(m):
        current_mode[0] = m
        return m

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        get_mode=lambda: current_mode[0],
        set_mode=_set_mode,
    )

    # 1. Bare /aegis_mode shows interactive menu
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/aegis_mode"}})
    text1 = bot.send_message.call_args[1]["text"]
    markup1 = bot.send_message.call_args[1]["reply_markup"]
    assert "Kontrol Mode Operasional" in text1
    assert markup1["inline_keyboard"][0][0]["callback_data"] == "mode:set:ask"

    # 2. Argument /aegis_mode agents updates mode directly
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/aegis_mode agents"}})
    assert current_mode[0] == "agents"
    text2 = bot.send_message.call_args[1]["text"]
    assert "Agents ⚡" in text2

    # 3. Invalid argument
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/aegis_mode invalid"}})
    text3 = bot.send_message.call_args[1]["text"]
    assert "Mode Tidak Valid" in text3


def test_command_dispatcher_config_llm():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()
    set_provider_spy = MagicMock()
    set_model_spy = MagicMock()
    test_provider_spy = MagicMock(return_value={"status": "ok", "provider": "Google Antigravity", "latency_ms": 35.5})

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        get_providers=lambda: [
            {"id": "antigravity", "name": "Google Antigravity", "is_active": True},
            {"id": "opencode", "name": "OpenCode Zen", "is_active": False},
        ],
        set_provider=set_provider_spy,
        get_models=lambda pid=None: [
            {"id": "gemini-3.1-pro-high", "name": "gemini-3.1-pro-high", "is_active": True},
            {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash", "is_active": False},
        ],
        set_active_model=set_model_spy,
        test_provider=test_provider_spy,
    )

    # 1. Bare /config_llm
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config_llm"}})
    assert bot.send_message.called
    text = bot.send_message.call_args[1]["text"]
    markup = bot.send_message.call_args[1]["reply_markup"]
    assert "Google Antigravity" in text
    assert "gemini-3.1-pro-high" in text
    assert markup["inline_keyboard"][0][0]["callback_data"] == "config:providers"
    assert markup["inline_keyboard"][0][1]["callback_data"] == "config:models"
    assert markup["inline_keyboard"][1][0]["callback_data"] == "config:ping"

    # 2. Aliases /config and /llm
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config"}})
    assert bot.send_message.called
    assert "Google Antigravity" in bot.send_message.call_args[1]["text"]

    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/llm"}})
    assert bot.send_message.called
    assert "Google Antigravity" in bot.send_message.call_args[1]["text"]

    # 3. /config_llm providers (list)
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config_llm providers"}})
    assert bot.send_message.called
    text_p = bot.send_message.call_args[1]["text"]
    assert "Daftar LLM Provider" in text_p
    assert "Google Antigravity" in text_p
    assert "OpenCode Zen" in text_p

    # 4. /config_llm provider <id> (switch)
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config_llm provider opencode"}})
    set_provider_spy.assert_called_with("opencode")
    assert bot.send_message.called
    text_set_p = bot.send_message.call_args[1]["text"]
    assert "Provider LLM Diperbarui" in text_set_p
    assert "opencode" in text_set_p

    # 5. /config_llm models (list)
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config_llm models"}})
    assert bot.send_message.called
    text_m = bot.send_message.call_args[1]["text"]
    assert "Daftar Model" in text_m
    assert "gemini-3.1-pro-high" in text_m

    # 6. /config_llm model <id> (switch)
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config_llm model gemini-2.5-flash"}})
    set_model_spy.assert_called_with("gemini-2.5-flash")
    assert bot.send_message.called
    text_set_m = bot.send_message.call_args[1]["text"]
    assert "Model LLM Diperbarui" in text_set_m
    assert "gemini-2.5-flash" in text_set_m

    # 7. /config_llm ping (test connection)
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/config_llm ping"}})
    test_provider_spy.assert_called()
    assert bot.send_message.called
    text_ping = bot.send_message.call_args[1]["text"]
    assert "35.5" in text_ping or "ms" in text_ping



def test_command_dispatcher_aegis_chat_and_skill_template():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()
    steer_spy = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        on_steer_command=steer_spy,
        get_active_skill=lambda: "spec-driven-development",
    )

    # 1. Bare /aegis_chat displays guide templates
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/aegis_chat"}})
    text1 = bot.send_message.call_args[1]["text"]
    markup1 = bot.send_message.call_args[1]["reply_markup"]
    assert "Template Skills Pemandu" in text1
    assert any("skill:set:spec-driven-development" in btn["callback_data"] for row in markup1["inline_keyboard"] for btn in row)

    # 2. /aegis_chat with prompt routes to steer turn
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/aegis_chat Analisis performa database"}})
    steer_spy.assert_called_with("Analisis performa database", chat_id=123)

    # 3. Free text message without '/' routes directly to steer turn
    steer_spy.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "Buatkan test unit"}})
    steer_spy.assert_called_with("Buatkan test unit", chat_id=123)


def test_command_dispatcher_rejects_legacy_commands():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
    )

    for legacy in ["/provider", "/mode", "/steer", "/skills", "/model", "/testprovider"]:
        bot.reset_mock()
        handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": f"{legacy} arg"}})
        assert bot.send_message.called
        text = bot.send_message.call_args[1]["text"]
        assert "Telah Diperbarui" in text
        assert "/repo" in text
        assert "/aegis_mode" in text
        assert "/aegis_chat" in text
        assert "/config_llm" in text


def test_command_dispatcher_status_and_agents():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        get_runtime_status=lambda: "🟢 Gateway Operational",
        get_agents=lambda: [{"name": "Zeus Orchestrator", "role": "Ship Master", "status": "Active"}],
    )

    # /status
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/status"}})
    assert bot.send_message.call_args[1]["text"] == "🟢 Gateway Operational"

    # /agents
    bot.reset_mock()
    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/agents"}})
    text = bot.send_message.call_args[1]["text"]
    assert "Zeus Orchestrator" in text
    assert "Ship Master" in text


def test_command_dispatcher_help_includes_config_llm():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
    )

    handler.handle_update({"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "/help"}})
    assert bot.send_message.called
    text = bot.send_message.call_args[1]["text"]
    assert "/config_llm" in text


# =============================================================================
# 4. CALLBACK DISPATCHER
# =============================================================================


def test_callback_query_dispatcher():
    bot = MagicMock()
    sec = MagicMock(is_authorized=MagicMock(return_value=True))
    pairing = MagicMock()
    hitl_action_spy = MagicMock()
    set_mode_spy = MagicMock()
    set_provider_spy = MagicMock()
    set_model_spy = MagicMock()
    set_skill_spy = MagicMock()
    retry_spy = MagicMock(return_value=True)
    delegate_spy = MagicMock(return_value=True)

    handler = TelegramUpdateHandler(
        bot_client=bot,
        security_manager=sec,
        pairing_manager=pairing,
        on_hitl_action=hitl_action_spy,
        set_mode=set_mode_spy,
        set_provider=set_provider_spy,
        set_active_model=set_model_spy,
        set_active_skill=set_skill_spy,
        on_prompt_retry=retry_spy,
        on_agent_delegate=delegate_spy,
        get_providers=lambda: [{"id": "p1", "name": "OpenAI", "is_active": True}],
        get_models=lambda pid=None: [{"id": "gpt-4o", "name": "gpt-4o", "is_active": True}],
    )

    def _make_cb(data, msg_id=10):
        return {
            "callback_query": {
                "id": "cb-123",
                "from": {"id": 456},
                "message": {"chat": {"id": 789}, "message_id": msg_id, "text": "Original text"},
                "data": data,
            }
        }

    # 1. hitl:allow
    handler.handle_update(_make_cb("hitl:allow:req-999"))
    hitl_action_spy.assert_called_with("allow", "req-999")
    bot.answer_callback_query.assert_called_with(callback_query_id="cb-123", text="Persetujuan dicatat: ALLOW")
    assert "DISETUJUI" in bot.edit_message_text.call_args[1]["text"]

    # 2. mode:set:agents
    bot.reset_mock()
    handler.handle_update(_make_cb("mode:set:agents"))
    set_mode_spy.assert_called_with("agents")
    assert "Agents ⚡" in bot.edit_message_text.call_args[1]["text"]

    # 3. config:main
    bot.reset_mock()
    handler.handle_update(_make_cb("config:main"))
    assert "Konfigurasi LLM" in bot.edit_message_text.call_args[1]["text"]

    # 4. config:providers
    bot.reset_mock()
    handler.handle_update(_make_cb("config:providers"))
    assert "Daftar LLM Provider" in bot.edit_message_text.call_args[1]["text"]

    # 5. config:models
    bot.reset_mock()
    handler.handle_update(_make_cb("config:models"))
    assert "Daftar Model" in bot.edit_message_text.call_args[1]["text"]

    # 6. config:ping
    bot.reset_mock()
    handler.handle_update(_make_cb("config:ping"))
    assert "Uji Konektivitas LLM" in bot.edit_message_text.call_args[1]["text"]

    # 7. provider:set:p1
    bot.reset_mock()
    handler.handle_update(_make_cb("provider:set:p1"))
    set_provider_spy.assert_called_with("p1")

    # 8. model:set:gpt-4o
    bot.reset_mock()
    handler.handle_update(_make_cb("model:set:gpt-4o"))
    set_model_spy.assert_called_with("gpt-4o")

    # 9. skill:set:spec-driven-development
    bot.reset_mock()
    handler.handle_update(_make_cb("skill:set:spec-driven-development"))
    set_skill_spy.assert_called_with("spec-driven-development")
    assert "Skill Diaktifkan" in bot.edit_message_text.call_args[1]["text"]

    # 10. prompt:retry:cache-key
    bot.reset_mock()
    handler.handle_update(_make_cb("prompt:retry:cache-key"))
    retry_spy.assert_called_with("cache-key", 789)

    # 11. agent:delegate:sess-key
    bot.reset_mock()
    handler.handle_update(_make_cb("agent:delegate:sess-key"))
    delegate_spy.assert_called_with("sess-key", 789)


# =============================================================================
# 5. EXECUTION ISOLATION (ASK & AGENTS EXECUTORS)
# =============================================================================


def test_turn_executor_ask_mode():
    bot = MagicMock()
    gate = MagicMock()
    svc = MagicMock()

    ask_executor = AskModeTurnExecutor(
        bot_client=bot,
        gate=gate,
        get_active_skill=lambda: "spec-driven-development",
    )

    svc.dispatch_remote_turn.return_value = {
        "consultant_result": {"reply": "Berikut rencana teknis fitur."},
        "session_id": "sess-ask-100",
    }

    ask_executor.execute("Bantu spec login", chat_id=123, svc=svc)

    svc.dispatch_remote_turn.assert_called_with(content="Bantu spec login", mode="ask")
    assert bot.send_message.called
    msg_args = bot.send_message.call_args[1]
    assert "Berikut rencana teknis fitur." in msg_args["text"]
    # Check delegation button is offered because active skill is spec-driven
    markup = msg_args["reply_markup"]
    assert markup["inline_keyboard"][0][0]["callback_data"] == "agent:delegate:sess-ask-100"


def test_turn_executor_ask_mode_error_retry():
    bot = MagicMock()
    gate = MagicMock()
    svc = MagicMock()
    svc.dispatch_remote_turn.side_effect = RuntimeError("Connection timeout to provider")

    ask_executor = AskModeTurnExecutor(
        bot_client=bot,
        gate=gate,
    )

    ask_executor.execute("Bantu spec login", chat_id=123, svc=svc)

    assert gate.save_retry_prompt.called
    assert bot.send_message.called
    msg_args = bot.send_message.call_args[1]
    assert "Terjadi Kesalahan" in msg_args["text"]
    assert "prompt:retry:" in msg_args["reply_markup"]["inline_keyboard"][0][0]["callback_data"]


def test_turn_executor_agents_mode_strict_fail_fast():
    bot = MagicMock()
    gate = MagicMock()
    svc = MagicMock()

    agents_executor = AgentsModeTurnExecutor(
        bot_client=bot,
        gate=gate,
    )

    # Response without task_id in task!
    svc.dispatch_remote_turn.return_value = {
        "status": "ok",
        "task": {},  # NO task_id
    }

    with patch.object(TelegramStreamRelay, "error") as mock_relay_error:
        agents_executor.execute("Jalankan refactor", chat_id=123, svc=svc)

        # MUST FAIL-FAST: relay.error called, gate.register_task NOT called
        assert mock_relay_error.called
        err_text = mock_relay_error.call_args[0][0]
        assert "task ID tidak ditemukan" in err_text
        assert not gate.register_task.called
        assert gate.save_retry_prompt.called


def test_turn_executor_agents_mode_success_stream():
    bot = MagicMock()
    gate = MagicMock()
    svc = MagicMock()

    agents_executor = AgentsModeTurnExecutor(
        bot_client=bot,
        gate=gate,
        poll_interval=0.01,
        max_wait=1,
    )

    svc.dispatch_remote_turn.return_value = {
        "task": {"task_id": "task-auton-999"},
        "session_id": "sess-auton-999",
    }
    svc.get_task.return_value = {"status": "completed"}
    svc.get_task_report.return_value = {"summary": "Perbaikan berhasil diselesaikan."}

    with patch.object(TelegramStreamRelay, "finalize") as mock_relay_finalize:
        agents_executor.execute("Jalankan perbaikan kode", chat_id=123, svc=svc)

        gate.register_task.assert_called_with(123, "task-auton-999", session_id="sess-auton-999")
        assert mock_relay_finalize.called
        fin_text = mock_relay_finalize.call_args[0][0]
        assert "Perbaikan berhasil diselesaikan." in fin_text
        gate.complete_task.assert_called_with(123, "task-auton-999")


# =============================================================================
# 6. COMPANION LIFECYCLE, AUDIT LOG, & DELEGATION
# =============================================================================


def test_companion_lifecycle_and_audit_log():
    bot = MagicMock()
    gate = MagicMock()
    sec = MagicMock()

    gate.resolve_chat_id.return_value = 5555

    companion = TelegramCompanion(
        bot_token="test_token",
        bot_client=bot,
        security_manager=sec,
        gate=gate,
    )

    # 1. Audit log
    sent = companion.send_audit_log(tool_name="edit_file", target="app.py", reason="Refactoring")
    assert sent is True
    gate.resolve_chat_id.assert_called()
    assert bot.send_message.called
    assert "edit_file" in bot.send_message.call_args[1]["text"]

    # 2. Polling lifecycle
    assert companion.start() is True
    bot.start_polling.assert_called()
    companion.stop()
    bot.stop_polling.assert_called()


def test_companion_approval_events():
    bot = MagicMock()
    gate = MagicMock()
    sec = MagicMock()
    coordinator = MagicMock()

    gate.resolve_chat_id.return_value = 5555

    companion = TelegramCompanion(
        bot_token="test_token",
        bot_client=bot,
        security_manager=sec,
        coordinator=coordinator,
        gate=gate,
        get_mode=lambda: "ask",
    )

    # In ask mode, sends diff summary with buttons
    payload = {
        "approval_id": "req-1",
        "tool": "terminal_exec",
        "reason": "Install packages",
        "target_path": "package.json",
    }
    companion.on_approval_event(session_id="sess-1", event_type="approval_requested", payload=payload)
    assert bot.send_message.called
    msg = bot.send_message.call_args[1]
    assert msg["chat_id"] == 5555
    assert "package.json" in msg["text"]
    assert "hitl:allow:req-1" in msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]

    # In agents mode, auto-approves and sends audit log
    bot.reset_mock()
    companion.get_mode = lambda: "agents"
    companion.on_approval_event(session_id="sess-1", event_type="approval_requested", payload=payload)
    coordinator.resolve.assert_called_with("req-1", allow=True)
    assert "AUDIT LOG" in bot.send_message.call_args[1]["text"]


def test_delegation_bridge():
    bot = MagicMock()
    gate = MagicMock()
    sec = MagicMock()

    companion = TelegramCompanion(
        bot_token="test_token",
        bot_client=bot,
        security_manager=sec,
        gate=gate,
    )

    mock_svc = MagicMock()
    mock_svc.delegate_session_to_agent_task.return_value = {
        "task": {"task_id": "task-del-123"}
    }
    mock_svc.get_task.return_value = {"status": "completed"}
    mock_svc.get_task_report.return_value = {"summary": "Delegated task completed"}

    with patch("agent_ai.runtime.telegram.companion._get_gateway_service", return_value=mock_svc):
        with patch.object(TaskMonitor, "poll_task_until_done", return_value=("completed", "Report")):
            res = companion.handle_agent_delegate("sess-del", chat_id=123)
            assert res is True


def test_diff_formatter_and_stream_relay():
    # 1. Diff Formatter
    files = [GitFileDiffStat(path="src/main.py", insertions=10, deletions=2)]
    summary = format_diff_summary("Edit Code", "Refactoring", files)
    assert "src/main.py" in summary
    assert "+10" in summary
    assert "-2" in summary

    # 2. Stream Relay
    bot = MagicMock()
    bot.send_message.return_value = {"ok": True, "result": {"message_id": 999}}

    relay = TelegramStreamRelay(bot_client=bot, chat_id=123, throttle_interval=0.0)
    relay.set_status("⚡", "Working...")
    relay.finalize("Final output", success=True)

    assert bot.send_message.called
    assert bot.edit_message_text.called
    fin_text = bot.edit_message_text.call_args[1]["text"]
    assert "Final output" in fin_text
