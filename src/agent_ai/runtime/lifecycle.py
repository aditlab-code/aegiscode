"""Runtime Task Lifecycle Manager & Guard.

Mengonsolidasikan transisi state task:
QUEUED -> PENDING -> RUNNING -> VALIDATING -> (COMPLETED | FAILED | CANCELLED).
Mencegah eksekusi ganda ke scheduler (enqueue_guard) serta memastikan
pembatalan (cancel_task) mencatat event terminal kanonik task_cancelled.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set

from agent_ai.session.events import EventType, ExecutionEvent, make_event
from agent_ai.task.models import TERMINAL_STATUSES, TaskStatus

logger = logging.getLogger(__name__)


class TaskLifecycleState(str, Enum):
    """Status lifecycle terstandarisasi untuk eksekusi task."""

    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_LIFECYCLE_STATES: frozenset[str] = frozenset(
    {TaskLifecycleState.COMPLETED.value, TaskLifecycleState.FAILED.value, TaskLifecycleState.CANCELLED.value}
)


class TaskLifecycleTransitionError(ValueError):
    """Transisi state tidak valid atau melanggar aturan idempotensi."""


# Peta transisi status yang sah
_ALLOWED_STATE_TRANSITIONS: Dict[str, frozenset[str]] = {
    TaskLifecycleState.QUEUED.value: frozenset(
        {TaskLifecycleState.PENDING.value, TaskLifecycleState.RUNNING.value, TaskLifecycleState.CANCELLED.value, TaskLifecycleState.FAILED.value}
    ),
    TaskLifecycleState.PENDING.value: frozenset(
        {TaskLifecycleState.RUNNING.value, TaskLifecycleState.CANCELLED.value, TaskLifecycleState.FAILED.value}
    ),
    TaskLifecycleState.RUNNING.value: frozenset(
        {TaskLifecycleState.VALIDATING.value, TaskLifecycleState.COMPLETED.value, TaskLifecycleState.FAILED.value, TaskLifecycleState.CANCELLED.value}
    ),
    TaskLifecycleState.VALIDATING.value: frozenset(
        {TaskLifecycleState.COMPLETED.value, TaskLifecycleState.FAILED.value, TaskLifecycleState.CANCELLED.value}
    ),
    TaskLifecycleState.COMPLETED.value: frozenset(),
    TaskLifecycleState.FAILED.value: frozenset(),
    TaskLifecycleState.CANCELLED.value: frozenset(),
}


class TaskLifecycleManager:
    """Mengelola siklus hidup task secara thread-safe dan idempotent.

    Menjamin:
    1. Transisi state searah yang teratur (tidak ada regresi dari terminal).
    2. Guard enqueue ganda (enqueue_guard).
    3. Penomoran urutan event yang meningkat monotonik per task.
    4. Pencatatan event pembatalan (task_cancelled) yang aman ke observer/store.
    """

    def __init__(self, task_id: str, session_id: Optional[str] = None, initial_state: str = TaskLifecycleState.QUEUED.value) -> None:
        self.task_id = str(task_id).strip()
        self.session_id = str(session_id or "")
        self._lock = threading.Lock()
        self._state = str(initial_state).strip().lower()
        self._sequence = 0
        self._enqueued = False
        self._cancelled = False
        self._history: list[dict[str, Any]] = [
            {"state": self._state, "timestamp": time.time(), "sequence": 0}
        ]

    @property
    def current_state(self) -> str:
        with self._lock:
            return self._state

    @property
    def is_terminal(self) -> bool:
        with self._lock:
            return self._state in TERMINAL_LIFECYCLE_STATES

    def enqueue_guard(self) -> bool:
        """Cegah pendaftaran ganda ke scheduler/antrean.

        Returns:
            True jika berhasil di-enqueue untuk pertama kali; False jika sudah pernah di-enqueue atau sudah terminal.
        """
        with self._lock:
            if self._enqueued or self._state in TERMINAL_LIFECYCLE_STATES:
                return False
            self._enqueued = True
            if self._state == TaskLifecycleState.QUEUED.value:
                # Transisi aman ke pending jika baru masuk antrean
                self._state = TaskLifecycleState.PENDING.value
                self._sequence += 1
                self._history.append({
                    "state": self._state,
                    "timestamp": time.time(),
                    "sequence": self._sequence,
                })
            return True

    def transition_to(
        self,
        target_state: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        on_event: Optional[Callable[[ExecutionEvent], None]] = None,
    ) -> ExecutionEvent:
        """Transisikan task ke target_state secara idempotent dan thread-safe.

        Jika task sudah berada dalam target_state atau sudah terminal dan target_state tidak diizinkan,
        mencegah perubahan liar dan tetap menghasilkan event yang konsisten.
        """
        target = str(target_state).strip().lower()
        with self._lock:
            # Idempotensi jika state sudah sama persis
            if self._state == target:
                self._sequence += 1
                evt = make_event(
                    session_id=self.session_id,
                    event_type=self._map_state_to_event_type(target),
                    task_id=self.task_id,
                    payload=payload or {"state": target, "idempotent": True},
                    status=target,
                    sequence=self._sequence,
                )
                if on_event:
                    try:
                        on_event(evt)
                    except Exception:
                        logger.exception("on_event callback failed")
                return evt

            # Cegah mutasi keluar dari terminal
            if self._state in TERMINAL_LIFECYCLE_STATES:
                raise TaskLifecycleTransitionError(
                    f"Tidak dapat mengubah task '{self.task_id}' dari terminal state '{self._state}' ke '{target}'."
                )

            # Validasi transisi sah
            allowed = _ALLOWED_STATE_TRANSITIONS.get(self._state, frozenset())
            if target not in allowed:
                raise TaskLifecycleTransitionError(
                    f"Transisi tidak valid untuk task '{self.task_id}': '{self._state}' -> '{target}'."
                )

            self._state = target
            self._sequence += 1
            if target == TaskLifecycleState.CANCELLED.value:
                self._cancelled = True

            self._history.append({
                "state": target,
                "timestamp": time.time(),
                "sequence": self._sequence,
                "payload": payload,
            })

            evt = make_event(
                session_id=self.session_id,
                event_type=self._map_state_to_event_type(target),
                task_id=self.task_id,
                payload=payload or {"state": target},
                status=target,
                sequence=self._sequence,
            )

        if on_event:
            try:
                on_event(evt)
            except Exception:
                logger.exception("on_event callback failed")

        return evt

    def cancel_task(
        self,
        reason: str = "user_cancelled",
        *,
        on_event: Optional[Callable[[ExecutionEvent], None]] = None,
    ) -> ExecutionEvent:
        """Batalkan task secara aman dan pancarkan event task_cancelled."""
        with self._lock:
            if self._state == TaskLifecycleState.CANCELLED.value:
                # Idempotent cancellation
                self._sequence += 1
                evt = make_event(
                    session_id=self.session_id,
                    event_type=EventType.TASK_CANCELLED,
                    task_id=self.task_id,
                    payload={"reason": reason, "idempotent": True},
                    status=TaskLifecycleState.CANCELLED.value,
                    sequence=self._sequence,
                )
                if on_event:
                    try:
                        on_event(evt)
                    except Exception:
                        pass
                return evt

            if self._state in TERMINAL_LIFECYCLE_STATES:
                # Sudah terminal (completed/failed), tidak bisa diubah jadi cancelled
                self._sequence += 1
                evt = make_event(
                    session_id=self.session_id,
                    event_type=self._map_state_to_event_type(self._state),
                    task_id=self.task_id,
                    payload={"warning": f"Task already terminal in {self._state}"},
                    status=self._state,
                    sequence=self._sequence,
                )
                return evt

        return self.transition_to(
            TaskLifecycleState.CANCELLED.value,
            payload={"reason": reason},
            on_event=on_event,
        )

    def _map_state_to_event_type(self, state: str) -> EventType:
        mapping = {
            TaskLifecycleState.QUEUED.value: EventType.TASK_CREATED,
            TaskLifecycleState.PENDING.value: EventType.TASK_CREATED,
            TaskLifecycleState.RUNNING.value: EventType.TASK_STARTED,
            TaskLifecycleState.VALIDATING.value: EventType.VALIDATION_STARTED,
            TaskLifecycleState.COMPLETED.value: EventType.TASK_COMPLETED,
            TaskLifecycleState.FAILED.value: EventType.TASK_FAILED,
            TaskLifecycleState.CANCELLED.value: EventType.TASK_CANCELLED,
        }
        return mapping.get(state, EventType.PHASE_CHANGED)
