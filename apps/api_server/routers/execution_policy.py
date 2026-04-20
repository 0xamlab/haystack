"""
GET  /v1/execution/policy  — get the org's autonomous execution policy
PATCH /v1/execution/policy — update policy thresholds

No new MCP tool — this is a configuration endpoint for operators and dashboards.
Changes take effect immediately for all subsequent executions.
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.execution_policy_service import (
    ExecutionPolicy,
    get_policy,
    set_policy,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Execution Policy"])


class ExecutionPolicyResponse(BaseModel):
    """Current execution policy for the calling org."""
    org_id: str
    min_confidence: float
    risk_floor: float | None
    require_calibration: bool
    allow_reexecution: bool
    updated_at: str


class UpdatePolicyRequest(BaseModel):
    """Partial update — only supplied fields are changed."""
    min_confidence: float | None = Field(
        None, ge=0.0, le=1.0,
        description="Minimum confidence to allow execution (0–1). Default: 0.5.",
    )
    risk_floor: float | None = Field(
        None, ge=0.0,
        description=(
            "Maximum tolerable downside loss (absolute). "
            "If p5 < -risk_floor the execution is blocked. "
            "Set to null to disable the check."
        ),
    )
    require_calibration: bool | None = Field(
        None,
        description=(
            "When true, trigger auto_execute is disabled until the org has ≥5 "
            "recorded outcomes. Manual execution is always allowed."
        ),
    )
    allow_reexecution: bool | None = Field(
        None,
        description="When true, already-executed decisions can fire again without force=true.",
    )


def _to_response(org_id: str, policy: ExecutionPolicy) -> ExecutionPolicyResponse:
    return ExecutionPolicyResponse(
        org_id=org_id,
        min_confidence=policy.min_confidence,
        risk_floor=policy.risk_floor,
        require_calibration=policy.require_calibration,
        allow_reexecution=policy.allow_reexecution,
        updated_at=policy.updated_at.isoformat(),
    )


@router.get(
    "/v1/execution/policy",
    response_model=ExecutionPolicyResponse,
    summary="Get execution policy",
    description=(
        "Returns the org's current autonomous execution safety policy. "
        "Gates applied to every POST /v1/decisions/{id}/execute call and trigger auto_execute:\n\n"
        "- **min_confidence**: decisions below this confidence are blocked\n"
        "- **risk_floor**: decisions where worst-case (p5) exceeds this loss are blocked\n"
        "- **require_calibration**: auto_execute waits for ≥5 recorded outcomes\n"
        "- **allow_reexecution**: idempotency — prevents double-actions\n\n"
        "All gates can be bypassed individually: `force=true` (idempotency) or "
        "`override_safety=true` (confidence + risk_floor)."
    ),
)
async def get_execution_policy(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> ExecutionPolicyResponse:
    org_id = str(auth["org_id"])
    return _to_response(org_id, get_policy(org_id))


@router.patch(
    "/v1/execution/policy",
    response_model=ExecutionPolicyResponse,
    summary="Update execution policy",
    description=(
        "Partial update — only supplied fields are changed. Changes take effect "
        "immediately for all subsequent executions. Audit logs record every update."
    ),
)
async def update_execution_policy(
    payload: UpdatePolicyRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> ExecutionPolicyResponse:
    org_id = str(auth["org_id"])
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    policy = set_policy(org_id, **updates)

    logger.info(
        "execution_policy_updated",
        org_id=org_id,
        changes=updates,
    )
    return _to_response(org_id, policy)
