"""Shared operator config resolution for repo-shipped verification scripts."""

from __future__ import annotations

import os
from collections.abc import Mapping

from apps.operator_http.privacy import operator_private_profile, validate_operator_api_base_url

DEFAULT_LOCAL_OPERATOR_BASE_URL = "http://localhost:8000"
API_KEY_ENV_VARS = ("ALGENTA_API_KEY", "DE_API_KEY")
BASE_URL_ENV_VARS = ("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL")


def resolve_operator_api_key(
    explicit_value: str = "",
    env: Mapping[str, str] | None = None,
) -> str:
    """Return an explicitly configured operator API key or an empty string."""
    value = explicit_value.strip()
    if value:
        return value

    mapping = os.environ if env is None else env
    for key in API_KEY_ENV_VARS:
        candidate = mapping.get(key, "").strip()
        if candidate:
            return candidate
    return ""


def resolve_operator_base_url(
    explicit_value: str = "",
    env: Mapping[str, str] | None = None,
    *,
    strip_trailing_slash: bool = False,
    surface: str = "operator script",
) -> str:
    """Return the configured operator base URL under the shared privacy contract."""
    mapping = os.environ if env is None else env
    value = explicit_value.strip()
    configured = False
    if value:
        configured = True
    if not value:
        for key in BASE_URL_ENV_VARS:
            candidate = mapping.get(key, "").strip()
            if candidate:
                value = candidate
                configured = True
                break
    if operator_private_profile(mapping) and not configured:
        raise ValueError(
            f"{surface} private profiles require an explicit self-hosted API origin. "
            "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
        )
    if not value:
        value = DEFAULT_LOCAL_OPERATOR_BASE_URL
    value = validate_operator_api_base_url(
        value,
        surface=surface,
        env=mapping,
    )
    if strip_trailing_slash:
        return value.rstrip("/")
    return value
