from __future__ import annotations

import pytest

from apps.api_server.config import get_settings
from apps.api_server.services.public_url_policy import (
    PublicUrlConfigurationError,
    resolve_api_public_base_url,
    resolve_app_public_base_url,
    resolve_billing_redirect_urls,
    validate_public_url_configuration,
)


def _refresh_settings() -> None:
    get_settings.cache_clear()


def test_saas_public_url_policy_uses_cloud_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
        monkeypatch.delenv("DE_BASE_URL", raising=False)
        _refresh_settings()

        assert resolve_api_public_base_url() == "https://api.algenta.ai"
        assert resolve_app_public_base_url() == "https://app.algenta.ai"
    finally:
        _refresh_settings()


def test_saas_public_url_policy_ignores_transport_base_url_without_public_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.delenv("API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.setenv("ALGENTA_BASE_URL", "https://internal.customer.example")
        _refresh_settings()

        assert resolve_api_public_base_url() == "https://api.algenta.ai"
    finally:
        _refresh_settings()


def test_saas_public_url_policy_honors_explicit_public_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
        monkeypatch.setenv("ALGENTA_BASE_URL", "https://internal.customer.example")
        monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://public.customer.example")
        _refresh_settings()

        assert resolve_api_public_base_url() == "https://public.customer.example"
    finally:
        _refresh_settings()


def test_private_public_url_policy_uses_transport_base_url_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.setenv("ALGENTA_BASE_URL", "https://decision.customer.internal")
        _refresh_settings()

        assert resolve_api_public_base_url() == "https://decision.customer.internal"
        assert resolve_app_public_base_url() == "https://decision.customer.internal"
    finally:
        _refresh_settings()


def test_private_public_url_policy_accepts_algenta_api_url_transport_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
        monkeypatch.delenv("DE_BASE_URL", raising=False)
        monkeypatch.setenv("ALGENTA_API_URL", "https://decision.customer.internal")
        _refresh_settings()

        assert resolve_api_public_base_url() == "https://decision.customer.internal"
        assert resolve_app_public_base_url() == "https://decision.customer.internal"
    finally:
        _refresh_settings()


def test_private_public_url_policy_uses_local_safe_defaults_without_cloud_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
        monkeypatch.delenv("DE_BASE_URL", raising=False)
        _refresh_settings()

        assert resolve_api_public_base_url() == "http://localhost:8000"
        assert resolve_app_public_base_url() == "http://localhost:8000"
    finally:
        _refresh_settings()


def test_private_public_url_policy_prefers_request_origin_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        _refresh_settings()

        redirect_urls = resolve_billing_redirect_urls(
            request_origin="https://decision.customer.internal"
        )

        assert redirect_urls.success_url == (
            "https://decision.customer.internal/dashboard/billing?success=1"
        )
        assert redirect_urls.cancel_url == (
            "https://decision.customer.internal/dashboard/billing?cancelled=1"
        )
        assert redirect_urls.return_url == "https://decision.customer.internal/dashboard/billing"
    finally:
        _refresh_settings()


def test_private_public_url_policy_accepts_legacy_dashboard_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("APP_BASE_URL", raising=False)
        monkeypatch.setenv("DE_APP_BASE_URL", "https://console.customer.internal")
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.setenv("ALGENTA_BASE_URL", "https://decision.customer.internal")
        _refresh_settings()

        assert resolve_app_public_base_url() == "https://console.customer.internal"
        redirects = resolve_billing_redirect_urls(request_origin=None)
        assert redirects.success_url == "https://console.customer.internal/dashboard/billing?success=1"
        assert redirects.cancel_url == "https://console.customer.internal/dashboard/billing?cancelled=1"
        assert redirects.return_url == "https://console.customer.internal/dashboard/billing"
    finally:
        _refresh_settings()


def test_private_public_url_policy_rejects_algenta_owned_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
        monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://api.algenta.ai")
        _refresh_settings()

        with pytest.raises(
            PublicUrlConfigurationError,
            match="ALGENTA_API_PUBLIC_BASE_URL / API_PUBLIC_BASE_URL must not point to an Algenta-owned host",
        ):
            validate_public_url_configuration()
    finally:
        _refresh_settings()


def test_private_public_url_policy_rejects_legacy_public_api_alias_on_algenta_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.setenv("API_PUBLIC_BASE_URL", "https://api.algenta.ai")
        _refresh_settings()

        with pytest.raises(
            PublicUrlConfigurationError,
            match="ALGENTA_API_PUBLIC_BASE_URL / API_PUBLIC_BASE_URL must not point to an Algenta-owned host",
        ):
            validate_public_url_configuration()
    finally:
        _refresh_settings()
