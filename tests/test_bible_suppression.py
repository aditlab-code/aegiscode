"""Unit tests for empty Project Bible template suppression."""

from pathlib import Path
from agent_ai.projects.retrieval import BibleRetriever, retrieve_bible_context


class DummyEmptyBrain:
    """Mock ProjectBrain with zero entries across all categories."""

    class MockIntelligence:
        categories = ["architecture", "conventions", "facts"]

        def read_category(self, category: str):
            return []

    def __init__(self) -> None:
        self.intelligence = self.MockIntelligence()

    def get_context(self):
        return type("Context", (), {"text": ""})()


def test_empty_bible_retrieval_returns_empty_text() -> None:
    brain = DummyEmptyBrain()
    retriever = BibleRetriever(brain)
    result = retriever.retrieve("architecture overview")

    assert result is not None
    assert result.level == "empty"
    assert result.total_entries == 0
    assert result.selected_count == 0
    # Must NOT return verbose placeholder lines when empty
    assert result.text == ""


def test_retrieve_bible_context_empty_is_empty() -> None:
    brain = DummyEmptyBrain()
    result = retrieve_bible_context(brain, "explain architecture")
    assert result is not None
    assert result.text == ""
