import asyncio
import os
import sys
from pathlib import Path

import pytest
from channels.testing import WebsocketCommunicator

# Ensure web/django_app is in sys.path
django_dir = Path(__file__).resolve().parent.parent / "web" / "django_app"
if str(django_dir) not in sys.path:
    sys.path.insert(0, str(django_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.asgi import application  # noqa: E402


def test_terminal_consumer_websocket_lifecycle() -> None:
    async def _run():
        communicator = WebsocketCommunicator(application, "/ws/terminal/")
        connected, _ = await communicator.connect()
        assert connected, "WebSocket connection should succeed"

        # Send resize command
        await communicator.send_json_to({"type": "resize", "rows": 24, "cols": 80})

        # Send a simple echo command
        await communicator.send_json_to({"type": "input", "data": "echo CONSUMER_OK\n"})

        # Collect response
        response = ""
        for _ in range(5):
            try:
                msg = await communicator.receive_from(timeout=1.0)
                response += msg
                if "CONSUMER_OK" in response:
                    break
            except asyncio.TimeoutError:
                break

        assert "CONSUMER_OK" in response, f"Expected CONSUMER_OK in output, got: {response!r}"

        # Clean disconnect
        await communicator.disconnect()

    asyncio.run(_run())
