"""Tests for Task Scheduler Lifecycle & Safe Boundary Isolation.

Mencakup:
1. Anti-Double-Scheduling & Atomic State Guard (enqueue_guard terminal rejection, concurrent scheduler dispatch).
2. Cooperative Cancellation Safe Boundary & Eliminasi Duplikasi Event (single task_cancelled event, tool boundary).
3. Deteksi Respons Malformed dari Provider (empty response fails deterministically, provider_malformed_response event).
4. Deterministic Error & Timeout Terminal Status (TimeoutError, provider_retry_exhausted, task_failed structured payload).
5. Uncaught exception & Emergency loop safety abort (loop_safety_abort preserves FAILED status).
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DJANGO_DIR = PROJECT_ROOT / "web" / "django_app"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(DJANGO_DIR) not in sys.path:
    sys.path.insert(0, str(DJANGO_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

from agent_ai.core.cancel import CancellationToken
from agent_ai.core.executor import ToolExecutor
from agent_ai.tools.base import BaseTool
from agent_ai.core.models import AgentStatus
from agent_ai.core.orchestrator import AgentOrchestrator
from agent_ai.core.response import ActionType, LLMAction, LLMResponse
from agent_ai.providers.base import BaseProvider, GenerateOptions, GenerateResult
from agent_ai.runtime.lifecycle import (
    TERMINAL_LIFECYCLE_STATES,
    TaskLifecycleManager,
    TaskLifecycleState,
)
from tests.conftest import wait_for_condition
from agent_ai.runtime.runtime import AgentRuntime, RuntimeProgress, RuntimeResult, RuntimeStatus
from agent_ai.session.events import EventType, ExecutionEvent
from agent_ai.session.store import InMemorySessionStore
from agent_ai.tasks.models import TaskStatus
from api.services import GatewayService, TaskRecord


# --------------------------------------------------------------------------- #
# Helpers & Mock Providers
# --------------------------------------------------------------------------- #
class DummyMockProvider(BaseProvider):
    """Provider minimal untuk simulasi response terkontrol."""

    def __init__(self, responses: Optional[List[Any]] = None) -> None:
        super().__init__()
        self.name = "mock_provider"
        self._responses = list(responses or [])
        self._call_count = 0

    def generate(
        self,
        messages: List[Any],
        options: Optional[GenerateOptions] = None,
        tools: Optional[List[Any]] = None,
        tool_choice: Any = None,
    ) -> GenerateResult:
        self._call_count += 1
        if self._responses:
            item = self._responses.pop(0)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, GenerateResult):
                return item
            if isinstance(item, str):
                return GenerateResult(text=item, raw={})
        return GenerateResult(text="Selesai", raw={})

    def normalize_response(self, result: GenerateResult) -> LLMResponse:
        raw = result.raw or {}
        choices = raw.get("choices") or []
        actions: list[LLMAction] = []
        if choices:
            msg = choices[0].get("message") or {}
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                actions.append(
                    LLMAction(
                        type=ActionType.TOOL_CALL,
                        name=fn.get("name", "unknown"),
                        arguments=args,
                        id=tc.get("id"),
                    )
                )
        return LLMResponse(
            text=result.text or "",
            actions=actions,
            provider=self.name,
            reasoning=result.reasoning,
        )


# --------------------------------------------------------------------------- #
# 1. Anti-Double-Scheduling & Idempotency Tests
# --------------------------------------------------------------------------- #
def test_enqueue_guard_rejects_terminal_states() -> None:
    """Task yang berstatus COMPLETED, FAILED, atau CANCELLED dilarang masuk antrean kembali."""
    for state in (
        TaskLifecycleState.COMPLETED.value,
        TaskLifecycleState.FAILED.value,
        TaskLifecycleState.CANCELLED.value,
    ):
        mgr = TaskLifecycleManager(task_id=f"t-term-{state}", initial_state=state)
        # Langsung panggil enqueue_guard pada state terminal
        assert mgr.enqueue_guard() is False
        assert mgr.current_state == state
        assert mgr.is_terminal is True


def test_concurrent_scheduler_dispatch_executes_only_once() -> None:
    """10 thread memanggil _scheduler_pump dan _start_execution serentak untuk task yang sama.
    Task hanya boleh dieksekusi tepat satu kali.
    """
    service = GatewayService()
    service.auto_execute = False  # Kontrol manual pemanggilan scheduler

    # Buat task dalam status pending
    res = service.create_task("Tugas pengujian concurrency")
    task_id = res["task_id"]

    execution_count = 0
    lock = threading.Lock()

    def fake_run_task_inner(tid: str, token: CancellationToken) -> None:
        nonlocal execution_count
        with lock:
            execution_count += 1

    service._run_task_inner = fake_run_task_inner  # type: ignore

    # 10 thread mencoba memicu _scheduler_pump dan _start_execution secara serentak
    def worker(idx: int) -> None:
        if idx % 2 == 0:
            service._scheduler_pump()
        else:
            service._start_execution(task_id)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(worker, i) for i in range(10)]
        for f in futures:
            f.result()

    # Menunggu task dieksekusi dan mencapai status terminal secara deterministik
    wait_for_condition(lambda: execution_count >= 1, timeout=3.0, interval=0.02)
    wait_for_condition(
        lambda: (
            service.get_task(task_id).get("queue_state") == "done"
            or service.get_task(task_id).get("status") in ("completed", "failed", "cancelled")
        ),
        timeout=3.0,
        interval=0.02,
    )
    assert execution_count == 1
    rec = service.get_task(task_id)
    # Setelah eksekusi slot dilepas dan queue_state menjadi done
    assert rec["queue_state"] == "done"


# --------------------------------------------------------------------------- #
# 2. Cooperative Cancellation & Event Deduplication Tests
# --------------------------------------------------------------------------- #
def test_cancel_pending_task_emits_single_cancelled_event() -> None:
    """Pembatalan task yang masih pending di queue menghasilkan tepat 1 event task_cancelled."""
    service = GatewayService()
    service.auto_execute = False  # Jangan auto jalankan agar tetap pending

    res = service.create_task("Tugas yang akan dibatalkan")
    task_id = res["task_id"]
    session_id = res["session_id"]

    assert service.get_task(task_id)["queue_state"] == "pending"
    assert task_id not in service._cancel_tokens

    # Batalkan task
    cancelled_res = service.cancel_task(task_id)
    assert cancelled_res["status"] == "cancelled"

    # Periksa event di session store
    events = service.sessions.get_events(session_id, task_id=task_id)
    cancel_events = [
        e for e in events
        if getattr(e.event_type, "value", str(e.event_type)) == "task_cancelled"
    ]
    assert len(cancel_events) == 1
    assert cancel_events[0].payload.get("reason") == "user_cancelled"

    # Panggilan cancel kedua idempoten (status tidak berubah, tidak menambah event duplikat)
    service.cancel_task(task_id)
    events_after = service.sessions.get_events(session_id, task_id=task_id)
    cancel_events_after = [
        e for e in events_after
        if getattr(e.event_type, "value", str(e.event_type)) == "task_cancelled"
    ]
    assert len(cancel_events_after) == 1


def test_cancel_running_task_deduplicates_terminal_event() -> None:
    """Pembatalan task yang sedang running menghasilkan tepat 1 event task_cancelled (tanpa duplikat)."""
    service = GatewayService()
    service.auto_execute = False

    res = service.create_task("Tugas berjalan dibatalkan")
    task_id = res["task_id"]
    session_id = res["session_id"]

    # Simulasikan task running dengan token aktif
    token = CancellationToken()
    service._cancel_tokens[task_id] = token
    with service._lock:
        service._tasks[task_id].queue_state = "running"
        service._tasks[task_id].status = "running"

    # Pembatalan dipanggil saat token aktif di background
    service.cancel_task(task_id)
    assert token.is_cancelled() is True
    assert service.get_task(task_id)["status"] == "cancelled"

    # Di background thread, runtime mencapai safe boundary dan memancarkan terminal event
    runtime = AgentRuntime(
        provider=DummyMockProvider(),
        session_store=service.sessions,
        session_id=session_id,
    )
    runtime._current_task_id = task_id
    progress = RuntimeProgress()
    cancelled_result = RuntimeResult(
        status=RuntimeStatus.CANCELLED,
        result=None,
        error="Dibatalkan pengguna",
        progress=progress,
    )
    # Finalisasi runtime
    runtime._lifecycle_finalize(None, cancelled_result)

    # Periksa total event task_cancelled
    events = service.sessions.get_events(session_id, task_id=task_id)
    cancel_events = [
        e for e in events
        if getattr(e.event_type, "value", str(e.event_type)) == "task_cancelled"
    ]

    # Finalisasi kedua kali tidak boleh menambah event terminal
    runtime._lifecycle_finalize(None, cancelled_result)
    events_again = service.sessions.get_events(session_id, task_id=task_id)
    cancel_events_again = [
        e for e in events_again
        if getattr(e.event_type, "value", str(e.event_type)) == "task_cancelled"
    ]

def test_safe_boundary_cancellation_aborts_subsequent_tools() -> None:
    """Pembatalan kooperatif di safe boundary menghentikan pemanggilan tool berikutnya."""
    tool2_called = False

    class ScriptedMultiToolProvider(BaseProvider):
        def __init__(self) -> None:
            super().__init__()
            self.name = "multi_tool_provider"
            self.call_count = 0

        def generate(self, messages, options=None, tools=None, tool_choice=None):
            self.call_count += 1
            if self.call_count == 1:
                tc1 = {"id": "c1", "type": "function", "function": {"name": "tool1", "arguments": "{}"}}
                return GenerateResult(text="", raw={"choices": [{"message": {"tool_calls": [tc1]}}]})
            if self.call_count == 2:
                tc2 = {"id": "c2", "type": "function", "function": {"name": "tool2", "arguments": "{}"}}
                return GenerateResult(text="", raw={"choices": [{"message": {"tool_calls": [tc2]}}]})
            return GenerateResult(text="Selesai", raw={})

        def normalize_response(self, result: GenerateResult) -> LLMResponse:
            raw = result.raw or {}
            choices = raw.get("choices") or []
            actions = []
            if choices:
                msg = choices[0].get("message") or {}
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    actions.append(LLMAction(
                        type=ActionType.TOOL_CALL,
                        name=fn.get("name", "unknown"),
                        arguments={},
                        id=tc.get("id"),
                    ))
            return LLMResponse(text=result.text or "", actions=actions, provider=self.name)

    token = CancellationToken()
    provider = ScriptedMultiToolProvider()

    class Tool1(BaseTool):
        name = "tool1"
        description = "tool 1"
        def execute(self, **arguments: Any) -> Any:
            token.request("user_stopped_after_tool1")
            return "tool1 ok"

    class Tool2(BaseTool):
        name = "tool2"
        description = "tool 2"
        def execute(self, **arguments: Any) -> Any:
            nonlocal tool2_called
            tool2_called = True
            return "tool2 ok"
    executor = ToolExecutor()
    executor.registry.register(Tool1())
    executor.registry.register(Tool2())

    orchestrator = AgentOrchestrator(
        provider=provider,
        executor=executor,
        cancel_token=token,
    )
    result = orchestrator.run("Tugas 2 langkah tool")

    assert result.status == AgentStatus.CANCELLED
    assert tool2_called is False
    assert provider.call_count == 1

# --------------------------------------------------------------------------- #
# 3. Malformed Provider Response Detection Tests
# --------------------------------------------------------------------------- #
def test_malformed_empty_response_fails_deterministically() -> None:
    """Respons kosong tanpa text, tool call, maupun reasoning menghasilkan status FAILED
    dan memancarkan event provider_malformed_response.
    """
    empty_provider = DummyMockProvider(responses=[GenerateResult(text="", raw={})])
    events: list[tuple[str, dict]] = []

    def sink(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    orchestrator = AgentOrchestrator(
        provider=empty_provider,
        event_sink=sink,
    )
    result = orchestrator.run("Lakukan sesuatu")

    # Status harus FAILED (bukan DONE/COMPLETED)
    assert result.status == AgentStatus.FAILED
    assert "respons kosong" in (result.error or "")

    # Event provider_malformed_response harus dipancarkan
    malformed_events = [p for et, p in events if et == "provider_malformed_response"]
    assert len(malformed_events) == 1
    assert malformed_events[0]["error"] == "empty_content_and_tools"


def test_malformed_empty_response_tolerated_with_explicit_flag() -> None:
    """Bila opsi allow_empty_response=True disetel eksplisit, respons kosong diterima."""
    empty_provider = DummyMockProvider(responses=[GenerateResult(text="", raw={})])
    orchestrator = AgentOrchestrator(
        provider=empty_provider,
        options=GenerateOptions(extra={"allow_empty_response": True}),
    )
    result = orchestrator.run("Lakukan sesuatu")
    assert result.status == AgentStatus.DONE


# --------------------------------------------------------------------------- #
# 4. Deterministic Error & Timeout Handling Tests
# --------------------------------------------------------------------------- #
def test_provider_timeout_exhaustion_produces_structured_failure() -> None:
    """Timeout request yang menghabiskan kuota retry menghasilkan status terminal FAILED
    dengan error_type='timeout'.
    """
    timeout_provider = DummyMockProvider(
        responses=[TimeoutError("Connection timed out"), TimeoutError("Connection timed out")]
    )
    events: list[tuple[str, dict]] = []

    def sink(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    orchestrator = AgentOrchestrator(
        provider=timeout_provider,
        event_sink=sink,
    )
    # Set retry policy agar 1 attempt awal + 1 retry = 2 attempts
    orchestrator._api_retry_policy = lambda: (1, 0.0)  # type: ignore

    result = orchestrator.run("Lakukan operasi berbatas waktu")

    assert result.status == AgentStatus.FAILED
    assert "timed out" in (result.error or "").lower()

    # Periksa event provider_retry_exhausted
    exhausted_events = [p for et, p in events if et == "provider_retry_exhausted"]
    assert len(exhausted_events) == 1
    assert exhausted_events[0]["error_type"] == "timeout"


def test_runtime_task_failed_event_includes_timeout_type() -> None:
    """AgentRuntime memancarkan event task_failed dengan payload {'error_type': 'timeout'}
    saat RuntimeResult berstatus timeout.
    """
    store = InMemorySessionStore()
    session = store.create_session("s-timeout")
    runtime = AgentRuntime(
        provider=DummyMockProvider(),
        session_store=store,
        session_id=session.session_id,
    )
    runtime._current_task_id = "task-to-1"

    result = RuntimeResult(
        status=RuntimeStatus.FAILED,
        result=None,
        error="Provider 'openai' request timed out after 4 attempts",
        progress=RuntimeProgress(),
    )
    runtime._lifecycle_finalize(None, result)

    evts = store.get_events(session.session_id, task_id="task-to-1")
    failed_evts = [
        e for e in evts
        if getattr(e.event_type, "value", str(e.event_type)) == "task_failed"
    ]
    assert len(failed_evts) == 1
    assert failed_evts[0].payload.get("error_type") == "timeout"


# --------------------------------------------------------------------------- #
# 5. Loop Safety Abort & Uncaught Exception Boundaries
# --------------------------------------------------------------------------- #
def test_emergency_safety_ceiling_aborts_as_failed() -> None:
    """Bila jumlah langkah tool menyentuh max_steps, status loop adalah FAILED (bukan DONE)."""
    tool_call_dict = {
        "id": "c1",
        "type": "function",
        "function": {"name": "test_tool", "arguments": "{}"},
    }
    looping_provider = DummyMockProvider(
        responses=[
            GenerateResult(text="", raw={"choices": [{"message": {"tool_calls": [tool_call_dict]}}]}),
            GenerateResult(text="", raw={"choices": [{"message": {"tool_calls": [tool_call_dict]}}]}),
            GenerateResult(text="", raw={"choices": [{"message": {"tool_calls": [tool_call_dict]}}]}),
        ]
    )
    events: list[tuple[str, dict]] = []

    def sink(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    orchestrator = AgentOrchestrator(
        provider=looping_provider,
        event_sink=sink,
    )
    # Jalankan dengan max_steps=2
    res = orchestrator.run_continuous_loop("Infinite tool task", max_steps=2)
    assert res.status == AgentStatus.FAILED
    assert "Emergency safety limit tercapai" in (res.error or "")

    abort_events = [p for et, p in events if et == "loop_safety_abort"]
    assert len(abort_events) == 1


def test_execute_task_unexpected_crash_transitions_to_terminal_failed() -> None:
    """Jika _run_task_inner crash atau melempar unhandled exception, task record
    wajib ditransisikan ke status failed dan queue_state menjadi done tanpa menggantung.
    """
    service = GatewayService()
    service.auto_execute = False

    res = service.create_task("Tugas simulasi crash worker")
    task_id = res["task_id"]

    def crashing_run_task_inner(tid: str, token: CancellationToken) -> None:
        raise RuntimeError("Fatal worker thread crash")

    service._run_task_inner = crashing_run_task_inner  # type: ignore

    token = CancellationToken()
    with pytest.raises(RuntimeError, match="Fatal worker thread crash"):
        service._execute_task(task_id, token)

    rec = service.get_task(task_id)
    assert rec["status"] == "failed"
    assert rec["queue_state"] == "done"
    assert "Task terminated unexpectedly" in rec.get("error", "")


def test_kill_process_tree_tiered_sigterm_and_cleanup() -> None:
    """_kill_process_tree menghentikan proses anak dan descendant tanpa exception."""
    from agent_ai.tools.terminal import _kill_process_tree

    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert proc.poll() is None
    _kill_process_tree(proc)
    proc.wait(timeout=1.0)
    assert proc.poll() is not None
