from __future__ import annotations

import warnings

import pytest

from apps.api_server.config import get_settings
from apps.api_server.main import app
from apps.platform_contract import (
    load_platform_contract_manifest,
    load_platform_contract_manifest_model,
)
from tests._asgi_client import SyncASGIClient
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)


def _clear_platform_contract_route_state() -> None:
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_get_platform_contract_route_returns_manifest_shape(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "ALGENTA_DEPLOYMENT_MODE",
        "ALGENTA_DISABLE_CLOUD",
        "ALGENTA_API_PUBLIC_BASE_URL",
        "API_PUBLIC_BASE_URL",
        "ALGENTA_BASE_URL",
        "DE_BASE_URL",
        "ALGENTA_API_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    _clear_platform_contract_route_state()
    response = await client.get("/v1/meta/contract")

    assert response.status_code == 200
    body = response.json()
    manifest = load_platform_contract_manifest()

    assert body["contract_version"] == manifest["contract_version"]
    assert body["brand"] == manifest["brand"]
    assert body["api_base_url"] == manifest["api_base_url"]
    assert body["mcp_endpoint"] == manifest["mcp_endpoint"]
    assert body["mcp_tools_endpoint"] == manifest["mcp_tools_endpoint"]
    assert body["primary_data_query_contract"]["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert body["capability_plane"]["api"]["list_providers_endpoint"] == "/v1/capability-providers"
    assert (
        body["capability_plane"]["direct_sdk"]["typescript"]["route_capabilities_method"]
        == "routeCapabilities"
    )
    assert (
        body["primary_data_query_contract"]["direct_sdk"]["python"]["contract_method"]
        == "get_contract"
    )
    assert (
        body["primary_data_query_contract"]["direct_sdk"]["typescript"]["contract_method"]
        == "getContract"
    )
    assert body["primary_data_query_contract"]["cli"]["contract_command"] == "de contract"
    assert body["primary_data_query_contract"]["mcp"]["contract_tool"] == "get_contract"
    assert_manifest_backed_integrations(body["integrations"])


def test_get_platform_contract_route_rebases_private_profile_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://decision.customer.internal")
    _clear_platform_contract_route_state()

    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/meta/contract")
    finally:
        _clear_platform_contract_route_state()

    assert response.status_code == 200
    body = response.json()
    assert body["api_base_url"] == "https://decision.customer.internal"
    assert body["mcp_endpoint"] == "https://decision.customer.internal/mcp"
    assert body["mcp_tools_endpoint"] == "https://decision.customer.internal/mcp/tools"
    assert body["primary_data_query_contract"]["api"]["contract_endpoint"] == "/v1/meta/contract"


def test_get_platform_contract_route_rebases_private_profile_urls_from_algenta_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "https://decision.customer.internal")
    _clear_platform_contract_route_state()

    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/meta/contract")
    finally:
        _clear_platform_contract_route_state()

    assert response.status_code == 200
    body = response.json()
    assert body["api_base_url"] == "https://decision.customer.internal"
    assert body["mcp_endpoint"] == "https://decision.customer.internal/mcp"
    assert body["mcp_tools_endpoint"] == "https://decision.customer.internal/mcp/tools"


def test_get_platform_contract_route_rejects_invalid_signed_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apps.api_server.routers.meta as meta_router

    for key in (
        "ALGENTA_DEPLOYMENT_MODE",
        "ALGENTA_DISABLE_CLOUD",
        "ALGENTA_API_PUBLIC_BASE_URL",
        "API_PUBLIC_BASE_URL",
        "ALGENTA_BASE_URL",
        "DE_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    payload = load_platform_contract_manifest_model().model_copy(
        update={"api_key_prefixes": {"live": "de_live_", "test": 7}}
    )
    monkeypatch.setattr(meta_router, "load_platform_contract_manifest_model", lambda: payload)
    _clear_platform_contract_route_state()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with SyncASGIClient(app) as client:
            response = client.get("/v1/meta/contract")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "invalid_platform_contract_manifest"
    assert body["error"]["details"]["cause"] == "api_key_prefixes.test"
    assert body["error"]["details"]["validation_errors"][0]["path"] == "api_key_prefixes.test"
    assert caught == []
