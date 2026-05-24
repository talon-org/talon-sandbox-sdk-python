"""Filesystem sub-object for talon-sandbox SDK."""
from __future__ import annotations

import posixpath
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

from ._client import Client
from .errors import NotFoundError


@dataclass
class FsEntry:
    """A single directory entry."""

    name: str
    type: str  # "file" | "dir"
    size: int
    modified: datetime


@dataclass
class FsInfo:
    """File or directory metadata."""

    size: int
    modified: datetime
    is_dir: bool
    mode: int = 0o644


class Fs:
    """Filesystem operations inside a sandbox.

    Access via ``sb.fs``. Methods use absolute paths inside the sandbox.
    """

    def __init__(self, sandbox_id: str, client: Client) -> None:
        self._sandbox_id = sandbox_id
        self._client = client

    def _path(self, path: str) -> str:
        return f"/v1/sandboxes/{self._sandbox_id}/fs/{path.lstrip('/')}"

    def _list_path(self, path: str) -> str:
        return f"/v1/sandboxes/{self._sandbox_id}/fs-list/{path.lstrip('/')}"

    async def read(self, path: str) -> bytes:
        """Read file contents as bytes."""
        resp = await self._client.get(self._path(path))
        return bytes(resp.content)

    async def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read file contents as text."""
        data = await self.read(path)
        return data.decode(encoding)

    async def write(self, path: str, data: bytes) -> None:
        """Write bytes to a file (creates intermediate directories)."""
        await self._client.put(
            self._path(path),
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )

    async def write_text(self, path: str, text: str, encoding: str = "utf-8") -> None:
        """Write text to a file."""
        await self.write(path, text.encode(encoding))

    async def list(self, path: str) -> list[FsEntry]:
        """List directory contents."""
        resp = await self._client.get(self._list_path(path))
        data = resp.json()
        entries = []
        for e in data.get("entries", []):
            entries.append(
                FsEntry(
                    name=str(e["name"]),
                    type="dir" if e.get("is_dir") else "file",
                    size=int(e.get("size", 0)),
                    modified=datetime.fromtimestamp(
                        float(e.get("mod_time", 0)), tz=timezone.utc
                    ),
                )
            )
        return entries

    async def remove(self, path: str) -> None:
        """Remove a file or directory."""
        await self._client.delete(self._path(path))

    async def stat(self, path: str) -> FsInfo:
        """Get file metadata."""
        parent = posixpath.dirname(path) or "/"
        name = posixpath.basename(path)
        resp = await self._client.get(self._list_path(parent))
        data = resp.json()
        for e in data.get("entries", []):
            if e["name"] == name:
                return FsInfo(
                    size=int(e.get("size", 0)),
                    modified=datetime.fromtimestamp(
                        float(e.get("mod_time", 0)), tz=timezone.utc
                    ),
                    is_dir=bool(e.get("is_dir")),
                )
        raise NotFoundError(f"Path not found: {path}")

    async def exists(self, path: str) -> bool:
        """Return True if the path exists."""
        try:
            await self.stat(path)
            return True
        except Exception:
            return False

    async def read_stream(self, path: str, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        """Stream file contents in chunks (for large files)."""
        async with self._client._http.stream(
            "GET", self._path(path), headers=self._client._auth_headers()
        ) as resp:
            async for chunk in resp.aiter_bytes(chunk_size):
                yield chunk
