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
        self._is_disconnected: bool = False
    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()

        # Verifikasi Autentikasi dan Origin sebelum shell dialokasikan (AEG-08)
        from api.auth import verify_websocket_auth

        is_allowed, reason, user_info = verify_websocket_auth(self.scope)
        if not is_allowed:
            logger.warning("Terminal WebSocket rejected: %s", reason)
            await self.accept()
            await self.send(
                text_data=f"\r\n\x1b[31m[Security: {reason}]\x1b[0m\r\n"
            )
            close_code = 4003 if "Origin" in reason else 4001
            await self.close(code=close_code)
            return

        self.scope["user_info"] = user_info

        url_route = self.scope.get("url_route", {})
        kwargs = url_route.get("kwargs", {})
        self.project_id = kwargs.get("project_id") or ""

        workspace_root = str(Path.cwd())
        if self.project_id:
            try:
                from api.services import get_service

                service = get_service()
                root = service._project_root_by_id(self.project_id)
                if not root.is_dir():
                    raise FileNotFoundError(f"Project directory {root} tidak ditemukan.")
                workspace_root = str(root)
            except Exception as exc:
                logger.warning(
                    "Could not resolve workspace for project %s: %s",
                    self.project_id,
                    exc,
                )
                await self.accept()
                await self.send(
                    text_data=f"\r\n\x1b[31m[Error: Workspace project '{self.project_id}' tidak valid: {exc}]\x1b[0m\r\n"
                )
                await self.close(code=4004)
                return

        await self.accept()

        self.pty = PTYSession(
            workspace_root=workspace_root,
            on_output=self._handle_pty_output,
        )
        from api.lifecycle import get_lifecycle_manager

        try:
            self.pty.start()
            get_lifecycle_manager().register_pty(self.pty)
        except Exception as exc:
            logger.error("Failed to start PTY session: %s", exc)
            await self.send(
                text_data=f"\r\n\x1b[31m[Error starting shell: {exc}]\x1b[0m\r\n"
            )
            await self.close()

    def _handle_pty_output(self, data: bytes) -> None:
        """Callback from PTY reader thread. Dispatches output to WebSocket."""
        if self._is_disconnected or not self._loop or self._loop.is_closed():
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
        self._is_disconnected = True
        if self.pty is not None:
            pty_to_clean = self.pty
            self.pty = None

            from api.lifecycle import get_lifecycle_manager

            get_lifecycle_manager().unregister_pty(pty_to_clean)
            try:
                await asyncio.wait_for(asyncio.to_thread(pty_to_clean.terminate), timeout=1.0)
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning("PTY async teardown timed out or failed: %s", exc)
