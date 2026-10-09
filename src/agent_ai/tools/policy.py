"""Tool eksplisit untuk eskalasi Execution Policy Agent (Decommissioned).

Sistem kini beroperasi penuh dalam mode otonom terpadu (Unified Autonomous Execution).
Tool ini dipertahankan sebagai no-op stub kompatibel agar pemanggil lama tidak rusak.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from agent_ai.tools.base import BaseTool, ToolValidationError

logger = logging.getLogger(__name__)


class RequestPolicyEscalationTool(BaseTool):
    name = "request_policy_escalation"
    description = (
        "Meminta eskalasi mode kebijakan eksekusi Agent. "
        "Catatan: Mode eksekusi otonom kini aktif penuh secara permanen."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Alasan teknis eskalasi.",
            },
            "target_mode": {
                "type": "string",
                "description": "Mode tujuan (opsional).",
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
        target_mode = arguments.get("target_mode") or "agents"

        effective_mode = target_mode
        if self.escalator is not None:
            try:
                res = self.escalator(str(reason).strip(), target_mode)
                effective_mode = getattr(res, "effective_mode", target_mode) or target_mode
            except Exception as exc:
                logger.warning("Optional policy escalator hook failed (non-critical): %s", exc)

        return {
            "success": True,
            "effective_mode": str(effective_mode),
            "reason": str(reason).strip(),
            "message": "Policy escalation decommissioned: unified autonomous execution is permanently active.",
        }


__all__ = ["RequestPolicyEscalationTool"]
