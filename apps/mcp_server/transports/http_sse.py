"""
HTTP/SSE transport — for OpenWebUI, LibreChat, Continue, Cline HTTP, n8n, custom apps.

Canonical standalone endpoints:
  GET  /mcp/tools     — tool listing (human-readable)
  GET  /mcp/sse       — SSE connection
  POST /mcp/messages  — MCP message handler

Legacy aliases remain available for backward compatibility:
  GET  /tools
  GET  /sse
  POST /messages

Also exports _build_fastapi_router() for embedding in the main FastAPI app.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from typing import Any

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
    scheme = headers.get("x-forwarded-proto") or scope.get("scheme") or "http"
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host:
        server = scope.get("server")
        if isinstance(server, tuple) and len(server) == 2:
            host = f"{server[0]}:{server[1]}"
    if not host:
        return None
    return f"{scheme}://{host}".rstrip("/")


def _scope_product(scope: Scope) -> str | None:
    """The ``X-Algenta-Product`` routing hint (e.g. ``codna``) — selects an edition."""
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


async def run_http_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Run the MCP server over HTTP/SSE."""
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
    from mcp.types import TextContent, Tool
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    from apps.mcp_server.client import request_overrides
    from apps.mcp_server.errors import serialize_tool_error
    from apps.mcp_server.products import resolve_visible_tools
    from apps.mcp_server.registry import call_tool, get_tool_specs

    def _build_transport_endpoints(
        *,
        messages_path: str,
    ) -> tuple[ASGIApp, ASGIApp]:
        server = Server("algenta-decision-engine")
        sse_transport = SseServerTransport(messages_path)

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
            api_key: str | None = None
            base_url: str | None = None
            product: str | None = None
            try:
                request = server.request_context.request
            except LookupError:
                request = None
            if request is not None and hasattr(request, "scope"):
                api_key = _scope_api_key(request.scope)
                base_url = _scope_base_url(request.scope)
                product = _scope_product(request.scope)
            try:
                with request_overrides(api_key=api_key, base_url=base_url):
                    result = await call_tool(name, arguments or {}, resolve_visible_tools(product))
            except Exception as exc:
                logger.error("tool_error", tool=name, error=str(exc))
                result = serialize_tool_error(exc, tool_name=name)
            return [TextContent(type="text", text=result)]

        async def sse_endpoint_app(scope: Scope, receive: Receive, send: Send) -> None:
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                init_opts = InitializationOptions(
                    server_name="algenta-decision-engine",
                    server_version="1.0.0",
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

    canonical_sse, canonical_messages = _build_transport_endpoints(messages_path="/mcp/messages")
    legacy_sse, legacy_messages = _build_transport_endpoints(messages_path="/messages")

    async def handle_tools(request: Request) -> JSONResponse:
        allowed = resolve_visible_tools(
            (request.headers.get("x-algenta-product") or "").strip() or None
        )
        return JSONResponse({"tools": get_tool_specs(allowed)})

    return Starlette(
        routes=[
            Route("/mcp/tools", endpoint=handle_tools),
            Mount("/mcp/sse", app=canonical_sse),
            Mount("/mcp/messages", app=canonical_messages),
            Route("/tools", endpoint=handle_tools),
            Mount("/sse", app=legacy_sse),
            Mount("/messages", app=legacy_messages),
        ],
    )


def _build_fastapi_router() -> APIRouter | None:
    """
    Return a FastAPI APIRouter mounting MCP SSE at /mcp/*.
    Called from apps/api_server/main.py to embed MCP into the main API process.
    Returns a tools-only router if the optional mcp package is not installed.
    """
    try:
        from fastapi import APIRouter
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        from apps.mcp_server.products import resolve_visible_tools
        from apps.mcp_server.registry import get_tool_specs
    except ImportError:
        return None

    router = APIRouter(tags=["MCP"])

    @router.get("/mcp/tools", summary="List available MCP tools")
    async def list_tools(request: Request) -> JSONResponse:
        allowed = resolve_visible_tools(
            (request.headers.get("x-algenta-product") or "").strip() or None
        )
        return JSONResponse({"tools": get_tool_specs(allowed)})

    try:
        from mcp.server import NotificationOptions, Server
        from mcp.server.models import InitializationOptions
        from mcp.server.sse import SseServerTransport
        from mcp.types import TextContent, Tool

        from apps.mcp_server.errors import serialize_tool_error
        from apps.mcp_server.registry import call_tool
    except ImportError:

        def _mcp_transport_unavailable_response() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "mcp_transport_unavailable",
                        "message": ("The MCP SSE transport is unavailable in this environment."),
                        "details": {
                            "hint": (
                                "Install requirements-mcp.txt to enable /mcp/sse and /mcp/messages."
                            )
                        },
                    }
                },
            )

        @router.get(
            "/mcp/sse",
            summary="MCP SSE transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={
                503: {
                    "description": "MCP SSE transport unavailable in this environment."
                }
            },
        )
        async def mcp_sse_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        @router.post(
            "/mcp/messages",
            summary="MCP message transport unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            responses={
                503: {
                    "description": "MCP message transport unavailable in this environment."
                }
            },
        )
        async def mcp_messages_unavailable() -> JSONResponse:
            return _mcp_transport_unavailable_response()

        logger.warning(
            "mcp_sse_transport_unavailable",
            hint="Install requirements-mcp.txt to enable /mcp/sse and /mcp/messages.",
        )
        return router

    mcp_server = Server("algenta-decision-engine")
    sse_transport = SseServerTransport("/mcp/messages")
    from apps.mcp_server.client import request_overrides

    async def sse_endpoint_app(scope: Scope, receive: Receive, send: Send) -> None:
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            init_opts = InitializationOptions(
                server_name="algenta-decision-engine",
                server_version="1.0.0",
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

    @mcp_server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Tool]:
        allowed = resolve_visible_tools(_request_product(mcp_server))
        return [
            Tool(
                name=spec["name"],
                description=spec["description"],
                inputSchema=spec["inputSchema"],
            )
            for spec in get_tool_specs(allowed)
        ]

    @mcp_server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        request: object | None = None
        api_key: str | None = None
        base_url: str | None = None
        product: str | None = None
        try:
            request = mcp_server.request_context.request
        except LookupError:
            request = None
        if request is not None and hasattr(request, "scope"):
            api_key = _scope_api_key(request.scope)
            base_url = _scope_base_url(request.scope)
            product = _scope_product(request.scope)
        try:
            with request_overrides(api_key=api_key, base_url=base_url):
                result = await call_tool(name, arguments or {}, resolve_visible_tools(product))
        except Exception as exc:
            logger.error("tool_error", tool=name, error=str(exc))
            result = serialize_tool_error(exc, tool_name=name)
        return [TextContent(type="text", text=result)]

    router.mount("/mcp/sse", sse_endpoint_app, name="mcp_sse")
    router.mount("/mcp/messages", post_message_endpoint_app, name="mcp_messages")

    return router
