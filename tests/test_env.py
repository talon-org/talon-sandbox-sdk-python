"""Tests for sb.env.*"""
from __future__ import annotations

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

BASE = "http://localhost:18080"


@pytest.mark.asyncio
async def test_env_get() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/env").mock(
            return_value=httpx.Response(200, json={"env": {"NODE_ENV": "development"}})
        )
        sb = await Sandbox.create()
        val = await sb.env.get("NODE_ENV")
        assert val == "development"


@pytest.mark.asyncio
async def test_env_get_missing_returns_none() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/env").mock(
            return_value=httpx.Response(200, json={"env": {}})
        )
        sb = await Sandbox.create()
        val = await sb.env.get("MISSING")
        assert val is None


@pytest.mark.asyncio
async def test_env_set() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        set_route = router.put("/v1/sandboxes/sbx_test123/env").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.env.set("API_KEY", "sk-...")
        assert set_route.called


@pytest.mark.asyncio
async def test_env_unset() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        unset_route = router.delete("/v1/sandboxes/sbx_test123/env/OLD").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.env.unset("OLD")
        assert unset_route.called


@pytest.mark.asyncio
async def test_env_all() -> None:
    env_data = {"NODE_ENV": "development", "PORT": "3000"}
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/env").mock(
            return_value=httpx.Response(200, json={"env": env_data})
        )
        sb = await Sandbox.create()
        all_env = await sb.env.all()
        assert all_env == env_data
