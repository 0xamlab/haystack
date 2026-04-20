"""
Async job endpoints:
  POST   /v1/jobs                    — submit async simulation job
  GET    /v1/jobs/{job_id}           — poll job status
  GET    /v1/jobs/{job_id}/result    — fetch completed job result
  POST   /v1/jobs/{job_id}/cancel    — cancel a queued/running job
  POST   /v1/webhooks/test           — test webhook delivery
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import AsyncSessionLocal, get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.job import Job, JobStatus
from apps.api_server.models.simulation_run import (
    ExecutionType,
    RunStatus,
    SimulationMode,
    SimulationRun,
)
from apps.api_server.schemas.simulate import (
    SimulateRequest,
    SimulateRequestAuto,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.job_service import (
    cancel_job,
    create_job,
    execute_job,
    get_job,
    get_job_result,
)
from apps.api_server.services.simulation_service import (
    _build_auto_mojo_payload,
    _build_expert_mojo_payload,
)
from apps.api_server.services.webhook_service import (
    build_webhook_payload,
    deliver_webhook,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Async Jobs"])


class SubmitJobRequest(BaseModel):
    """Request to submit an async simulation job."""
    model_config = ConfigDict(strict=False)

    request: SimulateRequest
    callback_url: str | None = Field(
        default=None,
        description="URL to POST when the job completes. Must be HTTPS in production.",
    )


class JobStatusResponse(BaseModel):
    """Job status returned by poll endpoint."""
    job_id: uuid.UUID
    run_id: uuid.UUID
    org_id: uuid.UUID
    status: str
    queue_name: str
    retry_count: int
    callback_url: str | None
    callback_status: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    ttl_expires_at: datetime | None
    poll_url: str


class SubmitJobResponse(BaseModel):
    """Returned immediately on job submission."""
    job_id: uuid.UUID
    run_id: uuid.UUID
    status: str
    poll_url: str
    message: str = "Job queued. Poll the poll_url for status updates."


class WebhookTestRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    callback_url: str = Field(..., description="URL to send test webhook to")


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int
    message: str


def _job_to_response(job: Job, base_url: str = "") -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        run_id=job.run_id,
        org_id=job.org_id,
        status=job.status.value,
        queue_name=job.queue_name,
        retry_count=job.retry_count,
        callback_url=job.callback_url,
        callback_status=job.callback_status.value,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        ttl_expires_at=job.ttl_expires_at,
        poll_url=f"{base_url}/v1/jobs/{job.id}",
    )


@router.get(
    "/v1/jobs/list",
    summary="List async jobs for this org",
)
async def list_jobs(
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    status: str | None = None,
) -> dict:
    """Paginated list of all jobs for the authenticated org."""
    from sqlalchemy import desc, func, select

    base_q = select(Job).where(Job.org_id == auth["org_id"])
    if status:
        try:
            status_val = JobStatus(status)
            base_q = base_q.where(Job.status == status_val)
        except ValueError:
            pass
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * limit
    items = (
        await db.execute(
            base_q.order_by(desc(Job.created_at)).offset(offset).limit(limit)
        )
    ).scalars().all()
    pages = max(1, (total + limit - 1) // limit)
    return {
        "jobs": [_job_to_response(j).model_dump() for j in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.post(
    "/v1/jobs",
    response_model=SubmitJobResponse,
    status_code=202,
    summary="Submit an async simulation job",
    description=(
        "Submit a large simulation to run asynchronously. "
        "Returns a job_id immediately. Poll /v1/jobs/{job_id} for status. "
        "Provide a callback_url to receive a webhook when complete."
    ),
)
async def submit_job(
    request: Request,
    payload: SubmitJobRequest,
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> SubmitJobResponse:
    import hashlib

    sim_request = payload.request

    # Build Mojo payload
    if isinstance(sim_request, SimulateRequestAuto):
        mojo_payload = _build_auto_mojo_payload(sim_request)
        mode = SimulationMode.AUTO
    else:
        mojo_payload = _build_expert_mojo_payload(sim_request)
        mode = SimulationMode.EXPERT

    request_hash = hashlib.sha256(json.dumps(mojo_payload, sort_keys=True).encode()).hexdigest()

    # Create SimulationRun in QUEUED state
    run = SimulationRun(
        org_id=auth["org_id"],
        api_key_id=auth["key_id"],
        mode=mode,
        request_hash=request_hash,
        status=RunStatus.QUEUED,
        execution_type=ExecutionType.ASYNC,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.flush()

    # Create Job
    job = await create_job(
        run_id=run.id,
        org_id=auth["org_id"],
        db=db,
        callback_url=payload.callback_url,
    )

    request_payload = sim_request.model_dump(mode="json")
    await db.commit()
    enqueued = False
    try:
        from apps.worker.tasks.simulation_task import enqueue_simulation_job
        enqueued = enqueue_simulation_job(str(job.id), request_payload)
    except Exception as exc:
        logger.warning("job_enqueue_failed", error=str(exc), job_id=str(job.id))

    if not enqueued:
        logger.info("job_execute_in_process", job_id=str(job.id), run_id=str(run.id))
        asyncio.create_task(_execute_job_in_process(job.id, request_payload))

    base_url = str(request.base_url).rstrip("/")
    poll_url = f"{base_url}/v1/jobs/{job.id}"

    logger.info("job_submitted", job_id=str(job.id), run_id=str(run.id), org_id=str(auth["org_id"]))

    return SubmitJobResponse(
        job_id=job.id,
        run_id=run.id,
        status=job.status.value,
        poll_url=poll_url,
    )


@router.get(
    "/v1/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll job status",
)
async def get_job_status(
    job_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    job = await get_job(job_id, auth["org_id"], db)
    base_url = str(request.base_url).rstrip("/")
    return _job_to_response(job, base_url)


async def _execute_job_in_process(job_id: uuid.UUID, request_payload: dict[str, object]) -> None:
    """Fallback async job runner for local/self-hosted deployments without a worker."""
    async with AsyncSessionLocal() as db:
        try:
            await execute_job(job_id=job_id, request_payload=request_payload, db=db)
        except Exception as exc:
            logger.error("job_in_process_failed", job_id=str(job_id), error=str(exc), exc_info=True)


@router.get(
    "/v1/jobs/{job_id}/result",
    summary="Fetch job result",
    description="Returns the full result if completed, or 202 with status if still processing.",
)
async def get_job_result_endpoint(
    job_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await get_job(job_id, auth["org_id"], db)

    if job.status == JobStatus.COMPLETED:
        result = await get_job_result(job_id, auth["org_id"], db)
        return {"status": "completed", "result": result}
    elif job.status == JobStatus.FAILED:
        return {"status": "failed", "error": job.error_message}
    elif job.status == JobStatus.CANCELLED:
        return {"status": "cancelled"}
    else:
        return {"status": job.status.value, "message": "Job is still processing. Poll again later."}


@router.post(
    "/v1/jobs/{job_id}/cancel",
    response_model=JobStatusResponse,
    summary="Cancel a job",
)
async def cancel_job_endpoint(
    job_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    job = await cancel_job(job_id, auth["org_id"], db)
    base_url = str(request.base_url).rstrip("/")
    return _job_to_response(job, base_url)


@router.post(
    "/v1/webhooks/test",
    response_model=WebhookTestResponse,
    summary="Test webhook delivery",
    description="Send a test webhook payload to a URL and return the delivery result.",
)
async def test_webhook(
    payload: WebhookTestRequest,
    auth: AuthContext = Depends(get_current_org),
) -> WebhookTestResponse:
    test_payload = build_webhook_payload(
        event="webhook.test",
        job_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        org_id=auth["org_id"],
        result={"message": "This is a test webhook from the Decision Engine."},
    )
    success, status_code, message = await deliver_webhook(
        callback_url=payload.callback_url,
        payload=test_payload,
        max_retries=0,  # No retries for test delivery
    )
    return WebhookTestResponse(success=success, status_code=status_code, message=message)
