"""talon-sandbox — Python SDK v2.

Run code in isolated sandboxes from Python.

Quick start::

    from talon_sandbox import Sandbox

    async def main():
        async with await Sandbox.create(image="node:20-bookworm") as sb:
            result = await sb.run("node --version")
            print(result.stdout)

Or synchronously::

    sb = Sandbox.create(image="node:20-bookworm")
    print(sb.id)
"""
from __future__ import annotations

from ._client import Client
from ._config import configure
from .browser import Browser, BrowserSession
from .env import Env
from .errors import (
    AuthError,
    ConflictError,
    NetworkError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    SandboxError,
    ServerError,
    TimeoutError,
)
from .fs import Fs, FsEntry, FsInfo
from .process import Process, ProcessResult
from .sandbox import Sandbox
from .terminal import PTYSession, Terminal

__version__ = "0.1.0"
__all__ = [
    # Core
    "Sandbox",
    "configure",
    "Client",
    # Sub-objects
    "Fs",
    "FsEntry",
    "FsInfo",
    "Env",
    "Browser",
    "BrowserSession",
    "Terminal",
    "PTYSession",
    "Process",
    "ProcessResult",
    # Errors
    "SandboxError",
    "AuthError",
    "NotFoundError",
    "QuotaError",
    "RateLimitError",
    "TimeoutError",
    "NetworkError",
    "ServerError",
    "ConflictError",
]
