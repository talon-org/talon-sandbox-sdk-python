"""Tests for sb.run() and sb.spawn()."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import PROCESS_DATA, SANDBOX_DATA

BASE = "http://localhost:18080"


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
