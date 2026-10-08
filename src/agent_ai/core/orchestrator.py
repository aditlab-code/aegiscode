"""Agent Orchestrator: iterative agent loop.

Menghubungkan Agent/provider, AgentLoop, ToolExecutor, dan LLMResponse menjadi
satu siklus iteratif:

    Task -> LLM -> LLMResponse
        -> FINAL      : selesai (result)
        -> TOOL_CALL  : ToolExecutor -> AgentObservation
                        -> observation dikirim kembali ke LLM -> ulangi
    sampai FINAL atau max_iterations.

Prinsip:
    - Provider hanya dipakai lewat abstraction (BaseProvider.generate +
      normalize_response). Tidak ada format tool-call provider baru.
    - LLMResponse adalah protocol internal.
    - Tool error dikirim kembali sebagai observation (loop tidak crash).
    - Hormati max_iterations via AgentLoop sebagai SAFETY LIMIT, bukan target.
    - Completion detection: sinyal final dari model adalah source of truth;
      loop berhenti saat final muncul. Selain itu, setelah setiap observation
      loop memeriksa bukti langkah (implementasi + requirement task terpenuhi,
      tanpa error aktif) dan berhenti lebih awal bila task terdeteksi selesai.
      Verification hanya diwajibkan bila task menuntutnya; mutasi sukses +
      requirement terpenuhi dapat menjadi completion. Bila iteration limit
      tercapai, bukti langkah yang sama dipakai untuk memutuskan Completed vs
      Failed, sehingga task yang sudah selesai tidak salah ditandai Failed
      hanya karena model terus memanggil tool.
    - Blok heuristic di atas berlaku HANYA untuk LOOP LAMA. Jalur continuous
      (`run_continuous_loop`, `use_continuous_loop=True`) TIDAK memakai
      heuristic completion apa pun: keputusan selesai murni dari response LLM
      yang tidak memiliki tool call (LLM Final -> DONE).
    - ProjectBrain (opsional) dipakai untuk membaca context sebelum task dan
      menyimpan learning setelah selesai. Orchestrator tidak tahu detail
      IntelligenceContext/Learner (hanya lewat facade ProjectBrain).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Tuple

from agent_ai.core.bible_lifecycle import (
    BibleContextState,
    bible_source_revision,
    fingerprint_text,
    resolve_bible_root,
)
from agent_ai.core.cancel import CancellationToken
from agent_ai.core.coding import CodingTask
from agent_ai.core.executor import ToolExecutor
from agent_ai.core.history import ConversationHistory
from agent_ai.core.loop import AgentLoop, MaxIterationsExceeded
from agent_ai.core.models import AgentObservation, AgentStatus
from agent_ai.core.observability import EventSink, emit as emit_event
from agent_ai.core.orchestration.context_pipeline import ContextPipeline
from agent_ai.core.orchestration.continuous_runner import ContinuousRunner
from agent_ai.core.orchestration.contracts import (
    DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS,
    OrchestrationConfig,
    OrchestratorResult,
    RunResult,
    TurnExecutionState,
)
from agent_ai.core.orchestration.legacy_runner import LegacyRunner
from agent_ai.core.orchestration.provider_runner import (
    DEFAULT_MAX_PROVIDER_ATTEMPTS,
    ProviderRunner,
    extract_partial_response,
    redact_credentials,
)
from agent_ai.core.orchestration.retrieval_state import (
    RetrievalStateManager,
    read_result_span,
    retrieval_identity,
    search_result_key,
    sync_retrieval_cache,
)
from agent_ai.core.orchestration.tool_results import (
    record_tool_result,
    tool_payload_to_observation,
    vision_content_message,
)

from agent_ai.core.provider_contract import sanitize_provider_response
from agent_ai.core.response import ActionType, LLMResponse, extract_reasoning_and_content
from agent_ai.core.types import ToolCall, ToolResultPayload
from agent_ai.providers.base import (
    BaseProvider,
    GenerateOptions,
    Message,
    ToolChoice,
    ToolDefinition,
)
from agent_ai.reliability.manager import ReliabilityManager
from agent_ai.reliability.models import (
    DecisionAction,
    ProgressSnapshot,
    ReliabilityDecision,
)

if TYPE_CHECKING:  # pragma: no cover - hanya untuk type hint, hindari import cycle
    from agent_ai.projects.brain import ProjectBrain


# Dipertahankan untuk KOMPATIBILITAS API (default parameter yang diimpor
# sebagian verifier). Nilainya BUKAN lagi digunakan sebagai hard stop:
# continuous loop TIDAK di-FAIL karena jumlah step. Loop berhenti hanya ketika
# LLM memberi response final TANPA tool call, user cancel, atau fatal error
# nyata. Agent task dapat berjalan selama diperlukan.
_CONTINUOUS_SAFETY_MAX_STEPS = DEFAULT_CONTINUOUS_SAFETY_MAX_STEPS

#: Estimasi kasar karakter per token, dipakai untuk mengubah anggaran token
#: provider (mis. context window default provider) menjadi anggaran karakter konteks
#: pengetahuan. Heuristik sederhana tanpa tokenizer eksternal.
_KNOWLEDGE_CHARS_PER_TOKEN = 4

#: Total attempt DEFAULT untuk SATU pemanggilan logis LLM/provider bila
#: konfigurasi retry request API (`data/settings.json` -> `api_retry`) tidak
#: tersedia: 1 attempt awal + 3 pengulangan = 4 attempt.
_DEFAULT_MAX_PROVIDER_ATTEMPTS = DEFAULT_MAX_PROVIDER_ATTEMPTS

_redact_credentials = redact_credentials
_extract_partial_response = extract_partial_response


# OrchestratorResult diimpor dari agent_ai.core.orchestration.contracts untuk standardisasi.


class AgentOrchestrator:
    """Menjalankan iterative agent loop di atas provider + tools.

    Args:
        provider: instance BaseProvider (abstraction).
        executor: ToolExecutor. Default: ToolExecutor() dengan registry global.
        max_iterations: batas iterasi (anti infinite loop).
        options: GenerateOptions default untuk setiap pemanggilan LLM.
        system_prompt: prompt sistem opsional.
        brain: ProjectBrain opsional. Bila diisi, context Project Intelligence
            disisipkan sebelum task dan learning disimpan setelah selesai.
        brain_learning: bila False, context brain tetap dipakai tetapi learning
            tidak dijalankan di akhir run (dikelola pemanggil, mis. Runtime).
        use_continuous_loop: bila True, `run()` memakai continuous loop Native
            Tool Calling (satu percakapan kontinu) menggantikan loop lama.
            Default True: continuous loop adalah jalur eksekusi NORMAL; loop
            lama hanya dipakai bila pemanggil memberi eksplisit `False`
            (kompatibilitas/uji).
        environment_context: Environment Context project-local (markdown dari
            `.aegis/ENVIRONMENT.md`). Bila diisi, disisipkan sebagai system
            message pada awal session continuous loop. Disiapkan pemanggil.
        context_budget_tokens: anggaran token untuk konteks percakapan
            (system + task + history) pada continuous loop. Bila None, anggaran
            diturunkan dari provider (`knowledge_budget_tokens`) atau config
            context yang ada. Riwayat yang melebihi anggaran dipadatkan secara
            DETERMINISTIK (tanpa LLM); task pendek tidak berubah.
    """

    def __init__(
        self,
        provider: BaseProvider,
        executor: Optional[ToolExecutor] = None,
        max_iterations: int = 10,
        options: Optional[GenerateOptions] = None,
        system_prompt: Optional[str] = None,
        brain: Optional["ProjectBrain"] = None,
        brain_learning: bool = True,
        use_tools: bool = True,
        tool_choice: Optional[ToolChoice] = None,
        reliability: Optional[ReliabilityManager] = None,
        event_sink: Optional[EventSink] = None,
        use_continuous_loop: bool = True,
        environment_context: Optional[str] = None,
        cancel_token: Optional[CancellationToken] = None,
        context_budget_tokens: Optional[int] = None,
        response_log: Optional[Any] = None,
        execution_policy: Optional[Dict[str, Any]] = None,
        policy_escalator: Optional[Callable[[str, str | None], Any]] = None,
        working_state_provider: Optional[Callable[[], str]] = None,
    ) -> None:
        self.provider = provider
        self.executor = executor or ToolExecutor()
        self.max_iterations = max_iterations
        self.options = options
        self.system_prompt = system_prompt
        self.brain = brain
        # Environment Context (project-local, opsional). Bila diisi (teks
        # markdown dari `.aegis/ENVIRONMENT.md`), disisipkan sebagai system
        # message pada awal session continuous loop. Disiapkan oleh pemanggil
        # (mis. AgentRuntime) agar tidak menulis file di sini.
        self.environment_context = environment_context
        # Bila False, orchestrator tetap membaca context brain tetapi TIDAK
        # melakukan learning di akhir run (learning dikelola pemanggil, mis.
        # sekali per task di Runtime). Default True (perilaku lama).
        self.brain_learning = brain_learning
        # Native tool calling: kirim definisi tool dari registry ke provider.
        # Default aktif; tool_choice default None (tidak dipaksa).
        self.use_tools = use_tools
        self.tool_choice = tool_choice
        # Reliability Layer (opsional). Bila None, loop berjalan seperti biasa.
        self.reliability = reliability
        # Observability (#55): sink event opsional. Bila None, tidak ada event
        # yang diemit (backward compatible). Sink menerima (event_type, payload)
        # dan payload sudah disanitasi (tanpa secret).
        self.event_sink = event_sink
        # Jalur execution baru (Native Tool Calling, satu percakapan kontinu).
        # Default False -> `run()` memakai loop lama (backward compatible).
        self.use_continuous_loop = use_continuous_loop
        # Cooperative cancellation (opsional). Bila diisi, loop memeriksa token
        # ini pada SAFE BOUNDARY (sebelum iteration LLM berikutnya dan sebelum
        # setiap tool call) dan berhenti sebagai CANCELLED tanpa tool call baru.
        # Bukan sistem cancellation kedua: satu token dibagikan lintas layer.
        self.cancel_token = cancel_token
        # Working State provider (opsional): callable yang mengembalikan
        # Working State sebagai teks untuk sistem message setiap round.
        self.working_state_provider = working_state_provider
        # Anggaran token untuk konteks percakapan (system + task + history).
        # Bila None, anggaran diturunkan dari provider (context window) atau
        # config context yang sudah ada; lihat `_context_budget_tokens()`.
        # Dipakai runtime compaction continuous loop agar riwayat lama tidak
        # dikirim mentah setiap round. None + fallback None = tanpa batas
        # (perilaku lama).
        self.context_budget_tokens = context_budget_tokens
        # Log response API LLM (opsional, dari `data/settings.json` ->
        # `write_log_response_api`). Bila diisi (objek duck-typed dengan
        # `append(record)`), SETIAP response mentah yang benar-benar diterima
        # AETHER dari provider dicatat per round ke
        # `.aegis/log/response/<task_id>.json`. Bila None (default), TIDAK ada
        # penulisan apa pun (AETHER berjalan seperti sekarang). Ini murni
        # observability: TIDAK mengubah loop/lifecycle/provider.
        self.response_log = response_log
        # Counter round LLM (per task; satu orchestrator = satu task). Dipakai
        # sebagai nomor `round` pada log response agar tiap request LLM dalam
        # task dapat diurutkan.
        self._llm_round = 0
        # Agent Execution Policy (fast/balanced/deep) — INFORMASI/strategi kerja,
        # BUKAN hard limit dan BUKAN penggerak keputusan loop. Berisi
        # ExecutionPolicyState.to_dict() (requested_mode/effective_mode/reason).
        # None (default) = policy tidak aktif -> perilaku persis seperti
        # sebelumnya (Agent & Consultant; consultant TIDAK mengirim policy).
        self.execution_policy = dict(execution_policy) if execution_policy else None
        # Callback escalation opsional `(reason, target_mode) -> Any` yang
        # disediakan pemanggil (runtime). Bila None, orchestrator tidak dapat
        # memicu escalation (mekanisme tetap ada di runtime/gateway).
        self.policy_escalator = policy_escalator
        self._bible_context_state: Optional[BibleContextState] = None
        self._last_working_state_text: Optional[str] = None
        self.context_pipeline = ContextPipeline(self)
        self.retrieval_state = RetrievalStateManager(self)
        self.legacy_runner = LegacyRunner(self)
        self.provider_runner = ProviderRunner(self)

    # ------------------------------------------------------------------ #
    # Tool definitions
    # ------------------------------------------------------------------ #
    def _tool_definitions(self) -> List[ToolDefinition]:
        """Bangun ToolDefinition (provider-agnostic) dari ToolRegistry.specs().

        Semua tool yang terdaftar tersedia untuk model. Tidak ada nama tool
        yang di-hardcode. Format konversi ke API dilakukan oleh provider.
        """
        if not self.use_tools:
            return []
        specs = self.executor.registry.specs()
        return [ToolDefinition.from_spec(spec) for spec in specs]

    # ------------------------------------------------------------------ #
    # Agent Execution Policy (fast/balanced/deep)
    # ------------------------------------------------------------------ #
    @property
    def effective_mode(self) -> Optional[str]:
        """Mode policy efektif saat ini (None bila policy tidak aktif)."""
        if not isinstance(self.execution_policy, Mapping):
            return None
        value = self.execution_policy.get("effective_mode")
        return str(value) if value else None

    @property
    def requested_mode(self) -> Optional[str]:
        """Mode policy yang diminta user/metadata (None bila tidak aktif)."""
        if not isinstance(self.execution_policy, Mapping):
            return None
        value = self.execution_policy.get("requested_mode")
        return str(value) if value else None

    def request_policy_escalation(
        self,
        reason: str,
        target_mode: Optional[str] = None,
    ) -> Any:
        """Minta escalation policy kepada pemanggil (mekanisme, bukan rule).

        Orkestrator TIDAK memutuskan escalation dan TIDAK membaca keyword task:
        ia hanya menyediakan jalur agar keputusan Agent/LLM (atau pemanggil)
        dapat MENAIKKAN mode. Bila pemanggil tidak menyediakan `policy_escalator`
        atau policy tidak aktif, hasilnya None (no-op; loop tidak terpengaruh).

        Args:
            reason: alasan escalation (wajib non-kosong).
            target_mode: mode tujuan opsional (default: satu tingkat di atas).

        Returns:
            Hasil dari escalator pemanggil (mis. state policy terbaru), atau
            None bila mekanisme tidak tersedia.
        """
        callback = self.policy_escalator
        if callback is None:
            return None
        result = callback(reason, target_mode)
        # Segarkan snapshot policy lokal agar informasi yang dipegang
        # orchestrator (effective_mode) mengikuti escalation terbaru. Ini
        # murni metadata: TIDAK mengubah keputusan loop.
        try:
            to_dict = getattr(result, "to_dict", None)
            if callable(to_dict):
                self.execution_policy = dict(to_dict())
        except Exception:  # noqa: BLE001 - metadata tidak boleh menggagalkan task
            pass
        return result

    def _policy_event_fields(self) -> Dict[str, Any]:
        """Field policy untuk event (kosong bila policy tidak aktif).

        Additive & aman: hanya menambahkan kunci bila policy aktif, sehingga
        payload/event lama TIDAK berubah bentuknya. Nilai murni metadata.
        """
        if not isinstance(self.execution_policy, Mapping):
            return {}
        fields: Dict[str, Any] = {}
        for key in ("requested_mode", "effective_mode"):
            value = self.execution_policy.get(key)
            if value:
                fields[key] = str(value)
        escalated = self.execution_policy.get("escalated")
        if escalated is not None:
            fields["policy_escalated"] = bool(escalated)
        return fields

    # ------------------------------------------------------------------ #
    # Cooperative cancellation (safe boundary)
    # ------------------------------------------------------------------ #
    def _cancel_requested(self) -> bool:
        """True bila pembatalan (user stop) sudah diminta.

        Dibaca pada SAFE BOUNDARY saja (sebelum memanggil LLM lagi / sebelum
        tool call berikutnya). Tidak memaksa menghentikan operasi yang sedang
        blocking; operasi tersebut diselesaikan dulu lalu loop berhenti.
        """
        token = self.cancel_token
        return token is not None and token.is_cancelled()

    def _cancel_reason(self) -> str:
        """Alasan pembatalan (fallback generik) untuk pesan status."""
        token = self.cancel_token
        reason = getattr(token, "reason", None) if token is not None else None
        return reason or "Task dibatalkan (user stop)."

    # ------------------------------------------------------------------ #
    # Context Pipeline & Knowledge Lifecycle (Delegasi ke ContextPipeline)
    # ------------------------------------------------------------------ #
    def _build_messages(
        self,
        task: str,
        history: List[Message],
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Message]:
        """Bangun daftar pesan untuk LLM: system + task + history."""
        return self.context_pipeline.build_messages(
            task, history, user_parts=user_parts
        )

    def _brain_context_message(self, query: str = "") -> Optional[Message]:
        """Ambil context Project Intelligence sebagai system message."""
        return self.context_pipeline.brain_context_message(query)

    def bible_context_state(self) -> BibleContextState:
        """State Bible context untuk scope task yang sedang berjalan."""
        return self.context_pipeline.bible_context_state()

    def begin_bible_context_scope(self, scope: str = "") -> BibleContextState:
        """Mulai scope task baru: Bible dianggap belum pernah dikirim."""
        return self.context_pipeline.begin_bible_context_scope(scope)

    def invalidate_bible_context(self, reason: str = "") -> BibleContextState:
        """Tandai context Bible pada scope ini tidak valid lagi."""
        return self.context_pipeline.invalidate_bible_context(reason)

    def bible_context_state_dict(self) -> Dict[str, Any]:
        """Ringkasan state Bible context tanpa isi konten."""
        return self.context_pipeline.bible_context_state_dict()

    def _bible_sources_revision(self) -> Optional[str]:
        """Revision murah sumber Bible (nama+size+mtime tiap kategori)."""
        return self.context_pipeline.bible_sources_revision()

    def _mark_bible_context_sent(
        self,
        state: BibleContextState,
        text: str,
        revision: Optional[str],
        query: str,
    ) -> bool:
        """Catat context Bible yang dikirim. False = isi identik (jangan kirim)."""
        return self.context_pipeline.mark_bible_context_sent(
            state, text, revision, query
        )

    def _bible_context_message_for_task(self, task: str = "") -> Optional[Message]:
        """Retrieval existing + lifecycle gate untuk satu task."""
        return self.context_pipeline.bible_context_message_for_task(task)

    def _refresh_bible_context(
        self, history: ConversationHistory, task: str = ""
    ) -> bool:
        """Cek per round (murah): sisipkan context Bible HANYA bila berubah."""
        return self.context_pipeline.refresh_bible_context(history, task)

    def _refresh_working_state_context(
        self, history: ConversationHistory
    ) -> bool:
        """Sisipkan Working State sebagai system message HANYA bila berubah."""
        return self.context_pipeline.refresh_working_state_context(history)


    def _knowledge_budget_tokens(self) -> Optional[int]:
        """Anggaran token konteks pengetahuan dari provider (bila dilaporkan)."""
        return self.context_pipeline.knowledge_budget_tokens()

    def _knowledge_budget_chars(self) -> Optional[int]:
        """Anggaran karakter untuk konteks pengetahuan (dari provider)."""
        return self.context_pipeline.knowledge_budget_chars()

    def _retrieve_knowledge_context(self, query: str = "") -> str:
        """Context pengetahuan berbasis relevance (Bible retrieval)."""
        return self.context_pipeline.retrieve_knowledge_context(query)

    def _fit_knowledge_context(self, text: str) -> str:
        """Potong konteks pengetahuan agar muat pada context window provider."""
        return self.context_pipeline.fit_knowledge_context(text)

    def _environment_context_message(self) -> Optional[Message]:
        """Environment Context (project-local) sebagai system message (opsional)."""
        return self.context_pipeline.environment_context_message()

    def _policy_directive_message(self) -> Optional[Message]:
        """Arahan operasional Execution Policy (Fast, Balanced, Deep)."""
        return self.context_pipeline.policy_directive_message()

    def _context_budget_decision(self) -> Tuple[Optional[int], str]:
        """Anggaran token pesan + sumber keputusan (untuk observability)."""
        return self.context_pipeline.context_budget_decision()

    def _context_budget_tokens(self) -> Optional[int]:
        """Anggaran token untuk daftar pesan (system + task + history)."""
        return self.context_pipeline.context_budget_tokens()

    def _knowledge_context_budget_tokens(self) -> Optional[int]:
        """Anggaran untuk konteks pengetahuan (Project Bible / retrieval)."""
        return self.context_pipeline.knowledge_context_budget_tokens()

    def _tool_definitions_tokens(self, tools: List[ToolDefinition]) -> int:
        """Estimasi token definisi tool (dikirim pada request yang sama)."""
        return self.context_pipeline.tool_definitions_tokens(tools)

    def _compile_context_messages(
        self,
        history: ConversationHistory,
        tools: List[ToolDefinition],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Kompilasi pesan ke format provider dengan runtime context compaction."""
        return self.context_pipeline.compile_context_messages(history, tools)


    # ------------------------------------------------------------------ #
    # Retrieval State Tracking & Cache Sync (Delegasi ke RetrievalState)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _retrieval_identity(
        tool_name: str, arguments: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Identitas satu retrieval untuk deteksi repeat (OBSERVABILITY SAJA)."""
        return retrieval_identity(tool_name, arguments)


    @staticmethod
    def _read_result_span(content: Optional[str]) -> Optional[Tuple[str, int, int]]:
        """Ekstrak (path, start, end) dari hasil read_file yang MEMUAT isi."""
        return read_result_span(content)

    @staticmethod
    def _search_result_key(content: Optional[str]) -> Optional[Tuple[str, str, int]]:
        """Ekstrak (query, path, context_lines) dari hasil search_code berisi."""
        return search_result_key(content)

    def _sync_retrieval_cache(
        self,
        history: ConversationHistory,
        compiled: List[Any],
        stats: Optional[Dict[str, int]] = None,
    ) -> None:
        """Selaraskan cache retrieval dengan pesan yang BENAR-BENAR dikirim."""
        self.retrieval_state.sync_retrieval_cache(history, compiled, stats=stats)


    def _model_name(self) -> str:
        """Nama model aktif untuk logging. Tidak pernah secret.

        Prioritas: `options.model` (model eksplisit per-run) -> `provider.config.model`
        (model default provider, mis. config provider). Fallback ke config
        provider penting agar log `provider_request` tidak menampilkan model
        kosong ketika provider memakai model default-nya (bukan bug runtime,
        hanya akurasi logging). Tidak mengubah payload yang dikirim provider.
        """
        if self.options is not None and getattr(self.options, "model", None):
            return self.options.model
        config = getattr(self.provider, "config", None)
        model = getattr(config, "model", None)
        return model or ""

    def _provider_response_payload(self, response: LLMResponse) -> Dict[str, Any]:
        """Payload event `provider_response` untuk satu response LLM sukses.

        Menyertakan `usage` (token AKTUAL) BILA provider melaporkannya pada
        response mentah — TIDAK ada estimasi/counter token baru. Bila provider
        tidak melaporkan usage, field `usage` TIDAK disertakan sehingga UI
        menampilkan "—" (bukan angka dummy).
        """
        return ProviderRunner(self).provider_response_payload(response)

    @staticmethod
    def _extract_commentary(response: LLMResponse) -> str:
        """Ambil commentary natural dari response LLM (bila bermakna).

        Commentary = teks penjelasan LLM tentang pekerjaannya. BUKAN log tool
        dan BUKAN payload code/tool. Mengembalikan string kosong bila teks
        tidak bermakna (kosong / hanya whitespace / terlihat seperti dump
        code/tool payload) sehingga UI tidak menampilkan noise.
        """
        text = (response.text or "").strip()
        if not text:
            return ""
        # Abaikan teks yang jelas berupa payload code/tool (bukan commentary).
        lowered = text.lower()
        if lowered.startswith(("```", "tool_call", "function_call", "{")):
            return ""
        # Batasi panjang agar tidak membanjiri UI (commentary ringkas).
        if len(text) > 600:
            text = text[:600].rstrip() + "…"
        return text

    @staticmethod
    def _tool_target(arguments: Dict[str, Any]) -> str:
        """Ekstrak target ringkas tool dari argumen yang memang tersedia.

        Mengambil path/query/command bila ada (tanpa hardcode nama file).
        Mengembalikan string kosong bila tidak ada informasi target.
        """
        if not arguments:
            return ""
        for key in ("path", "file", "filename", "query", "command", "pattern", "target"):
            value = arguments.get(key)
            if value:
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _observation_to_message(observation: AgentObservation) -> Message:
        """Ubah AgentObservation menjadi pesan untuk dikirim kembali ke LLM."""
        return LegacyRunner.observation_to_message(observation)

    # ------------------------------------------------------------------ #
    # Reliability & Legacy helpers (Delegasi ke LegacyRunner)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _action_signature(action: Any) -> str:
        """Identitas action: nama + argumen (deterministik)."""
        return LegacyRunner.action_signature(action)

    @staticmethod
    def _observation_signature(observation: AgentObservation) -> str:
        """Ringkasan observation untuk deteksi perubahan (bukan identitas penuh)."""
        return LegacyRunner.observation_signature(observation)

    @staticmethod
    def _observation_outcome(observation: AgentObservation) -> str:
        """Klasifikasi outcome observation (provider-agnostic)."""
        return LegacyRunner.observation_outcome(observation)

    # Konstanta legacy heuristik
    _MUTATION_MARKERS = LegacyRunner.MUTATION_MARKERS
    _MAX_TRUNCATION_RECOVERIES = 3
    _VALIDATION_KEYWORDS = LegacyRunner.VALIDATION_KEYWORDS
    _NO_VALIDATION_PHRASES = LegacyRunner.NO_VALIDATION_PHRASES
    _TARGET_FILE_RE = LegacyRunner.TARGET_FILE_RE
    _REQUIREMENT_FEATURES = LegacyRunner.REQUIREMENT_FEATURES
    _CRUD_WORDS = LegacyRunner.CRUD_WORDS
    _CRUD_FEATURES = LegacyRunner.CRUD_FEATURES


    @classmethod
    def _task_requires_validation(cls, task: str) -> bool:
        """True bila task eksplisit menuntut test/validasi/debug."""
        return LegacyRunner.task_requires_validation(task)

    @classmethod
    def _task_target_files(cls, task: str) -> set:
        """Nama file/path yang disebut eksplisit pada task."""
        return LegacyRunner.task_target_files(task)

    @staticmethod
    def _step_targets(step: Any) -> set:
        """Semua basename path dari argumen action sebuah step (bila ada)."""
        return LegacyRunner.step_targets(step)

    @staticmethod
    def _contains_word(text: str, word: str) -> bool:
        """True bila word muncul sebagai kata utuh pada text (lowercase)."""
        return LegacyRunner.contains_word(text, word)

    @classmethod
    def _task_requirement_features(cls, task: str) -> Dict[str, tuple]:
        """Fitur/aksi yang SECARA JELAS dinyatakan task (deterministik)."""
        return LegacyRunner.task_requirement_features(task)

    @staticmethod
    def _step_evidence(step: Any) -> str:
        """Teks bukti dari argumen action step (konten/command yang dihasilkan)."""
        return LegacyRunner.step_evidence(step)

    @classmethod
    def _is_change_observation(cls, observation: AgentObservation) -> bool:
        """True bila observation menandakan perubahan nyata (implementasi)."""
        return LegacyRunner.is_change_observation(observation)

    @staticmethod
    def _is_failure_observation(observation: Optional[AgentObservation]) -> bool:
        """True bila observation merepresentasikan error aktif."""
        return LegacyRunner.is_failure_observation(observation)

    @classmethod
    def _is_validation_observation(cls, observation: AgentObservation) -> bool:
        """True bila observation adalah eksekusi command yang sukses."""
        return LegacyRunner.is_validation_observation(observation)

    def _completion_signal(self, response: LLMResponse) -> Optional[str]:
        """Teks final bila response membawa sinyal penyelesaian task."""
        return LegacyRunner.completion_signal(response)


    def _completion_detected(self, loop: AgentLoop) -> bool:
        """Deteksi penyelesaian task dari bukti langkah + requirement task."""
        return self.legacy_runner.completion_detected(loop)


    @staticmethod
    def _completion_result() -> str:
        """Result ringkas saat completion terdeteksi (di loop atau di limit)."""
        return LegacyRunner.completion_result()

    def _recovery_message(self, decision: ReliabilityDecision) -> Message:
        """Pesan recovery yang disisipkan ke context (bukan loop baru)."""
        return LegacyRunner.recovery_message(decision)

    @staticmethod
    def _truncation_message() -> Message:
        """Pesan recovery saat response provider terpotong (finish_reason=length)."""
        return LegacyRunner.truncation_message()

    def _handle_provider_error(
        self, loop: AgentLoop, error: BaseException
    ) -> Optional[Message]:
        """Tangani error provider via reliability."""
        return ProviderRunner(self).handle_provider_error(loop, error)

    def _record_and_decide(
        self,
        loop: AgentLoop,
        action: Any,
        observation: AgentObservation,
    ) -> Optional[ReliabilityDecision]:
        """Catat progres ke reliability dan kembalikan keputusan (bila ada)."""
        return self.legacy_runner.record_and_decide(loop, action, observation)


    # ------------------------------------------------------------------ #
    # Provider call resilience & logging (delegasi ke ProviderRunner)
    # ------------------------------------------------------------------ #
    def _next_llm_round(self) -> int:
        """Naikkan & kembalikan nomor round LLM (per task)."""
        return ProviderRunner(self).next_llm_round()

    def _record_llm_response(self, record: Optional[Dict[str, Any]]) -> None:
        """Catat satu record response API ke log (best-effort, tidak pernah crash)."""
        ProviderRunner(self).record_llm_response(record)

    def _response_record_success(
        self, *, round_index: int, attempt: int, response: LLMResponse
    ) -> Dict[str, Any]:
        """Record log untuk satu response LLM yang BERHASIL diterima."""
        return ProviderRunner(self).response_record_success(
            round_index=round_index, attempt=attempt, response=response
        )

    def _response_record_error(
        self, *, round_index: int, attempt: int, error: BaseException
    ) -> Dict[str, Any]:
        """Record log untuk satu pemanggilan provider yang GAGAL (partial)."""
        return ProviderRunner(self).response_record_error(
            round_index=round_index, attempt=attempt, error=error
        )

    def _call_provider(
        self,
        *,
        messages: List[Any],
        options: Optional[GenerateOptions],
        tools: Optional[List[ToolDefinition]],
        round_index: int,
        attempt: int = 1,
    ) -> LLMResponse:
        """Panggil provider + catat response mentah (bila logging aktif)."""
        return ProviderRunner(self).call_provider(
            messages=messages,
            options=options,
            tools=tools,
            round_index=round_index,
            attempt=attempt,
        )

    def _api_retry_policy(self) -> Tuple[int, float]:
        """Baca kebijakan retry request API LLM dari `data/settings.json`."""
        return ProviderRunner(self).api_retry_policy()

    def _generate_with_retry(
        self,
        *,
        loop: AgentLoop,
        messages: List[Any],
        options: Optional[GenerateOptions],
        tools: Optional[List[ToolDefinition]],
    ) -> Optional[LLMResponse]:
        """Panggil `provider.generate` dengan retry provider-level (bounded)."""
        return ProviderRunner(self).generate_with_retry(
            loop=loop,
            messages=messages,
            options=options,
            tools=tools,
        )

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(
        self,
        task: str,
        *,
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> OrchestratorResult:
        """Jalankan iterative agent loop untuk sebuah task.

        Bila `use_continuous_loop` aktif (default), delegasikan ke
        `run_continuous_loop()` (Native Tool Calling, satu percakapan kontinu).
        Loop lama hanya dipakai bila pemanggil memberi eksplisit
        `use_continuous_loop=False` (kompatibilitas/uji).

        Args:
            task: task/permintaan user.
            user_parts: content blocks opsional untuk pesan user awal (mis.
                image, format internal AETHER provider-agnostic). Kosong
                (default) = perilaku text-only tidak berubah.

        Returns:
            OrchestratorResult (status DONE/FAILED, result, steps).
        """
        if self.use_continuous_loop:
            return self.run_continuous_loop(task, user_parts=user_parts)
        return self.legacy_runner.run(task, user_parts=user_parts)


    # ------------------------------------------------------------------ #
    # Continuous loop (Native Tool Calling, satu percakapan kontinu)
    # ------------------------------------------------------------------ #
    def run_continuous_loop(
        self,
        task: str,
        *,
        system_prompt: Optional[str] = None,
        max_steps: int = _CONTINUOUS_SAFETY_MAX_STEPS,
        options: Optional[GenerateOptions] = None,
        user_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> OrchestratorResult:
        """Jalankan SATU percakapan kontinu sampai LLM memberi jawaban final.

        Pola Native Tool Calling (tanpa nested session, tanpa completion
        detection semantik):

            LLM -> tool_calls -> eksekusi SEMUA tool -> hasil role="tool"
                -> LLM -> tool_calls -> ... -> LLM final (tanpa tool call)

        Karakteristik:
            - Satu `ConversationHistory` untuk seluruh task (system + task +
              seluruh turn), BUKAN session LLM baru per langkah.
            - Hasil tool SELALU dikirim sebagai pesan role "tool" dengan
              `tool_call_id` (via ConversationHistory), bukan dijejalkan
              sebagai pesan user.
            - Tidak ada reasoning/observation buatan AETHER di antara iterasi;
              setelah hasil tool, kontrol kembali 100% ke LLM.
            - Completion sepenuhnya ditentukan LLM: loop berhenti saat response
              final (tanpa tool call). Tidak ada semantic evaluator/planner baru.

        Args:
            task: task/permintaan user.
            system_prompt: override system prompt (default: system prompt loop).
            max_steps: emergency safety guard terhadap runaway loop. Nilai
                default TINGGI dan bukan limit behavior agent.
            options: override GenerateOptions (default: options loop).
            user_parts: content blocks opsional untuk pesan user awal (mis.
                image, format internal AETHER provider-agnostic). Kosong
                (default) = perilaku text-only tidak berubah.

        Returns:
            OrchestratorResult (status DONE/FAILED, result, steps).
        """
        # Delegasi modular ke ContinuousRunner:
        # Loop memanggil self._compile_context_messages untuk compaction context,
        # dan keputusan penyelesaian murni dari LLM:
        #   if not response.has_tool_calls:
        #       loop.finish(result=response.text...)
        runner = ContinuousRunner(self)
        return runner.run(
            task=task,
            system_prompt=system_prompt,
            max_steps=max_steps,
            options=options,
            user_parts=user_parts,
        )

    def _record_tool_result(
        self, history: ConversationHistory, payload: ToolResultPayload
    ) -> None:
        """Catat hasil satu tool ke histori sebagai pesan role "tool"."""
        record_tool_result(history, payload, event_sink=self.event_sink)

    @staticmethod
    def _vision_content_message(output: Any) -> str:
        """Teks pendamping pesan multimodal (menyebut path bila tersedia)."""
        return vision_content_message(output)

    @staticmethod
    def _tool_payload_to_observation(payload: ToolResultPayload) -> AgentObservation:
        """Ubah ToolResultPayload menjadi AgentObservation (bookkeeping step)."""
        return tool_payload_to_observation(payload)

    def run_coding_task(self, task: str) -> CodingTask:
        """Jalankan task coding dan bungkus hasilnya sebagai CodingTask.

        Thin wrapper di atas run(); tidak mengubah logika loop. AgentLoop tetap
        mengelola iteration/action/observation.

        Returns:
            CodingTask (request, status, iterations, result, error, steps).
        """
        coding = CodingTask(request=task).start()
        result = self.run(task)
        if result.success:
            coding.complete(
                result=result.result,
                iterations=result.iterations,
                steps=result.steps,
            )
        else:
            coding.fail(
                error=result.error or "task gagal",
                iterations=result.iterations,
                steps=result.steps,
            )
        return coding

    # ------------------------------------------------------------------ #
    # Learning (opsional, terisolasi)
    # ------------------------------------------------------------------ #
    def _learn_from_run(self, task: str, loop: AgentLoop) -> Optional[Dict[str, Any]]:
        """Kirim ringkasan pekerjaan ke brain.learn (opsional).

        Learning error TIDAK menggagalkan task utama; kembalikan None bila
        brain tidak tersedia atau learning gagal.
        """
        if self.brain is None or not self.brain_learning:
            return None
        try:
            observations = self._build_observations(task, loop)
            if not observations:
                return None
            result = self.brain.learn(observations)
            return result.to_dict() if hasattr(result, "to_dict") else None
        except Exception:  # noqa: BLE001 - learning error harus terisolasi
            return None

    @staticmethod
    def _build_observations(task: str, loop: AgentLoop) -> List[str]:
        """Bangun observations ringkas dari task + hasil loop (bukan per step)."""
        observations: List[str] = [f"Task: {task}"]
        if loop.state.result:
            observations.append(f"Result: {loop.state.result}")
        if loop.state.error:
            observations.append(f"Error: {loop.state.error}")
        # Ringkas tool results yang relevan (bukan setiap internal step).
        for step in loop.to_dict()["steps"]:
            observation = step.get("observation") or {}
            if observation.get("success") and observation.get("content"):
                observations.append(f"Tool result: {observation['content']}")
        return observations


