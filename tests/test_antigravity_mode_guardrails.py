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
from agent_ai.providers.base import GenerateOptions, Message, ProviderAPIError
from agent_ai.tools.filesystem import ReadFileTool


def test_format_antigravity_policy_directive() -> None:
    """Pastikan direktif memuat larangan log dan batas per mode."""
    fast_dir = _format_antigravity_policy_directive("fast")
    assert ".aegis/log/" in fast_dir
    assert ".aether/log/" in fast_dir
    assert "FAST" in fast_dir
    assert "2-3" in fast_dir

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


def test_streaming_circuit_breaker_enforces_fast_mode_file_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifikasi bahwa circuit breaker menghentikan pembacaan berkas ke-4 di mode fast."""
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

    with pytest.raises(ProviderAPIError, match="Pelanggaran Guardrail Efisiensi Mode Fast"):
        p.generate(prompt="Perlu dilanjutkan", options=opts)

    assert fake_proc.killed is True


def test_read_file_tool_rejects_log_directories(tmp_path: Path) -> None:
    """Verifikasi bahwa ReadFileTool internal menolak pembacaan berkas di .aegis/log/."""
    log_dir = tmp_path / ".aegis" / "log"
    log_dir.mkdir(parents=True)
    sample_log = log_dir / "test.log"
    sample_log.write_text("dummy trace", encoding="utf-8")

    tool = ReadFileTool(root=tmp_path)

    with pytest.raises(ToolExecutionError, match="Akses ditolak: Pembacaan berkas internal log"):
        tool.execute(path=".aegis/log/test.log")
