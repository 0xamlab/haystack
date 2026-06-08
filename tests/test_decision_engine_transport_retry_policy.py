from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

exceptions = importlib.import_module("decision_engine.exceptions")
retry_policy = importlib.import_module("decision_engine.transport_retry_policy")
transport_response = importlib.import_module("decision_engine.transport_response")
sync_transport = importlib.import_module("decision_engine.client_transport")
async_transport = importlib.import_module("decision_engine.async_client_transport")


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        headers: dict[str, str] | None = None,
        body: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._body = {} if body is None else body

    def json(self) -> object:
        return self._body


def test_handle_response_preserves_success_array_payloads() -> None:
    response = _FakeResponse(
        status_code=200,
        body=[{"id": "key_1", "key_prefix": "de_live_abcd"}],
    )

    result = transport_response.handle_response(response, auth_message="Auth failed")

    assert result == [{"id": "key_1", "key_prefix": "de_live_abcd"}]


def test_parse_retry_after_header_supports_seconds() -> None:
    assert retry_policy.parse_retry_after_header("45") == 45


def test_parse_retry_after_header_supports_http_date(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    retry_at = datetime(2026, 5, 18, 12, 0, 17, tzinfo=UTC)
    monkeypatch.setattr(retry_policy, "utc_now", lambda: now)

    assert retry_policy.parse_retry_after_header(format_datetime(retry_at)) == 17


def test_parse_retry_after_header_defaults_on_invalid_values() -> None:
    assert retry_policy.parse_retry_after_header("not-a-delay") == 60
    assert retry_policy.parse_retry_after_header("") == 60
    assert retry_policy.parse_retry_after_header(None) == 60


def test_parse_retry_after_header_returns_zero_for_expired_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    retry_at = datetime(2026, 5, 18, 11, 59, 50, tzinfo=UTC)
    monkeypatch.setattr(retry_policy, "utc_now", lambda: now)

    assert retry_policy.parse_retry_after_header(format_datetime(retry_at)) == 0


def test_handle_response_429_uses_robust_retry_after_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    retry_at = datetime(2026, 5, 18, 12, 0, 9, tzinfo=UTC)
    monkeypatch.setattr(retry_policy, "utc_now", lambda: now)

    response = _FakeResponse(
        status_code=429,
        headers={"Retry-After": format_datetime(retry_at)},
        body={"error": {"message": "Slow down", "code": "rate_limited"}},
    )

    with pytest.raises(exceptions.RateLimitError, match="Slow down") as exc_info:
        transport_response.handle_response(response, auth_message="Auth failed")

    assert exc_info.value.retry_after == 9
    assert exc_info.value.error_code == "rate_limited"


def test_handle_response_429_defaults_when_retry_after_is_invalid() -> None:
    response = _FakeResponse(
        status_code=429,
        headers={"Retry-After": "tomorrow-ish"},
        body={"error": {"message": "Slow down", "code": "rate_limited"}},
    )

    with pytest.raises(exceptions.RateLimitError) as exc_info:
        transport_response.handle_response(response, auth_message="Auth failed")

    assert exc_info.value.retry_after == 60


def test_sync_transport_uses_fallback_backoff_for_zero_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    responses = iter(
        [
            exceptions.RateLimitError("Slow down", retry_after=0, status_code=429),
            {"ok": True},
        ]
    )

    def _request(method: str, path: str, **kwargs):
        outcome = next(responses)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client = SimpleNamespace(
        _max_retries=1,
        _client=SimpleNamespace(request=_request),
        _handle_response=lambda response: response,
        _get_httpx_module=lambda: SimpleNamespace(HTTPError=RuntimeError),
    )
    monkeypatch.setattr(sync_transport.time, "sleep", sleep_calls.append)

    result = sync_transport.request_with_retries(client, "GET", "/v1/query")

    assert result == {"ok": True}
    assert sleep_calls == [5.0]


def test_sync_transport_does_not_retry_inline_preview_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    error = exceptions.RateLimitError(
        "Slow down",
        retry_after=60,
        status_code=429,
        response_body={"error": {"code": "inline_preview_rate_limited"}},
    )
    client = SimpleNamespace(
        _max_retries=3,
        _client=SimpleNamespace(request=lambda *args, **kwargs: (_ for _ in ()).throw(error)),
        _handle_response=lambda response: response,
        _get_httpx_module=lambda: SimpleNamespace(HTTPError=RuntimeError),
    )
    monkeypatch.setattr(sync_transport.time, "sleep", sleep_calls.append)

    with pytest.raises(exceptions.RateLimitError) as exc_info:
        sync_transport.request_with_retries(client, "GET", "/v1/query")

    assert exc_info.value.error_code == "inline_preview_rate_limited"
    assert sleep_calls == []


@pytest.mark.anyio
async def test_async_transport_uses_server_backoff_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    responses = iter(
        [
            exceptions.ServerError("try again", status_code=503),
            {"ok": True},
        ]
    )

    async def _request(method: str, path: str, **kwargs):
        outcome = next(responses)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client = SimpleNamespace(
        _max_retries=1,
        _client=SimpleNamespace(request=_request),
        _handle_response=lambda response: response,
        _get_httpx_module=lambda: SimpleNamespace(HTTPError=RuntimeError),
    )

    async def _sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _sleep)

    result = await async_transport.request_with_retries(client, "GET", "/v1/query")

    assert result == {"ok": True}
    assert sleep_calls == [1.0]
