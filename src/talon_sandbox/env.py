"""Environment variable sub-object for talon-sandbox SDK."""
from __future__ import annotations

from ._client import Client


class Env:
    """Manage environment variables inside a running sandbox.

    Access via ``sb.env``.
    """

    def __init__(self, sandbox_id: str, client: Client) -> None:
        self._sandbox_id = sandbox_id
        self._client = client

    def _base(self) -> str:
        return f"/v1/sandboxes/{self._sandbox_id}/env"

    async def get(self, key: str) -> str | None:
        """Return the value of an environment variable, or None."""
        all_env = await self.all()
        return all_env.get(key)

    async def all(self) -> dict[str, str]:
        """Return all environment variables as a dict."""
        resp = await self._client.get(self._base())
        result: dict[str, str] = resp.json().get("env", {})
        return result

    async def set(self, key: str, value: str) -> None:
        """Set an environment variable (affects subsequent processes)."""
        await self._client.put(self._base(), json={"key": key, "value": value})

    async def unset(self, key: str) -> None:
        """Remove an environment variable."""
        await self._client.delete(f"{self._base()}/{key}")
