# AegisCode Tool and Provider Extensibility Guide

AegisCode is designed for clean extensibility. This guide details how to implement custom tools, connect external Model Context Protocol (MCP) servers, and register new LLM providers within Aegis Agent.
---

## 1. Implementing Custom Tools

All tools inherit from the base tool contract in `src/agent_ai/tools/base.py` and register with `src/agent_ai/tools/registry.py`.

### 1.1 Tool Implementation Structure

To create a new tool, create a file in `src/agent_ai/tools/` or add to an existing module:

```python
from typing import Any, Dict
from src.agent_ai.tools.base import BaseTool, ToolResult

class CodeMetricsTool(BaseTool):
    """Calculates complexity metrics for a given source file."""

    name: str = "calculate_metrics"
    description: str = "Analyzes cyclomatic complexity and lines of code for a target file."
    
    # JSON schema defining tool parameters for the LLM
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path to the source file to analyze."
            }
        },
        "required": ["file_path"]
    }

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        try:
            # Enforce path sandboxing via workspace policy
            resolved_path = self.resolve_workspace_path(file_path)
            
            # Compute metric
            metrics = self._analyze_file(resolved_path)
            
            return ToolResult(
                success=True,
                output=f"Metrics for {file_path}: {metrics}",
                data=metrics
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Failed to calculate metrics: {str(exc)}",
                error=str(exc)
            )
```

### 1.2 Registering the Tool
Register your new tool in `src/agent_ai/tools/registry.py`:

```python
from src.agent_ai.tools.code_metrics import CodeMetricsTool

def register_default_tools(registry: ToolRegistry) -> None:
    # Existing tools...
    registry.register(CodeMetricsTool())
```

### 1.3 Security & Sandbox Rules
- Tools must never execute outside the configured workspace directory without explicit permission gateway override (`src/agent_ai/permission/`).
- Shell commands through terminal tools are subject to command blacklist filters.
- Sensitive environment variables (e.g. `*_API_KEY`, passwords) must be masked in tool output.

---

## 2. Model Context Protocol (MCP) Integration

AegisCode supports the Model Context Protocol (MCP), allowing Aegis Agent to consume tools and resources from external MCP servers.

Configuration lives in `.aegis/mcp.json` (with automatic fallback to `.aether/mcp.json` or `.env`):
```json
{
  "mcp_servers": {
    "database_inspector": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"]
    },
    "github_mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "mcp/github"]
    }
  }
}
```

AegisCode's `src/agent_ai/mcp/` bridge automatically discovers external MCP capabilities and translates them into native Aegis Agent tool definitions at runtime startup.

---

## 3. Adding New LLM Providers

AegisCode provides a unified interface for model backends (Google Antigravity, OpenAI, Anthropic, DeepSeek, Ollama, OpenRouter, NineRouter, etc.).

### 3.1 Base Provider Contract
All providers extend `BaseProvider` in `src/agent_ai/providers/base.py`:

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any
from src.agent_ai.providers.models import CompletionChunk, Message

class BaseProvider(ABC):
    """Abstract interface for LLM execution providers."""

    @abstractmethod
    async def complete_stream(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> AsyncGenerator[CompletionChunk, None]:
        """Streams response tokens and tool calls."""
        yield
```

### 3.2 Provider Factory Registration
Register your provider in `src/agent_ai/providers/factory.py`:

```python
from src.agent_ai.providers.custom import CustomProvider

def create_provider(provider_name: str, config: Dict[str, Any]) -> BaseProvider:
    if provider_name == "custom_llm":
        return CustomProvider(
            api_key=config.get("api_key"),
            base_url=config.get("base_url")
        )
    # Existing provider instantiations...
```

### 3.3 Robustness & Retries (`retry.py`)
Wrap outbound provider calls with Aegis Agent's backoff utility:
- Automatically handles HTTP 429 (Rate Limits) and HTTP 503 (Overloaded).
- Configurable maximum retries with exponential jitter backoff.
- Failover support: switches to a configured secondary provider if the primary provider sustains consecutive timeouts.
