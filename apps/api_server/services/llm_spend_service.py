"""Managed-LLM spend metering + cap enforcement (D3).

The platform meters every *managed* (pooled-key) LLM call in ``llm_usage_records`` and fails closed
when an org's monthly managed spend reaches its cap. BYOK calls (the org's own provider key) are
recorded with zero platform cost — the customer pays their provider directly — so they never count
toward the cap. Spend is denominated in micro-dollars (``USD_MICROS``).

PR-5b wires this into the call path: ``provider_chat_completion`` AND ``provider_embeddings`` run
``gate_managed_llm_call`` before the provider call (fail closed over-cap) and ``meter_managed_llm_call``
after (record the managed spend). Both no-op unless the call resolves to the managed key, so BYOK +
self-host paths are untouched. ``managed_llm_mode_enabled`` (the deployment switch) lives in ``tenant_keys`` beside
``require_per_tenant_keys`` and is re-exported here for callers that import it from this module.

CAP SOUNDNESS: the gate is a best-effort PRE-call check, not a reservation — a single call can
overshoot once the gate passes (bounded by the model's context window × rate), and two concurrent
managed calls can both pass before either records (TOCTOU). So the cap bounds *when new managed
calls stop being accepted*, not exact total spend; combined with the per-minute rate limit + the
concurrent-jobs cap, managed spend stays bounded, never unbounded. Metering writes are best-effort
(a write failure logs + continues rather than failing the user's already-succeeded call), so the
recorded total can slightly under-count on a DB blip.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.llm_usage_record import USD_MICROS, LLMKeyType, LLMUsageRecord
from apps.api_server.services import llm_pricing, plan_limits
from apps.api_server.services.tenant_keys import (
    KEY_TYPE_MANAGED,
    current_org_keys,
    managed_llm_mode_enabled,  # noqa: F401 — re-exported (stable import path for callers/tests)
    provider_key_type,
)

logger = structlog.get_logger(__name__)

_BILLING_PERIOD_FMT = "%Y-%m"


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


async def over_spend_cap(
    *,
    org_id: uuid.UUID,
    plan: str,
    managed_quota_usd_month: int | None,
    db: AsyncSession,
    period: str | None = None,
) -> tuple[bool, int, int]:
    """Return (is_over, spent_micros, cap_micros) for the org's monthly managed-LLM spend.

    Unlimited cap (resolved to 0) → (False, spent, 0). The single source of truth both error
    surfaces build on: the HTTP gate (``check_llm_spend_quota``, 402) and the provider-layer gate
    (``gate_managed_llm_call``, LLMAPIError)."""
    cap_micros = resolve_llm_spend_cap_micros(plan, managed_quota_usd_month)
    if cap_micros <= 0:
        return False, 0, 0
    spent_micros = await get_monthly_llm_spend_micros(org_id, db, period=period)
    return spent_micros >= cap_micros, spent_micros, cap_micros


def _spend_cap_detail(spent_micros: int, cap_micros: int, period: str) -> dict:
    return {
        "code": "managed_llm_spend_cap_exceeded",
        "message": (
            f"Monthly managed-LLM spend cap reached "
            f"(${spent_micros / USD_MICROS:.2f} of ${cap_micros / USD_MICROS:.2f}). "
            "Add your own provider key (BYOK) or upgrade your plan to continue."
        ),
        "spent_usd": round(spent_micros / USD_MICROS, 4),
        "limit_usd": round(cap_micros / USD_MICROS, 2),
        "billing_period": period,
        "upgrade_url": "https://algenta.ai/pricing",
    }


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
    period = period or current_billing_period()
    is_over, spent_micros, cap_micros = await over_spend_cap(
        org_id=org_id, plan=plan, managed_quota_usd_month=managed_quota_usd_month, db=db, period=period
    )
    if is_over:
        logger.warning(
            "managed_llm_spend_cap_exceeded",
            org_id=str(org_id), plan=plan, spent_micros=spent_micros,
            cap_micros=cap_micros, period=period,
        )
        raise HTTPException(status_code=402, detail={"error": _spend_cap_detail(spent_micros, cap_micros, period)})


# ── Provider-layer call-path wiring (PR-5b) ──────────────────────────────────────
# Both no-op unless the call resolves to the MANAGED key (provider_key_type), so BYOK + self-host
# paths are completely untouched. They read the org context from the request/run ContextVar
# (current_org_keys) and use their OWN short-lived session (like resolve_org_keys) — the LLM call
# path threads no DB session.


async def gate_managed_llm_call(*, backend: str, api_key_env: str | None) -> None:
    """PRE-call fail-closed gate for a managed LLM call. No-op for BYOK/self-host/none.

    Raises ``LLMAPIError("payment_required", ...)`` when the org is over its managed spend cap —
    the provider router maps that to HTTP 402 and does NOT retry other targets."""
    if provider_key_type(api_key_env, backend) != KEY_TYPE_MANAGED:
        return
    keys = current_org_keys()
    if keys is None or keys.org_id is None:
        return
    period = current_billing_period()
    async with AsyncSessionLocal() as db:
        is_over, spent_micros, cap_micros = await over_spend_cap(
            org_id=keys.org_id, plan=keys.plan or "free",
            managed_quota_usd_month=keys.managed_quota_usd_month, db=db, period=period,
        )
    if is_over:
        from apps.api_server.services.llm_api_service import LLMAPIError

        logger.warning(
            "managed_llm_spend_cap_exceeded",
            org_id=str(keys.org_id), backend=backend, spent_micros=spent_micros,
            cap_micros=cap_micros, period=period,
        )
        detail = _spend_cap_detail(spent_micros, cap_micros, period)
        raise LLMAPIError("payment_required", detail["message"], detail)


async def meter_managed_llm_call(
    *,
    backend: str,
    api_key_env: str | None,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> None:
    """POST-call metering for a managed LLM call. No-op for BYOK/self-host/none.

    Best-effort: a metering write failure is logged and swallowed — the user's call already
    succeeded, so we never turn an accounting blip into a failed (and possibly re-charged) request.
    The recorded total can therefore slightly under-count on a DB error (see module caveat)."""
    if provider_key_type(api_key_env, backend) != KEY_TYPE_MANAGED:
        return
    keys = current_org_keys()
    if keys is None or keys.org_id is None:
        return
    try:
        async with AsyncSessionLocal() as db:
            await record_llm_usage(
                org_id=keys.org_id, backend=backend, model=model, key_type=LLMKeyType.MANAGED,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                cache_read_tokens=cache_read_tokens, cache_write_tokens=cache_write_tokens, db=db,
            )
            await db.commit()
    except Exception as exc:
        logger.warning(
            "managed_llm_meter_failed",
            org_id=str(keys.org_id), backend=backend, model=model, error=str(exc),
        )
