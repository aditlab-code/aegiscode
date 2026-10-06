"""Pengujian regresi untuk Milestone 1 (Tahap A) — Integritas Inti dan Batas Aman AI.

Mencakup pengujian otomatis untuk:
- AI-01: Pemfilteran metadata internal runtime pada payload provider (JSON serializable).
- AI-02: Batas read-only Consultant terhadap perintah evaluasi skrip interpreter inline.
- AI-03: Siklus pembatalan deterministik pada orchestrator retry loop.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from agent_ai.consultant.tools import consultant_command_violation
from agent_ai.core.orchestrator import AgentOrchestrator
from agent_ai.providers.base import (
    GenerateOptions,
    Message,
    filter_provider_extra,
)
from agent_ai.providers.openai_compatible import OpenAICompatibleProvider


# --------------------------------------------------------------------------- #
# AI-01: Pemfilteran metadata runtime pada provider OpenAI-compatible
# --------------------------------------------------------------------------- #
class DummyOpenAIProvider(OpenAICompatibleProvider):
    """Subclass pengujian untuk memverifikasi _build_payload tanpa koneksi jaringan."""

    def __init__(self) -> None:
        self.config = MagicMock()
        self.config.model = "test-model"
        self.supports_model_discovery = False
        self.send_model_field = True


def test_ai01_filter_provider_extra_removes_internal_keys_and_callables():
    """filter_provider_extra wajib membuang kunci internal dan objek callable."""
    raw_extra = {
        "event_sink": lambda *a: None,
        "execution_policy": {"effective_mode": "balanced"},
        "mode": "balanced",
        "workspace_root": "/tmp/test",
        "runtime_context": {"foo": "bar"},
        "seed": 42,
        "custom_param": "valid_value",
    }
    filtered = filter_provider_extra(raw_extra)

    assert "event_sink" not in filtered
    assert "execution_policy" not in filtered
    assert "mode" not in filtered
    assert "workspace_root" not in filtered
    assert "runtime_context" not in filtered
    assert filtered.get("seed") == 42
    assert filtered.get("custom_param") == "valid_value"


def test_ai01_openai_provider_build_payload_serializable_with_event_sink():
    """_build_payload wajib menghasilkan JSON yang dapat diserialisasi meskipun extra memuat event_sink."""
    provider = DummyOpenAIProvider()
    options = GenerateOptions(
        model="gpt-4o",
        temperature=0.7,
        max_tokens=1000,
        extra={
            "event_sink": lambda *a: None,
            "execution_policy": {"effective_mode": "deep"},
            "workspace_root": "/path/to/workspace",
            "seed": 12345,
        },
    )
    messages = [Message(role="user", content="Halo")]
    payload = provider._build_payload(prompt=None, messages=messages, options=options)

    # Validasi bahwa json.dumps tidak melempar TypeError
    serialized = json.dumps(payload)
    parsed = json.loads(serialized)

    assert parsed["model"] == "gpt-4o"
    assert parsed["seed"] == 12345
    assert "event_sink" not in parsed
    assert "execution_policy" not in parsed
    assert "workspace_root" not in parsed


# --------------------------------------------------------------------------- #
# AI-02: Penegakan batas read-only terhadap command interpreter di Consultant
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "cmd",
    [
        'python -c "open(\'test.txt\', \'w\').write(\'data\')"',
        'python3 -c "import os; os.remove(\'a.py\')"',
        'node -e "require(\'fs\').writeFileSync(\'b.js\', \'\')"',
        'node --eval "process.exit(1)"',
        'perl -e "unlink(\'x\')"',
        'ruby -e "File.delete(\'y\')"',
        'bash -c "echo evil > file.txt"',
        'sh -c "rm -rf ."',
    ],
)
def test_ai02_consultant_blocks_inline_script_evaluation(cmd: str):
    """Perintah evaluasi skrip inline wajib ditolak oleh guard Consultant."""
    violation = consultant_command_violation(cmd)
    assert violation is not None
    assert "evaluasi kode inline" in violation or "berpotensi memodifikasi file" in violation or "redirect" in violation


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "git diff",
        "git log -n 5",
        "pytest tests/",
        "python -m pytest",
        "npm run build",
        "npm test",
    ],
)
def test_ai02_consultant_allows_diagnostic_commands(cmd: str):
    """Perintah diagnostik dan pengujian yang sah tetap diizinkan."""
    violation = consultant_command_violation(cmd)
    assert violation is None


# --------------------------------------------------------------------------- #
# AI-03: Pembatalan saat jeda retry tidak memicu pemanggilan provider tambahan
# --------------------------------------------------------------------------- #
def test_ai03_cancel_during_retry_stops_further_provider_calls():
    """Pembatalan selama jeda retry memastikan provider hanya dipanggil sekali."""
    call_count = 0

    def mock_call_provider(**kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Transient network timeout")

    # Buat instance minimal AgentOrchestrator dengan mocks
    orchestrator = MagicMock(spec=AgentOrchestrator)
    orchestrator.provider = MagicMock()
    orchestrator.provider.name = "mock_provider"
    orchestrator._model_name = MagicMock(return_value="mock-model")
    orchestrator._api_retry_policy = MagicMock(return_value=(2, 0.2))  # 2 retry, 0.2 detik sleep
    orchestrator._next_llm_round = MagicMock(return_value=1)
    orchestrator._call_provider = mock_call_provider
    orchestrator.event_sink = None

    cancel_requested = False
    orchestrator._cancel_requested = lambda: cancel_requested
    orchestrator._cancel_reason = lambda: "User requested cancel"

    mock_loop = MagicMock()

    # Jalankan _generate_with_retry di thread terpisah atau ubah cancel_requested saat jeda
    # Kita intercept pemanggilan sleep untuk mengubah flag cancel
    original_sleep = time.sleep

    def mock_sleep(duration):
        nonlocal cancel_requested
        cancel_requested = True
        original_sleep(0.01)

    # Gunakan fungsi asli _generate_with_retry
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(time, "sleep", mock_sleep)
        res = AgentOrchestrator._generate_with_retry(
            orchestrator,
            loop=mock_loop,
            messages=[],
            options=None,
            tools=None,
        )

    assert res is None
    # Pemanggilan provider harus berhenti pada percobaan pertama
    assert call_count == 1
    mock_loop.cancel.assert_called_once_with("User requested cancel")
