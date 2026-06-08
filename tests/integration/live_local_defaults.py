"""Shared local defaults for legacy live integration runners.

These values are only for repo-local test harnesses that target a local server.
They are intentionally fake placeholders and must never be treated as bundled
service credentials.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_LOCAL_LIVE_API_KEY = "de_live_testonlyplaceholderdonotuse1234567890abcd"
DEFAULT_LOCAL_LIVE_BASE_URL = "http://localhost:8000"


def resolve_local_live_api_key(env: Mapping[str, str] | None = None) -> str:
    """Return the configured local live-test API key or the shared fake placeholder."""
    mapping = env or os.environ
    value = mapping.get("DE_API_KEY", "").strip()
    if value:
        return value
    return DEFAULT_LOCAL_LIVE_API_KEY


def has_configured_local_live_api_key(env: Mapping[str, str] | None = None) -> bool:
    """Return whether a real local live-test API key was explicitly configured."""
    return resolve_local_live_api_key(env) != DEFAULT_LOCAL_LIVE_API_KEY


def configured_local_live_base_url(env: Mapping[str, str] | None = None) -> str | None:
    """Return the explicitly configured local live-test base URL, if any."""
    mapping = env or os.environ
    value = mapping.get("DE_BASE_URL", "").strip()
    if value:
        return value
    return None


def resolve_local_live_base_url(
    env: Mapping[str, str] | None = None,
    *,
    strip_trailing_slash: bool = False,
) -> str:
    """Return the configured local live-test base URL or the shared localhost default."""
    value = configured_local_live_base_url(env) or DEFAULT_LOCAL_LIVE_BASE_URL
    if strip_trailing_slash:
        return value.rstrip("/")
    return value
