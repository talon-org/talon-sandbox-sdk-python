"""Tests for Sandbox lifecycle."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

# 默认端点与 _config.py resolve_server() 默认值保持一致
BASE = "https://api.sandbox.talon.net.cn"


@pytest.mark.asyncio
async def test_create_returns_sandbox() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        sb = await Sandbox.create(image="node:20-bookworm")
        assert sb.id == "sbx_test123"
        assert sb.state == "running"


@pytest.mark.asyncio
async def test_create_normalizes_resources() -> None:
    with respx.mock(base_url=BASE) as router:
        route = router.post("/v1/sandboxes").mock(
            return_value=httpx.Response(201, json=SANDBOX_DATA)
        )
        await Sandbox.create(
            image="node:20-bookworm",
            resources={"cpu": 2, "memory": "4GiB"},
        )
        payload = json.loads(route.calls[0].request.read())
        assert payload["cpu_millis"] == 2000
        assert payload["memory_bytes"] == 4 * 1024**3


@pytest.mark.asyncio
async def test_create_normalizes_timeout_string() -> None:
    with respx.mock(base_url=BASE) as router:
        route = router.post("/v1/sandboxes").mock(
            return_value=httpx.Response(201, json=SANDBOX_DATA)
        )
        await Sandbox.create(timeout="30m", ttl="6h")
        payload = json.loads(route.calls[0].request.read())
        assert payload["idle_timeout_seconds"] == 1800
        assert payload["ttl_seconds"] == 21600


@pytest.mark.asyncio
async def test_get_attaches_to_existing() -> None:
    with respx.mock(base_url=BASE) as router:
        router.get("/v1/sandboxes/sbx_test123").mock(
            return_value=httpx.Response(200, json=SANDBOX_DATA)
        )
        sb = await Sandbox.get("sbx_test123")
        assert sb.id == "sbx_test123"


@pytest.mark.asyncio
async def test_list_returns_filtered_by_labels() -> None:
    """客户端兜底过滤：服务端返回全量结果，客户端按 labels 过滤后只剩匹配项。"""
    data = {
        "sandboxes": [
            {**SANDBOX_DATA, "labels": {"project": "agent-x"}},  # type: ignore[arg-type]
            {**SANDBOX_DATA, "id": "sbx_other", "labels": {"project": "other"}},  # type: ignore[arg-type]
        ]
    }
    with respx.mock(base_url=BASE) as router:
        router.get("/v1/sandboxes").mock(return_value=httpx.Response(200, json=data))
        sbs = await Sandbox.list(labels={"project": "agent-x"})
        assert len(sbs) == 1
        assert sbs[0].id == "sbx_test123"


@pytest.mark.asyncio
async def test_list_sends_label_query_params() -> None:
    """服务端过滤：labels 非空时，应把每对 (key, value) 拼成 label=key:value
    作为 query 参数发送；同一请求中可出现多个 label= 参数（AND 语义）。"""
    # 模拟服务端已按 label 过滤，只返回匹配结果
    data = {"sandboxes": [{**SANDBOX_DATA, "labels": {"env": "prod", "team": "infra"}}]}  # type: ignore[arg-type]
    with respx.mock(base_url=BASE) as router:
        route = router.get("/v1/sandboxes").mock(return_value=httpx.Response(200, json=data))
        sbs = await Sandbox.list(labels={"env": "prod", "team": "infra"})
        assert len(sbs) == 1
        # 验证请求中确实携带了 label query 参数
        sent_params = route.calls[0].request.url.params.multi_items()
        label_values = [v for k, v in sent_params if k == "label"]
        assert "env:prod" in label_values
        assert "team:infra" in label_values


@pytest.mark.asyncio
async def test_list_no_label_params_when_labels_empty() -> None:
    """labels 为空（None）时，不应附加任何 label query 参数，行为与旧版本一致。"""
    data = {"sandboxes": [SANDBOX_DATA]}
    with respx.mock(base_url=BASE) as router:
        route = router.get("/v1/sandboxes").mock(return_value=httpx.Response(200, json=data))
        await Sandbox.list()
        sent_params = route.calls[0].request.url.params.multi_items()
        label_values = [v for k, v in sent_params if k == "label"]
        assert label_values == []


@pytest.mark.asyncio
async def test_kill_calls_delete() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.delete("/v1/sandboxes/sbx_test123").mock(return_value=httpx.Response(204))
        sb = await Sandbox.create()
        await sb.kill()


@pytest.mark.asyncio
async def test_pause_and_resume() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/pause").mock(return_value=httpx.Response(204))
        router.post("/v1/sandboxes/sbx_test123/resume").mock(return_value=httpx.Response(204))
        sb = await Sandbox.create()
        await sb.pause()
        await sb.resume()


@pytest.mark.asyncio
async def test_context_manager_kills_on_exit() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        kill_route = router.delete("/v1/sandboxes/sbx_test123").mock(
            return_value=httpx.Response(204)
        )
        async with await Sandbox.create() as sb:
            assert sb.id == "sbx_test123"
        assert kill_route.called


@pytest.mark.asyncio
async def test_invalid_network_raises() -> None:
    with pytest.raises(ValueError, match="invalid"):
        await Sandbox.create(network="unknown-policy")


@pytest.mark.asyncio
async def test_sandbox_properties() -> None:
    from datetime import datetime

    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        sb = await Sandbox.create()
        assert sb.image == "node:20-bookworm"
        assert isinstance(sb.created_at, datetime)
        assert sb.labels == {"project": "test"}
        assert sb.network == "allowlist"


@pytest.mark.asyncio
async def test_create_sends_env_and_labels() -> None:
    with respx.mock(base_url=BASE) as router:
        route = router.post("/v1/sandboxes").mock(
            return_value=httpx.Response(201, json=SANDBOX_DATA)
        )
        await Sandbox.create(
            env={"NODE_ENV": "development"},
            labels={"project": "agent-x"},
        )
        payload = json.loads(route.calls[0].request.read())
        assert payload["env"] == {"NODE_ENV": "development"}
        assert payload["labels"] == {"project": "agent-x"}


# ─── HTTP client lifecycle (C2 regression) ─────────────────────────────────


@pytest.mark.asyncio
async def test_kill_closes_owned_client() -> None:
    """kill() must close the underlying httpx pool when Sandbox owns it."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.delete("/v1/sandboxes/sbx_test123").mock(return_value=httpx.Response(204))
        sb = await Sandbox.create()
        client = sb._client
        assert sb._owns_client is True
        await sb.kill()
        assert sb._owns_client is False
        # httpx.AsyncClient.is_closed reports the pool state
        assert client._http.is_closed is True


@pytest.mark.asyncio
async def test_kill_preserves_passed_client() -> None:
    """When the caller passed a client, kill() must NOT close it."""
    from talon_sandbox import Client

    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.delete("/v1/sandboxes/sbx_test123").mock(return_value=httpx.Response(204))
        my_client = Client(server=BASE, api_key="ask_x")
        try:
            sb = await Sandbox.create(client=my_client)
            assert sb._owns_client is False
            await sb.kill()
            # Caller's client still usable
            assert my_client._http.is_closed is False
        finally:
            await my_client.aclose()


@pytest.mark.asyncio
async def test_aexit_closes_owned_client() -> None:
    """async with Sandbox.create(): block must close on exit."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.delete("/v1/sandboxes/sbx_test123").mock(return_value=httpx.Response(204))
        async with await Sandbox.create() as sb:
            client = sb._client
        assert client._http.is_closed is True


@pytest.mark.asyncio
async def test_kill_idempotent_on_404() -> None:
    """kill() on an already-destroyed sandbox should not raise."""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.delete("/v1/sandboxes/sbx_test123").mock(return_value=httpx.Response(404, text=""))
        sb = await Sandbox.create()
        client = sb._client
        await sb.kill()  # must not raise
        assert client._http.is_closed is True
