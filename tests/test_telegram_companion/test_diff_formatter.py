from __future__ import annotations

import pytest

from agent_ai.runtime.telegram.diff_formatter import (
    GitFileDiffStat,
    format_diff_summary,
)


def test_format_diff_summary_with_files():
    files = [
        GitFileDiffStat(path="src/agent_ai/core.py", insertions=12, deletions=3),
        GitFileDiffStat(path="tests/test_core.py", insertions=45, deletions=0),
    ]
    summary = format_diff_summary(
        action_name="git_commit",
        description="Refactor runtime execution engine",
        files=files,
    )

    assert "⚠️ <b>Approval Diperlukan: git_commit</b>" in summary
    assert "Refactor runtime execution engine" in summary
    assert "<code>src/agent_ai/core.py</code> (+12 / -3)" in summary
    assert "<code>tests/test_core.py</code> (+45 / -0)" in summary
    assert "Tekan tombol di bawah untuk memutuskan:" in summary


def test_format_diff_summary_empty_files():
    summary = format_diff_summary(
        action_name="shell_command",
        description="Run migrations",
        files=[],
    )
    assert "⚠️ <b>Approval Diperlukan: shell_command</b>" in summary
    assert "Tidak ada berkas langsung yang dimodifikasi" in summary


def test_format_diff_summary_escapes_html():
    summary = format_diff_summary(
        action_name="update <tag>",
        description="Fix <script> alert & crash",
        files=[GitFileDiffStat(path="src/<utils>.py", insertions=1, deletions=1)],
    )
    assert "&lt;tag&gt;" in summary
    assert "&lt;script&gt;" in summary
    assert "&lt;utils&gt;.py" in summary
