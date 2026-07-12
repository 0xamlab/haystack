"""
HTTP transport for OpenWebUI, LibreChat, Continue, Cline HTTP, n8n, and custom apps.

Canonical standalone endpoints:
  GET  /mcp/tools     — tool listing (human-readable)
  *    /mcp           — Streamable HTTP (GET, POST, DELETE)

Deprecated HTTP+SSE endpoints remain available for backward compatibility:
  GET  /mcp/sse
  POST /mcp/messages
  GET  /tools
  GET  /sse
  POST /messages

Also exports _build_fastapi_router() for embedding in the main FastAPI app.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import structlog
from fastapi import APIRouter, status
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class _StreamableHTTPASGIApp:
    """ASGI adapter for the official SDK session manager."""

    def __init__(self, session_manager: Any) -> None:
        self._session_manager = session_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._session_manager.handle_request(scope, receive, send)


class _CallableASGIApp:
    """Keep raw ASGI callables from being coerced into request handlers by Starlette."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app(scope, receive, send)


class _MCPToolCallAuthChallengeASGIApp:
    """Require caller auth for embedded tool execution while leaving discovery public."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("method") != "POST" or _scope_api_key(scope):
            await self._app(scope, receive, send)
            return

        received: list[Message] = []
        while True:
            message = await receive()
            received.append(message)
            if message.get("type") != "http.request" or not message.get("more_body", False):
                break

        body = b"".join(
            message.get("body", b"")
            for message in received
            if message.get("type") == "http.request"
        )
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            payload = None

        if isinstance(payload, dict) and payload.get("method") == "tools/call":
            response = JSONResponse(
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Bearer realm="algenta", error="invalid_token"'
                },
                content={
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {
                        "code": -32001,
                        "message": "Authentication required: sign in to run Algenta tools.",
                    },
                },
            )
            await response(scope, receive, send)
            return

        replay_index = 0

        async def replay_receive() -> Message:
            nonlocal replay_index
            if replay_index < len(received):
                message = received[replay_index]
                replay_index += 1
                return message
            return await receive()

        await self._app(scope, replay_receive, send)


class _LifespanBoundASGIApp:
    """Dispatch to the fresh official SDK manager owned by the active lifespan."""

    def __init__(self) -> None:
        self._app: ASGIApp | None = None

    def bind(self, app: ASGIApp) -> None:
        if self._app is not None:
            raise RuntimeError("MCP Streamable HTTP manager is already active.")
        self._app = app

    def unbind(self, app: ASGIApp) -> None:
        if self._app is not app:
            raise RuntimeError("MCP Streamable HTTP manager ownership changed unexpectedly.")
        self._app = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        app = self._app
        if app is None:
            response = JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "mcp_transport_unavailable",
                        "message": "The MCP Streamable HTTP manager is not running.",
                    }
                },
            )
            await response(scope, receive, send)
            return
        await app(scope, receive, send)


@asynccontextmanager
async def _streamable_manager_lifespan(session_manager: Any):
    """Keep the SDK manager's AnyIO cancel scope inside one task."""
    started = asyncio.Event()
    stop = asyncio.Event()

    async def _serve() -> None:
        async with session_manager.run():
            started.set()
            await stop.wait()

    task = asyncio.create_task(_serve(), name="algenta-mcp-streamable-http")
    started_wait = asyncio.create_task(started.wait())
    done, _ = await asyncio.wait({task, started_wait}, return_when=asyncio.FIRST_COMPLETED)
    if task in done:
        started_wait.cancel()
        await task
        raise RuntimeError("MCP Streamable HTTP manager exited during startup.")
    try:
        yield
    finally:
        stop.set()
        await task


def _scope_headers(scope: Scope) -> dict[str, str]:
    headers: dict[str, str] = {}
    raw_headers = scope.get("headers", ())
    if not isinstance(raw_headers, Sequence):
        return headers
    for header in raw_headers:
        if not isinstance(header, Sequence) or len(header) != 2:
            continue
        raw_key, raw_value = header
        if not isinstance(raw_key, bytes) or not isinstance(raw_value, bytes):
            continue
        try:
            key = raw_key.decode("latin-1").lower()
            value = raw_value.decode("latin-1")
        except Exception as exc:
            logger.debug("scope_header_decode_failed", error=str(exc))
            continue
        headers[key] = value
    return headers


def _scope_api_key(scope: Scope) -> str | None:
    headers = _scope_headers(scope)
    auth = headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    api_key = headers.get("x-api-key", "").strip()
    return api_key or None


def _scope_base_url(scope: Scope) -> str | None:
    headers = _scope_headers(scope)
    scheme = str(scope.get("scheme") or "http").lower()
    if scheme not in {"http", "https"}:
        return None
    host = headers.get("host")
    if not host:
        server = scope.get("server")
        if isinstance(server, tuple) and len(server) == 2:
            host = f"{server[0]}:{server[1]}"
    if not host:
        return None
    return f"{scheme}://{host}".rstrip("/")


def _embedded_downstream_base_url(scope: Scope) -> str:
    """Resolve the in-process API target used by embedded MCP tool handlers."""
    configured = os.environ.get("ALGENTA_MCP_LOOPBACK_URL", "").strip().rstrip("/")
    if configured:
        parsed = urlsplit(configured)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "ALGENTA_MCP_LOOPBACK_URL must be an absolute loopback HTTP(S) URL."
            )
        return configured

    port_text = os.environ.get("PORT", "8000").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("PORT must be an integer for embedded MCP routing.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535 for embedded MCP routing.")
    return f"http://127.0.0.1:{port}"


def _scope_product(scope: Scope) -> str | None:
    """Read the ``X-Algenta-Product`` routing hint that selects an edition."""
    return _scope_headers(scope).get("x-algenta-product", "").strip() or None


def _request_product(server: Any) -> str | None:
    """Pull the product hint off the active MCP request's HTTP scope (if any)."""
    try:
        request = server.request_context.request
    except LookupError:
        return None
    if request is not None and hasattr(request, "scope"):
        return _scope_product(request.scope)
    return None


def _transport_security_settings(default_base_url: str) -> Any:
    """Build the SDK's DNS-rebinding guard from normal Algenta URL configuration."""
    from mcp.server.transport_security import TransportSecuritySettings

    allowed_hosts = {"127.0.0.1:*", "localhost:*", "[::1]:*"}
    allowed_origins = {
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        "https://127.0.0.1:*",
        "https://localhost:*",
        "https://[::1]:*",
    }
    configured_urls = [
        os.environ.get("ALGENTA_BASE_URL", ""),
        os.environ.get("DE_BASE_URL", ""),
        os.environ.get("ALGENTA_API_URL", ""),
        default_base_url,
    ]
    for value in configured_urls:
        parsed = urlsplit(value.strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            allowed_hosts.add(parsed.netloc)
            allowed_origins.add(f"{parsed.scheme}://{parsed.netloc}")
    allowed_hosts.update(
        item.strip()
        for item in os.environ.get("ALGENTA_MCP_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    )
    allowed_origins.update(
        item.strip()
        for item in os.environ.get("ALGENTA_MCP_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(allowed_hosts),
        allowed_origins=sorted(allowed_origins),
    )


async def run_http_server(host: str = "127.0.0.1", port: int = 8001) -> None:
    """Run the MCP server over Streamable HTTP with legacy SSE compatibility."""
    try:
        import uvicorn
    except ImportError:
        logger.error("http_deps_missing", hint="pip install mcp starlette uvicorn")
        raise

    app = _build_http_app()
    logger.info("mcp_http_server_starting", host=host, port=port)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    uvr = uvicorn.Server(config)
    await uvr.serve()


def _build_http_app() -> ASGIApp:
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions
    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.types import TextContent, Tool
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    from algenta_mcp import config
    from algenta_mcp.client import request_overrides
    from algenta_mcp.errors import serialize_tool_error
    from algenta_mcp.products import resolve_visible_tools
    from algenta_mcp.registry import call_tool, get_tool_specs

    def _build_server(*, use_request_base_url: bool) -> Any:
        server = Server("algenta-mcp", version=config.VERSION)

        @server.list_tools()  # type: ignore[misc]
        async def handle_list_tools() -> list[Tool]:
            allowed = resolve_visible_tools(_request_product(server))
            return [
                Tool(
                    name=spec["name"],
                    description=spec["description"],
                    inputSchema=spec["inputSchema"],
                )
                for spec in get_tool_specs(allowed)
            ]

        @server.call_tool()  # type: ignore[misc]
        async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            request: object | None = None
            try:
                request = server.request_context.request
            except LookupError:
                pass
            scope = request.scope if request is not None and hasattr(request, "scope") else {}
            try:
                with request_overrides(
                    api_key=_scope_api_key(scope),
                    base_url=(
                        _embedded_downstream_base_url(scope) if use_request_base_url else None
                    ),
                ):
                    result = await call_tool(
                        name,
                        arguments or {},
                        resolve_visible_tools(_scope_product(scope)),
                    )
            except Exception as exc:
                logger.error("tool_error", tool=name, error=str(exc))
                result = serialize_tool_error(exc, tool_name=name)
            return [TextContent(type="text", text=result)]

        return server

    def _build_legacy_transport_endpoints(*, messages_path: str) -> tuple[ASGIApp, ASGIApp]:
        server = _build_server(use_request_base_url=False)
        sse_transport = SseServerTransport(messages_path)

        async def sse_endpoint_app(scope: Scope, receive: Receive, send: Send) -> None:
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                init_opts = InitializationOptions(
                    server_name="algenta-mcp",
                    server_version=config.VERSION,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                )
                await server.run(streams[0], streams[1], init_opts)

        async def post_message_endpoint_app(
            scope: Scope,
            receive: Receive,
            send: Send,
        ) -> None:
            await sse_transport.handle_post_message(scope, receive, send)

        return sse_endpoint_app, post_message_endpoint_app

    streamable_http = _LifespanBoundASGIApp()
    canonical_sse, canonical_messages = _build_legacy_transport_endpoints(
        messages_path="/mcp/messages"
    )
    legacy_sse, legacy_messages = _build_legacy_transport_endpoints(messages_path="/messages")

    @asynccontextmanager
    async def lifespan(_: Any):
        streamable_manager = StreamableHTTPSessionManager(
            app=_build_server(use_request_base_url=False),
            json_response=True,
            stateless=True,
            security_settings=_transport_security_settings(config.BASE_URL),
        )
        active_app = _StreamableHTTPASGIApp(streamable_manager)
        async with _streamable_manager_lifespan(streamable_manager):
            streamable_http.bind(active_app)
            try:
                yield
            finally:
                streamable_http.unbind(active_app)

    async def handle_tools(request: Request) -> JSONResponse:
        allowed = resolve_visible_tools(
            (request.headers.get("x-algenta-product") or "").strip() or None
        )
        return JSONResponse({"tools": get_tool_specs(allowed)})

    return Starlette(
        routes=[
            Route("/mcp/tools", endpoint=handle_tools),
            Route("/mcp", endpoint=streamable_http),
            Mount("/mcp/sse", app=canonical_sse),
            Mount("/mcp/messages", app=canonical_messages),
            Route("/tools", endpoint=handle_tools),
            Mount("/sse", app=legacy_sse),
            Mount("/messages", app=legacy_messages),
        ],
        lifespan=lifespan,
    )


def _build_fastapi_router() -> APIRouter | None:
    """
    Return a FastAPI APIRouter mounting Streamable HTTP and legacy SSE at /mcp/*.
    Called from apps/api_server/main.py to embed MCP into the main API process.
    Returns a tools-only router if the optional mcp package is not installed.
    """
    try:
        from fastapi import APIRouter
        from starlette.responses import JSONResponse

        from algenta_mcp.products import resolve_visible_tools
        from algenta_mcp.registry import get_tool_specs
    except ImportError:
        return None

    try:
        from mcp.server import NotificationOptions, Server
        from mcp.server.models import InitializationOptions
        from mcp.server.sse import SseServerTransport
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from mcp.types import TextContent, Tool

        from algenta_mcp import config
        from algenta_mcp.client import request_overrides
        from algenta_mcp.errors import serialize_tool_error
        from algenta_mcp.registry import call_tool
    except ImportError:
        router = APIRouter(tags=["MCP"])

        def _mcp_transport_unavailable_response() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "mcp_transport_unavailable",
                        "message": "The MCP HTTP transport is unavailable in this environment.",
                        "details": {
                            "hint": "Install the API or algenta-mcp package with its dependencies."
                        },
                    }
                },
            )

        @router.get(
            "/mcp",
            summary="MCP Streamable HTTP transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={
                503: {
                    "description": "MCP Streamable HTTP transport unavailable in this environment."
                }
            },
        )
        async def mcp_streamable_http_get_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        @router.post(
            "/mcp",
            summary="MCP Streamable HTTP transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={503: {"description": "MCP Streamable HTTP transport unavailable."}},
        )
        async def mcp_streamable_http_post_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        @router.delete(
            "/mcp",
            summary="MCP Streamable HTTP transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={503: {"description": "MCP Streamable HTTP transport unavailable."}},
        )
        async def mcp_streamable_http_delete_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        @router.get(
            "/mcp/sse",
            summary="Legacy MCP SSE transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={
                503: {
                    "description": "Legacy MCP SSE transport unavailable in this environment."
                }
            },
        )
        async def mcp_sse_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        @router.post(
            "/mcp/messages",
            summary="Legacy MCP message transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={
                503: {
                    "description": "Legacy MCP message transport unavailable in this environment."
                }
            },
        )
        async def mcp_messages_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        logger.warning(
            "mcp_http_transport_unavailable",
            hint="Install the API or algenta-mcp package with its dependencies.",
        )

        @router.get("/mcp/tools", summary="List available MCP tools")
        async def list_tools_unavailable(request: Request) -> JSONResponse:
            allowed = resolve_visible_tools(
                (request.headers.get("x-algenta-product") or "").strip() or None
            )
            return JSONResponse({"tools": get_tool_specs(allowed)})

        return router

    def _build_server(*, use_request_base_url: bool) -> Any:
        server = Server("algenta-mcp", version=config.VERSION)

        @server.list_tools()  # type: ignore[misc]
        async def _list_tools() -> list[Tool]:
            allowed = resolve_visible_tools(_request_product(server))
            return [
                Tool(
                    name=spec["name"],
                    description=spec["description"],
                    inputSchema=spec["inputSchema"],
                )
                for spec in get_tool_specs(allowed)
            ]

        @server.call_tool()  # type: ignore[misc]
        async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            request: object | None = None
            try:
                request = server.request_context.request
            except LookupError:
                pass
            scope = request.scope if request is not None and hasattr(request, "scope") else {}
            try:
                with request_overrides(
                    api_key=_scope_api_key(scope),
                    base_url=(
                        _embedded_downstream_base_url(scope) if use_request_base_url else None
                    ),
                ):
                    result = await call_tool(
                        name,
                        arguments or {},
                        resolve_visible_tools(_scope_product(scope)),
                    )
            except Exception as exc:
                logger.error("tool_error", tool=name, error=str(exc))
                result = serialize_tool_error(exc, tool_name=name)
            return [TextContent(type="text", text=result)]

        return server

    mcp_server = _build_server(use_request_base_url=True)
    sse_transport = SseServerTransport("/mcp/messages")

    async def sse_endpoint_app(scope: Scope, receive: Receive, send: Send) -> None:
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            init_opts = InitializationOptions(
                server_name="algenta-mcp",
                server_version=config.VERSION,
                capabilities=mcp_server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )
            await mcp_server.run(streams[0], streams[1], init_opts)

    async def post_message_endpoint_app(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        await sse_transport.handle_post_message(scope, receive, send)

    streamable_http = _LifespanBoundASGIApp()

    @asynccontextmanager
    async def lifespan(_: Any):
        streamable_manager = StreamableHTTPSessionManager(
            app=_build_server(use_request_base_url=True),
            json_response=True,
            stateless=True,
            security_settings=_transport_security_settings(config.BASE_URL),
        )
        active_app = _MCPToolCallAuthChallengeASGIApp(
            _StreamableHTTPASGIApp(streamable_manager)
        )
        async with _streamable_manager_lifespan(streamable_manager):
            streamable_http.bind(active_app)
            try:
                yield
            finally:
                streamable_http.unbind(active_app)

    router = APIRouter(tags=["MCP"], lifespan=lifespan)

    @router.get("/mcp/tools", summary="List available MCP tools")
    async def list_tools(request: Request) -> JSONResponse:
        allowed = resolve_visible_tools(
            (request.headers.get("x-algenta-product") or "").strip() or None
        )
        return JSONResponse({"tools": get_tool_specs(allowed)})

    router.add_route(
        "/mcp",
        streamable_http,
        methods=["GET", "POST", "DELETE"],
        name="mcp_streamable_http",
    )
    router.add_route(
        "/mcp/sse",
        _CallableASGIApp(sse_endpoint_app),
        methods=["GET"],
        name="mcp_sse",
    )
    router.add_route(
        "/mcp/messages",
        _CallableASGIApp(post_message_endpoint_app),
        methods=["POST"],
        name="mcp_messages",
    )

    return router
