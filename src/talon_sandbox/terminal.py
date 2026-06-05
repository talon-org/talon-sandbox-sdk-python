"""Terminal (PTY) sub-object for talon-sandbox SDK."""
from __future__ import annotations

import asyncio
import json as _json
from typing import Any

import websockets
import websockets.exceptions
from websockets.asyncio.client import connect as ws_connect

from ._client import Client
from ._event_emitter import EventEmitter
from ._version import get_user_agent


class PTYSession(EventEmitter):
    """An open PTY session over WebSocket.

    Events:
    - ``data``  — bytes chunk received from the terminal
    - ``exit``  — int exit code when the session closes
    - ``error`` — Exception on connection error
    """

    EVENTS = frozenset({"data", "exit", "error"})

    def __init__(self, ws: Any) -> None:
        super().__init__()
        self._ws = ws
        self._recv_task: asyncio.Task[None] | None = None
        self._closed = False
        self._data_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def _recv_loop(self) -> None:
        try:
            async for frame in self._ws:
                data = frame if isinstance(frame, bytes) else frame.encode()
                self._data_queue.put_nowait(data)
                self._emit("data", data)
        except websockets.exceptions.ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else 0
            self._emit("exit", code)
        except Exception as e:
            self._emit("error", e)
        finally:
            self._closed = True

    async def write(self, data: bytes | str) -> None:
        """Send data to the PTY stdin."""
        if self._closed:
            from .errors import SandboxError

            raise SandboxError("PTY session is closed")
        payload = data.encode() if isinstance(data, str) else data
        await self._ws.send(payload)

    async def resize(self, *, rows: int, cols: int) -> None:
        """Resize the terminal window."""
        msg = _json.dumps({"type": "resize", "rows": rows, "cols": cols})
        await self._ws.send(msg.encode())

    async def close(self) -> None:
        """Close the PTY session."""
        if not self._closed:
            self._closed = True
            await self._ws.close()
            if self._recv_task:
                self._recv_task.cancel()
                try:
                    await self._recv_task
                except asyncio.CancelledError:
                    pass

    def __aiter__(self) -> PTYSession:
        return self

    async def __anext__(self) -> bytes:
        while not self._closed or not self._data_queue.empty():
            try:
                chunk = await asyncio.wait_for(self._data_queue.get(), timeout=0.1)
                return chunk
            except asyncio.TimeoutError:
                continue
        raise StopAsyncIteration

    async def __aenter__(self) -> PTYSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class Terminal:
    """Manage PTY sessions for a sandbox.

    Access via ``sb.terminal``.
    """

    def __init__(self, sandbox_id: str, client: Client) -> None:
        self._sandbox_id = sandbox_id
        self._client = client

    def _ws_url(self) -> str:
        return self._client._ws_url(f"/v1/sandboxes/{self._sandbox_id}/pty")

    async def open(
        self,
        *,
        rows: int = 24,
        cols: int = 80,
        env: dict[str, str] | None = None,
    ) -> PTYSession:
        """Open a new PTY session.

        Args:
            rows: Terminal rows (default 24).
            cols: Terminal columns (default 80).
            env: Additional environment variables for the shell.

        Returns:
            PTYSession with EventEmitter interface.
        """
        # WebSocket 握手同样带上规范 User-Agent，与 HTTP 请求来源追踪保持一致
        extra_headers: list[tuple[str, str]] = [("User-Agent", get_user_agent())]
        auth = self._client._auth_header_value()
        if auth:
            extra_headers.append(("Authorization", auth))

        ws = await ws_connect(self._ws_url(), additional_headers=extra_headers)
        session = PTYSession(ws)
        loop = asyncio.get_running_loop()
        session._recv_task = loop.create_task(session._recv_loop())
        return session
