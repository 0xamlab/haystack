"""GitHub user → engine org resolution for the website BYOK bridge.

The hard part is the personal-vs-org-install mapping: a personal install matches by slug with no
GitHub call; an org install requires an installation-token membership check, and only ACTIVE ADMINS
may manage the org key. Covers: personal match, org-admin match, non-admin denied (fail-closed),
multiple-orgs ambiguity (409), caller-level GitHub failures (App unconfigured / egress denied), and
the Redis short-circuit."""
from __future__ import annotations

import uuid

import pytest

from apps.api_server.services import byok_org_resolver as r
from apps.api_server.services import github_app_auth
from apps.api_server.services.byok_org_resolver import OrgResolutionError
from apps.api_server.services.egress_guard import EgressPolicyDeniedError


class _Org:
    def __init__(self, org_id: uuid.UUID, name: str | None = None) -> None:
        self.id = org_id
        self.name = name or f"org-{str(org_id)[:8]}"


class _Install:
    def __init__(self, installation_id: int, account_login: str, org_id: uuid.UUID) -> None:
        self.installation_id = installation_id
        self.account_login = account_login
        self.org_id = org_id
        self.account_type = "organization"
        self.suspended = False


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class _DB:
    """Returns the seeded org-installation rows for the one enumeration query; counts commits."""

    def __init__(self, install_rows):
        self._rows = install_rows
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _stmt):
        return _Result(self._rows)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _FakeRedis:
    def __init__(self, initial=None):
        self.store = dict(initial or {})

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


@pytest.fixture
def patch_helpers(monkeypatch):
    """Default: no personal install, no org rows, membership denies, org lookup maps id->._Org."""

    async def _no_personal(db, *, account_id, account_type):
        return None

    async def _org_by_id(db, org_id):
        return _Org(org_id)

    monkeypatch.setattr(r, "lookup_org_for_account", _no_personal)
    monkeypatch.setattr(r, "_org_by_id", _org_by_id)
    return monkeypatch


async def test_personal_install_matches_without_github_call(monkeypatch):
    pid = uuid.uuid4()

    async def _personal(db, *, account_id, account_type):
        assert account_id == 583231 and account_type == "user"
        return _Org(pid)

    called = {"membership": 0}

    async def _membership(*a, **k):
        called["membership"] += 1
        return {"state": "active", "role": "admin"}

    monkeypatch.setattr(r, "lookup_org_for_account", _personal)
    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    org = await r.resolve_org_for_github_user(
        _DB([]), github_user_id=583231, github_login="octocat", redis=None
    )
    assert org.id == pid
    assert called["membership"] == 0  # personal path never touches GitHub


async def test_org_admin_is_resolved(patch_helpers):
    monkeypatch = patch_helpers
    oid = uuid.uuid4()
    db = _DB([_Install(11, "acme", oid)])

    async def _membership(installation_id, org_login, username, **k):
        assert installation_id == 11 and org_login == "acme" and username == "octocat"
        return {"state": "active", "role": "admin"}

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    org = await r.resolve_org_for_github_user(
        db, github_user_id=1, github_login="octocat", redis=None
    )
    assert org.id == oid
    assert db.commits == 1  # token cold-cache persisted


async def test_org_member_non_admin_is_denied(patch_helpers):
    monkeypatch = patch_helpers
    db = _DB([_Install(11, "acme", uuid.uuid4())])

    async def _membership(*a, **k):
        return {"state": "active", "role": "member"}  # member != admin

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "no_org" and exc.value.http_status == 403


async def test_pending_membership_is_denied(patch_helpers):
    monkeypatch = patch_helpers
    db = _DB([_Install(11, "acme", uuid.uuid4())])

    async def _membership(*a, **k):
        return {"state": "pending", "role": "admin"}  # invited but not active

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "no_org"


async def test_not_a_member_returns_none_and_is_denied(patch_helpers):
    monkeypatch = patch_helpers
    db = _DB([_Install(11, "acme", uuid.uuid4())])

    async def _membership(*a, **k):
        return None  # 404 -> not a member

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "no_org"


async def test_multiple_admin_orgs_is_ambiguous(patch_helpers):
    monkeypatch = patch_helpers
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    db = _DB([_Install(11, "acme", o1), _Install(22, "globex", o2)])

    async def _membership(*a, **k):
        return {"state": "active", "role": "admin"}

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "multiple_orgs" and exc.value.http_status == 409
    # The eligible orgs come back so the caller can render a picker (id+name, name-sorted).
    assert {o["id"] for o in exc.value.orgs} == {str(o1), str(o2)}
    assert [o["name"] for o in exc.value.orgs] == sorted(o["name"] for o in exc.value.orgs)


async def test_selected_org_id_disambiguates_multiple_orgs(patch_helpers):
    monkeypatch = patch_helpers
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    db = _DB([_Install(11, "acme", o1), _Install(22, "globex", o2)])
    redis = _FakeRedis()

    async def _membership(*a, **k):
        return {"state": "active", "role": "admin"}

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    org = await r.resolve_org_for_github_user(
        db, github_user_id=1, github_login="x", redis=redis, selected_org_id=o2
    )
    assert org.id == o2
    assert redis.store.get(f"{r._CACHE_PREFIX}1") == str(o2)  # pick is cached


async def test_invalid_selected_org_id_still_ambiguous(patch_helpers):
    monkeypatch = patch_helpers
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    db = _DB([_Install(11, "acme", o1), _Install(22, "globex", o2)])

    async def _membership(*a, **k):
        return {"state": "active", "role": "admin"}

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    # A selection the caller doesn't actually administer must NOT grant access — still 409.
    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(
            db, github_user_id=1, github_login="x", redis=None, selected_org_id=uuid.uuid4()
        )
    assert exc.value.code == "multiple_orgs"


async def test_selected_org_id_bypasses_stale_cache(patch_helpers):
    monkeypatch = patch_helpers
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    db = _DB([_Install(11, "acme", o1), _Install(22, "globex", o2)])
    # Cache is pinned to o1, but the caller explicitly picks o2 — the pick must win.
    redis = _FakeRedis({f"{r._CACHE_PREFIX}1": str(o1)})

    async def _membership(*a, **k):
        return {"state": "active", "role": "admin"}

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    org = await r.resolve_org_for_github_user(
        db, github_user_id=1, github_login="x", redis=redis, selected_org_id=o2
    )
    assert org.id == o2


async def test_app_unconfigured_surfaces_503(patch_helpers):
    monkeypatch = patch_helpers
    db = _DB([_Install(11, "acme", uuid.uuid4())])

    async def _membership(*a, **k):
        raise github_app_auth.GithubAppNotConfiguredError("nope")

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "github_app_unconfigured" and exc.value.http_status == 503


async def test_egress_denied_surfaces_502(patch_helpers):
    monkeypatch = patch_helpers
    db = _DB([_Install(11, "acme", uuid.uuid4())])

    class _Decision:
        surface = "github_app_oauth"
        reason = "denied"
        egress_class = "customer_connector"

    async def _membership(*a, **k):
        raise EgressPolicyDeniedError(_Decision())

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "github_unreachable" and exc.value.http_status == 502


async def test_transient_per_org_failure_is_skipped_then_denied(patch_helpers):
    monkeypatch = patch_helpers
    db = _DB([_Install(11, "acme", uuid.uuid4())])

    async def _membership(*a, **k):
        raise RuntimeError("github 500 minting token")  # not config/egress -> skip this org

    monkeypatch.setattr(github_app_auth, "installation_membership_role", _membership)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_github_user(db, github_user_id=1, github_login="x", redis=None)
    assert exc.value.code == "no_org"  # fail-closed (degraded, not crash)


async def test_redis_cache_short_circuits(monkeypatch):
    oid = uuid.uuid4()
    redis = _FakeRedis({f"{r._CACHE_PREFIX}1": str(oid)})

    async def _org_by_id(db, org_id):
        assert org_id == oid
        return _Org(org_id)

    async def _should_not_run(*a, **k):
        raise AssertionError("personal lookup must not run on a cache hit")

    monkeypatch.setattr(r, "_org_by_id", _org_by_id)
    monkeypatch.setattr(r, "lookup_org_for_account", _should_not_run)

    org = await r.resolve_org_for_github_user(
        _DB([]), github_user_id=1, github_login="x", redis=redis
    )
    assert org.id == oid


async def test_personal_match_is_cached(patch_helpers):
    monkeypatch = patch_helpers
    pid = uuid.uuid4()
    redis = _FakeRedis()

    async def _personal(db, *, account_id, account_type):
        return _Org(pid)

    monkeypatch.setattr(r, "lookup_org_for_account", _personal)

    await r.resolve_org_for_github_user(_DB([]), github_user_id=7, github_login="x", redis=redis)
    assert redis.store.get(f"{r._CACHE_PREFIX}7") == str(pid)


# ── GitHub identity with NO App installation: lazy personal org (checkout unblock) ──────────


async def test_github_no_install_auto_provisions_personal_org(patch_helpers):
    """A "Continue with GitHub" user with no App install must still resolve to an org when
    auto-provision is on — otherwise they can never check out (403 at /account/billing/*)."""
    monkeypatch = patch_helpers
    provisioned = _Org(uuid.uuid4(), name="sb-user-uid-1")

    async def _no_link(db, supabase_uid):
        return None

    async def _gh_no_org(db, **kwargs):
        raise OrgResolutionError("no_org", "no install", http_status=403)

    async def _provision(db, *, supabase_uid, email=None):
        return provisioned

    async def _link(db, *, supabase_uid, org_id):
        return org_id

    monkeypatch.setattr(r, "_org_for_identity_link", _no_link)
    monkeypatch.setattr(r, "resolve_org_for_github_user", _gh_no_org)
    monkeypatch.setattr(r, "provision_org_for_supabase_uid", _provision)
    monkeypatch.setattr(r, "ensure_identity_link", _link)

    org = await r.resolve_org_for_supabase_user(
        _DB([]), supabase_uid="uid-1", github_user_id=7, auto_provision=True
    )
    assert org.id == provisioned.id


async def test_github_no_install_without_auto_provision_still_403s(patch_helpers):
    monkeypatch = patch_helpers

    async def _no_link(db, supabase_uid):
        return None

    async def _gh_no_org(db, **kwargs):
        raise OrgResolutionError("no_org", "no install", http_status=403)

    monkeypatch.setattr(r, "_org_for_identity_link", _no_link)
    monkeypatch.setattr(r, "resolve_org_for_github_user", _gh_no_org)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_supabase_user(
            _DB([]), supabase_uid="uid-1", github_user_id=7, auto_provision=False
        )
    assert exc.value.code == "no_org"


async def test_github_non_no_org_errors_are_not_swallowed(patch_helpers):
    """Only a fresh 'no_org' falls through to provisioning — ambiguity (409) must surface."""
    monkeypatch = patch_helpers

    async def _no_link(db, supabase_uid):
        return None

    async def _gh_ambiguous(db, **kwargs):
        raise OrgResolutionError("multiple_orgs", "pick one", http_status=409)

    monkeypatch.setattr(r, "_org_for_identity_link", _no_link)
    monkeypatch.setattr(r, "resolve_org_for_github_user", _gh_ambiguous)

    with pytest.raises(OrgResolutionError) as exc:
        await r.resolve_org_for_supabase_user(
            _DB([]), supabase_uid="uid-1", github_user_id=7, auto_provision=True
        )
    assert exc.value.code == "multiple_orgs"


# ── Stale identity link: a removed member must stop resolving the org ────────────


async def test_stale_link_removed_member_falls_through(patch_helpers):
    """A non-GitHub identity whose email has NO active seat in the linked org is a
    removed member — the link is stale, so resolution falls through to provisioning
    a fresh personal org instead of honoring the dead link."""
    monkeypatch = patch_helpers
    dead_org = _Org(uuid.uuid4(), name="ex-team-org")
    fresh = _Org(uuid.uuid4(), name="sb-user-fresh")

    async def _linked(db, supabase_uid):
        return dead_org

    async def _no_seat(db, org, *, email, github_user_id):
        return False  # no active User row → stale

    async def _provision(db, *, supabase_uid, email=None):
        return fresh

    async def _link(db, *, supabase_uid, org_id):
        return org_id

    monkeypatch.setattr(r, "_org_for_identity_link", _linked)
    monkeypatch.setattr(r, "_link_still_valid", _no_seat)
    monkeypatch.setattr(r, "provision_org_for_supabase_uid", _provision)
    monkeypatch.setattr(r, "ensure_identity_link", _link)

    org = await r.resolve_org_for_supabase_user(
        _DB([]), supabase_uid="uid-removed", email="ex@member.com", auto_provision=True
    )
    assert org.id == fresh.id  # NOT dead_org — the stale link was skipped


async def test_valid_link_active_member_is_honored(patch_helpers):
    """A still-active member's link resolves the org normally (no regression)."""
    monkeypatch = patch_helpers
    org_row = _Org(uuid.uuid4(), name="team-org")

    async def _linked(db, supabase_uid):
        return org_row

    async def _has_seat(db, org, *, email, github_user_id):
        return True

    monkeypatch.setattr(r, "_org_for_identity_link", _linked)
    monkeypatch.setattr(r, "_link_still_valid", _has_seat)

    org = await r.resolve_org_for_supabase_user(
        _DB([]), supabase_uid="uid-active", email="active@member.com"
    )
    assert org.id == org_row.id
