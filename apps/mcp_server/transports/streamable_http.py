"""MCP Streamable HTTP transport — a single ``POST /mcp`` JSON-RPC endpoint.

This is the transport Microsoft 365 Copilot's ``RemoteMCPServer`` runtime connects
to (declarative-agent MCP support, GA 2025-12-15). It speaks MCP over the modern
Streamable HTTP transport (one endpoint, JSON-RPC 2.0 request/response) directly on
the existing tool ``registry`` — with NO dependency on the ``mcp`` package, so it is
immune to the ``mcp`` → ``starlette>=0.52`` vs FastAPI version conflict that leaves
the legacy ``/mcp/sse`` transport dark on the API image.

Design:
  * ``tools/list`` / ``tools/call`` are served from ``registry`` (the same specs +
    handlers the stdio / SSE transports use), so the tool surface is identical.
  * A tool call forwards the caller's Bearer token (Microsoft Entra SSO acquired by
    Copilot via the OAuthPluginVault) to a LOOPBACK engine call (``localhost:8000``),
    so tools execute as the signed-in user/org under the engine's own auth.

Copilot compatibility notes (verified against Microsoft Learn + the Agents Toolkit
issue tracker, 2026):
  * Copilot's RemoteMCPServer runtime currently sends ``Accept: application/json``
    WITHOUT ``text/event-stream`` (Agents Toolkit issue #15421). A strict Streamable
    HTTP server answers 406 and every call fails. We DO NOT gate on the Accept header
    and always return a JSON body, so this bug cannot break us.
  * Auth is ``OAuthPluginVault`` (Entra SSO) — the same vault the API-plugin action
    used; no new registration is required.
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

# MCP protocol revisions we understand. We echo the client's requested version when
# it is one of these, else advertise the default below.
_DEFAULT_PROTOCOL = "2025-06-18"
_KNOWN_PROTOCOLS = frozenset({"2025-06-18", "2025-03-26", "2024-11-05"})

_SERVER_INFO = {"name": "algenta-decision-engine", "version": "1.0.0"}

# The tool handlers are HTTP clients of the engine. When embedded in the API process
# we loop back to the local server so the handler's downstream call stays in-process
# (no external egress) and carries the caller's forwarded token.
_LOOPBACK_URL = os.environ.get("ALGENTA_MCP_LOOPBACK_URL", "http://localhost:8000").rstrip("/")


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    api_key = request.headers.get("x-api-key", "").strip()
    return api_key or None


def _product(request: Request) -> str | None:
    return request.headers.get("x-algenta-product", "").strip() or None


def _jsonrpc_error(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _jsonrpc_result(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


async def _handle_message(msg: dict[str, Any], request: Request) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns None for notifications (no response)."""
    from apps.mcp_server.client import request_overrides
    from apps.mcp_server.products import resolve_visible_tools
    from apps.mcp_server.registry import call_tool, get_tool_specs

    method = msg.get("method")
    id_ = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        params = msg.get("params") or {}
        requested = params.get("protocolVersion")
        protocol = requested if requested in _KNOWN_PROTOCOLS else _DEFAULT_PROTOCOL
        return _jsonrpc_result(
            id_,
            {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": _SERVER_INFO,
            },
        )

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None  # notification — no response

    if method == "ping":
        return _jsonrpc_result(id_, {})

    if method == "tools/list":
        allowed = resolve_visible_tools(_product(request))
        tools = [
            {
                "name": spec["name"],
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for spec in get_tool_specs(allowed)
        ]
        return _jsonrpc_result(id_, {"tools": tools})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments")
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(id_, -32602, "tools/call requires a string 'name'")
        if not isinstance(arguments, dict):
            arguments = {}
        allowed = resolve_visible_tools(_product(request))
        api_key = _bearer(request)
        try:
            with request_overrides(api_key=api_key, base_url=_LOOPBACK_URL):
                text = await call_tool(name, arguments, allowed)
        except Exception as exc:  # a tool failure is reported in-band, not as a transport error
            logger.error("mcp_streamable_tool_error", tool=name, error=str(exc))
            return _jsonrpc_result(
                id_,
                {
                    "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                    "isError": True,
                },
            )
        return _jsonrpc_result(
            id_,
            {"content": [{"type": "text", "text": text}], "isError": False},
        )

    if is_notification:
        return None
    return _jsonrpc_error(id_, -32601, f"Method not found: {method}")


def build_streamable_http_router() -> APIRouter:
    """FastAPI router exposing the MCP Streamable HTTP endpoint at ``/mcp``."""
    router = APIRouter(tags=["mcp"])

    @router.post("/mcp")
    async def mcp_post(request: Request) -> Response:  # noqa: ANN202 - FastAPI route
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400, content=_jsonrpc_error(None, -32700, "Parse error")
            )

        # OAuth challenge: a tool call needs the caller's identity. If none is present,
        # answer 401 + WWW-Authenticate so Copilot's OAuthPluginVault triggers the Entra
        # SSO sign-in/consent and RETRIES with a bearer token (the handshake — initialize
        # and tools/list — stays open so discovery works before consent).
        _msgs = body if isinstance(body, list) else [body]
        _wants_call = any(
            isinstance(m, dict) and m.get("method") == "tools/call" for m in _msgs
        )
        if _wants_call and not _bearer(request):
            _id = next(
                (m.get("id") for m in _msgs if isinstance(m, dict) and m.get("method") == "tools/call"),
                None,
            )
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="algenta", error="invalid_token"'},
                content=_jsonrpc_error(_id, -32001, "Authentication required: sign in to run Algenta tools."),
            )

        if isinstance(body, list):  # JSON-RPC batch
            responses: list[dict[str, Any]] = []
            for item in body:
                if isinstance(item, dict):
                    result = await _handle_message(item, request)
                    if result is not None:
                        responses.append(result)
            if not responses:  # all notifications
                return Response(status_code=202)
            return JSONResponse(content=responses)

        if isinstance(body, dict):
            result = await _handle_message(body, request)
            if result is None:  # notification
                return Response(status_code=202)
            return JSONResponse(content=result)

        return JSONResponse(status_code=400, content=_jsonrpc_error(None, -32600, "Invalid Request"))

    @router.get("/mcp")
    async def mcp_get() -> Response:  # noqa: ANN202
        # The optional server->client SSE stream is not implemented; this server is
        # request/response only. 405 is the spec-compliant answer for GET here.
        return Response(status_code=405)

    @router.delete("/mcp")
    async def mcp_delete() -> Response:  # noqa: ANN202
        # Stateless — there is no per-session state to tear down.
        return Response(status_code=204)

    return router
