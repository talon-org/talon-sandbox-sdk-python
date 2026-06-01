"""Tests for sb.start() / sb.stop()."""
from __future__ import annotations

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

BASE = "https://api.sandbox.talon.net.cn"


@pytest.mark.asyncio
async def test_start_calls_correct_endpoint() -> None:
    """sb.start() 应 POST /v1/sandboxes/{id}/start 并成功（204）。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        start_route = router.post("/v1/sandboxes/sbx_test123/start").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.start()
        assert start_route.called


@pytest.mark.asyncio
async def test_stop_calls_correct_endpoint() -> None:
    """sb.stop() 应 POST /v1/sandboxes/{id}/stop 并成功（204）。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        stop_route = router.post("/v1/sandboxes/sbx_test123/stop").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.stop()
        assert stop_route.called


@pytest.mark.asyncio
async def test_start_and_stop_are_independent() -> None:
    """start/stop 与 pause/resume 互不干扰，四个方法都可正常调用。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/start").mock(return_value=httpx.Response(204))
        router.post("/v1/sandboxes/sbx_test123/stop").mock(return_value=httpx.Response(204))
        router.post("/v1/sandboxes/sbx_test123/pause").mock(return_value=httpx.Response(204))
        router.post("/v1/sandboxes/sbx_test123/resume").mock(return_value=httpx.Response(204))

        sb = await Sandbox.create()
        await sb.stop()
        await sb.start()
        await sb.pause()
        await sb.resume()
