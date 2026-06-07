"""
GET /v1/calibration — Confidence calibration status for the calling org.

Surfaces the org's historical prediction accuracy so users can understand
how much to trust confidence scores and how the auto-learning loop is performing.

No new MCP tool needed — this is a transparency endpoint for dashboards and audit.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.calibration_service import CalibrationStats, get_calibration

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Calibration"])


class CalibrationResponse(BaseModel):
    """Org-level confidence calibration state."""

    org_id: str
    is_reliable: bool
    n_samples: int
    bias: float | None
    rmse_pct: float | None
    hit_rate: float | None
    direction: str
    confidence_multiplier: float
    summary: str
    last_updated: str | None


@router.get(
    "/v1/calibration",
    response_model=CalibrationResponse,
    summary="Get confidence calibration status",
    description=(
        "Returns the org's historical prediction accuracy metrics computed from all "
        "recorded outcomes (`PATCH /v1/decisions/{id}/outcome`). "
        "The `confidence_multiplier` is applied automatically to every simulation "
        "and recommendation once `n_samples >= 5`.\n\n"
        "**Key fields**\n"
        "- `bias`: mean relative error — negative means over-optimistic\n"
        "- `hit_rate`: fraction of predictions within ±20% of actual\n"
        "- `confidence_multiplier`: factor currently applied to raw simulation confidence\n"
        "- `is_reliable`: false until 5+ outcomes are recorded"
    ),
)
async def get_calibration_status(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CalibrationResponse:
    org_id_str = str(auth["org_id"])
    _ws = auth.get("workspace_id")
    stats: CalibrationStats = get_calibration(org_id_str, str(_ws) if _ws else None)

    return CalibrationResponse(
        org_id=org_id_str,
        is_reliable=stats.is_reliable,
        n_samples=stats.n_samples,
        bias=round(stats.bias, 6) if stats.is_reliable else None,
        rmse_pct=round(stats.rmse_pct, 6) if stats.is_reliable else None,
        hit_rate=round(stats.hit_rate, 4) if stats.is_reliable else None,
        direction=stats.direction,
        confidence_multiplier=round(stats.confidence_multiplier(), 4),
        summary=stats.summary(),
        last_updated=stats.last_updated.isoformat() if stats.is_reliable else None,
    )
