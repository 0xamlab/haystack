"""Decision Workflow API — /v1/decision-cases, /v1/analysis-runs, /v1/decision-plans.

The HTTP surface over the DecisionService (Build order 4). The workflow:

  POST /v1/decision-cases                       — frame a decision (create; immutable revision 1)
  PUT  /v1/decision-cases/{id}                  — re-frame (material change → new revision,
                                                  prior approvals invalidated)
  GET  /v1/decision-cases/{id}                  — case status + current revision
  POST /v1/decision-cases/{id}/analysis-runs    — 202: run the governed analysis (poll for result)
  POST /v1/decision-cases/{id}/refresh          — 202: re-run the current revision (manual refresh)
  GET  /v1/analysis-runs/{run_id}               — poll run status
  GET  /v1/analysis-runs/{run_id}/result        — the host-independent result object
  GET  /v1/analysis-runs/{run_id}/evidence      — evidence + provenance ("what was accessed")
  POST /v1/analysis-runs/{run_id}/action-plans  — propose a safe execution plan (plan_hash + nonce)
  POST /v1/decision-plans/{plan_id}/approve     — separately-authenticated approval
                                                  (exact plan_hash + single-use nonce)
  POST /v1/decision-plans/{plan_id}/execute     — execute an APPROVED plan (approve != execute)
  POST /v1/decision-cases/{id}/outcomes         — record what actually happened

Approval is deliberately NOT exposed as an MCP/LLM tool — it is an explicit, credentialed
HTTP operation. The analysis contract is async (202 + poll) so slower packs can move to a
worker without changing clients; the current pack is deterministic and completes inline.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org, require_verified_email
from apps.api_server.schemas.decision_workflow import (
    AnalysisResultResponse,
    AnalysisRunAccepted,
    AnalysisRunStatusResponse,
    ApprovalResponse,
    ApproveRequest,
    CreateDecisionCaseRequest,
    DecisionCaseResponse,
    EvidenceResponse,
    ExecutionPlanResponse,
    OutcomeResponse,
    RecordOutcomeRequest,
    StartAnalysisRequest,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.decision_service import DecisionService, DecisionServiceError
from apps.api_server.services.decision_service.service import RequestScope
from apps.api_server.services.decision_service.sql_repository import SqlDecisionRepository

logger = structlog.get_logger(__name__)
router = APIRouter(
    tags=["Decision Workflow"], dependencies=[Depends(require_verified_email)]
)

# DecisionServiceError code → HTTP status. Unknown codes fall back to 400.
_STATUS_BY_CODE = {
    "case_not_found": 404,
    "revision_not_found": 404,
    "run_not_found": 404,
    "plan_not_found": 404,
    "unknown_pack": 400,
    "invalid_framing": 422,
    "invalid_retention_mode": 422,
    "run_not_completed": 409,
    "no_feasible_solution": 409,
    "plan_not_approvable": 409,
    "plan_not_approved": 409,
    "stale_plan": 409,
    "plan_hash_mismatch": 403,
    "invalid_nonce": 403,
    "approval_expired": 403,
    "insufficient_role": 403,
    "idempotency_key_conflict": 409,
}


def _http(exc: DecisionServiceError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


def get_decision_service(db: AsyncSession = Depends(get_db)) -> DecisionService:
    """Request-scoped DecisionService over the SQL repository. Overridable in tests."""
    return DecisionService(SqlDecisionRepository(db))


# Approving or executing a decision plan is a privileged act: admin-or-owner only. Service
# keys are pinned to 'viewer' by the auth layer precisely so they can never reach this.
_APPROVAL_MIN_ROLE = "admin"


def _scope_from_auth(auth: AuthContext, request: Request | None = None) -> RequestScope:
    user_id = auth.get("user_id")
    # request is optional so existing callers keep working; when present the receipt gains the
    # correlation ids, which is what makes several receipts from one agent turn reassemblable.
    request_id = getattr(request.state, "request_id", None) if request is not None else None
    trace_id = getattr(request.state, "trace_id", None) if request is not None else None
    idem = request.headers.get("Idempotency-Key", "").strip() if request is not None else ""
    return RequestScope(
        org_id=auth["org_id"],
        workspace_id=auth.get("workspace_id"),
        principal=str(user_id) if user_id else f"key:{auth.get('key_id')}",
        role=auth.get("role"),
        request_id=request_id,
        trace_id=trace_id,
        idempotency_key=idem or None,
    )


def _case_response(case, rev) -> DecisionCaseResponse:  # type: ignore[no-untyped-def]
    return DecisionCaseResponse(
        case_id=case.id,
        pack_id=case.pack_id,
        title=case.title,
        owner=case.owner,
        status=case.status,
        current_revision_id=case.current_revision_id,
        current_revision_number=case.current_revision_number,
        inputs_hash=getattr(rev, "inputs_hash", None),
    )


def _run_accepted(request: Request, run) -> AnalysisRunAccepted:  # type: ignore[no-untyped-def]
    base = str(request.base_url).rstrip("/")
    return AnalysisRunAccepted(
        run_id=run.id,
        case_id=run.case_id,
        status=run.status,
        poll_url=f"{base}/v1/analysis-runs/{run.id}",
        result_url=f"{base}/v1/analysis-runs/{run.id}/result",
    )


@router.post(
    "/v1/decision-cases",
    response_model=DecisionCaseResponse,
    status_code=201,
    summary="Frame a decision (create a case + immutable revision 1)",
)
async def create_decision_case(
    payload: CreateDecisionCaseRequest,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> DecisionCaseResponse:
    scope = _scope_from_auth(auth)
    try:
        case, rev = await svc.create_or_update_decision(
            scope,
            pack_id=payload.pack_id,
            title=payload.title,
            pack_input=payload.pack_input,
            owner=payload.owner,
            objective=payload.objective,
            horizon_days=payload.horizon_days,
        )
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return _case_response(case, rev)


@router.put(
    "/v1/decision-cases/{case_id}",
    response_model=DecisionCaseResponse,
    summary="Re-frame a decision (material change → new immutable revision)",
)
async def update_decision_case(
    case_id: uuid.UUID,
    payload: CreateDecisionCaseRequest,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> DecisionCaseResponse:
    scope = _scope_from_auth(auth)
    try:
        case, rev = await svc.create_or_update_decision(
            scope,
            pack_id=payload.pack_id,
            title=payload.title,
            pack_input=payload.pack_input,
            case_id=case_id,
            owner=payload.owner,
            objective=payload.objective,
            horizon_days=payload.horizon_days,
        )
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return _case_response(case, rev)


@router.get(
    "/v1/decision-cases/{case_id}",
    response_model=DecisionCaseResponse,
    summary="Get a decision case",
)
async def get_decision_case(
    case_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
) -> DecisionCaseResponse:
    scope = _scope_from_auth(auth)
    case = await svc._repo.get_case(case_id, scope.org_id, scope.workspace_id)
    if case is None:
        raise _http(DecisionServiceError("case_not_found", "Decision case not found"))
    rev = (
        await svc._repo.get_revision(case.current_revision_id, scope.org_id, scope.workspace_id)
        if case.current_revision_id
        else None
    )
    return _case_response(case, rev)


@router.post(
    "/v1/decision-cases/{case_id}/analysis-runs",
    response_model=AnalysisRunAccepted,
    status_code=202,
    summary="Run the governed analysis (async: poll for the result)",
)
async def start_analysis_run(
    case_id: uuid.UUID,
    request: Request,
    payload: StartAnalysisRequest | None = None,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> AnalysisRunAccepted:
    scope = _scope_from_auth(auth)
    retention = payload.retention_mode if payload else "exploratory"
    try:
        run = await svc.run_decision_analysis(scope, case_id=case_id, retention_mode=retention)
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return _run_accepted(request, run)


@router.post(
    "/v1/decision-cases/{case_id}/refresh",
    response_model=AnalysisRunAccepted,
    status_code=202,
    summary="Manually refresh: re-run the current revision with fresh evidence",
)
async def refresh_decision(
    case_id: uuid.UUID,
    request: Request,
    payload: StartAnalysisRequest | None = None,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> AnalysisRunAccepted:
    scope = _scope_from_auth(auth)
    retention = payload.retention_mode if payload else "exploratory"
    try:
        run = await svc.refresh_decision(scope, case_id=case_id, retention_mode=retention)
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return _run_accepted(request, run)


@router.get(
    "/v1/analysis-runs/{run_id}",
    response_model=AnalysisRunStatusResponse,
    summary="Poll an analysis run",
)
async def get_analysis_run(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
) -> AnalysisRunStatusResponse:
    scope = _scope_from_auth(auth)
    try:
        run = await svc.get_run(scope, run_id)
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    return AnalysisRunStatusResponse(
        run_id=run.id,
        case_id=run.case_id,
        revision_id=run.revision_id,
        status=run.status,
        model_version=run.model_version_ref,
        reproducibility_id=run.reproducibility_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


@router.get(
    "/v1/analysis-runs/{run_id}/result",
    response_model=AnalysisResultResponse,
    summary="Fetch the analysis result (host-independent object)",
)
async def get_analysis_result(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
) -> AnalysisResultResponse:
    scope = _scope_from_auth(auth)
    try:
        payload = await svc.get_result(scope, run_id)
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    return AnalysisResultResponse(**payload)


@router.get(
    "/v1/analysis-runs/{run_id}/evidence",
    response_model=EvidenceResponse,
    summary="Inspect evidence + provenance (what was accessed, under which retention mode)",
)
async def inspect_evidence(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
) -> EvidenceResponse:
    scope = _scope_from_auth(auth)
    try:
        payload = await svc.inspect_evidence(scope, run_id)
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    return EvidenceResponse(**payload)


@router.post(
    "/v1/analysis-runs/{run_id}/action-plans",
    response_model=ExecutionPlanResponse,
    status_code=201,
    summary="Propose a safe execution plan (returns the plan_hash + single-use approval nonce)",
)
async def propose_action_plan(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> ExecutionPlanResponse:
    scope = _scope_from_auth(auth)
    try:
        plan = await svc.propose_action_plan(scope, run_id)
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return ExecutionPlanResponse(
        plan_id=plan.id,
        case_id=plan.case_id,
        run_id=plan.run_id,
        lifecycle_state=plan.lifecycle_state,
        plan_hash=plan.plan_hash,
        nonce=plan.nonce,
        actions=plan.actions,
    )


@router.post(
    "/v1/decision-plans/{plan_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a proposed plan (separately authenticated; plan_hash + single-use nonce)",
    description=(
        "Approval is an explicit, credentialed operation bound to the exact plan hash and a "
        "single-use nonce. It is intentionally not exposed as an MCP/LLM tool. Approving does "
        "NOT execute the plan (approve != execute)."
    ),
)
async def approve_plan(
    plan_id: uuid.UUID,
    payload: ApproveRequest,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    scope = _scope_from_auth(auth)
    try:
        approval = await svc.approve(
            scope,
            plan_id=plan_id,
            plan_hash=payload.plan_hash,
            nonce=payload.nonce,
            idempotency_key=payload.idempotency_key,
            required_role=_APPROVAL_MIN_ROLE,
        )
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    logger.info(
        "decision_plan_approved",
        plan_id=str(plan_id),
        case_id=str(approval.case_id),
        org_id=str(scope.org_id),
    )
    return ApprovalResponse(
        approval_id=approval.id,
        case_id=approval.case_id,
        plan_id=approval.plan_id,
        status=approval.status,
        approver_principal=approval.approver_principal,
        decided_at=approval.decided_at,
    )


@router.post(
    "/v1/decision-plans/{plan_id}/execute",
    response_model=ExecutionPlanResponse,
    summary="Execute an APPROVED plan (safe MVP actions only)",
)
async def execute_plan(
    plan_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> ExecutionPlanResponse:
    scope = _scope_from_auth(auth, request)
    try:
        plan = await svc.execute_approved_plan(
            scope, plan_id=plan_id, required_role=_APPROVAL_MIN_ROLE
        )
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return ExecutionPlanResponse(
        plan_id=plan.id,
        case_id=plan.case_id,
        run_id=plan.run_id,
        lifecycle_state=plan.lifecycle_state,
        plan_hash=plan.plan_hash,
        nonce=None,  # never re-expose the nonce after propose time
        actions=plan.actions,
        receipt=plan.receipt,
    )


@router.post(
    "/v1/decision-cases/{case_id}/outcomes",
    response_model=OutcomeResponse,
    status_code=201,
    summary="Record what actually happened (closes the learning loop)",
)
async def record_outcome(
    case_id: uuid.UUID,
    payload: RecordOutcomeRequest,
    auth: AuthContext = Depends(get_current_org),
    svc: DecisionService = Depends(get_decision_service),
    db: AsyncSession = Depends(get_db),
) -> OutcomeResponse:
    scope = _scope_from_auth(auth)
    try:
        outcome = await svc.record_outcome(
            scope,
            case_id=case_id,
            run_id=payload.run_id,
            actual_metrics=payload.actual_metrics,
            notes=payload.notes,
        )
    except DecisionServiceError as exc:
        raise _http(exc) from exc
    await db.commit()
    return OutcomeResponse(
        outcome_id=outcome.id,
        case_id=outcome.case_id,
        run_id=outcome.run_id,
        actual_metrics=outcome.actual_metrics,
        delta=outcome.delta,
        recorded_at=outcome.recorded_at,
    )
