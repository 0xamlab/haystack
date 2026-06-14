"""Wave 2 PR-5a: managed-LLM accounting foundation.

Covers the additive pieces only (no resolution-path change yet): pricing math + conservative
fallback, the spend-cap resolver, recording + summing managed vs BYOK spend, the fail-closed 402
cap gate, the org managed-LLM column defaults, and the managed-mode env switch. The 3-tier key
resolver + the call-site wiring land in PR-5b.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from apps.api_server.models.llm_usage_record import USD_MICROS, LLMKeyType
from apps.api_server.services import llm_pricing
from apps.api_server.services.llm_spend_service import (
    check_llm_spend_quota,
    get_monthly_llm_spend_micros,
    managed_llm_mode_enabled,
    record_llm_usage,
    resolve_llm_spend_cap_micros,
)

# ── Pricing (pure) ────────────────────────────────────────────────────────────


def test_pricing_known_model_is_token_times_rate():
    # claude-sonnet = $3/Mtok in, $15/Mtok out → micros = tokens · rate.
    micros = llm_pricing.compute_cost_micros(
        model="claude-sonnet-4-6", prompt_tokens=1_000, completion_tokens=500
    )
    assert micros == 1_000 * 3 + 500 * 15  # 10_500 µ$ = $0.0105


def test_pricing_unknown_model_is_never_free():
    # An unrecognized id must meter via the conservative fallback ($10 in / $30 out), not $0.
    micros = llm_pricing.compute_cost_micros(
        model="totally-made-up-model-2099", prompt_tokens=1_000, completion_tokens=1_000
    )
    assert micros == 1_000 * 10 + 1_000 * 30  # 40_000 µ$
    assert micros > 0


def test_pricing_specific_before_family():
    # "gpt-4o-mini" must not be priced as the pricier "gpt-4o".
    mini = llm_pricing.compute_cost_micros(model="gpt-4o-mini", prompt_tokens=1_000)
    full = llm_pricing.compute_cost_micros(model="gpt-4o-2024-08-06", prompt_tokens=1_000)
    assert mini < full


# ── Cap resolver (pure) ─────────────────────────────────────────────────────────


def test_cap_resolver_plan_default_and_override():
    assert resolve_llm_spend_cap_micros("free", None) == 5 * USD_MICROS
    assert resolve_llm_spend_cap_micros("pro", None) == 200 * USD_MICROS
    # A per-org override (>0) wins over the plan default…
    assert resolve_llm_spend_cap_micros("free", 2) == 2 * USD_MICROS
    # …including capping an otherwise-unlimited plan.
    assert resolve_llm_spend_cap_micros("enterprise", 100) == 100 * USD_MICROS
    # Enterprise with no override = unlimited (0).
    assert resolve_llm_spend_cap_micros("enterprise", None) == 0


# ── Managed-mode switch ─────────────────────────────────────────────────────────


def test_managed_mode_switch_reads_env(monkeypatch):
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    assert managed_llm_mode_enabled() is False
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    assert managed_llm_mode_enabled() is True
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "off")
    assert managed_llm_mode_enabled() is False


# ── DB-backed accounting ────────────────────────────────────────────────────────


async def _seed_org(plan="free", quota=0):
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus

    async with AsyncSessionLocal() as s:
        org = Organization(
            name="Managed LLM Test",
            slug=f"mllm-{uuid.uuid4().hex[:8]}",
            plan=OrgPlan(plan),
            status=OrgStatus.ACTIVE,
            managed_llm_quota_usd_month=quota,
        )
        s.add(org)
        await s.commit()
        return org.id


async def test_org_managed_llm_columns_default():
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization

    org_id = await _seed_org()
    async with AsyncSessionLocal() as s:
        org = await s.get(Organization, org_id)
        assert org.managed_llm_enabled is False
        assert org.managed_llm_quota_usd_month == 0


async def test_record_byok_is_free_managed_is_metered():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id = await _seed_org()
    async with AsyncSessionLocal() as s:
        byok = await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-sonnet-4-6",
            key_type=LLMKeyType.BYOK, prompt_tokens=1_000, completion_tokens=1_000, db=s,
        )
        managed = await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-sonnet-4-6",
            key_type=LLMKeyType.MANAGED, prompt_tokens=1_000, completion_tokens=1_000, db=s,
        )
        await s.commit()
    assert byok == 0  # customer pays their provider — never platform-metered
    assert managed == 1_000 * 3 + 1_000 * 15  # 18_000 µ$

    async with AsyncSessionLocal() as s:
        total = await get_monthly_llm_spend_micros(org_id, s)
    assert total == managed  # only the managed row counts


async def test_check_quota_passes_under_cap_and_402s_over():
    from apps.api_server.db.session import AsyncSessionLocal

    # Tight per-org override: $1/mo managed budget.
    org_id = await _seed_org(plan="free", quota=1)

    # Nothing spent yet → passes.
    async with AsyncSessionLocal() as s:
        await check_llm_spend_quota(org_id=org_id, plan="free", managed_quota_usd_month=1, db=s)

    # Spend past $1: claude-sonnet 400k input = 400k·$3/Mtok = 1_200_000 µ$ > 1_000_000.
    async with AsyncSessionLocal() as s:
        await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-sonnet-4-6",
            key_type=LLMKeyType.MANAGED, prompt_tokens=400_000, db=s,
        )
        await s.commit()

    async with AsyncSessionLocal() as s:
        with pytest.raises(HTTPException) as exc:
            await check_llm_spend_quota(org_id=org_id, plan="free", managed_quota_usd_month=1, db=s)
    assert exc.value.status_code == 402
    assert exc.value.detail["error"]["code"] == "managed_llm_spend_cap_exceeded"


async def test_unlimited_cap_never_blocks():
    from apps.api_server.db.session import AsyncSessionLocal

    org_id = await _seed_org(plan="enterprise", quota=0)
    async with AsyncSessionLocal() as s:
        await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-opus-4",
            key_type=LLMKeyType.MANAGED, prompt_tokens=1_000_000, completion_tokens=1_000_000, db=s,
        )
        await s.commit()
    async with AsyncSessionLocal() as s:
        # enterprise + no override = unlimited → no raise even after large spend.
        await check_llm_spend_quota(
            org_id=org_id, plan="enterprise", managed_quota_usd_month=0, db=s
        )
