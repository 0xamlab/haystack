"""RFC 9728 OAuth protected-resource metadata for the MCP server (routers/oauth_protected_resource.py).

Mirrors tests/test_license_jwks.py's pattern for a standalone /.well-known/* surface: mount only
this router on a bare FastAPI() app and hit it with TestClient. Covers the honesty discipline this
repo already establishes for GET /.well-known/jwks.json (routers/license.py) and applies here: both
the bare and the /mcp path-appended location 404 with neither Microsoft Entra ID nor generic OIDC
configured, and publish a well-formed document -- naming every actually-trusted issuer, never a
guess -- once either (or both) is.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api_server.config import get_settings
from apps.api_server.routers import oauth_protected_resource as oauth_pr_router

_BASE_URL = "https://mcp-gateway.example.test"
_ENTRA_TENANT = "11111111-1111-1111-1111-111111111111"
_ENTRA_OTHER_TENANT = "22222222-2222-2222-2222-222222222222"
_OIDC_ISSUER = "https://idp.example.com/realms/acme"

_PATHS = (
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
)


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(oauth_pr_router.router)
    return app


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch):
    """A deterministic public base URL, and neither authorization server configured by default."""
    for key in (
        "ALGENTA_API_PUBLIC_BASE_URL",
        "API_PUBLIC_BASE_URL",
        "ALGENTA_ENTRA_TENANT_ID",
        "ALGENTA_ENTRA_AUDIENCE",
        "ALGENTA_ENTRA_ALLOWED_TENANTS",
        "ALGENTA_OIDC_ISSUER",
        "ALGENTA_OIDC_AUDIENCE",
        "ALGENTA_OIDC_JWKS_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", _BASE_URL)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── unconfigured: never advertise an authorization server that doesn't exist ───


@pytest.mark.parametrize("path", _PATHS)
def test_404s_when_no_authorization_server_is_configured(path: str) -> None:
    with TestClient(_app()) as client:
        response = client.get(path)
    assert response.status_code == 404


# ── Entra configured ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", _PATHS)
def test_entra_configured_publishes_its_issuer(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setenv("ALGENTA_ENTRA_TENANT_ID", _ENTRA_TENANT)
    monkeypatch.setenv("ALGENTA_ENTRA_AUDIENCE", "api://algenta-gateway")
    get_settings.cache_clear()

    with TestClient(_app()) as client:
        response = client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == f"{_BASE_URL}/mcp"
    assert body["authorization_servers"] == [
        f"https://login.microsoftonline.com/{_ENTRA_TENANT}/v2.0"
    ]
    assert body["bearer_methods_supported"] == ["header"]
    assert "scopes_supported" not in body  # no invented scopes Algenta doesn't actually enforce


def test_entra_multi_tenant_lists_every_allowed_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_ENTRA_TENANT_ID", _ENTRA_TENANT)
    monkeypatch.setenv("ALGENTA_ENTRA_AUDIENCE", "api://algenta-gateway")
    monkeypatch.setenv("ALGENTA_ENTRA_ALLOWED_TENANTS", _ENTRA_OTHER_TENANT)
    get_settings.cache_clear()

    with TestClient(_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.json()["authorization_servers"] == [
        f"https://login.microsoftonline.com/{_ENTRA_TENANT}/v2.0",
        f"https://login.microsoftonline.com/{_ENTRA_OTHER_TENANT}/v2.0",
    ]


# ── Generic OIDC configured ──────────────────────────────────────────────────────


def test_generic_oidc_configured_publishes_its_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_OIDC_ISSUER", _OIDC_ISSUER)
    monkeypatch.setenv("ALGENTA_OIDC_AUDIENCE", "algenta-gateway")
    monkeypatch.setenv(
        "ALGENTA_OIDC_JWKS_URL", f"{_OIDC_ISSUER}/protocol/openid-connect/certs"
    )
    get_settings.cache_clear()

    with TestClient(_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource")

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == f"{_BASE_URL}/mcp"
    assert body["authorization_servers"] == [_OIDC_ISSUER]


def test_oidc_partially_configured_still_404s(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issuer + audience with no JWKS URL is not a usable verifier — must not advertise it."""
    monkeypatch.setenv("ALGENTA_OIDC_ISSUER", _OIDC_ISSUER)
    monkeypatch.setenv("ALGENTA_OIDC_AUDIENCE", "algenta-gateway")
    get_settings.cache_clear()

    with TestClient(_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource")

    assert response.status_code == 404


# ── Both configured ──────────────────────────────────────────────────────────────


def test_both_entra_and_oidc_configured_lists_both_issuers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_ENTRA_TENANT_ID", _ENTRA_TENANT)
    monkeypatch.setenv("ALGENTA_ENTRA_AUDIENCE", "api://algenta-gateway")
    monkeypatch.setenv("ALGENTA_OIDC_ISSUER", _OIDC_ISSUER)
    monkeypatch.setenv("ALGENTA_OIDC_AUDIENCE", "algenta-gateway")
    monkeypatch.setenv(
        "ALGENTA_OIDC_JWKS_URL", f"{_OIDC_ISSUER}/protocol/openid-connect/certs"
    )
    get_settings.cache_clear()

    with TestClient(_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.json()["authorization_servers"] == [
        f"https://login.microsoftonline.com/{_ENTRA_TENANT}/v2.0",
        _OIDC_ISSUER,
    ]


# ── both routes agree, and are unauthenticated + hidden from the public schema ───


def test_both_locations_serve_the_same_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_ENTRA_TENANT_ID", _ENTRA_TENANT)
    monkeypatch.setenv("ALGENTA_ENTRA_AUDIENCE", "api://algenta-gateway")
    get_settings.cache_clear()

    with TestClient(_app()) as client:
        bare = client.get("/.well-known/oauth-protected-resource")
        scoped = client.get("/.well-known/oauth-protected-resource/mcp")

    assert bare.json() == scoped.json()


def test_route_is_unauthenticated_and_hidden_from_the_openapi_schema() -> None:
    app = _app()
    for route in app.routes:
        if getattr(route, "path", None) in _PATHS:
            assert route.include_in_schema is False
