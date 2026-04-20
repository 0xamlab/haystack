"""Job lifecycle service — create, get, update, cancel async simulation jobs."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.job import (
    Job,
    JobStatus,
    WebhookStatus,
    is_terminal,
    is_valid_transition,
)
from apps.api_server.models.simulation_run import RunStatus, SimulationRun
from apps.api_server.schemas.simulate import SimulateRequest

logger = structlog.get_logger(__name__)

_DEFAULT_TTL_HOURS = 24
_SIMULATE_REQUEST_ADAPTER = TypeAdapter(SimulateRequest)


async def create_job(
    run_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
    callback_url: str | None = None,
    queue_name: str = "default",
) -> Job:
    """Create a new Job record in QUEUED state."""
    ttl = datetime.now(UTC) + timedelta(hours=_DEFAULT_TTL_HOURS)
    job = Job(
        run_id=run_id,
        org_id=org_id,
        queue_name=queue_name,
        status=JobStatus.QUEUED,
        callback_url=callback_url,
        callback_status=WebhookStatus.PENDING if callback_url else WebhookStatus.NOT_CONFIGURED,
        ttl_expires_at=ttl,
    )
    db.add(job)
    await db.flush()
    logger.info("job_created", job_id=str(job.id), run_id=str(run_id), org_id=str(org_id))
    return job


async def get_job(job_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Job:
    """Fetch a job, enforcing org isolation. Raises 404 or 403."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "job_not_found", "message": f"Job {job_id} not found."}},
        )
    if job.org_id != org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "job_access_denied",
                    "message": "Access to this job is not allowed.",
                }
            },
        )
    return job


async def update_job_status(
    job_id: uuid.UUID,
    new_status: JobStatus,
    db: AsyncSession,
    error_message: str | None = None,
) -> Job:
    """Update job status with state machine validation."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    if not is_valid_transition(job.status, new_status):
        raise ValueError(f"Invalid job transition: {job.status} → {new_status}")

    job.status = new_status
    if error_message:
        job.error_message = error_message
    if new_status == JobStatus.RUNNING:
        job.started_at = datetime.now(UTC)
    if is_terminal(new_status):
        job.completed_at = datetime.now(UTC)

    await db.flush()
    logger.info("job_status_updated", job_id=str(job_id), new_status=new_status.value)
    return job


async def cancel_job(job_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Job:
    """Cancel a job if it's still in a cancellable state."""
    job = await get_job(job_id, org_id, db)
    if is_terminal(job.status):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "job_already_terminal",
                    "message": (
                        f"Job is already in terminal state: {job.status.value}. "
                        "Cannot cancel."
                    ),
                }
            },
        )
    if not is_valid_transition(job.status, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "job_cannot_be_cancelled",
                    "message": f"Job in state '{job.status.value}' cannot be cancelled.",
                }
            },
        )
    return await update_job_status(job.id, JobStatus.CANCELLED, db)


async def get_job_result(
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any] | None:
    """Get the simulation result for a completed job, or None if not ready."""
    job = await get_job(job_id, org_id, db)
    if job.status != JobStatus.COMPLETED:
        return None

    # Fetch associated SimulationRun
    run_result = await db.execute(
        select(SimulationRun).where(SimulationRun.id == job.run_id)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        return None

    full_result = await _load_run_result_payload(run)
    if full_result is not None:
        return full_result

    return {
        "job_id": str(job_id),
        "run_id": str(job.run_id),
        "status": job.status.value,
        "engine_version": run.engine_version,
        "scenarios_run": run.scenarios_run,
        "duration_ms": run.duration_ms,
        "output_blob_ref": run.output_blob_ref,
        "message": "Full result stored. Fetch via output_blob_ref if provided.",
    }


async def execute_job(
    job_id: uuid.UUID,
    request_payload: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Execute an async simulation job end-to-end inside the API process or a worker.

    The request payload is carried alongside the job because the current async-job
    model stores metadata for the queued run, not the original simulation body.
    """
    from apps.api_server.models.job import Job
    from apps.api_server.services.simulation_service import run_simulation_fast
    from apps.api_server.services.webhook_service import (
        build_webhook_payload,
        deliver_webhook,
    )

    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    run_result = await db.execute(select(SimulationRun).where(SimulationRun.id == job.run_id))
    run = run_result.scalar_one_or_none()
    if run is None:
        raise ValueError(f"SimulationRun {job.run_id} not found for job {job_id}")

    if is_terminal(job.status):
        result = await get_job_result(job_id, job.org_id, db)
        return result or {
            "status": job.status.value,
            "job_id": str(job.id),
            "run_id": str(job.run_id),
        }

    sim_request = _SIMULATE_REQUEST_ADAPTER.validate_python(request_payload)

    job.status = JobStatus.VALIDATING
    await db.flush()

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    run.status = RunStatus.RUNNING
    run.started_at = run.started_at or datetime.now(UTC)
    await db.commit()

    try:
        envelope, _persist_meta = await run_simulation_fast(
            request=sim_request,
            org_id=job.org_id,
            api_key_id=run.api_key_id,
        )
        await db.refresh(job)
        await db.refresh(run)

        if job.status != JobStatus.CANCELLED:
            from apps.api_server.services._persist_helpers import _persist_result_reference

            persist_meta = {
                "run_id": str(run.id),
                "org_id": str(job.org_id),
                "envelope_json": envelope.model_dump(mode="json"),
            }
            await _persist_result_reference(run=run, persist_meta=persist_meta)
    except Exception as exc:
        await db.refresh(job)
        await db.refresh(run)
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        job.completed_at = datetime.now(UTC)
        run.status = RunStatus.FAILED
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        await db.commit()
        raise

    if job.status != JobStatus.CANCELLED:
        run.status = RunStatus.COMPLETED
        run.engine_version = envelope.engine_version
        run.scenarios_run = envelope.scenarios_run
        run.billing_units = 1
        run.completed_at = datetime.now(UTC)
        run.duration_ms = envelope.execution_ms
        run.result_hash = envelope.result_hash
        run.recommended_action = envelope.recommended_action
        run.confidence = envelope.confidence
        run.expected_value = envelope.metrics.expected_value
        run.probability_of_loss = envelope.metrics.probability_of_loss
        run.std_deviation = envelope.metrics.std_deviation
        run.rationale = envelope.rationale
        try:
            run.simulation_model = envelope.simulation_model  # type: ignore[assignment]
        except Exception as exc:
            logger.debug(
                "job_simulation_model_persist_failed",
                job_id=str(job.id),
                run_id=str(run.id),
                error=str(exc),
            )

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        job.error_message = None
        await db.commit()

    result = await get_job_result(job_id, job.org_id, db)
    result_payload = result or {
        "status": job.status.value,
        "job_id": str(job.id),
        "run_id": str(job.run_id),
    }

    if job.callback_url and job.status == JobStatus.COMPLETED:
        webhook_payload = build_webhook_payload(
            event="job.completed",
            job_id=job.id,
            run_id=job.run_id,
            org_id=job.org_id,
            result=result_payload,
        )
        delivered, _status_code, _message = await deliver_webhook(job.callback_url, webhook_payload)
        await db.refresh(job)
        job.callback_status = WebhookStatus.DELIVERED if delivered else WebhookStatus.FAILED
        await db.commit()

    return result_payload


async def _load_run_result_payload(run: SimulationRun) -> dict[str, Any] | None:
    """Load the full persisted result payload for a run when available."""
    if not getattr(run, "result_url", None) and not getattr(run, "output_blob_ref", None):
        return None

    from apps.api_server.services.storage_service import (
        generate_presigned_download_url,
        get_result,
    )

    result_url = run.result_url or generate_presigned_download_url(run.org_id, run.id)
    if not result_url:
        return None
    return await get_result(result_url)
