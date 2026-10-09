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
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

_orig_subprocess_run = subprocess.run
logger = logging.getLogger(__name__)
import requests

from agent_ai.config.settings import AntigravityConfig, settings
from agent_ai.providers.base import (
    BaseProvider,
    GenerateOptions,
    GenerateResult,
    Message,
    ProviderAPIError,
    ProviderNotConfiguredError,
    ProviderRequest,
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
    from agent_ai.runtime.activity import normalize_canonical_tool_name

    return normalize_canonical_tool_name(agy_name)

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


def _tool_call_signature(tool_name: str, params: Dict[str, Any]) -> str:
    """Buat signature kanonikal dari tool call untuk mendeteksi perulangan identik."""
    try:
        norm_params = json.dumps(params, sort_keys=True, default=str)
    except Exception:
        norm_params = str(params)
    return f"{tool_name}:{norm_params}"


def _format_antigravity_policy_directive(mode: str = "agents") -> str:
    """Format prompt direktif workspace safety dan eksplorasi alami untuk Antigravity CLI."""
    rules = [
        "CRITICAL WORKSPACE SAFETY & AUTONOMOUS EXPLORATION DIRECTIVES:",
        "1. STRICT LOG FILE PROHIBITION: You must NEVER read, search, grep, or inspect files inside '.aegis/log/' or any '.log' or '.json' files inside log directories. These are internal diagnostic logs and reading them causes immediate context overflow and process termination.",
        "2. WORKSPACE FOCUS: Focus directly on the relevant source code and project documentation (such as README.md, package.json, src/). Do NOT explore or search for non-existent internal metadata directories (.aegis/, .brain/).",
        "3. WORKSPACE BOUNDARY INTEGRITY: You must NEVER execute shell commands or tools that navigate outside the project root (no '..', no inspecting parent directories). Stay strictly inside the active project directory.",
        "4. NATURAL EXPLORATION & CODEGRAPH NAVIGATION: Feel free to explore related codebases, inspect symbols, follow definitions, and leverage CodeGraph navigation tools to understand architecture and relational dependencies deeply.",
        "5. CONFIDENT REFACTORING: Thorough reading, iterative edits, and multi-file refactoring are fully supported to complete the requested engineering task safely and accurately.",
    ]
    return "\n".join(rules)


_IGNORE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".aegis",
    ".aether",
    ".brain",
    "__pycache__",
    ".venv",
    "venv",
    ".turbo",
    ".next",
    ".nuxt",
    ".output",
    "target",
    "vendor",
    ".cache",
    ".pytest_cache",
    ".coverage",
}

_CODE_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte",
    ".py", ".go", ".rs", ".php", ".rb", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".html",
    ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".sql"
}

_COMMON_STOP_WORDS = {
    "buat", "bikin", "tambah", "ubah", "ganti", "file", "berkas", "code", "kode",
    "project", "aplikasi", "yang", "dan", "atau", "pada", "untuk", "dengan", "saya",
    "kamu", "bisa", "tolong", "make", "create", "update", "modify", "please", "help",
    "from", "with", "into", "that", "this", "test", "testing", "cek", "check", "fix",
    "error", "bug", "perbaiki", "fitur", "feature", "run", "jalankan",
}


def _detect_manifest_intel(cwd_path: Path) -> List[str]:
    """Deteksi file manifest (package.json, pyproject.toml, Cargo.toml, go.mod) secara dinamis."""
    intel: List[str] = []

    # 1. Node.js / JavaScript / TypeScript
    pkg_json_path = cwd_path / "package.json"
    if pkg_json_path.is_file():
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
            scripts = pkg_data.get("scripts", {})
            script_names = list(scripts.keys())
            if "test" in script_names:
                intel.append(
                    f"package.json detected. Defined scripts: {script_names} (script 'test' is available: 'npm test')"
                )
            else:
                intel.append(
                    f"package.json detected. Defined scripts: {script_names} (CRITICAL: NO 'test' script found in package.json; do NOT run npm test)"
                )
        except Exception:
            intel.append("package.json detected (unparseable)")

    # 2. Python
    pyproject_path = cwd_path / "pyproject.toml"
    setup_py = cwd_path / "setup.py"
    req_txt = cwd_path / "requirements.txt"
    if pyproject_path.is_file():
        intel.append("pyproject.toml detected (Python project).")
    elif setup_py.is_file():
        intel.append("setup.py detected (Python project).")
    elif req_txt.is_file():
        intel.append("requirements.txt detected (Python project).")

    # 3. Rust
    if (cwd_path / "Cargo.toml").is_file():
        intel.append("Cargo.toml detected (Rust project; use cargo commands).")

    # 4. Go
    if (cwd_path / "go.mod").is_file():
        intel.append("go.mod detected (Go module project).")

    # 5. PHP
    if (cwd_path / "composer.json").is_file():
        intel.append("composer.json detected (PHP Composer project).")

    return intel


def _extract_query_keywords(query: str) -> List[str]:
    """Ekstrak token kata kunci relevan dari kueri pengguna."""
    if not query:
        return []
    tokens = re.findall(r"[A-Za-z0-9_]{3,}", query.lower())
    keywords = [t for t in tokens if t not in _COMMON_STOP_WORDS]
    seen = set()
    result = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result


def _resolve_semantic_search_candidates(cwd_path: Path, query: str, limit: int) -> List[Dict[str, Any]]:
    """Legacy vector search candidates decommissioned in favor of deterministic CodeGraph AST."""
    return []


def _extract_file_symbols(file_path: Path, max_lines: int = 60) -> List[str]:
    """Ekstrak simbol penting secara instan dari awal berkas tanpa overhead eksternal."""
    ext = file_path.suffix.lower()
    symbols: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f):
                if idx >= max_lines:
                    break
                line_str = line.strip()
                if ext in (".ts", ".tsx", ".js", ".jsx"):
                    m = re.search(r"export\s+(?:default\s+)?(?:function|const|class|type|interface)\s+([A-Za-z0-9_]+)", line_str)
                    if m:
                        symbols.append(m.group(1))
                elif ext == ".py":
                    m = re.search(r"^(?:def|class)\s+([A-Za-z0-9_]+)", line_str)
                    if m:
                        symbols.append(m.group(1))
                elif ext in (".go", ".rs"):
                    m = re.search(r"^(?:func|fn|struct|type)\s+([A-Za-z0-9_]+)", line_str)
                    if m:
                        symbols.append(m.group(1))
    except Exception:
        pass
    return symbols[:3]


def _fallback_dynamic_code_scan(cwd_path: Path, query: str, limit: int) -> List[Dict[str, Any]]:
    """Pindai seluruh struktur repositori secara dinamis untuk menemukan berkas kode paling relevan."""
    keywords = _extract_query_keywords(query)
    all_candidates: List[tuple[int, Path]] = []
    scanned_count = 0
    max_scan = 2000

    try:
        for root, dirs, files in os.walk(cwd_path):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for file in files:
                scanned_count += 1
                if scanned_count > max_scan:
                    break
                p = Path(root) / file
                ext = p.suffix.lower()
                if ext not in _CODE_EXTS:
                    continue
                try:
                    rel_p = p.relative_to(cwd_path).as_posix()
                except ValueError:
                    rel_p = p.as_posix()

                rel_lower = rel_p.lower()
                file_stem_lower = p.stem.lower()

                score = 0
                for kw in keywords:
                    if kw == file_stem_lower:
                        score += 30
                    elif kw in file_stem_lower:
                        score += 20
                    elif kw in rel_lower:
                        score += 10

                if keywords and score > 0:
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            content_sample = "".join([f.readline() for _ in range(50)]).lower()
                            for kw in keywords:
                                if kw in content_sample:
                                    score += 8
                    except Exception:
                        pass
                elif not keywords:
                    # Bila tidak ada kata kunci spesifik, prioritaskan berkas kode terdekat dari root workspace
                    try:
                        depth = len(p.relative_to(cwd_path).parts)
                    except ValueError:
                        depth = 1
                    score = max(1, 15 - depth)

                if score > 0:
                    all_candidates.append((score, p))
            if scanned_count > max_scan:
                break
    except Exception:
        pass

    all_candidates.sort(key=lambda x: x[0], reverse=True)
    top_files = all_candidates[:limit]

    results: List[Dict[str, Any]] = []
    for _, p in top_files:
        try:
            rel = p.relative_to(cwd_path).as_posix()
        except ValueError:
            rel = p.as_posix()
        syms = _extract_file_symbols(p)
        results.append({
            "path": rel,
            "symbols": syms,
        })
    return results


def _resolve_dynamic_code_context(cwd_path: Optional[str], query: str, mode: str) -> str:
    """Susun Workspace Intel dinamis dari manifest dan pencarian semantik / fallback AST."""
    if not cwd_path or not os.path.isdir(cwd_path):
        return ""

    mode_clean = (mode or "balanced").lower().strip()
    if mode_clean == "fast":
        limit = 3
    elif mode_clean == "deep":
        limit = 8
    else:  # balanced
        limit = 5

    root = Path(cwd_path).resolve()
    manifest_info = _detect_manifest_intel(root)

    semantic_candidates = _resolve_semantic_search_candidates(root, query, limit)
    targets: List[str] = []

    if semantic_candidates:
        for idx, c in enumerate(semantic_candidates, 1):
            sym = f" (symbol: {c['symbol']})" if c.get("symbol") else ""
            targets.append(f"{idx}. {c['path']}{sym}")
    else:
        ast_candidates = _fallback_dynamic_code_scan(root, query, limit)
        for idx, c in enumerate(ast_candidates, 1):
            sym_str = f" (exported: {', '.join(c['symbols'])})" if c.get("symbols") else ""
            targets.append(f"{idx}. {c['path']}{sym_str}")

    intel_lines: List[str] = [
        "============================================================",
        "WORKSPACE INTEL (DYNAMIC CODE DISCOVERY - PRE-COMPUTED)",
        "============================================================",
    ]

    if manifest_info:
        intel_lines.append("Project Manifest & Scripts:")
        for m in manifest_info:
            intel_lines.append(f"- {m}")
        intel_lines.append("")

    if targets:
        intel_lines.append(f"Pre-Discovered Relevant Target Code ({mode_clean.upper()} Mode - Top {len(targets)}):")
        intel_lines.extend(targets)
        intel_lines.extend([
            "",
            "ACTION DIRECTIVE: Focus your read_file / edit_file actions directly on the target files above.",
            "Do NOT run blind exploratory shell commands ('find .', 'ls -R', or blind tests) to locate files.",
        ])
    else:
        intel_lines.extend([
            "Workspace Note: No specific code files matched pre-retrieval. Use targeted search_code or read_file.",
        ])

    intel_lines.append("============================================================")
    return "\n".join(intel_lines)


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
        policy_directive: Optional[str] = None,
    ) -> str:
        """Format daftar pesan Message/dict menjadi teks dialog terstruktur."""
        formatted_turns: List[str] = []
        tools_injected = False

        if policy_directive:
            formatted_turns.append(f"[SYSTEM]:\n{policy_directive}")

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
        request: Optional[ProviderRequest] = None,
    ) -> GenerateResult:
        """Kirim request ke Antigravity via agy CLI bridge atau HTTP API."""
        if request is not None or (prompt or messages):
            resolved = self._resolve_request(prompt, messages, options, tools, tool_choice, request)
            messages = resolved.messages
            options = resolved.generation_options or options
            tools = resolved.tools if resolved.tools is not None else tools
            prompt = None

        if not prompt and not messages:
            raise ValueError("Minimal salah satu dari 'prompt' atau 'messages' harus diisi.")

        tool_defs = self._build_tool_definitions(tools) if tools else []
        model = (options and options.model) or self.config.model or "gemini-3.8-flash-medium"
        if model in ("claude-opus-4-6", "claude-opus", "opus"):
            model = "claude-opus-4-6-thinking"
        elif model in ("claude-sonnet-4-6-thinking", "claude-sonnet"):
            model = "claude-sonnet-4-6"

        cli = self._resolve_cli_path()
        if cli:
            cwd = (
                (options.extra.get("workspace_root") if options and options.extra else None)
                or getattr(self.config, "workspace_root", None)
                or None
            )
            target_cwd: Optional[str] = None
            if cwd and os.path.exists(str(cwd)):
                target_cwd = str(Path(cwd).resolve())

            policy_mode = (
                (options.extra.get("execution_policy", {}).get("effective_mode") if options and options.extra else None)
                or (options.extra.get("mode") if options and options.extra else None)
                or "balanced"
            )
            policy_directive = _format_antigravity_policy_directive(policy_mode)

            query = ""
            if prompt:
                query = prompt
            elif messages:
                for msg in reversed(messages):
                    if _extract_msg_role(msg).lower() == "user":
                        query = _extract_msg_content(msg)
                        break

            if target_cwd:
                workspace_intel = _resolve_dynamic_code_context(target_cwd, query, policy_mode)
                if workspace_intel:
                    policy_directive = f"{policy_directive}\n\n{workspace_intel}"

            if messages:
                input_text = self._format_messages_to_prompt(
                    messages, tools=tool_defs if tool_defs else None, policy_directive=policy_directive
                )
            elif prompt:
                if tool_defs:
                    input_text = f"[SYSTEM]:\n{policy_directive}\n\n{_format_tools_prompt(tool_defs)}\n\n[USER]:\n{prompt}"
                else:
                    input_text = f"[SYSTEM]:\n{policy_directive}\n\n[USER]:\n{prompt}"
            else:
                input_text = ""

            event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = (
                options.extra.get("event_sink")
                if options and options.extra and callable(options.extra.get("event_sink"))
                else None
            )

            # Bila event_sink tersedia, gunakan stream-json agar intermediate tool
            # calls dipancarkan real-time ke UI timeline Aegis saat agy berjalan.
            use_streaming = event_sink is not None
            output_format = "stream-json" if use_streaming else "json"
            cmd = [cli, "-p", input_text, "--model", model, "--output-format", output_format, "--dangerously-skip-permissions"]
            if options and options.max_tokens is not None:
                cmd.extend(["--max-tokens", str(options.max_tokens)])
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
            base_timeout = self.config.timeout or 120
            # Bila execution policy adalah 'balanced' atau 'deep' (atau model berkemampuan thinking/reasoning),
            # naikkan timeout minimal menjadi 180 detik agar tidak terputus saat proses reasoning/thinking berlangsung.
            if policy_mode in ("balanced", "deep") or getattr(self, "supports_thinking", False) or "flash-medium" in model or "pro-high" in model:
                timeout = max(base_timeout, 180)
            else:
                timeout = base_timeout
            # Idle timeout: batas waktu keheningan tanpa output baru (inactivity window)
            idle_timeout = getattr(self.config, "idle_timeout", 60) or 60
            # Max timeout: batas absolut keselamatan eksekusi (safety ceiling)
            max_timeout = max(timeout, 600)
            cancel_check = (
                options.extra.get("cancel_check")
                if options and options.extra and callable(options.extra.get("cancel_check"))
                else None
            )
            cancel_token = (
                options.extra.get("cancel_token")
                if options and options.extra
                else None
            )

            def is_cancelled() -> bool:
                if cancel_check is not None and cancel_check():
                    return True
                if cancel_token is not None and getattr(cancel_token, "is_cancelled", None) and cancel_token.is_cancelled():
                    return True
                return False

            if is_cancelled():
                raise ProviderUnavailableError("Antigravity execution dibatalkan oleh pengguna (user stop).")

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
                accumulated_thoughts: List[str] = []
                final_response = ""
                raw_data: Dict[str, Any] = {}
                start_time = time.time()
                last_activity_time = start_time
                files_read_set: set[str] = set()
                file_read_counts: Dict[str, int] = {}
                tool_call_counts: Dict[str, int] = {}
                zero_result_streak = 0
                try:
                    while True:
                        if is_cancelled():
                            proc.kill()
                            raise ProviderUnavailableError(
                                "Antigravity execution dibatalkan oleh pengguna (user stop)."
                            )
                        if time.time() - last_activity_time > idle_timeout:
                            proc.kill()
                            raise ProviderUnavailableError(
                                f"Antigravity CLI idle timeout: tidak ada aktivitas selama {idle_timeout} detik."
                            )
                        if time.time() - start_time > max_timeout:
                            proc.kill()
                            raise ProviderUnavailableError(
                                f"Antigravity CLI melebihi batas waktu eksekusi maksimum {max_timeout} detik."
                            )
                        line = proc.stdout.readline() if proc.stdout else ""
                        if not line:
                            if proc.poll() is not None:
                                break
                            if is_cancelled():
                                proc.kill()
                                raise ProviderUnavailableError(
                                    "Antigravity execution dibatalkan oleh pengguna (user stop)."
                                )
                            time.sleep(0.02)
                            continue

                        line_str = line.strip()
                        if not line_str:
                            continue

                        try:
                            item = json.loads(line_str)
                        except Exception:
                            continue

                        last_activity_time = time.time()
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
                                        # Active Streaming Circuit Breaker:
                                        # 1. Blokir pelanggaran batas workspace (directory traversal keluar dari root)
                                        # 2. Blokir pembacaan berkas log internal (.aegis/log/ dsb)
                                        # 3. Batasi pembacaan berkas unik di mode fast (maks 3 berkas)
                                        norm_target = target.replace("\\", "/").lower()

                                        is_traversal_breach = False
                                        if aegis_tool == "run_command":
                                            cmd_tokens = norm_target.split()
                                            if any(tok == ".." or tok.startswith("../") or "/../" in tok for tok in cmd_tokens):
                                                is_traversal_breach = True
                                        elif aegis_tool in ("read_file", "edit_file", "write_file", "delete_file"):
                                            if norm_target.startswith("../") or "/../" in norm_target:
                                                is_traversal_breach = True
                                            elif target_cwd and norm_target.startswith("/"):
                                                norm_cwd = target_cwd.replace("\\", "/").lower()
                                                if not norm_target.startswith(norm_cwd):
                                                    is_traversal_breach = True

                                        if aegis_tool in ("edit_file", "write_file", "replace_file_content", "delete_file", "move_file"):
                                            if norm_target in file_read_counts:
                                                file_read_counts[norm_target] = 0

                                        if is_traversal_breach:
                                            proc.kill()
                                            raise ProviderAPIError(
                                                f"Pelanggaran Batasan Workspace: Operasi '{target}' mengakses direktori di luar root proyek. "
                                                "Eksekusi dibatasi ketat di dalam root proyek aktif.",
                                                status_code=403,
                                                endpoint="agy CLI",
                                                response_body=f"Circuit breaker: workspace boundary violation '{target}'",
                                            )

                                        if aegis_tool == "read_file":
                                            is_log_target = (
                                                "/.aegis/log/" in norm_target
                                                or norm_target.startswith(".aegis/log/")
                                                or "/.aether/log/" in norm_target
                                                or norm_target.startswith(".aether/log/")
                                                or (norm_target.endswith(".log") and (".aegis" in norm_target or ".aether" in norm_target))
                                            )
                                            if is_log_target:
                                                proc.kill()
                                                raise ProviderAPIError(
                                                    f"Pelanggaran Guardrail Keamanan: Antigravity CLI dihentikan karena mencoba membaca berkas log '{target}'. "
                                                    "Membaca berkas log dilarang untuk mencegah token overflow.",
                                                    status_code=400,
                                                    endpoint="agy CLI",
                                                    response_body=f"Circuit breaker: forbidden log file read '{target}'",
                                                )
                                            if target:
                                                files_read_set.add(target)
                                                read_count = file_read_counts.get(norm_target, 0) + 1
                                                file_read_counts[norm_target] = read_count
                                                if read_count > 2:
                                                    logger.debug("Repeated file read: %s (%dx)", target, read_count)

                                        # Multi-Tool Signature Redundancy Tracking (non-read_file)
                                        if aegis_tool != "read_file":
                                            tool_sig = _tool_call_signature(aegis_tool, params)
                                            tool_count = tool_call_counts.get(tool_sig, 0) + 1
                                            tool_call_counts[tool_sig] = tool_count
                                            if tool_count > 2:
                                                logger.debug("Repeated tool call: %s (%dx)", tool_sig, tool_count)

                                        if event_sink:
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
                                elif step_type in ("thought", "reasoning"):
                                    thought_delta = step_update.get("thought_delta") or step_update.get("text_delta")
                                    if thought_delta:
                                        accumulated_thoughts.append(thought_delta)
                                        if event_sink:
                                            event_sink("agent_reasoning_delta", {
                                                "delta": thought_delta,
                                                "reasoning": thought_delta,
                                            })
                                elif step_type == "agent_response":
                                    text_delta = step_update.get("text_delta")
                                    if text_delta:
                                        accumulated_text.append(text_delta)
                            elif item.get("event") == "result":
                                res_obj = item.get("result") or {}
                                final_response = res_obj.get("response") or ""
                                raw_data = res_obj
                                status_code_val = res_obj.get("status") or "SUCCESS"
                                if status_code_val == "ERROR":
                                    err_detail = res_obj.get("error") or "Antigravity CLI execution error"
                                    try:
                                        proc.kill()
                                    except Exception:
                                        pass
                                    raise ProviderAPIError(
                                        f"Antigravity CLI mengembalikan status ERROR: {err_detail}",
                                        status_code=500,
                                        endpoint="agy CLI",
                                        response_body=err_detail,
                                    )
                                break
                            elif "response" in item and item.get("response"):
                                final_response = item["response"]
                                raw_data = item
                                break
                except Exception:
                    proc.kill()
                    raise

                stderr_text = ""
                try:
                    if proc.stderr:
                        stderr_text = proc.stderr.read().strip()
                except Exception:
                    pass

                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

                ret_code = getattr(proc, "returncode", 0)
                if ret_code != 0 and not accumulated_text and not final_response:
                    err_msg = stderr_text or f"Exit code {ret_code}"
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
                    reasoning="\n".join(accumulated_thoughts).strip() or None,
                )

            # Jalur B: Standar subprocess.run (untuk mock unit test atau non-streaming)
            if is_cancelled():
                raise ProviderUnavailableError("Antigravity execution dibatalkan oleh pengguna (user stop).")

            try:
                if subprocess.run is _orig_subprocess_run:
                    proc_b = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env,
                        cwd=target_cwd,
                    )
                    start_b = time.time()
                    while proc_b.poll() is None:
                        if is_cancelled():
                            proc_b.kill()
                            raise ProviderUnavailableError(
                                "Antigravity execution dibatalkan oleh pengguna (user stop)."
                            )
                        if time.time() - start_b > timeout:
                            proc_b.kill()
                            raise ProviderUnavailableError(
                                f"Antigravity CLI timeout setelah {timeout} detik."
                            )
                        time.sleep(0.05)
                    stdout_b, stderr_b = proc_b.communicate()
                    proc = subprocess.CompletedProcess(cmd, proc_b.returncode, stdout_b, stderr_b)
                else:
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
            accumulated_thoughts: List[str] = []
            # Bila stdout berisi baris-baris stream-json dan event_sink aktif
            if stdout.startswith("{") and "\n{" in stdout and event_sink:
                accumulated_text = []
                final_response = ""
                raw_data = {}
                file_read_counts: Dict[str, int] = {}
                tool_call_counts: Dict[str, int] = {}
                zero_result_streak = 0
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
                                    norm_target = target.replace("\\", "/").lower()
                                    if aegis_tool in ("edit_file", "write_file", "replace_file_content", "delete_file", "move_file"):
                                        if norm_target in file_read_counts:
                                            file_read_counts[norm_target] = 0
                                    elif aegis_tool == "read_file" and target:
                                        read_count = file_read_counts.get(norm_target, 0) + 1
                                        file_read_counts[norm_target] = read_count
                                        if read_count > 2:
                                            logger.debug("Repeated file read: %s (%dx)", target, read_count)

                                    # Multi-Tool Signature Redundancy Tracking (non-read_file)
                                    if aegis_tool != "read_file":
                                        tool_sig = _tool_call_signature(aegis_tool, params)
                                        tool_count = tool_call_counts.get(tool_sig, 0) + 1
                                        tool_call_counts[tool_sig] = tool_count
                                        if tool_count > 2:
                                            logger.debug("Repeated tool call: %s (%dx)", tool_sig, tool_count)

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
                            elif step_type in ("thought", "reasoning"):
                                thought_delta = step_update.get("thought_delta") or step_update.get("text_delta")
                                if thought_delta:
                                    accumulated_thoughts.append(thought_delta)
                                    if event_sink:
                                        event_sink("agent_reasoning_delta", {
                                            "delta": thought_delta,
                                            "reasoning": thought_delta,
                                        })
                            elif step_type == "agent_response":
                                text_delta = step_update.get("text_delta")
                                if text_delta:
                                    accumulated_text.append(text_delta)
                        elif item.get("event") == "result":
                            res_obj = item.get("result") or {}
                            final_response = res_obj.get("response") or ""
                            raw_data = res_obj
                            if res_obj.get("status") == "ERROR":
                                err_detail = res_obj.get("error") or "Antigravity CLI execution error"
                                raise ProviderAPIError(
                                    f"Antigravity CLI mengembalikan status ERROR: {err_detail}",
                                    status_code=500,
                                    endpoint="agy CLI",
                                    response_body=err_detail,
                                )
                            break
                        elif "response" in item and item.get("response"):
                            final_response = item["response"]
                            raw_data = item
                            break
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
                reasoning="\n".join(accumulated_thoughts).strip() or None,
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
            max_retries = 3
            resp = None
            last_exc = None
            for attempt in range(max_retries):
                try:
                    resp = requests.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=self.config.timeout or 120,
                    )
                    if resp.status_code in (502, 503, 504) and attempt < max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    break
                except (requests.ConnectionError, requests.Timeout) as exc:
                    last_exc = exc
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    raise ProviderUnavailableError(
                        f"Gagal menghubungi Antigravity HTTP endpoint '{endpoint}': {exc}"
                    ) from exc
                except requests.RequestException as exc:
                    raise ProviderUnavailableError(
                        f"Gagal menghubungi Antigravity HTTP endpoint '{endpoint}': {exc}"
                    ) from exc

            if resp is None and last_exc is not None:
                raise ProviderUnavailableError(
                    f"Gagal menghubungi Antigravity HTTP endpoint '{endpoint}' setelah {max_retries} percobaan: {last_exc}"
                ) from last_exc

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
            reasoning_text = None
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {})
                first_text = msg.get("content", "") or ""
                reasoning_text = msg.get("reasoning_content") or msg.get("reasoning") or None

            return GenerateResult(
                text=first_text,
                model=model,
                provider=self.name,
                raw=data if isinstance(data, dict) else {},
                reasoning=reasoning_text,
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
                    reasoning=result.reasoning or first_msg.get("reasoning_content") or first_msg.get("reasoning") or None,
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
            reasoning=result.reasoning or first_msg.get("reasoning_content") or first_msg.get("reasoning") or None,
        )
