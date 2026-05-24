"""Sandbox — main entry point for talon-sandbox SDK v2."""
from __future__ import annotations

import builtins
import shlex
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ._async_compat import maybe_await
from ._client import Client
from ._parse import parse_duration, parse_size
from .process import Process, ProcessResult

if TYPE_CHECKING:
    from .browser import Browser
    from .env import Env
    from .fs import Fs
    from .terminal import Terminal

_VALID_NETWORKS = frozenset(
    {
        "allowlist",
        "open",
        "sealed",
        "deny",
        "offline",
        "restricted-egress",
        "full-egress",
    }
)


def _build_create_body(
    image: str | None,
    resources: dict[str, Any] | None,
    network: str | None,
    env: dict[str, str] | None,
    timeout: str | int | None,
    ttl: str | int | None,
    labels: dict[str, str] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if image:
        body["image_id"] = image
    if network:
        if network not in _VALID_NETWORKS:
            raise ValueError(
                f"network={network!r} invalid, expected: "
                "allowlist|open|sealed|deny|offline|restricted-egress|full-egress"
            )
        body["network_policy"] = network
    if env:
        body["env"] = env
    if labels:
        body["labels"] = labels

    if resources:
        if "cpu" in resources:
            cpu = resources["cpu"]
            if isinstance(cpu, float) and cpu < 10:
                body["cpu_millis"] = int(cpu * 1000)
            elif isinstance(cpu, int) and cpu < 100:
                body["cpu_millis"] = cpu * 1000
            else:
                body["cpu_millis"] = int(cpu)
        if "memory" in resources:
            body["memory_bytes"] = parse_size(resources["memory"])
        if "disk" in resources:
            body["disk_bytes"] = parse_size(resources["disk"])

    if timeout is not None:
        body["idle_timeout_seconds"] = parse_duration(timeout)
    if ttl is not None:
        body["ttl_seconds"] = parse_duration(ttl)

    return body


class Sandbox:
    """Talon Sandbox — create and control isolated execution environments.

    Async usage::

        sb = await Sandbox.create(image="node:20-bookworm", resources={"cpu": 2, "memory": "4GiB"})
        result = await sb.run("node --version")
        print(result.stdout)
        await sb.kill()

    Sync usage (no await)::

        sb = Sandbox.create(image="node:20-bookworm")
        print(sb.id)
    """

    def __init__(self, data: dict[str, Any], client: Client) -> None:
        self._data = data
        self._client = client

        from .browser import Browser
        from .env import Env
        from .fs import Fs
        from .terminal import Terminal

        self.fs: Fs = Fs(self._data["id"], client)
        self.env: Env = Env(self._data["id"], client)
        self.browser: Browser = Browser(self._data["id"], client)
        self.terminal: Terminal = Terminal(self._data["id"], client)

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def id(self) -> str:
        return str(self._data["id"])

    @property
    def state(self) -> str:
        return str(self._data.get("state", "unknown"))

    @property
    def image(self) -> str:
        return str(self._data.get("image_id", ""))

    @property
    def created_at(self) -> datetime:
        ts = self._data.get("created_at", 0)
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)

    @property
    def labels(self) -> dict[str, str]:
        raw = self._data.get("labels") or {}
        return {str(k): str(v) for k, v in raw.items()}

    @property
    def network(self) -> str:
        return str(self._data.get("network_policy", ""))

    # ── Factory methods ───────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        *,
        image: str | None = None,
        resources: dict[str, Any] | None = None,
        network: str | None = None,
        env: dict[str, str] | None = None,
        timeout: str | int | None = None,
        ttl: str | int | None = None,
        labels: dict[str, str] | None = None,
        wait: bool = True,
        client: Client | None = None,
        server: str | None = None,
        api_key: str | None = None,
    ) -> Any:
        """Create a new sandbox.

        Works both with and without ``await``::

            sb = await Sandbox.create(image="node:20-bookworm")  # async
            sb = Sandbox.create(image="node:20-bookworm")        # sync
        """
        # Validate early (before creating coroutine) so sync callers get immediate errors
        if network is not None and network not in _VALID_NETWORKS:
            raise ValueError(
                f"network={network!r} invalid, expected: "
                "allowlist|open|sealed|deny|offline|restricted-egress|full-egress"
            )

        async def _create() -> Sandbox:
            c = client or Client(server=server, api_key=api_key)
            body = _build_create_body(image, resources, network, env, timeout, ttl, labels)
            params: dict[str, str] = {"wait": "running"} if wait else {}
            resp = await c.post("/v1/sandboxes", json=body, params=params)
            return cls(resp.json(), c)

        return maybe_await(_create())

    @classmethod
    def get(
        cls,
        sandbox_id: str,
        *,
        client: Client | None = None,
        server: str | None = None,
        api_key: str | None = None,
    ) -> Any:
        """Attach to an existing sandbox by ID."""

        async def _get() -> Sandbox:
            c = client or Client(server=server, api_key=api_key)
            resp = await c.get(f"/v1/sandboxes/{sandbox_id}")
            return cls(resp.json(), c)

        return maybe_await(_get())

    @classmethod
    def list(
        cls,
        *,
        labels: dict[str, str] | None = None,
        client: Client | None = None,
        server: str | None = None,
        api_key: str | None = None,
    ) -> Any:
        """List all sandboxes for the current tenant."""

        async def _list() -> list[Sandbox]:
            c = client or Client(server=server, api_key=api_key)
            resp = await c.get("/v1/sandboxes")
            data = resp.json()
            sandboxes: list[dict[str, Any]] = data.get("sandboxes", [])
            if labels:
                sandboxes = [
                    s
                    for s in sandboxes
                    if all(
                        (s.get("labels") or {}).get(k) == v for k, v in labels.items()
                    )
                ]
            return [cls(s, c) for s in sandboxes]

        return maybe_await(_list())

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def pause(self) -> None:
        """Freeze all processes inside the sandbox."""
        await self._client.post(f"/v1/sandboxes/{self.id}/pause")

    async def resume(self) -> None:
        """Resume a paused sandbox."""
        await self._client.post(f"/v1/sandboxes/{self.id}/resume")

    async def kill(self) -> None:
        """Destroy the sandbox (irreversible)."""
        await self._client.delete(f"/v1/sandboxes/{self.id}")

    # ── Command execution ─────────────────────────────────────────────────

    async def run(
        self,
        command: str | builtins.list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> ProcessResult:
        """Run a command synchronously and return the result.

        Args:
            command: Shell command string or argv list.
            env: Additional environment variables.
            cwd: Working directory inside sandbox.

        Returns:
            ProcessResult with stdout, stderr, exit_code, duration.
        """
        if isinstance(command, str):
            cmd_list = shlex.split(command)
        else:
            cmd_list = list(command)

        body: dict[str, Any] = {"command": cmd_list}
        if env:
            body["env"] = [f"{k}={v}" for k, v in env.items()]
        if cwd:
            body["cwd"] = cwd

        t0 = time.monotonic()
        resp = await self._client.post(
            f"/v1/sandboxes/{self.id}/exec",
            json=body,
        )
        elapsed = time.monotonic() - t0

        data = resp.json()
        return ProcessResult(
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            exit_code=int(data.get("exit_code", 0)),
            duration=elapsed,
        )

    async def spawn(
        self,
        command: str | builtins.list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> Process:
        """Start a long-running process and return a handle.

        Args:
            command: Shell command string or argv list.
            env: Additional environment variables.
            cwd: Working directory inside sandbox.

        Returns:
            Process handle with EventEmitter interface.
        """
        if isinstance(command, str):
            cmd_list = shlex.split(command)
        else:
            cmd_list = list(command)

        body: dict[str, Any] = {"command": cmd_list}
        if env:
            body["env"] = [f"{k}={v}" for k, v in env.items()]
        if cwd:
            body["cwd"] = cwd

        resp = await self._client.post(
            f"/v1/sandboxes/{self.id}/processes",
            json=body,
        )
        return Process._from_api(resp.json(), self.id, self._client)

    async def processes(self) -> builtins.list[Process]:
        """List all processes running in the sandbox."""
        resp = await self._client.get(f"/v1/sandboxes/{self.id}/processes")
        data = resp.json()
        return [
            Process._from_api(p, self.id, self._client)
            for p in data.get("processes", [])
        ]

    # ── Port exposure ─────────────────────────────────────────────────────

    async def expose(
        self,
        port: int,
        *,
        sign: bool = False,
        ttl: str | None = None,
        subdomain: str | None = None,
    ) -> str:
        """Expose a sandbox port and return its preview URL.

        Args:
            port: Container port to expose (1-65535).
            sign: Issue a signed URL (Spec 48).
            ttl: Token lifetime, e.g. "1h" (only with sign=True).
            subdomain: Custom subdomain prefix.

        Returns:
            Preview URL string.

        Raises:
            NotImplementedError: If server does not yet support the expose endpoint.
        """
        body: dict[str, Any] = {"port": port, "sign": sign}
        if ttl:
            body["ttl"] = ttl
        if subdomain:
            body["subdomain"] = subdomain

        from .errors import NotFoundError

        try:
            resp = await self._client.post(
                f"/v1/sandboxes/{self.id}/expose",
                json=body,
            )
        except NotFoundError as e:
            raise NotImplementedError(
                "sb.expose() requires server v1.1+ (Spec 50). "
                "Upgrade your talon-sandbox server or use the preview proxy directly."
            ) from e

        return str(resp.json()["url"])

    async def unexpose(self, port: int) -> None:
        """Remove a port exposure."""
        await self._client.delete(f"/v1/sandboxes/{self.id}/expose/{port}")

    async def exposed(self) -> builtins.list[dict[str, Any]]:
        """List all exposed ports and their URLs."""
        resp = await self._client.get(f"/v1/sandboxes/{self.id}/expose")
        result: list[dict[str, Any]] = resp.json().get("ports", [])
        return result

    # ── Context manager ───────────────────────────────────────────────────

    async def __aenter__(self) -> Sandbox:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.kill()

    def __repr__(self) -> str:
        return f"Sandbox(id={self.id!r}, state={self.state!r})"
