"""A3 behavioral-matrix: drive Algenta's REAL production MCP Server with the OFFICIAL mcp SDK.

Confirmed gap (mcp==2.0.0, bumped in #849): mcp.client._memory.InMemoryTransport ships explicitly
"for testing MCP servers without network overhead", driving a real mcp.server.lowlevel.server.Server
directly with the official mcp.ClientSession -- and nothing in this suite used it. Everything else
(the ~20 existing tests/test_mcp_*.py files, tests/integration/test_mcp_server.py,
packages/mcp/tests/test_protocol.py) drives Algenta's own tools through Starlette's TestClient, raw
httpx, or Algenta's own hand-rolled client/registry calls -- never the official third-party SDK
talking to a real Server object the way an actual MCP client (Claude Desktop, Cursor, an
agent framework) would.

Two real Server-construction paths exist in production, both privately nested (no public
constructor exported) -- see apps/mcp_server/transports/stdio.py::run_stdio_server and
apps/mcp_server/transports/http_sse.py::_build_fastapi_router. This file drives BOTH, faithfully,
with zero reimplementation of their logic:

  * InMemoryTransport tests capture the REAL Server that run_stdio_server() builds, by spying on
    mcp.server.Server.__init__ (a stable, public SDK constructor -- not an Algenta internal) and
    aborting stdio_server() (also monkeypatched) before it touches the real process's stdin/stdout,
    right after the real Server is constructed. Every handler on the captured Server is exactly
    apps.mcp_server.registry.call_tool / get_tool_specs -- Algenta's real production dispatch.
    Zero HTTP is involved: this is the true "in-memory, no network overhead" case the gap names.

  * The live-HTTP tests drive the REAL embedded mount (apps.mcp_server.server.create_fastapi_router,
    the exact router apps/api_server/main.py includes on the real app) over a real loopback socket,
    using the official mcp.client.streamable_http.streamable_http_client + mcp.ClientSession. This
    is the transport whose auth-challenge behavior (apps/mcp_server/transports/http_sse.py's
    _MCPToolCallAuthChallengeASGIApp) only exists at the HTTP layer -- InMemoryTransport bypasses
    it entirely (ctx.request is None), so it needs a real socket to exercise for real.

Every assertion below is against a real, running Algenta stack (real live apps.api_server.main:app
process, real Postgres-backed auth, real registry/tool dispatch) reached exclusively through the
official mcp SDK's own client objects -- never Algenta's own client.py, never a raw HTTP status
code inspected by hand.
"""

from __future__ import annotations

import asyncio
import contextlib
import tempfile
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp import ClientSession
from mcp.client._memory import InMemoryTransport
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from tests._mcp_live_server_fixture import live_api_server, seed_owner_org_and_key

pytestmark = pytest.mark.anyio


# ── shared live server + real seeded org/key ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def live_server():
    runtime_dir = Path(tempfile.mkdtemp(prefix="a3-official-sdk-runtime-"))
    with live_api_server(runtime_dir=runtime_dir) as base_url:
        yield base_url


@pytest.fixture(scope="module")
def owner_auth(live_server: str) -> tuple[str, str]:
    del live_server
    return asyncio.run(seed_owner_org_and_key("official-sdk"))


# ── in-memory transport: the REAL stdio Server, captured via a spy on the SDK's own public
#    Server.__init__ (never Algenta's private nested builder), never touching real stdin/stdout ──


class _AbortStdioError(Exception):
    """Sentinel used to stop run_stdio_server() the instant its real Server is constructed,
    before it tries to open the process's actual stdin/stdout streams."""


async def _build_real_stdio_server() -> Any:
    import mcp.server as mcp_server_module
    import mcp.server.stdio as stdio_module

    captured: dict[str, Any] = {}
    original_init = mcp_server_module.Server.__init__

    def _capturing_init(self: Any, *args: Any, **kwargs: Any) -> None:
        captured["server"] = self
        original_init(self, *args, **kwargs)

    @contextlib.asynccontextmanager
    async def _abort_before_real_stdio():
        raise _AbortStdioError()
        yield  # pragma: no cover - unreachable, required to keep this an async generator

    mcp_server_module.Server.__init__ = _capturing_init
    stdio_module.stdio_server = _abort_before_real_stdio
    try:
        from apps.mcp_server.transports.stdio import run_stdio_server

        try:
            await run_stdio_server()
        except _AbortStdioError:
            pass
    finally:
        mcp_server_module.Server.__init__ = original_init
    assert "server" in captured, "run_stdio_server() did not construct a Server before aborting"
    return captured["server"]


async def test_inmemory_official_sdk_initialize_and_list_tools(live_server: str) -> None:
    del live_server
    server = await _build_real_stdio_server()
    async with InMemoryTransport(server) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            assert init.server_info.name == "algenta-mcp"
            tools = await session.list_tools()
            assert len(tools.tools) > 100, "the real full registry should list well over 100 tools"
            assert any(tool.name == "list_decisions" for tool in tools.tools)
            assert any(tool.name == "execute_decision" for tool in tools.tools)
            assert any(tool.name == "approve_agent_run" for tool in tools.tools)


async def test_inmemory_official_sdk_call_tool_readonly_succeeds_with_real_backend(
    live_server: str, owner_auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stdio Server has no per-request HTTP scope, so it authenticates ambiently (env
    ALGENTA_API_KEY/ALGENTA_BASE_URL) -- set those to a REAL seeded key + the REAL live server,
    then call a read-only tool through the official SDK and confirm a real, successful result."""
    owner_key, _org_id = owner_auth
    monkeypatch.setenv("ALGENTA_API_KEY", owner_key)
    monkeypatch.setenv("ALGENTA_BASE_URL", live_server)

    server = await _build_real_stdio_server()
    async with InMemoryTransport(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_decisions", {})
            assert result.is_error is False
            assert '"decisions"' in result.content[0].text
            assert '"total"' in result.content[0].text


async def test_inmemory_official_sdk_call_tool_without_credential_surfaces_real_auth_error(
    live_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ambient credential at all -> the REAL UnsupportedMCPAuthConfigurationError from
    apps/mcp_server/client.py, surfaced through the official SDK's CallToolResult -- a genuine
    structured auth error, not a guess."""
    del live_server
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    server = await _build_real_stdio_server()
    async with InMemoryTransport(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_decisions", {})
            # Since the algenta-mcp 1.0.28 error-envelope contract (PR #1154, ported to this
            # embedded copy in the apps/mcp_server re-sync), the serialize_tool_error path
            # marks the envelope isError=True so agents read a failure as a failure; the
            # structured error JSON in content[0].text is unchanged from before. (This pin
            # previously asserted isError=False as "intentional" — that was the bug the
            # 1.0.28 contract fixed.)
            assert result.is_error is True
            assert "unsupported_mcp_auth_configuration" in result.content[0].text
            assert "ALGENTA_API_KEY" in result.content[0].text


# ── live HTTP: the REAL embedded /mcp mount, official SDK over a real loopback socket ────────


async def test_live_http_official_sdk_initialize_and_list_tools_are_public(live_server: str) -> None:
    """Discovery (initialize/list_tools) stays open with NO Authorization header -- the real
    posture apps/mcp_server/transports/http_sse.py documents (only tools/call is challenged)."""
    mcp_url = f"{live_server}/mcp"
    async with httpx2.AsyncClient() as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                assert init.server_info.name == "algenta-mcp"
                tools = await session.list_tools()
                assert any(tool.name == "list_decisions" for tool in tools.tools)


async def test_live_http_official_sdk_call_tool_without_bearer_surfaces_real_mcp_error(
    live_server: str,
) -> None:
    """A tools/call with no credential hits the real ASGI-layer auth challenge
    (_MCPToolCallAuthChallengeASGIApp), which replies with a raw HTTP 401 whose body is a
    well-formed JSON-RPC error. The official SDK's own transport (mcp.client.streamable_http)
    parses that body and raises it as a genuine mcp.shared.exceptions.MCPError to the caller --
    NOT a raw httpx.HTTPStatusError the test would have to inspect by hand."""
    mcp_url = f"{live_server}/mcp"
    async with httpx2.AsyncClient() as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                with pytest.raises(MCPError) as excinfo:
                    await session.call_tool("list_decisions", {})
    assert excinfo.value.code == -32001
    assert "authentication required" in excinfo.value.message.lower()


async def test_live_http_official_sdk_call_tool_with_bearer_succeeds_for_real(
    live_server: str, owner_auth: tuple[str, str]
) -> None:
    """A real Bearer token on the official SDK's http_client clears the real auth challenge and
    reaches the real embedded tool dispatch (apps/mcp_server/transports/http_sse.py's
    use_request_base_url=True variant, forwarding to this SAME live process)."""
    owner_key, _org_id = owner_auth
    mcp_url = f"{live_server}/mcp"
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {owner_key}"}) as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("list_decisions", {})
    assert result.is_error is False
    assert '"decisions"' in result.content[0].text
