"""HTTP-level tests for the generic-OIDC branch in get_current_org (middleware/auth.py).

Builds a minimal FastAPI app with a protected echo route using the REAL get_current_org
dependency, monkeypatching only the leaf I/O: the JWKS fetch (local RSA key) and the
principal-mapping resolver's DB session. Proves the wiring end-to-end: a valid OIDC token
reaches the route with the mapping's org/workspace; wrong-audience/unmapped tokens are
rejected with the right status; an OIDC-looking token NEVER falls through to the API-key
path; X-Workspace-Id is explicitly refused for OIDC callers.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI

from apps.api_server.middleware import auth as auth_middleware
from apps.api_server.services import oidc_auth
from apps.api_server.services.auth_service import AuthContext
from tests._asgi_client import SyncASGIClient
from tests.test_oidc_auth import ISSUER, _jwks, _Settings, _token

ORG_ID = uuid.uuid4()
WORKSPACE_ID = uuid.uuid4()
MAPPED_SUBJECT = "mapped-subject-1"


class _MappingRow:
    id = uuid.uuid4()
    org_id = ORG_ID
    workspace_id = WORKSPACE_ID
    issuer = ISSUER
    subject = MAPPED_SUBJECT
    principal_type = "user"
    email = "mapped@acme.example"
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
    """Returns the mapping row for the mapped subject, the org row for Organization queries."""

    async def execute(self, stmt: Any) -> _Result:
        text = str(stmt)
        if "oidc_principal_mappings" in text:
            subject = None
            for _, v in stmt.compile().params.items():
                if isinstance(v, str) and v == MAPPED_SUBJECT:
                    subject = v
            return _Result(_MappingRow() if subject else None)
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
    monkeypatch.setattr(oidc_auth, "get_settings", lambda: settings)

    async def fake_fetch(*, force: bool = False):
        return _jwks()

    monkeypatch.setattr(oidc_auth, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(oidc_auth, "_jwks_cache", None)
    monkeypatch.setattr(oidc_auth, "_last_forced_jwks_refetch", 0.0)
    yield settings


def test_valid_oidc_token_reaches_route_with_mapped_scope(_patch) -> None:
    token = _token(sub=MAPPED_SUBJECT)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["org_id"] == str(ORG_ID)
        assert body["workspace_id"] == str(WORKSPACE_ID)  # derived from the mapping
        assert body["is_platform"] is False
        assert body["email"] == "user@acme.example"


def test_unmapped_principal_is_403_not_fallthrough(_patch) -> None:
    token = _token(sub="unmapped-subject")
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "oidc_principal_not_mapped"


def test_wrong_audience_token_is_401_no_fallthrough(_patch) -> None:
    token = _token(aud="some-other-api", sub=MAPPED_SUBJECT)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "oidc_wrong_audience"


def test_expired_oidc_token_is_401_never_apikey_path(_patch) -> None:
    token = _token(exp_delta=-120, sub=MAPPED_SUBJECT)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "oidc_token_expired"


def test_oidc_caller_may_not_set_workspace_header(_patch) -> None:
    token = _token(sub=MAPPED_SUBJECT)
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(uuid.uuid4())}
    with SyncASGIClient(_app(), headers=headers) as client:
        r = client.get("/echo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "workspace_scope_not_permitted"


def test_unconfigured_gateway_ignores_oidc_routing(_patch) -> None:
    # With OIDC unconfigured, an OIDC-shaped token goes down the normal api-key path
    # and is rejected as an invalid key — the OIDC branch must not activate.
    _patch.oidc_issuer = ""
    token = _token(sub=MAPPED_SUBJECT)
    with SyncASGIClient(_app(), headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get("/echo")
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "invalid_api_key"
