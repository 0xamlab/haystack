"""
Decision Memory — /v1/decisions

Persistent log of every decision made through the engine, with outcome tracking.

Lifecycle:
  POST   /v1/decisions              — log a decision (links to a run_id)
  GET    /v1/decisions              — list logged decisions (most recent first)
  GET    /v1/decisions/{id}         — get a single decision record
  PATCH  /v1/decisions/{id}/outcome — record what actually happened (closes the loop)
  DELETE /v1/decisions/{id}         — soft-delete (org data hygiene)

This is the foundation of the self-improving engine:
  Δ = actual_outcome - expected_value
  Over time, track which decision types are over/under-confident.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.decision_log import DecisionLog
from apps.api_server.schemas.response import DecisionPlan
from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Decision Memory"])


# ─── Request / Response schemas ───────────────────────────────────────────────

class LogDecisionRequest(BaseModel):
    """Body for POST /v1/decisions — log a decision that was made."""
    run_id: uuid.UUID | None = Field(
        None,
        description=(
            "ID of the simulation run that produced this decision "
            "(links DecisionPlan -> DecisionLog)."
        ),
    )
    context: str | None = Field(
        None,
        max_length=2000,
        description="Free-text description of the business situation when this decision was made.",
    )
    chosen_action: str = Field(..., max_length=200, description="The action that was chosen.")
    options_considered: list[str] | None = Field(
        None,
        description="All option names that were evaluated before choosing.",
    )
    expected_value: float | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    rationale: str | None = Field(None, max_length=2000)
    risk_p5: float | None = None
    risk_p95: float | None = None
    risk_pol: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Probability of loss at decision time",
    )
    request_hash: str | None = Field(None, max_length=64)
    result_hash: str | None = Field(None, max_length=64)

    @classmethod
    def from_decision_plan(
        cls,
        plan: DecisionPlan,
        context: str | None = None,
    ) -> LogDecisionRequest:
        """Convenience: build a LogDecisionRequest from a DecisionPlan."""
        return cls(
            context=context,
            chosen_action=plan.recommended_action,
            options_considered=[o.name for o in plan.options],
            expected_value=plan.expected_value,
            confidence=plan.confidence,
            rationale=plan.rationale,
            risk_p5=plan.risk.p5,
            risk_p95=plan.risk.p95,
            risk_pol=plan.risk.probability_of_loss,
            request_hash=plan.integrity.get("request_hash") if plan.integrity else None,
            result_hash=plan.integrity.get("result_hash") if plan.integrity else None,
        )


class RecordOutcomeRequest(BaseModel):
    """Body for PATCH /v1/decisions/{id}/outcome — close the feedback loop."""
    actual_outcome: float = Field(
        ...,
        description="Observed outcome value (e.g. actual monthly revenue).",
    )
    outcome_notes: str | None = Field(None, max_length=2000)


class ExecuteDecisionRequest(BaseModel):
    """Body for POST /v1/decisions/{id}/execute — fire the decision to a webhook."""
    webhook_url: str = Field(
        ...,
        max_length=2048,
        description="HTTPS endpoint that will receive and act on this decision.",
    )
    timeout_seconds: float = Field(
        default=10.0, ge=1.0, le=60.0,
        description="Webhook request timeout in seconds.",
    )
    force: bool = Field(
        default=False,
        description=(
            "Override the idempotency gate. Pass true to re-execute a decision that was "
            "already delivered. Does NOT override confidence or risk_floor gates."
        ),
    )
    override_safety: bool = Field(
        default=False,
        description=(
            "Bypass confidence and risk_floor policy gates for this single execution. "
            "Requires explicit intent. Logs the override for audit."
        ),
    )
    metadata: dict | None = Field(
        None,
        description="Optional extra key-value pairs merged into the webhook payload.",
    )


class ExecutionReceipt(BaseModel):
    """Returned by POST /v1/decisions/{id}/execute."""
    decision_id: uuid.UUID
    webhook_url: str
    execution_status: str          # "delivered" | "failed"
    response_code: int | None
    executed_at: datetime
    payload_summary: dict          # Compact preview of what was sent
    safety_overridden: bool = False   # True when override_safety was used


class DecisionLogResponse(BaseModel):
    """Single decision log entry."""
    id: uuid.UUID
    org_id: uuid.UUID
    run_id: uuid.UUID | None
    context: str | None
    chosen_action: str
    options_considered: list[str] | None
    expected_value: float | None
    confidence: float | None
    rationale: str | None
    risk_p5: float | None
    risk_p95: float | None
    risk_pol: float | None
    request_hash: str | None
    result_hash: str | None
    actual_outcome: float | None
    outcome_delta: float | None
    outcome_notes: str | None
    outcome_recorded_at: datetime | None
    executed_at: datetime | None
    execution_status: str | None
    execution_webhook_url: str | None
    execution_response_code: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, m: DecisionLog) -> DecisionLogResponse:
        options: list[str] | None = None
        if m.options_considered:
            try:
                options = json.loads(m.options_considered)
            except (json.JSONDecodeError, TypeError):
                options = [m.options_considered]
        return cls(
            id=m.id,
            org_id=m.org_id,
            run_id=m.run_id,
            context=m.context,
            chosen_action=m.chosen_action,
            options_considered=options,
            expected_value=m.expected_value,
            confidence=m.confidence,
            rationale=m.rationale,
            risk_p5=m.risk_p5,
            risk_p95=m.risk_p95,
            risk_pol=m.risk_pol,
            request_hash=m.request_hash,
            result_hash=m.result_hash,
            actual_outcome=m.actual_outcome,
            outcome_delta=m.outcome_delta,
            outcome_notes=m.outcome_notes,
            outcome_recorded_at=m.outcome_recorded_at,
            executed_at=m.executed_at,
            execution_status=m.execution_status,
            execution_webhook_url=m.execution_webhook_url,
            execution_response_code=m.execution_response_code,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class DecisionListResponse(BaseModel):
    decisions: list[DecisionLogResponse]
    total: int
    page: int
    limit: int
    pages: int
    page_size: int


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/v1/decisions",
    response_model=DecisionLogResponse,
    status_code=201,
    summary="Log a decision",
    description=(
        "Record a decision that was made. Link it to a simulation run_id to bind "
        "the full DecisionPlan context. Call PATCH /outcome later to close the loop."
    ),
)
async def log_decision(
    payload: LogDecisionRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> DecisionLogResponse:
    entry = DecisionLog(
        org_id=auth["org_id"],
        run_id=payload.run_id,
        context=payload.context,
        chosen_action=payload.chosen_action,
        options_considered=(
            json.dumps(payload.options_considered)
            if payload.options_considered
            else None
        ),
        expected_value=payload.expected_value,
        confidence=payload.confidence,
        rationale=payload.rationale,
        risk_p5=payload.risk_p5,
        risk_p95=payload.risk_p95,
        risk_pol=payload.risk_pol,
        request_hash=payload.request_hash,
        result_hash=payload.result_hash,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    logger.info(
        "decision_logged",
        decision_id=str(entry.id),
        org_id=str(auth["org_id"]),
        chosen_action=entry.chosen_action,
    )
    return DecisionLogResponse.from_model(entry)


@router.get(
    "/v1/decisions",
    response_model=DecisionListResponse,
    summary="List logged decisions",
    description="Returns the org's decision history, most recent first. Supports pagination.",
)
async def list_decisions(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
    page_size: int | None = Query(
        default=None,
        ge=1,
        le=200,
        description="Legacy compatibility alias for limit.",
    ),
    with_outcome_only: bool = Query(
        default=False,
        description="When true, return only decisions where actual_outcome has been recorded.",
    ),
) -> DecisionListResponse:
    effective_limit = int(limit or page_size or 20)
    offset = (page - 1) * effective_limit
    stmt = (
        select(DecisionLog)
        .where(DecisionLog.org_id == auth["org_id"])
        .order_by(DecisionLog.created_at.desc())
        .offset(offset)
        .limit(effective_limit)
    )
    if with_outcome_only:
        stmt = stmt.where(DecisionLog.actual_outcome.is_not(None))

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    # Total count
    from sqlalchemy import func
    count_stmt = (
        select(func.count())
        .select_from(DecisionLog)
        .where(DecisionLog.org_id == auth["org_id"])
    )
    if with_outcome_only:
        count_stmt = count_stmt.where(DecisionLog.actual_outcome.is_not(None))
    total = (await db.execute(count_stmt)).scalar_one()

    return DecisionListResponse(
        decisions=[DecisionLogResponse.from_model(r) for r in rows],
        total=total,
        page=page,
        limit=effective_limit,
        pages=max(1, (total + effective_limit - 1) // effective_limit),
        page_size=effective_limit,
    )


@router.get(
    "/v1/decisions/{decision_id}",
    response_model=DecisionLogResponse,
    summary="Get a single decision",
)
async def get_decision(
    decision_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> DecisionLogResponse:
    result = await db.execute(
        select(DecisionLog)
        .where(DecisionLog.id == decision_id, DecisionLog.org_id == auth["org_id"])
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Decision not found")
    return DecisionLogResponse.from_model(entry)


@router.patch(
    "/v1/decisions/{decision_id}/outcome",
    response_model=DecisionLogResponse,
    summary="Record actual outcome",
    description=(
        "Close the feedback loop: record what actually happened after the "
        "decision was made. Sets actual_outcome, computes outcome_delta = "
        "actual - expected, and timestamps the recording."
    ),
)
async def record_outcome(
    decision_id: uuid.UUID,
    payload: RecordOutcomeRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> DecisionLogResponse:
    result = await db.execute(
        select(DecisionLog)
        .where(DecisionLog.id == decision_id, DecisionLog.org_id == auth["org_id"])
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Decision not found")

    entry.actual_outcome = payload.actual_outcome
    entry.outcome_notes = payload.outcome_notes
    entry.outcome_recorded_at = datetime.now(UTC)
    if entry.expected_value is not None:
        entry.outcome_delta = payload.actual_outcome - entry.expected_value

    await db.commit()
    await db.refresh(entry)

    # ── Auto-learning loop: refresh calibration from all org outcomes ──────────
    # Runs synchronously (fast: DB query + in-memory update) after every outcome.
    try:
        from apps.api_server.services.calibration_service import refresh_calibration_from_db
        await refresh_calibration_from_db(str(auth["org_id"]), db)
    except Exception as _cal_exc:
        logger.warning("calibration_refresh_failed", error=str(_cal_exc))

    logger.info(
        "outcome_recorded",
        decision_id=str(entry.id),
        expected=entry.expected_value,
        actual=entry.actual_outcome,
        delta=entry.outcome_delta,
    )
    return DecisionLogResponse.from_model(entry)


@router.post(
    "/v1/decisions/{decision_id}/execute",
    response_model=ExecutionReceipt,
    status_code=200,
    summary="Execute a decision via webhook",
    description=(
        "Fire the decision to an external webhook URL, turning the logged decision "
        "into an automated action. The webhook receives the full decision context "
        "(chosen action, expected value, confidence, risk profile, integrity hashes). "
        "Execution status and the HTTP response code are persisted back to the decision log "
        "for full audit trail. Re-execution is allowed — each call overwrites the prior receipt."
    ),
)
async def execute_decision(
    decision_id: uuid.UUID,
    payload: ExecuteDecisionRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> ExecutionReceipt:
    result = await db.execute(
        select(DecisionLog)
        .where(DecisionLog.id == decision_id, DecisionLog.org_id == auth["org_id"])
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Decision not found")

    # ── Safety gates (policy-configurable per org) ────────────────────────────
    from apps.api_server.services.execution_policy_service import (
        check_execution_gates,
        get_policy,
    )
    org_id_str = str(auth["org_id"])
    policy = get_policy(org_id_str)
    already_executed = entry.execution_status == "delivered"
    violation = check_execution_gates(
        policy=policy,
        confidence=entry.confidence,
        risk_p5=entry.risk_p5,
        already_executed=already_executed,
        force=payload.force,
        override_safety=payload.override_safety,
    )
    if violation:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": f"execution_blocked_{violation.gate}",
                    "gate": violation.gate,
                    "message": violation.detail,
                    "override_hint": violation.override_hint,
                }
            },
        )

    if payload.override_safety and (
        entry.confidence is not None and entry.confidence < policy.min_confidence
        or (policy.risk_floor is not None and entry.risk_p5 is not None
            and entry.risk_p5 < -policy.risk_floor)
    ):
        logger.warning(
            "execution_safety_override",
            decision_id=str(decision_id),
            confidence=entry.confidence,
            risk_p5=entry.risk_p5,
            org_id=org_id_str,
        )

    # Build the webhook payload — full decision context, structured for action
    options: list[str] | None = None
    if entry.options_considered:
        try:
            options = json.loads(entry.options_considered)
        except (json.JSONDecodeError, TypeError):
            options = [entry.options_considered]

    webhook_payload: dict = {
        "event":         "decision.execute",
        "decision_id":   str(entry.id),
        "org_id":        str(entry.org_id),
        "decision": {
            "chosen_action":      entry.chosen_action,
            "context":            entry.context,
            "expected_value":     entry.expected_value,
            "confidence":         entry.confidence,
            "rationale":          entry.rationale,
            "options_considered": options,
            "risk": {
                "p5":  entry.risk_p5,
                "p95": entry.risk_p95,
                "probability_of_loss": entry.risk_pol,
            },
            "run_id":    str(entry.run_id) if entry.run_id else None,
        },
        "integrity": {
            k: v for k, v in {
                "request_hash": entry.request_hash,
                "result_hash":  entry.result_hash,
            }.items() if v
        } or None,
    }
    if payload.metadata:
        webhook_payload["metadata"] = payload.metadata

    # Dispatch to webhook
    executed_at = datetime.now(UTC)
    response_code: int | None = None
    execution_status = "failed"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=payload.timeout_seconds) as client:
            resp = await client.post(payload.webhook_url, json=webhook_payload)
            response_code = resp.status_code
            execution_status = "delivered" if resp.is_success else "failed"
    except Exception as exc:
        logger.warning(
            "execution_webhook_failed",
            decision_id=str(decision_id),
            webhook_url=payload.webhook_url,
            error=str(exc),
        )
        execution_status = "failed"

    # Persist execution receipt
    entry.executed_at = executed_at
    entry.execution_status = execution_status
    entry.execution_webhook_url = payload.webhook_url
    entry.execution_response_code = response_code
    entry.execution_receipt = json.dumps({
        "webhook_url":   payload.webhook_url,
        "response_code": response_code,
        "executed_at":   executed_at.isoformat(),
        "status":        execution_status,
    })
    await db.commit()

    logger.info(
        "decision_executed",
        decision_id=str(entry.id),
        webhook_url=payload.webhook_url,
        status=execution_status,
        response_code=response_code,
    )

    return ExecutionReceipt(
        decision_id=entry.id,
        webhook_url=payload.webhook_url,
        execution_status=execution_status,
        response_code=response_code,
        executed_at=executed_at,
        payload_summary={
            "chosen_action":  entry.chosen_action,
            "expected_value": entry.expected_value,
            "confidence":     entry.confidence,
        },
        safety_overridden=payload.override_safety,
    )


@router.delete(
    "/v1/decisions/{decision_id}",
    status_code=204,
    response_model=None,
    summary="Delete a decision log entry",
)
async def delete_decision(
    decision_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(DecisionLog)
        .where(DecisionLog.id == decision_id, DecisionLog.org_id == auth["org_id"])
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Decision not found")
    await db.execute(
        delete(DecisionLog)
        .where(DecisionLog.id == decision_id, DecisionLog.org_id == auth["org_id"])
    )
    await db.commit()
