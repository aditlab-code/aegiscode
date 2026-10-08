"""Helper emisi event terpadu untuk event stream UI/SSE (Fase 2 MVP Modularization).

Mendefinisikan helper pemancar event terstandarisasi untuk alur eksekusi agent:
- provider_request / provider_response / retry / exhaustion
- reasoning delta / agent commentary
- tool called / result / completion / observation
- loop safety abort

Wire format schema dipertahankan 100% identik dengan implementasi baseline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent_ai.core.observability import EventSink, emit as emit_event
from agent_ai.core.response import LLMResponse, response_usage


def format_provider_response_payload(
    response: LLMResponse,
    default_provider: str = "",
    default_model: str = "",
) -> Dict[str, Any]:
    """Bangun payload event `provider_response` dari LLMResponse."""
    payload: Dict[str, Any] = {
        "provider": response.provider or default_provider,
        "model": response.model or default_model,
        "finish_reason": (
            response.finish_reason.value
            if hasattr(response.finish_reason, "value")
            else str(response.finish_reason)
        ),
        "tool_calls": len(response.tool_calls()),
    }
    usage = response_usage(getattr(response, "raw", None))
    if usage:
        payload["usage"] = usage
    return payload


def emit_provider_request(
    sink: Optional[EventSink],
    *,
    provider: str,
    model: str,
    iteration: int,
    tool_count: int,
    context_stats: Optional[Dict[str, Any]] = None,
    policy_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """Pancarkan event `provider_request`."""
    payload: Dict[str, Any] = {
        "provider": provider,
        "model": model,
        "iteration": int(iteration),
        "tool_count": int(tool_count),
    }
    if context_stats:
        payload.update(context_stats)
    if policy_fields:
        payload.update(policy_fields)
    emit_event(sink, "provider_request", payload)


def emit_provider_response(
    sink: Optional[EventSink],
    payload: Dict[str, Any],
) -> None:
    """Pancarkan event `provider_response`."""
    emit_event(sink, "provider_response", payload)


def emit_provider_retry(
    sink: Optional[EventSink],
    *,
    provider: str,
    model: str,
    attempt: int,
    next_attempt: int,
    max_attempts: int,
    error_type: str,
    error: str,
) -> None:
    """Pancarkan event `provider_retry` (tanpa credential)."""
    emit_event(
        sink,
        "provider_retry",
        {
            "provider": provider,
            "model": model,
            "attempt": int(attempt),
            "next_attempt": int(next_attempt),
            "max_attempts": int(max_attempts),
            "error_type": error_type,
            "error": error,
        },
    )


def emit_provider_retry_succeeded(
    sink: Optional[EventSink],
    *,
    provider: str,
    model: str,
    attempt: int,
    max_attempts: int,
) -> None:
    """Pancarkan event `provider_retry_succeeded`."""
    emit_event(
        sink,
        "provider_retry_succeeded",
        {
            "provider": provider,
            "model": model,
            "attempt": int(attempt),
            "max_attempts": int(max_attempts),
        },
    )


def emit_provider_retry_exhausted(
    sink: Optional[EventSink],
    *,
    provider: str,
    model: str,
    attempts: int,
    error_type: str,
    error: str,
) -> None:
    """Pancarkan event `provider_retry_exhausted`."""
    emit_event(
        sink,
        "provider_retry_exhausted",
        {
            "provider": provider,
            "model": model,
            "attempts": int(attempts),
            "error_type": error_type,
            "error": error,
        },
    )


def emit_provider_truncated(
    sink: Optional[EventSink],
    *,
    provider: str,
    model: str,
    finish_reason: str,
    recovery: int,
) -> None:
    """Pancarkan event `provider_response_truncated`."""
    emit_event(
        sink,
        "provider_response_truncated",
        {
            "provider": provider,
            "model": model,
            "finish_reason": finish_reason,
            "recovery": int(recovery),
        },
    )


def emit_provider_malformed(
    sink: Optional[EventSink],
    *,
    provider: str,
    model: str,
    error: str,
    iteration: int,
) -> None:
    """Pancarkan event `provider_malformed_response`."""
    emit_event(
        sink,
        "provider_malformed_response",
        {
            "provider": provider,
            "model": model,
            "error": error,
            "iteration": int(iteration),
        },
    )


def emit_reasoning(
    sink: Optional[EventSink],
    *,
    delta: str,
    reasoning: Optional[str] = None,
) -> None:
    """Pancarkan event `agent_reasoning_delta`."""
    emit_event(
        sink,
        "agent_reasoning_delta",
        {
            "delta": delta,
            "reasoning": reasoning if reasoning is not None else delta,
        },
    )


def emit_commentary(
    sink: Optional[EventSink],
    *,
    text: str,
    iteration: int,
) -> None:
    """Pancarkan event `agent_commentary`."""
    emit_event(
        sink,
        "agent_commentary",
        {
            "text": text,
            "iteration": int(iteration),
        },
    )


def emit_tool_call(
    sink: Optional[EventSink],
    *,
    tool: str,
    tool_call_id: str,
    arguments: Dict[str, Any],
    target: str = "",
    iteration: int = 0,
) -> None:
    """Pancarkan event `tool_called`."""
    emit_event(
        sink,
        "tool_called",
        {
            "tool": tool,
            "tool_call_id": tool_call_id,
            "arguments": arguments,
            "target": target,
            "iteration": int(iteration),
        },
    )


def emit_tool_result(
    sink: Optional[EventSink],
    *,
    tool: str,
    tool_call_id: str,
    success: bool,
    output: str,
    error: Optional[str] = None,
) -> None:
    """Pancarkan event `tool_result`."""
    emit_event(
        sink,
        "tool_result",
        {
            "tool": tool,
            "tool_call_id": tool_call_id,
            "success": bool(success),
            "status": "success" if success else "error",
            "output": output,
            "error": error,
        },
    )


def emit_tool_completion(
    sink: Optional[EventSink],
    *,
    tool: str,
    tool_call_id: str,
    success: bool,
    error: Optional[str] = None,
    target: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Pancarkan event `tool_completed`."""
    emit_event(
        sink,
        "tool_completed",
        {
            "tool": tool,
            "tool_call_id": tool_call_id,
            "success": bool(success),
            "error": error,
            "target": target,
            "metadata": metadata or {},
        },
    )


def emit_observation(
    sink: Optional[EventSink],
    *,
    action_id: str,
    success: bool,
    content: str,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Pancarkan event `agent_observation`."""
    emit_event(
        sink,
        "agent_observation",
        {
            "action_id": action_id,
            "success": bool(success),
            "error": error,
            "content": content,
            "metadata": metadata or {},
        },
    )


def emit_observation_received(
    sink: Optional[EventSink],
    *,
    tool: str,
    tool_call_id: str,
    success: bool,
    content: str,
) -> None:
    """Pancarkan event `observation_received`."""
    emit_event(
        sink,
        "observation_received",
        {
            "tool": tool,
            "tool_call_id": tool_call_id,
            "success": bool(success),
            "content": content,
        },
    )


def emit_loop_safety_abort(
    sink: Optional[EventSink],
    *,
    max_steps: int,
    iteration: int,
) -> None:
    """Pancarkan event `loop_safety_abort`."""
    emit_event(
        sink,
        "loop_safety_abort",
        {
            "max_steps": int(max_steps),
            "iteration": int(iteration),
        },
    )


__all__ = [
    "emit_commentary",
    "emit_loop_safety_abort",
    "emit_observation",
    "emit_observation_received",
    "emit_provider_malformed",
    "emit_provider_request",
    "emit_provider_response",
    "emit_provider_retry",
    "emit_provider_retry_exhausted",
    "emit_provider_retry_succeeded",
    "emit_provider_truncated",
    "emit_reasoning",
    "emit_tool_call",
    "emit_tool_completion",
    "emit_tool_result",
    "format_provider_response_payload",
]
