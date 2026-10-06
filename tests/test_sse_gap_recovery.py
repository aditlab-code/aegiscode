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
