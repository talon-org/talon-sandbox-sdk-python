"""Internal async HTTP client for talon-sandbox SDK."""
from __future__ import annotations

from typing import Any

import httpx

from ._config import resolve_api_key, resolve_server
from .errors import NetworkError, _raise_for_status

_REQUEST_ID_HEADER = "X-Request-ID"


class Client:
    """Async HTTP client for the Talon Sandbox API.

    Can be passed explicitly to ``Sandbox.create(..., client=client)``
    to override global config.

    Example::

        from talon_sandbox import Client
        client = Client(server="https://api.example.com", api_key="ask_...")
    """

    def __init__(
        self,
        *,
        server: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = resolve_server(server)
        self._api_key = resolve_api_key(api_key)
        self._timeout = timeout
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def _ws_url(self, path: str) -> str:
        url = self._base_url
        url = url.replace("https://", "wss://", 1)
        url = url.replace("http://", "ws://", 1)
        return f"{url}{path}"

    def _auth_header_value(self) -> str | None:
        h = self._auth_headers()
        return h.get("Authorization")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int | tuple[int, ...] = 200,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
        try:
            resp = await self._http.request(method, path, headers=headers, **kwargs)
        except httpx.ConnectError as e:
            raise NetworkError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            from .errors import TimeoutError as SdkTimeoutError

            raise SdkTimeoutError(f"Request timed out: {e}") from e

        request_id = resp.headers.get(_REQUEST_ID_HEADER)

        if isinstance(expected_status, int):
            ok = resp.status_code == expected_status
        else:
            ok = resp.status_code in expected_status

        if not ok:
            _raise_for_status(resp.status_code, resp.text, request_id=request_id)

        return resp

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", path, expected_status=(200, 204), **kwargs)

    async def post(
        self,
        path: str,
        *,
        expected_status: int | tuple[int, ...] = (200, 201, 204),
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._request("POST", path, expected_status=expected_status, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("PUT", path, expected_status=(200, 204), **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("DELETE", path, expected_status=(200, 204), **kwargs)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
