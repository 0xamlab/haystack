"""Wave 2 PR-5b: the 3-tier provider-key resolver + the managed-spend gate/meter wiring.

The resolver precedence is: BYOK (org's own key) > strict-fail-closed > managed (hosted pooled key,
opted-in org, metered) > self-host (legacy single-tenant env key). When ALGENTA_MANAGED_LLM is off
(default) the logic collapses to the legacy BYOK>env path byte-for-byte (covered by the existing
test_tenant_keys); these tests exercise the new managed tier + the call-path gate/meter.
"""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.services.tenant_keys import (
    KEY_TYPE_BYOK,
    KEY_TYPE_MANAGED,
    KEY_TYPE_NONE,
    KEY_TYPE_SELF_HOST,
    OrgKeys,
    provider_key_type,
    reset_org_keys_override,
    resolve_provider_api_key,
    set_org_keys_override,
)

ENV = "TEST_MANAGED_PROVIDER_KEY"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    monkeypatch.delenv(ENV, raising=False)
    yield


def _bind(**kw):
    return set_org_keys_override(OrgKeys(org_id=uuid.uuid4(), **kw))


# ── Resolver tiers (sync) ───────────────────────────────────────────────────────


def test_byok_wins_in_any_mode(monkeypatch):
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    tok = _bind(provider_keys={"anthropic": "byok-key"}, managed_allowed=True)
    try:
        assert resolve_provider_api_key(ENV, "anthropic") == "byok-key"
        assert provider_key_type(ENV, "anthropic") == KEY_TYPE_BYOK
    finally:
        reset_org_keys_override(tok)


def test_strict_per_tenant_fails_closed(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    monkeypatch.setenv(ENV, "env-key")
    tok = _bind(provider_keys={})
    try:
        assert resolve_provider_api_key(ENV, "anthropic") is None
        assert provider_key_type(ENV, "anthropic") == KEY_TYPE_NONE
    finally:
        reset_org_keys_override(tok)


def test_managed_allowed_draws_env_as_managed(monkeypatch):
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    tok = _bind(provider_keys={}, managed_allowed=True)
    try:
        assert resolve_provider_api_key(ENV, "anthropic") == "env-key"
        assert provider_key_type(ENV, "anthropic") == KEY_TYPE_MANAGED
    finally:
        reset_org_keys_override(tok)


def test_managed_not_opted_in_fails_closed(monkeypatch):
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    tok = _bind(provider_keys={}, managed_allowed=False)
    try:
        assert resolve_provider_api_key(ENV, "anthropic") is None
        assert provider_key_type(ENV, "anthropic") == KEY_TYPE_NONE
    finally:
        reset_org_keys_override(tok)


def test_managed_never_leaks_to_agentic_sidecar(monkeypatch):
    # The agentic path resolves with api_key_env=None (BYOK-only). Managed env must never be drawn,
    # else the sidecar would run unmetered managed spend.
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    tok = _bind(provider_keys={}, managed_allowed=True)
    try:
        assert resolve_provider_api_key(None, "anthropic") is None
        assert provider_key_type(None, "anthropic") == KEY_TYPE_NONE
    finally:
        reset_org_keys_override(tok)


def test_self_host_legacy_unchanged(monkeypatch):
    # managed mode OFF + no strict flag → the pooled env key is THE key (self_host), not metered.
    monkeypatch.setenv(ENV, "env-key")
    assert resolve_provider_api_key(ENV, "anthropic") == "env-key"
    assert provider_key_type(ENV, "anthropic") == KEY_TYPE_SELF_HOST
    # ...and no env → none.
    assert resolve_provider_api_key("MISSING_ENV", "anthropic") is None
    assert provider_key_type("MISSING_ENV", "anthropic") == KEY_TYPE_NONE


def test_managed_mode_without_org_context_fails_closed(monkeypatch):
    # In managed mode a request with no bound org cannot borrow the pooled env key.
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    assert resolve_provider_api_key(ENV, "anthropic") is None
    assert provider_key_type(ENV, "anthropic") == KEY_TYPE_NONE


# ── resolve_org_keys populates the managed posture (DB) ────────────────────────────


async def _seed_org(*, managed_enabled, quota=0, plan="free"):
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus

    async with AsyncSessionLocal() as s:
        org = Organization(
            name="MLLM Resolver", slug=f"mllmr-{uuid.uuid4().hex[:8]}",
            plan=OrgPlan(plan), status=OrgStatus.ACTIVE,
            managed_llm_enabled=managed_enabled, managed_llm_quota_usd_month=quota,
        )
        s.add(org)
        await s.commit()
        return org.id


async def test_resolve_org_keys_managed_allowed_tracks_mode_and_flag(monkeypatch):
    from apps.api_server.services.tenant_key_store import invalidate_org_keys, resolve_org_keys

    org_id = await _seed_org(managed_enabled=True, quota=7)

    # managed mode ON + org opted in → allowed, with plan + quota carried.
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    invalidate_org_keys()
    keys = await resolve_org_keys(org_id)
    assert keys.managed_allowed is True
    assert keys.plan == "free"
    assert keys.managed_quota_usd_month == 7

    # managed mode OFF → not allowed even though the org flag is set.
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    invalidate_org_keys()
    keys = await resolve_org_keys(org_id)
    assert keys.managed_allowed is False


async def test_resolve_org_keys_not_allowed_when_org_flag_off(monkeypatch):
    from apps.api_server.services.tenant_key_store import invalidate_org_keys, resolve_org_keys

    org_id = await _seed_org(managed_enabled=False)
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    invalidate_org_keys()
    keys = await resolve_org_keys(org_id)
    assert keys.managed_allowed is False


# ── Call-path gate + meter (DB) ────────────────────────────────────────────────────


async def test_gate_blocks_managed_call_over_cap(monkeypatch):
    from apps.api_server.services.llm_api_service import LLMAPIError
    from apps.api_server.services.llm_spend_service import gate_managed_llm_call, record_llm_usage
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.llm_usage_record import LLMKeyType

    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    org_id = await _seed_org(managed_enabled=True, quota=1)  # $1/mo budget

    # Spend past $1 (claude-sonnet 400k input = $1.20).
    async with AsyncSessionLocal() as s:
        await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-sonnet-4-6",
            key_type=LLMKeyType.MANAGED, prompt_tokens=400_000, db=s,
        )
        await s.commit()

    tok = set_org_keys_override(
        OrgKeys(org_id=org_id, managed_allowed=True, plan="free", managed_quota_usd_month=1)
    )
    try:
        with pytest.raises(LLMAPIError) as exc:
            await gate_managed_llm_call(backend="anthropic", api_key_env=ENV)
        assert exc.value.code == "payment_required"
    finally:
        reset_org_keys_override(tok)


async def test_gate_noop_for_byok_even_over_cap(monkeypatch):
    from apps.api_server.services.llm_spend_service import gate_managed_llm_call, record_llm_usage
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.llm_usage_record import LLMKeyType

    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    org_id = await _seed_org(managed_enabled=True, quota=1)
    async with AsyncSessionLocal() as s:
        await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-sonnet-4-6",
            key_type=LLMKeyType.MANAGED, prompt_tokens=400_000, db=s,
        )
        await s.commit()

    # BYOK present for this backend → classified BYOK → gate is a no-op (BYOK never blocked).
    tok = set_org_keys_override(
        OrgKeys(org_id=org_id, provider_keys={"anthropic": "byok"}, managed_allowed=True,
                plan="free", managed_quota_usd_month=1)
    )
    try:
        await gate_managed_llm_call(backend="anthropic", api_key_env=ENV)  # no raise
    finally:
        reset_org_keys_override(tok)


async def test_meter_records_managed_only(monkeypatch):
    from apps.api_server.services.llm_spend_service import (
        get_monthly_llm_spend_micros,
        meter_managed_llm_call,
    )
    from apps.api_server.db.session import AsyncSessionLocal

    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv(ENV, "env-key")
    org_id = await _seed_org(managed_enabled=True)

    # Managed classification → meter writes a costed row.
    tok = set_org_keys_override(OrgKeys(org_id=org_id, managed_allowed=True, plan="free"))
    try:
        await meter_managed_llm_call(
            backend="anthropic", api_key_env=ENV, model="claude-sonnet-4-6",
            prompt_tokens=1_000, completion_tokens=1_000,
        )
    finally:
        reset_org_keys_override(tok)
    async with AsyncSessionLocal() as s:
        spent = await get_monthly_llm_spend_micros(org_id, s)
    assert spent == 1_000 * 3 + 1_000 * 15  # 18_000 µ$

    # BYOK classification → meter is a no-op (no additional spend).
    tok = set_org_keys_override(
        OrgKeys(org_id=org_id, provider_keys={"anthropic": "byok"}, managed_allowed=True, plan="free")
    )
    try:
        await meter_managed_llm_call(
            backend="anthropic", api_key_env=ENV, model="claude-sonnet-4-6",
            prompt_tokens=5_000, completion_tokens=5_000,
        )
    finally:
        reset_org_keys_override(tok)
    async with AsyncSessionLocal() as s:
        spent_after = await get_monthly_llm_spend_micros(org_id, s)
    assert spent_after == 18_000  # unchanged — BYOK is not metered


async def test_embeddings_gates_before_provider_call(monkeypatch):
    # Embeddings draw the managed key too, so they must be gated (else managed spend escapes the cap
    # on that surface). Prove the gate runs BEFORE the network call: stub it to raise, and fail if
    # the provider POST is reached first.
    from apps.api_server.services import llm_spend_service
    from apps.api_server.services.llm_provider_service import ProviderModelConfig, _embeddings_api

    seen: dict[str, object] = {}

    async def _fake_gate(*, backend, api_key_env):
        seen["backend"] = backend
        seen["api_key_env"] = api_key_env
        raise RuntimeError("gate-ran-first")

    async def _boom_post(**_kwargs):
        raise AssertionError("provider POST reached before the managed-spend gate")

    monkeypatch.setattr(llm_spend_service, "gate_managed_llm_call", _fake_gate)
    monkeypatch.setattr(_embeddings_api, "_provider_post_json", _boom_post)

    cfg = ProviderModelConfig(
        model_id="provider.embed",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed embeddings model.",
        capabilities=("embeddings",),
    )
    with pytest.raises(RuntimeError, match="gate-ran-first"):
        await _embeddings_api.provider_embeddings(config=cfg, inputs=["hi"], dimensions=8)
    assert seen["backend"] == "openai" and seen["api_key_env"] == "OPENAI_API_KEY"


# ── HTTP mapping ───────────────────────────────────────────────────────────────────


def test_payment_required_maps_to_402():
    from types import SimpleNamespace

    from apps.api_server.routers.llm import _llm_api_http_exception
    from apps.api_server.services.llm_api_service import LLMAPIError

    req = SimpleNamespace(state=SimpleNamespace(request_id="req-1"))
    http = _llm_api_http_exception(
        LLMAPIError("payment_required", "cap reached", {"code": "managed_llm_spend_cap_exceeded"}),
        req,
    )
    assert http.status_code == 402
    assert http.detail["error"]["code"] == "payment_required"
