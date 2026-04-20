from __future__ import annotations

import httpx
import pytest

from apps.mcp_server import client as mcp_client
from apps.mcp_server.errors import (
    MCPUpstreamUnavailableError,
    UnsupportedMCPAuthConfigurationError,
    serialize_tool_error,
)


def test_request_overrides_supply_api_key_and_base_url(monkeypatch):
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with pytest.raises(UnsupportedMCPAuthConfigurationError, match="API key"):
        mcp_client._headers()

    with mcp_client.request_overrides(
        api_key="de_test_override",
        base_url="http://127.0.0.1:8000",
    ):
        headers = mcp_client._headers()
        assert headers["Authorization"] == "Bearer de_test_override"
        assert mcp_client._resolve_base_url() == "http://127.0.0.1:8000"


def test_request_overrides_do_not_leak_state(monkeypatch):
    monkeypatch.setenv("ALGENTA_API_KEY", "de_test_env")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://env.local")

    with mcp_client.request_overrides(
        api_key="de_test_override",
        base_url="http://override.local",
    ):
        assert mcp_client._headers()["Authorization"] == "Bearer de_test_override"
        assert mcp_client._resolve_base_url() == "http://override.local"

    assert mcp_client._headers()["Authorization"] == "Bearer de_test_env"
    assert mcp_client._resolve_base_url() == "http://env.local"


@pytest.mark.asyncio
async def test_api_maps_transport_error_to_upstream_unavailable() -> None:
    class _BrokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, **kwargs):
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("boom", request=request)

    original = mcp_client.httpx.AsyncClient
    mcp_client.httpx.AsyncClient = _BrokenClient  # type: ignore[assignment]
    try:
        with mcp_client.request_overrides(
            api_key="de_test_override",
            base_url="http://127.0.0.1:8000",
        ):
            with pytest.raises(MCPUpstreamUnavailableError, match="unavailable"):
                await mcp_client.api("GET", "/v1/health")
    finally:
        mcp_client.httpx.AsyncClient = original  # type: ignore[assignment]


def test_serialize_tool_error_returns_contract_payloads() -> None:
    auth_error = UnsupportedMCPAuthConfigurationError("missing auth")
    upstream_error = MCPUpstreamUnavailableError("temporary outage")

    assert "unsupported_mcp_auth_configuration" in serialize_tool_error(auth_error, tool_name="simulate")
    assert "mcp_upstream_unavailable" in serialize_tool_error(upstream_error, tool_name="simulate")
    assert "unknown_tool" in serialize_tool_error(KeyError("nope"), tool_name="nope")
