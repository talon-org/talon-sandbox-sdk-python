"""Tests for sb.terminal PTY session."""
from __future__ import annotations

import asyncio

import pytest

from talon_sandbox.errors import SandboxError
from talon_sandbox.terminal import PTYSession


class FakeWS:
    """Minimal fake WebSocket for unit tests."""

    sent: list[bytes]

    def __init__(self) -> None:
        self.sent = []
        self._closed = False

    async def send(self, data: bytes) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self._closed = True

    def __aiter__(self) -> "FakeWS":
        return self

    async def __anext__(self) -> bytes:
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_pty_event_emitter_on_data() -> None:
    session = PTYSession(FakeWS())
    received: list[bytes] = []
    session.on("data", lambda chunk: received.append(chunk))
    session._emit("data", b"hello")
    assert received == [b"hello"]


@pytest.mark.asyncio
async def test_pty_write_encodes_string() -> None:
    ws = FakeWS()
    session = PTYSession(ws)
    await session.write("ls\n")
    assert ws.sent == [b"ls\n"]


@pytest.mark.asyncio
async def test_pty_write_bytes() -> None:
    ws = FakeWS()
    session = PTYSession(ws)
    await session.write(b"\x03")
    assert ws.sent == [b"\x03"]


@pytest.mark.asyncio
async def test_pty_close_marks_closed() -> None:
    ws = FakeWS()
    session = PTYSession(ws)
    await session.close()
    assert session._closed is True


@pytest.mark.asyncio
async def test_pty_write_after_close_raises() -> None:
    ws = FakeWS()
    session = PTYSession(ws)
    session._closed = True
    with pytest.raises(SandboxError, match="closed"):
        await session.write("ls")


@pytest.mark.asyncio
async def test_pty_off_removes_listener() -> None:
    session = PTYSession(FakeWS())
    calls: list[bytes] = []

    def cb(chunk: bytes) -> None:
        calls.append(chunk)

    session.on("data", cb)
    session._emit("data", b"x")
    session.off("data", cb)
    session._emit("data", b"y")
    assert calls == [b"x"]


@pytest.mark.asyncio
async def test_pty_multiple_listeners() -> None:
    session = PTYSession(FakeWS())
    a: list[bytes] = []
    b: list[bytes] = []
    session.on("data", lambda chunk: a.append(chunk))
    session.on("data", lambda chunk: b.append(chunk))
    session._emit("data", b"hello")
    assert a == [b"hello"]
    assert b == [b"hello"]


@pytest.mark.asyncio
async def test_pty_invalid_event_raises() -> None:
    session = PTYSession(FakeWS())
    with pytest.raises(ValueError, match="Unknown event"):
        session.on("invalid", lambda x: None)


@pytest.mark.asyncio
async def test_pty_context_manager() -> None:
    ws = FakeWS()
    session = PTYSession(ws)
    async with session:
        session._emit("data", b"hi")
    assert session._closed is True


@pytest.mark.asyncio
async def test_pty_exit_event() -> None:
    session = PTYSession(FakeWS())
    exits: list[int] = []
    session.on("exit", lambda code: exits.append(code))
    session._emit("exit", 0)
    assert exits == [0]
