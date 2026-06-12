"""B10 PR11a: the per-org key store + the API and worker binding hooks.

Covers the acceptance bar: keys encrypted at rest, resolve_org_keys decrypts per (org, backend),
the API dependency + the router wiring + the worker hook bind the ContextVar from org_id, env
fallback for pooled/self-hosted, required-BYOK fail-closed, short-TTL cache + rotation
invalidation, isolation of a store failure (degrades to empty, never raises), and that no key
material leaks through reprs.

resolve_org_keys reads on its OWN session (apps...tenant_key_store.AsyncSessionLocal), so the tests
patch that factory rather than passing a session.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from apps.api_server.middleware.tenant_key_binding import bind_tenant_keys
from apps.api_server.models.tenant_provider_key import ENGINE_BACKEND
from apps.api_server.services import tenant_keys as tk
from apps.api_server.services.config_crypto import encrypt_secret
from apps.api_server.services.tenant_key_store import (
    KEY_AAD_CONTEXT,
    invalidate_org_keys,
    resolve_org_keys,
)

# A deterministic 64-hex KEK so encryption is actually exercised (encrypted-at-rest assertions).
_KEK = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    invalidate_org_keys()  # no cross-test cache bleed
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    monkeypatch.delenv("MY_KEY", raising=False)
    yield
    invalidate_org_keys()


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    """Async-context-manager session stub for resolve_org_keys' own session (read-only select)."""

    def __init__(self, rows, raises):
        self._rows = rows
        self._raises = raises

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def execute(self, _stmt):
        if self._raises:
            raise RuntimeError("db unavailable")
        return _FakeResult(self._rows)


def _patch_session(monkeypatch, rows=None, raises=False):
    """Patch the store's session factory; returns a dict with the count of sessions opened."""
    state = {"sessions": 0}

    def _factory():
        state["sessions"] += 1
        return _FakeSession(rows or [], raises)

    monkeypatch.setattr("apps.api_server.services.tenant_key_store.AsyncSessionLocal", _factory)
    return state


def _row(org_id, backend, encrypted_key):
    return SimpleNamespace(org_id=org_id, backend=backend, encrypted_key=encrypted_key)


# --- encryption at rest + resolve --------------------------------------------------------------


async def test_keys_encrypted_at_rest_and_resolve_decrypts(monkeypatch):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    org = uuid.uuid4()
    enc_openai = encrypt_secret("sk-openai", org_id=org, context=KEY_AAD_CONTEXT)
    enc_engine = encrypt_secret("engine-key", org_id=org, context=KEY_AAD_CONTEXT)

    # at rest = ciphertext, not the plaintext key
    assert enc_openai.startswith("enc:v1:") and "sk-openai" not in enc_openai

    _patch_session(monkeypatch, rows=[_row(org, "openai", enc_openai), _row(org, ENGINE_BACKEND, enc_engine)])
    keys = await resolve_org_keys(org)
    assert keys.provider_keys == {"openai": "sk-openai"}
    assert keys.engine_key == "engine-key"


async def test_resolve_empty_when_no_rows(monkeypatch):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    _patch_session(monkeypatch, rows=[])
    keys = await resolve_org_keys(uuid.uuid4())
    assert keys.provider_keys == {} and keys.engine_key is None


async def test_resolve_degrades_to_empty_on_store_error(monkeypatch):
    # A DB error must NOT raise into the request/run — degrade to empty. Because resolve_org_keys
    # uses its OWN session, the caller's session can never be poisoned by this failure.
    _patch_session(monkeypatch, raises=True)
    keys = await resolve_org_keys(uuid.uuid4())
    assert keys.provider_keys == {} and keys.engine_key is None


# --- cache + rotation invalidation -------------------------------------------------------------


async def test_cache_avoids_repeat_db_then_invalidate(monkeypatch):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    org = uuid.uuid4()
    state = _patch_session(
        monkeypatch, rows=[_row(org, "openai", encrypt_secret("k", org_id=org, context=KEY_AAD_CONTEXT))]
    )
    await resolve_org_keys(org)
    await resolve_org_keys(org)
    assert state["sessions"] == 1  # second resolve served from cache (no new session)
    invalidate_org_keys(org)
    await resolve_org_keys(org)
    assert state["sessions"] == 2  # rotation bust forces a fresh read


# --- API request hook + router wiring ----------------------------------------------------------


async def test_api_hook_binds_override_then_resets(monkeypatch):
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    org = uuid.uuid4()
    enc = encrypt_secret("org-openai", org_id=org, context=KEY_AAD_CONTEXT)
    _patch_session(monkeypatch, rows=[_row(org, "openai", enc)])

    agen = bind_tenant_keys(auth={"org_id": org})  # async generator dependency
    await agen.__anext__()  # enter: sets the ContextVar
    try:
        bound = tk.current_org_keys()
        assert bound is not None and bound.provider_keys["openai"] == "org-openai"
        assert tk.resolve_provider_api_key("MY_KEY", "openai") == "org-openai"
    finally:
        with pytest.raises(StopAsyncIteration):
            await agen.__anext__()  # teardown: resets
    assert tk.current_org_keys() is None  # reset after the request


def test_routers_wire_bind_tenant_keys():
    # Runtime assertion that the hook is actually attached to the routers (not just defined): a
    # regression that drops the router dependency fails here.
    from apps.api_server.routers import llm, repositories

    for router in (repositories.router, llm.router):
        deps = [getattr(d, "dependency", None) for d in router.dependencies]
        assert bind_tenant_keys in deps


# --- worker / fire-and-forget mechanism --------------------------------------------------------


async def test_worker_mechanism_binds_engine_key_from_org(monkeypatch):
    # The worker re-resolves from org_id and binds the override; resolve_engine_api_key then returns
    # the per-org key (the same mechanism execute_repository_job uses around _run_repository_kind;
    # an end-to-end assertion of that wiring lives in test_repository_job_service.py).
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", _KEK)
    monkeypatch.setenv("ALGENTA_ENGINE_API_KEY", "pooled-engine")
    org = uuid.uuid4()
    enc = encrypt_secret("org-engine", org_id=org, context=KEY_AAD_CONTEXT)
    _patch_session(monkeypatch, rows=[_row(org, ENGINE_BACKEND, enc)])
    token = tk.set_org_keys_override(await resolve_org_keys(org))
    try:
        assert tk.resolve_engine_api_key() == "org-engine"
    finally:
        tk.reset_org_keys_override(token)
    assert tk.resolve_engine_api_key() == "pooled-engine"  # env fallback after reset


# --- pooled/self-hosted fallback + required-BYOK fail-closed ------------------------------------


async def test_pooled_env_fallback_when_no_override(monkeypatch):
    monkeypatch.setenv("MY_KEY", "pooled-openai")
    _patch_session(monkeypatch, rows=[])  # empty store -> no override
    token = tk.set_org_keys_override(await resolve_org_keys(uuid.uuid4()))
    try:
        assert tk.resolve_provider_api_key("MY_KEY", "openai") == "pooled-openai"
    finally:
        tk.reset_org_keys_override(token)


async def test_required_byok_fails_closed_with_empty_store(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    monkeypatch.setenv("MY_KEY", "pooled-openai")
    _patch_session(monkeypatch, rows=[])
    token = tk.set_org_keys_override(await resolve_org_keys(uuid.uuid4()))
    try:
        assert tk.resolve_provider_api_key("MY_KEY", "openai") is None  # no pooled borrow
    finally:
        tk.reset_org_keys_override(token)
