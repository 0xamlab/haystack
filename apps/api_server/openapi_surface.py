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
        return "/mcp/sse"
    return f"{resolved_server_url.rstrip('/')}/mcp/sse"


def apply_openapi_surface(schema: dict[str, object]) -> dict[str, object]:
    server_url = openapi_server_url()
    schema["servers"] = [{"url": server_url}]
    schema["x-canonical-mcp-endpoint"] = openapi_mcp_endpoint(server_url)
    return schema
