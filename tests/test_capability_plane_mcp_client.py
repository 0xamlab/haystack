"""External MCP client: discovery + tool-call proxy + egress fail-closed.

Algenta acts as an MCP *client* to a customer-registered external MCP server. These tests stand up a
fake MCP server over httpx.MockTransport, speaking the Streamable HTTP JSON-RPC protocol, and verify:
  - list_remote_tools performs the initialize handshake and returns the server's tools;
  - call_remote_tool proxies tools/call and returns the result (JSON and SSE response shapes);
  - every call is governed by the egress policy — an un-allowlisted host fails closed BEFORE any HTTP.
"""
from __future__ import annotations

import json

import httpx
import pytest

from apps.api_server.config import get_settings
from apps.api_server.services.capability_plane._mcp_client import (
    MCPClientError,
    build_auth_headers,
    call_remote_tool,
    list_remote_tools,
)
from apps.api_server.services.egress_guard import EgressPolicyDeniedError

SERVER_URL = "https://mcp.customer.internal/mcp"
_REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured before any monkeypatch of httpx.AsyncClient

TOOLS = [
    {
        "name": "echo",
        "description": "Echo the input text.",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
    }
]


def _json_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    method = body.get("method")
    if method == "initialize":
        return httpx.Response(
            200,
            headers={"Mcp-Session-Id": "sess-test-1"},
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake-mcp", "version": "1"},
                },
            },
        )
    if method == "notifications/initialized":
        return httpx.Response(202)
    if method == "tools/list":
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": TOOLS}})
    if method == "tools/call":
        args = body["params"]["arguments"]
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"content": [{"type": "text", "text": args.get("text", "")}], "isError": False},
            },
        )
    return httpx.Response(400, json={"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "method not found"}})


def _sse_handler(request: httpx.Request) -> httpx.Response:
    """Like _json_handler but returns tools/call as a Server-Sent Events frame."""
    body = json.loads(request.content)
    if body.get("method") == "tools/call":
        message = {
            "jsonrpc": "2.0",
            "id": body["id"],
            "result": {"content": [{"type": "text", "text": "via-sse"}], "isError": False},
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=f"event: message\ndata: {json.dumps(message)}\n\n",
        )
    return _json_handler(request)


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _allow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "*.customer.internal")
    get_settings.cache_clear()


def _deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()


def test_build_auth_headers() -> None:
    assert build_auth_headers(None) == {}
    assert build_auth_headers({"type": "bearer", "token": "t"}) == {"Authorization": "Bearer t"}
    assert build_auth_headers({"type": "api_key", "token": "k"}) == {"X-API-Key": "k"}
    assert build_auth_headers({"type": "api_key", "token": "k", "header": "X-My-Key"}) == {"X-My-Key": "k"}
    # secrets-free custom headers pass through
    assert build_auth_headers({"type": "none", "headers": {"X-Trace": "1"}}) == {"X-Trace": "1"}


@pytest.mark.anyio
async def test_list_remote_tools_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    try:
        async with _mock_client(_json_handler) as client:
            tools = await list_remote_tools(SERVER_URL, client=client)
        assert [t["name"] for t in tools] == ["echo"]
        assert tools[0]["inputSchema"]["properties"]["text"]["type"] == "string"
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_call_remote_tool_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    try:
        async with _mock_client(_json_handler) as client:
            result = await call_remote_tool(
                SERVER_URL, tool_name="echo", arguments={"text": "hello"}, client=client
            )
        assert result["isError"] is False
        assert result["content"][0]["text"] == "hello"
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_call_remote_tool_sse_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    try:
        async with _mock_client(_sse_handler) as client:
            result = await call_remote_tool(SERVER_URL, tool_name="echo", arguments={}, client=client)
        assert result["content"][0]["text"] == "via-sse"
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_egress_denied_when_not_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _deny(monkeypatch)
    try:
        async with _mock_client(_json_handler) as client:
            with pytest.raises(EgressPolicyDeniedError):
                await list_remote_tools(SERVER_URL, client=client)
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_tool_error_surfaces_as_mcp_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "tools/call":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32000, "message": "boom"}},
            )
        return _json_handler(request)

    try:
        async with _mock_client(handler) as client:
            with pytest.raises(MCPClientError):
                await call_remote_tool(SERVER_URL, tool_name="echo", arguments={}, client=client)
    finally:
        get_settings.cache_clear()


# --- Integration: discovery + execution wiring through the HTTP API (external server mocked) ---

import uuid  # noqa: E402
from uuid import uuid4  # noqa: E402

from apps.api_server.db.session import AsyncSessionLocal  # noqa: E402
from apps.api_server.main import app  # noqa: E402
from apps.api_server.middleware.auth import get_current_org  # noqa: E402
from apps.api_server.models import Organization, OrgPlan, OrgStatus  # noqa: E402


async def _seed_org() -> str:
    async with AsyncSessionLocal() as session:
        org = Organization(
            name="MCP Provider Test Org",
            slug=f"mcp-provider-{uuid4().hex[:12]}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.commit()
        return str(org.id)


def _fake_auth_for(org_id: str):
    async def _auth() -> dict[str, str]:
        return {"org_id": org_id, "user_id": f"user-{uuid4().hex[:8]}", "key_id": f"key-{uuid4().hex[:8]}", "plan": "pro"}
    return _auth


@pytest.mark.anyio
async def test_mcp_provider_preview_discovery(client, monkeypatch: pytest.MonkeyPatch) -> None:
    org_id = await _seed_org()
    _allow(monkeypatch)
    # The egress wrapper builds the outbound client; inject a MockTransport in its place.
    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.httpx.AsyncClient",
        lambda **_kw: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(_json_handler)),
    )
    app.dependency_overrides[get_current_org] = _fake_auth_for(org_id)
    try:
        resp = await client.post(
            "/v1/capability-bindings/discover",
            json={
                "provider_id": "provider.mcp.generic",
                "profile_id": "profile.mcp.workspace",
                "scope": "workspace",
                "execution_owner": "algenta_managed",
                "config": {"server_url": SERVER_URL},
            },
        )
        assert resp.status_code == 200, resp.text
        assert "echo" in resp.text
        assert "mcp_tool" in resp.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_mcp_provider_create_discover_execute(client, monkeypatch: pytest.MonkeyPatch) -> None:
    org_id = await _seed_org()
    _allow(monkeypatch)
    # The egress wrapper builds the outbound client; inject a MockTransport in its place.
    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.httpx.AsyncClient",
        lambda **_kw: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(_json_handler)),
    )
    app.dependency_overrides[get_current_org] = _fake_auth_for(org_id)
    try:
        create = await client.post(
            "/v1/capability-bindings",
            json={
                "provider_id": "provider.mcp.generic",
                "profile_id": "profile.mcp.workspace",
                "binding_name": "External MCP server",
                "scope": "workspace",
                "execution_owner": "algenta_managed",
                "config": {"server_url": SERVER_URL, "auth": {"type": "bearer", "token": "secret-xyz"}},
            },
        )
        assert create.status_code in (200, 201), create.text
        binding_id = create.json()["binding_id"]

        # The stored auth token must be redacted in binding GET responses.
        got = await client.get(f"/v1/capability-bindings/{binding_id}")
        assert got.status_code == 200, got.text
        assert "secret-xyz" not in got.text

        disc = await client.post(f"/v1/capability-bindings/{binding_id}/discover")
        assert disc.status_code == 200, disc.text
        assert "echo" in disc.text

        caps = await client.get("/v1/capabilities")
        assert caps.status_code == 200, caps.text
        payload = caps.json()
        entries = payload if isinstance(payload, list) else payload.get("capabilities", payload.get("data", []))
        mcp_caps = [c for c in entries if c.get("kind") == "mcp_tool"]
        assert mcp_caps, f"no mcp_tool capabilities in {entries}"
        cap_id = mcp_caps[0]["capability_id"]

        exe = await client.post(
            "/v1/capabilities/execute",
            json={"capability_id": cap_id, "input": {"arguments": {"text": "round-trip"}}},
        )
        assert exe.status_code == 200, exe.text
        assert "round-trip" in exe.text  # the proxied tool echoed our argument back
        # The encrypted auth token must never surface in any catalog/execute response.
        assert "secret-xyz" not in caps.text
        assert "secret-xyz" not in disc.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_blocked_link_local_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if egress would allow it, the feature-scoped guard blocks link-local/metadata addresses.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "true")
    get_settings.cache_clear()
    try:
        async with _mock_client(_json_handler) as client:
            with pytest.raises(MCPClientError) as exc:
                await list_remote_tools("https://169.254.169.254/mcp", client=client)
        assert exc.value.code == "mcp_blocked_destination"
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_initialize_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32000, "message": "no"}}
            )
        return _json_handler(request)

    try:
        async with _mock_client(handler) as client:
            with pytest.raises(MCPClientError) as exc:
                await list_remote_tools(SERVER_URL, client=client)
        assert exc.value.code == "mcp_initialize_error"
    finally:
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_tools_list_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "tools/list":
            cursor = (body.get("params") or {}).get("cursor")
            if not cursor:
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": [{"name": "a"}], "nextCursor": "p2"}})
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": [{"name": "b"}]}})
        return _json_handler(request)

    try:
        async with _mock_client(handler) as client:
            tools = await list_remote_tools(SERVER_URL, client=client)
        assert {t["name"] for t in tools} == {"a", "b"}
    finally:
        get_settings.cache_clear()
