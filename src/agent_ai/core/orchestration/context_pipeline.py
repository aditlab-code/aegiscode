"""Pipeline perakitan dan kompilasi konteks pesan untuk Agent Orchestrator (Fase 2 PR-MVP-3).

Mengelola:
- Perakitan system prompt, environment context, policy directives, dan user parts.
- Integrasi Project Intelligence (Brain) & Project Bible.
- Task-scoped Bible context lifecycle (anti duplikasi, auto-refresh per-turn).
- Working State injection & refresh.
- Runtime context compaction (sliding window & tool compaction, budget derivation).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from agent_ai.core.bible_lifecycle import (
    BibleContextState,
    bible_source_revision,
    fingerprint_text,
    resolve_bible_root,
)
from agent_ai.core.history import ConversationHistory
from agent_ai.core.observability import emit as emit_event
from agent_ai.core.orchestration.retrieval_state import sync_retrieval_cache
from agent_ai.providers.base import Message, ToolDefinition

if TYPE_CHECKING:  # pragma: no cover
    from agent_ai.core.orchestrator import AgentOrchestrator

#: Estimasi kasar karakter per token
_KNOWLEDGE_CHARS_PER_TOKEN = 4


class ContextPipeline:
    """Pipeline perakitan, seleksi knowledge, dan kompilasi pesan."""

    def __init__(self, orchestrator: Any = None) -> None:
        self.orchestrator = orchestrator
        self._bible_context_state: Optional[BibleContextState] = None
        self._last_working_state_text: Optional[str] = None

    def _has_orch_override(self, attr_name: str) -> bool:
        if self.orchestrator is None:
            return False
        return attr_name in getattr(self.orchestrator, "__dict__", {})

    # ------------------------------------------------------------------ #
    # History & initial messages
    # ------------------------------------------------------------------ #
    def build_messages(
        self,
        task: str,
        history: List[Message],
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Message]:
        """Bangun daftar pesan untuk LLM: system + task + history."""
        messages: List[Message] = []
        system_prompt = (
            getattr(self.orchestrator, "system_prompt", None)
            if self.orchestrator is not None
            else None
        )
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        environment = self.environment_context_message()
        if environment is not None:
            messages.append(environment)
        policy_directive = self.policy_directive_message()
        if policy_directive is not None:
            messages.append(policy_directive)
        messages.append(Message(role="user", content=task, parts=user_parts))
        messages.extend(history)
        return messages

    # ------------------------------------------------------------------ #
    # Environment & Policy Directives
    # ------------------------------------------------------------------ #
    def environment_context_message(self) -> Optional[Message]:
        """Environment Context (project-local) sebagai system message."""
        if self._has_orch_override("_environment_context_message"):
            return self.orchestrator._environment_context_message()
        env_text = (
            getattr(self.orchestrator, "environment_context", "")
            if self.orchestrator is not None
            else ""
        )
        text = (env_text or "").strip()
        if not text:
            return None
        return Message(role="system", content=text)

    def policy_directive_message(self) -> Optional[Message]:
        """Arahan operasional Execution Policy (Fast/Balanced/Deep)."""
        if self._has_orch_override("_policy_directive_message"):
            return self.orchestrator._policy_directive_message()
        mode = None
        if self.orchestrator is not None:
            mode = getattr(self.orchestrator, "effective_mode", None)
        if not mode:
            return None
        try:
            from agent_ai.runtime.policy import directive_prompt_for_mode

            text = directive_prompt_for_mode(mode)
            if not text:
                return None
            return Message(role="system", content=text)
        except Exception:  # noqa: BLE001
            return None


    # ------------------------------------------------------------------ #
    # Brain & Bible Context Lifecycle
    # ------------------------------------------------------------------ #
    def bible_context_state(self) -> BibleContextState:
        """State Bible context untuk task-scope aktif."""
        if self.orchestrator is not None and hasattr(
            self.orchestrator, "_bible_context_state"
        ):
            state = getattr(self.orchestrator, "_bible_context_state", None)
            if state is None:
                state = BibleContextState()
                self.orchestrator._bible_context_state = state
            return state
        if self._bible_context_state is None:
            self._bible_context_state = BibleContextState()
        return self._bible_context_state

    def begin_bible_context_scope(self, scope: str = "") -> BibleContextState:
        """Mulai scope task baru: Bible dianggap belum pernah dikirim."""
        state = BibleContextState(scope=scope or "")
        if self.orchestrator is not None:
            self.orchestrator._bible_context_state = state
        self._bible_context_state = state
        return state

    def invalidate_bible_context(self, reason: str = "") -> BibleContextState:
        """Tandai context Bible pada scope ini tidak valid lagi."""
        return self.bible_context_state().invalidate(reason)

    def bible_context_state_dict(self) -> Dict[str, Any]:
        """Ringkasan state Bible context tanpa isi konten."""
        return self.bible_context_state().to_dict()

    def bible_sources_revision(self) -> Optional[str]:
        """Revision murah sumber Bible (nama+size+mtime tiap kategori)."""
        if self._has_orch_override("_bible_sources_revision"):
            return self.orchestrator._bible_sources_revision()
        brain = (
            getattr(self.orchestrator, "brain", None)
            if self.orchestrator is not None
            else None
        )
        try:
            return bible_source_revision(resolve_bible_root(brain))
        except Exception:
            return None

    def mark_bible_context_sent(
        self,
        state: BibleContextState,
        text: str,
        revision: Optional[str],
        query: str,
    ) -> bool:
        """Catat context Bible yang dikirim. False = isi identik (jangan kirim)."""
        if self._has_orch_override("_mark_bible_context_sent"):
            return self.orchestrator._mark_bible_context_sent(
                state, text, revision, query
            )
        fingerprint = fingerprint_text(text or "")
        return state.mark_injected(fingerprint, revision, query=query)

    def brain_context_message(self, query: str = "") -> Optional[Message]:
        """Ambil context Project Intelligence sebagai system message."""
        if self._has_orch_override("_brain_context_message"):
            return self.orchestrator._brain_context_message(query)
        brain = (
            getattr(self.orchestrator, "brain", None)
            if self.orchestrator is not None
            else None
        )
        if brain is None:
            return None
        text = self.retrieve_knowledge_context(query)
        text = self.fit_knowledge_context(text)
        if not text.strip():
            return None
        return Message(role="system", content=text)

    def bible_context_message_for_task(self, task: str = "") -> Optional[Message]:
        """Retrieval existing + lifecycle gate untuk satu task."""
        if self._has_orch_override("_bible_context_message_for_task"):
            return self.orchestrator._bible_context_message_for_task(task)
        state = self.bible_context_state()
        revision = self.bible_sources_revision()
        if not state.needs_retrieval(revision):
            state.record_skip()
            return None
        message = self.brain_context_message(task)
        if message is None:
            return None
        if not self.mark_bible_context_sent(state, message.content, revision, task):
            state.record_skip()
            return None
        return message

    def refresh_bible_context(
        self, history: ConversationHistory, task: str = ""
    ) -> bool:
        """Cek per putaran: sisipkan context Bible HANYA bila berubah."""
        if self._has_orch_override("_refresh_bible_context"):
            return self.orchestrator._refresh_bible_context(history, task)
        if history is None:
            return False
        message = self.bible_context_message_for_task(task)
        if message is None:
            return False
        try:
            history.append_system_message(message.content)
        except Exception:
            return False
        return True

    def refresh_working_state_context(
        self, history: ConversationHistory
    ) -> bool:
        """Sisipkan Working State sebagai system message HANYA bila berubah."""
        if self._has_orch_override("_refresh_working_state_context"):
            return self.orchestrator._refresh_working_state_context(history)

        if history is None:
            return False
        provider = (
            getattr(self.orchestrator, "working_state_provider", None)
            if self.orchestrator is not None
            else None
        )
        if provider is None:
            return False
        try:
            text = provider()
        except Exception:  # noqa: BLE001
            return False
        if not text:
            return False
        last_text = (
            getattr(self.orchestrator, "_last_working_state_text", None)
            if self.orchestrator is not None
            else self._last_working_state_text
        )
        if text == last_text:
            return False
        try:
            history.append_system_message(text)
        except Exception:  # noqa: BLE001
            return False
        if self.orchestrator is not None:
            self.orchestrator._last_working_state_text = text
        self._last_working_state_text = text
        return True

    # ------------------------------------------------------------------ #
    # Knowledge budget & retrieval
    # ------------------------------------------------------------------ #
    def knowledge_budget_tokens(self) -> Optional[int]:
        """Anggaran token konteks pengetahuan dari provider."""
        if self._has_orch_override("_knowledge_budget_tokens"):
            return self.orchestrator._knowledge_budget_tokens()
        provider = (
            getattr(self.orchestrator, "provider", None)
            if self.orchestrator is not None
            else None
        )
        getter = getattr(provider, "knowledge_budget_tokens", None)
        if getter is None:
            return None
        try:
            tokens = getter()
        except Exception:  # noqa: BLE001
            return None
        if not tokens or int(tokens) <= 0:
            return None
        return int(tokens)

    def knowledge_budget_chars(self) -> Optional[int]:
        """Anggaran karakter untuk konteks pengetahuan."""
        if self._has_orch_override("_knowledge_budget_chars"):
            return self.orchestrator._knowledge_budget_chars()
        tokens = self.knowledge_budget_tokens()
        if tokens is None:
            return None
        return tokens * _KNOWLEDGE_CHARS_PER_TOKEN

    def retrieve_knowledge_context(self, query: str = "") -> str:
        """Context pengetahuan berbasis relevance (Bible retrieval)."""
        if self._has_orch_override("_retrieve_knowledge_context"):
            return self.orchestrator._retrieve_knowledge_context(query)
        brain = (
            getattr(self.orchestrator, "brain", None)
            if self.orchestrator is not None
            else None
        )
        event_sink = (
            getattr(self.orchestrator, "event_sink", None)
            if self.orchestrator is not None
            else None
        )
        try:
            from agent_ai.projects.retrieval import BibleRetriever

            retriever = BibleRetriever(brain)
            result = retriever.retrieve(
                query, budget_tokens=self.knowledge_context_budget_tokens()
            )
            if result is not None:
                emit_event(event_sink, "bible_retrieval", result.to_metadata())
                return result.text
        except Exception:  # noqa: BLE001
            pass
        try:
            ctx = brain.get_context()
        except Exception:  # noqa: BLE001
            return ""
        return getattr(ctx, "text", "") or ""

    def fit_knowledge_context(self, text: str) -> str:
        """Potong konteks pengetahuan agar muat pada context window."""
        if self._has_orch_override("_fit_knowledge_context"):
            return self.orchestrator._fit_knowledge_context(text)
        budget = self.knowledge_budget_chars()
        if budget is None or len(text) <= budget:
            return text
        cut = text.rfind("\n", 0, budget)
        if cut <= 0:
            cut = budget
        return (
            text[:cut].rstrip()
            + "\n- (konteks pengetahuan dipotong otomatis agar muat pada context "
            "window provider)"
        )

    # ------------------------------------------------------------------ #
    # Context Compaction & Budgeting
    # ------------------------------------------------------------------ #
    def context_budget_decision(self) -> Tuple[Optional[int], str]:
        """Anggaran token pesan + sumber keputusan."""
        if self._has_orch_override("_context_budget_decision"):
            return self.orchestrator._context_budget_decision()
        explicit = (
            getattr(self.orchestrator, "context_budget_tokens", None)
            if self.orchestrator is not None
            else None
        )
        if explicit is not None:
            value = int(explicit)
            return (value, "explicit") if value > 0 else (None, "none")
        provider_budget = self.knowledge_budget_tokens()
        if provider_budget is not None:
            return (provider_budget, "provider")
        try:
            from agent_ai.config.settings import settings

            value = int(getattr(settings.context, "max_tokens", 0) or 0)
        except Exception:  # noqa: BLE001
            return (None, "none")
        return (value, "config") if value > 0 else (None, "none")

    def context_budget_tokens(self) -> Optional[int]:
        """Anggaran token untuk daftar pesan."""
        if self._has_orch_override("_context_budget_tokens"):
            return self.orchestrator._context_budget_tokens()
        return self.context_budget_decision()[0]

    def knowledge_context_budget_tokens(self) -> Optional[int]:
        """Anggaran untuk konteks pengetahuan (Project Bible / retrieval)."""
        if self._has_orch_override("_knowledge_context_budget_tokens"):
            return self.orchestrator._knowledge_context_budget_tokens()
        provider_budget = self.knowledge_budget_tokens()
        try:
            from agent_ai.config.settings import settings

            cap = int(getattr(settings.context, "knowledge_max_tokens", 0) or 0)
            share = float(getattr(settings.context, "knowledge_share", 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            return provider_budget
        share_cap = 0
        if share > 0:
            conversation = self.context_budget_tokens()
            if conversation:
                share_cap = int(int(conversation) * share)
        caps = [value for value in (cap, share_cap) if value > 0]
        if not caps:
            return provider_budget
        effective = min(caps)
        if provider_budget is None:
            return effective
        return min(int(provider_budget), effective)

    def tool_definitions_tokens(self, tools: List[ToolDefinition]) -> int:
        """Estimasi token definisi tool."""
        if self._has_orch_override("_tool_definitions_tokens"):
            return self.orchestrator._tool_definitions_tokens(tools)
        total = 0
        for tool in tools or []:
            try:
                payload = json.dumps(tool.to_dict(), ensure_ascii=False, default=str)
            except Exception:  # noqa: BLE001
                payload = getattr(tool, "name", "") or ""
            total += max(1, len(payload) // _KNOWLEDGE_CHARS_PER_TOKEN)
        return total

    def compile_context_messages(
        self,
        history: ConversationHistory,
        tools: List[ToolDefinition],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Kompilasi pesan ke format provider dengan runtime context compaction."""
        if self._has_orch_override("_compile_context_messages"):
            return self.orchestrator._compile_context_messages(history, tools)

        from agent_ai.config.settings import compression_enabled

        if not compression_enabled():
            return history.to_provider_format(), {}

        budget, budget_source = self.context_budget_decision()
        if budget is None:
            return history.to_provider_format(), {}

        overhead = self.tool_definitions_tokens(tools)
        if budget > 0 and overhead >= budget:
            overhead = min(overhead, max(0, budget // 2))
        before = history.estimate_tokens()
        original = history.messages

        comp_stats: Dict[str, int] = {}
        compiled = history.compile_compacted_messages(
            budget, overhead_tokens=overhead, stats=comp_stats
        )

        span_stats: Dict[str, int] = {}
        if self._has_orch_override("_sync_retrieval_cache"):
            self.orchestrator._sync_retrieval_cache(history, compiled, stats=span_stats)
        else:
            executor = (
                getattr(self.orchestrator, "executor", None)
                if self.orchestrator is not None
                else None
            )
            sync_retrieval_cache(executor, history, compiled, stats=span_stats)

        after = history.estimate_messages_tokens(compiled)
        tool_stats = ConversationHistory.tool_compaction_stats(original, compiled)

        stats: Dict[str, Any] = {
            "context_budget": int(budget),
            "context_budget_source": str(budget_source),
            "context_overhead": int(overhead),
            "context_before": int(before),
            "context_after": int(after),
            "context_compacted": after < before,
            "context_tool_results": int(tool_stats["tool_results"]),
            "context_tool_compacted": int(tool_stats["tool_compacted"]),
            "context_tool_raw_chars": int(tool_stats["tool_raw_chars"]),
            "context_tool_compacted_chars": int(tool_stats["tool_compacted_chars"]),
        }
        stats.update({key: int(val) for key, val in comp_stats.items()})
        stats.update({key: int(val) for key, val in span_stats.items()})
        return [message.to_provider_dict() for message in compiled], stats


__all__ = [
    "ContextPipeline",
]
