"""
/v1/metering — local runtime execution analytics ingestion.

Called by the Algenta daemon (apps.runtime.metering.MeteringQueue._flush)
every 60 seconds with a batch of local execution events.

This endpoint is analytics-only.  Quota enforcement is handled by the
credit bucket (POST /v1/credits/refresh) and the device heartbeat.
Events are structured-logged for the analytics pipeline and counted in
Redis for dashboards.  No UsageRecord rows are written here (which
avoids double-counting with cloud-API quota checks).

POST /v1/metering
  Body:    { device_id, events: [...] }
  Response: { accepted, billing_period }
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["metering"])

# Redis key TTL — 35 days covers any billing period + buffer
_METERING_TTL = 35 * 86_400


# ── Request / response ────────────────────────────────────────────────────────

class MeteringEvent(BaseModel):
    event_type:  str   = ""
    module:      str   = ""
    function:    str   = ""
    engine_used: str   = ""
    latency_ms:  float = 0.0
    success:     bool  = True
    timestamp:   float = 0.0
    request_id:  str   = ""


class MeteringBatchRequest(BaseModel):
    device_id: str                  = Field(..., min_length=1, max_length=64)
    events:    list[MeteringEvent]  = Field(default_factory=list)


class MeteringBatchResponse(BaseModel):
    accepted:       int
    billing_period: str


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/v1/metering",
    response_model=MeteringBatchResponse,
    summary="Ingest local runtime execution analytics",
    description=(
        "Called by the local runtime daemon to flush buffered execution events. "
        "Analytics only — quota enforcement is handled by the credit bucket. "
        "Events are structured-logged for the analytics pipeline."
    ),
)
async def ingest_metering_events(
    body: MeteringBatchRequest,
    ctx:  Annotated[AuthContext, Depends(get_current_org)],
) -> MeteringBatchResponse:
    if not body.events:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code":    "empty_events",
                    "message": "events list cannot be empty",
                }
            },
        )

    org_id = ctx["org_id"]
    now    = datetime.now(UTC)

    # Group events by billing period (derived from per-event timestamp).
    # Events collected around a midnight crossing may span two periods.
    period_counts: dict[str, int] = defaultdict(int)
    for event in body.events:
        if event.timestamp:
            period = datetime.fromtimestamp(
                event.timestamp, tz=UTC
            ).strftime("%Y-%m")
        else:
            period = now.strftime("%Y-%m")
        period_counts[period] += 1

    primary_period = max(period_counts, key=lambda p: period_counts[p])

    # Increment analytics counter in Redis (best-effort — never fails the call).
    await _increment_metering_counter(org_id, period_counts)

    # Structured log for analytics pipeline / SIEM / data warehouse ingestion.
    logger.info(
        "metering_events_ingested",
        org_id=str(org_id),
        device_id=body.device_id[:8],
        accepted=len(body.events),
        billing_period=primary_period,
        modules_used=sorted({e.module for e in body.events if e.module}),
        success_rate=round(
            sum(1 for e in body.events if e.success) / len(body.events), 4
        ),
        avg_latency_ms=round(
            sum(e.latency_ms for e in body.events) / len(body.events), 2
        ),
    )

    return MeteringBatchResponse(
        accepted=len(body.events),
        billing_period=primary_period,
    )


# ── Redis analytics counter ───────────────────────────────────────────────────

async def _increment_metering_counter(
    org_id: object,
    period_counts: dict[str, int],
) -> None:
    """Atomically increment metering event counters per billing period.

    Key:   metering_events:{org_id}:{YYYY-MM}
    Value: cumulative count of local execution events reported this period.
    Used by usage dashboards; not used for quota enforcement.
    """
    try:
        import redis.asyncio as aioredis

        from apps.api_server.config import get_settings

        r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        for period, count in period_counts.items():
            key     = f"metering_events:{org_id}:{period}"
            new_val = await r.incrby(key, count)
            if new_val == count:
                await r.expire(key, _METERING_TTL)
        await r.aclose()
    except Exception as exc:
        logger.debug("metering_counter_redis_failed", error=str(exc))
