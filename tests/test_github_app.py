"""GitHub App (codna) — unit tests for the inbound webhook, installation-token minter,
worker dispatch, and install callback.

Fake-session style (mirrors test_repository_job_service.py): no real DB, GitHub mocked.
These run in CI under `test:hardening`. End-to-end (real install + real GitHub) is gated
on owner infra and is out of scope here.

Note: the webhook no longer turns GitHub events into fix-PR jobs (see
apps/api_server/routers/github_webhooks.py's module docstring) — the real codna-ai App's
event handling lives entirely in the separate `codna` repo's own webhook service. This
backend only tracks installation lifecycle + the install/OAuth callback.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.models.job import JobKind
from apps.api_server.routers import github_webhooks as ghwh
from apps.api_server.services import github_app_auth
from apps.api_server.services import repository_job_service as rjs
from apps.api_server.services import tenant_key_store

_SECRET = "whsec_test_secret"


async def _async_none(*_args, **_kwargs):
    return None


# ── tenant-key store: default empty so the worker key-bind never touches a real DB ──
class _StoreResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _StoreSession:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def execute(self, _q):
        return _StoreResult(self._rows)


@pytest.fixture(autouse=True)
def _empty_tenant_store(monkeypatch):
    tenant_key_store.invalidate_org_keys()
    monkeypatch.setattr(tenant_key_store, "AsyncSessionLocal", lambda: _StoreSession([]))
    yield
    tenant_key_store.invalidate_org_keys()


# ── fakes ───────────────────────────────────────────────────────────────────
class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """Returns pre-seeded query results in order; records adds/commits. No real DB."""

    def __init__(self, values):
        self._values = list(values)
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0

    async def execute(self, _query):
        return _FakeResult(self._values.pop(0) if self._values else None)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass

    async def refresh(self, _obj):
        pass


class _FakeRedis:
    def __init__(self, *, set_returns=None, get_value=None):
        self._set_returns = list(set_returns or [])
        self._get_value = get_value
        self.sets: list[tuple] = []

    async def set(self, key, val, **kw):
        self.sets.append((key, val, kw))
        return self._set_returns.pop(0) if self._set_returns else True

    async def get(self, _key):
        return self._get_value

    async def delete(self, *_keys):
        return 1


class _FakeRequest:
    def __init__(self, body: bytes, redis=None):
        self._body = body
        self.app = SimpleNamespace(state=SimpleNamespace(redis=redis))

    async def body(self) -> bytes:
        return self._body


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _configure(monkeypatch, *, secret: str | None = _SECRET, configured: bool = True):
    monkeypatch.setattr(ghwh, "app_configured", lambda: configured)
    monkeypatch.setattr(
        ghwh,
        "get_settings",
        lambda: SimpleNamespace(github_app_webhook_secret=secret, github_app_slug="codna"),
    )


def _install_row(org_id=None, *, suspended=False):
    return SimpleNamespace(
        org_id=org_id or uuid.uuid4(),
        installation_id=12345,
        suspended=suspended,
        encrypted_access_token=None,
        token_expires_at=None,
    )


def _check_payload():
    return {
        "action": "completed",
        "check_suite": {"conclusion": "failure", "head_sha": "abc123", "head_branch": "main"},
        "installation": {"id": 12345},
        "repository": {"full_name": "octo/repo", "clone_url": "https://github.com/octo/repo.git",
                       "default_branch": "main"},
    }


# ── webhook route ──────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_webhook_actionable_looking_event_is_ignored(monkeypatch):
    """Events that used to spawn a fix-PR job (check_suite, issues+label, pull_request_review)
    are now simply acked + ignored — this backend no longer processes them at all."""
    _configure(monkeypatch)
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row()])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="d-1",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body) == {"status": "ignored", "event": "check_suite"}
    assert not db.added


@pytest.mark.anyio
async def test_webhook_bad_signature_401(monkeypatch):
    _configure(monkeypatch)
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row()])
    req = _FakeRequest(body)
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_webhook(
            req, db, x_github_event="check_suite",
            x_hub_signature_256="sha256=deadbeef", x_github_delivery="d-2",
        )
    assert exc.value.status_code == 401
    assert not db.added  # nothing enqueued


@pytest.mark.anyio
async def test_webhook_not_configured_404(monkeypatch):
    _configure(monkeypatch, secret=None, configured=False)
    body = b"{}"
    req = _FakeRequest(body)
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_webhook(
            req, _FakeSession([]), x_github_event="check_suite",
            x_hub_signature_256=_sign(body), x_github_delivery="d",
        )
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_webhook_unknown_installation_acked(monkeypatch):
    _configure(monkeypatch)
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([None])  # no installation row
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="d-3",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body)["reason"] == "unknown installation"
    assert not db.added


@pytest.mark.anyio
async def test_webhook_suspended_installation_acked(monkeypatch):
    _configure(monkeypatch)
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row(suspended=True)])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="d-3b",
    )
    assert resp.status_code == 202
    assert not db.added


# ── internal engine-key endpoint (the account-linking bridge to codna-webhook) ────────────────
def _configure_engine_key(monkeypatch, *, secret: str | None = "shh"):
    monkeypatch.setattr(
        ghwh, "get_settings",
        lambda: SimpleNamespace(codna_webhook_internal_secret=secret),
    )


@pytest.mark.anyio
async def test_engine_key_not_configured_404(monkeypatch):
    _configure_engine_key(monkeypatch, secret=None)
    with pytest.raises(HTTPException) as exc:
        await ghwh.codna_webhook_engine_key(_FakeSession([]), installation_id=12345, authorization="Bearer shh")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_engine_key_missing_auth_401(monkeypatch):
    _configure_engine_key(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await ghwh.codna_webhook_engine_key(_FakeSession([]), installation_id=12345, authorization=None)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_engine_key_wrong_auth_401(monkeypatch):
    _configure_engine_key(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await ghwh.codna_webhook_engine_key(
            _FakeSession([]), installation_id=12345, authorization="Bearer wrong-secret",
        )
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_engine_key_unresolvable_installation_404(monkeypatch):
    """Unknown installation now attempts self-provisioning first (see below) -- this covers the
    case where even the App-JWT lookup can't resolve it (e.g. GitHub-side hiccup, or the
    installation was genuinely removed), which still 404s."""
    _configure_engine_key(monkeypatch)
    monkeypatch.setattr(github_app_auth, "resolve_installation_account", _async_none)
    with pytest.raises(HTTPException) as exc:
        await ghwh.codna_webhook_engine_key(
            _FakeSession([None]), installation_id=12345, authorization="Bearer shh",
        )
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_engine_key_self_provisions_unknown_installation(monkeypatch):
    """The webhook install-first path (installation: created) can never fire for any real
    installer -- codna-ai's one configured webhook URL points at codna-webhook, not here. So an
    unknown installation must self-provision right here, from the same App-JWT-resolved account
    the webhook path would have used, instead of permanently 404ing every fresh external install."""
    _configure_engine_key(monkeypatch)
    org = SimpleNamespace(id=uuid.uuid4())

    async def _fake_resolve(_installation_id):
        return {"id": 999, "login": "acme-corp", "type": "organization"}

    async def _fake_provision(_db, **_kw):
        return org

    monkeypatch.setattr(github_app_auth, "resolve_installation_account", _fake_resolve)
    monkeypatch.setattr(ghwh, "provision_or_lookup_org_for_installation", _fake_provision)

    db = _FakeSession([None])  # initial lookup: no existing row
    resp = await ghwh.codna_webhook_engine_key(db, installation_id=12345, authorization="Bearer shh")
    assert resp.status_code == 200
    payload = json.loads(resp.body)
    assert payload["org_id"] == str(org.id)
    assert payload["engine_key"]
    # both the new GithubAppInstallation binding and the fresh service APIKey were added
    assert len(db.added) == 2
    installation_row = next(o for o in db.added if isinstance(o, ghwh.GithubAppInstallation))
    assert installation_row.installation_id == 12345
    assert installation_row.org_id == org.id
    key = next(o for o in db.added if isinstance(o, ghwh.APIKey))
    assert key.org_id == org.id
    assert key.is_service is True


@pytest.mark.anyio
async def test_engine_key_suspended_installation_404(monkeypatch):
    _configure_engine_key(monkeypatch)
    db = _FakeSession([_install_row(suspended=True)])
    with pytest.raises(HTTPException) as exc:
        await ghwh.codna_webhook_engine_key(db, installation_id=12345, authorization="Bearer shh")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_engine_key_mints_fresh_short_lived_service_key(monkeypatch):
    _configure_engine_key(monkeypatch)
    org = uuid.uuid4()
    db = _FakeSession([_install_row(org)])
    resp = await ghwh.codna_webhook_engine_key(db, installation_id=12345, authorization="Bearer shh")
    assert resp.status_code == 200
    payload = json.loads(resp.body)
    assert payload["org_id"] == str(org)
    assert payload["engine_key"]  # a raw, usable key was returned
    assert len(db.added) == 1
    key = db.added[0]
    assert key.org_id == org
    assert key.is_service is True
    assert key.user_id is None
    assert key.hashed_key != payload["engine_key"]  # never the raw value, only its hash
    assert key.expires_at is not None  # short-lived, not a standing credential


@pytest.mark.anyio
async def test_webhook_installation_created_provisions_org(monkeypatch):
    """INSTALL-FIRST via webhook: installation.created with no codna org mints one and binds it,
    BEFORE the unknown-installation drop."""
    _configure(monkeypatch)

    async def _resolve(iid, *, org_id=None):
        return {"id": 9999, "login": "acme", "type": "organization"}

    monkeypatch.setattr(ghwh.github_app_auth, "resolve_installation_account", _resolve)
    body = json.dumps({"action": "created", "installation": {"id": 12345}}).encode()
    # row lookup -> None (no binding yet); provision SELECT-by-slug -> None (mint)
    db = _FakeSession([None, None])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="installation",
        x_hub_signature_256=_sign(body), x_github_delivery="d-created",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body).get("provisioned") is True
    kinds = [type(o).__name__ for o in db.added]
    assert kinds.count("Organization") == 1
    assert kinds.count("GithubAppInstallation") == 1


@pytest.mark.anyio
async def test_webhook_installation_created_account_unresolved_ignored(monkeypatch):
    """If the App JWT can't resolve the account, ack + ignore (don't mint a junk org)."""
    _configure(monkeypatch)

    async def _resolve(iid, *, org_id=None):
        return None

    monkeypatch.setattr(ghwh.github_app_auth, "resolve_installation_account", _resolve)
    body = json.dumps({"action": "created", "installation": {"id": 12345}}).encode()
    db = _FakeSession([None])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="installation",
        x_hub_signature_256=_sign(body), x_github_delivery="d-unres",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body)["reason"] == "account unresolved"
    assert not db.added


@pytest.mark.anyio
async def test_webhook_installation_deleted_removes_binding(monkeypatch):
    _configure(monkeypatch)
    row = _install_row()
    body = json.dumps({"action": "deleted", "installation": {"id": 12345}}).encode()
    db = _FakeSession([row])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="installation",
        x_hub_signature_256=_sign(body), x_github_delivery="d-del",
    )
    assert resp.status_code == 202
    # uninstall frees the binding so the installation can later be linked to a different org
    assert db.deleted == [row]


@pytest.mark.anyio
async def test_webhook_installation_suspend_sets_flag(monkeypatch):
    _configure(monkeypatch)
    row = _install_row()
    body = json.dumps({"action": "suspend", "installation": {"id": 12345}}).encode()
    db = _FakeSession([row])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="installation",
        x_hub_signature_256=_sign(body), x_github_delivery="d-susp",
    )
    assert resp.status_code == 202
    assert row.suspended is True
    assert db.deleted == []


@pytest.mark.anyio
async def test_webhook_installation_unsuspend_clears(monkeypatch):
    _configure(monkeypatch)
    row = _install_row(suspended=True)
    body = json.dumps({"action": "unsuspend", "installation": {"id": 12345}}).encode()
    db = _FakeSession([row])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="installation",
        x_hub_signature_256=_sign(body), x_github_delivery="d-unsusp",
    )
    assert resp.status_code == 202
    assert row.suspended is False


@pytest.mark.anyio
async def test_webhook_non_actionable_event_acked(monkeypatch):
    _configure(monkeypatch)
    body = json.dumps({"action": "opened", "installation": {"id": 12345},
                       "repository": {"full_name": "o/r"}}).encode()
    db = _FakeSession([_install_row()])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="pull_request",
        x_hub_signature_256=_sign(body), x_github_delivery="d-pr",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body)["status"] == "ignored"
    assert not db.added


# ── install start (2E) ──────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_install_start_requires_admin(monkeypatch):
    _configure(monkeypatch)
    auth = {"org_id": uuid.uuid4(), "role": "member"}
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_install_start(_FakeRequest(b"", redis=_FakeRedis()), auth)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_install_start_admin_redirects(monkeypatch):
    _configure(monkeypatch)
    redis = _FakeRedis()
    auth = {"org_id": uuid.uuid4(), "role": "owner"}
    resp = await ghwh.github_install_start(_FakeRequest(b"", redis=redis), auth)
    assert resp.status_code in (302, 307)
    assert redis.sets  # a single-use state nonce was stored


# ── install callback (2E) ───────────────────────────────────────────────────────
def _verify_ok(monkeypatch, ok=True):
    monkeypatch.setattr(ghwh, "app_configured", lambda: True)

    async def _verify(installation_id, code, *, org_id):
        # Success now returns the trusted account dict; failure returns None.
        return {"id": 1234, "login": "acme", "type": "organization"} if ok else None

    monkeypatch.setattr(
        ghwh.github_app_auth, "verify_user_administers_installation", _verify
    )


@pytest.mark.anyio
async def test_install_callback_binds_verified_org(monkeypatch):
    _verify_ok(monkeypatch)
    org = uuid.uuid4()
    redis = _FakeRedis(get_value=str(org))
    db = _FakeSession([None])  # no existing row
    resp = await ghwh.github_install_callback(
        _FakeRequest(b"", redis=redis), db, installation_id=999, code="oauthcode", state="st-1",
    )
    assert resp.status_code in (302, 307)
    assert len(db.added) == 1
    assert db.added[0].installation_id == 999
    assert db.added[0].org_id == org


@pytest.mark.anyio
async def test_install_callback_unverified_403(monkeypatch):
    """An attacker-supplied installation_id the OAuth user does not administer is rejected."""
    _verify_ok(monkeypatch, ok=False)
    redis = _FakeRedis(get_value=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_install_callback(
            _FakeRequest(b"", redis=redis), _FakeSession([]),
            installation_id=999, code="c", state="s",
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_install_callback_no_cross_org_rebind_409(monkeypatch):
    """An installation already linked to another org cannot be silently re-homed."""
    _verify_ok(monkeypatch)
    existing = _install_row(uuid.uuid4())  # bound to some OTHER org
    redis = _FakeRedis(get_value=str(uuid.uuid4()))  # a different org starts the bind
    db = _FakeSession([existing])
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_install_callback(
            _FakeRequest(b"", redis=redis), db, installation_id=12345, code="c", state="s",
        )
    assert exc.value.status_code == 409
    assert not db.added


@pytest.mark.anyio
async def test_install_callback_expired_state_400(monkeypatch):
    """A SUPPLIED state that's unknown/expired still 400s (don't fall through to install-first)."""
    _verify_ok(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_install_callback(
            _FakeRequest(b"", redis=_FakeRedis(get_value=None)), _FakeSession([]),
            installation_id=999, code="c", state="stale-nonce",
        )
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_install_callback_install_first_provisions_and_binds(monkeypatch):
    """INSTALL-FIRST: no state nonce => mint an org from the verified account and bind."""
    _verify_ok(monkeypatch)  # verify returns the trusted account dict
    # SELECT org-by-slug -> None (provision creates), then SELECT installation -> None (bind).
    db = _FakeSession([None, None])
    resp = await ghwh.github_install_callback(
        _FakeRequest(b"", redis=_FakeRedis()), db, installation_id=999, code="c", state=None,
    )
    assert resp.status_code in (302, 307)
    assert "/github/app/setup?installation_id=999" in resp.headers["location"]
    # one Organization minted + one service APIKey + one installation binding
    kinds = [type(o).__name__ for o in db.added]
    assert kinds.count("Organization") == 1
    assert kinds.count("APIKey") == 1
    assert kinds.count("GithubAppInstallation") == 1
    binding = next(o for o in db.added if type(o).__name__ == "GithubAppInstallation")
    assert binding.installation_id == 999
    assert binding.account_login == "acme"
    assert binding.account_type == "organization"


@pytest.mark.anyio
async def test_install_callback_redirects_to_setup_page(monkeypatch):
    """The dashboard-first bind also lands on the dependency-free setup page."""
    _verify_ok(monkeypatch)
    redis = _FakeRedis(get_value=str(uuid.uuid4()))
    resp = await ghwh.github_install_callback(
        _FakeRequest(b"", redis=redis), _FakeSession([None]),
        installation_id=555, code="c", state="st",
    )
    assert resp.status_code in (302, 307)
    assert "/github/app/setup?installation_id=555" in resp.headers["location"]


@pytest.mark.anyio
async def test_app_setup_page_is_html_and_safe():
    resp = await ghwh.github_app_setup(installation_id=4242)
    body = resp.body.decode()
    assert resp.status_code == 200
    assert "free trial" in body.lower()
    assert "#4242" in body  # int-cast installation id, no raw interpolation
    assert "<input" not in body.lower()  # no BYOK key form yet


@pytest.mark.anyio
async def test_install_callback_not_configured_404(monkeypatch):
    monkeypatch.setattr(ghwh, "app_configured", lambda: False)
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_install_callback(
            _FakeRequest(b"", redis=_FakeRedis()), _FakeSession([]),
            installation_id=999, code="c", state="s",
        )
    assert exc.value.status_code == 404


# ── installation-token minter (2B) ──────────────────────────────────────────────
@pytest.mark.anyio
async def test_get_installation_token_mints_and_caches(monkeypatch):
    monkeypatch.setattr(github_app_auth, "_app_jwt", lambda: "jwt-token")
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    async def _fake_http(**kwargs):
        assert kwargs["surface"] == "github_app_token"
        assert kwargs["egress_class"] == "customer_connector"
        assert kwargs["explicit_configured"] is True
        return SimpleNamespace(status_code=201, json=lambda: {"token": "ghs_abc", "expires_at": expires})

    monkeypatch.setattr(github_app_auth.egress_guard, "async_http_request", _fake_http)
    redis = _FakeRedis()
    row = _install_row()
    org = uuid.uuid4()
    tok = await github_app_auth.get_installation_token(12345, org_id=org, redis=redis, installation_row=row)
    assert tok == "ghs_abc"
    assert redis.sets and redis.sets[0][1] == "ghs_abc"  # cached
    assert row.encrypted_access_token  # persisted backstop
    assert row.token_expires_at is not None


@pytest.mark.anyio
async def test_get_installation_token_redis_hit(monkeypatch):
    def _no_mint(_id):
        raise AssertionError("must not mint on a cache hit")

    monkeypatch.setattr(github_app_auth, "_mint_installation_token", _no_mint)
    redis = _FakeRedis(get_value=b"cached-tok")
    tok = await github_app_auth.get_installation_token(12345, org_id=uuid.uuid4(), redis=redis)
    assert tok == "cached-tok"


@pytest.mark.anyio
async def test_get_installation_token_row_backstop(monkeypatch):
    async def _no_mint(_id):
        raise AssertionError("must not mint when the row token is still valid")

    monkeypatch.setattr(github_app_auth, "_mint_installation_token", _no_mint)
    row = _install_row()
    row.encrypted_access_token = "row-tok"  # config-crypto is a no-op without a KEK
    row.token_expires_at = datetime.now(UTC) + timedelta(minutes=30)
    tok = await github_app_auth.get_installation_token(
        12345, org_id=uuid.uuid4(), redis=None, installation_row=row
    )
    assert tok == "row-tok"


@pytest.mark.anyio
async def test_get_installation_token_row_backstop_near_expiry_remints(monkeypatch):
    """A token within the refresh margin must be re-minted, not handed to the pipeline."""
    monkeypatch.setattr(github_app_auth, "_app_jwt", lambda: "jwt")
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    async def _fake_http(**kwargs):
        return SimpleNamespace(status_code=201, json=lambda: {"token": "fresh", "expires_at": expires})

    monkeypatch.setattr(github_app_auth.egress_guard, "async_http_request", _fake_http)
    row = _install_row()
    row.encrypted_access_token = "stale"
    row.token_expires_at = datetime.now(UTC) + timedelta(seconds=60)  # < 300s margin
    tok = await github_app_auth.get_installation_token(
        12345, org_id=uuid.uuid4(), redis=None, installation_row=row
    )
    assert tok == "fresh"  # re-minted, not the near-expiry "stale"


# ── OAuth install-ownership verification (Fix: callback hijack) ──────────────────
def _mock_verify_http(monkeypatch, *, account, user_login="alice", membership=None):
    """Mock the 4-call admin-verification flow: code->token, /user, /app/installations/{id},
    /user/memberships/orgs/{org}."""
    monkeypatch.setattr(
        github_app_auth, "get_settings",
        lambda: SimpleNamespace(github_app_client_id="cid", github_app_client_secret="csec"),
    )
    monkeypatch.setattr(github_app_auth, "_app_jwt", lambda: "app-jwt")

    async def _fake_http(**kwargs):
        url = kwargs["url"]
        if url.endswith("access_token"):
            return SimpleNamespace(status_code=200, json=lambda: {"access_token": "user-tok"})
        if url.endswith("/user"):
            return SimpleNamespace(status_code=200, json=lambda: {"login": user_login})
        if "/app/installations/" in url:
            return SimpleNamespace(status_code=200, json=lambda: {"account": account})
        if "/user/memberships/orgs/" in url:
            return SimpleNamespace(status_code=200, json=lambda: (membership or {}))
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(github_app_auth.egress_guard, "async_http_request", _fake_http)


@pytest.mark.anyio
async def test_verify_org_admin_true(monkeypatch):
    _mock_verify_http(
        monkeypatch, account={"id": 42, "login": "Acme", "type": "Organization"},
        user_login="alice", membership={"state": "active", "role": "admin"},
    )
    # Success now returns the trusted App-JWT-resolved account (truthy), not bare True.
    acct = await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4())
    assert acct == {"id": 42, "login": "acme", "type": "organization"}


@pytest.mark.anyio
async def test_verify_org_member_not_admin_false(monkeypatch):
    # access (member) is NOT enough — must be an org admin
    _mock_verify_http(
        monkeypatch, account={"id": 42, "login": "Acme", "type": "Organization"},
        user_login="bob", membership={"state": "active", "role": "member"},
    )
    assert await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4()) is None


@pytest.mark.anyio
async def test_verify_user_account_owner_true(monkeypatch):
    _mock_verify_http(
        monkeypatch, account={"id": 7, "login": "Alice", "type": "User"}, user_login="alice"
    )
    acct = await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4())
    assert acct == {"id": 7, "login": "alice", "type": "user"}


@pytest.mark.anyio
async def test_verify_user_account_other_user_false(monkeypatch):
    _mock_verify_http(
        monkeypatch, account={"id": 7, "login": "victim", "type": "User"}, user_login="attacker"
    )
    assert await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4()) is None


@pytest.mark.anyio
async def test_verify_user_administers_installation_unconfigured(monkeypatch):
    monkeypatch.setattr(
        github_app_auth, "get_settings",
        lambda: SimpleNamespace(github_app_client_id=None, github_app_client_secret=None),
    )
    assert await github_app_auth.verify_user_administers_installation(1, "c", org_id=uuid.uuid4()) is None


@pytest.mark.anyio
async def test_verify_user_administers_installation_no_code(monkeypatch):
    monkeypatch.setattr(
        github_app_auth, "get_settings",
        lambda: SimpleNamespace(github_app_client_id="cid", github_app_client_secret="csec"),
    )
    # No OAuth code => cannot verify => None (do not bind).
    assert await github_app_auth.verify_user_administers_installation(1, "", org_id=uuid.uuid4()) is None


# ── worker dispatch ───────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_execute_job_by_kind_routes_repository(monkeypatch):
    job_id = uuid.uuid4()
    db = _FakeSession([JobKind.REPOSITORY_PIPELINE.value])
    called = {}

    async def _fake_repo(job_id, db):
        called["repo"] = True
        return {"ok": "repo"}

    monkeypatch.setattr(rjs, "execute_repository_job", _fake_repo)
    out = await rjs.execute_job_by_kind(job_id, db)
    assert out == {"ok": "repo"}
    assert called.get("repo")


@pytest.mark.anyio
async def test_execute_job_by_kind_stale_github_event_kind_raises_clear_error(monkeypatch):
    """A historical github_event_* job (from before the retirement) hits a clear, explicit
    "unsupported job_kind" error if it's ever re-dispatched, instead of importing the deleted
    github_event_service module."""
    job_id = uuid.uuid4()
    db = _FakeSession([JobKind.GITHUB_EVENT_ISSUE.value])

    async def _fake_repo(job_id, db):
        raise ValueError(f"unsupported repository job_kind: {JobKind.GITHUB_EVENT_ISSUE.value}")

    monkeypatch.setattr(rjs, "execute_repository_job", _fake_repo)
    with pytest.raises(ValueError, match="unsupported repository job_kind"):
        await rjs.execute_job_by_kind(job_id, db)


# ── migration linkage (2A) ──────────────────────────────────────────────────────
def test_migration_0039_chain():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "apps/api_server/alembic/versions/0039_add_github_app_installations.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_0039", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "0039"
    assert mod.down_revision == "0038"
    assert callable(mod.upgrade) and callable(mod.downgrade)


def test_installation_model_tablename():
    from apps.api_server.models.github_app_installation import GithubAppInstallation

    assert GithubAppInstallation.__tablename__ == "github_app_installations"
