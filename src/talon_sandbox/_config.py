"""Global configuration for talon-sandbox SDK."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class _Config:
    server: str | None = None
    api_key: str | None = None


_global_config = _Config()


def configure(
    *,
    server: str | None = None,
    api_key: str | None = None,
) -> None:
    """Set global defaults for all Sandbox operations.

    These are overridden by explicit ``client=`` arguments.
    Environment variables take the highest precedence.

    Example::

        from talon_sandbox import configure
        configure(server="https://api.sandbox.talon.net.cn", api_key="ask_...")
    """
    _global_config.server = server
    _global_config.api_key = api_key


def resolve_server(explicit: str | None = None) -> str:
    """Resolve server URL: env > explicit > global > default.

    默认指向官方托管端点；自部署用户可通过环境变量或显式参数覆盖。
    """
    return (
        os.environ.get("TALON_SANDBOX_SERVER")
        or explicit
        or _global_config.server
        or "https://api.sandbox.talon.net.cn"
    ).rstrip("/")


def resolve_api_key(explicit: str | None = None) -> str | None:
    """Resolve API key: env > explicit > global."""
    return (
        os.environ.get("TALON_SANDBOX_API_KEY")
        or explicit
        or _global_config.api_key
    )
