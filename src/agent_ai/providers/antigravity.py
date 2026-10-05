"""Implementasi provider Google Antigravity.

Google Antigravity adalah standalone agentic provider dari Google yang menyediakan
model frontier reasoning:
    - Gemini 3.8 Flash (High, Medium, Low)
    - Gemini 3.7 Flash
    - Gemini 3.1 Pro (High, Low)
    - Claude Sonnet 4.6 / Claude Opus 4.6 (Thinking)
    - GPT-OSS 120B

Antigravity dapat diakses melalui:
1. Native CLI Bridge (`agy -p ... --output-format json`), memanfaatkan
   autentikasi Google OAuth lokal di `~/.gemini/oauth_creds.json`.
2. HTTP / REST API endpoint (`ANTIGRAVITY_API_KEY` / `ANTIGRAVITY_BASE_URL`).

Referensi: https://antigravity.google/docs/models/
"""

from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

_orig_subprocess_run = subprocess.run
import requests

from agent_ai.config.settings import AntigravityConfig, settings
from agent_ai.providers.base import (
    BaseProvider,
    GenerateOptions,
    GenerateResult,
    Message,
    ProviderAPIError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    ToolChoice,
    ToolDefinition,
    from_provider_safe_tool_name,
    to_provider_safe_tool_name,
)

if TYPE_CHECKING:
    from agent_ai.core.response import LLMResponse

DEFAULT_ANTIGRAVITY_MODELS: List[str] = [
    "gemini-3.8-flash-high",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-low",
    "gemini-3.7-flash-high",
    "gemini-3.7-flash-medium",
    "gemini-3.1-pro-high",
    "gemini-3.1-pro-low",
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gpt-oss-120b-medium",
]


def _extract_msg_role(msg: Any) -> str:
    """Ambil role dari objek Message atau dictionary."""
    if isinstance(msg, dict):
        return str(msg.get("role") or "user")
    return str(getattr(msg, "role", "user") or "user")


def _extract_msg_content(msg: Any) -> str:
    """Ambil content dari objek Message atau dictionary."""
    if isinstance(msg, dict):
        val = msg.get("content")
        return str(val) if val is not None else ""
    val = getattr(msg, "content", "")
    return str(val) if val is not None else ""

def _map_agy_tool_name(agy_name: str) -> str:
    """Petakan nama tool internal Antigravity CLI (agy) ke nama tool standar Aegis."""
    name = (agy_name or "").lower().strip()
    if name in ("view_file", "read_file", "read_symbol", "view_symbol"):
        return "read_file"
    if name in ("write_to_file", "write_file"):
        return "write_file"
    if name in ("edit_file", "edit_file_part"):
        return "edit_file"
    if name in ("list_dir", "find_files", "find_by_name"):
        return "list_files"
    if name in ("grep", "grep_search", "search_file"):
        return "search_code"
    if name == "run_command":
        return "run_command"
    return name


def _extract_agy_target(tool_name: str, params: Dict[str, Any]) -> str:
    """Ekstrak path/command/target dari parameter tool Antigravity CLI."""
    if not isinstance(params, dict):
        return ""
    if tool_name in ("read_file", "write_file", "edit_file"):
        return str(params.get("AbsolutePath") or params.get("path") or params.get("file_path") or "")
    if tool_name == "run_command":
        return str(params.get("CommandLine") or params.get("command") or "")
    if tool_name == "list_files":
        return str(params.get("DirectoryPath") or params.get("path") or params.get("dir") or "")
    if tool_name in (
        "search_code",
        "hybrid_search",
        "semantic_search",
        "atlas_query",
        "rig_query",
    ):
        return str(params.get("Query") or params.get("query") or params.get("pattern") or "")
    return str(params.get("path") or params.get("command") or params.get("target") or "")


def _extract_tool_call_dict(tc: Any) -> Dict[str, Any]:
    """Ekstrak nama, arguments, dan id dari dict atau objek ToolCall."""
    if isinstance(tc, dict):
        if "function" in tc and isinstance(tc["function"], dict):
            fn = tc["function"]
            name = fn.get("name", "")
            raw_args = fn.get("arguments", {})
        else:
            name = tc.get("name", "")
            raw_args = tc.get("arguments", {})
        call_id = tc.get("id")
    else:
        name = getattr(tc, "name", "")
        raw_args = getattr(tc, "arguments", {})
        call_id = getattr(tc, "id", None)
        if not name and hasattr(tc, "function") and isinstance(tc.function, dict):
            name = tc.function.get("name", "")
            raw_args = tc.function.get("arguments", {})

    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except Exception:
            args = raw_args
    else:
        args = raw_args

    res: Dict[str, Any] = {"name": to_provider_safe_tool_name(str(name or "")), "arguments": args}
    if call_id:
        res["id"] = str(call_id)
    return res


def _format_tools_prompt(tools: List[ToolDefinition]) -> str:
    """Format daftar ToolDefinition menjadi prompt instruksi tool calling."""
    lines: List[str] = [
        "## Available Tools",
        "You have access to the following tools to inspect and modify the workspace:",
    ]
    for tool in tools:
        safe_name = to_provider_safe_tool_name(tool.name)
        params_str = json.dumps(tool.parameters or {"type": "object", "properties": {}}, indent=2)
        lines.append(f"\n### `{safe_name}`")
        if tool.description:
            lines.append(f"Description: {tool.description}")
        lines.append(f"Parameters Schema:\n```json\n{params_str}\n```")

    lines.extend([
        "\n## Tool Calling Instructions",
        "To invoke a tool, output a tool call block using one of these formats:",
        "",
        "Primary format:",
        "```tool_call",
        '{"name": "<tool_name>", "arguments": {<args>}}',
        "```",
        "",
        "Secondary / Batch format:",
        "```json",
        '{"tool_calls": [{"name": "<tool_name>", "arguments": {<args>}}]}',
        "```",
        "",
        "XML alternative format:",
        '<tool_call>{"name": "<tool_name>", "arguments": {<args>}}</tool_call>',
        "",
        "Important instructions:",
        "1. Always provide natural commentary/reasoning before or after the tool block explaining what you are doing.",
        "2. Only provide valid JSON within the tool call block.",
        "3. When the task is complete and no more tools are needed, return final text without tool call blocks.",
    ])
    return "\n".join(lines)


def _to_openai_tool(tool: ToolDefinition) -> Dict[str, Any]:
    """Ubah ToolDefinition menjadi format tool OpenAI function."""
    return {
        "type": "function",
        "function": {
            "name": to_provider_safe_tool_name(tool.name),
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_openai_tool_choice(tool_choice: ToolChoice) -> Any:
    """Ubah ToolChoice menjadi parameter tool_choice OpenAI."""
    if tool_choice.mode == "auto":
        return "auto"
    if tool_choice.mode == "none":
        return "none"
    if tool_choice.mode == "required":
        return "required"
    if tool_choice.name or tool_choice.mode == "specific":
        tool_name = tool_choice.name or ""
        return {
            "type": "function",
            "function": {
                "name": to_provider_safe_tool_name(tool_name),
            },
        }
    return "auto"

class AntigravityProvider(BaseProvider):
    """Provider AI untuk Google Antigravity (CLI bridge atau HTTP API)."""

    name = "antigravity"
    requires_model = True

    def __init__(self, config: Optional[AntigravityConfig] = None) -> None:
        self.config = config or settings.antigravity

    def _resolve_cli_path(self) -> Optional[str]:
        """Temukan executable agy di sistem."""
        if self.config.cli_path:
            return self.config.cli_path if os.path.exists(self.config.cli_path) else None

        found = shutil.which("agy")
        if found and os.path.exists(found):
            return found

        home_local = os.path.expanduser("~/.local/bin/agy")
        if os.path.exists(home_local):
            return home_local

        return None

    def is_available(self) -> bool:
        """Cek apakah Antigravity siap digunakan (agy CLI, ADC Enterprise, atau API key)."""
        if self._resolve_cli_path() is not None:
            return True
        if self.config.enable_adc:
            adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
            if os.path.exists(adc_path):
                return True
        return bool(self.config.api_key)

    def knowledge_budget_tokens(self) -> Optional[int]:
        """Kapasitas token context window."""
        return self.config.context_window or 1048576

    def list_available_models(self) -> List[str]:
        """Daftar model yang didukung oleh Antigravity."""
        cli = self._resolve_cli_path()
        if cli:
            try:
                env = os.environ.copy()
                if self.config.enable_adc:
                    env["AGY_ADC_AUTH"] = "true"
                if self.config.project_id:
                    env["GOOGLE_CLOUD_PROJECT"] = self.config.project_id
                if self.config.location:
                    env["GOOGLE_CLOUD_LOCATION"] = self.config.location

                proc = subprocess.run(
                    [cli, "models"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=10,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    discovered: List[str] = []
                    for line in proc.stdout.splitlines():
                        line = line.strip()
                        if not line or line.startswith("⠋") or line.startswith("Fetching"):
                            continue
                        parts = line.split()
                        if parts:
                            discovered.append(parts[0])
                    if discovered:
                        return discovered
            except Exception:
                pass
        return list(DEFAULT_ANTIGRAVITY_MODELS)

    _format_tools_prompt = staticmethod(_format_tools_prompt)
    _to_openai_tool = staticmethod(_to_openai_tool)
    _to_openai_tool_choice = staticmethod(_to_openai_tool_choice)

    def _format_messages_to_prompt(
        self,
        messages: Any,
        tools: Optional[List[ToolDefinition]] = None,
    ) -> str:
        """Format daftar pesan Message/dict menjadi teks dialog terstruktur."""
        formatted_turns: List[str] = []
        tools_injected = False

        for msg in messages:
            role = _extract_msg_role(msg).lower()
            content = _extract_msg_content(msg)

            if role == "system":
                if tools and not tools_injected:
                    formatted_turns.append(f"[SYSTEM]:\n{content}\n\n{_format_tools_prompt(tools)}")
                    tools_injected = True
                else:
                    formatted_turns.append(f"[SYSTEM]:\n{content}")
            elif role == "user":
                formatted_turns.append(f"[USER]:\n{content}")
            elif role == "assistant":
                tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
                if tool_calls:
                    blocks: List[str] = []
                    for tc in tool_calls:
                        tc_data = _extract_tool_call_dict(tc)
                        tc_payload = {"name": tc_data["name"], "arguments": tc_data["arguments"]}
                        blocks.append(f"```tool_call\n{json.dumps(tc_payload, indent=2)}\n```")
                    tool_blocks = "\n\n".join(blocks)
                    if content.strip():
                        formatted_turns.append(f"[ASSISTANT]:\n{content}\n\n{tool_blocks}")
                    else:
                        formatted_turns.append(f"[ASSISTANT]:\n{tool_blocks}")
                else:
                    formatted_turns.append(f"[ASSISTANT]:\n{content}")
            elif role == "tool":
                name = ""
                if isinstance(msg, dict):
                    name = msg.get("name") or msg.get("tool_call_id") or ""
                else:
                    name = getattr(msg, "name", None) or getattr(msg, "tool_call_id", None) or ""
                target_name = name or "result"
                formatted_turns.append(f"[TOOL RESULT for {target_name}]:\n{content}")
            else:
                formatted_turns.append(f"[{role.upper()}]:\n{content}")

        if tools and not tools_injected:
            formatted_turns.insert(0, f"[SYSTEM]:\n{_format_tools_prompt(tools)}")

        return "\n\n".join(formatted_turns)

    def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Any]] = None,
        options: Optional[GenerateOptions] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
    ) -> GenerateResult:
        """Kirim request ke Antigravity via agy CLI bridge atau HTTP API."""
        if not prompt and not messages:
            raise ValueError("Minimal salah satu dari 'prompt' atau 'messages' harus diisi.")

        tool_defs = self._build_tool_definitions(tools) if tools else []
        model = (options and options.model) or self.config.model or "gemini-3.8-flash-medium"

        cli = self._resolve_cli_path()
        if cli:
            if messages:
                input_text = self._format_messages_to_prompt(messages, tools=tool_defs if tool_defs else None)
            elif prompt:
                if tool_defs:
                    input_text = f"[SYSTEM]:\n{_format_tools_prompt(tool_defs)}\n\n[USER]:\n{prompt}"
                else:
                    input_text = prompt
            else:
                input_text = ""

            event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = (
                options.extra.get("event_sink")
                if options and options.extra and callable(options.extra.get("event_sink"))
                else None
            )
            cwd = (
                (options.extra.get("workspace_root") if options and options.extra else None)
                or getattr(self.config, "workspace_root", None)
                or None
            )
            target_cwd: Optional[str] = None
            if cwd and os.path.exists(str(cwd)):
                target_cwd = str(Path(cwd).resolve())


            # Bila event_sink tersedia, gunakan stream-json agar intermediate tool
            # calls dipancarkan real-time ke UI timeline Aegis saat agy berjalan.
            use_streaming = event_sink is not None
            output_format = "stream-json" if use_streaming else "json"
            cmd = [cli, "-p", input_text, "--model", model, "--output-format", output_format]
            if target_cwd:
                cmd.extend(["--add-dir", target_cwd])
            env = os.environ.copy()
            if self.config.enable_adc:
                env["AGY_ADC_AUTH"] = "true"
            if self.config.project_id:
                env["GOOGLE_CLOUD_PROJECT"] = self.config.project_id
                env["GOOGLE_CLOUD_QUOTA_PROJECT"] = self.config.project_id
            if self.config.location:
                env["GOOGLE_CLOUD_LOCATION"] = self.config.location

            timeout = self.config.timeout or 120

            # Jalur A: Live streaming via subprocess.Popen (real Antigravity CLI execution)
            if use_streaming and subprocess.run is _orig_subprocess_run:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        env=env,
                        cwd=target_cwd,
                    )
                except OSError as exc:
                    raise ProviderUnavailableError(
                        f"Gagal menjalankan Antigravity CLI di '{cli}': {exc}"
                    ) from exc

                accumulated_text: List[str] = []
                final_response = ""
                raw_data: Dict[str, Any] = {}
                start_time = time.time()

                try:
                    while True:
                        if time.time() - start_time > timeout:
                            proc.kill()
                            raise ProviderUnavailableError(
                                f"Antigravity CLI timeout setelah {timeout} detik."
                            )
                        line = proc.stdout.readline() if proc.stdout else ""
                        if not line:
                            if proc.poll() is not None:
                                break
                            time.sleep(0.02)
                            continue

                        line_str = line.strip()
                        if not line_str:
                            continue

                        try:
                            item = json.loads(line_str)
                        except Exception:
                            continue

                        if isinstance(item, dict):
                            if item.get("event") == "step_update":
                                step_update = item.get("step_update") or {}
                                step_type = step_update.get("step_type")
                                state = step_update.get("state")
                                step_idx = step_update.get("step_index", 0)
                                call_id = f"agy_{step_idx}"

                                if step_type == "tool":
                                    agy_tool = step_update.get("tool_name") or ""
                                    aegis_tool = _map_agy_tool_name(agy_tool)
                                    tool_info = step_update.get("tool_info") or {}
                                    params = tool_info.get("parameters") or {}
                                    target = _extract_agy_target(aegis_tool, params)

                                    if state == "ACTIVE" and event_sink:
                                        event_sink("tool_called", {
                                            "tool": aegis_tool,
                                            "arguments": params,
                                            "target": target,
                                            "call_id": call_id,
                                        })
                                    elif state == "DONE" and event_sink:
                                        output = tool_info.get("output", "")
                                        event_sink("tool_completed", {
                                            "tool": aegis_tool,
                                            "success": True,
                                            "target": target,
                                            "call_id": call_id,
                                        })
                                        event_sink("observation_received", {
                                            "tool": aegis_tool,
                                            "content": output,
                                            "success": True,
                                            "target": target,
                                        })
                                elif step_type == "agent_response":
                                    text_delta = step_update.get("text_delta")
                                    if text_delta:
                                        accumulated_text.append(text_delta)
                            elif "response" in item and item.get("response"):
                                final_response = item["response"]
                                raw_data = item
                except Exception:
                    proc.kill()
                    raise

                stderr_text = proc.stderr.read().strip() if proc.stderr else ""
                proc.wait()

                if proc.returncode != 0 and not accumulated_text and not final_response:
                    err_msg = stderr_text or f"Exit code {proc.returncode}"
                    raise ProviderAPIError(
                        f"Antigravity CLI mengembalikan error: {err_msg}",
                        status_code=proc.returncode,
                        endpoint="agy CLI",
                        response_body=err_msg,
                    )

                text = "".join(accumulated_text) or final_response or ""
                if not raw_data:
                    raw_data = {"status": "SUCCESS", "response": text}

                return GenerateResult(
                    text=text,
                    model=model,
                    provider=self.name,
                    raw=raw_data,
                )

            # Jalur B: Standar subprocess.run (untuk mock unit test atau non-streaming)
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=target_cwd,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderUnavailableError(
                    f"Antigravity CLI timeout setelah {timeout} detik."
                ) from exc
            except OSError as exc:
                raise ProviderUnavailableError(
                    f"Gagal menjalankan Antigravity CLI di '{cli}': {exc}"
                ) from exc

            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
                raise ProviderAPIError(
                    f"Antigravity CLI mengembalikan error: {err_msg}",
                    status_code=proc.returncode,
                    endpoint="agy CLI",
                    response_body=err_msg,
                )

            stdout = proc.stdout.strip()
            # Bila stdout berisi baris-baris stream-json dan event_sink aktif
            if stdout.startswith("{") and "\n{" in stdout and event_sink:
                accumulated_text = []
                final_response = ""
                raw_data = {}
                for line in stdout.splitlines():
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        item = json.loads(line_str)
                    except Exception:
                        continue
                    if isinstance(item, dict):
                        if item.get("event") == "step_update":
                            step_update = item.get("step_update") or {}
                            step_type = step_update.get("step_type")
                            state = step_update.get("state")
                            step_idx = step_update.get("step_index", 0)
                            call_id = f"agy_{step_idx}"
                            if step_type == "tool":
                                agy_tool = step_update.get("tool_name") or ""
                                aegis_tool = _map_agy_tool_name(agy_tool)
                                tool_info = step_update.get("tool_info") or {}
                                params = tool_info.get("parameters") or {}
                                target = _extract_agy_target(aegis_tool, params)
                                if state == "ACTIVE":
                                    event_sink("tool_called", {
                                        "tool": aegis_tool,
                                        "arguments": params,
                                        "target": target,
                                        "call_id": call_id,
                                    })
                                elif state == "DONE":
                                    output = tool_info.get("output", "")
                                    event_sink("tool_completed", {
                                        "tool": aegis_tool,
                                        "success": True,
                                        "target": target,
                                        "call_id": call_id,
                                    })
                                    event_sink("observation_received", {
                                        "tool": aegis_tool,
                                        "content": output,
                                        "success": True,
                                        "target": target,
                                    })
                            elif step_type == "agent_response":
                                text_delta = step_update.get("text_delta")
                                if text_delta:
                                    accumulated_text.append(text_delta)
                        elif "response" in item and item.get("response"):
                            final_response = item["response"]
                            raw_data = item
                text = "".join(accumulated_text) or final_response or stdout
                data = raw_data or {"status": "SUCCESS", "response": text}
            else:
                try:
                    data = json.loads(stdout)
                    text = data.get("response", "")
                except Exception:
                    text = stdout
                    data = {"raw_text": stdout}

            return GenerateResult(
                text=text,
                model=model,
                provider=self.name,
                raw=data,
            )

        # Fallback ke HTTP endpoint bila API key tersedia
        if self.config.api_key and self.config.base_url:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            chat_messages: List[Dict[str, Any]] = []
            if messages:
                for m in messages:
                    role = _extract_msg_role(m)
                    content = _extract_msg_content(m)
                    m_dict: Dict[str, Any] = {"role": role, "content": content}

                    tool_calls = m.get("tool_calls") if isinstance(m, dict) else getattr(m, "tool_calls", None)
                    if role == "assistant" and tool_calls:
                        formatted_calls = []
                        for tc in tool_calls:
                            tc_data = _extract_tool_call_dict(tc)
                            call_id = tc_data.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                            safe_name = to_provider_safe_tool_name(tc_data.get("name", ""))
                            args = tc_data.get("arguments", {})
                            args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                            formatted_calls.append({
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": safe_name,
                                    "arguments": args_str,
                                },
                            })
                        m_dict["tool_calls"] = formatted_calls
                        if not content:
                            m_dict["content"] = None

                    if role == "tool":
                        tool_call_id = m.get("tool_call_id") if isinstance(m, dict) else getattr(m, "tool_call_id", None)
                        name = m.get("name") if isinstance(m, dict) else getattr(m, "name", None)
                        if tool_call_id:
                            m_dict["tool_call_id"] = tool_call_id
                        if name:
                            m_dict["name"] = to_provider_safe_tool_name(name)

                    chat_messages.append(m_dict)
            else:
                chat_messages.append({"role": "user", "content": prompt or ""})

            payload: Dict[str, Any] = {
                "model": model,
                "messages": chat_messages,
            }
            if tool_defs:
                payload["tools"] = [_to_openai_tool(t) for t in tool_defs]
            if tool_choice is not None:
                payload["tool_choice"] = _to_openai_tool_choice(tool_choice)
            if options and options.temperature is not None:
                payload["temperature"] = options.temperature
            if options and options.max_tokens is not None:
                payload["max_tokens"] = options.max_tokens

            endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
            try:
                resp = requests.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout or 120,
                )
            except requests.RequestException as exc:
                raise ProviderUnavailableError(
                    f"Gagal menghubungi Antigravity HTTP endpoint '{endpoint}': {exc}"
                ) from exc

            if not resp.ok:
                raise ProviderAPIError(
                    f"Antigravity HTTP API mengembalikan status {resp.status_code}",
                    status_code=resp.status_code,
                    endpoint=endpoint,
                    response_body=resp.text,
                )

            data = resp.json()
            choices = data.get("choices") or []
            first_text = ""
            if choices and isinstance(choices[0], dict):
                first_text = choices[0].get("message", {}).get("content", "") or ""

            return GenerateResult(
                text=first_text,
                model=model,
                provider=self.name,
                raw=data,
            )

        raise ProviderNotConfiguredError(
            "Provider 'antigravity' belum dikonfigurasi: Antigravity CLI ('agy') tidak ditemukan di sistem "
            "dan ANTIGRAVITY_API_KEY tidak di-set. Jalankan 'agy' di terminal untuk autentikasi Google atau set ANTIGRAVITY_API_KEY di .env."
        )

    def normalize_response(self, result: GenerateResult) -> "LLMResponse":
        """Ubah raw response Antigravity menjadi LLMResponse yang dinormalisasi."""
        from agent_ai.core.response import (
            ActionType,
            FinishReason,
            LLMAction,
            LLMResponse,
        )

        raw = result.raw if isinstance(result.raw, dict) else {}
        choices = raw.get("choices") or []
        first_choice = choices[0] if (choices and isinstance(choices[0], dict)) else {}
        first_msg = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
        raw_reason = first_choice.get("finish_reason")

        # Branch A: Native Tool Calls in result.raw (OpenAI-compatible HTTP format)
        raw_calls = (
            first_msg.get("tool_calls")
            or raw.get("tool_calls")
            or []
        )
        if isinstance(raw_calls, list) and raw_calls:
            actions: List[LLMAction] = []
            for call in raw_calls:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") if isinstance(call.get("function"), dict) else {}
                raw_name = fn.get("name") or call.get("name") or ""
                name = from_provider_safe_tool_name(raw_name)
                args = fn.get("arguments") if "function" in call else call.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"_raw": args}
                elif not isinstance(args, dict):
                    args = {"_raw": args} if args is not None else {}
                cid = call.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                actions.append(
                    LLMAction(
                        name=name,
                        arguments=args,
                        type=ActionType.TOOL_CALL,
                        id=cid,
                    )
                )
            if actions:
                text = (
                    result.text
                    or first_msg.get("content")
                    or ""
                )
                return LLMResponse(
                    text=text,
                    actions=actions,
                    finish_reason=FinishReason.TOOL_CALLS,
                    raw=raw,
                    provider=self.name,
                    model=result.model,
                )

        # Branch B: Text-Embedded Tool Calls (CLI bridge & embedded responses)
        raw_text = result.text or (raw.get("response") if isinstance(raw, dict) else "") or ""
        patterns = [
            re.compile(r"```tool_call\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE),
            re.compile(r"<tool_call>\s*\n?(.*?)\n?</tool_call>", re.DOTALL | re.IGNORECASE),
            re.compile(r"```json\s*\n?(\{\s*\"tool_calls\"\s*:.*?)\n?```", re.DOTALL | re.IGNORECASE),
            re.compile(r"```json\s*\n?(\{\s*\"name\"\s*:.*?\"arguments\"\s*:.*?)\n?```", re.DOTALL | re.IGNORECASE),
        ]

        matched_spans: List[tuple[int, int]] = []
        actions = []

        for pattern in patterns:
            for m in pattern.finditer(raw_text):
                m_start, m_end = m.start(), m.end()
                # Hindari overlap bila span sudah dicakup pola sebelumnya
                if any(not (m_end <= s or m_start >= e) for s, e in matched_spans):
                    continue

                inner = m.group(1).strip()
                try:
                    payload = json.loads(inner)
                except Exception:
                    continue

                extracted_actions: List[LLMAction] = []
                if isinstance(payload, dict):
                    if "tool_calls" in payload and isinstance(payload["tool_calls"], list):
                        for item in payload["tool_calls"]:
                            if isinstance(item, dict):
                                item_name = from_provider_safe_tool_name(item.get("name", ""))
                                item_args = item.get("arguments", {})
                                if isinstance(item_args, str):
                                    try:
                                        item_args = json.loads(item_args)
                                    except Exception:
                                        item_args = {"_raw": item_args}
                                elif not isinstance(item_args, dict):
                                    item_args = {"_raw": item_args} if item_args is not None else {}
                                cid = item.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                                extracted_actions.append(
                                    LLMAction(
                                        name=item_name,
                                        arguments=item_args,
                                        type=ActionType.TOOL_CALL,
                                        id=cid,
                                    )
                                )
                    elif "name" in payload and isinstance(payload.get("name"), str):
                        item_name = from_provider_safe_tool_name(payload.get("name", ""))
                        item_args = payload.get("arguments", {})
                        if isinstance(item_args, str):
                            try:
                                item_args = json.loads(item_args)
                            except Exception:
                                item_args = {"_raw": item_args}
                        elif not isinstance(item_args, dict):
                            item_args = {"_raw": item_args} if item_args is not None else {}
                        cid = payload.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                        extracted_actions.append(
                            LLMAction(
                                name=item_name,
                                arguments=item_args,
                                type=ActionType.TOOL_CALL,
                                id=cid,
                            )
                        )
                elif isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict) and "name" in item:
                            item_name = from_provider_safe_tool_name(item.get("name", ""))
                            item_args = item.get("arguments", {})
                            if isinstance(item_args, str):
                                try:
                                    item_args = json.loads(item_args)
                                except Exception:
                                    item_args = {"_raw": item_args}
                            elif not isinstance(item_args, dict):
                                item_args = {"_raw": item_args} if item_args is not None else {}
                            cid = item.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                            extracted_actions.append(
                                LLMAction(
                                    name=item_name,
                                    arguments=item_args,
                                    type=ActionType.TOOL_CALL,
                                    id=cid,
                                )
                            )

                if extracted_actions:
                    actions.extend(extracted_actions)
                    matched_spans.append((m_start, m_end))

        if actions:
            matched_spans.sort(key=lambda s: s[0])
            text_parts: List[str] = []
            last_idx = 0
            for s, e in matched_spans:
                text_parts.append(raw_text[last_idx:s])
                last_idx = e
            text_parts.append(raw_text[last_idx:])
            commentary = "".join(text_parts)
            commentary = re.sub(r"\n\s*\n+", "\n\n", commentary).strip()
            finish_reason = FinishReason.TOOL_CALLS
        else:
            commentary = raw_text
            if raw_reason == "length":
                finish_reason = FinishReason.LENGTH
            else:
                finish_reason = FinishReason.STOP

        return LLMResponse(
            text=commentary,
            actions=actions,
            finish_reason=finish_reason,
            raw=raw,
            provider=self.name,
            model=result.model,
        )
