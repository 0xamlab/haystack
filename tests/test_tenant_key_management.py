"""B10 PR11c: self-serve per-tenant provider/engine key management (BYOK write path).

Service: backend mapping/validation, set/rotate (encrypted at rest, KEK-required), delete, list
(write-only — selects no key material), cache invalidation after commit. Routes: admin-only RBAC,
encryption-required 409, write-only responses, 404 on missing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from apps.api_server.db.session import get_db
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.models.tenant_provider_key import ENGINE_BACKEND, TenantProviderKey
from apps.api_server.services import tenant_key_management as m
from apps.api_server.services.tenant_key_management import TenantKeyError
from tests._asgi_client import SyncASGIClient

_KEK = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"


@pytest.fixture(autouse=True)
def _noop_audit(monkeypatch):
    async def _audit(**_kwargs):
        return None

    monkeypatch.setattr(m, "write_audit_event", _audit)
    monkeypatch.delenv("ALGENTA_CONFIG_ENCRYPTION_KEY", raising=False)


@pytest.fixture
def invalidations(monkeypatch):
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(m, "invalidate_org_keys", lambda org_id: calls.append(org_id))
    return calls


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return self._value or []


class _FakeSession:
    """No-DB async session: pops pre-seeded execute() results; records add/delete/commit."""

    def __init__(self, results):
        self._results = list(results)
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    async def execute(self, _stmt):
        return _Result(self._results.pop(0) if self._results else None)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1


# ── backend mapping/validation ────────────────────────────────────────────────────────────────


def test_store_backend_maps_and_validates():
    assert m._store_backend("openai") == "openai"
    assert m._store_backend("ENGINE") == ENGINE_BACKEND  # case-insensitive label
    with pytest.raises(TenantKeyError):
        m._store_backend("bogus_provider")
    with pytest.raises(TenantKeyError):
        m._store_backend("algenta_engine")  # the raw sentinel is not a valid API label


# ── set / rotate ──────────────────────────────────────────────────────────────────────────────


async def test_set_fresh_adds_encrypted_row_and_invalidates(monkeypatch, invalidations):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    org = uuid.uuid4()
    db = _FakeSession([None])  # no existing row
    rotated = await m.set_org_key(
        db, org_id=org, api_backend="anthropic", api_key="sk-SECRET", actor_email="a@x"
    )
    assert rotated is False
    assert len(db.added) == 1
    row = db.added[0]
    assert isinstance(row, TenantProviderKey) and row.backend == "anthropic"
    assert row.encrypted_key.startswith("enc:v1:") and "sk-SECRET" not in row.encrypted_key
    assert db.commits == 1
    assert invalidations == [org]


async def test_set_rotate_updates_existing_in_place(monkeypatch, invalidations):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    org = uuid.uuid4()
    existing = TenantProviderKey(org_id=org, backend="openai", encrypted_key="enc:v1:OLD")
    db = _FakeSession([existing])
    rotated = await m.set_org_key(
        db, org_id=org, api_backend="openai", api_key="new-key", actor_email="a@x"
    )
    assert rotated is True
    assert db.added == []  # updated, not inserted
    assert existing.encrypted_key.startswith("enc:v1:") and existing.encrypted_key != "enc:v1:OLD"


async def test_set_engine_label_maps_to_sentinel(monkeypatch, invalidations):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    db = _FakeSession([None])
    await m.set_org_key(db, org_id=uuid.uuid4(), api_backend="engine", api_key="ek", actor_email="a@x")
    assert db.added[0].backend == ENGINE_BACKEND


async def test_set_without_encryption_key_refuses(invalidations):
    # No KEK -> refuse (never store a plaintext key). Nothing written, nothing invalidated.
    db = _FakeSession([None])
    with pytest.raises(TenantKeyError) as exc:
        await m.set_org_key(db, org_id=uuid.uuid4(), api_backend="openai", api_key="k", actor_email="a@x")
    assert exc.value.code == "encryption_key_required"
    assert db.added == [] and db.commits == 0 and invalidations == []


# ── delete ────────────────────────────────────────────────────────────────────────────────────


async def test_delete_existing_then_missing(monkeypatch, invalidations):
    org = uuid.uuid4()
    existing = TenantProviderKey(org_id=org, backend="openai", encrypted_key="enc:v1:x")
    db = _FakeSession([existing])
    assert await m.delete_org_key(db, org_id=org, api_backend="openai", actor_email="a@x") is True
    assert db.deleted == [existing] and db.commits == 1 and invalidations == [org]

    db2 = _FakeSession([None])
    assert await m.delete_org_key(db2, org_id=org, api_backend="openai", actor_email="a@x") is False
    assert db2.commits == 0


# ── list (write-only) ─────────────────────────────────────────────────────────────────────────


async def test_list_maps_sentinel_and_carries_no_key_material():
    now = datetime.now(UTC)
    db = _FakeSession([[("openai", now), (ENGINE_BACKEND, now)]])
    out = await m.list_org_key_backends(db, org_id=uuid.uuid4())
    assert ("openai", now) in out
    assert ("engine", now) in out  # sentinel surfaced under the API label
    assert all(len(entry) == 2 for entry in out)  # (backend, updated_at) — no key field


# ── routes: RBAC + encryption-required + write-only ─────────────────────────────────────────────


def _auth(role: str):
    return lambda: {"org_id": uuid.uuid4(), "role": role, "email": "admin@example.com"}


def _overrides(role: str, db):
    app.dependency_overrides[get_current_org] = _auth(role)
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = lambda: db


def test_route_non_admin_is_forbidden(monkeypatch):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    db = _FakeSession([None])
    _overrides("member", db)
    try:
        with SyncASGIClient(app) as client:
            r = client.post("/v1/provider-keys", json={"backend": "anthropic", "api_key": "sk"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert db.added == []  # never wrote


def test_route_admin_set_returns_204_and_stores_ciphertext(monkeypatch):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    db = _FakeSession([None])
    _overrides("admin", db)
    try:
        with SyncASGIClient(app) as client:
            r = client.post("/v1/provider-keys", json={"backend": "anthropic", "api_key": "sk-LEAK"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 204
    assert len(db.added) == 1
    assert db.added[0].encrypted_key.startswith("enc:v1:") and "sk-LEAK" not in db.added[0].encrypted_key


def test_route_set_without_kek_is_409(monkeypatch):
    monkeypatch.delenv("ALGENTA_CONFIG_ENCRYPTION_KEY", raising=False)
    db = _FakeSession([None])
    _overrides("admin", db)
    try:
        with SyncASGIClient(app) as client:
            r = client.post("/v1/provider-keys", json={"backend": "anthropic", "api_key": "sk"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "encryption_key_required"


def test_route_list_is_write_only(monkeypatch):
    now = datetime.now(UTC)
    db = _FakeSession([[("openai", now), (ENGINE_BACKEND, now)]])
    _overrides("admin", db)
    try:
        with SyncASGIClient(app) as client:
            r = client.get("/v1/provider-keys")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    backends = {k["backend"] for k in r.json()["keys"]}
    assert backends == {"openai", "engine"}
    assert "encrypted_key" not in r.text and "api_key" not in r.text  # no key material on the wire
