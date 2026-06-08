"""MCP server configuration — environment variables."""

from __future__ import annotations

import os
from typing import Final

from apps.privacy_policy import policy_from_environment
from apps.platform_contract_constants import API_BASE_URL

VERSION: Final[str] = "1.0.0"

for _legacy_dynamic_name in ("BASE_URL", "API_KEY", "TIMEOUT", "CONNECT_TIMEOUT", "PORT"):
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
    if name == "PORT":
        return resolve_port()
    if name == "VERSION":
        return VERSION
    raise AttributeError(f"module 'apps.mcp_server.config' has no attribute {name!r}")


__all__ = [
    "API_KEY",
    "BASE_URL",
    "CONNECT_TIMEOUT",
    "PORT",
    "TIMEOUT",
    "VERSION",
    "resolve_api_key",
    "resolve_base_url",
    "resolve_connect_timeout",
    "resolve_port",
    "resolve_timeout",
]
