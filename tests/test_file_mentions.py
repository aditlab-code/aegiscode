"""Unit tests for @file mention resolution."""

from pathlib import Path
import pytest

from agent_ai.contextbuilder.mention import (
    extract_mention_paths,
    resolve_file_mentions,
)


def test_extract_mention_paths() -> None:
    text = "Please check @README.md and also @src/App.vue for details"
    paths = extract_mention_paths(text)
    assert paths == ["README.md", "src/App.vue"]


def test_extract_mention_paths_ignores_email() -> None:
    text = "Contact support@example.com or check @docs/setup.md"
    paths = extract_mention_paths(text)
    assert paths == ["docs/setup.md"]


def test_resolve_file_mentions_attaches_existing_files(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# My Awesome Project\nThis is a test project.", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code = src_dir / "index.js"
    code.write_text("console.log('hello world');", encoding="utf-8")

    prompt = "@README.md tolong jelaskan project ini dan @src/index.js"
    enriched, attachments = resolve_file_mentions(prompt, tmp_path)

    assert len(attachments) == 2
    assert attachments[0]["path"] == "README.md"
    assert "My Awesome Project" in attachments[0]["content"]
    assert attachments[1]["path"] == "src/index.js"
    assert "console.log" in attachments[1]["content"]

    assert "# File Lampiran dari Mention (@file):" in enriched
    assert "## File: README.md" in enriched
    assert "## File: src/index.js" in enriched
    assert "# My Awesome Project" in enriched


def test_resolve_file_mentions_blocks_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret_password", encoding="utf-8")

    prompt = "Read @../secret.txt please"
    enriched, attachments = resolve_file_mentions(prompt, tmp_path)

    assert len(attachments) == 0
    assert enriched == prompt
    assert "secret_password" not in enriched


def test_resolve_file_mentions_graceful_on_missing_file(tmp_path: Path) -> None:
    prompt = "Check @does_not_exist.txt"
    enriched, attachments = resolve_file_mentions(prompt, tmp_path)

    assert len(attachments) == 0
    assert enriched == prompt


def test_consultant_service_resolves_file_mentions_in_quick_mode(tmp_path: Path) -> None:
    from agent_ai.consultant.service import ConsultantService
    from agent_ai.providers.base import BaseProvider, GenerateResult
    from agent_ai.core.response import FinishReason, LLMResponse

    # Create README.md in test workspace
    readme = tmp_path / "README.md"
    readme.write_text("# oh-my-javanese\nLanguage processor for Javanese.", encoding="utf-8")

    received_prompts: list[str] = []

    class EchoProvider(BaseProvider):
        name = "echo"

        def is_available(self) -> bool:
            return True

        def generate(self, prompt=None, messages=None, options=None, tools=None, tool_choice=None):
            if messages:
                for m in messages:
                    content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")
                    received_prompts.append(str(content))
            return GenerateResult(text="Analisis README selesai.", model="echo", provider=self.name)

        def normalize_response(self, result):
            return LLMResponse(text=result.text, actions=[], finish_reason=FinishReason.STOP)

    svc = ConsultantService()
    prov = EchoProvider()

    # Call in default "quick" mode
    res = svc.consult(
        "@README.md tolong jelaskan project ini",
        provider=prov,
        root=str(tmp_path),
        mode="quick",
    )

    assert res.status == "done"
    assert res.reply == "Analisis README selesai."
    # The provider MUST have received the actual content of README.md!
    assert len(received_prompts) > 0
    full_user_prompt = "\n".join(received_prompts)
    assert "# oh-my-javanese" in full_user_prompt
    assert "Language processor for Javanese." in full_user_prompt
    assert "File Lampiran dari Mention (@file):" in full_user_prompt

