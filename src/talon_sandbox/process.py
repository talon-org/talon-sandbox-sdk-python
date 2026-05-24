"""ProcessResult (from run) and Process (from spawn) for talon-sandbox SDK."""
from __future__ import annotations

import asyncio
import contextlib
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

    A background task polls the platform's process list + log endpoints and
    fires events as new bytes arrive / the process exits. Cancelled when
    ``wait()`` returns, ``kill()`` is called, or the sandbox is destroyed.

    Events:
    - ``stdout`` — str chunk emitted from the process stdout+stderr (combined)
    - ``stderr`` — reserved; server log endpoint combines streams so this is
      not currently fired separately
    - ``exit``   — int exit code when the process terminates
    - ``error``  — Exception if streaming fails

    The poll cadence is 500 ms (cheap server-side, low latency for short
    commands). A future server-side WebSocket log endpoint can replace the
    polling without changing this surface.
    """

    EVENTS = frozenset({"stdout", "stderr", "exit", "error"})

    POLL_INTERVAL_SEC = 0.5
    LOG_TAIL_BYTES = 65536

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
        # Number of log bytes already emitted; next poll only emits the suffix.
        self._log_offset: int = 0
        # Background poll task. Started lazily on first wait/on/explicit
        # _start_streaming to avoid creating tasks before an event loop runs.
        self._poll_task: asyncio.Task[None] | None = None
        self._poll_lock = asyncio.Lock()

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

    def on(self, event, callback):  # type: ignore[override]
        # Registering a stdout/stderr listener implies the caller wants
        # streaming, so spin up the poll loop on demand.
        result = super().on(event, callback)
        if event in ("stdout", "stderr", "exit", "error"):
            self._ensure_streaming()
        return result

    async def wait(self) -> int:
        """Block until the process exits and return its exit code."""
        self._ensure_streaming()
        await self._done.wait()
        return self._exit_code if self._exit_code is not None else 0

    async def kill(self) -> None:
        """Send kill signal to the process."""
        await self._client.delete(
            f"/v1/sandboxes/{self._sandbox_id}/processes/{self._id}"
        )
        # Drain any remaining log bytes, then mark exited so wait() returns
        # immediately rather than waiting for the next poll tick.
        if not self._done.is_set():
            await self._final_log_drain()
            self._mark_exited(-1)

    def _ensure_streaming(self) -> None:
        """Lazily start the background poll task on the current loop."""
        if self._poll_task is not None and not self._poll_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop yet — wait() / on() will call us again later.
            return
        self._poll_task = loop.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        """Poll the platform for new log bytes + process state until exit."""
        try:
            while not self._done.is_set():
                await self._tick_once()
                if self._done.is_set():
                    break
                await asyncio.sleep(self.POLL_INTERVAL_SEC)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface to user via event
            self._emit("error", exc)
            # Don't leave wait() hanging on a polling crash.
            if not self._done.is_set():
                self._mark_exited(-1)

    async def _tick_once(self) -> None:
        """One iteration: drain new log bytes, check process state."""
        # 1. Drain new log bytes.
        async with self._poll_lock:
            try:
                log_resp = await self._client.get(
                    f"/v1/sandboxes/{self._sandbox_id}/processes/{self._id}/logs",
                    params={"tail": str(self.LOG_TAIL_BYTES)},
                )
            except Exception:
                # Likely 404 (process already cleaned up) — fall through to
                # state poll which will set the exit code.
                log_resp = None

            if log_resp is not None:
                text = log_resp.text
                if len(text) > self._log_offset:
                    new_chunk = text[self._log_offset :]
                    self._log_offset = len(text)
                    if new_chunk:
                        self._emit("stdout", new_chunk)
                elif len(text) < self._log_offset:
                    # Server rotated / truncated the tail window — reset
                    # offset to current end to avoid double-emitting.
                    self._log_offset = len(text)

        # 2. Check process state.
        try:
            list_resp = await self._client.get(
                f"/v1/sandboxes/{self._sandbox_id}/processes"
            )
        except Exception:
            return  # transient — try next tick

        for entry in list_resp.json().get("processes", []):
            if entry.get("id") != self._id:
                continue
            state = entry.get("state")
            if state in ("exited", "killed", "failed"):
                # Final drain in case more bytes arrived since the log poll.
                await self._final_log_drain()
                self._mark_exited(int(entry.get("exit_code", 0) or 0))
            return

        # Process not in list at all → assume cleaned up / unknown exit.
        await self._final_log_drain()
        self._mark_exited(-1)

    async def _final_log_drain(self) -> None:
        async with self._poll_lock:
            try:
                resp = await self._client.get(
                    f"/v1/sandboxes/{self._sandbox_id}/processes/{self._id}/logs",
                    params={"tail": str(self.LOG_TAIL_BYTES)},
                )
            except Exception:
                return
            text = resp.text
            if len(text) > self._log_offset:
                self._emit("stdout", text[self._log_offset :])
                self._log_offset = len(text)

    def _mark_exited(self, exit_code: int) -> None:
        if self._done.is_set():
            return
        self._exit_code = exit_code
        self._done.set()
        self._emit("exit", exit_code)
        # Best-effort cancel of the poll task in case _mark_exited is called
        # by the caller (kill()) before the loop notices.
        if self._poll_task is not None and not self._poll_task.done():
            self._poll_task.cancel()

    async def aclose(self) -> None:
        """Stop polling and release resources. Safe to call multiple times."""
        if self._poll_task is not None and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._poll_task

    @classmethod
    def _from_api(cls, data: dict[str, Any], sandbox_id: str, client: Client) -> Process:
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
