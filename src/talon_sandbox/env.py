"""Environment variable sub-object for talon-sandbox SDK."""
from __future__ import annotations

from urllib.parse import quote

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

    def _key_url(self, key: str) -> str:
        return f"{self._base()}/{quote(key, safe='')}"

    async def get(self, key: str) -> str | None:
        """Return the value of an environment variable, or None if not set.

        Fetches all env vars and returns the value for *key*, or ``None`` when
        the key is absent.  The backend returns an empty string for keys that
        exist but have no value; ``None`` is reserved for keys that are not set
        at all, preserving the expected ``Optional[str]`` contract.
        """
        all_env = await self.all()
        return all_env.get(key)

    async def all(self) -> dict[str, str]:
        """Return all environment variables as a ``{key: value}`` dict."""
        resp = await self._client.get(self._base())
        result: dict[str, str] = resp.json().get("env", {})
        return result

    async def set(self, key: str, value: str) -> None:
        """Set a persistent environment variable for the sandbox.

        Sends ``PUT /v1/sandboxes/{id}/env/{key}`` with body ``{"value": ...}``.

        Note: this updates the persisted value only.  Already-running processes
        will not see the new value; the change takes effect the next time a
        process is started inside the sandbox.
        """
        await self._client.put(self._key_url(key), json={"value": value})

    async def unset(self, key: str) -> None:
        """Remove an environment variable from the sandbox.

        Sends ``DELETE /v1/sandboxes/{id}/env/{key}``.  Already-running
        processes are not affected; the variable is absent for subsequent
        processes.
        """
        await self._client.delete(self._key_url(key))
