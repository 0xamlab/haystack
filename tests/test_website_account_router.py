"""Website account settings router (GET/PATCH /account/settings) — Supabase-authenticated.

This is the Supabase-auth twin of /v1/me's org-settings slice, added because /v1/me itself is
API-key-only (get_current_org) and the website never held one of those: every "connect GitHub" /
"toggle automatic fixes" call from the account page carries a raw Supabase access_token, which
get_current_org always rejected with a generic invalid_api_key 401. That 401 was silent in the
UI (getCodnaFixEnabled() falls back to a permissive default; setCodnaFixEnabled() showed a
generic error) -- these tests pin the new route's actual contract."""
from __future__ import annotations

import uuid

from apps.api_server.db.session import get_db
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.user import UserRole
from apps.api_server.services import byok_org_resolver, supabase_auth
from tests._asgi_client import SyncASGIClient

_IDENT = {
    "supabase_uid": "sb-uuid-octocat",
    "github_user_id": 583231,
    "github_login": "octocat",
    "email": "octocat@example.com",
    "provider": "github",
}


class _Org:
    def __init__(self, org_id, *, name="Acme", codna_fix_enabled=True):
        self.id = org_id
        self.name = name
        self.codna_fix_enabled = codna_fix_enabled


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDb:
    """Only what _require_org_admin's membership lookup + the PATCH's commit need."""

    def __init__(self, member_row=None):
        self._member_row = member_row
        self.commits = 0

    async def execute(self, _query):
        return _FakeResult(self._member_row)

    async def commit(self):
        self.commits += 1


def _overrides(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: object()


def _stub_auth(monkeypatch, *, configured=True, identity=None):
    monkeypatch.setattr(supabase_auth, "supabase_configured", lambda: configured)

    async def _verify(token):
        assert token == "JWT"
        return {"verified": True}

    monkeypatch.setattr(supabase_auth, "verify_supabase_jwt", _verify)
    monkeypatch.setattr(supabase_auth, "extract_identity", lambda claims: identity or _IDENT)


def _stub_resolve(monkeypatch, org):
    async def _resolve(db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):
        return org

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)


def test_get_account_settings_happy_path(monkeypatch):
    org = _Org(uuid.uuid4(), name="Acme", codna_fix_enabled=False)
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _overrides(_FakeDb())
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"org_id": str(org.id), "org_name": "Acme", "codna_fix_enabled": False}
    assert resp.headers.get("cache-control") == "no-store"


def test_get_account_settings_missing_bearer_is_401(monkeypatch):
    _stub_auth(monkeypatch)
    _overrides(_FakeDb())
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 401


def test_patch_account_settings_admin_updates_toggle(monkeypatch):
    org = _Org(uuid.uuid4(), codna_fix_enabled=True)
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    owner_row = type("Row", (), {"role": UserRole.OWNER})()
    db = _FakeDb(member_row=owner_row)
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.request(
                "PATCH",
                "/account/settings",
                json={"codna_fix_enabled": False},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["codna_fix_enabled"] is False
    assert org.codna_fix_enabled is False
    assert db.commits == 1


def test_patch_account_settings_member_forbidden(monkeypatch):
    org = _Org(uuid.uuid4(), codna_fix_enabled=True)
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    member_row = type("Row", (), {"role": UserRole.MEMBER})()
    db = _FakeDb(member_row=member_row)
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.request(
                "PATCH",
                "/account/settings",
                json={"codna_fix_enabled": False},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    # Unauthorized -- must never mutate the org.
    assert org.codna_fix_enabled is True
    assert db.commits == 0


def test_patch_account_settings_row_less_admin_passes(monkeypatch):
    """No Users row for this email in this org -- a GitHub-install admin resolution (the only
    row-less path), which already proves admin, same as website_team.py's gate."""
    org = _Org(uuid.uuid4(), codna_fix_enabled=True)
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    db = _FakeDb(member_row=None)
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.request(
                "PATCH",
                "/account/settings",
                json={"codna_fix_enabled": False},
                headers={"authorization": "Bearer JWT"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert org.codna_fix_enabled is False
