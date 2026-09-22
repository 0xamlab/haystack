"""MCP server configuration — environment variables."""

from __future__ import annotations

import os
from typing import Final

# Egress/privacy reused from the published SDK (single source of truth — no vendored logic).
from decision_engine.privacy_profile import cloud_disabled

def _resolve_version() -> str:
    # The installed distribution is authoritative; the fallback literal only serves source
    # checkouts (tests, local runs) and is kept in lockstep with pyproject by
    # tests/test_sdk_package_metadata.py.
    try:
        from importlib.metadata import version

        return version("algenta-mcp")
    except Exception:  # PackageNotFoundError or a broken metadata store — never fatal at import
        return _FALLBACK_VERSION


_FALLBACK_VERSION: Final[str] = "1.0.25"
VERSION: Final[str] = _resolve_version()
# Public default API base URL (same value the SDK uses); only used when nothing is configured and
# cloud is not disabled.
_DEFAULT_API_BASE_URL: Final[str] = "https://api.algenta.ai"

# The legacy Streamable HTTP handshake version this server negotiates for an `initialize`-opened
# connection (matches the embedded copy's apps.platform_contract_constants.MCP_PROTOCOL_VERSION;
# this package is deliberately decoupled from the monorepo, so it is a literal here, not an import).
MCP_PROTOCOL_VERSION_LEGACY: Final[str] = "2025-11-25"
# The modern per-request protocol era this server ALSO serves — with zero extra registration, via
# mcp>=2.0.0's built-in dual-era dispatch (MCP-Protocol-Version header / `_meta` envelope; see
# algenta_mcp/transports/{http_sse,stdio}.py). Real and reachable today, not aspirational.
MCP_PROTOCOL_VERSION_MODERN: Final[str] = "2026-07-28"
# Both eras this deployment actually serves. MCP_PROTOCOL_VERSION_LEGACY stays first/default: it's
# still what a plain `initialize` handshake negotiates.
MCP_PROTOCOL_VERSIONS_SUPPORTED: Final[tuple[str, ...]] = (
    MCP_PROTOCOL_VERSION_LEGACY,
    MCP_PROTOCOL_VERSION_MODERN,
)

for _legacy_dynamic_name in (
    "BASE_URL",
    "API_KEY",
    "TIMEOUT",
    "CONNECT_TIMEOUT",
    "HOST",
    "PORT",
):
    globals().pop(_legacy_dynamic_name, None)


def _env(key: str) -> str:
    return (os.environ.get(key) or "").strip()


def resolve_base_url() -> str:
    configured_base_url = (
        _env("ALGENTA_BASE_URL") or _env("DE_BASE_URL") or _env("ALGENTA_API_URL")
    ).rstrip("/")
    if configured_base_url:
        return configured_base_url
    if cloud_disabled():
        return ""
    return _DEFAULT_API_BASE_URL


def resolve_api_key() -> str:
    return _env("ALGENTA_API_KEY") or _env("DE_API_KEY")


def resolve_timeout() -> float:
    return float(_env("ALGENTA_MCP_TIMEOUT") or "60")


def resolve_connect_timeout() -> float:
    return float(_env("ALGENTA_MCP_CONNECT_TIMEOUT") or _env("ALGENTA_MCP_TIMEOUT") or "120")


def resolve_host() -> str:
    return _env("ALGENTA_MCP_HOST") or "127.0.0.1"


def resolve_port() -> int:
    return int(_env("ALGENTA_MCP_PORT") or "8001")


def __getattr__(name: str):
    if name == "BASE_URL":
        return resolve_base_url()
    if name == "API_KEY":
        return resolve_api_key()
    if name == "TIMEOUT":
        return resolve_timeout()
    if name == "CONNECT_TIMEOUT":
        return resolve_connect_timeout()
    if name == "HOST":
        return resolve_host()
    if name == "PORT":
        return resolve_port()
    if name == "VERSION":
        return VERSION
    raise AttributeError(f"module 'algenta_mcp.config' has no attribute {name!r}")


__all__ = [
    "API_KEY",
    "BASE_URL",
    "CONNECT_TIMEOUT",
    "HOST",
    "MCP_PROTOCOL_VERSION_LEGACY",
    "MCP_PROTOCOL_VERSION_MODERN",
    "MCP_PROTOCOL_VERSIONS_SUPPORTED",
    "PORT",
    "TIMEOUT",
    "VERSION",
    "resolve_api_key",
    "resolve_base_url",
    "resolve_connect_timeout",
    "resolve_host",
    "resolve_port",
    "resolve_timeout",
]
