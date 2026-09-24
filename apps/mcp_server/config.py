"""MCP server configuration — environment variables."""

from __future__ import annotations

import os
from typing import Final

from apps.platform_contract_constants import API_BASE_URL
from apps.platform_contract_constants import MCP_PROTOCOL_VERSION as _MCP_PROTOCOL_VERSION_LEGACY
from apps.privacy_policy import policy_from_environment

# serverInfo.version reported by the embedded MCP mount. Deliberately a literal (never a
# runtime import of algenta_mcp / importlib.metadata): the API image ships packages/mcp as
# source, not an installed distribution, and the mount must answer `initialize` even when the
# package tree is absent. The literal CANNOT drift from the published package version:
# scripts/bump_sdk_version.py rewrites this exact line in the same lockstep commit that bumps
# packages/mcp (added to its LOCKSTEP table), and
# tests/test_sdk_package_metadata.py::test_mcp_serverinfo_fallback_version_is_aligned fails CI
# if the two ever disagree. (The 1.0.4-era drift — embedded VERSION stuck while the package
# moved on — is exactly what that pair exists to prevent.)
VERSION: Final[str] = "1.0.29"

# The legacy Streamable HTTP handshake version this server negotiates for an `initialize`-opened
# connection (unchanged; re-exported from the generated platform contract so there is one source
# of truth — see apps/platform_contract_constants.py).
MCP_PROTOCOL_VERSION_LEGACY: Final[str] = _MCP_PROTOCOL_VERSION_LEGACY
# The modern per-request protocol era this server ALSO serves — with zero extra registration, via
# mcp>=2.0.0's built-in dual-era dispatch (MCP-Protocol-Version header / `_meta` envelope; see
# apps/mcp_server/transports/{http_sse,stdio}.py). Real and reachable today, not aspirational.
MCP_PROTOCOL_VERSION_MODERN: Final[str] = "2026-07-28"
# Both eras this deployment actually serves — this is the truthful list `get_contract` advertises
# (apps/mcp_server/tools/meta.py). MCP_PROTOCOL_VERSION_LEGACY stays first/default: it's still what
# a plain `initialize` handshake negotiates, and what the generated platform contract's singular
# `mcp_protocol_version` field (a much larger, cross-SDK generated surface — see
# apps/platform_contract_constants.py) continues to document unchanged.
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
    if policy_from_environment().disable_cloud:
        return ""
    return API_BASE_URL


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
    raise AttributeError(f"module 'apps.mcp_server.config' has no attribute {name!r}")


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
