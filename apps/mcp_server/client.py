"""Shared httpx client for MCP tool handlers."""

from __future__ import annotations

import contextvars
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import structlog

from apps.privacy_policy import (
    PrivacyConfigurationError,
    is_algenta_owned_destination,
    parse_egress_destination,
    policy_from_environment,
)

from . import config
from .errors import (
    MCPAPIError,
    MCPPrivacyConfigurationError,
    MCPUpstreamUnavailableError,
    UnsupportedMCPAuthConfigurationError,
)

logger = structlog.get_logger(__name__)

_API_KEY_OVERRIDE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "algenta_mcp_api_key_override",
    default=None,
)
_BASE_URL_OVERRIDE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "algenta_mcp_base_url_override",
    default=None,
)


def _resolve_api_key() -> str:
    return (
        _API_KEY_OVERRIDE.get()
        or os.environ.get("ALGENTA_API_KEY", "")
        or os.environ.get("DE_API_KEY", "")
        or config.API_KEY
    )


def _configured_base_url() -> str:
    return (
        _BASE_URL_OVERRIDE.get()
        or os.environ.get("ALGENTA_BASE_URL", "").rstrip("/")
        or os.environ.get("DE_BASE_URL", "").rstrip("/")
        or os.environ.get("ALGENTA_API_URL", "").rstrip("/")
        or config.BASE_URL
    ).rstrip("/")


def _validated_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    policy = policy_from_environment()
    try:
        destination = parse_egress_destination(normalized)
    except PrivacyConfigurationError as exc:
        raise MCPPrivacyConfigurationError(
            "MCP downstream base URL must be a valid absolute URL."
        ) from exc
    if policy.disable_cloud and is_algenta_owned_destination(destination.host):
        raise MCPPrivacyConfigurationError(
            "MCP private profiles cannot target Codna-owned cloud URLs. "
            "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL "
            "or a request base URL for your self-hosted deployment."
        )
    return normalized


def _resolve_base_url() -> str:
    return _validated_base_url(_configured_base_url())


def resolve_base_url() -> str:
    return _resolve_base_url()


@contextmanager
def request_overrides(*, api_key: str | None = None, base_url: str | None = None) -> Iterator[None]:
    """Temporarily override MCP downstream auth/base URL for the current request context."""
    key_token = _API_KEY_OVERRIDE.set(api_key) if api_key else None
    base_token = _BASE_URL_OVERRIDE.set(base_url.rstrip("/")) if base_url else None
    try:
        yield
    finally:
        if base_token is not None:
            _BASE_URL_OVERRIDE.reset(base_token)
        if key_token is not None:
            _API_KEY_OVERRIDE.reset(key_token)


def _headers() -> dict[str, str]:
    api_key = _resolve_api_key()
    if not api_key:
        raise UnsupportedMCPAuthConfigurationError(
            "ALGENTA_API_KEY / DE_API_KEY environment variables are not set "
            "and no request API key was provided. "
            "Set ALGENTA_API_KEY / DE_API_KEY or connect with Authorization: Bearer <key>."
        )
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": f"algenta-mcp/{config.VERSION}",
    }


def _serialize_payload(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return str(payload)


def _extract_structured_error_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    top_level_error = payload.get("error")
    if isinstance(top_level_error, dict):
        return top_level_error
    detail = payload.get("detail")
    if isinstance(detail, dict):
        nested_error = detail.get("error")
        if isinstance(nested_error, dict):
            return nested_error
        if "code" in detail and "message" in detail:
            return detail
    return None


def _api_error_from_status_payload(status_code: int, payload: Any) -> MCPAPIError:
    error_payload = _extract_structured_error_payload(payload) or {}
    error_code = str(error_payload.get("code") or "api_error").strip() or "api_error"
    details_raw = error_payload.get("details")
    details = (
        [item for item in details_raw if isinstance(item, dict)]
        if isinstance(details_raw, list)
        else None
    )
    message = f"API error {status_code}: {_serialize_payload(payload)}"
    return MCPAPIError(
        error_code=error_code,
        message=message,
        status_code=status_code,
        details=details,
        payload=payload,
    )


async def api(
    method: str,
    path: str,
    *,
    timeout: float | None = None,
    **kwargs: Any,
) -> Any:
    """Make an authenticated request to the Algenta API."""
    status_code, payload = await api_with_status(
        method,
        path,
        timeout=timeout,
        **kwargs,
    )
    if status_code >= 400:
        raise _api_error_from_status_payload(status_code, payload)
    return payload


async def api_with_status(
    method: str,
    path: str,
    *,
    timeout: float | None = None,
    **kwargs: Any,
) -> tuple[int, Any]:
    """Make an authenticated request and return the HTTP status plus decoded payload."""
    base_url = _resolve_base_url()
    request_timeout = config.TIMEOUT if timeout is None else timeout
    try:
        async with httpx.AsyncClient(timeout=request_timeout, headers=_headers()) as client:
            response = await getattr(client, method.lower())(f"{base_url}{path}", **kwargs)
    except httpx.TimeoutException as exc:
        raise MCPUpstreamUnavailableError(
            "Algenta API timed out while handling this MCP request.",
        ) from exc
    except httpx.TransportError as exc:
        raise MCPUpstreamUnavailableError(
            "Algenta API was unavailable while handling this MCP request.",
        ) from exc

    try:
        payload = response.json()
    except Exception:
        payload = response.text
    if response.status_code >= 500 and _extract_structured_error_payload(payload) is None:
        raise MCPUpstreamUnavailableError(
            "Algenta API returned a temporary upstream failure for this MCP request.",
        )
    return response.status_code, payload
