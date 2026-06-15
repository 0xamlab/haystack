"""GitHub App (codna) — unit tests for the inbound webhook, installation-token minter,
event handler, worker dispatch, and install callback.

Fake-session style (mirrors test_repository_job_service.py): no real DB, GitHub mocked.
These run in CI under `test:hardening`. End-to-end (real install + real GitHub) is gated
on owner infra and is out of scope here.
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

from apps.api_server.models.job import JobKind, JobStatus
from apps.api_server.routers import github_webhooks as ghwh
from apps.api_server.services import github_app_auth, github_event_service
from apps.api_server.services import repository_job_service as rjs
from apps.api_server.services import tenant_key_store

_SECRET = "whsec_test_secret"


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


# ── classify ──────────────────────────────────────────────────────────────────
def test_classify_check_suite_failure():
    assert ghwh._classify("check_suite", _check_payload()) is JobKind.GITHUB_EVENT_CHECK


def test_classify_check_suite_success_ignored():
    p = _check_payload()
    p["check_suite"]["conclusion"] = "success"
    assert ghwh._classify("check_suite", p) is None


def test_classify_check_run_ignored():
    # check_run is deliberately ignored — only the aggregate check_suite is acted on,
    # so one CI run can't fan out into N duplicate fix PRs.
    p = {"action": "completed", "check_run": {"conclusion": "failure", "head_sha": "x"}}
    assert ghwh._classify("check_run", p) is None


def test_classify_issue_label():
    p = {"action": "labeled", "label": {"name": "codna-fix"}}
    assert ghwh._classify("issues", p) is JobKind.GITHUB_EVENT_ISSUE


def test_classify_issue_other_label_ignored():
    p = {"action": "labeled", "label": {"name": "bug"}}
    assert ghwh._classify("issues", p) is None


def test_classify_pr_review():
    assert ghwh._classify("pull_request_review", {"action": "submitted"}) is JobKind.GITHUB_EVENT_PR_REVIEW


def test_classify_unknown_event_ignored():
    assert ghwh._classify("push", {}) is None


# ── webhook route ──────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_webhook_valid_signature_enqueues(monkeypatch):
    _configure(monkeypatch)
    enqueued: list[uuid.UUID] = []

    async def _fake_enqueue(job_id):
        enqueued.append(job_id)

    async def _claim_true(db, did, iid):
        return True, None

    monkeypatch.setattr(ghwh, "_enqueue", _fake_enqueue)
    monkeypatch.setattr(ghwh, "_claim_delivery", _claim_true)
    org = uuid.uuid4()
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row(org)])
    req = _FakeRequest(body, redis=None)

    resp = await ghwh.github_webhook(
        req, db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="d-1",
    )
    assert resp.status_code == 202
    payload = json.loads(resp.body)
    assert payload["status"] == "queued"
    assert payload["job_kind"] == JobKind.GITHUB_EVENT_CHECK.value
    # a job was created with the right kind + org + carried payload
    assert len(db.added) == 1
    job = db.added[0]
    assert job.job_kind == JobKind.GITHUB_EVENT_CHECK.value
    assert job.org_id == org
    assert job.request_payload["installation_id"] == 12345
    assert job.request_payload["event"] == "check_suite"
    assert len(enqueued) == 1


@pytest.mark.anyio
async def test_webhook_durable_dedup_duplicate(monkeypatch):
    """Redis-down path still dedupes via the durable claim (layer 2)."""
    _configure(monkeypatch)
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("dup must not enqueue"))

    async def _claim_false(db, did, iid):
        return False, None  # already claimed, no recoverable job

    monkeypatch.setattr(ghwh, "_claim_delivery", _claim_false)
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row()])
    resp = await ghwh.github_webhook(
        _FakeRequest(body, redis=None), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="dup-durable",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body)["status"] == "duplicate"
    assert not db.added


@pytest.mark.anyio
async def test_webhook_redelivery_requeues_unrun_job(monkeypatch):
    """A re-delivery of a job that was committed but never enqueued re-enqueues it (recovery)."""
    _configure(monkeypatch)
    stuck = uuid.uuid4()
    enqueued: list[uuid.UUID] = []

    async def _fake_enqueue(job_id):
        enqueued.append(job_id)

    async def _claim_existing(db, did, iid):
        return False, stuck  # already claimed; here is the job it produced

    monkeypatch.setattr(ghwh, "_enqueue", _fake_enqueue)
    monkeypatch.setattr(ghwh, "_claim_delivery", _claim_existing)
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row()])
    resp = await ghwh.github_webhook(
        _FakeRequest(body, redis=None), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="redeliver-1",
    )
    assert resp.status_code == 202
    payload = json.loads(resp.body)
    assert payload["status"] == "requeued"
    assert payload["job_id"] == str(stuck)
    assert enqueued == [stuck]
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
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("must not enqueue"))
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
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("must not enqueue"))
    body = json.dumps(_check_payload()).encode()
    db = _FakeSession([_install_row(suspended=True)])
    resp = await ghwh.github_webhook(
        _FakeRequest(body), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="d-3b",
    )
    assert resp.status_code == 202
    assert not db.added


@pytest.mark.anyio
async def test_webhook_dedup_duplicate(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("dup must not enqueue"))
    body = json.dumps(_check_payload()).encode()
    redis = _FakeRedis(get_value="1")  # read-through hit => already processed
    db = _FakeSession([_install_row()])
    resp = await ghwh.github_webhook(
        _FakeRequest(body, redis=redis), db, x_github_event="check_suite",
        x_hub_signature_256=_sign(body), x_github_delivery="dup-1",
    )
    assert resp.status_code == 202
    assert json.loads(resp.body)["status"] == "duplicate"


@pytest.mark.anyio
async def test_webhook_installation_deleted_removes_binding(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("must not enqueue"))
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
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("must not enqueue"))
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
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("must not enqueue"))
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
    monkeypatch.setattr(ghwh, "_enqueue", lambda _j: pytest.fail("must not enqueue"))
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
        return ok

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
async def test_install_callback_missing_state_400(monkeypatch):
    _verify_ok(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await ghwh.github_install_callback(
            _FakeRequest(b"", redis=_FakeRedis(get_value=None)), _FakeSession([]),
            installation_id=999, code="c", state=None,
        )
    assert exc.value.status_code == 400


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
        monkeypatch, account={"login": "Acme", "type": "Organization"},
        user_login="alice", membership={"state": "active", "role": "admin"},
    )
    assert await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4()) is True


@pytest.mark.anyio
async def test_verify_org_member_not_admin_false(monkeypatch):
    # access (member) is NOT enough — must be an org admin
    _mock_verify_http(
        monkeypatch, account={"login": "Acme", "type": "Organization"},
        user_login="bob", membership={"state": "active", "role": "member"},
    )
    assert await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4()) is False


@pytest.mark.anyio
async def test_verify_user_account_owner_true(monkeypatch):
    _mock_verify_http(monkeypatch, account={"login": "Alice", "type": "User"}, user_login="alice")
    assert await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4()) is True


@pytest.mark.anyio
async def test_verify_user_account_other_user_false(monkeypatch):
    _mock_verify_http(monkeypatch, account={"login": "victim", "type": "User"}, user_login="attacker")
    assert await github_app_auth.verify_user_administers_installation(77, "c", org_id=uuid.uuid4()) is False


@pytest.mark.anyio
async def test_verify_user_administers_installation_unconfigured(monkeypatch):
    monkeypatch.setattr(
        github_app_auth, "get_settings",
        lambda: SimpleNamespace(github_app_client_id=None, github_app_client_secret=None),
    )
    assert await github_app_auth.verify_user_administers_installation(1, "c", org_id=uuid.uuid4()) is False


@pytest.mark.anyio
async def test_verify_user_administers_installation_no_code(monkeypatch):
    monkeypatch.setattr(
        github_app_auth, "get_settings",
        lambda: SimpleNamespace(github_app_client_id="cid", github_app_client_secret="csec"),
    )
    # No OAuth code => cannot verify => False (do not bind).
    assert await github_app_auth.verify_user_administers_installation(1, "", org_id=uuid.uuid4()) is False


# ── event handler (2D) ──────────────────────────────────────────────────────────
def _event_job(kind=JobKind.GITHUB_EVENT_CHECK, **overrides):
    base = dict(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        workspace_id=None,
        job_kind=kind.value,
        status=JobStatus.QUEUED,
        request_payload={"installation_id": 12345, "event": "check_run", "payload": _check_payload()},
        result_payload=None,
        started_at=None,
        completed_at=None,
        error_message=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.anyio
async def test_execute_github_event_job_completes(monkeypatch):
    job = _event_job()
    db = _FakeSession([job, _install_row()])

    async def _fake_token(*a, **k):
        return "tok"

    async def _fake_drive(**k):
        return {"status": "pr_opened", "pull_request_url": "https://github.com/o/r/pull/7"}

    monkeypatch.setattr(github_event_service.github_app_auth, "get_installation_token", _fake_token)
    monkeypatch.setattr(github_event_service, "_drive_fix", _fake_drive)
    result = await github_event_service.execute_github_event_job(job_id=job.id, db=db)
    assert result["status"] == "pr_opened"
    assert job.status == JobStatus.COMPLETED
    assert job.result_payload == result
    assert job.error_message is None


@pytest.mark.anyio
async def test_execute_github_event_job_idempotent_terminal(monkeypatch):
    job = _event_job(status=JobStatus.COMPLETED, result_payload={"status": "pr_opened"})
    db = _FakeSession([job])

    async def _must_not(**k):
        raise AssertionError("terminal job must not re-run")

    monkeypatch.setattr(github_event_service, "_drive_fix", _must_not)
    result = await github_event_service.execute_github_event_job(job_id=job.id, db=db)
    assert result == {"status": "pr_opened"}


@pytest.mark.anyio
async def test_execute_github_event_job_inflight_not_rerun(monkeypatch):
    """A freshly-RUNNING job (concurrent worker / immediate redelivery) must NOT re-run."""
    job = _event_job(status=JobStatus.RUNNING, result_payload=None,
                     started_at=datetime.now(UTC))  # just started => in-flight
    db = _FakeSession([job])

    async def _must_not(**k):
        raise AssertionError("an in-flight job must not re-run _drive_fix")

    monkeypatch.setattr(github_event_service, "_drive_fix", _must_not)
    result = await github_event_service.execute_github_event_job(job_id=job.id, db=db)
    assert result["status"] == JobStatus.RUNNING.value


@pytest.mark.anyio
async def test_execute_github_event_job_stale_running_reclaimed(monkeypatch):
    """A job stuck RUNNING past the reclaim window (crashed worker) IS re-executed."""
    job = _event_job(status=JobStatus.RUNNING, result_payload=None,
                     started_at=datetime.now(UTC) - timedelta(hours=2))  # stale
    db = _FakeSession([job, _install_row()])

    async def _fake_token(*a, **k):
        return "tok"

    async def _fake_drive(**k):
        return {"status": "pr_opened"}

    monkeypatch.setattr(github_event_service.github_app_auth, "get_installation_token", _fake_token)
    monkeypatch.setattr(github_event_service, "_drive_fix", _fake_drive)
    result = await github_event_service.execute_github_event_job(job_id=job.id, db=db)
    assert result["status"] == "pr_opened"
    assert job.status == JobStatus.COMPLETED


@pytest.mark.anyio
async def test_execute_github_event_job_failure_marks_failed(monkeypatch):
    job = _event_job()
    db = _FakeSession([job, _install_row()])

    async def _fake_token(*a, **k):
        return "tok"

    async def _boom(**k):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(github_event_service.github_app_auth, "get_installation_token", _fake_token)
    monkeypatch.setattr(github_event_service, "_drive_fix", _boom)
    with pytest.raises(RuntimeError):
        await github_event_service.execute_github_event_job(job_id=job.id, db=db)
    assert job.status == JobStatus.FAILED
    assert "blew up" in (job.error_message or "")


@pytest.mark.anyio
async def test_drive_fix_opens_pr(monkeypatch):
    from apps.api_server.services import repository_intelligence_core as ric
    from apps.api_server.services import repository_intelligence_pipeline as rip

    captured = {}

    async def _fake_pipeline(*, connector, request):
        captured["stop_after"] = request.stop_after
        captured["issue_text"] = request.signals.issue_text
        return SimpleNamespace(
            snapshot_id="snap-1",
            decision_plan=SimpleNamespace(decision_plan_id="dp-1"),
            simulation=SimpleNamespace(validated_inputs={"simulation_id": "sim-1"}),
        )

    async def _fake_apply(*, connector, request):
        captured["mode"] = request.mode
        captured["decision_plan_id"] = request.decision_plan_id
        captured["simulation_id"] = request.simulation_id
        captured["write_permission"] = request.write_permission
        return SimpleNamespace(pull_request_url="https://github.com/octo/repo/pull/9")

    posted = []

    async def _fake_post(**k):
        posted.append(k)

    monkeypatch.setattr(rip, "run_repository_pipeline", _fake_pipeline)
    monkeypatch.setattr(ric, "apply_repository_decision", _fake_apply)
    monkeypatch.setattr(github_event_service, "_post_github", _fake_post)

    out = await github_event_service._drive_fix(
        event="check_run", payload=_check_payload(), token="tok",
        org_id=uuid.uuid4(), installation_id=12345,
    )
    assert out["status"] == "pr_opened"
    assert out["pull_request_url"].endswith("/pull/9")
    assert captured["stop_after"] == "simulate"
    assert captured["mode"] == "remote_pr"
    assert captured["write_permission"] is True
    assert captured["decision_plan_id"] == "dp-1"
    assert captured["simulation_id"] == "sim-1"
    # the PR link is posted back as a commit comment
    assert posted and "/pull/9" in posted[0]["body"]["body"]


@pytest.mark.anyio
async def test_drive_fix_pins_clone_url_to_github(monkeypatch):
    """The clone URL is derived from the validated owner/repo + pinned to github.com,
    never taken from the attacker-controllable payload clone_url (token-exfil guard)."""
    from apps.api_server.services import repository_intelligence_pipeline as rip

    seen = {}

    async def _fake_pipeline(*, connector, request):
        import json as _json
        from apps.api_server.services.config_crypto import decrypt_config_json

        cfg = _json.loads(decrypt_config_json(connector.config_json, org_id=connector.org_id))
        seen["repository_url"] = cfg["repository_url"]
        return SimpleNamespace(snapshot_id="s", decision_plan=None, simulation=None)

    async def _fake_post(**k):
        pass

    monkeypatch.setattr(rip, "run_repository_pipeline", _fake_pipeline)
    monkeypatch.setattr(github_event_service, "_post_github", _fake_post)
    payload = _check_payload()
    payload["repository"]["clone_url"] = "https://evil.example.com/octo/repo.git"  # ignored
    await github_event_service._drive_fix(
        event="check_suite", payload=payload, token="tok", org_id=uuid.uuid4(), installation_id=1,
    )
    assert seen["repository_url"] == "https://github.com/octo/repo.git"


@pytest.mark.anyio
async def test_drive_fix_rejects_bad_full_name(monkeypatch):
    for bad in ("evil.com/a/../b", "../../etc", "noslash", "a/b@c", "https://x/y"):
        payload = _check_payload()
        payload["repository"]["full_name"] = bad
        with pytest.raises(ValueError):
            await github_event_service._drive_fix(
                event="check_suite", payload=payload, token="t", org_id=uuid.uuid4(), installation_id=1,
            )


@pytest.mark.anyio
async def test_drive_fix_no_plan_comments(monkeypatch):
    from apps.api_server.services import repository_intelligence_pipeline as rip

    async def _fake_pipeline(*, connector, request):
        return SimpleNamespace(snapshot_id="s", decision_plan=None, simulation=None)

    posted = []

    async def _fake_post(**k):
        posted.append(k)

    monkeypatch.setattr(rip, "run_repository_pipeline", _fake_pipeline)
    monkeypatch.setattr(github_event_service, "_post_github", _fake_post)
    out = await github_event_service._drive_fix(
        event="check_run", payload=_check_payload(), token="tok",
        org_id=uuid.uuid4(), installation_id=12345,
    )
    assert out["status"] == "no_plan"
    assert posted  # still comments to close the loop


@pytest.mark.anyio
async def test_pr_review_comments_only(monkeypatch):
    posted = []

    async def _fake_post(**k):
        posted.append(k)

    monkeypatch.setattr(github_event_service, "_post_github", _fake_post)
    payload = {"pull_request": {"number": 4}, "repository": {"full_name": "octo/repo"}}
    out = await github_event_service._handle_pr_review(payload, "tok", uuid.uuid4())
    assert out["status"] == "commented"
    assert posted and posted[0]["path"].endswith("/issues/4/comments")


# ── worker dispatch ───────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_execute_job_by_kind_routes_github(monkeypatch):
    job_id = uuid.uuid4()
    db = _FakeSession([JobKind.GITHUB_EVENT_ISSUE.value])
    called = {}

    async def _fake_event(*, job_id, db):
        called["github"] = True
        return {"ok": True}

    monkeypatch.setattr(github_event_service, "execute_github_event_job", _fake_event)
    out = await rjs.execute_job_by_kind(job_id, db)
    assert out == {"ok": True}
    assert called.get("github")


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
