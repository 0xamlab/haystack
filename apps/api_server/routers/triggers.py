"""
Real-time trigger layer — /v1/triggers

Register threshold conditions on data sources. When a source is queried and
its current metric value crosses the registered threshold, the trigger fires:
  1. Runs the attached simulation template
  2. Logs the result to Decision Memory
  3. Optionally dispatches a webhook

Architecture (current: manual + check-on-query):
  - Triggers stored in-process dict (no DB — no migration needed for MVP)
  - fire_trigger: explicit evaluation + simulation execution
  - list_triggers: inspect all registered triggers
  - Future: background worker polls sources on a schedule

POST   /v1/triggers              — register a trigger
GET    /v1/triggers              — list all triggers
POST   /v1/triggers/{id}/fire   — manually fire / force evaluate
PATCH  /v1/triggers/{id}/pause  — pause a trigger
DELETE /v1/triggers/{id}        — remove a trigger
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, TypeAdapter

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    EgressPolicyDeniedError,
    async_http_request,
    audit_context_from_auth,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Triggers"])

# ── In-process trigger store (per-org, per-process) ───────────────────────────
# Keyed by (org_id_str, trigger_id).  For a production deployment, swap this
# for a DB-backed store (trigger_logs table + migration 0017).
_TRIGGER_STORE: dict[str, dict[str, Any]] = {}  # trigger_id → trigger_record


# ─── Request / Response schemas ───────────────────────────────────────────────


class TriggerCondition(BaseModel):
    source_id: str
    metric_hint: str
    threshold: float
    direction: Literal["above", "below", "change"]
    aggregation: Literal["sum", "avg", "max", "min", "count"] = "sum"


class RegisterTriggerRequest(BaseModel):
    name: str = Field(..., max_length=200)
    condition: TriggerCondition
    simulation_template: dict[str, Any] = Field(
        ...,
        description="SimulateRequest-compatible payload to run when trigger fires.",
    )
    webhook_url: str | None = Field(
        None,
        description="HTTPS endpoint to POST notification results to.",
    )
    execution_webhook_url: str | None = Field(
        None,
        description=(
            "When set and auto_execute=true, the full DecisionPlan is POSTed here as an "
            "actionable execution payload (same format as POST /v1/decisions/{id}/execute)."
        ),
    )
    auto_execute: bool = Field(
        default=False,
        description=(
            "If true, automatically dispatch the decision to execution_webhook_url "
            "after every successful trigger fire."
        ),
    )
    description: str | None = Field(None, max_length=500)


class TriggerSummary(BaseModel):
    trigger_id: str
    org_id: str
    name: str
    status: Literal["active", "paused"]
    condition: TriggerCondition
    description: str | None
    webhook_url: str | None
    execution_webhook_url: str | None = None
    auto_execute: bool = False
    created_at: datetime
    last_checked_at: datetime | None
    last_fired_at: datetime | None
    last_result_summary: str | None


class TriggerListResponse(BaseModel):
    triggers: list[TriggerSummary]
    count: int
    total: int
    page: int
    limit: int
    pages: int


class FireTriggerRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="Run simulation even if condition is not currently met.",
    )


class FireTriggerResponse(BaseModel):
    trigger_id: str
    condition_met: bool
    fired: bool
    simulation_run_id: str | None
    recommended_action: str | None
    expected_value: float | None
    confidence: float | None
    fired_at: datetime | None
    execution_status: str | None = None  # "delivered" | "failed" | None (not attempted)
    message: str


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _trigger_key(org_id: str, trigger_id: str) -> str:
    return f"{org_id}:{trigger_id}"


def _get_trigger(org_id: str, trigger_id: str) -> dict[str, Any] | None:
    return _TRIGGER_STORE.get(_trigger_key(org_id, trigger_id))


async def _evaluate_condition(
    condition: TriggerCondition,
    org_id: str,
    api_key_id: str,
) -> tuple[bool, float | None]:
    """
    Evaluate the trigger condition against the source's current data.
    Returns (condition_met, current_value).
    """
    from apps.api_server.routers.query import _run_query_internal  # lazy import

    try:
        current_val = await _run_query_internal(
            org_id=uuid.UUID(org_id),
            source_id=condition.source_id,
            metric_hint=condition.metric_hint,
            aggregation=condition.aggregation,
        )
    except Exception:
        # Source not accessible or query failed — don't fire
        return False, None

    if current_val is None:
        return False, None

    if condition.direction == "above":
        return current_val > condition.threshold, current_val
    elif condition.direction == "below":
        return current_val < condition.threshold, current_val
    else:  # "change"
        return True, current_val  # always fire for "change" direction


async def _run_simulation(
    template: dict[str, Any],
    org_id: str,
    api_key_id: str,
) -> dict[str, Any] | None:
    """Run the simulation template and return a summary dict including the full DecisionPlan."""
    from apps.api_server.schemas.response import build_decision_plan
    from apps.api_server.schemas.simulate import SimulateRequest
    from apps.api_server.services.simulation_service import run_simulation_fast

    try:
        req: Any = TypeAdapter(SimulateRequest).validate_python(template)
        envelope, _ = await run_simulation_fast(
            request=req,
            org_id=uuid.UUID(org_id),
            api_key_id=uuid.UUID(api_key_id),
        )
        decision_plan = build_decision_plan(envelope)
        return {
            "run_id": str(envelope.run_id),
            "recommended_action": envelope.recommended_action,
            "expected_value": envelope.metrics.expected_value,
            "confidence": envelope.confidence,
            "decision_plan": decision_plan.model_dump(mode="json"),
        }
    except Exception as exc:
        logger.warning("trigger_simulation_failed", error=str(exc))
        return None


async def _dispatch_webhook(
    url: str,
    payload: dict[str, Any],
    *,
    audit_context: EgressAuditContext | None = None,
) -> None:
    """Fire-and-forget webhook POST."""
    try:
        await async_http_request(
            method="POST",
            url=url,
            surface="trigger_webhook",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context,
            client_kwargs={"timeout": 10.0},
            json=payload,
        )
    except EgressPolicyDeniedError as exc:
        logger.warning("trigger_webhook_blocked", url=url, reason=exc.decision.reason)
    except Exception as exc:
        logger.warning("trigger_webhook_failed", url=url, error=str(exc))


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/v1/triggers",
    response_model=TriggerSummary,
    status_code=201,
    summary="Register a trigger",
)
async def register_trigger(
    payload: RegisterTriggerRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> TriggerSummary:
    trigger_id = str(uuid.uuid4())
    org_id = str(auth["org_id"])
    now = datetime.now(UTC)

    record: dict[str, Any] = {
        "trigger_id": trigger_id,
        "org_id": org_id,
        "name": payload.name,
        "status": "active",
        "condition": payload.condition.model_dump(),
        "simulation_template": payload.simulation_template,
        "webhook_url": payload.webhook_url,
        "execution_webhook_url": payload.execution_webhook_url,
        "auto_execute": payload.auto_execute,
        "description": payload.description,
        "created_at": now.isoformat(),
        "last_checked_at": None,
        "last_fired_at": None,
        "last_result_summary": None,
    }
    _TRIGGER_STORE[_trigger_key(org_id, trigger_id)] = record

    logger.info("trigger_registered", trigger_id=trigger_id, name=payload.name, org_id=org_id)
    return TriggerSummary(
        trigger_id=trigger_id,
        org_id=org_id,
        name=payload.name,
        status="active",
        condition=payload.condition,
        description=payload.description,
        webhook_url=payload.webhook_url,
        execution_webhook_url=payload.execution_webhook_url,
        auto_execute=payload.auto_execute,
        created_at=now,
        last_checked_at=None,
        last_fired_at=None,
        last_result_summary=None,
    )


@router.get(
    "/v1/triggers",
    response_model=TriggerListResponse,
    summary="List all triggers",
)
async def list_triggers(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    status: str = "all",
    page: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> TriggerListResponse:
    org_id = str(auth["org_id"])
    prefix = f"{org_id}:"
    records = [v for k, v in _TRIGGER_STORE.items() if k.startswith(prefix)]
    if status != "all":
        records = [r for r in records if r["status"] == status]

    summaries = [
        TriggerSummary(
            trigger_id=r["trigger_id"],
            org_id=r["org_id"],
            name=r["name"],
            status=r["status"],
            condition=TriggerCondition(**r["condition"]),
            description=r.get("description"),
            webhook_url=r.get("webhook_url"),
            execution_webhook_url=r.get("execution_webhook_url"),
            auto_execute=r.get("auto_execute", False),
            created_at=datetime.fromisoformat(r["created_at"]),
            last_checked_at=(
                datetime.fromisoformat(r["last_checked_at"]) if r.get("last_checked_at") else None
            ),
            last_fired_at=(
                datetime.fromisoformat(r["last_fired_at"]) if r.get("last_fired_at") else None
            ),
            last_result_summary=r.get("last_result_summary"),
        )
        for r in records
    ]
    paged = paginate_sequence(summaries, page=page, limit=limit)
    return TriggerListResponse(
        triggers=paged.items,
        count=len(paged.items),
        total=paged.total,
        page=paged.page,
        limit=paged.limit,
        pages=paged.pages,
    )


@router.post(
    "/v1/triggers/{trigger_id}/fire",
    response_model=FireTriggerResponse,
    summary="Fire a trigger",
    description=(
        "Evaluate the trigger condition and run the simulation template if met (or forced)."
    ),
)
async def fire_trigger(
    trigger_id: str,
    payload: FireTriggerRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> FireTriggerResponse:
    org_id = str(auth["org_id"])
    record = _get_trigger(org_id, trigger_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trigger not found")
    if record["status"] == "paused" and not payload.force:
        return FireTriggerResponse(
            trigger_id=trigger_id,
            condition_met=False,
            fired=False,
            simulation_run_id=None,
            recommended_action=None,
            expected_value=None,
            confidence=None,
            fired_at=None,
            message="Trigger is paused. Use force=true to override.",
        )

    now = datetime.now(UTC)
    record["last_checked_at"] = now.isoformat()

    # Evaluate condition
    condition = TriggerCondition(**record["condition"])
    condition_met, current_value = await _evaluate_condition(
        condition, org_id, str(auth.get("key_id", uuid.uuid4()))
    )

    should_fire = condition_met or payload.force
    sim_result: dict[str, Any] | None = None
    _auto_exec_allowed: bool = True  # updated below if auto_execute path is entered

    if should_fire:
        sim_result = await _run_simulation(
            record["simulation_template"], org_id, str(auth.get("key_id", uuid.uuid4()))
        )
        if sim_result:
            record["last_fired_at"] = now.isoformat()
            record["last_result_summary"] = (
                f"action={sim_result['recommended_action']} "
                f"ev={sim_result['expected_value']:.2f} "
                f"confidence={sim_result['confidence']:.2f}"
            )
            import asyncio

            egress_audit_context = audit_context_from_auth(
                auth,
                request_id=getattr(request.state, "request_id", None),
            )

            # ── Notification webhook — lightweight result summary ──────────
            if record.get("webhook_url"):
                notification_payload = {
                    "event": "trigger.fired",
                    "trigger_id": trigger_id,
                    "trigger_name": record["name"],
                    "condition_met": condition_met,
                    "current_value": current_value,
                    "run_id": sim_result["run_id"],
                    "recommended_action": sim_result["recommended_action"],
                    "expected_value": sim_result["expected_value"],
                    "confidence": sim_result["confidence"],
                }
                asyncio.create_task(
                    _dispatch_webhook(
                        record["webhook_url"],
                        notification_payload,
                        audit_context=egress_audit_context,
                    )
                )

            # ── Execution webhook — full DecisionPlan for automated action ─
            if record.get("auto_execute") and record.get("execution_webhook_url"):
                # Safety: check calibration policy before auto-executing
                _auto_exec_allowed = True
                _auto_exec_skip_reason: str | None = None
                try:
                    from apps.api_server.services.calibration_service import get_calibration
                    from apps.api_server.services.execution_policy_service import (
                        check_auto_execute_allowed,
                        get_policy,
                    )

                    _cal_stats = get_calibration(
                        org_id,
                        str(auth["workspace_id"]) if auth.get("workspace_id") else None,
                    )
                    _policy = get_policy(org_id)
                    _auto_exec_allowed, _auto_exec_skip_reason = check_auto_execute_allowed(
                        _policy, _cal_stats.is_reliable
                    )
                except Exception as exc:
                    logger.warning(
                        "trigger_policy_gate_check_failed",
                        trigger_id=trigger_id,
                        error=str(exc),
                    )

                if _auto_exec_allowed:
                    execution_payload = {
                        "event": "decision.execute",
                        "trigger_id": trigger_id,
                        "trigger_name": record["name"],
                        "fired_at": now.isoformat(),
                        "policy_snapshot_id": _policy.snapshot_id,
                        "decision_plan": sim_result.get("decision_plan"),
                    }
                    asyncio.create_task(
                        _dispatch_webhook(
                            record["execution_webhook_url"],
                            execution_payload,
                            audit_context=egress_audit_context,
                        )
                    )
                else:
                    logger.warning(
                        "auto_execute_skipped",
                        trigger_id=trigger_id,
                        reason=_auto_exec_skip_reason,
                    )

    logger.info(
        "trigger_fired",
        trigger_id=trigger_id,
        condition_met=condition_met,
        forced=payload.force,
        sim_run_id=sim_result.get("run_id") if sim_result else None,
    )

    # Determine execution status for response
    _exec_status: str | None = None
    if (
        should_fire
        and sim_result is not None
        and record.get("auto_execute")
        and record.get("execution_webhook_url")
    ):
        _exec_status = "dispatched" if _auto_exec_allowed else "skipped_uncalibrated"

    return FireTriggerResponse(
        trigger_id=trigger_id,
        condition_met=condition_met,
        fired=should_fire and sim_result is not None,
        simulation_run_id=sim_result.get("run_id") if sim_result else None,
        recommended_action=sim_result.get("recommended_action") if sim_result else None,
        expected_value=sim_result.get("expected_value") if sim_result else None,
        confidence=sim_result.get("confidence") if sim_result else None,
        fired_at=now if should_fire else None,
        execution_status=_exec_status,
        message=(
            f"Fired: {sim_result['recommended_action']}"
            if sim_result
            else "Condition not met."
            if not condition_met
            else "Simulation failed."
        ),
    )


@router.patch(
    "/v1/triggers/{trigger_id}/pause",
    summary="Pause or resume a trigger",
)
async def pause_trigger(
    trigger_id: str,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    paused: bool = True,
) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    record = _get_trigger(org_id, trigger_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trigger not found")
    record["status"] = "paused" if paused else "active"
    return {"trigger_id": trigger_id, "status": record["status"]}


@router.delete(
    "/v1/triggers/{trigger_id}",
    status_code=204,
    response_model=None,
    summary="Delete a trigger (idempotent)",
)
async def delete_trigger(
    trigger_id: str,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> None:
    org_id = str(auth["org_id"])
    key = _trigger_key(org_id, trigger_id)
    if key not in _TRIGGER_STORE:
        # Idempotent delete: the trigger is already gone (or never existed) — the
        # desired end state holds, so this is a success, not a 404.
        return JSONResponse(
            {"trigger_id": trigger_id, "deleted": True, "already_absent": True}
        )
    del _TRIGGER_STORE[key]
