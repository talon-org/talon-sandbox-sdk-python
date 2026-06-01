"""Tests for list_images()（GET /v1/images）。"""
from __future__ import annotations

import httpx
import pytest
import respx

from talon_sandbox import Sandbox, list_images

BASE = "https://api.sandbox.talon.net.cn"

IMAGE_LIST_RESP = {
    "images": [
        {
            "id": "img_abc",
            "name": "node:20-bookworm",
            "url": "registry.example.com/node:20-bookworm",
            "sha256": "abc123",
            "os": "linux",
            "arch": "amd64",
            "source": "builtin",
            "is_default": True,
            "description": "Node.js 20 on Debian Bookworm",
            "created_at": 1716556800,
        },
        {
            "id": "img_def",
            "name": "python:3.12-slim",
            "url": "registry.example.com/python:3.12-slim",
            "sha256": "def456",
            "os": "linux",
            "arch": "amd64",
            "source": "admin",
            "is_default": False,
            "description": "",
            "created_at": 1716556900,
        },
    ]
}


@pytest.mark.asyncio
async def test_list_images_returns_list() -> None:
    """Sandbox.list_images() 应返回 ImageDTO 列表。"""
    with respx.mock(base_url=BASE) as router:
        router.get("/v1/images").mock(return_value=httpx.Response(200, json=IMAGE_LIST_RESP))
        images = await Sandbox.list_images()
        assert len(images) == 2
        assert images[0]["id"] == "img_abc"
        assert images[0]["is_default"] is True
        assert images[1]["source"] == "admin"


@pytest.mark.asyncio
async def test_list_images_via_toplevel_function() -> None:
    """顶层 list_images() 函数应与 Sandbox.list_images() 等价。"""
    with respx.mock(base_url=BASE) as router:
        router.get("/v1/images").mock(return_value=httpx.Response(200, json=IMAGE_LIST_RESP))
        images = await list_images()
        assert len(images) == 2
        assert images[0]["name"] == "node:20-bookworm"


@pytest.mark.asyncio
async def test_list_images_empty() -> None:
    """无镜像时应返回空列表而非报错。"""
    with respx.mock(base_url=BASE) as router:
        router.get("/v1/images").mock(return_value=httpx.Response(200, json={"images": []}))
        images = await Sandbox.list_images()
        assert images == []


@pytest.mark.asyncio
async def test_list_images_fields_present() -> None:
    """ImageDTO 的所有必要字段都应存在。"""
    with respx.mock(base_url=BASE) as router:
        router.get("/v1/images").mock(return_value=httpx.Response(200, json=IMAGE_LIST_RESP))
        images = await Sandbox.list_images()
        img = images[0]
        for field in ("id", "name", "url", "sha256", "os", "arch", "source", "is_default", "created_at"):
            assert field in img, f"字段 {field!r} 不在 ImageDTO 中"
