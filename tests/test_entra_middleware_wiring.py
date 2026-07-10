"""HTTP-level tests for the Entra branch in get_current_org (middleware/auth.py).

Builds a minimal FastAPI app with a protected echo route using the REAL get_current_org
dependency, monkeypatching only the leaf I/O: the JWKS fetch (local RSA key) and the
principal-mapping resolver's DB session. Proves the wiring end-to-end: a valid Entra token
reaches the route with the mapping's org/workspace; Graph/foreign/unmapped tokens are
rejected with the right status; an Entra-looking token NEVER falls through to the API-key
path; X-Workspace-Id is explicitly refused for Entra callers.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI

from apps.api_server.middleware import auth as auth_middleware
from apps.api_server.services import entra_auth
from apps.api_server.services.auth_service import AuthContext
from tests._asgi_client import SyncASGIClient
from tests.test_entra_auth import _jwks, _Settings, _token

TENANT = _Settings.entra_tenant_id
ORG_ID = uuid.uuid4()
WORKSPACE_ID = uuid.uuid4()
MAPPED_OID = str(uuid.uuid4())


class _MappingRow:
    id = uuid.uuid4()
    org_id = ORG_ID
    workspace_id = WORKSPACE_ID
    tenant_id = TENANT
    principal_oid = MAPPED_OID
    principal_type = "user"
    email = "mapped@contoso.com"
    role = "member"
    status = "active"


class _OrgRow:
    id = ORG_ID
    plan = "pro"
    status = "active"


class _Result:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


class _StubDb:
    """Returns the mapping row for the mapped oid, the org row for Organization queries."""

    async def execute(self, stmt: Any) -> _Result:
        text = str(stmt)
        if "entra_principal_mappings" in text:
            oid = None
            for _, v in stmt.compile().params.items():
                if isinstance(v, str) and v == MAPPED_OID:
                    oid = v
            return _Result(_MappingRow() if oid else None)
        return _Result(_OrgRow())


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/echo")
    async def echo(ctx: AuthContext = Depends(auth_middleware.get_current_org)) -> dict[str, Any]:
        return {
            "org_id": str(ctx["org_id"]),
            "workspace_id": str(ctx["workspace_id"]) if ctx["workspace_id"] else None,
            "is_platform": ctx["is_platform"],
            "email": ctx["email"],
        }

    # only the DB dependency is overridden — get_current_org itself runs for real
    app.dependency_overrides[auth_middleware.get_db] = lambda: _StubDb()
    app.dependency_overrides[auth_middleware.get_redis] = lambda: None
    return app


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch):
    settings = _Settings()
    monkeypatch.setattr(entra_auth, "get_settings", lambda: settings)

    async def fake_fetch(tenant_id: str, *, force: bool = False):
        return _jwks()

    monkeypatch.setattr(entra_auth, "_fetch_jwks", fake_fetch)
    entra_auth._jwks_cache.clear()
    yield settings


def test_valid_entra_token_reaches_route_with_mapped_scope(_patch) -> None:
    token = _token(oid=MAPPED_OID)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["org_id"] == str(ORG_ID)
        assert body["workspace_id"] == str(WORKSPACE_ID)  # derived from the mapping
        assert body["is_platform"] is False
        assert body["email"] == "user@contoso.com"


def test_unmapped_principal_is_403_not_fallthrough(_patch) -> None:
    token = _token()  # random oid, not mapped
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "entra_principal_not_mapped"


def test_graph_token_is_rejected_401_no_fallthrough(_patch) -> None:
    token = _token(aud="https://graph.microsoft.com", oid=MAPPED_OID)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "entra_wrong_resource_token"


def test_foreign_tenant_is_403(_patch) -> None:
    token = _token(tid=str(uuid.uuid4()), oid=MAPPED_OID)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "entra_tenant_not_allowed"


def test_expired_entra_token_is_401_never_apikey_path(_patch) -> None:
    token = _token(exp_delta=-120, oid=MAPPED_OID)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "entra_token_expired"


def test_entra_caller_may_not_set_workspace_header(_patch) -> None:
    token = _token(oid=MAPPED_OID)
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(uuid.uuid4())}
    with SyncASGIClient(_app(), headers=headers) as client:
        r = client.get("/echo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "workspace_scope_not_permitted"


def test_unconfigured_gateway_ignores_entra_routing(_patch) -> None:
    # With Entra unconfigured, an Entra-shaped token goes down the normal api-key path
    # and is rejected as an invalid key — the Entra branch must not activate.
    _patch.entra_tenant_id = ""
    token = _token(oid=MAPPED_OID)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "invalid_api_key"
