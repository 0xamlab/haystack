"""
HTTP/SSE transport — for OpenWebUI, LibreChat, Continue, Cline HTTP, n8n, custom apps.

Endpoint: GET /sse     — SSE connection
          POST /messages — MCP message handler
          GET /tools    — tool listing (human-readable)

Also exports _build_fastapi_router() for embedding in the main FastAPI app.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def _scope_headers(scope) -> dict[str, str]:
    headers = {}
    for raw_key, raw_value in scope.get("headers", []):
        try:
            key = raw_key.decode("latin-1").lower()
            value = raw_value.decode("latin-1")
        except Exception as exc:
            logger.debug("scope_header_decode_failed", error=str(exc))
            continue
        headers[key] = value
    return headers


def _scope_api_key(scope) -> str | None:
    headers = _scope_headers(scope)
    auth = headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    api_key = headers.get("x-api-key", "").strip()
    return api_key or None


def _scope_base_url(scope) -> str | None:
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


async def run_http_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Run the MCP server over HTTP/SSE."""
    try:
        import uvicorn
        from mcp.server import NotificationOptions, Server
        from mcp.server.models import InitializationOptions
        from mcp.server.sse import SseServerTransport
        from mcp.types import TextContent, Tool
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError:
        logger.error("http_deps_missing", hint="pip install mcp starlette uvicorn")
        raise

    from apps.mcp_server.client import request_overrides
    from apps.mcp_server.errors import serialize_tool_error
    from apps.mcp_server.registry import call_tool, get_tool_specs

    server  = Server("algenta-decision-engine")
    sse_transport = SseServerTransport("/messages")

    class _SSEEndpointApp:
        async def __call__(self, scope, receive, send):
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

    class _PostMessageEndpointApp:
        async def __call__(self, scope, receive, send):
            await sse_transport.handle_post_message(scope, receive, send)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name=spec["name"],
                description=spec["description"],
                inputSchema=spec["inputSchema"],
            )
            for spec in get_tool_specs()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        request = None
        api_key = None
        base_url = None
        try:
            request = server.request_context.request
        except LookupError:
            request = None
        if request is not None:
            api_key = _scope_api_key(request.scope)
            base_url = _scope_base_url(request.scope)
        try:
            with request_overrides(api_key=api_key, base_url=base_url):
                result = await call_tool(name, arguments or {})
        except Exception as exc:
            logger.error("tool_error", tool=name, error=str(exc))
            result = serialize_tool_error(exc, tool_name=name)
        return [TextContent(type="text", text=result)]

    async def handle_tools(request: Request):
        return JSONResponse({"tools": get_tool_specs()})

    app = Starlette(
        routes=[
            Route("/sse",      endpoint=_SSEEndpointApp(), methods=["GET"]),
            Route("/tools",    endpoint=handle_tools),
            Route("/messages", endpoint=_PostMessageEndpointApp(), methods=["POST"]),
        ],
    )

    logger.info("mcp_http_server_starting", host=host, port=port)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    uvr    = uvicorn.Server(config)
    await uvr.serve()


def _build_fastapi_router():
    """
    Return a FastAPI APIRouter mounting MCP SSE at /mcp/*.
    Called from apps/api_server/main.py to embed MCP into the main API process.
    Returns a tools-only router if the optional mcp package is not installed.
    """
    try:
        from fastapi import APIRouter
        from starlette.responses import JSONResponse

        from apps.mcp_server.registry import get_tool_specs
    except ImportError:
        return None

    router = APIRouter(tags=["MCP"])

    @router.get("/mcp/tools", summary="List available MCP tools")
    async def list_tools():
        return JSONResponse({"tools": get_tool_specs()})

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
                        "message": (
                            "The MCP SSE transport is unavailable in this environment."
                        ),
                        "details": {
                            "hint": (
                                "Install requirements-mcp.txt to enable "
                                "/mcp/sse and /mcp/messages."
                            )
                        },
                    }
                },
            )

        @router.get("/mcp/sse", summary="MCP SSE transport unavailable")
        async def mcp_sse_unavailable():
            return _mcp_transport_unavailable_response()

        @router.post("/mcp/messages", summary="MCP message transport unavailable")
        async def mcp_messages_unavailable():
            return _mcp_transport_unavailable_response()

        logger.warning(
            "mcp_sse_transport_unavailable",
            hint="Install requirements-mcp.txt to enable /mcp/sse and /mcp/messages.",
        )
        return router

    mcp_server = Server("algenta-decision-engine")
    sse_transport = SseServerTransport("/mcp/messages")
    from apps.mcp_server.client import request_overrides

    class _SSEEndpointApp:
        async def __call__(self, scope, receive, send):
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

    class _PostMessageEndpointApp:
        async def __call__(self, scope, receive, send):
            await sse_transport.handle_post_message(scope, receive, send)

    @mcp_server.list_tools()
    async def _list_tools() -> list[Tool]:
        return [
            Tool(
                name=spec["name"],
                description=spec["description"],
                inputSchema=spec["inputSchema"],
            )
            for spec in get_tool_specs()
        ]

    @mcp_server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
        request = None
        api_key = None
        base_url = None
        try:
            request = mcp_server.request_context.request
        except LookupError:
            request = None
        if request is not None:
            api_key = _scope_api_key(request.scope)
            base_url = _scope_base_url(request.scope)
        try:
            with request_overrides(api_key=api_key, base_url=base_url):
                result = await call_tool(name, arguments or {})
        except Exception as exc:
            logger.error("tool_error", tool=name, error=str(exc))
            result = serialize_tool_error(exc, tool_name=name)
        return [TextContent(type="text", text=result)]

    router.add_route("/mcp/sse", _SSEEndpointApp(), methods=["GET"])
    router.add_route(
        "/mcp/messages",
        _PostMessageEndpointApp(),
        methods=["POST"],
        name="mcp_messages",
    )

    return router
