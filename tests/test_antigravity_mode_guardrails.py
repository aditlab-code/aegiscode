"""Unit tests untuk guardrail efisiensi mode dan keamanan AntigravityProvider."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, List
import pytest

from agent_ai.config.settings import AntigravityConfig
from agent_ai.tools.base import ToolExecutionError
from agent_ai.providers.antigravity import (
    AntigravityProvider,
    _format_antigravity_policy_directive,
)
from agent_ai.providers.base import GenerateOptions, Message, ProviderAPIError, ProviderUnavailableError
from agent_ai.tools.filesystem import ReadFileTool


def test_format_antigravity_policy_directive() -> None:
    """Pastikan direktif memuat larangan log dan batas per mode."""
    fast_dir = _format_antigravity_policy_directive("fast")
    assert ".aegis/log/" in fast_dir
    assert "FAST" in fast_dir
    assert "SURGICAL RESOLUTION" in fast_dir

    balanced_dir = _format_antigravity_policy_directive("balanced")
    assert ".aegis/log/" in balanced_dir
    assert "BALANCED" in balanced_dir

    deep_dir = _format_antigravity_policy_directive("deep")
    assert ".aegis/log/" in deep_dir
    assert "DEEP" in deep_dir


def test_antigravity_generate_injects_policy_directive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa generate menyuntikkan policy directive ke prompt CLI."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    captured_cmd: List[List[str]] = []

    def fake_run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.append(cmd)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"status": "SUCCESS", "response": "OK"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    opts = GenerateOptions(extra={"mode": "fast"})
    res = p.generate(messages=[{"role": "user", "content": "Perlu dilanjutkan"}], options=opts)
    assert res.text == "OK"
    assert len(captured_cmd) == 1
    prompt_str = captured_cmd[0][2]
    assert "CRITICAL WORKSPACE SAFETY & CONTEXT EFFICIENCY DIRECTIVES:" in prompt_str
    assert ".aegis/log/" in prompt_str
    assert "EXECUTION MODE: FAST" in prompt_str


def test_streaming_circuit_breaker_blocks_log_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa circuit breaker menghentikan proses saat mencoba membaca berkas log."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    class FakeProc:
        def __init__(self) -> None:
            self.killed = False
            self.lines = [
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 1,
                        "tool_info": {
                            "parameters": {"AbsolutePath": "/project/.aegis/log/ac134662b6344cefa10622cd7ec39692.log"}
                        },
                    },
                }) + "\n",
                "",
            ]
            self.stdout = self
            self.stderr = self

        def readline(self) -> str:
            if self.lines:
                return self.lines.pop(0)
            return ""

        def poll(self) -> int | None:
            return 0 if not self.lines else None

        def kill(self) -> None:
            self.killed = True

        def wait(self) -> None:
            pass

        def read(self) -> str:
            return ""

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    def dummy_sink(ev: str, data: Any) -> None:
        pass

    opts = GenerateOptions(extra={"event_sink": dummy_sink, "mode": "fast"})

    with pytest.raises(ProviderAPIError, match="mencoba membaca berkas log"):
        p.generate(prompt="Perlu dilanjutkan", options=opts)

    assert fake_proc.killed is True


def test_streaming_circuit_breaker_allows_fast_mode_file_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa pembacaan berkas ke-4 di mode fast tidak memutus proses (limit kaku dilepas)."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    class FakeProc:
        def __init__(self) -> None:
            self.killed = False
            self.lines = [
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 1,
                        "tool_info": {"parameters": {"path": "src/file1.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 2,
                        "tool_info": {"parameters": {"path": "src/file2.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 3,
                        "tool_info": {"parameters": {"path": "src/file3.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 4,
                        "tool_info": {"parameters": {"path": "src/file4.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "result",
                    "result": {"response": "ok", "status": "SUCCESS"},
                }) + "\n",
            ]
            self.stdout = self
            self.stderr = self

        def readline(self) -> str:
            if self.lines:
                return self.lines.pop(0)
            return ""

        def poll(self) -> int | None:
            return 0 if not self.lines else None

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: Any = None) -> None:
            pass
        def terminate(self) -> None:
            pass

        def read(self) -> str:
            return ""

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    def dummy_sink(ev: str, data: Any) -> None:
        pass

    opts = GenerateOptions(extra={"event_sink": dummy_sink, "mode": "fast"})

    res = p.generate(prompt="Perlu dilanjutkan", options=opts)
    assert res is not None
    assert fake_proc.killed is False


def test_read_file_tool_rejects_log_directories(tmp_path: Path) -> None:
    """Verifikasi bahwa ReadFileTool internal menolak pembacaan berkas di .aegis/log/."""
    log_dir = tmp_path / ".aegis" / "log"
    log_dir.mkdir(parents=True)
    sample_log = log_dir / "test.log"
    sample_log.write_text("dummy trace", encoding="utf-8")

    tool = ReadFileTool(root=tmp_path)

    with pytest.raises(ToolExecutionError, match="Akses ditolak: Pembacaan berkas internal log"):
        tool.execute(path=".aegis/log/test.log")


def test_format_antigravity_policy_directive_redundant_read_directive() -> None:
    """Verifikasi direktif pencegahan re-read redundan tercakup dalam prompt."""
    directive = _format_antigravity_policy_directive("balanced")
    expected_phrase = (
        "Do NOT re-read the same source file repeatedly. "
        "Once you have read a file, utilize its content immediately and proceed with your implementation."
    )
    assert expected_phrase in directive


def test_redundant_reread_warning_injected_after_two_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa pembacaan berkas > 2 kali tanpa mutasi memicu event warning."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    class FakeProc:
        def __init__(self) -> None:
            self.killed = False
            self.returncode = 0
            self.lines = [
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 1,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "DONE",
                        "step_index": 1,
                        "tool_info": {"parameters": {"path": "src/target.ts"}, "output": "content 1"},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 2,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "DONE",
                        "step_index": 2,
                        "tool_info": {"parameters": {"path": "src/target.ts"}, "output": "content 2"},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 3,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "DONE",
                        "step_index": 3,
                        "tool_info": {"parameters": {"path": "src/target.ts"}, "output": "content 3"},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "agent_response",
                        "text_delta": "Perbaikan selesai",
                    },
                }) + "\n",
                "",
            ]
            self.stdout = self
            self.stderr = self

        def readline(self) -> str:
            if self.lines:
                return self.lines.pop(0)
            return ""

        def poll(self) -> int | None:
            return 0 if not self.lines else None

        def kill(self) -> None:
            self.killed = True

        def wait(self) -> int:
            return 0

        def read(self) -> str:
            return ""

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    emitted_events: List[tuple[str, Any]] = []

    def sink(ev: str, data: Any) -> None:
        emitted_events.append((ev, data))

    opts = GenerateOptions(extra={"event_sink": sink, "mode": "balanced"})
    res = p.generate(prompt="Lakukan perbaikan", options=opts)

    assert res.text == "Perbaikan selesai"
    # Verifikasi event warning dipancarkan untuk read ke-3
    warning_events = [data for ev, data in emitted_events if ev == "warning"]
    assert len(warning_events) == 1
    assert warning_events[0]["target"] == "src/target.ts"
    assert warning_events[0]["read_count"] == 3
    assert "PERINGATAN REDUNDANSI" in warning_events[0]["message"]

    # Verifikasi observation_received menyertakan injeksi guardrail pada read ke-3
    observations = [data for ev, data in emitted_events if ev == "observation_received"]
    assert len(observations) == 3
    assert "[SISTEM GUARDRAIL]" not in observations[0]["content"]
    assert "[SISTEM GUARDRAIL]" not in observations[1]["content"]
    assert "[SISTEM GUARDRAIL]" in observations[2]["content"]


def test_redundant_reread_reset_on_file_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa mutasi berkas mereset hitungan pembacaan berkas."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    class FakeProc:
        def __init__(self) -> None:
            self.killed = False
            self.returncode = 0
            self.lines = [
                # Read 1
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 1,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                # Read 2
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 2,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                # Mutasi via edit_file
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "edit_file",
                        "state": "ACTIVE",
                        "step_index": 3,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                # Read setelah mutasi (dihitung sebagai read ke-1 baru)
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "read_file",
                        "state": "ACTIVE",
                        "step_index": 4,
                        "tool_info": {"parameters": {"path": "src/target.ts"}},
                    },
                }) + "\n",
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "agent_response",
                        "text_delta": "Perbaikan selesai",
                    },
                }) + "\n",
                "",
            ]
            self.stdout = self
            self.stderr = self

        def readline(self) -> str:
            if self.lines:
                return self.lines.pop(0)
            return ""

        def poll(self) -> int | None:
            return 0 if not self.lines else None

        def kill(self) -> None:
            self.killed = True

        def wait(self) -> int:
            return 0

        def read(self) -> str:
            return ""

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    emitted_events: List[tuple[str, Any]] = []

    def sink(ev: str, data: Any) -> None:
        emitted_events.append((ev, data))

    opts = GenerateOptions(extra={"event_sink": sink, "mode": "balanced"})
    res = p.generate(prompt="Lakukan perbaikan", options=opts)

    assert res.text == "Perbaikan selesai"
    # Karena edit_file mereset hitungan, read ke-4 tidak memicu warning
    warning_events = [data for ev, data in emitted_events if ev == "warning"]
    assert len(warning_events) == 0


def test_redundant_search_query_circuit_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa pencarian dengan parameter identik berulang 4x memicu circuit breaker."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    class FakeProc:
        def __init__(self) -> None:
            self.killed = False
            self.returncode = 0
            self.lines = [
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "tool_name": "search_code",
                        "state": "ACTIVE",
                        "step_index": i,
                        "tool_info": {"parameters": {"query": "missing_symbol"}},
                    },
                }) + "\n"
                for i in range(1, 5)
            ]
            self.stdout = self
            self.stderr = self

        def readline(self) -> str:
            if self.lines:
                return self.lines.pop(0)
            return ""

        def poll(self) -> int | None:
            return 0 if not self.lines else None

        def kill(self) -> None:
            self.killed = True

        def wait(self) -> int:
            return 0

        def read(self) -> str:
            return ""

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    opts = GenerateOptions(extra={"event_sink": lambda ev, d: None, "mode": "balanced"})
    with pytest.raises(ProviderAPIError) as exc_info:
        p.generate(prompt="Cari simbol", options=opts)

    assert exc_info.value.status_code == 429
    assert "Circuit Breaker Loop Terpicu" in str(exc_info.value)
    assert fake_proc.killed is True


def test_antigravity_cancellation_kills_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa ketika cancel_check bernilai True, subproses Antigravity seketika dibunuh."""
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    class FakeProc:
        def __init__(self) -> None:
            self.killed = False
            self.returncode = 0
            self.lines = [
                json.dumps({
                    "event": "step_update",
                    "step_update": {
                        "step_type": "thought",
                        "thought_delta": "sedang berpikir...",
                    },
                }) + "\n"
            ]
            self.stdout = self
            self.stderr = self

        def readline(self) -> str:
            if self.lines:
                return self.lines.pop(0)
            return ""

        def poll(self) -> int | None:
            return None

        def kill(self) -> None:
            self.killed = True

        def wait(self) -> int:
            return 0

        def read(self) -> str:
            return ""

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    # Simulasikan cancel_check yang menjadi True saat proses berjalan
    cancelled_flag = [False]

    def check_cancel() -> bool:
        return cancelled_flag[0]

    def event_sink(ev: str, d: Any) -> None:
        # Begitu menerima event reasoning pertama, pengguna mengklik Stop (cancel_check menjadi True)
        if ev == "agent_reasoning_delta":
            cancelled_flag[0] = True

    opts = GenerateOptions(extra={
        "event_sink": event_sink,
        "cancel_check": check_cancel,
        "mode": "balanced",
    })

    with pytest.raises(ProviderUnavailableError, match="dibatalkan oleh pengguna"):
        p.generate(prompt="Jalankan tugas", options=opts)

    assert fake_proc.killed is True


