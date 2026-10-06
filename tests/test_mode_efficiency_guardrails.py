"""Unit tests untuk penegakan efisiensi 3 Mode (Fast, Balanced, Deep).

Memverifikasi:
1. Batas maksimal 3 berkas unik penuh pada Mode Fast.
2. Penolakan terarah berkas ke-4 dengan pesan FAST_MODE_FILE_LIMIT_EXCEEDED.
3. Pembacaan simbol/rentang dan search_code tetap diizinkan pada batas mode Fast.
4. Eskalasi melalui RequestPolicyEscalationTool memperluas kuota ke mode Balanced (8 berkas) lalu Deep.
5. Injeksi directive system prompt per mode pada AgentOrchestrator.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_ai.core.orchestrator import AgentOrchestrator
from agent_ai.runtime.policy import (
    FAST_MODE_MAX_FULL_READS,
    BALANCED_MODE_MAX_FULL_READS,
    ExecutionPolicyResolver,
    ExecutionPolicyState,
    directive_prompt_for_mode,
)
from agent_ai.runtime.runtime import AgentRuntime
from agent_ai.task.models import PreparedTask
from agent_ai.tools.base import ToolExecutionError, ToolValidationError
from agent_ai.tools.filesystem import ReadFileTool
from agent_ai.tools.policy import RequestPolicyEscalationTool
from agent_ai.tools.read_cache import ToolReadCache
from agent_ai.tools.registry import ToolRegistry, build_registry


class DummyProvider:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []

    def generate(self, messages, tools=None, options=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        return SimpleNamespace(message=SimpleNamespace(content="selesai", tool_calls=[]))


def test_directive_prompt_contents():
    fast_prompt = directive_prompt_for_mode("fast")
    assert "FAST MODE ACTIVE" in fast_prompt
    assert "maximum 3 full file reads" in fast_prompt.lower()
    assert "request_policy_escalation" in fast_prompt

    balanced_prompt = directive_prompt_for_mode("balanced")
    assert "BALANCED MODE ACTIVE" in balanced_prompt
    assert "up to 8 full file reads" in balanced_prompt.lower()

    deep_prompt = directive_prompt_for_mode("deep")
    assert "DEEP MODE ACTIVE" in deep_prompt
    assert "unrestricted exploration" in deep_prompt.lower()



def test_fast_mode_read_file_limit():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        # Buat 5 berkas dummy
        for i in range(1, 6):
            (root / f"file{i}.py").write_text(f"def func_{i}():\n    return {i}\n")

        cache = ToolReadCache()
        cache.set_policy_mode("fast")
        read_tool = ReadFileTool(root=root, read_cache=cache)

        # 1. Tiga berkas pertama berhasil dibaca penuh
        r1 = read_tool.execute(path="file1.py")
        assert "func_1" in r1["content"]
        r2 = read_tool.execute(path="file2.py")
        assert "func_2" in r2["content"]
        r3 = read_tool.execute(path="file3.py")
        assert "func_3" in r3["content"]
        assert cache.full_read_count() == 3

        # 2. Berkas yang sudah dibaca boleh dibaca ulang
        r1_again = read_tool.execute(path="file1.py")
        assert r1_again.get("already_available") is True or "func_1" in r1_again.get("content", "")

        # 3. Berkas ke-4 DITOLAK dengan pesan instruksi eskalasi
        with pytest.raises(ToolExecutionError) as exc_info:
            read_tool.execute(path="file4.py")

        err_msg = str(exc_info.value)
        assert "FAST_MODE_FILE_LIMIT_EXCEEDED" in err_msg
        assert "request_policy_escalation" in err_msg
        assert "target_mode='balanced'" in err_msg

        # 4. Pembacaan simbol atau rentang baris TETAP DIIZINKAN (surgical read)
        r4_symbol = read_tool.execute(path="file4.py", symbol="func_4")
        assert "func_4" in r4_symbol["content"]

        r5_range = read_tool.execute(path="file5.py", start_line=1, end_line=1)
        assert "def func_5" in r5_range["content"]


def test_escalation_broadens_read_file_limit():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        for i in range(1, 12):
            (root / f"f{i}.py").write_text(f"# file {i}\nx = {i}\n")

        cache = ToolReadCache()
        cache.set_policy_mode("fast")
        read_tool = ReadFileTool(root=root, read_cache=cache)

        # Baca 3 berkas di mode Fast
        for i in range(1, 4):
            read_tool.execute(path=f"f{i}.py")

        # Berkas ke-4 ditolak di Fast
        with pytest.raises(ToolExecutionError) as exc_info:
            read_tool.execute(path="f4.py")
        assert "FAST_MODE_FILE_LIMIT_EXCEEDED" in str(exc_info.value)

        # Escalasi ke Balanced
        cache.set_policy_mode("balanced")

        # Sekarang berkas ke-4 berhasil dibaca!
        r4 = read_tool.execute(path="f4.py")
        assert "file 4" in r4["content"]

        # Baca hingga berkas ke-8
        for i in range(5, 9):
            read_tool.execute(path=f"f{i}.py")
        assert cache.full_read_count() == 8

        # Berkas ke-9 ditolak di Balanced
        with pytest.raises(ToolExecutionError) as exc_info:
            read_tool.execute(path="f9.py")
        assert "BALANCED_MODE_FILE_LIMIT_EXCEEDED" in str(exc_info.value)

        # Escalasi ke Deep
        cache.set_policy_mode("deep")

        # Berkas ke-9 dan seterusnya bebas dibaca
        r9 = read_tool.execute(path="f9.py")
        assert "file 9" in r9["content"]
        r10 = read_tool.execute(path="f10.py")
        assert "file 10" in r10["content"]


def test_request_policy_escalation_tool():
    current_mode = "fast"

    def dummy_escalator(reason, target_mode=None):
        nonlocal current_mode
        current_mode = target_mode or "balanced"
        return SimpleNamespace(effective_mode=current_mode, reason=reason)

    tool = RequestPolicyEscalationTool(escalator=dummy_escalator)

    # Validasi input
    with pytest.raises(ToolValidationError):
        tool.execute()
    with pytest.raises(ToolValidationError):
        tool.execute(reason="   ")

    # Eksekusi eskalasi berhasil
    res = tool.execute(reason="Perlu membaca modul tambahan", target_mode="balanced")
    assert res["success"] is True
    assert res["effective_mode"] == "balanced"
    assert current_mode == "balanced"


def test_orchestrator_injects_policy_directive_message():
    provider = DummyProvider()
    orchestrator = AgentOrchestrator(
        provider=provider,
        system_prompt="Base System Prompt",
        execution_policy={"effective_mode": "fast", "requested_mode": "fast"},
    )

    messages = orchestrator._build_messages("Kerjakan tugas", [])
    system_contents = [m.content for m in messages if m.role == "system"]
    assert "Base System Prompt" in system_contents
    assert any("FAST MODE ACTIVE" in sc for sc in system_contents)


def test_runtime_syncs_policy_with_cache_and_tools(tmp_path):
    registry = build_registry(root=tmp_path)
    runtime = AgentRuntime(
        provider=DummyProvider(),
        project_root=tmp_path,
        requested_mode="fast",
    )
    # Suntikkan executor dengan registry yang baru dibangun
    from agent_ai.core.executor import ToolExecutor
    runtime.executor = ToolExecutor(registry=registry, workspace_root=tmp_path)

    # Jalankan runtime dengan task
    prepared = PreparedTask(task="lakukan sesuatu", task_id="test-policy-sync")
    runtime.run(prepared)

    # Periksa apakah read_cache sinkron ke mode 'fast'
    assert registry.read_cache.get_policy_mode() == "fast"

    # Periksa apakah tool request_policy_escalation terhubung ke escalator
    escalate_tool = registry.get("request_policy_escalation")
    assert escalate_tool is not None
    assert escalate_tool.escalator is not None

    # Panggil eskalasi lewat tool
    res = escalate_tool.execute(reason="Kebutuhan multi modul", target_mode="balanced")
    assert res["success"] is True
    assert res["effective_mode"] == "balanced"
    # Mode di cache ikut terbarui secara real-time
    assert registry.read_cache.get_policy_mode() == "balanced"
