"""Helper penanganan hasil tool dan observasi untuk orchestration runtime.

Menangani konversi ToolResultPayload ke AgentObservation, pencatatan hasil
tool ke histori percakapan (termasuk multimodal/vision split), dan pesan
konten observasi pendamping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agent_ai.core.history import ConversationHistory
from agent_ai.core.models import AgentObservation
from agent_ai.core.observability import EventSink, emit as emit_event
from agent_ai.core.types import ToolResultPayload


def vision_content_message(output: Any) -> str:
    """Teks pendamping pesan multimodal (menyebut path bila tersedia)."""
    path = output.get("path") if isinstance(output, dict) else None
    if path:
        return (
            f"[view_image] Konten gambar dari '{path}' dilampirkan sebagai "
            "input multimodal; gunakan gambar ini untuk menjawab."
        )
    return (
        "[view_image] Konten gambar dilampirkan sebagai input multimodal; "
        "gunakan gambar ini untuk menjawab."
    )


def tool_payload_to_observation(payload: ToolResultPayload) -> AgentObservation:
    """Ubah ToolResultPayload menjadi AgentObservation (bookkeeping step).

    HANYA dipakai untuk mencatat step (observability). Tidak menentukan
    completion dan TIDAK pernah dikirim ke LLM: histori LLM memakai pesan
    role "tool" lewat ConversationHistory.
    """
    if payload.is_success:
        return AgentObservation(
            content=payload.output,
            success=True,
            metadata={"tool": payload.tool_name},
        )
    return AgentObservation(
        content=None,
        success=False,
        error=payload.to_content(),
        metadata={"tool": payload.tool_name, "tool_error": True},
    )


def record_tool_result(
    history: ConversationHistory,
    payload: ToolResultPayload,
    event_sink: Optional[EventSink] = None,
) -> None:
    """Catat hasil satu tool ke histori sebagai pesan role "tool".

    Backward compatible: hasil tool biasa tetap SATU pesan role "tool"
    (teks) seperti sebelumnya.

    ADDITIVE (Vision/multimodal): bila hasil tool membawa content part
    gambar (kunci ``MULTIMODAL_PARTS_KEY``, mis. dari tool ``view_image``),
    part gambar DIPISAHKAN dari teks: teks tetap menjadi pesan role "tool"
    (kontrak tool calling — pesan tool harus text-only), sedangkan part
    gambar dikirim sebagai pesan user multimodal LANJUTAN sehingga provider
    adapter menerjemahkannya menjadi input image (image_url / Ollama images).
    Dengan begitu Agent benar-benar MELIHAT gambar lewat mekanisme provider
    multimodal yang sudah ada, tanpa menumpahkan base64 ke pesan tool.
    """
    try:
        from agent_ai.tools.base import split_multimodal_parts

        cleaned_output, parts = split_multimodal_parts(payload.output)
    except Exception:  # noqa: BLE001 - bridge multimodal tidak boleh gagalkan task
        cleaned_output, parts = payload.output, None

    if not parts:
        history.append_tool_result(
            payload.tool_call_id, payload.tool_name, payload.to_content()
        )
        return

    content = ToolResultPayload.stringify(cleaned_output)
    history.append_tool_result(payload.tool_call_id, payload.tool_name, content)
    # Pesan user lanjutan membawa gambar sebagai input multimodal. Pesan ini
    # TIDAK mengubah kontrak tool calling (assistant tool_calls -> tool ->
    # user) dan tidak mengubah keputusan LLM kapan task selesai.
    history.append_user_message(
        vision_content_message(cleaned_output), parts=parts
    )
    if event_sink is not None:
        emit_event(
            event_sink,
            "vision_image_attached",
            {
                "tool": payload.tool_name,
                "parts": len(parts),
            },
        )


# Kompatibilitas alias privat
_record_tool_result = record_tool_result
_vision_content_message = vision_content_message
_tool_payload_to_observation = tool_payload_to_observation

__all__ = [
    "record_tool_result",
    "tool_payload_to_observation",
    "vision_content_message",
    "_record_tool_result",
    "_tool_payload_to_observation",
    "_vision_content_message",
]
