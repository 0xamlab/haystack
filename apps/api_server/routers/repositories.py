from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.middleware.rbac import forbid_service_key
from apps.api_server.middleware.tenant_key_binding import bind_tenant_keys
from apps.api_server.schemas.repositories import (
    RepositoryApplyRequest,
    RepositoryApplyResponse,
    RepositoryDecisionPlanCreateRequest,
    RepositoryDecisionPlanResponse,
    RepositoryGraphQueryRequest,
    RepositoryGraphQueryResponse,
    RepositoryIntelligenceCapabilitiesResponse,
    RepositoryPipelineRequest,
    RepositoryPipelineResponse,
    RepositorySimulatePatchRequest,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositorySnapshotResponse,
    RepositoryTriageRequest,
    RepositoryTriageResponse,
)
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_visibility import get_visible_connector
from apps.api_server.services.repository_intelligence import (
    RepositoryIntelligenceError,
    apply_repository_decision,
    create_repository_decision_plan,
    get_repository_intelligence_capabilities,
    create_repository_snapshot,
    get_repository_snapshot,
    query_repository_graph,
    simulate_repository_decision,
    simulate_repository_patch as run_repository_patch_simulation,
    triage_repository,
)
from apps.api_server.services.repository_intelligence_pipeline import (
    run_repository_pipeline,
)
from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.job import JobKind
from apps.api_server.services.job_service import create_job
from apps.api_server.services.workspace_scope import workspace_id_for_write

logger = structlog.get_logger(__name__)

# B10 PR11: bind the authenticated org's per-tenant keys for every (sync, in-request) handler in
# this router; async runs set the override in the worker from job.org_id instead.
router = APIRouter(tags=["Repository Intelligence"], dependencies=[Depends(bind_tenant_keys)])


def _repository_http_exception(exc: RepositoryIntelligenceError, request: Request) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


async def _execute_repository_job_in_process(job_id: UUID) -> None:
    """Fire-and-forget fallback for deployments without a worker. Runs on a FRESH
    session/task so the request still returns 202 immediately (no event-loop block)."""
    from apps.api_server.services.repository_job_service import execute_repository_job

    async with AsyncSessionLocal() as db:
        try:
            await execute_repository_job(job_id=job_id, db=db)
        except Exception as exc:  # noqa: BLE001 — fallback runner; status is persisted on the job
            logger.error(
                "repository_job_in_process_failed", job_id=str(job_id), error=str(exc), exc_info=True
            )


async def _submit_repository_job(
    *,
    job_kind: JobKind,
    repository_id: UUID,
    request_body: Any,
    request: Request,
    db: AsyncSessionDep,
    auth: AuthContext,
) -> JSONResponse:
    """Wave B1: take a long repository run off the request path — create a Job, enqueue
    it on the worker (or fire-and-forget in-process where no worker exists), and return
    202 + a poll handle. The connector visibility was already enforced by the caller."""
    job = await create_job(
        None,
        auth["org_id"],
        db,
        queue_name="repository",
        workspace_id=workspace_id_for_write(auth),
        job_kind=job_kind,
        request_payload={
            "repository_id": str(repository_id),
            "request": request_body.model_dump(mode="json"),
        },
    )
    await db.commit()

    enqueued = False
    try:
        from apps.worker.tasks.repository_task import enqueue_repository_job

        enqueued = enqueue_repository_job(str(job.id))
    except Exception as exc:  # noqa: BLE001 — degrade to in-process on broker issues
        logger.warning("repository_job_enqueue_failed", job_id=str(job.id), error=str(exc))
    if not enqueued:
        asyncio.create_task(_execute_repository_job_in_process(job.id))

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        status_code=202,
        content={
            "job_id": str(job.id),
            "status": job.status.value,
            "job_kind": job_kind.value,
            "poll_url": f"{base_url}/v1/jobs/{job.id}",
            "message": "Repository job queued. Poll the poll_url for status and result.",
        },
    )


@router.get(
    "/v1/repositories/capabilities",
    response_model=RepositoryIntelligenceCapabilitiesResponse,
    summary="List repository intelligence language support and progress",
)
async def get_capabilities(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryIntelligenceCapabilitiesResponse:
    del request, auth
    return get_repository_intelligence_capabilities()


@router.post(
    "/v1/repositories/{repository_id}/snapshots",
    response_model=RepositorySnapshotResponse,
    summary="Create or reuse an immutable repository snapshot",
)
async def create_snapshot(
    repository_id: UUID,
    payload: RepositorySnapshotCreateRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositorySnapshotResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return create_repository_snapshot(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.get(
    "/v1/repositories/{repository_id}/snapshots/{snapshot_id}",
    response_model=RepositorySnapshotResponse,
    summary="Get one immutable repository snapshot",
)
async def get_snapshot(
    repository_id: UUID,
    snapshot_id: str,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositorySnapshotResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return get_repository_snapshot(connector=connector, snapshot_id=snapshot_id)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/triage",
    response_model=RepositoryTriageResponse,
    summary="Triage a repository snapshot into a bounded workspace evidence bundle",
)
async def triage_repository_snapshot(
    repository_id: UUID,
    payload: RepositoryTriageRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryTriageResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return triage_repository(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/graph-query",
    response_model=RepositoryGraphQueryResponse,
    summary="Query repository dependency and blast-radius graph from one persisted snapshot",
)
async def query_repository_snapshot_graph(
    repository_id: UUID,
    payload: RepositoryGraphQueryRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryGraphQueryResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return query_repository_graph(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/decision-plans",
    response_model=RepositoryDecisionPlanResponse,
    summary="Create one stored immutable repository decision plan revision",
)
async def create_decision_plan(
    repository_id: UUID,
    payload: RepositoryDecisionPlanCreateRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    async_execution: bool = False,
) -> RepositoryDecisionPlanResponse | JSONResponse:
    # Visibility is enforced on the request (with the caller's auth) before queuing.
    connector = await get_visible_connector(db, repository_id, auth)
    if async_execution:
        return await _submit_repository_job(
            job_kind=JobKind.REPOSITORY_DECISION_PLAN,
            repository_id=repository_id,
            request_body=payload,
            request=request,
            db=db,
            auth=auth,
        )
    try:
        return await create_repository_decision_plan(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/simulate",
    response_model=DecisionEnvelope,
    summary="Simulate repository patch risk and populate the decision envelope gate",
)
async def simulate_repository_patch(
    repository_id: UUID,
    payload: RepositorySimulationRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> DecisionEnvelope:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return await simulate_repository_decision(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/simulate-patch",
    response_model=DecisionEnvelope,
    summary="Simulate an in-flight working-tree patch (no stored decision plan)",
)
async def simulate_repository_working_tree_patch(
    repository_id: UUID,
    payload: RepositorySimulatePatchRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> DecisionEnvelope:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return await run_repository_patch_simulation(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/pipeline",
    response_model=RepositoryPipelineResponse,
    summary="Run snapshot->triage->plan->simulate in one call (AR-OPT-9, flag-gated)",
)
async def run_repository_intelligence_pipeline(
    repository_id: UUID,
    payload: RepositoryPipelineRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    async_execution: bool = False,
) -> RepositoryPipelineResponse | JSONResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    if async_execution:
        return await _submit_repository_job(
            job_kind=JobKind.REPOSITORY_PIPELINE,
            repository_id=repository_id,
            request_body=payload,
            request=request,
            db=db,
            auth=auth,
        )
    try:
        return await run_repository_pipeline(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/apply",
    response_model=RepositoryApplyResponse,
    summary="Apply a simulated repository decision through patch, local branch, or remote PR",
)
async def apply_repository_patch(
    repository_id: UUID,
    payload: RepositoryApplyRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryApplyResponse:
    # /apply performs an EXTERNAL write (patch / local branch / remote PR push). It authorizes only
    # on connector visibility, so the service-key repo-read allowance must be explicitly excluded
    # here — the agent's callback set (triage/graph-query/simulate-patch) never includes apply.
    forbid_service_key(auth, "repository apply (writes a patch / pushes a branch / opens a PR)")
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return await apply_repository_decision(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
