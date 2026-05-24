"""Tests for sb.fs.*"""
from __future__ import annotations

import httpx
import pytest
import respx

from talon_sandbox import Sandbox
from tests.conftest import SANDBOX_DATA

BASE = "http://localhost:18080"

FS_LIST_RESP = {
    "entries": [
        {"name": "main.py", "size": 123, "mod_time": 1716556800, "is_dir": False},
        {"name": "src", "size": 0, "mod_time": 1716556800, "is_dir": True},
    ],
    "total": 2,
}


@pytest.mark.asyncio
async def test_fs_read() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/fs/workspace/main.py").mock(
            return_value=httpx.Response(200, content=b"print('hi')")
        )
        sb = await Sandbox.create()
        data = await sb.fs.read("/workspace/main.py")
        assert data == b"print('hi')"


@pytest.mark.asyncio
async def test_fs_read_text() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/fs/workspace/main.py").mock(
            return_value=httpx.Response(200, content=b"print('hi')")
        )
        sb = await Sandbox.create()
        text = await sb.fs.read_text("/workspace/main.py")
        assert text == "print('hi')"


@pytest.mark.asyncio
async def test_fs_write() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        write_route = router.put("/v1/sandboxes/sbx_test123/fs/workspace/x").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.fs.write("/workspace/x", b"hello")
        assert write_route.called


@pytest.mark.asyncio
async def test_fs_write_text() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        write_route = router.put("/v1/sandboxes/sbx_test123/fs/workspace/x").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.fs.write_text("/workspace/x", "hello")
        assert write_route.called
        # Verify bytes were sent
        assert write_route.calls[0].request.content == b"hello"


@pytest.mark.asyncio
async def test_fs_list() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/fs-list/workspace").mock(
            return_value=httpx.Response(200, json=FS_LIST_RESP)
        )
        sb = await Sandbox.create()
        entries = await sb.fs.list("/workspace")
        assert len(entries) == 2
        assert entries[0].name == "main.py"
        assert entries[0].type == "file"
        assert entries[1].type == "dir"


@pytest.mark.asyncio
async def test_fs_remove() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        del_route = router.delete("/v1/sandboxes/sbx_test123/fs/workspace/old").mock(
            return_value=httpx.Response(204)
        )
        sb = await Sandbox.create()
        await sb.fs.remove("/workspace/old")
        assert del_route.called


@pytest.mark.asyncio
async def test_fs_stat() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/fs-list/workspace").mock(
            return_value=httpx.Response(200, json=FS_LIST_RESP)
        )
        sb = await Sandbox.create()
        info = await sb.fs.stat("/workspace/main.py")
        assert info.size == 123
        assert info.is_dir is False


@pytest.mark.asyncio
async def test_fs_exists_true() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/fs-list/workspace").mock(
            return_value=httpx.Response(200, json=FS_LIST_RESP)
        )
        sb = await Sandbox.create()
        assert await sb.fs.exists("/workspace/main.py") is True


@pytest.mark.asyncio
async def test_fs_exists_false() -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/v1/sandboxes").mock(return_value=httpx.Response(201, json=SANDBOX_DATA))
        router.get("/v1/sandboxes/sbx_test123/fs-list/workspace").mock(
            return_value=httpx.Response(200, json=FS_LIST_RESP)
        )
        sb = await Sandbox.create()
        assert await sb.fs.exists("/workspace/nonexistent.py") is False
