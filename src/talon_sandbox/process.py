"""ProcessResult (from run) and Process (from spawn) for talon-sandbox SDK."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ._client import Client
from ._event_emitter import EventEmitter


@dataclass
class ProcessResult:
    """Result of a completed ``sb.run()`` command."""

    stdout: str
    stderr: str
    exit_code: int
    duration: float  # seconds


class Process(EventEmitter):
    """Handle for a long-running spawned process (from ``sb.spawn()``).

    Events:
    - ``stdout`` — str line emitted from the process stdout
    - ``stderr`` — str line emitted from the process stderr
    - ``exit``   — int exit code when the process terminates
    - ``error``  — Exception if streaming fails
    """

    EVENTS = frozenset({"stdout", "stderr", "exit", "error"})

    def __init__(
        self,
        proc_id: str,
        sandbox_id: str,
        command: str,
        pid: int,
        started_at: datetime,
        client: Client,
    ) -> None:
        super().__init__()
        self._id = proc_id
        self._sandbox_id = sandbox_id
        self._command = command
        self._pid = pid
        self._started_at = started_at
        self._client = client
        self._exit_code: int | None = None
        self._done: asyncio.Event = asyncio.Event()

    @property
    def id(self) -> str:
        return self._id

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def command(self) -> str:
        return self._command

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @property
    def exit_code(self) -> int | None:
        return self._exit_code

    async def wait(self) -> int:
        """Block until the process exits and return its exit code."""
        await self._done.wait()
        return self._exit_code or 0

    async def kill(self) -> None:
        """Send kill signal to the process."""
        await self._client.delete(
            f"/v1/sandboxes/{self._sandbox_id}/processes/{self._id}"
        )

    def _mark_exited(self, exit_code: int) -> None:
        self._exit_code = exit_code
        self._done.set()
        self._emit("exit", exit_code)

    @classmethod
    def _from_api(cls, data: dict[str, Any], sandbox_id: str, client: Client) -> "Process":
        started_ts = data.get("started_at", 0)
        started = (
            datetime.fromtimestamp(started_ts, tz=timezone.utc)
            if started_ts
            else datetime.now(tz=timezone.utc)
        )
        cmd_list = data.get("command", [])
        command = " ".join(cmd_list) if isinstance(cmd_list, list) else str(cmd_list)
        return cls(
            proc_id=data["id"],
            sandbox_id=sandbox_id,
            command=command,
            pid=data.get("pid", 0),
            started_at=started,
            client=client,
        )
