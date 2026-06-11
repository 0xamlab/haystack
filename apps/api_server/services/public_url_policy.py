"""Shared public URL resolution for operator emails, billing, and upgrade hints."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

from apps.api_server.config import get_settings
from apps.platform_contract_constants import API_BASE_URL
from apps.privacy_policy import PrivacyPolicy, is_algenta_owned_destination

_CLOUD_APP_BASE_URL = "https://app.algenta.ai"
_LOCAL_API_BASE_URL = "http://localhost:8000"
_EXPLICIT_API_PUBLIC_BASE_URL_ENV_KEYS = (
    "ALGENTA_API_PUBLIC_BASE_URL",
    "API_PUBLIC_BASE_URL",
)
_EXPLICIT_API_PUBLIC_BASE_URL_FIELD_NAME = (
    "ALGENTA_API_PUBLIC_BASE_URL / API_PUBLIC_BASE_URL"
)
_EXPLICIT_APP_BASE_URL_FIELD_NAME = "ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL"
_TRANSPORT_API_BASE_URL_ENV_KEYS = (
    "ALGENTA_BASE_URL",
    "DE_BASE_URL",
    "ALGENTA_API_URL",
)
_TRANSPORT_API_BASE_URL_FIELD_NAME = "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL"


@dataclass(frozen=True)
class BillingRedirectUrls:
    success_url: str
    cancel_url: str
    return_url: str


class PublicUrlConfigurationError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _config_attr(config: object, name: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(name)
    return getattr(config, name, None)


def _first_non_empty_value(values: tuple[object | None, ...]) -> object | None:
    for raw_value in values:
        if raw_value is None:
            continue
        if isinstance(raw_value, str) and not raw_value.strip():
            continue
        return raw_value
    return None


def _explicit_public_api_base_url_raw_value(
    config: object,
    *,
    env: Mapping[str, str] | None = None,
) -> object | None:
    if isinstance(config, Mapping):
        mapping_value = _first_non_empty_value(
            (_config_attr(config, "api_public_base_url"),)
            + tuple(config.get(key) for key in _EXPLICIT_API_PUBLIC_BASE_URL_ENV_KEYS)
        )
        if mapping_value is not None:
            return mapping_value

    environment = os.environ if env is None else env
    explicit_env_value = _first_non_empty_value(
        tuple(environment.get(key) for key in _EXPLICIT_API_PUBLIC_BASE_URL_ENV_KEYS)
    )
    if explicit_env_value is not None:
        return explicit_env_value

    configured_value = _config_attr(config, "api_public_base_url")
    if configured_value is not None:
        if not isinstance(configured_value, str) or configured_value.strip():
            return configured_value
    return None


def _transport_api_base_url_raw_value(
    config: object,
    *,
    env: Mapping[str, str] | None = None,
) -> object | None:
    if isinstance(config, Mapping):
        mapping_value = _first_non_empty_value(
            tuple(config.get(key) for key in _TRANSPORT_API_BASE_URL_ENV_KEYS)
        )
        if mapping_value is not None:
            return mapping_value

    environment = os.environ if env is None else env
    explicit_env_value = _first_non_empty_value(
        tuple(environment.get(key) for key in _TRANSPORT_API_BASE_URL_ENV_KEYS)
    )
    if explicit_env_value is not None:
        return explicit_env_value

    configured_value = _config_attr(config, "api_transport_base_url")
    if configured_value is not None:
        if not isinstance(configured_value, str) or configured_value.strip():
            return configured_value
    return None


def _normalize_base_url(raw_value: object, *, field_name: str) -> str:
    value = str(raw_value).strip().rstrip("/")
    if not value:
        raise PublicUrlConfigurationError(
            "empty_public_base_url",
            f"{field_name} must not be empty when provided.",
            details={"field": field_name},
        )
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc or not parsed.hostname:
        raise PublicUrlConfigurationError(
            "invalid_public_base_url",
            f"{field_name} must be an absolute URL with scheme and host.",
            details={"field": field_name, "value": value},
        )
    return value


def _validate_private_profile_base_url(
    base_url: str,
    *,
    field_name: str,
    policy: PrivacyPolicy,
) -> str:
    host = urlparse(base_url).hostname
    if policy.private_profile and host and is_algenta_owned_destination(host):
        raise PublicUrlConfigurationError(
            "private_profile_public_url_forbidden",
            (
                f"{field_name} must not point to an Algenta-owned host in "
                f"{policy.deployment_mode} mode."
            ),
            details={
                "field": field_name,
                "value": base_url,
                "deployment_mode": policy.deployment_mode,
            },
        )
    return base_url


def _explicit_base_url(
    raw_value: object,
    *,
    field_name: str,
    policy: PrivacyPolicy,
) -> str | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and not raw_value.strip():
        return None
    normalized = _normalize_base_url(raw_value, field_name=field_name)
    return _validate_private_profile_base_url(
        normalized,
        field_name=field_name,
        policy=policy,
    )


def _configured_api_public_base_url(
    config: object,
    *,
    policy: PrivacyPolicy,
    env: Mapping[str, str] | None = None,
) -> str | None:
    explicit_override = _explicit_public_api_base_url_raw_value(config, env=env)
    if explicit_override is not None:
        return _explicit_base_url(
            explicit_override,
            field_name=_EXPLICIT_API_PUBLIC_BASE_URL_FIELD_NAME,
            policy=policy,
        )
    if not policy.private_profile:
        return None
    return _explicit_base_url(
        _transport_api_base_url_raw_value(config, env=env),
        field_name=_TRANSPORT_API_BASE_URL_FIELD_NAME,
        policy=policy,
    )


def has_explicit_public_api_base_url_override(
    config: object,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    return _explicit_public_api_base_url_raw_value(config, env=env) is not None


def _append_path(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url.rstrip('/')}{normalized_path}"


def request_origin_base_url(request: Any) -> str:
    base_url = getattr(request, "base_url", None)
    if base_url is None:
        raise PublicUrlConfigurationError(
            "missing_request_base_url",
            "Request does not expose a usable base_url.",
            details={},
        )
    return str(base_url).rstrip("/")


def resolve_api_public_base_url(
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    config = settings_obj or get_settings()
    policy = _config_attr(config, "privacy_policy")
    assert isinstance(policy, PrivacyPolicy)

    configured = _configured_api_public_base_url(
        config,
        policy=policy,
        env=env,
    )
    if configured is not None:
        return configured

    request_based = _explicit_base_url(
        request_origin,
        field_name="request_origin_base_url",
        policy=policy,
    )
    if request_based is not None:
        return request_based

    if policy.private_profile:
        return _LOCAL_API_BASE_URL
    return API_BASE_URL.rstrip("/")


def resolve_configured_api_public_base_url(
    *,
    settings_obj: object | None = None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    config = settings_obj or get_settings()
    policy = _config_attr(config, "privacy_policy")
    assert isinstance(policy, PrivacyPolicy)
    return _configured_api_public_base_url(config, policy=policy, env=env)


def resolve_app_public_base_url(
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> str:
    config = settings_obj or get_settings()
    policy = _config_attr(config, "privacy_policy")
    assert isinstance(policy, PrivacyPolicy)

    configured = _explicit_base_url(
        _config_attr(config, "app_base_url"),
        field_name=_EXPLICIT_APP_BASE_URL_FIELD_NAME,
        policy=policy,
    )
    if configured is not None:
        return configured

    request_based = _explicit_base_url(
        request_origin,
        field_name="request_origin_base_url",
        policy=policy,
    )
    if request_based is not None:
        return request_based

    if policy.private_profile:
        return resolve_api_public_base_url(
            settings_obj=config,
            request_origin=request_origin,
        )
    return _CLOUD_APP_BASE_URL


def resolve_billing_dashboard_url(
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> str:
    return _append_path(
        resolve_app_public_base_url(
            settings_obj=settings_obj,
            request_origin=request_origin,
        ),
        "/dashboard/billing",
    )


def resolve_dashboard_url(
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> str:
    return _append_path(
        resolve_app_public_base_url(
            settings_obj=settings_obj,
            request_origin=request_origin,
        ),
        "/dashboard",
    )


def resolve_simulate_endpoint_url(
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> str:
    return _append_path(
        resolve_api_public_base_url(
            settings_obj=settings_obj,
            request_origin=request_origin,
        ),
        "/v1/simulate",
    )


def resolve_email_verification_url(
    token: str,
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> str:
    base_url = resolve_app_public_base_url(
        settings_obj=settings_obj,
        request_origin=request_origin,
    )
    return f"{_append_path(base_url, '/auth/verify')}?{urlencode({'token': token})}"


def resolve_password_reset_url(
    token: str,
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> str:
    base_url = resolve_app_public_base_url(
        settings_obj=settings_obj,
        request_origin=request_origin,
    )
    return f"{_append_path(base_url, '/auth/reset-password')}?{urlencode({'token': token})}"


def resolve_billing_redirect_urls(
    *,
    settings_obj: object | None = None,
    request_origin: str | None = None,
) -> BillingRedirectUrls:
    billing_url = resolve_billing_dashboard_url(
        settings_obj=settings_obj,
        request_origin=request_origin,
    )
    return BillingRedirectUrls(
        success_url=f"{billing_url}?success=1",
        cancel_url=f"{billing_url}?cancelled=1",
        return_url=billing_url,
    )


def validate_public_url_configuration(settings_obj: object | None = None) -> None:
    config = settings_obj or get_settings()
    policy = _config_attr(config, "privacy_policy")
    assert isinstance(policy, PrivacyPolicy)
    _explicit_base_url(
        _config_attr(config, "app_base_url"),
        field_name=_EXPLICIT_APP_BASE_URL_FIELD_NAME,
        policy=policy,
    )
    _configured_api_public_base_url(
        config,
        policy=policy,
    )
