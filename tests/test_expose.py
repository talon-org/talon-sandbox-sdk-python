"""Tests for sb.expose / unexpose / exposed."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

# 默认端点与 _config.py resolve_server() 默认值保持一致
BASE = "https://api.sandbox.talon.net.cn"

EXPOSE_RESP = {
    "port": 5173,
    "url": "https://sb-test123-5173.preview.example.com",
    "signed": False,
    "expires_at": None,
}


@pytest.mark.asyncio
async def test_expose_returns_url() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/expose").mock(
            return_value=httpx.Response(200, json=EXPOSE_RESP)
        )
        sb = await Sandbox.create()
        url = await sb.expose(5173)
        assert url == "https://sb-test123-5173.preview.example.com"


@pytest.mark.asyncio
async def test_expose_sends_correct_body() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        route = router.post("/v1/sandboxes/sbx_test123/expose").mock(
            return_value=httpx.Response(200, json=EXPOSE_RESP)
        )
        sb = await Sandbox.create()
        await sb.expose(5173)
        payload = json.loads(route.calls[0].request.read())
        assert payload["port"] == 5173
        assert payload["sign"] is False


@pytest.mark.asyncio
async def test_expose_with_sign_and_options() -> None:
    signed_resp = {**EXPOSE_RESP, "signed": True, "expires_at": "2026-05-24T13:00:00Z"}
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        route = router.post("/v1/sandboxes/sbx_test123/expose").mock(
            return_value=httpx.Response(200, json=signed_resp)
        )
        sb = await Sandbox.create()
        url = await sb.expose(5173, sign=True, ttl="1h", subdomain="my-app")
        payload = json.loads(route.calls[0].request.read())
        assert payload["sign"] is True
        assert payload["ttl"] == "1h"
        assert payload["subdomain"] == "my-app"
        assert "preview" in url


@pytest.mark.asyncio
async def test_expose_404_raises_not_implemented() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/expose").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        sb = await Sandbox.create()
        with pytest.raises(NotImplementedError, match="(?i)upgrade"):
            await sb.expose(5173)


@pytest.mark.asyncio
async def test_unexpose() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        del_route = router.delete("/v1/sandboxes/sbx_test123/expose/5173").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.unexpose(5173)
        assert del_route.called


@pytest.mark.asyncio
async def test_exposed_list() -> None:
    ports_resp = {
        "ports": [
            {
                "port": 5173,
                "url": "https://sb-test123-5173.preview.example.com",
                "signed": False,
            }
        ]
    }
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/expose").mock(
            return_value=httpx.Response(200, json=ports_resp)
        )
        sb = await Sandbox.create()
        ports = await sb.exposed()
        assert len(ports) == 1
        assert ports[0]["port"] == 5173


@pytest.mark.asyncio
async def test_exposed_empty() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/expose").mock(
            return_value=httpx.Response(200, json={"ports": []})
        )
        sb = await Sandbox.create()
        ports = await sb.exposed()
        assert ports == []
