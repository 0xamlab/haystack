"""
Quota enforcement and usage recording service.

Provides:
- check_quota()       — raise 429 if org has exceeded monthly execution limit
- record_usage()      — write one UsageRecord row per billable API call
- get_usage_count()   — count usage records for current billing period

Plan quotas — defined in plan_limits.py (single source of truth):
  free/starter:  10,000 executions/month
  developer/pro: 500,000 executions/month
  team:          1,000,000 executions/month
  enterprise:    unlimited

Rate limiting (per-minute) is enforced via Redis INCR + EXPIRE.
Monthly quota is enforced by counting usage_records rows.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings
from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord

logger = structlog.get_logger(__name__)
settings = get_settings()

# ─── Plan definitions (derived from plan_limits.py) ──────────────────────────
# Keep PLAN_QUOTAS as a compatibility shim for code that imports it directly.
# New code should import from plan_limits instead.

_QUOTA_COMPAT_OVERRIDES: dict[str, dict[str, int | bool]] = {
    "free": {
        "simulations_month": 500,
        "rate_per_minute": 60,
        "async_jobs": False,
        "webhooks": False,
        "max_runs": 10_000,
        "max_batch": 10,
    },
    "developer": {
        "simulations_month": 10_000,
        "rate_per_minute": 300,
        "async_jobs": True,
        "webhooks": True,
        "max_runs": 100_000,
        "max_batch": 10,
    },
    "pro": {
        "simulations_month": 100_000,
        "rate_per_minute": 1_000,
        "async_jobs": True,
        "webhooks": True,
        "max_runs": 1_000_000,
        "max_batch": 100,
    },
}


def _build_plan_quotas() -> dict[str, dict]:
    from apps.api_server.services.plan_limits import _PLANS
    quotas = {
        name: {
            "simulations_month": cfg.executions_month,
            "rate_per_minute":   cfg.rate_per_minute,
            "async_jobs":        cfg.async_jobs,
            "webhooks":          cfg.webhooks,
            "max_runs":          cfg.max_runs_per_call,
            "max_batch":         cfg.max_batch,
        }
        for name, cfg in _PLANS.items()
    }
    for plan_name, overrides in _QUOTA_COMPAT_OVERRIDES.items():
        quotas.setdefault(plan_name, {}).update(overrides)
    return quotas

PLAN_QUOTAS: dict[str, dict] = _build_plan_quotas()

_BILLING_PERIOD_FMT = "%Y-%m"


def _current_billing_period() -> str:
    return datetime.now(UTC).strftime(_BILLING_PERIOD_FMT)


def _quota_cfg(plan: str) -> dict:
    return PLAN_QUOTAS.get(plan, PLAN_QUOTAS["free"])


def _set_rate_limit_state(request_state: Any | None, *, limit: int, remaining: int) -> None:
    if request_state is None:
        return
    request_state.rate_limit_limit = int(limit)
    request_state.rate_limit_remaining = max(int(remaining), 0)


# ─── Monthly quota check ──────────────────────────────────────────────────────

async def check_monthly_quota(
    org_id: uuid.UUID,
    plan: str,
    db: AsyncSession,
) -> None:
    """
    Check whether the org has remaining monthly simulation quota.
    Raises HTTP 429 if quota is exhausted.
    Enterprise plan (quota = 0) is always allowed.

    This is called BEFORE running the simulation so we fail fast.
    """
    limit = int(_quota_cfg(plan)["simulations_month"])

    if limit == 0:
        # Unlimited plan
        return

    period = _current_billing_period()
    result = await db.execute(
        select(func.count(UsageRecord.id))
        .where(UsageRecord.org_id == org_id)
        .where(UsageRecord.billing_period == period)
    )
    used = result.scalar_one() or 0

    if used >= limit:
        logger.warning(
            "quota_exceeded",
            org_id=str(org_id),
            plan=plan,
            used=used,
            limit=limit,
            period=period,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "quota_exceeded",
                    "message": (
                        f"Monthly simulation quota exhausted ({used}/{limit}). "
                        f"Upgrade your plan or wait until {period} resets."
                    ),
                    "used": used,
                    "limit": limit,
                    "billing_period": period,
                    "upgrade_url": "https://decisionengine.io/pricing",
                }
            },
        )


# ─── Rate limit check (Redis sliding window) ──────────────────────────────────

async def check_rate_limit(
    org_id: uuid.UUID,
    plan: str,
    redis_client: object,
    request_state: Any | None = None,
) -> None:
    """
    Per-minute sliding window rate limit enforced in Redis.
    Key: ratelimit:{org_id}:{YYYY-MM-DDTHH:MM}
    TTL: 70 seconds (covers the full minute + buffer)

    Raises HTTP 429 if rate limit exceeded.
    """
    rpm_limit = int(_quota_cfg(plan)["rate_per_minute"])
    allow_runtime_fallbacks = settings.allow_runtime_fallbacks

    # Use minute-level granularity
    minute_key = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M")
    redis_key = f"ratelimit:{org_id}:{minute_key}"

    try:
        r = redis_client  # type: ignore[attr-defined]
        current = await r.incr(redis_key)
        if current == 1:
            await r.expire(redis_key, 70)  # 70s TTL to cover minute boundary

        _set_rate_limit_state(
            request_state,
            limit=rpm_limit,
            remaining=max(rpm_limit - int(current), 0),
        )

        if current > rpm_limit:
            logger.warning(
                "rate_limit_exceeded",
                org_id=str(org_id),
                plan=plan,
                current=current,
                limit=rpm_limit,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": (
                            f"Rate limit exceeded. Max {rpm_limit} requests/minute "
                            f"for {plan} plan."
                        ),
                        "limit": rpm_limit,
                        "retry_after_seconds": 60,
                    }
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(rpm_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "rate_limit_backend_unavailable",
            error=str(exc),
            org_id=str(org_id),
            fallback_allowed=allow_runtime_fallbacks,
        )
        if allow_runtime_fallbacks:
            return
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "rate_limit_backend_unavailable",
                    "message": "Rate limiting backend unavailable.",
                    "details": {
                        "backend": "redis",
                        "policy": "strict_runtime",
                    },
                }
            },
            headers={"Retry-After": "30"},
        ) from exc


# ─── Usage recording ──────────────────────────────────────────────────────────

async def record_usage(
    org_id: uuid.UUID,
    plan: str,
    endpoint: UsageEndpoint,
    db: AsyncSession,
    *,
    api_key_id: uuid.UUID | None = None,
    simulation_run_id: uuid.UUID | None = None,
    scenarios_run: int = 0,
    billing_units: int = 1,
    org_email: str | None = None,
    org_name: str | None = None,
) -> UsageRecord:
    """
    Write one UsageRecord row for a completed billable API call.

    After recording:
    - Pushes metered usage to Stripe (non-blocking)
    - Sends quota alert emails at 80% and 100% (non-blocking)
    """
    period = _current_billing_period()
    record = UsageRecord(
        org_id=org_id,
        api_key_id=api_key_id,
        simulation_run_id=simulation_run_id,
        billing_period=period,
        endpoint=endpoint,
        billing_units=billing_units,
        scenarios_run=scenarios_run,
    )
    db.add(record)
    await db.flush()

    logger.info(
        "usage_recorded",
        org_id=str(org_id),
        plan=plan,
        endpoint=endpoint.value,
        billing_units=billing_units,
        scenarios_run=scenarios_run,
        period=period,
    )

    # ── Push metered usage to Stripe (non-blocking) ────────────────────────
    import asyncio
    asyncio.create_task(
        _push_stripe_usage(org_id=org_id, billing_units=billing_units, db=db)
    )

    # ── Quota alert emails at 80% / 100% ──────────────────────────────────
    if org_email:
        asyncio.create_task(
            _maybe_send_quota_alert(
                org_id=org_id, plan=plan, org_email=org_email,
                org_name=org_name or "Your Organization", db=db,
            )
        )

    return record


async def _push_stripe_usage(org_id: uuid.UUID, billing_units: int, db: AsyncSession) -> None:
    """Push one simulation unit of metered usage to Stripe. Fire-and-forget."""
    try:
        from sqlalchemy import select

        from apps.api_server.config import get_settings
        from apps.api_server.models.organization import Organization

        settings = get_settings()
        if not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test"):
            return  # Skip in dev / test mode unless real key

        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        if not org or not org.stripe_customer_id:
            return

        import time

        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                "https://api.stripe.com/v1/billing/meter_events",
                headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
                data={
                    "event_name": "simulation_run",
                    "payload[stripe_customer_id]": org.stripe_customer_id,
                    "payload[value]": str(billing_units),
                    "timestamp": str(int(time.time())),
                },
            )
    except Exception as exc:
        logger.warning("stripe_usage_push_failed", org_id=str(org_id), error=str(exc))


async def _maybe_send_quota_alert(
    org_id: uuid.UUID, plan: str, org_email: str, org_name: str, db: AsyncSession
) -> None:
    """Send quota alert email at 80% and 100% (once per billing period per threshold)."""
    try:
        import redis.asyncio as aioredis

        from apps.api_server.config import get_settings
        settings = get_settings()

        used = await get_monthly_usage_count(org_id, db)
        limit = int(_quota_cfg(plan)["simulations_month"])
        if limit == 0:
            return  # Unlimited plan

        pct = (used / limit) * 100 if limit > 0 else 0
        period = _current_billing_period()

        # Determine which threshold we just crossed
        threshold = None
        if pct >= 100:
            threshold = 100
        elif pct >= 80:
            threshold = 80

        if threshold is None:
            return

        # Check if we already sent this alert this period (Redis dedup)
        try:
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            alert_key = f"quota_alert:{org_id}:{period}:{threshold}"
            already_sent = await r.get(alert_key)
            if already_sent:
                return
            # Mark sent — expire after 35 days (covers billing period)
            await r.set(alert_key, "1", ex=35 * 86400)
            await r.aclose()
        except Exception as exc:
            logger.warning("quota_alert_dedup_unavailable", org_id=str(org_id), error=str(exc))

        from apps.api_server.services.email_service import send_quota_alert
        send_quota_alert(
            email=org_email,
            org_name=org_name,
            plan=plan,
            used=used,
            limit=limit,
            billing_period=period,
            pct=pct,
        )
        logger.info("quota_alert_sent", org_id=str(org_id), threshold=threshold, pct=pct)
    except Exception as exc:
        logger.warning("quota_alert_failed", org_id=str(org_id), error=str(exc))


async def get_monthly_usage_count(
    org_id: uuid.UUID,
    db: AsyncSession,
    billing_period: str | None = None,
) -> int:
    """Return count of usage records for the given billing period (defaults to current month)."""
    period = billing_period or _current_billing_period()
    result = await db.execute(
        select(func.count(UsageRecord.id))
        .where(UsageRecord.org_id == org_id)
        .where(UsageRecord.billing_period == period)
    )
    return result.scalar_one() or 0


# ─── Redis quota counter (sub-50ms hot path) ──────────────────────────────────

def _quota_redis_key(org_id: uuid.UUID, period: str) -> str:
    return f"quota_count:{org_id}:{period}"

# TTL: 35 days — covers full month + 5-day buffer for late-arriving events
_QUOTA_COUNTER_TTL = 35 * 86_400


async def check_quota_redis(
    org_id: uuid.UUID,
    plan: str,
    redis_client: object,
) -> None:
    """
    Redis-counter quota check — ~1ms vs ~8ms DB COUNT.

    On cold start (no Redis key yet), reads the DB count once and seeds the counter.
    Falls back to DB check if Redis is unavailable.

    Raises HTTP 429 when quota is exhausted.
    """
    limit = int(_quota_cfg(plan)["simulations_month"])
    if limit == 0:
        return  # Unlimited plan

    period = _current_billing_period()
    key    = _quota_redis_key(org_id, period)

    try:
        r = redis_client  # type: ignore[attr-defined]

        # Try to GET the counter
        raw = await r.get(key)

        if raw is None:
            # Cold start — seed from DB (happens once per org per month)
            # Use a fresh DB session since we're in a hot-path dependency
            from apps.api_server.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(func.count(UsageRecord.id))
                    .where(UsageRecord.org_id == org_id)
                    .where(UsageRecord.billing_period == period)
                )
                db_count = result.scalar_one() or 0
            # SET with TTL (not SETEX — use SET with EX parameter via set())
            await r.set(key, db_count, ex=_QUOTA_COUNTER_TTL)
            raw = db_count
        else:
            raw = int(raw)

        if int(raw) >= limit:
            logger.warning(
                "quota_exceeded_redis",
                org_id=str(org_id),
                plan=plan,
                used=int(raw),
                limit=limit,
                period=period,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "code": "quota_exceeded",
                        "message": (
                            f"Monthly simulation quota exhausted ({int(raw)}/{limit}). "
                            f"Upgrade your plan or wait until {period} resets."
                        ),
                        "used": int(raw),
                        "limit": limit,
                        "billing_period": period,
                        "upgrade_url": "https://decisionengine.io/pricing",
                    }
                },
            )

    except HTTPException:
        raise
    except Exception as exc:
        # Redis unavailable — fall back to DB check. This keeps quota enforcement
        # correct while making the degraded path explicit in logs.
        logger.warning(
            "quota_backend_unavailable_db_fallback",
            error=str(exc),
            org_id=str(org_id),
            fallback_backend="database",
        )
        from apps.api_server.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await check_monthly_quota(org_id, plan, db)


async def incr_quota_counter(
    org_id: uuid.UUID,
    period: str,
    redis_client: object,
) -> None:
    """
    Atomically increment the Redis quota counter after a successful simulation.
    Called from the persist task — not the hot path.
    """
    key = _quota_redis_key(org_id, period)
    try:
        r = redis_client  # type: ignore[attr-defined]
        current = await r.incr(key)
        # Refresh TTL on every increment so active orgs never expire mid-month
        if current == 1:
            # New key (wasn't seeded yet) — set TTL
            await r.expire(key, _QUOTA_COUNTER_TTL)
    except Exception as exc:
        logger.warning(
            "quota_counter_incr_failed",
            org_id=str(org_id),
            period=period,
            error=str(exc),
        )
