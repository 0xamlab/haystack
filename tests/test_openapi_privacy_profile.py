from __future__ import annotations

import pytest

from apps.api_server.config import get_settings
from apps.api_server.main import app
from apps.api_server.openapi_surface import (
    apply_openapi_surface,
    openapi_mcp_endpoint,
    openapi_server_url,
    validate_openapi_surface_configuration,
)


def _clear_openapi_state() -> None:
    get_settings.cache_clear()
    app.openapi_schema = None


def test_openapi_surface_assigns_stable_mcp_operation_ids() -> None:
    schema = apply_openapi_surface({})

    assert schema["paths"]["/mcp"]["get"]["operationId"] == "stream_mcp_events"
    assert schema["paths"]["/mcp"]["post"]["operationId"] == "send_mcp_message"
    assert (
        schema["paths"]["/mcp"]["delete"]["operationId"]
        == "terminate_mcp_session"
    )
    assert (
        schema["paths"]["/mcp/sse"]["get"]["operationId"]
        == "stream_legacy_mcp_events"
    )
    assert (
        schema["paths"]["/mcp/messages"]["post"]["operationId"]
        == "send_legacy_mcp_message"
    )


def test_openapi_saas_ignores_transport_base_url_without_public_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("API_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://internal.customer.example")
    _clear_openapi_state()

    try:
        assert openapi_server_url() == "https://api.algenta.ai"
        assert openapi_mcp_endpoint("https://api.algenta.ai") == "https://api.algenta.ai/mcp"

        schema = app.openapi()
        assert schema["servers"] == [{"url": "https://api.algenta.ai"}]
        assert schema["x-canonical-mcp-endpoint"] == "https://api.algenta.ai/mcp"
    finally:
        _clear_openapi_state()


def test_openapi_saas_honors_explicit_public_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://internal.customer.example")
    monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://public.customer.example")
    _clear_openapi_state()

    try:
        assert openapi_server_url() == "https://public.customer.example"
        assert (
            openapi_mcp_endpoint("https://public.customer.example")
            == "https://public.customer.example/mcp"
        )

        schema = app.openapi()
        assert schema["servers"] == [{"url": "https://public.customer.example"}]
        assert schema["x-canonical-mcp-endpoint"] == "https://public.customer.example/mcp"
    finally:
        _clear_openapi_state()


def test_openapi_private_profile_uses_relative_surface_without_explicit_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    _clear_openapi_state()

    try:
        assert openapi_server_url() == "/"
        assert openapi_mcp_endpoint("/") == "/mcp"

        schema = app.openapi()
        assert schema["servers"] == [{"url": "/"}]
        assert schema["x-canonical-mcp-endpoint"] == "/mcp"
    finally:
        _clear_openapi_state()


def test_openapi_private_profile_uses_explicit_self_hosted_surface_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://decision.customer.internal")
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    _clear_openapi_state()

    try:
        assert openapi_server_url() == "https://decision.customer.internal"
        assert (
            openapi_mcp_endpoint("https://decision.customer.internal")
            == "https://decision.customer.internal/mcp"
        )

        schema = app.openapi()
        assert schema["servers"] == [{"url": "https://decision.customer.internal"}]
        assert (
            schema["x-canonical-mcp-endpoint"]
            == "https://decision.customer.internal/mcp"
        )
    finally:
        _clear_openapi_state()


def test_openapi_private_profile_rejects_algenta_cloud_surface_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    _clear_openapi_state()

    try:
        with pytest.raises(
            ValueError,
            match=(
                "OpenAPI surface ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL "
                "must not point to an Algenta-owned host"
            ),
        ):
            validate_openapi_surface_configuration()
    finally:
        _clear_openapi_state()


def test_openapi_private_profile_rejects_algenta_cloud_public_api_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("API_PUBLIC_BASE_URL", "https://api.algenta.ai")
    _clear_openapi_state()

    try:
        with pytest.raises(
            ValueError,
            match=(
                "OpenAPI surface ALGENTA_API_PUBLIC_BASE_URL / API_PUBLIC_BASE_URL "
                "must not point to an Algenta-owned host"
            ),
        ):
            validate_openapi_surface_configuration()
    finally:
        _clear_openapi_state()


def test_openapi_private_profile_rejects_unallowlisted_public_surface_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.customer.example")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    _clear_openapi_state()

    try:
        with pytest.raises(
            ValueError,
            match="require a private/self-hosted origin or an allowlisted customer origin",
        ):
            validate_openapi_surface_configuration()
    finally:
        _clear_openapi_state()
