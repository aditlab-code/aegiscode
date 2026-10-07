"""Tests for Task Lifecycle Idempotency and Sequence Guard (Phase 1)."""

import pytest
from agent_ai.runtime.lifecycle import (
    TaskLifecycleManager,
    TaskLifecycleState,
    TaskLifecycleTransitionError,
)
from agent_ai.session.events import EventType, ExecutionEvent


def test_monotonic_sequence_and_enqueue_guard() -> None:
    mgr = TaskLifecycleManager(task_id="t-1", session_id="s-1")
    assert mgr.current_state == TaskLifecycleState.QUEUED.value

    # First enqueue succeeds and transitions to pending with sequence=1
    assert mgr.enqueue_guard() is True
    assert mgr.current_state == TaskLifecycleState.PENDING.value

    # Second enqueue fails (idempotent guard)
    assert mgr.enqueue_guard() is False
    assert mgr.current_state == TaskLifecycleState.PENDING.value


def test_transition_and_events() -> None:
    mgr = TaskLifecycleManager(task_id="t-2", session_id="s-2")
    mgr.enqueue_guard()

    events: list[ExecutionEvent] = []
    e1 = mgr.transition_to(TaskLifecycleState.RUNNING.value, on_event=events.append)

    assert e1.event_type == EventType.TASK_STARTED
    assert e1.sequence == 2
    assert mgr.current_state == TaskLifecycleState.RUNNING.value
    assert len(events) == 1

    # Idempotent re-transition to same state does not throw, generates event with sequence
    e2 = mgr.transition_to(TaskLifecycleState.RUNNING.value)
    assert e2.sequence == 3
    assert mgr.current_state == TaskLifecycleState.RUNNING.value

    # Transition to validating
    e3 = mgr.transition_to(TaskLifecycleState.VALIDATING.value)
    assert e3.event_type == EventType.VALIDATION_STARTED
    assert e3.sequence == 4

    # Terminal completion
    e4 = mgr.transition_to(TaskLifecycleState.COMPLETED.value)
    assert e4.event_type == EventType.TASK_COMPLETED
    assert mgr.is_terminal is True


def test_terminal_state_rejection() -> None:
    mgr = TaskLifecycleManager(task_id="t-3", session_id="s-3")
    mgr.enqueue_guard()
    mgr.transition_to(TaskLifecycleState.RUNNING.value)
    mgr.transition_to(TaskLifecycleState.COMPLETED.value)

    # Cannot transition out of terminal state
    with pytest.raises(TaskLifecycleTransitionError):
        mgr.transition_to(TaskLifecycleState.RUNNING.value)

    with pytest.raises(TaskLifecycleTransitionError):
        mgr.transition_to(TaskLifecycleState.FAILED.value)


def test_safe_cancellation_and_terminal_guard() -> None:
    mgr = TaskLifecycleManager(task_id="t-4", session_id="s-4")
    mgr.enqueue_guard()
    mgr.transition_to(TaskLifecycleState.RUNNING.value)

    cancel_evt = mgr.cancel_task(reason="user_stop")
    assert cancel_evt.event_type == EventType.TASK_CANCELLED
    assert mgr.current_state == TaskLifecycleState.CANCELLED.value
    assert mgr.is_terminal is True

    # Repeated cancellation is idempotent
    cancel_evt2 = mgr.cancel_task(reason="user_stop_again")
    assert cancel_evt2.event_type == EventType.TASK_CANCELLED
    assert cancel_evt2.payload.get("idempotent") is True
