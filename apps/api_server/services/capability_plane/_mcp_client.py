"""Minimal, egress-guarded MCP client for external Model Context Protocol servers.

This makes Algenta an MCP *client*: it connects to a customer-registered external MCP server over
the Streamable HTTP transport, lists its tools, and calls them on the agent's behalf — so an external
server's tools become first-class capabilities in the unified catalog.

Why a hand-rolled client instead of the `mcp` library: every outbound byte MUST flow through Algenta's
egress guard (the deployment's fail-closed privacy policy), so a self-hosted/air-gapped engine never
phones home to an un-allowlisted host. The `mcp` library opens its own transport and would bypass that
guard entirely. We therefore speak the protocol's JSON-RPC directly over ``egress_guard.async_http_request``.

Transport: MCP "Streamable HTTP" — JSON-RPC 2.0 POSTed to a single endpoint; the server replies with
either ``application/json`` or a one-shot ``text/event-stream`` (SSE) frame. Redirects are never
followed (SSRF hardening) and the destination is enforced on every request.
"""
from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    EgressPolicyDeniedError,
    async_http_request,
)

# A recent protocol revision; servers negotiate down via the initialize result if they are older.
_PROTOCOL_VERSION = "2025-06-18"
_SURFACE = "capability_plane.mcp_provider"
_SERVICE = "mcp-provider"
_DEFAULT_TIMEOUT_S = 30.0
_CLIENT_INFO = {"name": "algenta-capability-plane", "version": "1"}
# Hard ceilings against a hostile/oversized external server.
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 8 MiB per JSON-RPC response
_MAX_TOOL_PAGES = 50  # bound tools/list pagination
# Client construction stays inside egress_guard (the approved egress wrapper); we only pass the
# SSRF-safe options. follow_redirects=False: a redirect could escape the egress-enforced destination.
_CLIENT_KWARGS = {"follow_redirects": False, "trust_env": False}


def _assert_safe_destination(server_url: str) -> None:
    """Defense-in-depth SSRF guard for the caller-influenced MCP server URL.

    Blocks link-local / cloud-metadata (169.254.0.0/16, fe80::/10) and other never-legitimate
    targets (multicast / reserved / unspecified) regardless of the egress allowlist, since a
    wildcard-allowlisted or attacker-DNS-controlled host could otherwise be pointed at the cloud
    metadata endpoint. Loopback/private hosts remain governed by the operator's egress allowlist
    (so a legitimate internal MCP server still works). This is a check-time DNS resolution — the
    egress guard performs the policy decision separately.
    """
    host = (urlparse(server_url).hostname or "").strip("[]")
    if not host:
        return
    addresses: list[str]
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError, OSError):
            return
        addresses = list({info[4][0] for info in infos if info and info[4]})
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise MCPClientError(
                "mcp_blocked_destination",
                "The MCP server resolves to a blocked (link-local/metadata) address.",
            )


class MCPClientError(RuntimeError):
    """A typed failure talking to an external MCP server (never leaks raw response bodies)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def build_auth_headers(auth: dict[str, Any] | None) -> dict[str, str]:
    """Translate a binding's ``auth`` config into request headers. Never logs the secret."""
    if not isinstance(auth, dict):
        return {}
    auth_type = str(auth.get("type") or "none").strip().lower()
    headers: dict[str, str] = {}
    # Always honor explicit custom headers first (e.g. a gateway key).
    custom = auth.get("headers")
    if isinstance(custom, dict):
        headers.update({str(k): str(v) for k, v in custom.items()})
    token = auth.get("token") or auth.get("api_key") or auth.get("key")
    if auth_type in {"bearer", "oauth", "token"} and token:
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type in {"api_key", "apikey"} and token:
        header_name = str(auth.get("header") or "X-API-Key")
        headers[header_name] = str(token)
    return headers


def _parse_rpc_response(resp: httpx.Response, *, rpc_id: int) -> dict[str, Any]:
    """Return the JSON-RPC message from a JSON or SSE (text/event-stream) response."""
    if resp.status_code >= 400:
        raise MCPClientError(
            "mcp_http_error",
            f"MCP server returned HTTP {resp.status_code}.",
        )
    declared = resp.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _MAX_RESPONSE_BYTES:
        raise MCPClientError("mcp_response_too_large", "MCP server response exceeded the size limit.")
    if len(resp.content) > _MAX_RESPONSE_BYTES:
        raise MCPClientError("mcp_response_too_large", "MCP server response exceeded the size limit.")
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        message: dict[str, Any] | None = None
        for line in resp.text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                candidate = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and candidate.get("id") == rpc_id:
                message = candidate
                break
            if isinstance(candidate, dict) and ("result" in candidate or "error" in candidate):
                message = candidate
        if message is None:
            raise MCPClientError("mcp_invalid_response", "No JSON-RPC message in the MCP SSE stream.")
        return message
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        raise MCPClientError("mcp_invalid_response", "MCP server response was not valid JSON.")
    if not isinstance(payload, dict):
        raise MCPClientError("mcp_invalid_response", "MCP server response was not a JSON object.")
    return payload


async def _rpc(
    client: Any,
    server_url: str,
    *,
    method: str,
    params: dict[str, Any] | None,
    rpc_id: int,
    headers: dict[str, str],
    audit: EgressAuditContext | None,
    timeout: float,
    request_id: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        body["params"] = params
    resp = await async_http_request(
        method="POST",
        url=server_url,
        surface=_SURFACE,
        service_name=_SERVICE,
        # A customer-registered MCP server is an explicitly-configured destination (like a connector),
        # so it is allowlist-eligible (customer_connector class) rather than undeclared_public.
        explicit_configured=True,
        audit_context=audit,
        client=client,
        client_kwargs=_CLIENT_KWARGS,
        headers=headers,
        json=body,
        timeout=timeout,
    )
    message = _parse_rpc_response(resp, rpc_id=rpc_id)
    if isinstance(message.get("error"), dict):
        err = message["error"]
        raise MCPClientError(
            "mcp_tool_error",
            f"MCP server error {err.get('code')}: {str(err.get('message') or '')[:300]}",
        )
    result = message.get("result")
    if not isinstance(result, dict):
        raise MCPClientError("mcp_invalid_response", f"MCP '{method}' returned no result object.")
    # Carry the session id forward if the server issued one (header capture is done by the caller).
    return result


async def _notify(
    client: Any,
    server_url: str,
    *,
    method: str,
    headers: dict[str, str],
    audit: EgressAuditContext | None,
    timeout: float,
) -> None:
    body = {"jsonrpc": "2.0", "method": method}
    await async_http_request(
        method="POST",
        url=server_url,
        surface=_SURFACE,
        service_name=_SERVICE,
        # A customer-registered MCP server is an explicitly-configured destination (like a connector),
        # so it is allowlist-eligible (customer_connector class) rather than undeclared_public.
        explicit_configured=True,
        audit_context=audit,
        client=client,
        client_kwargs=_CLIENT_KWARGS,
        headers=headers,
        json=body,
        timeout=timeout,
    )


def _base_headers(extra: dict[str, str]) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    headers.update(extra)
    return headers


async def _handshake(
    client: Any,
    server_url: str,
    *,
    auth_headers: dict[str, str],
    audit: EgressAuditContext | None,
    timeout: float,
    request_id: str | None,
) -> dict[str, str]:
    """initialize + notifications/initialized. Returns the session headers to reuse for later calls."""
    init_headers = _base_headers(auth_headers)
    resp = await async_http_request(
        method="POST",
        url=server_url,
        surface=_SURFACE,
        service_name=_SERVICE,
        # A customer-registered MCP server is an explicitly-configured destination (like a connector),
        # so it is allowlist-eligible (customer_connector class) rather than undeclared_public.
        explicit_configured=True,
        audit_context=audit,
        client=client,
        client_kwargs=_CLIENT_KWARGS,
        headers=init_headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            },
        },
        timeout=timeout,
    )
    init_message = _parse_rpc_response(resp, rpc_id=1)
    if isinstance(init_message.get("error"), dict):
        err = init_message["error"]
        raise MCPClientError(
            "mcp_initialize_error",
            f"MCP initialize was rejected: {str(err.get('message') or '')[:200]}",
        )
    init_result = init_message.get("result")
    if not isinstance(init_result, dict):
        raise MCPClientError("mcp_invalid_response", "MCP initialize returned no result object.")
    negotiated = init_result.get("protocolVersion")
    session_headers = dict(auth_headers)
    # Honor the server's negotiated protocol version; fall back to ours only if it omits one.
    session_headers["MCP-Protocol-Version"] = (
        negotiated if isinstance(negotiated, str) and negotiated else _PROTOCOL_VERSION
    )
    session_id = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
    if session_id:
        session_headers["Mcp-Session-Id"] = session_id
    await _notify(
        client,
        server_url,
        method="notifications/initialized",
        headers=_base_headers(session_headers),
        audit=audit,
        timeout=timeout,
    )
    return session_headers


async def list_remote_tools(
    server_url: str,
    *,
    auth: dict[str, Any] | None = None,
    audit: EgressAuditContext | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
    request_id: str | None = None,
    client: Any = None,
) -> list[dict[str, Any]]:
    """Connect to an external MCP server and return its advertised tools (list of {name, description, inputSchema}).

    When ``client`` is None the egress wrapper builds + manages an httpx client per call (the MCP
    session is carried in the Mcp-Session-Id header, not the connection). Tests inject a client.
    """
    _assert_safe_destination(server_url)
    tools: list[dict[str, Any]] = []
    try:
        session_headers = _base_headers(
            await _handshake(
                client, server_url, auth_headers=build_auth_headers(auth), audit=audit, timeout=timeout, request_id=request_id
            )
        )
        cursor: str | None = None
        for _ in range(_MAX_TOOL_PAGES):  # follow nextCursor pagination, bounded against a hostile server
            params: dict[str, Any] = {"cursor": cursor} if cursor else {}
            result = await _rpc(
                client, server_url, method="tools/list", params=params, rpc_id=2,
                headers=session_headers, audit=audit, timeout=timeout, request_id=request_id,
            )
            page = result.get("tools")
            if not isinstance(page, list):
                raise MCPClientError("mcp_invalid_response", "tools/list did not return a tools array.")
            tools.extend(t for t in page if isinstance(t, dict) and isinstance(t.get("name"), str))
            cursor = result.get("nextCursor")
            if not (isinstance(cursor, str) and cursor):
                break
    except httpx.HTTPError:
        raise MCPClientError("mcp_transport_error", "Could not reach the MCP server.")
    return tools


async def call_remote_tool(
    server_url: str,
    *,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    auth: dict[str, Any] | None = None,
    audit: EgressAuditContext | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
    request_id: str | None = None,
    client: Any = None,
) -> dict[str, Any]:
    """Invoke a tool on an external MCP server and return its result object ({content, isError, ...})."""
    _assert_safe_destination(server_url)
    try:
        session_headers = await _handshake(
            client, server_url, auth_headers=build_auth_headers(auth), audit=audit, timeout=timeout, request_id=request_id
        )
        result = await _rpc(
            client,
            server_url,
            method="tools/call",
            params={"name": tool_name, "arguments": dict(arguments or {})},
            rpc_id=3,
            headers=_base_headers(session_headers),
            audit=audit,
            timeout=timeout,
            request_id=request_id,
        )
    except httpx.HTTPError:
        raise MCPClientError("mcp_transport_error", "Could not reach the MCP server.")
    return result
