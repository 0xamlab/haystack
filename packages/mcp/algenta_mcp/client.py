"""Shared httpx client for MCP tool handlers."""

from __future__ import annotations

import contextvars
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import structlog

# Egress guard reused from the published SDK (single source of truth — no vendored security logic).
from decision_engine.privacy_profile import (
    cloud_disabled,
    is_algenta_owned_base_url,
    normalize_base_url,
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
# Whether this request context may fall back to the SERVER process's own credential. True for stdio /
# in-process use, where the environment IS the caller's configuration. HTTP transports set it False:
# an HTTP caller authenticates as itself or not at all. Without that, a keyless HTTP request reached
# _resolve_api_key() with no override and picked up ALGENTA_API_KEY / DE_API_KEY from the environment
# (docker-compose injects one into the api container), i.e. ran tools with the deployment's credential.
_AMBIENT_KEY_ALLOWED: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "algenta_mcp_ambient_key_allowed",
    default=True,
)


def _resolve_api_key() -> str:
    override = _API_KEY_OVERRIDE.get()
    if override:
        return override
    if not _AMBIENT_KEY_ALLOWED.get():
        # Deliberately empty rather than the process credential: _headers() then raises the
        # unsupported-auth error, which the transport serializes as a tool error.
        return ""
    return (
        os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "") or config.API_KEY
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
    try:
        normalized = normalize_base_url(base_url, component="Algenta MCP")
    except ValueError as exc:
        raise MCPPrivacyConfigurationError(
            "MCP downstream base URL must be a valid absolute URL."
        ) from exc
    if cloud_disabled() and is_algenta_owned_base_url(normalized):
        raise MCPPrivacyConfigurationError(
            "MCP private profiles cannot target Algenta-owned cloud URLs. "
            "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL "
            "or a request base URL for your self-hosted deployment."
        )
    return normalized


def _resolve_base_url() -> str:
    return _validated_base_url(_configured_base_url())


def resolve_base_url() -> str:
    return _resolve_base_url()


@contextmanager
def request_overrides(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    allow_ambient_key: bool = True,
) -> Iterator[None]:
    """Temporarily override MCP downstream auth/base URL for the current request context.

    ``allow_ambient_key=False`` additionally forbids falling back to the server process's
    ``ALGENTA_API_KEY`` / ``DE_API_KEY``; pass it from any transport where the caller is a remote HTTP
    client, so a request without its own credential fails instead of borrowing the deployment's.
    """
    key_token = _API_KEY_OVERRIDE.set(api_key) if api_key else None
    base_token = _BASE_URL_OVERRIDE.set(base_url.rstrip("/")) if base_url else None
    ambient_token = None if allow_ambient_key else _AMBIENT_KEY_ALLOWED.set(False)
    try:
        yield
    finally:
        if ambient_token is not None:
            _AMBIENT_KEY_ALLOWED.reset(ambient_token)
        if base_token is not None:
            _BASE_URL_OVERRIDE.reset(base_token)
        if key_token is not None:
            _API_KEY_OVERRIDE.reset(key_token)


def _headers() -> dict[str, str]:
    api_key = _resolve_api_key()
    if not api_key:
        raise UnsupportedMCPAuthConfigurationError(
            "ALGENTA_API_KEY is not set. "
            "Introspection (initialize/tools/list) needs no credentials, but executing "
            "tools requires a free community login — device registration at algenta.ai "
            "(free): run `algenta login` or create a key at "
            "https://app.algenta.ai/dashboard/api-keys, then set ALGENTA_API_KEY "
            "(or connect with Authorization: Bearer <key>)."
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


# Defense-in-depth: an error message interpolates the verbatim upstream body, which is also logged
# (str(exc)) and returned to the MCP client. A misbehaving upstream that reflects the request (or a
# minted key in a 4xx body) must never turn our error into a credential leak — scrub key material.
_SECRET_RE = re.compile(r"de_(?:live|test)_[A-Za-z0-9._\-]{6,}|[Bb]earer\s+[A-Za-z0-9._\-]{6,}")


def _redact_secrets(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text)


def _api_error_from_status_payload(status_code: int, payload: Any) -> MCPAPIError:
    error_payload = _extract_structured_error_payload(payload) or {}
    error_code = str(error_payload.get("code") or "api_error").strip() or "api_error"
    details_raw = error_payload.get("details")
    details = (
        [item for item in details_raw if isinstance(item, dict)]
        if isinstance(details_raw, list)
        else None
    )
    message = f"API error {status_code}: {_redact_secrets(_serialize_payload(payload))}"
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
