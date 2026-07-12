from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org, get_redis, require_verified_email
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
    SecurityAnalysisClosureRequest,
    SecurityAnalysisClosureResponse,
    SecurityAnalysisRequest,
    SecurityAnalysisResponse,
)
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_visibility import get_visible_connector
from apps.api_server.services.quota_service import (
    check_quota_redis,
    check_rate_limit,
    incr_quota_counter,
)
from apps.api_server.services.storage_accounting_service import gate_storage_cap
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
    analyze_repository_security,
    analyze_repository_security_closure,
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
router = APIRouter(
    tags=["Repository Intelligence"],
    dependencies=[Depends(require_verified_email), Depends(bind_tenant_keys)],
)


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


def _is_offline_auth(auth: AuthContext) -> bool:
    """True for a device/offline-license token. Such requests do NO central DB/Redis metering or
    quota — usage is metered PER DEVICE locally and reconciled out-of-band — so the fix hot path
    stays free of Postgres/Redis (works on a device gone dark)."""
    return auth.get("email") == "offline_license"


async def _repo_preflight(auth: AuthContext, request: Request, redis_client: object) -> None:
    """Apply any explicit endpoint or non-Algenta governance controls before compute.

    Algenta plans are unmetered, so both checks return without touching Redis for those plans.
    """
    if _is_offline_auth(auth):
        return  # per-device: no central rate-limit/quota DB on the device hot path
    await check_rate_limit(auth["org_id"], auth["plan"], redis_client, request_state=request.state)
    await check_quota_redis(auth["org_id"], auth["plan"], redis_client)


async def _meter_repository(
    *,
    tool_name: str,
    auth: AuthContext,
    db: AsyncSessionDep,
    redis_client: object,
    usage_key: str | None = None,
) -> None:
    """Record one local repository activity row after a successful compute call.

    Mirrors the canonical ``_persist_helpers`` sequence: insert inside a SAVEPOINT so a
    ``usage_key`` duplicate (retry / cross-replica race) rolls back ONLY this insert, and the
    quota counter is incremented only for quota-governed non-Algenta plans. The row commits with
    the request session on success and rolls back if the request later fails.
    Call AFTER the compute succeeds.
    """
    if _is_offline_auth(auth):
        return  # per-device metering: usage recorded locally on the device, never in Postgres
    from apps.api_server.services.quota_service import _metering_disabled

    if _metering_disabled():
        return  # metering off for everyone — no repository usage row / quota counter
    from sqlalchemy.exc import IntegrityError

    period = datetime.now(UTC).strftime("%Y-%m")
    inserted = False
    try:
        async with db.begin_nested():
            db.add(
                UsageRecord(
                    org_id=auth["org_id"],
                    workspace_id=workspace_id_for_write(auth),
                    api_key_id=auth.get("key_id"),
                    billing_period=period,
                    endpoint=UsageEndpoint.REPOSITORY,
                    billing_units=1,
                    product="codna",
                    tool_name=tool_name,
                    usage_key=usage_key,
                )
            )
            await db.flush()
        inserted = True
    except IntegrityError:
        logger.info("repository_usage_already_billed", tool=tool_name, org_id=str(auth["org_id"]))
    from apps.api_server.services.plan_limits import is_unmetered_execution_plan

    if inserted and redis_client is not None and not is_unmetered_execution_plan(auth["plan"]):
        try:
            await incr_quota_counter(auth["org_id"], period, redis_client)
        except Exception as exc:  # noqa: BLE001 — counter is best-effort; never fail the call
            logger.warning(
                "repository_quota_counter_incr_failed",
                org_id=str(auth["org_id"]),
                error=str(exc),
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
    redis_client: object = Depends(get_redis),
) -> RepositorySnapshotResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    try:
        result = create_repository_snapshot(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="create_repository_snapshot", auth=auth, db=db, redis_client=redis_client
    )
    return result


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
    redis_client: object = Depends(get_redis),
) -> RepositoryTriageResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    try:
        result = triage_repository(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="triage_repository", auth=auth, db=db, redis_client=redis_client
    )
    return result


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
    redis_client: object = Depends(get_redis),
) -> RepositoryGraphQueryResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    # graph-query writes a durable lookup artifact (graph_query_lookup) under the tenant prefix, so
    # it counts toward the storage sum — gate it too, keeping the agent-callback set uniformly gated.
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    try:
        result = query_repository_graph(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="query_repository_graph", auth=auth, db=db, redis_client=redis_client
    )
    return result


@router.post(
    "/v1/repositories/{repository_id}/security-analyses",
    response_model=SecurityAnalysisResponse,
    summary="Prove reachability for a batch of scanner findings (snapshot-cached)",
)
async def analyze_repository_security_findings(
    repository_id: UUID,
    payload: SecurityAnalysisRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    async_execution: bool = False,
) -> SecurityAnalysisResponse | JSONResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # writes a durable analysis manifest
    if async_execution:
        # large SARIF runs can be slow — take the proof off the request path (202 + poll handle)
        return await _submit_repository_job(
            job_kind=JobKind.REPOSITORY_SECURITY_ANALYSES,
            repository_id=repository_id,
            request_body=payload,
            request=request,
            db=db,
            auth=auth,
        )
    try:
        return analyze_repository_security(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/security-analyses/closure",
    response_model=SecurityAnalysisClosureResponse,
    summary="Re-prove that a patch closes the original finding obligation",
)
async def close_repository_security_finding(
    repository_id: UUID,
    payload: SecurityAnalysisClosureRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> SecurityAnalysisClosureResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return analyze_repository_security_closure(connector=connector, request=payload)
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
    redis_client: object = Depends(get_redis),
) -> RepositoryDecisionPlanResponse | JSONResponse:
    # Visibility is enforced on the request (with the caller's auth) before queuing.
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    if async_execution:
        # Meter on accept: the UsageRecord is added to the session and committed together with the
        # job by _submit_repository_job's commit (the worker does not re-meter the job today).
        await _meter_repository(
            tool_name="create_repository_decision_plan",
            auth=auth,
            db=db,
            redis_client=redis_client,
        )
        return await _submit_repository_job(
            job_kind=JobKind.REPOSITORY_DECISION_PLAN,
            repository_id=repository_id,
            request_body=payload,
            request=request,
            db=db,
            auth=auth,
        )
    try:
        result = await create_repository_decision_plan(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="create_repository_decision_plan", auth=auth, db=db, redis_client=redis_client
    )
    return result


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
    redis_client: object = Depends(get_redis),
) -> DecisionEnvelope:
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    try:
        result = await simulate_repository_decision(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="simulate_repository", auth=auth, db=db, redis_client=redis_client
    )
    return result


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
    redis_client: object = Depends(get_redis),
) -> DecisionEnvelope:
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    try:
        result = await run_repository_patch_simulation(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="simulate_repository_patch", auth=auth, db=db, redis_client=redis_client
    )
    return result


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
    redis_client: object = Depends(get_redis),
) -> RepositoryPipelineResponse | JSONResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    await gate_storage_cap(auth["org_id"], auth["plan"])  # free-tier storage cap (off by default)
    await _repo_preflight(auth, request, redis_client)
    if async_execution:
        await _meter_repository(
            tool_name="run_repository_pipeline", auth=auth, db=db, redis_client=redis_client
        )
        return await _submit_repository_job(
            job_kind=JobKind.REPOSITORY_PIPELINE,
            repository_id=repository_id,
            request_body=payload,
            request=request,
            db=db,
            auth=auth,
        )
    try:
        result = await run_repository_pipeline(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="run_repository_pipeline", auth=auth, db=db, redis_client=redis_client
    )
    return result


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
    redis_client: object = Depends(get_redis),
) -> RepositoryApplyResponse:
    # /apply performs an EXTERNAL write (patch / local branch / remote PR push). It authorizes only
    # on connector visibility, so the service-key repo-read allowance must be explicitly excluded
    # here — the agent's callback set (triage/graph-query/simulate-patch) never includes apply.
    forbid_service_key(auth, "repository apply (writes a patch / pushes a branch / opens a PR)")
    connector = await get_visible_connector(db, repository_id, auth)
    await _repo_preflight(auth, request, redis_client)
    try:
        result = await apply_repository_decision(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
    await _meter_repository(
        tool_name="apply_repository", auth=auth, db=db, redis_client=redis_client
    )
    return result
