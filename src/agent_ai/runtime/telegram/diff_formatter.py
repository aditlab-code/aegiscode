from __future__ import annotations

import html
from dataclasses import dataclass
from typing import List


@dataclass
class GitFileDiffStat:
    """Statistik delta perubahan satu berkas kode."""

    path: str
    insertions: int
    deletions: int


def format_diff_summary(
    action_name: str,
    description: str,
    files: List[GitFileDiffStat],
) -> str:
    """Format ringkasan diff yang padat dan ramah layar ponsel."""
    esc_action = html.escape(action_name)
    esc_desc = html.escape(description)

    lines = [
        f"⚠️ <b>Approval Diperlukan: {esc_action}</b>\n",
        f"📝 <i>{esc_desc}</i>\n",
        "<b>Perubahan Berkas:</b>",
    ]

    if not files:
        lines.append("• <i>Tidak ada berkas langsung yang dimodifikasi.</i>")
    else:
        for f in files:
            esc_path = html.escape(f.path)
            lines.append(f"• <code>{esc_path}</code> (+{f.insertions} / -{f.deletions})")

    lines.append("\nTekan tombol di bawah untuk memutuskan:")
    return "\n".join(lines)
