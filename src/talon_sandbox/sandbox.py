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
    network_allowed_hosts: list[str] | None = None,
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
    # 仅 allowlist/restricted-egress 策略有意义。
    # 非空时覆盖 worker 全局白名单；空/None 则回退到全局配置。
    if network_allowed_hosts:
        body["network_allowed_hosts"] = network_allowed_hosts
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

        sb = await Sandbox.create(image="talon-alpine", resources={"cpu": 2, "memory": "4GiB"})
        result = await sb.run("node --version")
        print(result.stdout)
        await sb.kill()

    Sync usage (no await)::

        sb = Sandbox.create(image="talon-alpine")
        print(sb.id)
    """

    def __init__(
        self,
        data: dict[str, Any],
        client: Client,
        *,
        owns_client: bool = False,
    ) -> None:
        self._data = data
        self._client = client
        # True when this Sandbox instantiated the Client itself (vs the caller
        # passing `client=` for sharing across multiple Sandbox instances).
        # On owned clients, kill() / __aexit__ also close the httpx pool so
        # long-running agents don't leak connections.
        self._owns_client = owns_client

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
        network_allowed_hosts: list[str] | None = None,
        wait: bool = True,
        client: Client | None = None,
        server: str | None = None,
        api_key: str | None = None,
    ) -> Any:
        """Create a new sandbox.

        Works both with and without ``await``::

            sb = await Sandbox.create(image="talon-alpine")  # async
            sb = Sandbox.create(image="talon-alpine")        # sync

        Args:
            network_allowed_hosts: allowlist/restricted-egress 策略下放行的 host 列表
                （域名/IP/CIDR）。非空时覆盖 worker 全局白名单；None 或空列表则回退全局。
                仅 allowlist 策略有意义，其他策略忽略此字段。
        """
        # Validate early (before creating coroutine) so sync callers get immediate errors
        if network is not None and network not in _VALID_NETWORKS:
            raise ValueError(
                f"network={network!r} invalid, expected: "
                "allowlist|open|sealed|deny|offline|restricted-egress|full-egress"
            )

        async def _create() -> Sandbox:
            owns = client is None
            c = client or Client(server=server, api_key=api_key)
            try:
                body = _build_create_body(
                    image, resources, network, env, timeout, ttl, labels,
                    network_allowed_hosts,
                )
                params: dict[str, str] = {"wait": "running"} if wait else {}
                resp = await c.post("/v1/sandboxes", json=body, params=params)
            except BaseException:
                # If create fails and we own the client, don't leak its pool.
                if owns:
                    await c.aclose()
                raise
            return cls(resp.json(), c, owns_client=owns)

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
            owns = client is None
            c = client or Client(server=server, api_key=api_key)
            try:
                resp = await c.get(f"/v1/sandboxes/{sandbox_id}")
            except BaseException:
                if owns:
                    await c.aclose()
                raise
            return cls(resp.json(), c, owns_client=owns)

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
            owns = client is None
            c = client or Client(server=server, api_key=api_key)
            try:
                resp = await c.get("/v1/sandboxes")
            except BaseException:
                if owns:
                    await c.aclose()
                raise
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
            # Multiple Sandbox instances share a single client. The first
            # owns it so closing the first (or `async with` on it) tears
            # down the shared pool; the rest just hold a reference.
            result: list[Sandbox] = []
            for i, s in enumerate(sandboxes):
                result.append(cls(s, c, owns_client=(owns and i == 0)))
            if owns and not result:
                # Empty list with owned client: nothing to hold it. Close.
                await c.aclose()
            return result

        return maybe_await(_list())

    @classmethod
    def list_images(
        cls,
        *,
        client: Client | None = None,
        server: str | None = None,
        api_key: str | None = None,
    ) -> Any:
        """列出平台上所有可用的 sandbox 镜像（GET /v1/images）。

        这是顶层端点，与具体 sandbox 无关。

        Works both with and without ``await``::

            images = await Sandbox.list_images()   # async
            images = Sandbox.list_images()          # sync

        Returns:
            ``list[dict]``，每个 dict 对应一个 ImageDTO，字段：
            ``id``, ``name``, ``url``, ``sha256``, ``os``, ``arch``,
            ``source`` ("builtin"|"admin"), ``is_default``, ``description``,
            ``created_at``。
        """

        async def _list_images() -> list[dict[str, Any]]:
            owns = client is None
            c = client or Client(server=server, api_key=api_key)
            try:
                resp = await c.get("/v1/images")
                images: list[dict[str, Any]] = resp.json().get("images", [])
                return images
            finally:
                # images 是只读顶层端点，临时 client 用完即关；
                # 调用方显式传入的 client 不关（owns=False）。
                if owns:
                    await c.aclose()

        return maybe_await(_list_images())

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        """从 stopped 状态启动 sandbox（stopped→running）。

        与 resume（冻结态恢复）不同：start 针对的是完全停止的 sandbox。
        成功返回 None（后端 204 No Content）。
        """
        await self._client.post(f"/v1/sandboxes/{self.id}/start")

    async def stop(self) -> None:
        """将运行中的 sandbox 停止（running→stopped）。

        与 pause（冻结进程）不同：stop 彻底停止 sandbox，可通过 start() 重启。
        成功返回 None（后端 204 No Content）。
        """
        await self._client.post(f"/v1/sandboxes/{self.id}/stop")

    async def pause(self) -> None:
        """Freeze all processes inside the sandbox."""
        await self._client.post(f"/v1/sandboxes/{self.id}/pause")

    async def resume(self) -> None:
        """Resume a paused sandbox."""
        await self._client.post(f"/v1/sandboxes/{self.id}/resume")

    async def kill(self) -> None:
        """Destroy the sandbox (irreversible).

        If this Sandbox owns its HTTP client (created by ``create()`` /
        ``get()`` without an explicit ``client=`` arg), the underlying
        httpx connection pool is also closed to avoid leaking sockets in
        long-running agents.
        """
        from .errors import NotFoundError

        try:
            await self._client.delete(f"/v1/sandboxes/{self.id}")
        except NotFoundError:
            # Already gone — idempotent kill is the expected DX.
            pass
        finally:
            if self._owns_client:
                self._owns_client = False  # idempotent
                await self._client.aclose()

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
        expose_ports: builtins.list[int] | None = None,
    ) -> Process:
        """Start a long-running process and return a handle.

        Args:
            command: Shell command string or argv list.
            env: Additional environment variables.
            cwd: Working directory inside sandbox.
            expose_ports: 进程声明对外暴露的容器端口，如 [5173]。
                预览反向代理准入与 DNAT 路由依赖此字段；
                启动 dev server 等常驻服务时须传入，否则预览 URL 无法路由到该进程。

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
        if expose_ports:
            body["expose_ports"] = expose_ports

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

    # ── Agent run ─────────────────────────────────────────────────────────

    async def agent_run(
        self,
        goal: str,
        *,
        max_steps: int | None = None,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """在 sandbox 内同步执行 AI browser agent（Spec 38）。

        通过 POST /v1/sandboxes/{id}/agent/run 调用，最长阻塞 5 分钟。
        browser-harness 按 goal 自动操作 headless Chromium 完成任务。

        Args:
            goal: 用自然语言描述 agent 要完成的任务，例如 "搜索 Python 最新版本"。
            max_steps: 最大步骤数（默认 20，后端硬上限 100）。
            llm_model: 提示给 harness 使用的 LLM 型号，例如
                ``"anthropic:claude-sonnet-4-6"``。省略时 harness 使用默认模型。

        Returns:
            ``AgentRunResponse`` 字典，字段：
            ``run_id``, ``status`` (completed/failed/timeout),
            ``duration_ms``, ``steps`` (列表), ``result``, ``exit_code``, ``stderr``。

        Note:
            LLM API key 应通过 Spec 27 secrets 注入 sandbox 环境变量，
            不应放在请求体（避免被 audit log 记录）。
        """
        body: dict[str, Any] = {"goal": goal}
        if max_steps is not None:
            body["max_steps"] = max_steps
        if llm_model is not None:
            body["llm_model"] = llm_model

        resp = await self._client.post(
            f"/v1/sandboxes/{self.id}/agent/run",
            json=body,
        )
        result: dict[str, Any] = resp.json()
        return result

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
