from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping, Sequence
from urllib.parse import urlparse

from apps.privacy_policy import (
    PRIVATE_HOST_SUFFIXES,
    destination_matches_allowlist,
    is_algenta_owned_destination,
    parse_egress_destination,
    policy_from_environment,
)

_DEFAULT_OPERATOR_ENV_KEYS = ("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL")
_DEFAULT_OPERATOR_APP_ENV_KEYS = ("ALGENTA_APP_BASE_URL", "APP_BASE_URL", "DE_APP_BASE_URL")
_DEFAULT_OPERATOR_CONSOLE_BASE_URL = "https://app.algenta.ai"


def _env(mapping: Mapping[str, str], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalized_operator_url(value: str, *, field_name: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute http(s) URL.")
    return normalized


def _policy_mapping(mapping: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in mapping.items()
        if key not in _DEFAULT_OPERATOR_ENV_KEYS
    }


def _private_operator_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    if any(normalized.endswith(suffix) for suffix in PRIVATE_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    )


def _join_url_path(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url.rstrip('/')}{normalized_path}"


def operator_private_profile(env: Mapping[str, str] | None = None) -> bool:
    mapping = os.environ if env is None else env
    policy = policy_from_environment(_policy_mapping(mapping))
    return policy.private_profile or policy.disable_cloud


def validate_operator_api_base_url(
    base_url: str,
    *,
    surface: str,
    env: Mapping[str, str] | None = None,
    require_self_hosted: bool = False,
    allow_internal_without_allowlist: bool = True,
) -> str:
    mapping = os.environ if env is None else env
    normalized = _normalized_operator_url(base_url, field_name="base_url")
    destination = parse_egress_destination(normalized)
    policy = policy_from_environment(_policy_mapping(mapping))

    if is_algenta_owned_destination(destination.host):
        if require_self_hosted:
            raise ValueError(
                f"{surface} requires a self-hosted base URL and cannot target Algenta-owned cloud URLs. "
                "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
            )
        if policy.disable_cloud:
            raise ValueError(
                f"{surface} private profiles cannot target Algenta-owned cloud URLs. "
                "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
            )

    if policy.allow_outbound_network:
        return normalized

    if allow_internal_without_allowlist and _private_operator_host(destination.host):
        return normalized

    if destination_matches_allowlist(destination, policy.egress_allowlist):
        return normalized

    if require_self_hosted:
        raise ValueError(
            f"{surface} requires a private/self-hosted origin or an allowlisted customer origin."
        )

    if policy.private_profile or policy.disable_cloud:
        raise ValueError(
            f"{surface} private profiles require a private/self-hosted origin or an allowlisted customer origin."
        )

    return normalized


def resolve_operator_api_base_url(
    *,
    saved_base_url: str | None = None,
    default_base_url: str = "http://localhost:8000",
    env: Mapping[str, str] | None = None,
    env_keys: Sequence[str] = _DEFAULT_OPERATOR_ENV_KEYS,
    surface: str,
    require_self_hosted: bool = False,
    allow_internal_without_allowlist: bool = True,
) -> str:
    mapping = os.environ if env is None else env
    configured = next((_env(mapping, key) for key in env_keys if _env(mapping, key)), None)
    persisted = saved_base_url.strip() if saved_base_url and saved_base_url.strip() else ""
    if operator_private_profile(mapping) and not configured and not persisted:
        raise ValueError(
            f"{surface} private profiles require an explicit self-hosted API origin. "
            "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
        )
    raw_base_url = configured or persisted or default_base_url
    return validate_operator_api_base_url(
        raw_base_url,
        surface=surface,
        env=mapping,
        require_self_hosted=require_self_hosted,
        allow_internal_without_allowlist=allow_internal_without_allowlist,
    )


def resolve_operator_console_base_url(
    *,
    fallback_api_base_url: str | None = None,
    default_base_url: str = _DEFAULT_OPERATOR_CONSOLE_BASE_URL,
    env: Mapping[str, str] | None = None,
    env_keys: Sequence[str] = _DEFAULT_OPERATOR_APP_ENV_KEYS,
    surface: str,
    require_self_hosted: bool = False,
    allow_internal_without_allowlist: bool = True,
) -> str:
    mapping = os.environ if env is None else env
    configured = next((_env(mapping, key) for key in env_keys if _env(mapping, key)), None)
    fallback_url = (
        fallback_api_base_url.strip()
        if fallback_api_base_url and fallback_api_base_url.strip()
        else None
    )
    if configured:
        raw_base_url = configured
    elif operator_private_profile(mapping) or require_self_hosted:
        if not fallback_url:
            raise ValueError(
                f"{surface} private profiles require an explicit self-hosted dashboard or API origin. "
                "Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or "
                "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
            )
        raw_base_url = fallback_url
    else:
        raw_base_url = default_base_url
    return validate_operator_api_base_url(
        raw_base_url,
        surface=surface,
        env=mapping,
        require_self_hosted=require_self_hosted,
        allow_internal_without_allowlist=allow_internal_without_allowlist,
    )


def resolve_operator_dashboard_url(
    *,
    fallback_api_base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    surface: str,
    require_self_hosted: bool = False,
    allow_internal_without_allowlist: bool = True,
) -> str:
    base_url = resolve_operator_console_base_url(
        fallback_api_base_url=fallback_api_base_url,
        env=env,
        surface=surface,
        require_self_hosted=require_self_hosted,
        allow_internal_without_allowlist=allow_internal_without_allowlist,
    )
    return _join_url_path(base_url, "/dashboard")
