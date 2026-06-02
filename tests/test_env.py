"""Tests for sb.env.*"""
from __future__ import annotations

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

# 默认端点与 _config.py resolve_server() 默认值保持一致
BASE = "https://api.sandbox.talon.net.cn"


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
    """PUT /v1/sandboxes/{id}/env/{key} with body {"value": ...}."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        set_route = router.put("/v1/sandboxes/sbx_test123/env/API_KEY").mock(
            return_value=httpx.Response(200, json={"env": {"API_KEY": "sk-..."}})
        )
        sb = await Sandbox.create()
        await sb.env.set("API_KEY", "sk-...")
        assert set_route.called
        sent = set_route.calls.last.request
        import json as _json
        body = _json.loads(sent.content)
        assert body == {"value": "sk-..."}, f"unexpected body: {body}"
        assert "key" not in body, "body must not contain 'key' field"


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
async def test_env_set_url_encodes_key() -> None:
    """Keys with special characters are percent-encoded in the path."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        # Key "MY KEY" should be encoded as "MY%20KEY"
        set_route = router.put("/v1/sandboxes/sbx_test123/env/MY%20KEY").mock(
            return_value=httpx.Response(200, json={"env": {"MY KEY": "val"}})
        )
        sb = await Sandbox.create()
        await sb.env.set("MY KEY", "val")
        assert set_route.called


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
