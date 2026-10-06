"""
Test suite untuk Milestone 3 (Tahap C — Efisiensi Token, Thinking Adapter, & Skalabilitas).
Menguji:
1. OPT-01 / R-AI-01: Pengecekan error non-retryable pada AgentOrchestrator (berhenti seketika tanpa retry loop berulang).
2. OPT-05 / R-AI-05: Observabilitas OSError pada ConsultantSessionStore (last_save_error dan graceful degradation).
"""
import json
import tempfile
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_ai.config import settings as settings_mod
from agent_ai.core.orchestrator import AgentOrchestrator
from agent_ai.core.executor import ToolExecutor
from agent_ai.providers.openai_compatible import OpenAICompatibleProvider
from agent_ai.providers.base import GenerateOptions, GenerateResult
from agent_ai.consultant.store import ConsultantSessionStore


class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    pass


class FakeScriptedProvider(OpenAICompatibleProvider):
    name = "fake-provider"

    def __init__(self, script=None):
        self.config = SimpleNamespace(model="test-model")
        self.script = list(script or [])
        self.calls = 0

    def generate(self, prompt=None, messages=None, options=None, tools=None, tool_choice=None):
        idx = self.calls
        self.calls += 1
        if idx < len(self.script):
            item = self.script[idx]
        else:
            item = self.script[-1]
        if isinstance(item, BaseException) or (isinstance(item, type) and issubclass(item, BaseException)):
            raise item if isinstance(item, BaseException) else item("provider error")
        return GenerateResult(text=str(item), model="test-model", provider="fake-provider")


def test_opt01_non_retryable_error_aborts_immediately():
    """Memverifikasi bahwa error non-retryable (AuthenticationError) langsung
    menghentikan retry loop pada percobaan pertama tanpa sleep berulang."""
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        settings_file = tmp_dir / "settings.json"
        settings_file.write_text(
            json.dumps({"api_retry": {"failed_count": 3, "failed_sleep": 1.0}}),
            encoding="utf-8"
        )
        with patch.object(settings_mod, "SETTINGS_PATH", settings_file):
            provider = FakeScriptedProvider([AuthenticationError("401 Unauthorized - invalid api key")])
            orchestrator = AgentOrchestrator(
                provider=provider,
                executor=ToolExecutor(),
                options=GenerateOptions(model="test-model"),
                use_continuous_loop=True,
            )

            with patch("time.sleep") as mock_sleep:
                result = orchestrator.run("Test task")

                # Status FAILED
                assert result.status.name == "FAILED" or str(result.status) == "AgentStatus.FAILED"
                # Provider call seharusnya hanya dipanggil 1 kali karena error non-retryable
                assert provider.calls == 1
                # time.sleep tidak boleh dipanggil sama sekali
                assert mock_sleep.call_count == 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_opt01_retryable_error_exhausts_retries():
    """Memverifikasi bahwa exception retryable (mis. RateLimitError) tetap mencoba
    mengulang hingga batas retry tercapai."""
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        settings_file = tmp_dir / "settings.json"
        settings_file.write_text(
            json.dumps({"api_retry": {"failed_count": 2, "failed_sleep": 0.01}}),
            encoding="utf-8"
        )
        with patch.object(settings_mod, "SETTINGS_PATH", settings_file):
            provider = FakeScriptedProvider([RateLimitError("429 Too Many Requests")])
            orchestrator = AgentOrchestrator(
                provider=provider,
                executor=ToolExecutor(),
                options=GenerateOptions(model="test-model"),
                use_continuous_loop=True,
            )

            with patch("time.sleep") as mock_sleep:
                result = orchestrator.run("Test task")

                assert result.status.name == "FAILED" or str(result.status) == "AgentStatus.FAILED"
                # 1 attempt awal + 2 retry = 3 kali
                assert provider.calls == 3
                # Sleep dipanggil 2 kali
                assert mock_sleep.call_count == 2
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_opt05_store_oserror_recorded_in_last_save_error():
    """Memverifikasi bahwa kegagalan penulisan disk (OSError) pada ConsultantSessionStore
    tercatat dalam last_save_error dan tidak menyebabkan crash unhandled."""
    temp_dir = tempfile.mkdtemp()
    try:
        json_path = Path(temp_dir) / "consultant_sessions.json"
        store = ConsultantSessionStore(path=str(json_path))
        session = store.create_session(session_id="test_sess_01", project_id="proj_1", title="Test Session")
        assert store.last_save_error is None

        # Simulasikan disk/filesystem error pada open()
        with patch.object(Path, "open", side_effect=OSError("Disk quota exceeded")):
            store.rename_session(session_id="test_sess_01", title="Renamed Title", project_id="proj_1")
            assert store.last_save_error is not None
            assert "Disk quota exceeded" in store.last_save_error

        # Pemanggilan berikutnya yang sukses harus membersihkan last_save_error
        store.rename_session(session_id="test_sess_01", title="Clean Title", project_id="proj_1")
        assert store.last_save_error is None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
