"""Managed-LLM spend metering + cap enforcement (D3).

The platform meters every *managed* (pooled-key) LLM call in ``llm_usage_records`` and fails closed
when an org's monthly managed spend reaches its cap. BYOK calls (the org's own provider key) are
recorded with zero platform cost — the customer pays their provider directly — so they never count
toward the cap. Spend is denominated in micro-dollars (``USD_MICROS``).

This module is the accounting foundation (PR-5a). The 3-tier key resolver + the pre-call gate /
post-call metering call sites are wired in PR-5b; ``managed_llm_mode_enabled()`` is the deployment
switch they consult (it mirrors ``tenant_keys.require_per_tenant_keys`` — a direct env read, so the
sync resolver can consult it without a Settings round-trip).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.llm_usage_record import USD_MICROS, LLMKeyType, LLMUsageRecord
from apps.api_server.services import llm_pricing, plan_limits

logger = structlog.get_logger(__name__)

_BILLING_PERIOD_FMT = "%Y-%m"
_TRUTHY = {"1", "true", "yes", "on"}


def managed_llm_mode_enabled() -> bool:
    """True if this deployment runs in managed-LLM mode (hosted). Default off (self-host/BYOK).

    Read directly from the environment (like ``require_per_tenant_keys``) so the synchronous key
    resolver can consult it. OFF preserves legacy behavior exactly: the pooled env key is THE key
    for the single tenant; no managed gating, no metering.
    """
    return os.environ.get("ALGENTA_MANAGED_LLM", "").strip().lower() in _TRUTHY


def current_billing_period() -> str:
    """Current "YYYY-MM" billing window in UTC (same window UsageRecord uses)."""
    return datetime.now(UTC).strftime(_BILLING_PERIOD_FMT)


def resolve_llm_spend_cap_micros(plan: str, managed_quota_usd_month: int | None) -> int:
    """Resolve the monthly managed-LLM spend cap in micro-dollars. 0 = unlimited.

    A per-org override (``organizations.managed_llm_quota_usd_month`` > 0) takes precedence over the
    plan default (``plan_limits.llm_spend_cap_usd_month``) — so an explicit org budget can cap even
    an otherwise-unlimited plan, and a generous plan can be tightened per org.
    """
    if managed_quota_usd_month and managed_quota_usd_month > 0:
        return managed_quota_usd_month * USD_MICROS
    cap_usd = plan_limits.get(plan).llm_spend_cap_usd_month
    return max(0, cap_usd) * USD_MICROS


async def get_monthly_llm_spend_micros(
    org_id: uuid.UUID,
    db: AsyncSession,
    period: str | None = None,
) -> int:
    """Sum the org's managed-LLM spend (micro-dollars) for the period. DB is the source of truth.

    BYOK rows carry ``cost_usd_micros == 0`` so summing all rows == summing managed spend.
    """
    period = period or current_billing_period()
    result = await db.execute(
        select(func.coalesce(func.sum(LLMUsageRecord.cost_usd_micros), 0))
        .where(LLMUsageRecord.org_id == org_id)
        .where(LLMUsageRecord.billing_period == period)
    )
    return int(result.scalar_one() or 0)


async def record_llm_usage(
    *,
    org_id: uuid.UUID,
    backend: str,
    model: str,
    key_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    api_key_id: uuid.UUID | None = None,
    db: AsyncSession,
    period: str | None = None,
) -> int:
    """Record one LLM call and return its platform cost in micro-dollars.

    Cost is 0 for BYOK (the customer pays the provider). For MANAGED calls the cost is estimated via
    ``llm_pricing`` (conservative fallback for unknown models — never free). Adds the row + flushes;
    the caller owns the transaction (commit).
    """
    cost_micros = 0
    if key_type == LLMKeyType.MANAGED:
        cost_micros = llm_pricing.compute_cost_micros(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    record = LLMUsageRecord(
        org_id=org_id,
        api_key_id=api_key_id,
        billing_period=period or current_billing_period(),
        backend=backend,
        model=model,
        key_type=str(key_type),
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
        cache_read_tokens=max(0, cache_read_tokens),
        cache_write_tokens=max(0, cache_write_tokens),
        cost_usd_micros=cost_micros,
    )
    db.add(record)
    await db.flush()
    return cost_micros


async def check_llm_spend_quota(
    *,
    org_id: uuid.UUID,
    plan: str,
    managed_quota_usd_month: int | None,
    db: AsyncSession,
    period: str | None = None,
) -> None:
    """Fail closed (HTTP 402) when the org has reached its monthly managed-LLM spend cap.

    Called BEFORE a managed LLM call so we never start an over-budget request. Unlimited cap
    (resolved to 0) always passes. This is the enforcement half of the free-tier
    ``llm_spend_cap_usd_month`` defined in PR-3.
    """
    cap_micros = resolve_llm_spend_cap_micros(plan, managed_quota_usd_month)
    if cap_micros <= 0:
        return  # unlimited

    period = period or current_billing_period()
    spent_micros = await get_monthly_llm_spend_micros(org_id, db, period=period)
    if spent_micros >= cap_micros:
        logger.warning(
            "managed_llm_spend_cap_exceeded",
            org_id=str(org_id),
            plan=plan,
            spent_micros=spent_micros,
            cap_micros=cap_micros,
            period=period,
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": {
                    "code": "managed_llm_spend_cap_exceeded",
                    "message": (
                        f"Monthly managed-LLM spend cap reached "
                        f"(${spent_micros / USD_MICROS:.2f} of ${cap_micros / USD_MICROS:.2f}). "
                        "Add your own provider key (BYOK) or upgrade your plan to continue."
                    ),
                    "spent_usd": round(spent_micros / USD_MICROS, 4),
                    "limit_usd": round(cap_micros / USD_MICROS, 2),
                    "billing_period": period,
                    "upgrade_url": "https://decisionengine.io/pricing",
                }
            },
        )
