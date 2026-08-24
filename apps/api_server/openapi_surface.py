"""OpenAPI server metadata helpers for cloud-managed and private profiles."""

from __future__ import annotations

import os

from apps.api_server.config import get_settings
from apps.api_server.services.public_url_policy import (
    PublicUrlConfigurationError,
    resolve_configured_api_public_base_url,
)
from apps.operator_http.privacy import validate_operator_api_base_url
from apps.platform_contract_constants import API_BASE_URL, MCP_ENDPOINT


def _validated_configured_api_base_url() -> str:
    config = get_settings()
    try:
        configured_api_base_url = resolve_configured_api_public_base_url(
            settings_obj=config,
            env=os.environ,
        )
    except PublicUrlConfigurationError as exc:
        if exc.code == "private_profile_public_url_forbidden":
            raise ValueError(
                f"OpenAPI surface {exc}"
            ) from exc
        raise
    if configured_api_base_url is None:
        return ""
    return validate_operator_api_base_url(
        configured_api_base_url,
        surface="OpenAPI surface",
        env=os.environ,
    ).rstrip("/")


def validate_openapi_surface_configuration() -> None:
    _validated_configured_api_base_url()


def openapi_server_url() -> str:
    policy = get_settings().privacy_policy
    configured_api_base_url = _validated_configured_api_base_url()
    if policy.private_profile or policy.disable_cloud:
        return configured_api_base_url or "/"
    return configured_api_base_url or API_BASE_URL


def openapi_mcp_endpoint(server_url: str | None = None) -> str:
    resolved_server_url = server_url or openapi_server_url()
    if resolved_server_url == API_BASE_URL:
        return MCP_ENDPOINT
    if resolved_server_url == "/":
        return "/mcp"
    return f"{resolved_server_url.rstrip('/')}/mcp"


def apply_openapi_surface(schema: dict[str, object]) -> dict[str, object]:
    server_url = openapi_server_url()
    schema["servers"] = [{"url": server_url}]
    schema["x-canonical-mcp-endpoint"] = openapi_mcp_endpoint(server_url)
    paths = schema.setdefault("paths", {})
    if isinstance(paths, dict) and "/mcp" not in paths:
        paths["/mcp"] = {
            "get": {
                "tags": ["MCP"],
                "operationId": "stream_mcp_events",
                "summary": "MCP Streamable HTTP event stream",
                "responses": {
                    "200": {"description": "MCP server event stream."},
                    "405": {"description": "Standalone event stream is not enabled."},
                },
            },
            "post": {
                "tags": ["MCP"],
                "operationId": "send_mcp_message",
                "summary": "Send an MCP Streamable HTTP message",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "responses": {
                    "200": {"description": "MCP JSON-RPC response."},
                    "202": {"description": "MCP notification accepted."},
                },
            },
            "delete": {
                "tags": ["MCP"],
                "operationId": "terminate_mcp_session",
                "summary": "Terminate an MCP Streamable HTTP session",
                "responses": {
                    "200": {"description": "MCP session terminated."},
                    "404": {"description": "MCP session not found."},
                    "405": {"description": "Session termination is not enabled."},
                },
            },
        }
    if isinstance(paths, dict):
        # /mcp/tools is a real FastAPI route whenever the MCP router mounts, but the router is an
        # optional mount (it is skipped when the mcp stack cannot load on a given instance), so a
        # regeneration against such an instance silently drops it from the published spec — even
        # though every real deployment serves it and the docs promise it is always available
        # without auth. Hand-declare it (same shape FastAPI generates for the route) so the
        # canonical schema stays complete by construction. A mounted router's own entry wins.
        paths.setdefault(
            "/mcp/tools",
            {
                "get": {
                    "tags": ["MCP"],
                    "summary": "List available MCP tools",
                    "operationId": "list_tools_mcp_tools_get",
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": {"application/json": {"schema": {}}},
                        }
                    },
                }
            },
        )
        # The deprecated HTTP+SSE pair requires a key on every request (unlike streamable /mcp, which
        # leaves discovery open and challenges only tools/call). These operations are hand-declared
        # because the routes are raw ASGI, so their security has to be declared here too — otherwise the
        # published spec keeps advertising a transport that can execute tools as unauthenticated.
        paths.setdefault(
            "/mcp/sse",
            {
                "get": {
                    "tags": ["MCP"],
                    "operationId": "stream_legacy_mcp_events",
                    "summary": "Legacy MCP HTTP+SSE connection",
                    "deprecated": True,
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {"description": "Legacy MCP SSE stream."},
                        "401": {"description": "Authentication required."},
                    },
                }
            },
        )
        paths.setdefault(
            "/mcp/messages",
            {
                "post": {
                    "tags": ["MCP"],
                    "operationId": "send_legacy_mcp_message",
                    "summary": "Legacy MCP HTTP+SSE message",
                    "deprecated": True,
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "responses": {
                        "202": {"description": "Legacy MCP message accepted."},
                        "401": {"description": "Authentication required."},
                    },
                }
            },
        )
    return schema
