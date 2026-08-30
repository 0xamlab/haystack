"""Track C2 (real streaming): egress_guard.async_http_stream.

Mirrors test_llm_provider_egress.py's coverage of async_http_request, for the new streaming
counterpart: the SAME enforce_egress() gate must fire BEFORE any socket opens on the streaming
path too -- a request to a private/SSRF-guarded destination must be blocked even though the call
now goes through client.stream(...) instead of client.post(...)."""

from __future__ import annotations

import pytest

from apps.api_server.config import get_settings
from apps.api_server.services import egress_guard
from apps.api_server.services.egress_guard import EgressPolicyDeniedError


class _RaisingAsyncClient:
    """Constructing this fails the test -- proves no socket was opened past a policy deny."""

    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("httpx.AsyncClient must not be constructed when egress is denied")


class _FakeStreamResponse:
    status_code = 200

    async def aiter_lines(self):
        for line in ('data: {"ok": true}', ""):
            yield line

    async def aread(self) -> bytes:
        return b"{}"


class _FakeStreamCtx:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *exc) -> bool:
        return False


class _FakeAsyncClient:
    def __init__(self, **kwargs) -> None:
        del kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def stream(self, method: str, url: str, **kwargs):
        del method, url, kwargs
        return _FakeStreamCtx(_FakeStreamResponse())


@pytest.mark.anyio
async def test_async_http_stream_deny_raises_before_any_socket(monkeypatch):
    """A request to a private/unallowlisted destination must be blocked on the STREAMING path
    exactly as it is on the buffered async_http_request path -- constructing httpx.AsyncClient at
    all is proof a socket would have opened past the deny, so it fails the test if reached."""
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()
    monkeypatch.setattr(egress_guard.httpx, "AsyncClient", _RaisingAsyncClient)
    try:
        with pytest.raises(EgressPolicyDeniedError):
            async with egress_guard.async_http_stream(
                method="POST",
                url="https://api.unallowlisted-public.example/v1/chat/completions",
                surface="llm_provider_post_stream",
                egress_class="customer_connector",
                explicit_configured=True,
                json={"x": 1},
            ) as response:
                # Never reached: enforce_egress must raise before __aenter__ yields anything.
                await response.aread()
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_async_http_stream_blocks_private_destination_under_permissive_outbound(
    monkeypatch,
):
    """Same SSRF guard as the buffered path: an explicit allowlist entry that a private/loopback
    IP resolves behind must still be denied on the streaming call."""
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "true")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()
    monkeypatch.setattr(egress_guard.httpx, "AsyncClient", _RaisingAsyncClient)
    try:
        with pytest.raises(EgressPolicyDeniedError) as exc_info:
            async with egress_guard.async_http_stream(
                method="POST",
                url="http://127.0.0.1:11434/api/chat",
                surface="llm_provider_post_stream",
                egress_class="customer_connector",
                explicit_configured=True,
            ):
                raise AssertionError("stream body should never be reached when SSRF guard denies")
        assert exc_info.value.decision.reason.startswith("ssrf_guard")
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_async_http_stream_allows_and_streams_when_allowlisted(monkeypatch):
    """The happy path: an allowlisted destination passes the gate and the caller can iterate the
    (fake) streamed body without the response ever being fully buffered up front."""
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "*.customer.internal")
    get_settings.cache_clear()
    monkeypatch.setattr(egress_guard.httpx, "AsyncClient", _FakeAsyncClient)
    try:
        lines: list[str] = []
        async with egress_guard.async_http_stream(
            method="POST",
            url="https://provider.customer.internal/v1/chat/completions",
            surface="llm_provider_post_stream",
            egress_class="customer_connector",
            explicit_configured=True,
            json={"x": 1},
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                lines.append(line)
        assert lines == ['data: {"ok": true}', ""]
    finally:
        get_settings.cache_clear()
