"""Agent Runtime Layer AETHER.

Menyatukan layer yang sudah ada (PreparedTask, TaskPlan, AgentLoop,
AgentOrchestrator, ToolExecutor, provider/normalized LLMResponse) menjadi
runtime coding agent nyata:

    PreparedTask -> AgentRuntime -> Plan Step -> LLM -> ToolExecutor
        -> Observation -> LLM -> ... -> DONE / FAILED

Runtime provider-agnostic, tool execution lewat ToolExecutor/ToolRegistry,
dan tidak menyimpan hidden chain-of-thought.

    from agent_ai.runtime import AgentRuntime

    runtime = AgentRuntime(provider=provider)
    result = runtime.run(prepared_task)
"""

from agent_ai.runtime.models import RuntimeProgress, RuntimeResult, RuntimeStatus
from agent_ai.runtime.runtime import AgentRuntime
from agent_ai.runtime.working_state import (
    WorkingState,
    WorkingStateManager,
    PlanEntry,
    PlanEntryStatus,
    TERMINAL_PLAN_ENTRY_STATUSES,
)
from agent_ai.runtime.lifecycle import (
    TaskLifecycleManager,
    TaskLifecycleState,
    TaskLifecycleTransitionError,
    TERMINAL_LIFECYCLE_STATES,
)
from agent_ai.runtime.olympus_workflow import (
    OlympusPhase,
    OLYMPUS_ASSIGNMENTS,
    LifecycleState,
    load_lifecycle_state,
    save_lifecycle_state,
    advance_lifecycle_phase,
    map_olympus_to_ui_activity,
)

__all__ = [
    "AgentRuntime",
    "RuntimeResult",
    "RuntimeProgress",
    "RuntimeStatus",
    "WorkingState",
    "WorkingStateManager",
    "PlanEntry",
    "PlanEntryStatus",
    "TERMINAL_PLAN_ENTRY_STATUSES",
    "TaskLifecycleManager",
    "TaskLifecycleState",
    "TaskLifecycleTransitionError",
    "TERMINAL_LIFECYCLE_STATES",
    "OlympusPhase",
    "OLYMPUS_ASSIGNMENTS",
    "LifecycleState",
    "load_lifecycle_state",
    "save_lifecycle_state",
    "advance_lifecycle_phase",
    "map_olympus_to_ui_activity",
]
