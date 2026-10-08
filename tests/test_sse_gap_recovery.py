"""Pengujian unit dan integrasi untuk pemulihan gap SSE (AEG-10).

Memverifikasi:
1. EventSubscription memutar ulang (replay) event yang tertinggal berdasarkan last_event_id.
2. Endpoint /api/events mendukung header HTTP Last-Event-ID dan query param last_event_id.
3. Deduplikasi event berdasarkan urutan sequence monotonik.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

import pytest

# Ensure PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "django_app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

from django.conf import settings
if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"] + list(settings.ALLOWED_HOSTS)

import django
try:
    django.setup()
except RuntimeError:
    pass

from django.test import Client

from agent_ai.session.events import EventType, make_event
from agent_ai.session.store import InMemorySessionStore
from api.services import GatewayService
from api.streaming import EventSubscription, format_sse


def test_event_subscription_replay_from_last_event_id():
    """EventSubscription memutar ulang event setelah last_event_id."""
    store = InMemorySessionStore()

    # Buat 3 event di store
    ev1 = store.append_event(
        make_event(
            session_id="s1",
            event_type=EventType.TASK_STARTED,
            task_id="t1",
            payload={"step": "1"},
        )
    )
    ev2 = store.append_event(
        make_event(
            session_id="s1",
            event_type=EventType.TOOL_CALLED,
            task_id="t1",
            payload={"step": "2"},
        )
    )
    ev3 = store.append_event(
        make_event(
            session_id="s1",
            event_type=EventType.TOOL_COMPLETED,
            task_id="t1",
            payload={"step": "3"},
        )
    )

    # Klien disconnect pada ev1, reconnect membawa last_event_id = ev1.event_id
    sub = EventSubscription(
        store,
        session_id="s1",
        task_id="t1",
        last_event_id=ev1.event_id,
    )
    sub.start()

    # sub harus langsung memiliki ev2 dan ev3 di queue (replayed)
    replayed_1 = sub.get(timeout=0.2)
    assert replayed_1 is not None
    assert replayed_1.event_id == ev2.event_id

    replayed_2 = sub.get(timeout=0.2)
    assert replayed_2 is not None
    assert replayed_2.event_id == ev3.event_id

    # Event live berikutnya yang di-append harus masuk secara normal
    ev4 = store.append_event(
        make_event(
            session_id="s1",
            event_type=EventType.TASK_COMPLETED,
            task_id="t1",
            payload={"step": "4"},
        )
    )

    live_event = sub.get(timeout=0.2)
    assert live_event is not None
    assert live_event.event_id == ev4.event_id

    sub.close()


def test_event_subscription_deduplication():
    """EventSubscription tidak menduplikasi event dengan sequence yang sudah diterima."""
    store = InMemorySessionStore()

    ev1 = store.append_event(
        make_event(
            session_id="s1",
            event_type=EventType.TASK_STARTED,
            task_id="t1",
        )
    )

    # Reconnect dengan sequence ev1
    sub = EventSubscription(
        store,
        session_id="s1",
        task_id="t1",
        last_event_id=str(ev1.sequence),
    )
    sub.start()

    # Tidak ada event tertinggal setelah ev1
    assert sub.get(timeout=0.05) is None

    # Simulasikan callback manual dengan event lama (ev1)
    sub._on_event(ev1)
    assert sub.get(timeout=0.05) is None, "Event dengan sequence lama harus diabaikan"

    sub.close()


def test_api_events_last_event_id_header():
    """Endpoint /api/events merespons replay dengan header HTTP Last-Event-ID."""
    import asyncio
    from api.views import get_service

    async def _run():
        client = Client()
        service: GatewayService = get_service()
        store = service.sessions

        ev1 = store.append_event(
            make_event(
                session_id="sess_hdr",
                event_type=EventType.TASK_STARTED,
                task_id="t_hdr",
            )
        )
        ev2 = store.append_event(
            make_event(
                session_id="sess_hdr",
                event_type=EventType.TOOL_CALLED,
                task_id="t_hdr",
            )
        )

        resp = client.get(
            "/api/events?task_id=t_hdr",
            HTTP_LAST_EVENT_ID=ev1.event_id,
        )
        assert resp.status_code == 200
        assert resp.streaming

        stream = resp.streaming_content
        first = await anext(stream)
        first_str = first.decode("utf-8") if isinstance(first, bytes) else first
        assert ": connected" in first_str

        second = await anext(stream)
        second_str = second.decode("utf-8") if isinstance(second, bytes) else second
        assert ev2.event_id in second_str

        if hasattr(stream, "aclose"):
            await stream.aclose()

    asyncio.run(_run())
def test_session_store_append_event_idempotent():
    """InMemorySessionStore menolak duplikasi event_id dan melaporkan status idempotent."""
    store = InMemorySessionStore()

    ev1 = make_event(
        session_id="s_idem",
        event_type=EventType.TASK_STARTED,
        task_id="t_idem",
        payload={"step": 1},
    )

    stored, is_new = store.append_event_idempotent(ev1)
    assert is_new is True
    assert stored.sequence == 1
    assert stored.event_id == ev1.event_id

    # Append ulang event dengan event_id yang sama persis
    stored2, is_new2 = store.append_event_idempotent(ev1)
    assert is_new2 is False
    assert stored2.sequence == 1
    assert stored2.event_id == ev1.event_id

    # Pastikan total event tetap 1
    events = store.get_events(session_id="s_idem")
    assert len(events) == 1

def test_event_subscription_concurrent_replay_and_live_append():
    """EventSubscription menjamin atomic replay dan live buffering tanpa race condition atau lompatan sequence."""
    import threading
    import time

    store = InMemorySessionStore()
    # Buat 5 event awal (sequence 1 s.d. 5)
    initial_events = []
    for i in range(1, 6):
        ev = store.append_event(
            make_event(
                session_id="s_conc",
                event_type=EventType.TOOL_CALLED,
                task_id="t_conc",
                payload={"step": i},
            )
        )
        initial_events.append(ev)

    # Klien disconnect pada event 2 (sequence 2), reconnect meminta dari event 2
    sub = EventSubscription(
        store,
        session_id="s_conc",
        task_id="t_conc",
        last_event_id=initial_events[1].event_id,
    )

    live_appended = []

    def _worker_append():
        # Jeda sangat singkat untuk menabrak jendela start() / replay
        time.sleep(0.005)
        for i in range(6, 11):
            ev = store.append_event(
                make_event(
                    session_id="s_conc",
                    event_type=EventType.TOOL_CALLED,
                    task_id="t_conc",
                    payload={"step": i},
                )
            )
            live_appended.append(ev)
            time.sleep(0.002)

    t = threading.Thread(target=_worker_append)
    t.start()
    sub.start()
    t.join()

    # Kumpulkan seluruh event yang diterima subscriber
    received = []
    while True:
        ev = sub.get(timeout=0.1)
        if ev is None:
            break
        received.append(ev)

    sub.close()

    # Harus menerima sequence 3 s.d. 10 (total 8 event)
    received_seqs = [e.sequence for e in received]
    expected_seqs = list(range(3, 11))
    assert received_seqs == expected_seqs, f"Expected {expected_seqs}, got {received_seqs}"
    # Verifikasi tidak ada duplikasi sequence
    assert len(received_seqs) == len(set(received_seqs))


def test_event_subscription_unknown_last_event_id_prevents_history_flood():
    """Jika last_event_id tidak dikenal, sistem tidak membanjiri klien dengan seluruh riwayat masa lalu."""
    store = InMemorySessionStore()
    # Isi store dengan 10 event lama
    for i in range(1, 11):
        store.append_event(
            make_event(
                session_id="s_flood",
                event_type=EventType.TOOL_CALLED,
                task_id="t_flood",
                payload={"step": i},
            )
        )

    # Klien reconnect membawa last_event_id acak yang tidak valid / tidak dikenal
    sub = EventSubscription(
        store,
        session_id="s_flood",
        task_id="t_flood",
        last_event_id="unknown_bogus_event_id_9999",
    )
    sub.start()

    # Verifikasi tidak ada event yang diputar ulang (mencegah flood riwayat lama)
    assert sub.get(timeout=0.05) is None

    # Event baru yang masuk setelahnya harus tetap diterima
    new_ev = store.append_event(
        make_event(
            session_id="s_flood",
            event_type=EventType.TASK_COMPLETED,
            task_id="t_flood",
            payload={"step": 11},
        )
    )
    delivered = sub.get(timeout=0.1)
    assert delivered is not None
    assert delivered.event_id == new_ev.event_id
    assert delivered.sequence == 11

    sub.close()
