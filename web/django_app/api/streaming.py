"""SSE streaming untuk Aegis Gateway (#51).

Django HANYA menjadi transport:
    Aegis Event -> Django Gateway -> SSE -> Client

TIDAK membuat event model kedua, event bus baru, broker, Redis, Celery,
Channels, database, atau persistent event store. Memakai SessionStore Aegis
yang sudah ada (subscription minimal ditambahkan di layer session).

Format SSE standar:
    event: <event_type>
    data: <JSON payload>

Setiap frame juga menyertakan `id:` (event_id) dan `retry:` opsional.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, AsyncIterator, Dict, Iterator, Optional

from agent_ai.session.events import ExecutionEvent
from agent_ai.session.store import SessionStore

#: Batas jumlah event yang di-buffer per subscriber (bounded behavior).
DEFAULT_QUEUE_MAXSIZE = 1000

#: Interval heartbeat (detik) agar koneksi tidak idle-timeout.
DEFAULT_HEARTBEAT_SECONDS = 15.0


def format_sse(event: ExecutionEvent) -> str:
    """Format satu ExecutionEvent menjadi frame SSE standar.

    Format:
        id: <event_id>
        event: <event_type>
        data: <JSON payload>

    JSON payload memuat: event_id, sequence, timestamp, session_id, task_id,
    event_type, payload.
    """
    data = event.to_dict()
    lines = [
        f"id: {event.event_id}",
        f"event: {event.event_type.value}",
        f"data: {json.dumps(data, ensure_ascii=False)}",
        "",
        "",
    ]
    return "\n".join(lines)


def format_comment(text: str) -> str:
    """Format komentar SSE (mis. heartbeat)."""
    return f": {text}\n\n"


class EventSubscription:
    """Subscription tipis ke SessionStore Aegis (bounded, tanpa thread permanen).

    Membungkus callback subscription store + queue bounded. Callback store
    dipanggil saat event di-append; event yang lolos filter dimasukkan ke queue
    (drop bila penuh, agar tidak memory leak).

    Args:
        store: SessionStore Aegis.
        session_id: filter session (opsional).
        task_id: filter task (opsional).
        maxsize: batas queue (bounded).
    """

    def __init__(
        self,
        store: SessionStore,
        *,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        last_event_id: Optional[str] = None,
        maxsize: int = DEFAULT_QUEUE_MAXSIZE,
    ) -> None:
        self.store = store
        self.session_id = session_id
        self.task_id = task_id
        self.last_event_id = last_event_id
        self._queue: "queue.Queue[ExecutionEvent]" = queue.Queue(maxsize=maxsize)
        self._closed = False
        self._lock = threading.Lock()
        self._callback = self._on_event
        self._last_delivered_seq = 0

    def _matches(self, event: ExecutionEvent) -> bool:
        """Cek apakah event lolos filter session/task."""
        if self.session_id is not None and event.session_id != self.session_id:
            return False
        if self.task_id is not None and event.task_id != self.task_id:
            return False
        return True

    def _on_event(self, event: ExecutionEvent) -> None:
        """Callback store: masukkan event yang lolos filter ke queue."""
        with self._lock:
            if self._closed or not self._matches(event):
                return
            if event.sequence <= self._last_delivered_seq:
                return
            try:
                self._queue.put_nowait(event)
                self._last_delivered_seq = max(self._last_delivered_seq, event.sequence)
            except queue.Full:
                # Bounded: drop event bila subscriber lambat (anti memory leak).
                pass

    def start(self) -> None:
        """Mulai subscription: daftarkan callback ke store dan replay missed events."""
        with self._lock:
            if self.last_event_id:
                events = self.store.get_events()
                for e in events:
                    if str(e.event_id) == str(self.last_event_id) or str(e.sequence) == str(self.last_event_id):
                        self._last_delivered_seq = max(self._last_delivered_seq, e.sequence)
                        break

            self.store.subscribe(self._callback)

            if self._last_delivered_seq > 0 or self.last_event_id:
                replay_events = self.store.get_events(
                    session_id=self.session_id,
                    task_id=self.task_id,
                )
                for rev in replay_events:
                    if rev.sequence > self._last_delivered_seq:
                        try:
                            self._queue.put_nowait(rev)
                            self._last_delivered_seq = max(self._last_delivered_seq, rev.sequence)
                        except queue.Full:
                            break

    def close(self) -> None:
        """Akhiri subscription (unsubscribe dari store). Idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.store.unsubscribe(self._callback)

    @property
    def closed(self) -> bool:
        return self._closed

    def get(self, timeout: float) -> Optional[ExecutionEvent]:
        """Ambil event berikutnya (None bila timeout)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


class SSEStream:
    """Stream SSE hybrid (sinkron dan asinkron) untuk kompatibilitas penuh.

    Mendukung konsumsi sinkron (Iterator[str], next, close) untuk runner/testing
    maupun konsumsi asinkron (AsyncIterator[str], anext) untuk ASGI Daphne
    tanpa memblokir thread saat client disconnect.
    """

    def __init__(
        self,
        subscription: EventSubscription,
        *,
        heartbeat: float = DEFAULT_HEARTBEAT_SECONDS,
        is_disconnected: Optional[Any] = None,
    ) -> None:
        self.subscription = subscription
        self.heartbeat = heartbeat
        self.is_disconnected = is_disconnected
        self._last_heartbeat = 0.0

    def __iter__(self) -> "SSEStream":
        return self

    def __next__(self) -> str:
        import time

        if self._last_heartbeat == 0.0:
            self._last_heartbeat = time.time()

        while True:
            if self.is_disconnected is not None and self.is_disconnected():
                self.close()
                raise StopIteration
            if self.subscription.closed:
                raise StopIteration

            event = self.subscription.get(timeout=min(self.heartbeat, 0.2))
            now = time.time()
            if event is None:
                if now - self._last_heartbeat >= self.heartbeat:
                    self._last_heartbeat = now
                    return format_comment("heartbeat")
                continue
            self._last_heartbeat = now
            return format_sse(event)

    def __aiter__(self) -> "SSEStream":
        return self

    async def __anext__(self) -> str:
        import asyncio
        import time

        if self._last_heartbeat == 0.0:
            self._last_heartbeat = time.time()

        while True:
            if self.is_disconnected is not None and self.is_disconnected():
                self.close()
                raise StopAsyncIteration
            if self.subscription.closed:
                raise StopAsyncIteration

            try:
                event = await asyncio.to_thread(self.subscription.get, min(self.heartbeat, 0.2))
            except (asyncio.CancelledError, GeneratorExit):
                self.close()
                raise StopAsyncIteration

            now = time.time()
            if event is None:
                if now - self._last_heartbeat >= self.heartbeat:
                    self._last_heartbeat = now
                    return format_comment("heartbeat")
                continue
            self._last_heartbeat = now
            return format_sse(event)

    def close(self) -> None:
        """Tutup stream dan unsubscribe dari session store."""
        self.subscription.close()


def sse_stream(
    subscription: EventSubscription,
    *,
    heartbeat: float = DEFAULT_HEARTBEAT_SECONDS,
    is_disconnected: Optional[Any] = None,
) -> SSEStream:
    """Factory pembuat SSEStream hybrid (Iterator + AsyncIterator)."""
    return SSEStream(
        subscription,
        heartbeat=heartbeat,
        is_disconnected=is_disconnected,
    )

