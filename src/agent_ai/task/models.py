"""Model untuk Task Preparation, Lifecycle & Execution State.

Provider-agnostic. Mendefinisikan:
1. Persiapan task sebelum Agent Runtime berjalan (PreparedTask).
2. Status, identitas, dan state lifecycle task (TaskStatus, TaskPhase, TaskState).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from agent_ai.contextbuilder.models import ContextResult
from agent_ai.planning.models import TaskPlan


# ---------------------------------------------------------------------------
# Task Lifecycle Enums & Constants
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    """Status lifecycle task."""

    CREATED = "created"
    PREPARING = "preparing"
    PLANNING = "planning"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPhase(str, Enum):
    """Fase eksekusi yang lebih detail (opsional, untuk observability)."""

    NONE = "none"
    PREPARATION = "preparation"
    PLANNING = "planning"
    EXECUTION = "execution"
    TOOL_EXECUTION = "tool_execution"
    VALIDATION = "validation"
    FINALIZATION = "finalization"


#: Status terminal (tidak ada transition keluar).
TERMINAL_STATUSES = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED})


def new_task_id() -> str:
    """Buat task_id unik."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Task Models (State & Preparation)
# ---------------------------------------------------------------------------


@dataclass
class TaskState:
    """Snapshot state sebuah task.

    Attributes:
        task_id: identifier unik task.
        task: deskripsi task asli (tidak diubah).
        status: status lifecycle saat ini.
        phase: fase eksekusi detail saat ini.
        created_at: waktu task dibuat.
        updated_at: waktu update terakhir.
        timestamps: riwayat timestamp per status (status -> epoch detik).
        metadata: execution metadata bebas.
        result: hasil akhir (teks) bila COMPLETED.
        error: pesan error bila FAILED.
        failure: informasi kegagalan terstruktur (opsional).
    """

    task_id: str
    task: str = ""
    status: TaskStatus = TaskStatus.CREATED
    phase: TaskPhase = TaskPhase.NONE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    timestamps: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    failure: Optional[Dict[str, Any]] = None

    @property
    def is_terminal(self) -> bool:
        """True bila status sudah terminal (COMPLETED/FAILED/CANCELLED)."""
        return self.status in TERMINAL_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task": self.task,
            "status": self.status.value,
            "phase": self.phase.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timestamps": dict(self.timestamps),
            "metadata": self.metadata,
            "result": self.result,
            "error": self.error,
            "failure": self.failure,
        }


@dataclass
class PreparedTask:
    """Task yang sudah disiapkan untuk Agent Runtime.

    Attributes:
        task: task asli dari user (tidak diubah).
        context: ContextResult dari ContextBuilder (boleh None bila tidak ada).
        plan: TaskPlan dari TaskPlanner (boleh None bila tidak ada).
        metadata: info tambahan bebas (mis. sumber dependency, statistik).
        task_id: identifier task opsional (untuk Task Lifecycle & Change
            Tracking). None bila tidak dilacak.
    """

    task: str
    context: Optional[ContextResult] = None
    plan: Optional[TaskPlan] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "context": self.context.to_dict() if self.context is not None else None,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "metadata": self.metadata,
            "task_id": self.task_id,
        }

    def context_text(self) -> str:
        """Render context menjadi teks (bila ada), untuk dipakai runtime."""
        return self.context.to_text() if self.context is not None else ""
