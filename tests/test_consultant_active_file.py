"""Unit tests for active editor file and semantic context in ConsultantService."""

from pathlib import Path
import pytest

from agent_ai.consultant.service import ConsultantService, _build_active_file_context
from agent_ai.providers.base import BaseProvider, GenerateResult
from agent_ai.core.response import FinishReason, LLMResponse


def test_build_active_file_context_with_content(tmp_path: Path) -> None:
    active_file = {
        "path": "src/App.vue",
        "content": "<template><div>Hello World</div></template>",
        "cursor_line": 10,
        "selection": "<div>Hello World</div>",
    }
    block = _build_active_file_context(active_file, tmp_path)

    assert "# Berkas Aktif dari Text Editor: src/App.vue" in block
    assert "Posisi Kursor: Baris 10" in block
    assert "Teks Terpilih (Selection):" in block
    assert "<div>Hello World</div>" in block
    assert "<template><div>Hello World</div></template>" in block


def test_build_active_file_context_reads_from_disk_if_content_missing(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    f = src_dir / "index.js"
    f.write_text("console.log('from disk');", encoding="utf-8")

    active_file = {"path": "src/index.js"}
    block = _build_active_file_context(active_file, tmp_path)

    assert "# Berkas Aktif dari Text Editor: src/index.js" in block
    assert "console.log('from disk');" in block


def test_consultant_service_injects_active_file_into_llm_prompt(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    class MockProvider(BaseProvider):
        name = "mock"

        def is_available(self) -> bool:
            return True

        def generate(self, prompt=None, messages=None, options=None, tools=None, tool_choice=None):
            if messages:
                for m in messages:
                    c = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")
                    received_prompts.append(str(c))
            return GenerateResult(text="Analisis berkas aktif selesai.", model="mock", provider=self.name)

        def normalize_response(self, result):
            return LLMResponse(text=result.text, actions=[], finish_reason=FinishReason.STOP)

    svc = ConsultantService()
    prov = MockProvider()

    res = svc.consult(
        "tolong review file ini",
        provider=prov,
        root=str(tmp_path),
        mode="quick",
        active_file={
            "path": "docs/architecture.md",
            "content": "# Aegis Architecture\nAll systems nominal.",
            "cursor_line": 5,
        },
    )

    assert res.status == "done"
    assert res.reply == "Analisis berkas aktif selesai."

    full_prompt = "\n".join(received_prompts)
    assert "# Berkas Aktif dari Text Editor: docs/architecture.md" in full_prompt
    assert "# Aegis Architecture" in full_prompt
    assert "Posisi Kursor: Baris 5" in full_prompt
