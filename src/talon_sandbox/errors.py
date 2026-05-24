"""Exception hierarchy for talon-sandbox SDK."""
from __future__ import annotations

import json


class SandboxError(Exception):
    """Base class for all talon-sandbox SDK errors."""

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id

    def __repr__(self) -> str:
        cls = type(self).__name__
        return f"{cls}({self.args[0]!r}, request_id={self.request_id!r})"


class AuthError(SandboxError):
    """401 / 403 — authentication or authorization failure."""


class NotFoundError(SandboxError):
    """404 — sandbox, process, or file not found."""


class QuotaError(SandboxError):
    """422 — tenant quota exceeded."""


class RateLimitError(SandboxError):
    """429 — too many requests."""


class TimeoutError(SandboxError):
    """Request or wait-state timeout."""


class NetworkError(SandboxError):
    """Connection-level failure (DNS, TCP, TLS)."""


class ServerError(SandboxError):
    """5xx — server-side failure."""


class ConflictError(SandboxError):
    """409 — resource conflict (e.g. duplicate subdomain)."""


def _extract_message(body: str) -> str:
    try:
        data = json.loads(body)
        return str(data.get("error", body))
    except Exception:
        return body


def _raise_for_status(
    status_code: int, body: str, *, request_id: str | None
) -> None:
    """Raise the appropriate SandboxError subclass for an HTTP error."""
    msg = _extract_message(body)
    if status_code in (401, 403):
        raise AuthError(msg, request_id=request_id)
    if status_code == 404:
        raise NotFoundError(msg, request_id=request_id)
    if status_code == 409:
        raise ConflictError(msg, request_id=request_id)
    if status_code == 422:
        raise QuotaError(msg, request_id=request_id)
    if status_code == 429:
        raise RateLimitError(msg, request_id=request_id)
    if status_code >= 500:
        raise ServerError(msg, request_id=request_id)
    raise SandboxError(msg, request_id=request_id)
