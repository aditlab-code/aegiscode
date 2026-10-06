"""Kontrak Terpadu Normalisasi Respons Provider untuk Agent Orchestrator.

Menstandarkan protokol keluaran provider LLM ke objek internal LLMResponse,
menjamin invariant:
- Format argumen tool calls terstandardisasi (dict).
- Tool call ID selalu terisi (fallback UUID deterministik bila kosong).
- Parsing JSON malformed pada tool call arguments ditangani dengan aman tanpa crash.
- Penanganan konten teks dan reasoning bersih tanpa metadata HTTP yang bocor.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from agent_ai.core.response import ActionType, FinishReason, LLMAction, LLMResponse

logger = logging.getLogger(__name__)


def normalize_tool_call_arguments(raw_args: Any) -> Dict[str, Any]:
    """Konversi argumen tool call menjadi Dict[str, Any] secara aman."""
    if isinstance(raw_args, dict):
        return raw_args
    if not raw_args:
        return {}
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            if isinstance(parsed, dict):
                return parsed
            return {"_raw": parsed}
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Gagal mengurai JSON argumen tool call '%s': %s", raw_args, exc)
            return {"_raw_string": raw_args, "_parse_error": str(exc)}
    return {"_raw": raw_args}


def sanitize_provider_response(provider: Any, gen_result: Any) -> LLMResponse:
    """Normalisasi GenerateResult dari provider LLM ke kontrak internal LLMResponse."""
    if hasattr(provider, "normalize_response") and callable(provider.normalize_response):
        response: LLMResponse = provider.normalize_response(gen_result)
    elif isinstance(gen_result, LLMResponse):
        response = gen_result
    else:
        text = getattr(gen_result, "text", "") or ""
        reasoning = getattr(gen_result, "reasoning", None)
        response = LLMResponse(
            text=text,
            finish_reason=FinishReason.STOP,
            reasoning=reasoning,
        )

    # Validasi dan sanitasi actions / tool calls
    if response.actions:
        sanitized_actions: List[LLMAction] = []
        for action in response.actions:
            call_id = getattr(action, "id", None) or f"call_{uuid.uuid4().hex[:8]}"
            name = getattr(action, "name", "") or "unknown_tool"
            raw_args = getattr(action, "arguments", {})
            norm_args = normalize_tool_call_arguments(raw_args)

            sanitized_actions.append(
                LLMAction(
                    id=str(call_id),
                    name=str(name),
                    arguments=norm_args,
                    type=getattr(action, "type", ActionType.TOOL_CALL),
                )
            )
        response.actions = sanitized_actions

    return response
