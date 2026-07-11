"""Top-level /byok router (website / Supabase-authenticated BYOK).

The verifier + resolver have their own unit tests; here we pin the ROUTER contract: bearer
extraction, the inert-until-configured 503, the auth → resolve → store delegation + payload mapping
(provider/key → api_backend/api_key), and the error-status mapping (401 / resolver http_status /
TenantKeyError 409|400). External calls are stubbed so the test is hermetic."""
from __future__ import annotations

import uuid

from apps.api_server.db.session import get_db
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_redis
from apps.api_server.services import byok_org_resolver, supabase_auth
from apps.api_server.services import tenant_key_management as tk_mgmt
from apps.api_server.services.byok_org_resolver import OrgResolutionError
from tests._asgi_client import SyncASGIClient

_IDENT = {
    "supabase_uid": "sb-uuid-octocat",
    "github_user_id": 583231,
    "github_login": "octocat",
    "email": "octocat@example.com",
    "provider": "github",
}


class _Org:
    def __init__(self, org_id):
        self.id = org_id


def _overrides():
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_redis] = lambda: object()


def _stub_auth(monkeypatch, *, configured=True, identity=None):
    monkeypatch.setattr(supabase_auth, "supabase_configured", lambda: configured)

    async def _verify(token):
        assert token == "JWT"
        return {"verified": True}

    monkeypatch.setattr(supabase_auth, "verify_supabase_jwt", _verify)
    # verify_identity now uses the provider-agnostic extractor; keep the github one patched too.
    monkeypatch.setattr(supabase_auth, "extract_identity", lambda claims: identity or _IDENT)
    monkeypatch.setattr(
        supabase_auth, "extract_github_identity", lambda claims: identity or _IDENT
    )


def test_post_byok_happy_path_stores_mapped_key(monkeypatch):
    org_id = uuid.uuid4()
    _stub_auth(monkeypatch)

    async def _resolve(db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):
        assert github_user_id == 583231 and github_login == "octocat"
        return _Org(org_id)

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)

    captured = {}

    async def _set(db, *, org_id, api_backend, api_key, actor_email):
        captured.update(
            org_id=org_id, api_backend=api_backend, api_key=api_key, actor_email=actor_email
        )
        return False

    monkeypatch.setattr(tk_mgmt, "set_org_key", _set)

    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "anthropic", "key": "sk-ant-SECRET"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    assert captured == {
        "org_id": org_id,
        "api_backend": "anthropic",  # provider -> api_backend
        "api_key": "sk-ant-SECRET",  # key -> api_key
        "actor_email": "octocat@example.com",
    }
    # The raw key never appears in the response body.
    assert "sk-ant-SECRET" not in resp.text
    # A key-management mutation must never be cached by an intermediary.
    assert resp.headers.get("cache-control") == "no-store"


def test_post_byok_jwks_unreachable_is_503(monkeypatch):
    # A JWKS/service failure is the engine's problem (503), not a bad token (401).
    monkeypatch.setattr(supabase_auth, "supabase_configured", lambda: True)

    async def _verify(token):
        raise supabase_auth.SupabaseAuthError("jwks_unreachable", "no jwks")

    monkeypatch.setattr(supabase_auth, "verify_supabase_jwt", _verify)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "anthropic", "key": "sk"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "jwks_unreachable"


def test_post_byok_missing_bearer_is_401(monkeypatch):
    _stub_auth(monkeypatch)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post("/byok", json={"provider": "anthropic", "key": "sk"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "missing_bearer"


def test_post_byok_supabase_unconfigured_is_503(monkeypatch):
    _stub_auth(monkeypatch, configured=False)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "anthropic", "key": "sk"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "supabase_not_configured"


def test_post_byok_invalid_jwt_is_401(monkeypatch):
    monkeypatch.setattr(supabase_auth, "supabase_configured", lambda: True)

    async def _verify(token):
        raise supabase_auth.SupabaseAuthError("invalid_token", "bad")

    monkeypatch.setattr(supabase_auth, "verify_supabase_jwt", _verify)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "anthropic", "key": "sk"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_token"


def test_post_byok_resolution_error_maps_status(monkeypatch):
    _stub_auth(monkeypatch)

    async def _resolve(db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):
        raise OrgResolutionError("no_org", "none", http_status=403)

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "anthropic", "key": "sk"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "no_org"


def test_post_byok_encryption_required_is_409(monkeypatch):
    _stub_auth(monkeypatch)

    async def _resolve(db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):
        return _Org(uuid.uuid4())

    async def _set(db, **k):
        raise tk_mgmt.TenantKeyError("encryption_key_required", "need KEK")

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)
    monkeypatch.setattr(tk_mgmt, "set_org_key", _set)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "anthropic", "key": "sk"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "encryption_key_required"


def test_post_byok_rejects_engine_backend(monkeypatch):
    # The reserved engine key must NOT be manageable from the public website surface.
    _stub_auth(monkeypatch)

    async def _resolve(db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):
        raise AssertionError("must reject the engine backend before resolving an org")

    async def _set(db, **k):
        raise AssertionError("must never reach the key store for the engine backend")

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)
    monkeypatch.setattr(tk_mgmt, "set_org_key", _set)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/byok",
                json={"provider": "engine", "key": "sk"},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_backend"


def test_delete_byok_is_idempotent_204(monkeypatch):
    org_id = uuid.uuid4()
    _stub_auth(monkeypatch)

    async def _resolve(db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):
        return _Org(org_id)

    captured = {}

    async def _delete(db, *, org_id, api_backend, actor_email):
        captured.update(org_id=org_id, api_backend=api_backend)
        return False  # nothing to delete -> still 204

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)
    monkeypatch.setattr(tk_mgmt, "delete_org_key", _delete)
    _overrides()
    try:
        with SyncASGIClient(app) as client:
            resp = client.delete("/byok", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 204
    assert captured == {"org_id": org_id, "api_backend": "anthropic"}
