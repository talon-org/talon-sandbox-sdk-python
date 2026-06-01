"""Tests for sb.run() and sb.spawn()."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import PROCESS_DATA, SANDBOX_DATA

# 默认端点与 _config.py resolve_server() 默认值保持一致
BASE = "https://api.sandbox.talon.net.cn"


@pytest.mark.asyncio
async def test_run_returns_process_result() -> None:
    exec_resp = {"stdout": "hello\n", "stderr": "", "exit_code": 0}
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/exec").mock(
            return_value=httpx.Response(200, json=exec_resp)
        )
        sb = await Sandbox.create()
        result = await sb.run("echo hello")
        assert result.stdout == "hello\n"
        assert result.exit_code == 0
        assert result.duration >= 0


@pytest.mark.asyncio
async def test_run_splits_shell_command() -> None:
    exec_resp = {"stdout": "", "stderr": "", "exit_code": 0}
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        route = router.post("/v1/sandboxes/sbx_test123/exec").mock(
            return_value=httpx.Response(200, json=exec_resp)
        )
        sb = await Sandbox.create()
        await sb.run("npm install --save-dev")
        payload = json.loads(route.calls[0].request.read())
        assert payload["command"] == ["npm", "install", "--save-dev"]


@pytest.mark.asyncio
async def test_run_accepts_list() -> None:
    exec_resp = {"stdout": "ok", "stderr": "", "exit_code": 0}
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        route = router.post("/v1/sandboxes/sbx_test123/exec").mock(
            return_value=httpx.Response(200, json=exec_resp)
        )
        sb = await Sandbox.create()
        result = await sb.run(["node", "--version"])
        payload = json.loads(route.calls[0].request.read())
        assert payload["command"] == ["node", "--version"]
        assert result.stdout == "ok"


@pytest.mark.asyncio
async def test_spawn_returns_process_handle() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        sb = await Sandbox.create()
        proc = await sb.spawn("npm run dev")
        assert proc.id == "proc_abc123"
        assert proc.pid == 42


@pytest.mark.asyncio
async def test_spawn_kill() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        kill_route = router.delete(
            "/v1/sandboxes/sbx_test123/processes/proc_abc123"
        ).mock(return_value=httpx.Response(204))
        sb = await Sandbox.create()
        proc = await sb.spawn("npm run dev")
        await proc.kill()
        assert kill_route.called


@pytest.mark.asyncio
async def test_processes_list() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(200, json={"processes": [PROCESS_DATA]})
        )
        sb = await Sandbox.create()
        procs = await sb.processes()
        assert len(procs) == 1
        assert procs[0].id == "proc_abc123"


@pytest.mark.asyncio
async def test_spawn_event_emitter() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        sb = await Sandbox.create()
        proc = await sb.spawn("npm run dev")
        exits: list[int] = []
        proc.on("exit", lambda code: exits.append(code))
        proc._mark_exited(0)
        assert exits == [0]
        assert proc.exit_code == 0


# ─── Spawn streaming (C1 regression) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_spawn_wait_resolves_when_process_exits() -> None:
    """proc.wait() must return when the server marks the process exited."""
    exited = {**PROCESS_DATA, "state": "exited", "exit_code": 0}
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        router.get(
            "/v1/sandboxes/sbx_test123/processes/proc_abc123/logs"
        ).mock(return_value=httpx.Response(200, text=""))
        # First /processes call returns running, second returns exited.
        router.get("/v1/sandboxes/sbx_test123/processes").mock(
            side_effect=[
                httpx.Response(200, json={"processes": [PROCESS_DATA]}),
                httpx.Response(200, json={"processes": [exited]}),
            ]
        )
        # Speed up the poll loop so the test finishes quickly.
        from talon_sandbox.process import Process
        Process.POLL_INTERVAL_SEC = 0.01

        sb = await Sandbox.create()
        proc = await sb.spawn("npm run dev")
        code = await asyncio.wait_for(proc.wait(), timeout=2.0)
        assert code == 0
        assert proc.exit_code == 0


@pytest.mark.asyncio
async def test_spawn_emits_stdout_chunks() -> None:
    """As log bytes accumulate server-side, proc.on('stdout') should fire."""
    exited = {**PROCESS_DATA, "state": "exited", "exit_code": 0}
    log_responses = iter([
        httpx.Response(200, text="hello\n"),
        httpx.Response(200, text="hello\nworld\n"),
        httpx.Response(200, text="hello\nworld\n"),  # final drain
    ])
    list_responses = iter([
        httpx.Response(200, json={"processes": [PROCESS_DATA]}),
        httpx.Response(200, json={"processes": [exited]}),
    ])
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        router.get(
            "/v1/sandboxes/sbx_test123/processes/proc_abc123/logs"
        ).mock(side_effect=lambda req: next(log_responses))
        router.get("/v1/sandboxes/sbx_test123/processes").mock(
            side_effect=lambda req: next(list_responses)
        )
        from talon_sandbox.process import Process
        Process.POLL_INTERVAL_SEC = 0.01

        sb = await Sandbox.create()
        proc = await sb.spawn("npm run dev")
        chunks: list[str] = []
        proc.on("stdout", lambda c: chunks.append(c))
        code = await asyncio.wait_for(proc.wait(), timeout=2.0)
        assert code == 0
        combined = "".join(chunks)
        assert "hello" in combined
        assert "world" in combined
        # No double-emission of "hello" prefix on the second tick.
        assert combined.count("hello") == 1


@pytest.mark.asyncio
async def test_spawn_expose_ports_sent_in_body() -> None:
    """spawn(expose_ports=[5173]) 应将 expose_ports 写入请求体。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        spawn_route = router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        sb = await Sandbox.create()
        proc = await sb.spawn("npm run dev", expose_ports=[5173])
        assert proc.id == "proc_abc123"
        payload = json.loads(spawn_route.calls[0].request.read())
        assert payload["expose_ports"] == [5173]


@pytest.mark.asyncio
async def test_spawn_expose_ports_none_omitted() -> None:
    """spawn() 不传 expose_ports 时请求体不含该字段。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        spawn_route = router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        sb = await Sandbox.create()
        await sb.spawn("npm run dev")
        payload = json.loads(spawn_route.calls[0].request.read())
        assert "expose_ports" not in payload


@pytest.mark.asyncio
async def test_spawn_expose_ports_multiple() -> None:
    """spawn(expose_ports=[3000, 8080]) 支持多端口列表。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        spawn_route = router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        sb = await Sandbox.create()
        await sb.spawn("python -m http.server 3000", expose_ports=[3000, 8080])
        payload = json.loads(spawn_route.calls[0].request.read())
        assert payload["expose_ports"] == [3000, 8080]


@pytest.mark.asyncio
async def test_spawn_kill_unblocks_wait() -> None:
    """proc.kill() must cause wait() to return even if poll never sees exit."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(201, json=PROCESS_DATA)
        )
        router.delete(
            "/v1/sandboxes/sbx_test123/processes/proc_abc123"
        ).mock(return_value=httpx.Response(204))
        router.get(
            "/v1/sandboxes/sbx_test123/processes/proc_abc123/logs"
        ).mock(return_value=httpx.Response(200, text=""))
        router.get("/v1/sandboxes/sbx_test123/processes").mock(
            return_value=httpx.Response(200, json={"processes": [PROCESS_DATA]})
        )
        from talon_sandbox.process import Process
        Process.POLL_INTERVAL_SEC = 0.5  # slow poll so kill wins the race

        sb = await Sandbox.create()
        proc = await sb.spawn("sleep 999")

        async def kill_after_delay() -> None:
            await asyncio.sleep(0.05)
            await proc.kill()

        kill_task = asyncio.create_task(kill_after_delay())
        code = await asyncio.wait_for(proc.wait(), timeout=2.0)
        await kill_task
        # Server didn't mark exited; kill() forced it. -1 is our sentinel.
        assert code == -1
