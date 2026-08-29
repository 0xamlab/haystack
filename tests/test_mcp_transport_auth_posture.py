"""The MCP HTTP surface: discovery is open, execution is not, and the edition is not a header hint.

Four code-path asymmetries this pins, all found on the live surface (read-only probes) plus a code
trace:

1. The `tools/call` 401 challenge was wired to the streamable `/mcp` mount ONLY. The deprecated
   `GET /mcp/sse` + `POST /mcp/messages` pair was registered raw, so a `tools/call` delivered over the
   legacy lane never passed the challenge.
2. Downstream of that, an unauthenticated call reached `_resolve_api_key()` with no request override,
   which then fell back to the SERVER process's `ALGENTA_API_KEY` / `DE_API_KEY` — variables
   `docker-compose.selfhosted.yml` injects into the api container. That is the difference between
   "discovery only" and "an anonymous caller executing tools with the deployment's own credential".
3. `/mcp/tools` took the product edition solely from `X-Algenta-Product`, and
   `product_allowlist(None)` means "the entire registry" — so omitting the header advertised all 140
   tools of every brand (billing checkout/portal, api-key creation, team invites, audit logs and the
   three admin runtime tools included) instead of this deployment's edition.
4. The `WWW-Authenticate` challenge on both lanes carries an RFC 9728 `resource_metadata` hint
   (see `apps/api_server/routers/oauth_protected_resource.py`) ONLY when Entra and/or generic OIDC
   is actually configured — an unconfigured deployment's challenge must be byte-identical to before
   this Track landed (no dangling discovery hint pointing at a document that would 404).

`/mcp/tools` and streamable `tools/list` MUST stay public: `gitbook/sdk/mcp.md` publishes "no auth
required", and listing tools before sign-in is normal MCP client behaviour.
"""

from __future__ import annotations

import asyncio

import pytest

from apps.api_server.config import get_settings
from apps.api_server.main import app
from apps.mcp_server import client as mcp_client
from apps.mcp_server import products
from apps.mcp_server.errors import UnsupportedMCPAuthConfigurationError
from apps.mcp_server.registry import TOOLS
from apps.mcp_server.transports import http_sse
from tests._asgi_client import SyncASGIClient

_ANY_KEY = "sk-test-not-a-real-key"
_ENTRA_TENANT = "11111111-1111-1111-1111-111111111111"


# ── 1. The legacy lane requires a credential ───────────────────────────────────


def test_legacy_sse_handshake_is_refused_without_a_key() -> None:
    """It used to answer with a session id, which is the first half of the exploit chain."""
    with SyncASGIClient(app) as client:
        response = client.get("/mcp/sse")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert "session_id" not in response.text


def test_legacy_message_post_is_refused_without_a_key() -> None:
    with SyncASGIClient(app) as client:
        response = client.post(
            "/mcp/messages",
            params={"session_id": "00000000000000000000000000000000"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_me"}},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_the_legacy_guard_passes_an_authenticated_caller_through() -> None:
    """The gate must be about the credential, not about blocking the transport outright."""
    seen: list[str] = []

    async def _inner(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        seen.append(scope["path"])

    guard = http_sse._MCPLegacyTransportAuthASGIApp(_inner)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/mcp/sse",
        "headers": [(b"authorization", f"Bearer {_ANY_KEY}".encode())],
    }
    asyncio.run(guard(scope, None, None))
    assert seen == ["/mcp/sse"]


def test_the_legacy_guard_accepts_the_legacy_api_key_header_too() -> None:
    """X-API-Key is still accepted API-wide; the guard must not diverge from the API's own scheme."""
    seen: list[str] = []

    async def _inner(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        seen.append(scope["path"])

    guard = http_sse._MCPLegacyTransportAuthASGIApp(_inner)
    asyncio.run(
        guard(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp/messages",
                "headers": [(b"x-api-key", _ANY_KEY.encode())],
            },
            None,
            None,
        )
    )
    assert seen == ["/mcp/messages"]


# ── 2. No HTTP caller inherits the server's ambient credential ─────────────────


def test_an_http_request_never_borrows_the_process_api_key(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_API_KEY", "server-ambient-key")
    monkeypatch.setenv("DE_API_KEY", "server-ambient-key-legacy")

    # stdio / in-process: the environment IS the caller's configuration, so it still applies.
    assert mcp_client._resolve_api_key() == "server-ambient-key"

    # HTTP transport with no caller credential: must resolve to nothing, not to the deployment's key.
    with mcp_client.request_overrides(api_key=None, allow_ambient_key=False):
        assert mcp_client._resolve_api_key() == ""
        with pytest.raises(UnsupportedMCPAuthConfigurationError):
            mcp_client._headers()

    # …and the restriction must not leak past the request.
    assert mcp_client._resolve_api_key() == "server-ambient-key"


def test_an_authenticated_http_caller_still_forwards_its_own_key(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_API_KEY", "server-ambient-key")
    with mcp_client.request_overrides(api_key=_ANY_KEY, allow_ambient_key=False):
        assert mcp_client._resolve_api_key() == _ANY_KEY
        assert mcp_client._headers()["Authorization"] == f"Bearer {_ANY_KEY}"


def test_the_http_transports_ask_for_the_ambient_restriction() -> None:
    """Guards the wiring, not just the mechanism: both HTTP transport copies must pass the flag, or
    the contextvar above is dead code and the fallback is still reachable."""
    for path in (
        "apps/mcp_server/transports/http_sse.py",
        "packages/mcp/algenta_mcp/transports/http_sse.py",
    ):
        source = open(path, encoding="utf-8").read()
        assert source.count("allow_ambient_key=False") == 2, path


# ── 3. The edition is a deployment property, not a caller hint ─────────────────


def test_tool_listing_scopes_to_this_deployments_edition(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_PRODUCT", "algenta")
    with SyncASGIClient(app) as client:
        response = client.get("/mcp/tools")
    assert response.status_code == 200, "tool listing must stay public"
    names = {tool["name"] for tool in response.json()["tools"]}
    assert names == set(products.product_allowlist("algenta"))
    assert names < set(TOOLS), "the edition must be a strict subset of the registry"


@pytest.mark.parametrize(
    "tool",
    [
        "create_billing_checkout",
        "create_billing_portal",
        "get_billing_info",
        "create_api_key",
        "invite_team_member",
        "get_audit_logs",
        "get_runtime_modules",
        "get_runtime_benchmarks",
        "get_runtime_release_validation",
    ],
)
def test_out_of_edition_tools_are_not_advertised_unauthenticated(monkeypatch, tool: str) -> None:
    """These were all listed to anonymous callers. Billing ones also re-published the Stripe business
    model; the runtime ones are admin-only at the HTTP layer."""
    assert tool in TOOLS, f"{tool} vanished from the registry; update this list, do not delete it"
    monkeypatch.setenv("ALGENTA_PRODUCT", "algenta")
    with SyncASGIClient(app) as client:
        names = {t["name"] for t in client.get("/mcp/tools").json()["tools"]}
    assert tool not in names


def test_an_explicit_header_still_selects_an_edition(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_PRODUCT", "algenta")
    with SyncASGIClient(app) as client:
        response = client.get("/mcp/tools", headers={"X-Algenta-Product": "codna"})
    names = {tool["name"] for tool in response.json()["tools"]}
    assert names == set(products.product_allowlist("codna"))


def test_an_unknown_header_edition_still_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_PRODUCT", "algenta")
    with SyncASGIClient(app) as client:
        response = client.get("/mcp/tools", headers={"X-Algenta-Product": "not-a-product"})
    assert response.json()["tools"] == []


def test_an_unconfigured_shared_engine_keeps_advertising_the_full_registry(monkeypatch) -> None:
    """Existing direct integrations rely on the unscoped listing, so the narrowing is opt-in via the
    same setting that scopes billing — it must not silently change an unconfigured deployment."""
    monkeypatch.delenv("ALGENTA_PRODUCT", raising=False)
    monkeypatch.setattr(http_sse, "_deployment_product", lambda: None)
    with SyncASGIClient(app) as client:
        names = {tool["name"] for tool in client.get("/mcp/tools").json()["tools"]}
    assert names == set(TOOLS)


def test_the_effective_product_prefers_the_header_then_the_deployment(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_PRODUCT", "algenta")
    assert http_sse._effective_product("codna") == "codna"
    assert http_sse._effective_product(None) == "algenta"
    monkeypatch.setenv("ALGENTA_PRODUCT", "  ALGENTA  ")
    assert http_sse._effective_product(None) == "algenta"


# ── 4. RFC 9728 discovery hint on the WWW-Authenticate challenge ───────────────


@pytest.fixture()
def _clear_authorization_server_env(monkeypatch: pytest.MonkeyPatch):
    """Guarantee neither Entra nor generic OIDC is configured, then restore the settings cache."""
    for key in (
        "ALGENTA_ENTRA_TENANT_ID",
        "ALGENTA_ENTRA_AUDIENCE",
        "ALGENTA_ENTRA_ALLOWED_TENANTS",
        "ALGENTA_OIDC_ISSUER",
        "ALGENTA_OIDC_AUDIENCE",
        "ALGENTA_OIDC_JWKS_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_unconfigured_deployment_challenge_is_unchanged(_clear_authorization_server_env) -> None:
    """The exact pre-Track-A2b string — no dangling resource_metadata hint with nothing to
    discover."""
    assert http_sse._configured_authorization_servers() == ()
    scope = {"scheme": "https", "headers": [(b"host", b"api.algenta.ai")]}
    assert (
        http_sse._www_authenticate_header(scope)
        == 'Bearer realm="algenta", error="invalid_token"'
    )


def test_entra_configured_adds_the_resource_metadata_hint(
    monkeypatch: pytest.MonkeyPatch, _clear_authorization_server_env
) -> None:
    monkeypatch.setenv("ALGENTA_ENTRA_TENANT_ID", _ENTRA_TENANT)
    monkeypatch.setenv("ALGENTA_ENTRA_AUDIENCE", "api://algenta-gateway")
    get_settings.cache_clear()

    assert http_sse._configured_authorization_servers() == (
        f"https://login.microsoftonline.com/{_ENTRA_TENANT}/v2.0",
    )
    scope = {"scheme": "https", "headers": [(b"host", b"api.algenta.ai")]}
    header = http_sse._www_authenticate_header(scope)
    assert header == (
        'Bearer realm="algenta", error="invalid_token", '
        'resource_metadata="https://api.algenta.ai/.well-known/oauth-protected-resource/mcp"'
    )


def test_legacy_lane_401_carries_the_hint_only_when_configured(
    monkeypatch: pytest.MonkeyPatch, _clear_authorization_server_env
) -> None:
    with SyncASGIClient(app, base_url="http://testserver") as client:
        unconfigured = client.get("/mcp/sse")
    assert unconfigured.status_code == 401
    assert "resource_metadata" not in unconfigured.headers["www-authenticate"]

    monkeypatch.setenv("ALGENTA_ENTRA_TENANT_ID", _ENTRA_TENANT)
    monkeypatch.setenv("ALGENTA_ENTRA_AUDIENCE", "api://algenta-gateway")
    get_settings.cache_clear()

    with SyncASGIClient(app, base_url="http://testserver") as client:
        configured = client.get("/mcp/sse")
    assert configured.status_code == 401
    assert configured.headers["www-authenticate"] == (
        'Bearer realm="algenta", error="invalid_token", '
        'resource_metadata="http://testserver/.well-known/oauth-protected-resource/mcp"'
    )


def test_streamable_tools_call_401_carries_the_hint_only_when_configured(
    monkeypatch: pytest.MonkeyPatch, _clear_authorization_server_env
) -> None:
    """Uses a fresh router + real starlette TestClient (like
    test_embedded_tool_call_without_auth_returns_oauth_challenge in test_mcp_router.py): the
    streamable manager is lifespan-bound, and TestClient-as-context-manager is what drives that
    lifespan — the shared apps.api_server.main:app needs a live DB/Redis to start up."""
    pytest.importorskip("mcp")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    router = http_sse._build_fastapi_router()
    assert router is not None
    test_app = FastAPI()
    test_app.include_router(router)

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_contract", "arguments": {}},
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }

    with TestClient(test_app, base_url="http://testserver") as client:
        unconfigured = client.post("/mcp", json=body, headers=headers)
    assert unconfigured.status_code == 401
    assert "resource_metadata" not in unconfigured.headers["www-authenticate"]

    monkeypatch.setenv("ALGENTA_OIDC_ISSUER", "https://idp.example.com/realms/acme")
    monkeypatch.setenv("ALGENTA_OIDC_AUDIENCE", "algenta-gateway")
    monkeypatch.setenv(
        "ALGENTA_OIDC_JWKS_URL", "https://idp.example.com/realms/acme/protocol/openid-connect/certs"
    )
    get_settings.cache_clear()

    with TestClient(test_app, base_url="http://testserver") as client:
        configured = client.post("/mcp", json=body, headers=headers)
    assert configured.status_code == 401
    assert configured.headers["www-authenticate"] == (
        'Bearer realm="algenta", error="invalid_token", '
        'resource_metadata="http://testserver/.well-known/oauth-protected-resource/mcp"'
    )
