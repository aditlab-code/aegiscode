"""Model data untuk Unified Threaded Session Architecture.

Model ini merepresentasikan entitas kanonikal Sesi Terpadu (Unified Session)
yang menampung percakapan multi-turn (baik mode ask maupun agent), riwayat
eksekusi tool, perubahan berkas, dan status siklus hidup eksekusi.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def new_turn_id() -> str:
    """Buat identifier unik turn."""
    return f"turn_{uuid.uuid4().hex[:12]}"


def new_session_id() -> str:
    """Buat identifier unik session."""
    return f"sess_{uuid.uuid4().hex[:12]}"


@dataclass
class TurnExecutionData:
    """Data eksekusi untuk giliran berjenis agent."""

    task_id: str
    status: str = "completed"  # running, completed, failed, cancelled
    tool_events: List[Dict[str, Any]] = field(default_factory=list)
    changes: List[Dict[str, Any]] = field(default_factory=list)
    report: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konversi ke bentuk dictionary serializable."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "tool_events": list(self.tool_events or []),
            "changes": list(self.changes or []),
            "report": self.report,
            "error": self.error,
            "usage": dict(self.usage) if isinstance(self.usage, dict) else None,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional[TurnExecutionData]:
        """Rekonstruksi dari dictionary."""
        if not data or not isinstance(data, dict):
            return None
        return cls(
            task_id=str(data.get("task_id") or ""),
            status=str(data.get("status") or "completed"),
            tool_events=list(data.get("tool_events") or []),
            changes=list(data.get("changes") or []),
            report=data.get("report"),
            error=data.get("error"),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else None,
        )


@dataclass
class UnifiedTurn:
    """Satu giliran dalam sesi terpadu."""

    turn_id: str
    role: str  # "user" | "assistant"
    mode: str  # "ask" | "agent"
    content: str
    created_at: float = field(default_factory=time.time)
    images: Optional[List[Dict[str, Any]]] = None
    execution: Optional[TurnExecutionData] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konversi ke bentuk dictionary serializable."""
        return {
            "turn_id": self.turn_id,
            "role": self.role,
            "mode": self.mode,
            "content": self.content,
            "created_at": self.created_at,
            "images": [dict(img) for img in self.images] if self.images else [],
            "execution": self.execution.to_dict() if self.execution else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UnifiedTurn:
        """Rekonstruksi dari dictionary."""
        raw_images = data.get("images")
        images = [dict(img) for img in raw_images] if isinstance(raw_images, list) else None
        raw_exec = data.get("execution")
        execution = TurnExecutionData.from_dict(raw_exec) if raw_exec else None

        return cls(
            turn_id=str(data.get("turn_id") or new_turn_id()),
            role=str(data.get("role") or "user"),
            mode=str(data.get("mode") or "ask"),
            content=str(data.get("content") or ""),
            created_at=float(data.get("created_at") or time.time()),
            images=images,
            execution=execution,
        )


@dataclass
class UnifiedSession:
    """Entitas sesi tunggal kanonikal."""

    session_id: str
    project_id: Optional[str] = None
    title: str = "New Session"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: List[UnifiedTurn] = field(default_factory=list)
    execution_state: str = "idle"  # idle, running, cancelling
    active_task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konversi ke bentuk dictionary serializable."""
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "execution_state": self.execution_state,
            "active_task_id": self.active_task_id,
            "turns": [turn.to_dict() for turn in self.turns],
            "turn_count": len(self.turns),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UnifiedSession:
        """Rekonstruksi dari dictionary."""
        raw_turns = data.get("turns") or []
        turns = [UnifiedTurn.from_dict(t) for t in raw_turns if isinstance(t, dict)]
        return cls(
            session_id=str(data.get("session_id") or new_session_id()),
            project_id=data.get("project_id") or None,
            title=str(data.get("title") or "New Session"),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            turns=turns,
            execution_state=str(data.get("execution_state") or "idle"),
            active_task_id=data.get("active_task_id") or None,
        )
