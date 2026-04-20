"""Shared httpx client for MCP tool handlers."""
from __future__ import annotations

import contextvars
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import structlog

from . import config
from .errors import MCPUpstreamUnavailableError, UnsupportedMCPAuthConfigurationError

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


def _resolve_base_url() -> str:
    return (
        _BASE_URL_OVERRIDE.get()
        or os.environ.get("ALGENTA_BASE_URL", "").rstrip("/")
        or os.environ.get("DE_BASE_URL", "").rstrip("/")
        or config.BASE_URL
    ).rstrip("/")


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
            "ALGENTA_API_KEY environment variable is not set and no request API key was provided. "
            "Set ALGENTA_API_KEY or connect with Authorization: Bearer <key>."
        )
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": f"algenta-mcp/{config.VERSION}",
    }


async def api(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Make an authenticated request to the Algenta API."""
    base_url = _resolve_base_url()
    try:
        async with httpx.AsyncClient(timeout=config.TIMEOUT, headers=_headers()) as client:
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
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise MCPUpstreamUnavailableError(
                "Algenta API returned a temporary upstream failure for this MCP request.",
            ) from exc
        try:
            body = exc.response.text
        except Exception:
            body = exc.response.reason_phrase
        raise RuntimeError(f"API error {exc.response.status_code}: {body}") from exc

    return response.json()  # type: ignore[return-value]
