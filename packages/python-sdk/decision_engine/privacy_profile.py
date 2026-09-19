# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlparse

from ._contract import ALGENTA_OWNED_HOSTS, ALGENTA_OWNED_SUFFIXES, DEFAULT_BASE_URL

_PRIVATE_DEPLOYMENT_MODES = {"self_hosted", "air_gapped"}
_ALGENTA_OWNED_HOSTS = frozenset(ALGENTA_OWNED_HOSTS)
_ALGENTA_OWNED_SUFFIXES = tuple(ALGENTA_OWNED_SUFFIXES)
_DEFAULT_CONSOLE_BASE_URL = "https://app.algenta.ai"
_CONSOLE_BASE_URL_ENV_KEYS = ("ALGENTA_APP_BASE_URL", "APP_BASE_URL", "DE_APP_BASE_URL")


def _env(mapping: Mapping[str, str], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _normalized_deployment_mode(mapping: Mapping[str, str]) -> str:
    return (_env(mapping, "ALGENTA_DEPLOYMENT_MODE") or "saas").lower()


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        "ALGENTA_DISABLE_CLOUD must be a boolean-style value when set."
    )


def cloud_disabled(mapping: Mapping[str, str] | None = None) -> bool:
    env = os.environ if mapping is None else mapping
    explicit_disable_cloud = _parse_optional_bool(_env(env, "ALGENTA_DISABLE_CLOUD"))
    if explicit_disable_cloud is not None:
        return explicit_disable_cloud
    return _normalized_deployment_mode(env) in _PRIVATE_DEPLOYMENT_MODES


def private_profile_enabled(mapping: Mapping[str, str] | None = None) -> bool:
    env = os.environ if mapping is None else mapping
    return _normalized_deployment_mode(env) in _PRIVATE_DEPLOYMENT_MODES or cloud_disabled(env)


def is_algenta_owned_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = parsed.hostname.strip().lower() if parsed.hostname else ""
    if host in _ALGENTA_OWNED_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in _ALGENTA_OWNED_SUFFIXES)


def normalize_base_url(base_url: str, *, component: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(
            f"{component} base_url must be an absolute URL including scheme and host."
        )
    return normalized


def _join_url_path(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url.rstrip('/')}{normalized_path}"


def _configured_console_base_url(mapping: Mapping[str, str]) -> str | None:
    for key in _CONSOLE_BASE_URL_ENV_KEYS:
        value = _env(mapping, key)
        if value:
            return value
    return None


def resolve_client_base_url(
    *,
    explicit_base_url: str | None,
    component: str,
    env: Mapping[str, str] | None = None,
) -> str:
    mapping = os.environ if env is None else env
    configured_base_url = (
        _env(mapping, "ALGENTA_BASE_URL")
        or _env(mapping, "DE_BASE_URL")
        or _env(mapping, "ALGENTA_API_URL")
    )
    raw_base_url = explicit_base_url or configured_base_url or DEFAULT_BASE_URL
    normalized = normalize_base_url(raw_base_url, component=component)
    if cloud_disabled(mapping) and is_algenta_owned_base_url(normalized):
        raise ValueError(
            f"{component} private profiles cannot target Algenta-owned cloud URLs. "
            "Configure a self-hosted base_url or ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
        )
    return normalized


def resolve_console_base_url(
    *,
    component: str,
    env: Mapping[str, str] | None = None,
    fallback_base_url: str | None = None,
) -> str:
    mapping = os.environ if env is None else env
    configured_console_url = _configured_console_base_url(mapping)
    if configured_console_url:
        normalized = normalize_base_url(
            configured_console_url,
            component=f"{component} console",
        )
        if private_profile_enabled(mapping) and is_algenta_owned_base_url(normalized):
            raise ValueError(
                f"{component} private profiles cannot target Algenta-owned cloud URLs. "
                "Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a "
                "self-hosted base_url."
            )
        return normalized

    if private_profile_enabled(mapping):
        raw_base_url = (
            fallback_base_url
            or _env(mapping, "ALGENTA_BASE_URL")
            or _env(mapping, "DE_BASE_URL")
            or _env(mapping, "ALGENTA_API_URL")
        )
        if not raw_base_url:
            raise ValueError(
                f"{component} private profiles require an explicit self-hosted dashboard or API "
                "base_url. "
                "Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or "
                "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
            )
        normalized = normalize_base_url(raw_base_url, component=f"{component} console")
        if is_algenta_owned_base_url(normalized):
            raise ValueError(
                f"{component} private profiles cannot target Algenta-owned cloud URLs. "
                "Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a "
                "self-hosted base_url."
            )
        return normalized

    return _DEFAULT_CONSOLE_BASE_URL


def resolve_api_keys_url(
    *,
    component: str,
    env: Mapping[str, str] | None = None,
    fallback_base_url: str | None = None,
) -> str:
    return _join_url_path(
        resolve_console_base_url(
            component=component,
            env=env,
            fallback_base_url=fallback_base_url,
        ),
        "/dashboard/api-keys",
    )


def api_key_help_text(
    *,
    component: str,
    env: Mapping[str, str] | None = None,
    fallback_base_url: str | None = None,
) -> str:
    mapping = os.environ if env is None else env
    if private_profile_enabled(mapping) and not _configured_console_base_url(mapping):
        console_base_url = resolve_console_base_url(
            component=component,
            env=mapping,
            fallback_base_url=fallback_base_url,
        )
        return (
            "Create a key from your self-hosted admin surface or API base URL: "
            f"{console_base_url}"
        )
    api_keys_url = resolve_api_keys_url(
        component=component,
        env=mapping,
        fallback_base_url=fallback_base_url,
    )
    return f"Get a key at: {api_keys_url}"
