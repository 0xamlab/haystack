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
from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.models.user import User, UserRole
from apps.api_server.services import byok_org_resolver, github_app_auth, supabase_auth
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


class _Install:
    def __init__(self, installation_id, *, org_id=None, login="acme", type_="organization", suspended=False):
        self.installation_id = installation_id
        self.org_id = org_id
        self.account_login = login
        self.account_type = type_
        self.suspended = suspended


class _FakeResult:
    """Serves both shapes this router uses: .scalar_one_or_none() (membership lookup) and
    .scalars().all() (installation rows)."""

    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


def _bound_org_ids(query) -> set[str]:
    """Every org-id value actually bound into this query's WHERE clause."""
    try:
        params = query.compile(compile_kwargs={"literal_binds": False}).params
    except Exception:  # noqa: BLE001 — a query shape we don't need to introspect
        return set()
    return {str(v) for k, v in params.items() if "org_id" in k and v is not None}


class _FakeDb:
    """Answers the membership lookup with `member_row` and the installation query with
    `installs`.

    Two deliberate strictnesses, both of which caught real holes in an earlier version:

    1. Dispatch is on the query's TARGET ENTITY, not on `str(query)`. Compiling a Select and
       substring-matching a table name is brittle both ways — an unrelated query joining the
       table would misroute, and a table rename would send everything down the membership
       branch, making these tests pass vacuously. An unrecognized target raises.

    2. The installation query MUST be org-scoped, and rows are filtered by that bound org id
       rather than returned wholesale. Without this, deleting
       ``.where(GithubAppInstallation.org_id == org.id)`` from the router left all 10 tests
       green — i.e. nothing pinned tenancy on a surface that both READS other orgs' install
       metadata and DELETES rows it judges dead. Given this repo's cross-tenant audit history,
       that scoping is exactly what must be un-removable."""

    def __init__(self, member_row=None, installs=None):
        self._member_row = member_row
        self._installs = list(installs or [])
        self.commits = 0
        self.deleted: list[object] = []

    async def execute(self, query):
        entities = [d.get("entity") for d in getattr(query, "column_descriptions", [])]
        if GithubAppInstallation in entities:
            scoped = _bound_org_ids(query)
            if not scoped:
                raise AssertionError(
                    "the installation query is NOT org-scoped — it would read (and prune) "
                    "other tenants' GitHub App installations"
                )
            return _FakeResult(
                rows=[
                    i
                    for i in self._installs
                    if i not in self.deleted and str(i.org_id) in scoped
                ]
            )
        if User in entities:
            return _FakeResult(value=self._member_row)
        raise AssertionError(f"unexpected query target: {entities}")

    async def delete(self, obj):
        self.deleted.append(obj)

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


def _stub_app_configured(monkeypatch, configured=True):
    monkeypatch.setattr(github_app_auth, "app_configured", lambda: configured)


def _stub_liveness(monkeypatch, result):
    """result: True (live) / False (404, prune) / None (unverifiable) or a dict by id."""

    async def _live(installation_id, *, org_id=None, redis=None):
        return result[installation_id] if isinstance(result, dict) else result

    monkeypatch.setattr(github_app_auth, "installation_is_live", _live)


def test_get_account_settings_no_install_is_not_connected(monkeypatch):
    """The regression this endpoint exists for: an org resolves (identity link / email
    membership / CLI onboard) while having NO GitHub App install. The account page used to
    call that "Connected via GitHub" purely because an org came back."""
    org = _Org(uuid.uuid4(), name="Acme", codna_fix_enabled=False)
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _stub_app_configured(monkeypatch)
    _overrides(_FakeDb(installs=[]))
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "org_id": str(org.id),
        "org_name": "Acme",
        "codna_fix_enabled": False,
        "github_installations": [],
        "github_connected": False,
    }
    assert resp.headers.get("cache-control") == "no-store"


def test_get_account_settings_live_install_is_connected(monkeypatch):
    org = _Org(uuid.uuid4())
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _stub_app_configured(monkeypatch)
    _stub_liveness(monkeypatch, True)
    db = _FakeDb(installs=[_Install(999, org_id=org.id, login="acme")])
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    body = resp.json()
    assert body["github_connected"] is True
    assert body["github_installations"] == [
        {
            "installation_id": 999,
            "account_login": "acme",
            "account_type": "organization",
            "suspended": False,
        }
    ]
    assert db.deleted == []  # a live install is never pruned


def test_get_account_settings_prunes_uninstalled_row(monkeypatch):
    """The second half of the reported bug: this backend never sees the codna-ai App's
    installation.deleted (those webhooks go to codna's own service), so an uninstall leaves
    the row behind forever. A definitive 404 from GitHub must prune it and report disconnected."""
    org = _Org(uuid.uuid4())
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _stub_app_configured(monkeypatch)
    _stub_liveness(monkeypatch, False)  # GitHub 404 -> definitively gone
    dead = _Install(154718623, org_id=org.id)
    db = _FakeDb(installs=[dead])
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    body = resp.json()
    assert body["github_connected"] is False
    assert body["github_installations"] == []
    assert db.deleted == [dead]  # self-healed
    assert db.commits == 1


def test_get_account_settings_unverifiable_fails_open(monkeypatch):
    """GitHub unreachable / egress denied must NOT be reported as "you uninstalled it", and
    must never prune a row we could not actually disprove."""
    org = _Org(uuid.uuid4())
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _stub_app_configured(monkeypatch)
    _stub_liveness(monkeypatch, None)  # unknown
    row = _Install(777, org_id=org.id)
    db = _FakeDb(installs=[row])
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    body = resp.json()
    assert body["github_connected"] is True
    assert db.deleted == []
    assert db.commits == 0


def test_get_account_settings_suspended_install_is_not_connected(monkeypatch):
    org = _Org(uuid.uuid4())
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _stub_app_configured(monkeypatch)
    _stub_liveness(monkeypatch, True)
    db = _FakeDb(installs=[_Install(555, org_id=org.id, suspended=True)])
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    body = resp.json()
    assert body["github_connected"] is False  # present but suspended != usable
    assert len(body["github_installations"]) == 1


def test_get_account_settings_app_unconfigured_skips_github(monkeypatch):
    """With the App unconfigured there is no JWT to verify with -- report the rows as-is
    rather than pruning everything on an unverifiable answer."""
    org = _Org(uuid.uuid4())
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, org)
    _stub_app_configured(monkeypatch, configured=False)

    async def _boom(*_a, **_k):
        raise AssertionError("must not call GitHub when the App is unconfigured")

    monkeypatch.setattr(github_app_auth, "installation_is_live", _boom)
    db = _FakeDb(installs=[_Install(321, org_id=org.id)])
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    assert resp.json()["github_connected"] is True
    assert db.deleted == []


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


# ── cross-tenant isolation ─────────────────────────────────────────────────────
# This surface both READS install metadata (installation_id / account_login of a GitHub org)
# and DELETES rows it judges dead, so its org scoping is security-relevant, not cosmetic.
# Before these, removing `.where(GithubAppInstallation.org_id == org.id)` from the router left
# every test green.
def test_get_account_settings_never_reports_another_orgs_install(monkeypatch):
    mine = _Org(uuid.uuid4(), name="Mine")
    other_org_id = uuid.uuid4()
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, mine)
    _stub_app_configured(monkeypatch)
    _stub_liveness(monkeypatch, True)
    db = _FakeDb(
        installs=[
            _Install(1001, org_id=other_org_id, login="someone-elses-gh-org"),
        ]
    )
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    body = resp.json()
    assert body["github_installations"] == []
    assert body["github_connected"] is False
    assert "someone-elses-gh-org" not in resp.text  # no leakage of another tenant's GH org


def test_get_account_settings_prune_never_deletes_another_orgs_row(monkeypatch):
    """A 404 for MY install must never take out someone else's row."""
    mine = _Org(uuid.uuid4(), name="Mine")
    other_org_id = uuid.uuid4()
    _stub_auth(monkeypatch)
    _stub_resolve(monkeypatch, mine)
    _stub_app_configured(monkeypatch)
    _stub_liveness(monkeypatch, False)  # everything we're allowed to see is gone
    my_dead = _Install(2002, org_id=mine.id)
    their_row = _Install(3003, org_id=other_org_id)
    db = _FakeDb(installs=[my_dead, their_row])
    _overrides(db)
    try:
        with SyncASGIClient(app) as client:
            resp = client.get("/account/settings", headers={"authorization": "Bearer JWT"})
    finally:
        app.dependency_overrides.clear()
    assert resp.json()["github_connected"] is False
    assert db.deleted == [my_dead]
    assert their_row not in db.deleted
