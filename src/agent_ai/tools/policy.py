"""Tool eksplisit untuk eskalasi Execution Policy Agent (Fast, Balanced, Deep).

Memungkinkan LLM secara mandiri meminta eskalasi mode kerja bila kompleksitas
tugas melebihi estimasi awal (mis. membutuhkan penelusuran lebih banyak berkas).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from agent_ai.tools.base import BaseTool, ToolExecutionError, ToolValidationError


class RequestPolicyEscalationTool(BaseTool):
    name = "request_policy_escalation"
    description = (
        "Meminta eskalasi mode kebijakan eksekusi Agent (misalnya dari 'fast' ke 'balanced', "
        "atau dari 'balanced' ke 'deep') apabila batas kuota pembacaan berkas tercapai atau "
        "tugas memerlukan pemahaman arsitektur multi-berkas lebih luas. "
        "Eskalasi hanya boleh bernilai MAJU (fast -> balanced -> deep)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Alasan teknis mengapa eskalasi mode diperlukan.",
            },
            "target_mode": {
                "type": "string",
                "description": "Mode tujuan: 'balanced' atau 'deep'. Kosongkan untuk otomatis naik 1 tingkat.",
            },
        },
        "required": ["reason"],
    }

    def __init__(
        self,
        escalator: Optional[Callable[[str, Optional[str]], Any]] = None,
    ) -> None:
        self.escalator = escalator

    def set_escalator(self, escalator: Optional[Callable[[str, Optional[str]], Any]]) -> None:
        self.escalator = escalator

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        reason = arguments.get("reason")
        if not reason or not isinstance(reason, str) or not reason.strip():
            raise ToolValidationError("Argumen 'reason' wajib diisi dan tidak boleh kosong.")
        target_mode = arguments.get("target_mode")
        if target_mode is not None and not isinstance(target_mode, str):
            raise ToolValidationError("Argumen 'target_mode' harus berupa string.")

        if self.escalator is None:
            raise ToolExecutionError(
                "Mekanisme eskalasi policy tidak tersedia pada sesi/runtime saat ini."
            )

        try:
            result = self.escalator(reason.strip(), target_mode.strip() if target_mode else None)
        except Exception as exc:
            raise ToolExecutionError(f"Gagal melakukan eskalasi policy: {exc}") from exc

        if result is None:
            raise ToolExecutionError("Eskalasi policy tidak menghasilkan perubahan atau tidak aktif.")

        effective_mode = getattr(result, "effective_mode", None)
        if effective_mode is None and isinstance(result, dict):
            effective_mode = result.get("effective_mode")

        return {
            "success": True,
            "effective_mode": str(effective_mode),
            "reason": reason.strip(),
            "message": (
                f"Execution policy berhasil dieskalasi ke mode '{effective_mode}'. "
                "Batas kuota pembacaan berkas telah diperluas."
            ),
        }


__all__ = ["RequestPolicyEscalationTool"]
