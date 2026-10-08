"""Data contracts dan state tracking untuk modular orchestration runtime.

Mendefinisikan dataclass murni per-run dan per-turn tanpa dependensi
sirkular terhadap AgentOrchestrator atau provider adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_ai.core.models import AgentStatus

DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS = 1000


@dataclass
class OrchestrationConfig:
    """Konfigurasi batas, mode, dan budget untuk satu sesi orkestrasi."""

    max_iterations: int = 10
    max_steps: int = DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS
    context_budget_tokens: Optional[int] = None
    use_tools: bool = True
    use_continuous_loop: bool = True
    brain_learning: bool = True
    timeout_seconds: Optional[float] = None
    execution_policy: Optional[Dict[str, Any]] = None


@dataclass
class TurnExecutionState:
    """Status runtime per-turn untuk eksekusi continuous loop."""

    iteration: int = 0
    is_final_turn: bool = False
    truncated: bool = False
    truncation_recoveries: int = 0
    commentary: Optional[str] = None
    reasoning: Optional[str] = None
    last_action_count: int = 0
    provider_error: bool = False


@dataclass
class OrchestratorResult:
    """Hasil akhir orkestrasi task agent."""

    status: AgentStatus
    result: Optional[str] = None
    error: Optional[str] = None
    iterations: int = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    learning: Optional[Dict[str, Any]] = None
    # True bila kegagalan berasal dari provider (bukan tool/command).
    # Dipakai oleh Provider Fallback (#45) untuk memutuskan perpindahan provider.
    provider_error: bool = False
    reasoning: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status == AgentStatus.DONE


# Alias untuk keselarasan Phase 2 MVP architecture plan
RunResult = OrchestratorResult

__all__ = [
    "DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS",
    "OrchestrationConfig",
    "OrchestratorResult",
    "RunResult",
    "TurnExecutionState",
]
