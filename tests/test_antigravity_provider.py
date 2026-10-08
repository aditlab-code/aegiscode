"""Unit tests untuk AntigravityProvider (Google Antigravity).

Menguji:
    1. registry.get("antigravity") mengembalikan AntigravityProvider.
    2. Katalog get_provider_type("antigravity") mengembalikan spec Antigravity yang benar.
    3. build_provider_from_config() dengan provider_type="antigravity" berhasil.
    4. AntigravityProvider.is_available() mendeteksi keberadaan CLI atau API key.
    5. AntigravityProvider.list_available_models() menyajikan model frontier Antigravity.
    6. AntigravityProvider.generate() mengeksekusi via CLI bridge atau HTTP API mock.
    7. LLMConfigService.ensure_default_providers() mendaftarkan Google Antigravity otomatis.

Semua test DETERMINISTIK tanpa koneksi live network eksternal.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from agent_ai.config.settings import AntigravityConfig
from agent_ai.llm_config.providers import get_provider_type
from agent_ai.providers.antigravity import AntigravityProvider, DEFAULT_ANTIGRAVITY_MODELS
from agent_ai.core.response import FinishReason
from agent_ai.providers.base import (
    GenerateOptions,
    GenerateResult,
    Message,
    ProviderAPIError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    ToolChoice,
    ToolDefinition,
)
from agent_ai.providers.factory import build_provider_from_config
from agent_ai.providers.registry import get_provider


# --------------------------------------------------------------------------- #
# 1. Provider Registry
# --------------------------------------------------------------------------- #
def test_registry_get_antigravity_returns_provider() -> None:
    provider = get_provider("antigravity")
    assert isinstance(provider, AntigravityProvider)
    assert provider.name == "antigravity"


# --------------------------------------------------------------------------- #
# 2. Katalog Provider Type
# --------------------------------------------------------------------------- #
def test_catalog_antigravity_spec() -> None:
    spec = get_provider_type("antigravity")
    assert spec is not None
    assert spec.key == "antigravity"
    assert spec.label == "Google Antigravity"
    assert spec.env_prefix == "ANTIGRAVITY"
    assert spec.requires_api_key is False  # CLI/OAuth token
    assert spec.requires_model is True
    assert spec.supports_model_discovery is True


# --------------------------------------------------------------------------- #
# 3. Factory build_provider_from_config
# --------------------------------------------------------------------------- #
def test_factory_builds_antigravity_provider() -> None:
    config: dict[str, Any] = {
        "provider_type": "antigravity",
        "api_url": "https://antigravity.google/api/v1",
        "api_key": "test_token_123",
        "model": "gemini-3.8-flash-medium",
        "timeout": 90,
    }
    provider = build_provider_from_config(config)
    assert isinstance(provider, AntigravityProvider)
    assert provider.name == "antigravity"
    assert provider.config.base_url == "https://antigravity.google/api/v1"
    assert provider.config.api_key == "test_token_123"
    assert provider.config.model == "gemini-3.8-flash-medium"
    assert provider.config.timeout == 90


# --------------------------------------------------------------------------- #
# 4. is_available & model discovery
# --------------------------------------------------------------------------- #
def test_is_available_with_api_key() -> None:
    cfg = AntigravityConfig(api_key="token_abc", cli_path="/non/existent/path")
    p = AntigravityProvider(config=cfg)
    assert p.is_available() is True


def test_list_available_models_fallback() -> None:
    cfg = AntigravityConfig(cli_path="/non/existent/path")
    p = AntigravityProvider(config=cfg)
    models = p.list_available_models()
    assert "gemini-3.8-flash-medium" in models
    assert "gemini-3.1-pro-high" in models
    assert "claude-sonnet-4-6" in models


# --------------------------------------------------------------------------- #
# 5. generate() via CLI bridge (mocked subprocess)
# --------------------------------------------------------------------------- #
def test_generate_via_cli_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(cli_path="/bin/agy_mock", model="gemini-3.8-flash-medium")
    p = AntigravityProvider(config=cfg)

    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    fake_response = {
        "status": "SUCCESS",
        "response": "Hello from Antigravity model!",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps(fake_response),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = p.generate(prompt="Hello")
    assert res.text == "Hello from Antigravity model!"
    assert res.model == "gemini-3.8-flash-medium"
    assert res.provider == "antigravity"


def test_generate_handles_dict_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    captured_prompt = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        # cmd[2] is prompt
        captured_prompt.append(cmd[2])
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"response": "Dict message handled!"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Runtime passes dicts: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    dict_messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "Write code."},
    ]
    res = p.generate(messages=dict_messages)
    assert res.text == "Dict message handled!"
    assert "[SYSTEM]:\nYou are an agent." in captured_prompt[0]
    assert "[USER]:\nWrite code." in captured_prompt[0]


def test_generate_cli_error_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr="Antigravity auth expired",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ProviderAPIError, match="Antigravity CLI mengembalikan error"):
        p.generate(prompt="Hello")


# --------------------------------------------------------------------------- #
# 6. generate() via HTTP API mock
# --------------------------------------------------------------------------- #
def test_generate_via_http_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(
        api_key="token_secret",
        base_url="https://mock.antigravity.google/v1",
        cli_path="/non/existent",
    )
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: None)

    class FakeResponse:
        ok = True
        status_code = 200
        text = '{"choices": [{"message": {"content": "HTTP Antigravity answer"}}]}'

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": "HTTP Antigravity answer"}}]}

    import requests
    monkeypatch.setattr(requests, "post", lambda url, **kwargs: FakeResponse())

    res = p.generate(messages=[Message(role="user", content="Hi")])
    assert res.text == "HTTP Antigravity answer"


def test_generate_not_configured_raises() -> None:
    cfg = AntigravityConfig(api_key="", cli_path="/non/existent")
    p = AntigravityProvider(config=cfg)
    p._resolve_cli_path = lambda: None  # type: ignore

    with pytest.raises(ProviderNotConfiguredError, match="belum dikonfigurasi"):
        p.generate(prompt="Test")


# --------------------------------------------------------------------------- #
# 7. LLMConfigService.ensure_default_providers() auto-registration
# --------------------------------------------------------------------------- #
def test_llm_config_service_ensure_default_providers_registers_antigravity(tmp_path: Path) -> None:
    from agent_ai.llm_config.service import LLMConfigService

    db_path = tmp_path / "test_aether.db"
    env_path = tmp_path / ".env"
    env_path.write_text("ANTIGRAVITY_API_KEY=test_ag_key\n", encoding="utf-8")

    svc = LLMConfigService(db_path=db_path, env_path=env_path)
    assert len(svc.store.list_provider_instances()) == 0

    svc.ensure_default_providers()

    instances = svc.store.list_provider_instances()
    ag_inst = next((i for i in instances if i.provider_type == "antigravity"), None)
    assert ag_inst is not None
    assert ag_inst.name == "Google Antigravity"
    assert ag_inst.enabled is True
    assert ag_inst.api_key_env == "ANTIGRAVITY_API_KEY"

    # Default models are seeded
    models = svc.store.list_models(ag_inst.id)
    model_names = {m.model_name for m in models}
    assert "gemini-3.8-flash-medium" in model_names
    assert "gemini-3.1-pro-high" in model_names
    assert "claude-sonnet-4-6" in model_names


# --------------------------------------------------------------------------- #
# 8. Enterprise Features (ADC & Regional / Project Environment)
# --------------------------------------------------------------------------- #
def test_is_available_with_enterprise_adc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adc_mock = tmp_path / "adc.json"
    adc_mock.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("os.path.expanduser", lambda p: str(adc_mock) if "application_default_credentials" in p else p)

    cfg = AntigravityConfig(cli_path="/non/existent", api_key="", enable_adc=True)
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: None)
    assert p.is_available() is True


def test_generate_propagates_enterprise_env(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(
        cli_path="/bin/agy_mock",
        project_id="corp-gemini-ai",
        location="us",
        enable_adc=True,
    )
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    captured_env: dict[str, str] = {}

    def fake_run(cmd: list[str], env: dict[str, str] | None = None, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if env:
            captured_env.update(env)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"status": "SUCCESS", "response": "Enterprise OK"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = p.generate(prompt="Run enterprise check")
    assert res.text == "Enterprise OK"
    assert captured_env.get("AGY_ADC_AUTH") == "true"
    assert captured_env.get("GOOGLE_CLOUD_PROJECT") == "corp-gemini-ai"
    assert captured_env.get("GOOGLE_CLOUD_LOCATION") == "us"


# --------------------------------------------------------------------------- #
# 9. Tool Schemas & Response Normalization
# --------------------------------------------------------------------------- #
def test_format_tools_prompt() -> None:
    tool = ToolDefinition(
        name="read_file",
        description="Read file contents from workspace.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )
    prompt = AntigravityProvider._format_tools_prompt([tool])
    assert "## Available Tools" in prompt
    assert "### `read_file`" in prompt
    assert "Read file contents from workspace." in prompt
    assert "```tool_call" in prompt
    assert "<tool_call>" in prompt
    assert "```json" in prompt
    assert '"path"' in prompt


def test_format_messages_to_prompt_with_tools_and_tool_results() -> None:
    tool = ToolDefinition(
        name="read_file",
        description="Read file contents.",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "Check greeting.txt."},
        {
            "role": "assistant",
            "content": "Inspecting file first.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "read_file",
                        "arguments": {"path": "greeting.txt"},
                    },
                }
            ],
        },
        {"role": "tool", "name": "read_file", "tool_call_id": "call_123", "content": "hello world"},
    ]
    p = AntigravityProvider(config=AntigravityConfig())
    formatted = p._format_messages_to_prompt(messages, tools=[tool])
    assert "[SYSTEM]:\nYou are an agent." in formatted
    assert "## Available Tools" in formatted
    assert "[USER]:\nCheck greeting.txt." in formatted
    assert "[ASSISTANT]:\nInspecting file first." in formatted
    assert "```tool_call" in formatted
    assert '"read_file"' in formatted
    assert "[TOOL RESULT for read_file]:\nhello world" in formatted


def test_generate_cli_injects_tools_into_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    captured_prompt: list[str] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_prompt.append(cmd[2])
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"status": "SUCCESS", "response": "OK"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    tool = ToolDefinition(name="read_file", description="Read a file.")
    messages = [{"role": "user", "content": "Inspect file"}]
    res = p.generate(messages=messages, tools=[tool])
    assert res.text == "OK"
    assert len(captured_prompt) == 1
    assert "## Available Tools" in captured_prompt[0]
    assert "### `read_file`" in captured_prompt[0]
    assert "[USER]:\nInspect file" in captured_prompt[0]


def test_generate_http_includes_tools_and_tool_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(
        api_key="sk-test",
        base_url="https://api.antigravity.google/v1",
        cli_path="/non/existent",
    )
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: None)

    captured_payload: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        ok = True

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {"message": {"role": "assistant", "content": "I will read the file."}}
                ]
            }

    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> FakeResponse:
        if json:
            captured_payload.update(json)
        return FakeResponse()

    monkeypatch.setattr("requests.post", fake_post)
    tool = ToolDefinition(
        name="read_file",
        description="Read file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    res = p.generate(
        messages=[{"role": "user", "content": "Read greeting"}],
        tools=[tool],
        tool_choice=ToolChoice(mode="auto"),
    )
    assert res.text == "I will read the file."
    assert "tools" in captured_payload
    assert len(captured_payload["tools"]) == 1
    assert captured_payload["tools"][0]["function"]["name"] == "read_file"
    assert captured_payload["tool_choice"] == "auto"


def test_normalize_response_markdown_tool_call() -> None:
    p = AntigravityProvider(config=AntigravityConfig())
    raw_text = (
        "Inspecting file now.\n"
        "```tool_call\n"
        '{"name": "read_file", "arguments": {"path": "test.txt"}}\n'
        "```\n"
        "Please stand by."
    )
    res = GenerateResult(text=raw_text, model="gemini-3.8-flash-medium", provider="antigravity", raw={"response": raw_text})
    norm = p.normalize_response(res)
    assert norm.has_tool_calls is True
    assert norm.finish_reason == FinishReason.TOOL_CALLS
    assert len(norm.actions) == 1
    assert norm.actions[0].name == "read_file"
    assert norm.actions[0].arguments == {"path": "test.txt"}
    assert "```tool_call" not in norm.text
    assert "Inspecting file now." in norm.text
    assert "Please stand by." in norm.text


def test_normalize_response_multiple_tool_calls() -> None:
    p = AntigravityProvider(config=AntigravityConfig())
    raw_text = (
        "Reading both files:\n"
        "```tool_call\n"
        '{"name": "read_file", "arguments": {"path": "a.txt"}}\n'
        "```\n"
        "And the second one:\n"
        "```tool_call\n"
        '{"name": "read_file", "arguments": {"path": "b.txt"}}\n'
        "```"
    )
    res = GenerateResult(text=raw_text, model="gemini-3.8-flash-medium", provider="antigravity", raw={})
    norm = p.normalize_response(res)
    assert norm.has_tool_calls is True
    assert len(norm.actions) == 2
    assert norm.actions[0].name == "read_file"
    assert norm.actions[0].arguments == {"path": "a.txt"}
    assert norm.actions[1].name == "read_file"
    assert norm.actions[1].arguments == {"path": "b.txt"}
    assert "```tool_call" not in norm.text
    assert "Reading both files:" in norm.text


def test_normalize_response_json_tool_calls_variant() -> None:
    p = AntigravityProvider(config=AntigravityConfig())
    raw_text = (
        "Executing command:\n"
        "```json\n"
        '{"tool_calls": [{"name": "run_command", "arguments": {"command": "ls"}}]}\n'
        "```"
    )
    res = GenerateResult(text=raw_text, model="gemini-3.8-flash-medium", provider="antigravity", raw={})
    norm = p.normalize_response(res)
    assert norm.has_tool_calls is True
    assert len(norm.actions) == 1
    assert norm.actions[0].name == "run_command"
    assert norm.actions[0].arguments == {"command": "ls"}
    assert "```json" not in norm.text
    assert norm.text == "Executing command:"


def test_normalize_response_xml_tool_call() -> None:
    p = AntigravityProvider(config=AntigravityConfig())
    raw_text = (
        "Running tool now.\n"
        '<tool_call>{"name": "read_file", "arguments": {"path": "a.txt"}}</tool_call>'
    )
    res = GenerateResult(text=raw_text, model="gemini-3.8-flash-medium", provider="antigravity", raw={})
    norm = p.normalize_response(res)
    assert norm.has_tool_calls is True
    assert len(norm.actions) == 1
    assert norm.actions[0].name == "read_file"
    assert norm.actions[0].arguments == {"path": "a.txt"}
    assert "<tool_call>" not in norm.text
    assert norm.text == "Running tool now."


def test_normalize_response_native_raw_tool_calls() -> None:
    p = AntigravityProvider(config=AntigravityConfig())
    raw_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Calling native tool",
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path": "data.json"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }
    res = GenerateResult(text="Calling native tool", model="gemini-3.8-flash-medium", provider="antigravity", raw=raw_payload)
    norm = p.normalize_response(res)
    assert norm.has_tool_calls is True
    assert norm.finish_reason == FinishReason.TOOL_CALLS
    assert len(norm.actions) == 1
    assert norm.actions[0].name == "read_file"
    assert norm.actions[0].arguments == {"path": "data.json"}
    assert norm.actions[0].id == "call_abc123"
    assert norm.text == "Calling native tool"


def test_normalize_response_pure_text_consultant_mode() -> None:
    p = AntigravityProvider(config=AntigravityConfig())
    pure_text = "Saya sarankan kita menggunakan arsitektur microservices untuk project ini."
    res = GenerateResult(text=pure_text, model="gemini-3.8-flash-medium", provider="antigravity", raw={"response": pure_text})
    norm = p.normalize_response(res)
    assert norm.has_tool_calls is False
    assert norm.actions == []
    assert norm.finish_reason == FinishReason.STOP
    assert norm.text == pure_text


def test_generate_cli_stream_json_emits_tool_events(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    captured_events: list[tuple[str, dict[str, Any]]] = []

    def fake_event_sink(ev: str, payload: dict[str, Any]) -> None:
        captured_events.append((ev, payload))

    ndjson_lines = [
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 1,
                "step_type": "tool",
                "tool_name": "view_file",
                "state": "ACTIVE",
                "tool_info": {"parameters": {"AbsolutePath": "/workspace/main.py"}},
            },
        }),
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 1,
                "step_type": "tool",
                "tool_name": "view_file",
                "state": "DONE",
                "tool_info": {"output": "print('hello')"},
            },
        }),
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 2,
                "step_type": "tool",
                "tool_name": "write_to_file",
                "state": "ACTIVE",
                "tool_info": {"parameters": {"AbsolutePath": "/workspace/main.py"}},
            },
        }),
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 2,
                "step_type": "tool",
                "tool_name": "write_to_file",
                "state": "DONE",
                "tool_info": {"output": "ok"},
            },
        }),
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_index": 3,
                "step_type": "agent_response",
                "text_delta": "Task completed successfully.",
            },
        }),
    ]

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="\n".join(ndjson_lines),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    opts = GenerateOptions(extra={"event_sink": fake_event_sink})
    res = p.generate(prompt="Inspect and fix main.py", options=opts)

    assert res.text == "Task completed successfully."
    types = [ev[0] for ev in captured_events]
    assert "tool_called" in types
    assert "tool_completed" in types
    assert "observation_received" in types

    tools_called = [ev[1]["tool"] for ev in captured_events if ev[0] == "tool_called"]
    assert tools_called == ["read_file", "write_file"]
    targets = [ev[1]["target"] for ev in captured_events if ev[0] == "tool_called"]
    assert targets == ["/workspace/main.py", "/workspace/main.py"]

def test_generate_cli_workspace_root_scoping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = AntigravityConfig(cli_path="/bin/agy_mock")
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    workspace = tmp_path / "project_folder"
    workspace.mkdir()

    captured_call = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_call["cmd"] = cmd
        captured_call["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"response": "Scoped execution ok"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    opts = GenerateOptions(extra={"workspace_root": str(workspace)})
    res = p.generate(prompt="Run project task", options=opts)

    assert res.text == "Scoped execution ok"
    assert captured_call["cwd"] == str(workspace.resolve())
    assert "--add-dir" in captured_call["cmd"]
    add_dir_idx = captured_call["cmd"].index("--add-dir")
    assert captured_call["cmd"][add_dir_idx + 1] == str(workspace.resolve())
# --------------------------------------------------------------------------- #
# 13. Idle Activity Timeout & Max Execution Cap in Streaming Loop
# --------------------------------------------------------------------------- #
def test_streaming_idle_timeout_kills_process_when_stalled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jika stream tidak memancarkan data selama melebihi idle_timeout, proses dibunuh dan raise ProviderUnavailableError."""
    import agent_ai.providers.antigravity as agy_mod

    cfg = AntigravityConfig(cli_path="/bin/agy_mock", idle_timeout=10, timeout=120)
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    kill_called = False

    class FakeProc:
        def __init__(self) -> None:
            self.stdout = MagicMock()
            self.stdout.readline.return_value = ""  # Silent stream
            self.stderr = MagicMock()
            self.stderr.read.return_value = ""
            self.returncode = 0

        def poll(self) -> Any:
            return None  # Masih berjalan (stalled/hung)

        def kill(self) -> None:
            nonlocal kill_called
            kill_called = True

        def terminate(self) -> None:
            pass

        def wait(self, timeout: Any = None) -> None:
            pass

    fake_proc = FakeProc()

    # Pastikan subprocess.run is _orig_subprocess_run agar masuk Jalur A
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)
    monkeypatch.setattr(agy_mod, "_orig_subprocess_run", subprocess.run)

    # Simulasikan lonjakan waktu setelah start: panggilan time.time() melampaui idle_timeout (10s)
    current_time = 1000.0
    call_count = 0

    def mock_time() -> float:
        nonlocal current_time, call_count
        call_count += 1
        # Setelah loop dimulai, majukan waktu sebanyak 15 detik
        if call_count > 5:
            current_time += 15.0
        return current_time

    monkeypatch.setattr(agy_mod.time, "time", mock_time)

    sink_events = []
    opts = GenerateOptions(extra={"event_sink": lambda ev, d: sink_events.append((ev, d))})
    with pytest.raises(ProviderUnavailableError) as exc_info:
        p.generate(prompt="Long reasoning task", options=opts)
    assert "idle timeout" in str(exc_info.value).lower()
    assert kill_called is True


def test_streaming_active_stream_resets_idle_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jika stream aktif memancarkan chunk secara berkala melebihi durasi idle_timeout, eksekusi tidak putus."""
    import agent_ai.providers.antigravity as agy_mod

    cfg = AntigravityConfig(cli_path="/bin/agy_mock", idle_timeout=5, timeout=120)
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    # Siapkan baris stream: 3 thought lalu result penutup
    lines = [
        json.dumps({"event": "step_update", "step_update": {"step_type": "thought", "text_delta": "Thinking step 1"}}),
        json.dumps({"event": "step_update", "step_update": {"step_type": "thought", "text_delta": "Thinking step 2"}}),
        json.dumps({"event": "step_update", "step_update": {"step_type": "thought", "text_delta": "Thinking step 3"}}),
        json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": "Finished."}}),
    ]
    line_iter = iter(lines)

    def fake_readline() -> str:
        try:
            return next(line_iter)
        except StopIteration:
            return ""

    class FakeProc:
        def __init__(self) -> None:
            self.stdout = MagicMock()
            self.stdout.readline.side_effect = fake_readline
            self.stderr = MagicMock()
            self.stderr.read.return_value = ""
            self.returncode = 0
            self._poll_count = 0

        def poll(self) -> Any:
            self._poll_count += 1
            return 0 if self._poll_count > 4 else None

        def kill(self) -> None:
            pass

        def terminate(self) -> None:
            pass

        def wait(self, timeout: Any = None) -> None:
            pass

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)
    monkeypatch.setattr(agy_mod, "_orig_subprocess_run", subprocess.run)

    # Simulasikan waktu: setiap kali readline sukses, maju 3 detik.
    # Total waktu akan mencapai 12 detik (> idle_timeout 5 detik), namun karena timer
    # aktivitas di-reset setiap chunk, proses tetap berjalan hingga selesai.
    current_time = 100.0

    def mock_time() -> float:
        return current_time

    def fake_readline_with_clock() -> str:
        nonlocal current_time
        try:
            val = next(line_iter)
            current_time += 3.0  # Maju 3s setiap baris (kurang dari idle_timeout 5s)
            return val
        except StopIteration:
            return ""

    fake_proc.stdout.readline.side_effect = fake_readline_with_clock
    monkeypatch.setattr(agy_mod.time, "time", mock_time)

    sink_events = []
    opts = GenerateOptions(extra={"event_sink": lambda ev, d: sink_events.append((ev, d))})
    res = p.generate(prompt="Active reasoning task", options=opts)
    assert res.text == "Finished."
    assert "Thinking step 1" in (res.reasoning or "")


def test_streaming_max_timeout_kills_process_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jika eksekusi melampaui max_timeout meskipun ada aktivitas berkala, batas absolut memutus proses."""
    import agent_ai.providers.antigravity as agy_mod

    cfg = AntigravityConfig(cli_path="/bin/agy_mock", idle_timeout=60, timeout=120)
    p = AntigravityProvider(config=cfg)
    monkeypatch.setattr(p, "_resolve_cli_path", lambda: "/bin/agy_mock")

    kill_called = False

    class FakeProc:
        def __init__(self) -> None:
            self.stdout = MagicMock()
            # Terus memancarkan aktivitas
            self.stdout.readline.return_value = json.dumps({
                "event": "step_update",
                "step_update": {"step_type": "thought", "text_delta": "Still active..."},
            })
            self.stderr = MagicMock()
            self.stderr.read.return_value = ""
            self.returncode = 0

        def poll(self) -> Any:
            return None

        def kill(self) -> None:
            nonlocal kill_called
            kill_called = True

        def terminate(self) -> None:
            pass

        def wait(self, timeout: Any = None) -> None:
            pass

    fake_proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_proc)
    monkeypatch.setattr(agy_mod, "_orig_subprocess_run", subprocess.run)

    start_sim_time = 1000.0
    current_time = start_sim_time
    call_count = 0

    def mock_time() -> float:
        nonlocal current_time, call_count
        call_count += 1
        # Setelah loop berjalan beberapa iterasi, majukan waktu melampaui max_timeout (600s)
        if call_count > 6:
            current_time = start_sim_time + 700.0
        else:
            current_time += 1.0
        return current_time

    monkeypatch.setattr(agy_mod.time, "time", mock_time)

    sink_events = []
    opts = GenerateOptions(extra={"event_sink": lambda ev, d: sink_events.append((ev, d))})
    with pytest.raises(ProviderUnavailableError) as exc_info:
        p.generate(prompt="Runaway task", options=opts)
    assert "melebihi batas waktu eksekusi maksimum" in str(exc_info.value).lower()
    assert kill_called is True
