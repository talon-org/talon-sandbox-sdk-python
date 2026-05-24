"""Browser sub-object for talon-sandbox SDK."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._client import Client


@dataclass
class BrowserSession:
    """An active headless browser session."""

    cdp_url: str
    process_id: str
    sandbox_id: str


class Browser:
    """Control a headless Chromium browser inside the sandbox.

    Access via ``sb.browser``. The browser is started on demand;
    connect to it via the CDP URL using playwright or puppeteer.

    Example::

        browser = await sb.browser.start()
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            chrome = await p.chromium.connect_over_cdp(browser.cdp_url)
    """

    def __init__(self, sandbox_id: str, client: Client) -> None:
        self._sandbox_id = sandbox_id
        self._client = client

    def _base(self) -> str:
        return f"/v1/sandboxes/{self._sandbox_id}/browser"

    async def start(self) -> BrowserSession:
        """Launch a headless Chromium and return the session with CDP URL."""
        resp = await self._client.post(self._base())
        data: dict[str, Any] = resp.json()
        return BrowserSession(
            cdp_url=str(data.get("cdp_ws_url", "")),
            process_id=str(data.get("process_id", "")),
            sandbox_id=self._sandbox_id,
        )

    async def get(self) -> BrowserSession:
        """Get the current browser session."""
        resp = await self._client.get(self._base())
        data: dict[str, Any] = resp.json()
        return BrowserSession(
            cdp_url=str(data.get("cdp_ws_url", "")),
            process_id=str(data.get("process_id", "")),
            sandbox_id=self._sandbox_id,
        )

    async def stop(self) -> None:
        """Stop the browser session."""
        await self._client.delete(self._base())
