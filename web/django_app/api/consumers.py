"""WebSocket consumers for AegisCode interactive pseudo-terminal (PTY)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from channels.generic.websocket import AsyncWebsocketConsumer

from agent_ai.runtime.pty_session import PTYSession

logger = logging.getLogger(__name__)


class TerminalConsumer(AsyncWebsocketConsumer):
    """Full-duplex WebSocket consumer connecting xterm.js to a PTY session."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pty: Optional[PTYSession] = None
        self.project_id: str = ""
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        url_route = self.scope.get("url_route", {})
        kwargs = url_route.get("kwargs", {})
        self.project_id = kwargs.get("project_id") or ""

        workspace_root = str(Path.cwd())
        if self.project_id:
            try:
                from api.services import get_service

                service = get_service()
                root = service._project_root_by_id(self.project_id)
                if root.is_dir():
                    workspace_root = str(root)
            except Exception as exc:
                logger.warning(
                    "Could not resolve workspace for project %s: %s",
                    self.project_id,
                    exc,
                )

        await self.accept()

        self.pty = PTYSession(
            workspace_root=workspace_root,
            on_output=self._handle_pty_output,
        )
        try:
            self.pty.start()
        except Exception as exc:
            logger.error("Failed to start PTY session: %s", exc)
            await self.send(
                text_data=f"\r\n\x1b[31m[Error starting shell: {exc}]\x1b[0m\r\n"
            )
            await self.close()

    def _handle_pty_output(self, data: bytes) -> None:
        """Callback from PTY reader thread. Dispatches output to WebSocket."""
        if not self._loop or self._loop.is_closed():
            return

        text = data.decode("utf-8", errors="replace")
        coro = self.send(text_data=text)
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except RuntimeError:
            pass

    async def receive(
        self,
        text_data: Optional[str] = None,
        bytes_data: Optional[bytes] = None,
    ) -> None:
        if not self.pty or not self.pty.is_alive:
            return

        if bytes_data is not None:
            self.pty.write(bytes_data.decode("utf-8", errors="replace"))
            return

        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except (ValueError, TypeError):
            payload = None

        if isinstance(payload, dict):
            event_type = payload.get("type")
            if event_type == "input":
                raw_data = str(payload.get("data", ""))
                self.pty.write(raw_data)
            elif event_type == "resize":
                rows = int(payload.get("rows", 24))
                cols = int(payload.get("cols", 80))
                self.pty.resize(rows=rows, cols=cols)
            elif event_type == "signal":
                sig = payload.get("signal", "")
                if sig in ("SIGINT", "INT"):
                    self.pty.write("\x03")
        else:
            self.pty.write(text_data)

    async def disconnect(self, close_code: int) -> None:
        if self.pty is not None:
            self.pty.terminate()
            self.pty = None
