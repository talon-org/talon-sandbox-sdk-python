"""Typed async-safe EventEmitter for talon-sandbox SDK."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


class EventEmitter:
    """Lightweight event emitter with sync and async callback support.

    Usage::

        class MyStream(EventEmitter):
            EVENTS = frozenset({"data", "close", "error"})

        stream = MyStream()
        stream.on("data", lambda chunk: print(chunk))
        stream._emit("data", b"hello")
    """

    #: Subclasses should override with the set of valid event names.
    EVENTS: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Any]]] = {}

    def on(self, event: str, callback: Callable[..., Any]) -> EventEmitter:
        """Register *callback* for *event*. Returns self for chaining."""
        self._validate_event(event)
        self._listeners.setdefault(event, []).append(callback)
        return self

    def off(self, event: str, callback: Callable[..., Any]) -> EventEmitter:
        """Remove *callback* from *event* listeners."""
        try:
            self._listeners.get(event, []).remove(callback)
        except ValueError:
            pass
        return self

    def _emit(self, event: str, *args: Any) -> None:
        """Call all listeners for *event* with *args*.

        Sync callbacks are called directly. Async callbacks are scheduled
        as tasks on the running event loop if one exists.
        """
        for cb in list(self._listeners.get(event, [])):
            if asyncio.iscoroutinefunction(cb):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cb(*args))
                except RuntimeError:
                    # No event loop — skip async callback
                    pass
            else:
                cb(*args)

    def _validate_event(self, event: str) -> None:
        if self.EVENTS and event not in self.EVENTS:
            raise ValueError(
                f"Unknown event {event!r}. Valid events: {sorted(self.EVENTS)}"
            )
