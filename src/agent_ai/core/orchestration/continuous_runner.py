"""Continuous turn-by-turn agent execution runner (Native Tool Calling).

Mengelola alur Native Tool Calling:
LLM -> tool_calls -> eksekusi SEMUA tool -> hasil role="tool"
    -> LLM -> tool_calls -> ... -> LLM final (tanpa tool call).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from agent_ai.core.history import ConversationHistory
from agent_ai.core.loop import AgentLoop
from agent_ai.core.models import AgentObservation, AgentStatus
from agent_ai.core.observability import emit as emit_event
from agent_ai.core.orchestration.contracts import (
    DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS,
    OrchestrationConfig,
    OrchestratorResult,
    TurnExecutionState,
)
from agent_ai.core.orchestration.tool_results import (
    record_tool_result,
    tool_payload_to_observation,
)
from agent_ai.core.response import extract_reasoning_and_content
from agent_ai.core.types import ToolCall, ToolResultPayload
from agent_ai.providers.base import GenerateOptions

if TYPE_CHECKING:  # pragma: no cover
    from agent_ai.core.orchestrator import AgentOrchestrator


class ContinuousRunner:
    """Runner untuk continuous turn-by-turn agent execution loop.

    Pola Native Tool Calling (satu percakapan kontinu):
        LLM -> tool_calls -> eksekusi SEMUA tool -> hasil role="tool"
            -> LLM -> tool_calls -> ... -> LLM final (tanpa tool call)

    Karakteristik:
        - Satu ConversationHistory untuk seluruh task, bukan session LLM baru per langkah.
        - Hasil tool dikirim sebagai pesan role "tool" dengan tool_call_id.
        - Completion ditentukan sepenuhnya oleh LLM (response tanpa tool calls).
    """

    def __init__(
        self,
        orchestrator: Any,
        config: Optional[OrchestrationConfig] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.config = config or OrchestrationConfig()

    def run(
        self,
        task: str,
        *,
        system_prompt: Optional[str] = None,
        max_steps: int = DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS,
        options: Optional[GenerateOptions] = None,
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> OrchestratorResult:
        """Jalankan SATU percakapan kontinu sampai LLM memberi jawaban final."""
        orch = self.orchestrator
        effective_options = options if options is not None else orch.options
        prompt = system_prompt if system_prompt is not None else orch.system_prompt

        loop = AgentLoop(task=task, max_iterations=max(1, int(max_steps)))
        loop.start()

        # Satu percakapan kontinu untuk seluruh task.
        history = ConversationHistory()
        if prompt:
            history.append_system_message(prompt)
        environment_context = orch._environment_context_message()
        if environment_context is not None:
            history.append_system_message(environment_context.content)

        # Task isolation: state lifecycle Bible di-reset untuk task ini.
        orch.begin_bible_context_scope()
        brain_context = orch._bible_context_message_for_task(task)
        if brain_context is not None:
            history.append_system_message(brain_context.content)
        policy_directive = orch._policy_directive_message()
        if policy_directive is not None:
            history.append_system_message(policy_directive.content)
        history.append_user_message(task, parts=user_parts)

        tools = orch._tool_definitions()
        provider_error = False
        truncation_recoveries = 0
        retrieval_seen: Dict[Tuple[str, str, str, str, str], int] = {}

        while not loop.is_finished:
            # Refresh context per putaran
            orch._refresh_bible_context(history, task)
            orch._refresh_working_state_context(history)

            # Cooperative cancellation safe boundary
            if orch._cancel_requested():
                loop.cancel(orch._cancel_reason())
                break

            # Emergency infrastructure safety limit — BUKAN completion.
            if loop.iteration >= max_steps:
                loop.fail(
                    f"Emergency safety limit tercapai: {int(loop.iteration)} "
                    f"langkah tool dieksekusi (max_steps={max_steps}). Loop "
                    f"dihentikan oleh AETHER (infrastructure), bukan keputusan "
                    f"LLM; task TIDAK selesai. Periksa kemungkinan loop runaway."
                )
                emit_event(
                    orch.event_sink,
                    "loop_safety_abort",
                    {
                        "max_steps": int(max_steps),
                        "iteration": int(loop.iteration),
                    },
                )
                break

            # Runtime context compaction
            messages, context_stats = orch._compile_context_messages(history, tools)
            emit_event(
                orch.event_sink,
                "provider_request",
                {
                    "provider": getattr(orch.provider, "name", ""),
                    "model": orch._model_name(),
                    "iteration": loop.iteration,
                    "tool_count": len(tools),
                    **context_stats,
                    **orch._policy_event_fields(),
                },
            )

            # Provider call dengan retry lifecycle
            response = orch._generate_with_retry(
                loop=loop,
                messages=messages,
                options=effective_options,
                tools=tools,
            )
            if response is None:
                if loop.status != AgentStatus.CANCELLED:
                    provider_error = True
                break

            emit_event(
                orch.event_sink,
                "provider_response",
                orch._provider_response_payload(response),
            )

            if orch._cancel_requested():
                loop.cancel(orch._cancel_reason())
                break

            truncated = bool(getattr(response, "truncated", False))
            if not truncated:
                truncation_recoveries = 0

            is_final_turn = bool(not response.has_tool_calls and not truncated)

            # Commentary natural LLM
            commentary = orch._extract_commentary(response)
            if commentary:
                clean_commentary, _ = extract_reasoning_and_content(commentary)
                clean_comp, _ = extract_reasoning_and_content(response.text or "")
                if not (is_final_turn and clean_commentary.strip() == clean_comp.strip()):
                    emit_event(
                        orch.event_sink,
                        "agent_commentary",
                        {"text": clean_commentary, "iteration": loop.iteration},
                    )

            # LLM TIDAK memanggil tool -> jawaban final
            if not response.has_tool_calls:
                if truncated:
                    truncation_recoveries += 1
                    emit_event(
                        orch.event_sink,
                        "provider_response_truncated",
                        {
                            "provider": response.provider
                            or getattr(orch.provider, "name", ""),
                            "model": response.model or orch._model_name(),
                            "finish_reason": response.finish_reason.value,
                            "recovery": truncation_recoveries,
                        },
                    )
                    history.append_user_message(orch._truncation_message().content)
                    continue

                clean_res, reasoning_text = extract_reasoning_and_content(response.text or "")
                extracted_reasoning = reasoning_text or getattr(response, "reasoning", None)
                orch._last_reasoning = extracted_reasoning
                if extracted_reasoning:
                    emit_event(
                        orch.event_sink,
                        "agent_reasoning_delta",
                        {"delta": extracted_reasoning, "reasoning": extracted_reasoning},
                    )

                allow_empty = bool(
                    effective_options
                    and getattr(effective_options, "extra", None)
                    and isinstance(effective_options.extra, dict)
                    and effective_options.extra.get("allow_empty_response", False)
                )
                if not allow_empty and not (clean_res or "").strip() and not (extracted_reasoning or "").strip():
                    provider_name = (
                        getattr(response, "provider", None)
                        or getattr(orch.provider, "name", "")
                        or "unknown"
                    )
                    emit_event(
                        orch.event_sink,
                        "provider_malformed_response",
                        {
                            "provider": provider_name,
                            "model": response.model or orch._model_name(),
                            "error": "empty_content_and_tools",
                            "iteration": loop.iteration,
                        },
                    )
                    loop.fail("Provider menghasilkan respons kosong tanpa konten teks maupun tool call (malformed response).")
                    break

                history.append_assistant_message(content=clean_res)
                loop.finish(result=clean_res)
                break

            # LLM memanggil tool: catat assistant message dengan tool calls
            model_tool_calls = response.tool_calls()
            tool_calls = [
                ToolCall.create(action.name, action.arguments, id=action.id)
                for action in model_tool_calls
            ]
            history.append_assistant_message(
                content=response.text or None, tool_calls=tool_calls
            )

            if orch._cancel_requested():
                loop.cancel(orch._cancel_reason())
                break

            actions_by_id = {
                tool_call.id: action
                for tool_call, action in zip(tool_calls, model_tool_calls)
            }

            def _emit_tool_called(tool_call: ToolCall) -> None:
                action = actions_by_id.get(tool_call.id)
                arguments = (
                    dict(getattr(action, "arguments", {}) or {})
                    if action is not None
                    else {}
                )
                emit_event(
                    orch.event_sink,
                    "tool_called",
                    {
                        "tool": tool_call.name,
                        "tool_call_id": tool_call.id,
                        "arguments": arguments,
                        "target": orch._tool_target(arguments),
                        "iteration": loop.iteration,
                    },
                )

            def _emit_tool_finished(
                tool_call: ToolCall, payload: ToolResultPayload
            ) -> None:
                action = actions_by_id.get(tool_call.id)
                arguments = (
                    dict(getattr(action, "arguments", {}) or {})
                    if action is not None
                    else {}
                )
                emit_event(
                    orch.event_sink,
                    "tool_result",
                    {
                        "tool": payload.tool_name,
                        "tool_call_id": tool_call.id,
                        "success": payload.is_success,
                        "status": (
                            "success" if payload.is_success else "error"
                        ),
                        "output": payload.output,
                        "error": None if payload.is_success else payload.to_content(),
                    },
                )
                emit_event(
                    orch.event_sink,
                    "tool_completed",
                    {
                        "tool": payload.tool_name,
                        "tool_call_id": tool_call.id,
                        "success": payload.is_success,
                        "error": None if payload.is_success else payload.to_content(),
                        "target": orch._tool_target(arguments),
                        "metadata": {},
                    },
                )
                observation = orch._tool_payload_to_observation(payload)
                emit_event(
                    orch.event_sink,
                    "agent_observation",
                    {
                        "action_id": tool_call.id,
                        "success": observation.success,
                        "error": observation.error,
                        "content": observation.content,
                        "metadata": {
                            "tool": payload.tool_name,
                            **dict(observation.metadata or {}),
                        },
                    },
                )
                emit_event(
                    orch.event_sink,
                    "observation_received",
                    {
                        "tool": payload.tool_name,
                        "tool_call_id": tool_call.id,
                        "success": payload.is_success,
                        "content": payload.output,
                    },
                )
                try:
                    identity = orch._retrieval_identity(
                        payload.tool_name, arguments
                    )
                    if identity is not None:
                        key = (
                            str(payload.tool_name),
                            str(identity["path"]),
                            str(identity["range"]),
                            str(identity["mode"]),
                            "force" if identity["force"] else "normal",
                        )
                        retrieval_seen[key] = retrieval_seen.get(key, 0) + 1
                        if retrieval_seen[key] > 1:
                            output = payload.output
                            stub = bool(
                                isinstance(output, dict)
                                and (
                                    output.get("already_available")
                                    or output.get("already_read")
                                    or output.get("already_searched")
                                )
                            )
                            emit_event(
                                orch.event_sink,
                                "retrieval_repeat",
                                {
                                    "tool": payload.tool_name,
                                    "path": identity["path"],
                                    "range": identity["range"],
                                    "mode": identity["mode"],
                                    "force": bool(identity["force"]),
                                    "stub": stub,
                                    "result": "stub" if stub else "full",
                                    "repeat_count": int(retrieval_seen[key]),
                                    "iteration": loop.iteration,
                                },
                            )
                except Exception:  # noqa: BLE001 - event tidak boleh crash
                    pass

            batch = orch.executor.execute_tool_calls(
                tool_calls,
                on_start=_emit_tool_called,
                on_complete=_emit_tool_finished,
                cancel_check=orch._cancel_requested,
            )

            # Hasil dipetakan kembali sesuai urutan input
            for action, payload in zip(model_tool_calls, batch.payloads):
                if payload is None:
                    continue
                orch._record_tool_result(history, payload)
                loop.record_action(orch.executor.to_agent_action(action))
                loop.record_observation(orch._tool_payload_to_observation(payload))
            if batch.cancelled:
                loop.cancel(orch._cancel_reason())
                break

        learning = orch._learn_from_run(task, loop)
        return OrchestratorResult(
            status=loop.status,
            result=loop.state.result,
            error=loop.state.error,
            iterations=loop.iteration,
            steps=loop.to_dict()["steps"],
            learning=learning,
            provider_error=provider_error,
            reasoning=getattr(orch, "_last_reasoning", None),
        )

    def run_continuous_loop(
        self,
        task: str,
        *,
        system_prompt: Optional[str] = None,
        max_steps: int = DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS,
        options: Optional[GenerateOptions] = None,
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> OrchestratorResult:
        """Alias untuk run() demi konsistensi penamaan."""
        return self.run(
            task=task,
            system_prompt=system_prompt,
            max_steps=max_steps,
            options=options,
            user_parts=user_parts,
        )


__all__ = ["ContinuousRunner"]
