import pytest
from talon_sandbox.errors import (
    SandboxError,
    AuthError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    NetworkError,
    ServerError,
    ConflictError,
    _raise_for_status,
)


def test_base_has_request_id() -> None:
    e = SandboxError("oops", request_id="req_123")
    assert e.request_id == "req_123"
    assert str(e) == "oops"


def test_auth_error_401() -> None:
    with pytest.raises(AuthError) as exc_info:
        _raise_for_status(401, '{"error":"unauthorized"}', request_id="r1")
    assert exc_info.value.request_id == "r1"


def test_not_found_404() -> None:
    with pytest.raises(NotFoundError):
        _raise_for_status(404, '{"error":"not found"}', request_id=None)


def test_quota_422() -> None:
    with pytest.raises(QuotaError):
        _raise_for_status(422, '{"error":"quota"}', request_id=None)


def test_rate_limit_429() -> None:
    with pytest.raises(RateLimitError):
        _raise_for_status(429, '{"error":"too many"}', request_id=None)


def test_server_error_500() -> None:
    with pytest.raises(ServerError):
        _raise_for_status(500, "internal error", request_id=None)


def test_conflict_409() -> None:
    with pytest.raises(ConflictError):
        _raise_for_status(409, '{"error":"conflict"}', request_id=None)


def test_fallback_raw_body() -> None:
    with pytest.raises(SandboxError) as exc_info:
        _raise_for_status(418, "i am a teapot", request_id=None)
    assert "teapot" in str(exc_info.value)


def test_auth_error_403() -> None:
    with pytest.raises(AuthError):
        _raise_for_status(403, '{"error":"forbidden"}', request_id=None)
