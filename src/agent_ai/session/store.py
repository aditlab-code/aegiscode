"""SessionStore: abstraction untuk menyimpan session, task reference, dan event.

Provider-agnostic, tool-agnostic. Store TIDAK menjalankan logic agent dan
TIDAK mengetahui provider/tool tertentu.

Implementasi saat ini: InMemorySessionStore (tanpa database/persistence).
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

from agent_ai.session.events import ExecutionEvent, EventType
from agent_ai.session.models import Session, SessionStatus, TaskReference, new_session_id

#: Tipe callback subscriber: dipanggil setiap kali event di-append.
EventSubscriber = Callable[[ExecutionEvent], None]
TERMINAL_EVENT_TYPES = {
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.TASK_CANCELLED,
    EventType.TASK_COMPLETED.value,
    EventType.TASK_FAILED.value,
    EventType.TASK_CANCELLED.value,
}



class SessionStore(ABC):
    """Interface penyimpanan session + event.

    Semua operasi bersifat append-only untuk event: event tidak dapat diubah
    atau dihapus setelah dibuat.
    """

    # ------------------------------------------------------------------ #
    # Session
    # ------------------------------------------------------------------ #
    @abstractmethod
    def create_session(
        self,
        project_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        """Buat session baru."""
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Ambil session berdasarkan id (None bila tidak ada)."""
        raise NotImplementedError

    @abstractmethod
    def update_session(
        self,
        session_id: str,
        *,
        status: Optional[SessionStatus] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Session]:
        """Update status/metadata session (None bila session tidak ada)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Task reference
    # ------------------------------------------------------------------ #
    @abstractmethod
    def create_task_reference(
        self,
        session_id: str,
        task_id: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[TaskReference]:
        """Tambahkan referensi task ke session (None bila session tidak ada)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    @abstractmethod
    def append_event(self, event: ExecutionEvent) -> ExecutionEvent:
        """Tambahkan event (append-only). Mengembalikan event dengan sequence."""
        raise NotImplementedError

    def append_event_idempotent(self, event: ExecutionEvent) -> tuple[ExecutionEvent, bool]:
        """Tambahkan event secara idempotent.

        Jika event dengan event_id yang sama sudah pernah tersimpan,
        kembalikan event yang ada dengan flag False (bukan event baru).
        Jika belum ada, append dan kembalikan dengan flag True.
        """
        return self.append_event(event), True

    @abstractmethod
    def get_events(
        self,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
    ) -> List[ExecutionEvent]:
        """Ambil event (opsional difilter), urut deterministik (sequence)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Subscription (opsional, minimal)
    # ------------------------------------------------------------------ #
    def subscribe(self, callback: EventSubscriber) -> EventSubscriber:
        """Daftarkan callback yang dipanggil saat event baru di-append.

        Default: tidak mendukung subscription (no-op). Implementasi yang
        mendukung live streaming (mis. InMemorySessionStore) meng-override.

        Returns:
            Callback yang sama (untuk dipakai saat unsubscribe).
        """
        return callback

    def unsubscribe(self, callback: EventSubscriber) -> None:
        """Hapus callback subscription (default: no-op)."""
        return None


class InMemorySessionStore(SessionStore):
    """Implementasi in-memory (tanpa database/persistence).

    Event bersifat append-only dan diberi `sequence` monotonik agar ordering
    deterministik.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._events: List[ExecutionEvent] = []
        self._events_by_id: Dict[str, ExecutionEvent] = {}
        self._sequence: int = 0
        # Subscriber live (minimal): callback dipanggil saat event di-append.
        self._subscribers: List[EventSubscriber] = []
        # Parallel tool execution dapat meng-append event dari beberapa worker
        # thread sekaligus; lock menjaga sequence tetap monotonic & unik.
        self._event_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Session
    # ------------------------------------------------------------------ #
    def create_session(
        self,
        project_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        sid = session_id or new_session_id()
        if sid in self._sessions:
            raise ValueError(f"Session '{sid}' sudah ada.")
        session = Session(
            session_id=sid,
            project_id=project_id,
            metadata=dict(metadata or {}),
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def update_session(
        self,
        session_id: str,
        *,
        status: Optional[SessionStatus] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if status is not None:
            session.status = status
        if metadata:
            session.metadata.update(metadata)
        session.updated_at = time.time()
        return session

    # ------------------------------------------------------------------ #
    # Task reference
    # ------------------------------------------------------------------ #
    def create_task_reference(
        self,
        session_id: str,
        task_id: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[TaskReference]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if not task_id:
            raise ValueError("create_task_reference butuh task_id.")
        # Idempotent: jangan duplikasi task_id yang sama.
        for ref in session.tasks:
            if ref.task_id == task_id:
                return ref
        ref = TaskReference(task_id=task_id, metadata=dict(metadata or {}))
        session.tasks.append(ref)
        session.updated_at = time.time()
        return ref

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def append_event(self, event: ExecutionEvent) -> ExecutionEvent:
        """Append event dengan sequence monotonik (append-only).

        Thread-safe: parallel tool execution dapat meng-append event dari
        beberapa worker thread sekaligus. Lock HANYA membungkus penomoran
        sequence + append list (bukan subscriber), sehingga tidak ada
        sequence duplikat tanpa menyerialkan seluruh eksekusi tool.
        """
        with self._event_lock:
            # Periksa apakah event_id sudah ada
            if event.event_id and event.event_id in self._events_by_id:
                return self._events_by_id[event.event_id]

            # Deduplikasi event terminal: task_id hanya boleh memiliki tepat 1 terminal event
            evt_val = getattr(event.event_type, "value", str(event.event_type))
            if event.task_id and (event.event_type in TERMINAL_EVENT_TYPES or evt_val in TERMINAL_EVENT_TYPES):
                for existing in reversed(self._events):
                    if existing.task_id == event.task_id:
                        ex_val = getattr(existing.event_type, "value", str(existing.event_type))
                        if existing.event_type in TERMINAL_EVENT_TYPES or ex_val in TERMINAL_EVENT_TYPES:
                            return existing
            self._sequence += 1
            sequence = self._sequence
            # ExecutionEvent frozen -> buat salinan dengan sequence.
            stored = ExecutionEvent(
                event_id=event.event_id,
                session_id=event.session_id,
                task_id=event.task_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                payload=dict(event.payload),
                sequence=sequence,
                status=event.status or (event.payload.get("status") if isinstance(event.payload, dict) else None),
            )
            self._events.append(stored)
            if event.event_id:
                self._events_by_id[event.event_id] = stored
        # tidak boleh mengganggu append event atau subscriber lain.
        for callback in list(self._subscribers):
            try:
                callback(stored)
            except Exception:  # noqa: BLE001 - subscriber error tidak boleh crash
                continue
        return stored
    def append_event_idempotent(self, event: ExecutionEvent) -> tuple[ExecutionEvent, bool]:
        """Append event secara idempotent dan laporkan apakah event benar-benar baru."""
        with self._event_lock:
            if event.event_id and event.event_id in self._events_by_id:
                return self._events_by_id[event.event_id], False
        return self.append_event(event), True

    def subscribe(self, callback: EventSubscriber) -> EventSubscriber:
        """Daftarkan callback live (dipanggil saat event baru di-append)."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)
        return callback

    def unsubscribe(self, callback: EventSubscriber) -> None:
        """Hapus callback live (aman bila tidak terdaftar)."""
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def subscriber_count(self) -> int:
        """Jumlah subscriber aktif (untuk verifikasi cleanup)."""
        return len(self._subscribers)

    def get_events(
        self,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
    ) -> List[ExecutionEvent]:
        """Ambil event terurut berdasarkan sequence (deterministik)."""
        result = self._events
        if session_id is not None:
            result = [e for e in result if e.session_id == session_id]
        if task_id is not None:
            result = [e for e in result if e.task_id == task_id]
        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]
        return sorted(result, key=lambda e: e.sequence)
