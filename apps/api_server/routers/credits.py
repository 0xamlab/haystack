"""
/v1/credits — credit bucket refresh for the local runtime daemon.

Called by the Algenta daemon (apps/runtime/credits._background_refresh) when
the local execution credit pool drops below 10%.

Flow:
  1. Validate API key → resolve org + plan
  2. Read credits_issued_this_month from Redis  (key: credits_issued:{org}:{YYYY-MM})
  3. Deny if issued >= monthly_limit
  4. Grant min(batch_size, monthly_remaining) credits
  5. Atomically INCRBY credits_issued counter in Redis
  6. Return CreditRefreshResponse — daemon applies the grant locally

Redis key:  credits_issued:{org_id}:{YYYY-MM}
Redis TTL:  35 days  (covers any billing period + buffer)

Enforcement guarantee:
  Max overage = one credit batch.  A PRO org (500k/mo, 10k batch) can overshoot
  by at most 10k executions — <2%.  Enterprise gets 100k batches but is unlimited.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.plan_limits import (
    credit_batch_size as _batch_size,
)
from apps.api_server.services.plan_limits import (
    execution_quota as _monthly_limit,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["credits"])

_CREDIT_TTL = 86_400  # 24h per batch
_COUNTER_TTL = 35 * 86_400  # Redis key lifetime


# ── Request / response ────────────────────────────────────────────────────────


class CreditRefreshRequest(BaseModel):
    device_id: str
    billing_period: str  # "YYYY-MM"
    credits_used: int = 0  # client-reported, for analytics only


class CreditRefreshResponse(BaseModel):
    credits_granted: int
    credits_issued_this_month: int
    monthly_limit: int  # 0 = unlimited
    monthly_remaining: int  # 0 when unlimited
    billing_period: str
    expires_at: float  # unix timestamp — credits expire after this
    refresh_after: float  # daemon should refresh again after this
    server_time: float


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post(
    "/v1/credits/refresh",
    response_model=CreditRefreshResponse,
    summary="Issue an execution credit batch to the bundled runtime",
    description=(
        "The bundled runtime calls this endpoint automatically when its credit "
        "pool drops below 10%. Returns the number of credits granted and the "
        "expiry timestamp. Denied (HTTP 429) when the organization's monthly "
        "quota is exhausted."
    ),
)
async def refresh_credits(
    body: CreditRefreshRequest,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreditRefreshResponse:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from apps.api_server.models.api_key import APIKey

    if ctx["key_id"] is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "api_key_identity_required",
                    "message": "This endpoint requires an API-key identity.",
                }
            },
        )
    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.organization)).where(APIKey.id == ctx["key_id"])
    )
    api_key_row = result.scalar_one_or_none()
    if api_key_row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "api_key_not_found", "message": "API key not found."}},
        )
    plan = str(api_key_row.organization.plan)
    org_id = api_key_row.org_id

    batch = _batch_size(plan)
    monthly_max = _monthly_limit(plan)  # 0 = unlimited

    # ── Unlimited plan — grant full batch immediately ──────────────────────
    if monthly_max == 0:
        now = time.time()
        logger.info(
            "credits_granted_unlimited",
            org_id=str(org_id),
            plan=plan,
            granted=batch,
            device_id=body.device_id[:8],
        )
        return CreditRefreshResponse(
            credits_granted=batch,
            credits_issued_this_month=0,
            monthly_limit=0,
            monthly_remaining=0,
            billing_period=body.billing_period,
            expires_at=now + _CREDIT_TTL,
            refresh_after=now + _CREDIT_TTL * 0.9,
            server_time=now,
        )

    # ── Fetch issued-this-month from Redis (or DB fallback) ────────────────
    redis_key = f"credits_issued:{org_id}:{body.billing_period}"
    issued_so_far = await _get_issued(redis_key, org_id, body.billing_period, db)
    monthly_remaining = max(0, monthly_max - issued_so_far)

    if monthly_remaining <= 0:
        logger.warning(
            "credit_refresh_denied_quota",
            org_id=str(org_id),
            plan=plan,
            issued=issued_so_far,
            limit=monthly_max,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exhausted",
                "message": (
                    f"Monthly execution quota exhausted for plan '{plan}' "
                    f"({monthly_max:,} executions/mo).  "
                    f"Upgrade your plan or wait for the next billing period."
                ),
                "monthly_limit": monthly_max,
                "issued_this_month": issued_so_far,
                "billing_period": body.billing_period,
                "upgrade_url": "https://algenta.io/pricing",
            },
        )

    grant = min(batch, monthly_remaining)
    await _increment_issued(redis_key, grant, org_id, body.billing_period, db)
    new_issued = issued_so_far + grant

    now = time.time()
    logger.info(
        "credits_granted",
        org_id=str(org_id),
        plan=plan,
        granted=grant,
        issued_this_month=new_issued,
        monthly_remaining=max(0, monthly_max - new_issued),
        device_id=body.device_id[:8] if len(body.device_id) > 8 else body.device_id,
    )

    return CreditRefreshResponse(
        credits_granted=grant,
        credits_issued_this_month=new_issued,
        monthly_limit=monthly_max,
        monthly_remaining=max(0, monthly_max - new_issued),
        billing_period=body.billing_period,
        expires_at=now + _CREDIT_TTL,
        refresh_after=now + _CREDIT_TTL * 0.9,
        server_time=now,
    )


# ── Redis helpers (with DB fallback) ─────────────────────────────────────────


async def _get_issued(
    redis_key: str,
    org_id: uuid.UUID,
    billing_period: str,
    db: AsyncSession,
) -> int:
    """Return credits_issued for org this billing period."""
    # Try Redis first (fast path)
    try:
        import redis.asyncio as aioredis

        from apps.api_server.config import get_settings

        aioredis_module: Any = aioredis
        r = aioredis_module.from_url(get_settings().redis_url, decode_responses=True)
        val = await r.get(redis_key)
        await r.aclose()
        if val is not None:
            return int(val)
    except Exception as exc:
        logger.debug(
            "credits_issued_redis_read_failed",
            org_id=str(org_id),
            billing_period=billing_period,
            error=str(exc),
        )

    # Redis unavailable — fall back to DB count
    from sqlalchemy import func, select

    from apps.api_server.models.usage_record import UsageRecord

    result = await db.execute(
        select(func.coalesce(func.sum(UsageRecord.billing_units), 0))
        .where(UsageRecord.org_id == org_id)
        .where(UsageRecord.billing_period == billing_period)
    )
    return int(result.scalar_one() or 0)


async def _increment_issued(
    redis_key: str,
    amount: int,
    org_id: uuid.UUID,
    billing_period: str,
    db: AsyncSession,
) -> None:
    """Atomically record that `amount` credits were just issued."""
    try:
        import redis.asyncio as aioredis

        from apps.api_server.config import get_settings

        aioredis_module: Any = aioredis
        r = aioredis_module.from_url(get_settings().redis_url, decode_responses=True)
        new_val = await r.incrby(redis_key, amount)
        if new_val == amount:
            await r.expire(redis_key, _COUNTER_TTL)
        await r.aclose()
        return
    except Exception as exc:
        logger.debug(
            "credits_issued_redis_increment_failed",
            org_id=str(org_id),
            billing_period=billing_period,
            amount=amount,
            error=str(exc),
        )

    # Redis unavailable — persist as a usage_record (approximate but durable)
    from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord

    db.add(
        UsageRecord(
            org_id=org_id,
            billing_period=billing_period,
            endpoint=UsageEndpoint.SIMULATE,
            billing_units=amount,
            scenarios_run=0,
        )
    )
    await db.flush()
