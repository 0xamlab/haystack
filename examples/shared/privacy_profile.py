"""
Shared example privacy-profile helpers.

These helpers default example clients to the Cloud Managed base URL only when
the active deployment profile allows it. In `self_hosted` and `air_gapped`,
examples must point at an explicit self-hosted base URL and use the API key
provisioned by the self-hosted operator deployment. `ALGENTA_*` env vars stay
canonical, while legacy `DE_*` env vars and `ALGENTA_API_URL` remain accepted
for compatibility.
Private profiles fail closed and do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from decision_engine.privacy_profile import resolve_client_base_url


def _env(mapping: Mapping[str, str], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def resolve_example_api_base_url(
    *,
    component: str,
    default_base_url: str = "https://api.algenta.ai",
    env: Mapping[str, str] | None = None,
) -> str:
    mapping = os.environ if env is None else env
    explicit_base_url = (
        _env(mapping, "ALGENTA_BASE_URL")
        or _env(mapping, "DE_BASE_URL")
        or _env(mapping, "ALGENTA_API_URL")
        or default_base_url
    )
    return resolve_client_base_url(
        explicit_base_url=explicit_base_url,
        component=component,
        env=mapping,
    )


def resolve_example_api_key(
    *,
    component: str,
    env: Mapping[str, str] | None = None,
) -> str:
    mapping = os.environ if env is None else env
    api_key = _env(mapping, "ALGENTA_API_KEY") or _env(mapping, "DE_API_KEY")
    if api_key is None:
        raise ValueError(
            f"{component} requires ALGENTA_API_KEY or DE_API_KEY to be set.",
        )
    return api_key


__all__ = ["resolve_example_api_base_url", "resolve_example_api_key"]
