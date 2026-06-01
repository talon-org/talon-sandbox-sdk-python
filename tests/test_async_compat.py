"""Tests for sync/async dual-mode entry point."""
from __future__ import annotations

import httpx
import pytest
import respx

from talon_sandbox import Sandbox

# 默认端点与 _config.py resolve_server() 默认值保持一致
BASE = "https://api.sandbox.talon.net.cn"

SANDBOX_RESP = {
    "id": "sbx_test123",
    "state": "running",
    "image_id": "node:20-bookworm",
    "cpu_millis": 2000,
    "memory_bytes": 4294967296,
    "created_at": 1716556800,
    "profile": "default",
}


@respx.mock
def test_sync_create_works_without_await() -> None:
    """Sandbox.create() without await should work in synchronous code."""
    respx.post(f"{BASE}/v1/sandboxes").mock(
        return_value=httpx.Response(201, json=SANDBOX_RESP)
    )
    # No await — synchronous call
    sb = Sandbox.create(image="node:20-bookworm")
    assert sb.id == "sbx_test123"
    assert sb.state == "running"


@pytest.mark.asyncio
async def test_async_create_works_with_await() -> None:
    """await Sandbox.create() should work inside an async context."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_RESP))
        sb = await Sandbox.create(image="node:20-bookworm")
        assert sb.id == "sbx_test123"


@respx.mock
def test_sync_get_works_without_await() -> None:
    """Sandbox.get() without await should work in synchronous code."""
    respx.get(f"{BASE}/v1/sandboxes/sbx_test123").mock(
        return_value=httpx.Response(200, json=SANDBOX_RESP)
    )
    sb = Sandbox.get("sbx_test123")
    assert sb.id == "sbx_test123"


@respx.mock
def test_sync_list_works_without_await() -> None:
    """Sandbox.list() without await should work in synchronous code."""
    respx.get(f"{BASE}/v1/sandboxes").mock(
        return_value=httpx.Response(200, json={"sandboxes": [SANDBOX_RESP]})
    )
    sbs = Sandbox.list()
    assert len(sbs) == 1
    assert sbs[0].id == "sbx_test123"
