"""Sync/async dual-mode entry point helper.

Design:
- If called from within a running event loop, the coroutine is returned
  as-is so the caller can ``await`` it.
- If called from synchronous code (no running loop), ``asyncio.run()``
  executes the coroutine and returns the result directly.

This lets ``Sandbox.create(...)`` work both as ``await Sandbox.create(...)``
and as a plain synchronous call from a REPL or script.

We deliberately avoid nest_asyncio or thread-based hacks.
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def maybe_await(coro: Coroutine[Any, Any, T]) -> Any:
    """Return the coroutine directly if inside an event loop, else run it.

    The return type is ``T | Coroutine[Any, Any, T]`` depending on context.
    Callers that are always in async context should just ``await`` the result
    of the calling classmethod which itself returns a coroutine object.
    """
    try:
        asyncio.get_running_loop()
        # Inside a running loop — return coroutine for caller to await
        return coro
    except RuntimeError:
        # No running loop — run synchronously
        return asyncio.run(coro)
