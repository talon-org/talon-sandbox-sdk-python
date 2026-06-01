"""Tests for sb.agent_run()（Spec 38 高层 agent 入口）。"""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

BASE = "https://api.sandbox.talon.net.cn"

# 模拟后端 AgentRunResponse
AGENT_RUN_RESP = {
    "run_id": "run_abc123",
    "status": "completed",
    "duration_ms": 4200,
    "steps": [
        {
            "step": 1,
            "action": "Page.navigate",
            "thought": "导航到目标页面",
            "details": {"url": "https://example.com"},
        }
    ],
    "result": "任务完成",
    "exit_code": 0,
    "stderr": "",
}


@pytest.mark.asyncio
async def test_agent_run_returns_response_dict() -> None:
    """agent_run() 应返回包含 run_id/status 的字典。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/agent/run").mock(
            return_value=httpx.Response(200, json=AGENT_RUN_RESP)
        )
        sb = await Sandbox.create()
        resp = await sb.agent_run("搜索 Python 最新版本")
        assert resp["run_id"] == "run_abc123"
        assert resp["status"] == "completed"
        assert resp["exit_code"] == 0


@pytest.mark.asyncio
async def test_agent_run_sends_goal_in_body() -> None:
    """agent_run(goal=...) 应将 goal 写入请求体。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        agent_route = router.post("/v1/sandboxes/sbx_test123/agent/run").mock(
            return_value=httpx.Response(200, json=AGENT_RUN_RESP)
        )
        sb = await Sandbox.create()
        await sb.agent_run("测试目标")
        payload = json.loads(agent_route.calls[0].request.read())
        assert payload["goal"] == "测试目标"
        assert "max_steps" not in payload
        assert "llm_model" not in payload


@pytest.mark.asyncio
async def test_agent_run_sends_optional_fields() -> None:
    """agent_run(max_steps=50, llm_model=...) 应将可选字段写入请求体。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        agent_route = router.post("/v1/sandboxes/sbx_test123/agent/run").mock(
            return_value=httpx.Response(200, json=AGENT_RUN_RESP)
        )
        sb = await Sandbox.create()
        await sb.agent_run(
            "自动化测试任务",
            max_steps=50,
            llm_model="anthropic:claude-sonnet-4-6",
        )
        payload = json.loads(agent_route.calls[0].request.read())
        assert payload["goal"] == "自动化测试任务"
        assert payload["max_steps"] == 50
        assert payload["llm_model"] == "anthropic:claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_agent_run_returns_steps_list() -> None:
    """agent_run() 响应中应含 steps 列表。"""
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.post("/v1/sandboxes/sbx_test123/agent/run").mock(
            return_value=httpx.Response(200, json=AGENT_RUN_RESP)
        )
        sb = await Sandbox.create()
        resp = await sb.agent_run("任意目标")
        assert isinstance(resp["steps"], list)
        assert len(resp["steps"]) == 1
        assert resp["steps"][0]["action"] == "Page.navigate"
