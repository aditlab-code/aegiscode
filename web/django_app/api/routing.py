"""WebSocket URL routing for AegisCode API."""

from __future__ import annotations

from django.urls import re_path

from api import consumers

websocket_urlpatterns = [
    re_path(
        r"^ws/terminal/(?:(?P<project_id>[\w-]+)/?)?$",
        consumers.TerminalConsumer.as_asgi(),
    ),
]
