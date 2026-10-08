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


def test_terminal_consumer_async_teardown_cleans_pty() -> None:
    from api.consumers import TerminalConsumer
    from unittest.mock import MagicMock

    consumer = TerminalConsumer()
    assert consumer._is_disconnected is False

    # Create mock PTY
    mock_pty = MagicMock()
    mock_pty.terminate = MagicMock()
    consumer.pty = mock_pty

    # Test output guard before disconnect
    mock_loop = MagicMock()
    mock_loop.is_closed.return_value = False
    consumer._loop = mock_loop
    consumer.send = MagicMock()

    # Simulate disconnect
    async def _test_disconnect():
        await consumer.disconnect(close_code=1000)
        assert consumer._is_disconnected is True
        assert consumer.pty is None
        mock_pty.terminate.assert_called_once()

        # Test output guard after disconnect (should not schedule anything)
        consumer._handle_pty_output(b"should_be_ignored")
        mock_loop.create_task.assert_not_called()

    asyncio.run(_test_disconnect())


def test_terminal_consumer_project_switching_isolation(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj_a"
    proj_b = tmp_path / "proj_b"
    proj_a.mkdir()
    proj_b.mkdir()

    from unittest.mock import MagicMock, patch
    from api.lifecycle import get_lifecycle_manager

    lifecycle = get_lifecycle_manager()

    async def _run():
        def fake_root(pid: str):
            if pid == "proj-a":
                return proj_a
            if pid == "proj-b":
                return proj_b
            raise FileNotFoundError(pid)

        with patch("api.services.get_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service._project_root_by_id.side_effect = fake_root
            mock_get_service.return_value = mock_service

            # Connect Project A
            comm_a = WebsocketCommunicator(application, "/ws/terminal/proj-a/")
            connected_a, _ = await comm_a.connect()
            assert connected_a, "Project A connection should succeed"

            # Send input to Project A
            await comm_a.send_json_to({"type": "input", "data": "echo PROJ_A_ACTIVE\n"})
            resp_a = ""
            for _ in range(5):
                try:
                    resp_a += await comm_a.receive_from(timeout=1.0)
                    if "PROJ_A_ACTIVE" in resp_a:
                        break
                except asyncio.TimeoutError:
                    break
            assert "PROJ_A_ACTIVE" in resp_a

            # Disconnect Project A
            await comm_a.disconnect()

            # Connect Project B immediately
            comm_b = WebsocketCommunicator(application, "/ws/terminal/proj-b/")
            connected_b, _ = await comm_b.connect()
            assert connected_b, "Project B connection should succeed"

            # Send input to Project B
            await comm_b.send_json_to({"type": "input", "data": "echo PROJ_B_ACTIVE\n"})
            resp_b = ""
            for _ in range(5):
                try:
                    resp_b += await comm_b.receive_from(timeout=1.0)
                    if "PROJ_B_ACTIVE" in resp_b:
                        break
                except asyncio.TimeoutError:
                    break
            assert "PROJ_B_ACTIVE" in resp_b

            # Disconnect Project B
            await comm_b.disconnect()

    asyncio.run(_run())
