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
import os
import uuid
from datetime import UTC, datetime
from functools import cache
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.models.decision_log import DecisionLog
from apps.api_server.schemas.response import DecisionPlan, build_decision_plan
from apps.api_server.schemas.simulate import SimulateRequest
from apps.api_server.services.audit_service import get_client_ip, write_audit_event
from apps.api_server.services.workspace_scope import workspace_id_for_write, workspace_scope_clauses
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.egress_guard import (
    EgressPolicyDeniedError,
    async_http_request,
    audit_context_from_auth,
)
from apps.api_server.services.quota_service import check_quota_redis, check_rate_limit
from apps.api_server.services.simulation_service import run_simulation_fast
from apps.runtime_manifest import load_runtime_manifest

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Decision Memory"])


@cache
def _runtime_manifest_metadata() -> dict[str, str]:
    manifest = load_runtime_manifest(
        api_env=os.environ.get("API_ENV", "local"),
        runtime_library_http_api_enabled=os.environ.get(
            "RUNTIME_LIBRARY_HTTP_API_ENABLED",
            "",
        ).lower()
        in {"1", "true", "yes", "on"},
        deployment_mode=os.environ.get("ALGENTA_DEPLOYMENT_MODE", "local_dev_daemon"),
    )
    return {
        "schema_snapshot_id": manifest.schema_snapshot.snapshot_id,
        "manifest_version": manifest.module_manifest_version,
    }


def _current_policy_snapshot_id(org_id: str) -> str:
    from apps.api_server.services.execution_policy_service import get_policy

    return get_policy(org_id).snapshot_id


def _decision_audit_metadata(
    entry: DecisionLog,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "decision_id": str(entry.id),
        "chosen_action": entry.chosen_action,
        "run_id": str(entry.run_id) if entry.run_id else None,
        "request_hash": entry.request_hash,
        "result_hash": entry.result_hash,
        "policy_snapshot_id": entry.policy_snapshot_id,
        "schema_snapshot_id": entry.schema_snapshot_id,
        "manifest_version": entry.manifest_version,
    }
    if extra:
        metadata.update(extra)
    return {key: value for key, value in metadata.items() if value is not None}


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
            run_id=None,
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
        default=10.0,
        ge=1.0,
        le=60.0,
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
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional extra key-value pairs merged into the webhook payload.",
    )


class ExecutionReceipt(BaseModel):
    """Returned by POST /v1/decisions/{id}/execute."""

    decision_id: uuid.UUID
    webhook_url: str
    execution_status: str  # "delivered" | "failed"
    response_code: int | None
    executed_at: datetime
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    payload_summary: dict[str, Any]  # Compact preview of what was sent
    safety_overridden: bool = False  # True when override_safety was used


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
    policy_snapshot_id: str | None
    schema_snapshot_id: str | None
    manifest_version: str | None
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
            policy_snapshot_id=m.policy_snapshot_id,
            schema_snapshot_id=m.schema_snapshot_id,
            manifest_version=m.manifest_version,
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
    "/v1/decisions/plan",
    response_model=DecisionPlan,
    status_code=200,
    summary="Generate a structured decision plan",
    description=(
        "Run the same validated simulation request contract as /v1/simulate, but return only "
        "the structured DecisionPlan summary. This is intended for LLM and dashboard clients "
        "that need the compact plan object without the full DecisionEnvelope payload."
    ),
)
async def plan_decision(
    request: Request,
    payload: SimulateRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: object = Depends(get_redis),
) -> DecisionPlan:
    await check_rate_limit(
        auth["org_id"],
        auth["plan"],
        redis_client,
        request_state=request.state,
    )
    await check_quota_redis(auth["org_id"], auth["plan"], redis_client)

    envelope, _persist_meta = await run_simulation_fast(
        request=payload,
        org_id=auth["org_id"],
        api_key_id=auth["key_id"],
    )
    plan = build_decision_plan(envelope)

    try:
        from apps.api_server.services.calibration_service import calibrate_confidence

        calibrated_confidence, calibration_stats = calibrate_confidence(
            plan.confidence,
            str(auth["org_id"]),
            workspace_id=str(auth["workspace_id"]) if auth.get("workspace_id") else None,
        )
        plan.confidence = calibrated_confidence
        if calibration_stats.is_reliable:
            plan.calibration = calibration_stats.summary()
    except Exception as exc:
        logger.debug(
            "decision_plan_calibration_skipped",
            error=str(exc),
            request_id=getattr(request.state, "request_id", None),
            org_id=str(auth["org_id"]),
        )

    logger.info(
        "decision_plan_generated",
        request_id=getattr(request.state, "request_id", None),
        run_id=str(envelope.run_id),
        recommended_action=plan.recommended_action,
        org_id=str(auth["org_id"]),
    )
    return plan


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
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> DecisionLogResponse:
    org_id_str = str(auth["org_id"])
    runtime_metadata = _runtime_manifest_metadata()
    entry = DecisionLog(
        org_id=auth["org_id"],
        workspace_id=workspace_id_for_write(auth),
        run_id=payload.run_id,
        context=payload.context,
        chosen_action=payload.chosen_action,
        options_considered=(
            json.dumps(payload.options_considered) if payload.options_considered else None
        ),
        expected_value=payload.expected_value,
        confidence=payload.confidence,
        rationale=payload.rationale,
        risk_p5=payload.risk_p5,
        risk_p95=payload.risk_p95,
        risk_pol=payload.risk_pol,
        request_hash=payload.request_hash,
        result_hash=payload.result_hash,
        policy_snapshot_id=_current_policy_snapshot_id(org_id_str),
        schema_snapshot_id=runtime_metadata["schema_snapshot_id"],
        manifest_version=runtime_metadata["manifest_version"],
    )
    db.add(entry)
    await db.flush()
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="decision.log",
        resource_type="decision_log",
        resource_id=str(entry.id),
        ip_address=get_client_ip(request),
        metadata=_decision_audit_metadata(entry),
    )
    await db.commit()
    await db.refresh(entry)

    logger.info(
        "decision_logged",
        decision_id=str(entry.id),
        org_id=org_id_str,
        chosen_action=entry.chosen_action,
        policy_snapshot_id=entry.policy_snapshot_id,
        schema_snapshot_id=entry.schema_snapshot_id,
        manifest_version=entry.manifest_version,
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
        .where(*workspace_scope_clauses(DecisionLog, auth))
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
        select(func.count()).select_from(DecisionLog).where(*workspace_scope_clauses(DecisionLog, auth))
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
        select(DecisionLog).where(
            DecisionLog.id == decision_id, *workspace_scope_clauses(DecisionLog, auth)
        )
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
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> DecisionLogResponse:
    result = await db.execute(
        select(DecisionLog).where(
            DecisionLog.id == decision_id, *workspace_scope_clauses(DecisionLog, auth)
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Decision not found")

    entry.actual_outcome = payload.actual_outcome
    entry.outcome_notes = payload.outcome_notes
    entry.outcome_recorded_at = datetime.now(UTC)
    if entry.expected_value is not None:
        entry.outcome_delta = payload.actual_outcome - entry.expected_value

    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="decision.outcome",
        resource_type="decision_log",
        resource_id=str(entry.id),
        ip_address=get_client_ip(request),
        metadata=_decision_audit_metadata(
            entry,
            extra={
                "actual_outcome": payload.actual_outcome,
                "outcome_delta": entry.outcome_delta,
            },
        ),
    )
    await db.commit()
    await db.refresh(entry)

    # ── Auto-learning loop: refresh calibration from all org outcomes ──────────
    # Runs synchronously (fast: DB query + in-memory update) after every outcome.
    try:
        from apps.api_server.services.calibration_service import refresh_calibration_from_db

        await refresh_calibration_from_db(
            str(auth["org_id"]),
            db,
            workspace_id=str(auth["workspace_id"]) if auth.get("workspace_id") else None,
        )
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
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> ExecutionReceipt:
    result = await db.execute(
        select(DecisionLog).where(
            DecisionLog.id == decision_id, *workspace_scope_clauses(DecisionLog, auth)
        )
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
    runtime_metadata = _runtime_manifest_metadata()
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
        entry.confidence is not None
        and entry.confidence < policy.min_confidence
        or (
            policy.risk_floor is not None
            and entry.risk_p5 is not None
            and entry.risk_p5 < -policy.risk_floor
        )
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

    webhook_payload: dict[str, Any] = {
        "event": "decision.execute",
        "decision_id": str(entry.id),
        "org_id": str(entry.org_id),
        "decision": {
            "chosen_action": entry.chosen_action,
            "context": entry.context,
            "expected_value": entry.expected_value,
            "confidence": entry.confidence,
            "rationale": entry.rationale,
            "options_considered": options,
            "risk": {
                "p5": entry.risk_p5,
                "p95": entry.risk_p95,
                "probability_of_loss": entry.risk_pol,
            },
            "run_id": str(entry.run_id) if entry.run_id else None,
        },
        "integrity": {
            k: v
            for k, v in {
                "request_hash": entry.request_hash,
                "result_hash": entry.result_hash,
                "policy_snapshot_id": policy.snapshot_id,
                "schema_snapshot_id": entry.schema_snapshot_id
                or runtime_metadata["schema_snapshot_id"],
                "manifest_version": entry.manifest_version
                or runtime_metadata["manifest_version"],
            }.items()
            if v
        }
        or None,
    }
    if payload.metadata:
        webhook_payload["metadata"] = payload.metadata

    # Dispatch to webhook
    executed_at = datetime.now(UTC)
    response_code: int | None = None
    execution_status = "failed"

    try:
        resp = await async_http_request(
            method="POST",
            url=payload.webhook_url,
            surface="decision_execution_webhook",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_auth(
                auth,
                request_id=getattr(request.state, "request_id", None),
            ),
            client_kwargs={"timeout": payload.timeout_seconds},
            json=webhook_payload,
        )
        response_code = resp.status_code
        execution_status = "delivered" if resp.is_success else "failed"
    except EgressPolicyDeniedError as exc:
        logger.warning(
            "execution_webhook_blocked",
            decision_id=str(decision_id),
            webhook_url=payload.webhook_url,
            reason=exc.decision.reason,
        )
        execution_status = "failed"
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
    if entry.policy_snapshot_id is None:
        entry.policy_snapshot_id = policy.snapshot_id
    if entry.schema_snapshot_id is None:
        entry.schema_snapshot_id = runtime_metadata["schema_snapshot_id"]
    if entry.manifest_version is None:
        entry.manifest_version = runtime_metadata["manifest_version"]
    entry.execution_receipt = json.dumps(
        {
            "webhook_url": payload.webhook_url,
            "response_code": response_code,
            "executed_at": executed_at.isoformat(),
            "status": execution_status,
            "policy_snapshot_id": policy.snapshot_id,
            "schema_snapshot_id": entry.schema_snapshot_id,
            "manifest_version": entry.manifest_version,
        }
    )
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="decision.execute",
        resource_type="decision_log",
        resource_id=str(entry.id),
        ip_address=get_client_ip(request),
        result="success" if execution_status == "delivered" else "failure",
        metadata=_decision_audit_metadata(
            entry,
            extra={
                "webhook_url": payload.webhook_url,
                "response_code": response_code,
                "execution_status": execution_status,
                "safety_overridden": payload.override_safety,
            },
        ),
    )
    await db.commit()

    logger.info(
        "decision_executed",
        decision_id=str(entry.id),
        webhook_url=payload.webhook_url,
        status=execution_status,
        response_code=response_code,
        policy_snapshot_id=policy.snapshot_id,
    )

    return ExecutionReceipt(
        decision_id=entry.id,
        webhook_url=payload.webhook_url,
        execution_status=execution_status,
        response_code=response_code,
        executed_at=executed_at,
        policy_snapshot_id=policy.snapshot_id,
        schema_snapshot_id=entry.schema_snapshot_id or runtime_metadata["schema_snapshot_id"],
        manifest_version=entry.manifest_version or runtime_metadata["manifest_version"],
        payload_summary={
            "chosen_action": entry.chosen_action,
            "expected_value": entry.expected_value,
            "confidence": entry.confidence,
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
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(DecisionLog).where(
            DecisionLog.id == decision_id, *workspace_scope_clauses(DecisionLog, auth)
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Decision not found")
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="decision.delete",
        resource_type="decision_log",
        resource_id=str(decision_id),
        ip_address=get_client_ip(request),
        metadata=_decision_audit_metadata(entry),
    )
    await db.execute(
        delete(DecisionLog).where(
            DecisionLog.id == decision_id, *workspace_scope_clauses(DecisionLog, auth)
        )
    )
    await db.commit()
