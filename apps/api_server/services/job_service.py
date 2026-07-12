"""Job lifecycle service — create, get, update, cancel async simulation jobs."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.job import (
    Job,
    JobKind,
    JobStatus,
    WebhookStatus,
    is_terminal,
    is_valid_transition,
)
from apps.api_server.models.simulation_run import RunStatus, SimulationRun
from apps.api_server.schemas.simulate import SimulateRequest
from apps.api_server.services.egress_guard import EgressAuditContext

logger = structlog.get_logger(__name__)

_DEFAULT_TTL_HOURS = 24
_SIMULATE_REQUEST_ADAPTER: TypeAdapter[Any] = TypeAdapter(SimulateRequest)


async def _get_job_for_update(job_id: uuid.UUID, db: AsyncSession) -> Job | None:
    """Load a job row with an update lock for terminal state transitions."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _get_run_for_update(run_id: uuid.UUID, db: AsyncSession) -> SimulationRun | None:
    """Load a simulation run row with an update lock for terminal state transitions."""
    result = await db.execute(
        select(SimulationRun)
        .where(SimulationRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def enforce_concurrent_jobs(org_id: uuid.UUID, plan: str, db: AsyncSession) -> None:
    """Reject async job submission when the org is at its plan's concurrent in-flight job cap
    (queued/validating/running). 0 = unlimited. Free-tier cost cap (Wave 2)."""
    from apps.api_server.services.quota_service import _metering_disabled

    if _metering_disabled():
        return  # metering off for everyone — no plan-based concurrent-job cost cap
        # (real concurrency is still bounded by the licensed worker count + Mojo pool)
    from apps.api_server.services import plan_limits

    cap = plan_limits.get(plan).concurrent_jobs
    if cap <= 0:
        return
    inflight = (
        await db.execute(
            select(func.count())
            .select_from(Job)
            .where(
                Job.org_id == org_id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.RUNNING]),
            )
        )
    ).scalar_one()
    if inflight >= cap:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "concurrent_jobs_exceeded",
                    "message": (
                        f"Your plan allows {cap} concurrent job(s); {inflight} are already in "
                        "flight. Wait for one to finish or upgrade your plan."
                    ),
                    "limit": cap,
                }
            },
        )


async def create_job(
    run_id: uuid.UUID | None,
    org_id: uuid.UUID,
    db: AsyncSession,
    callback_url: str | None = None,
    queue_name: str = "default",
    workspace_id: uuid.UUID | None = None,
    *,
    job_kind: JobKind = JobKind.SIMULATION,
    request_payload: dict[str, Any] | None = None,
) -> Job:
    """Create a new Job record in QUEUED state.

    ``run_id`` is required for simulation jobs and None for repository jobs (which
    carry their input in ``request_payload`` instead of a SimulationRun)."""
    ttl = datetime.now(UTC) + timedelta(hours=_DEFAULT_TTL_HOURS)
    job = Job(
        run_id=run_id,
        org_id=org_id,
        workspace_id=workspace_id,
        queue_name=queue_name,
        status=JobStatus.QUEUED,
        job_kind=job_kind.value,
        request_payload=request_payload,
        callback_url=callback_url,
        callback_status=WebhookStatus.PENDING if callback_url else WebhookStatus.NOT_CONFIGURED,
        ttl_expires_at=ttl,
    )
    db.add(job)
    await db.flush()
    logger.info(
        "job_created",
        job_id=str(job.id),
        run_id=str(run_id) if run_id else None,
        org_id=str(org_id),
        job_kind=job_kind.value,
    )
    return job


def _job_not_found(job_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {"code": "job_not_found", "message": f"Job {job_id} not found."}},
    )


async def get_job(
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
    workspace_id: uuid.UUID | None = None,
) -> Job:
    """Fetch a job, enforcing org isolation (and workspace isolation when ``workspace_id``
    is set). Raises 404 or 403. A None workspace_id means org-wide (internal callers and
    org-wide platform calls), mirroring workspace_scope_clauses semantics."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise _job_not_found(job_id)
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
    # Cross-workspace (same org): treat as not-found to avoid leaking existence to a sibling workspace.
    if workspace_id is not None and job.workspace_id != workspace_id:
        raise _job_not_found(job_id)
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


async def cancel_job(
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
    workspace_id: uuid.UUID | None = None,
) -> Job:
    """Cancel a job if it's still in a cancellable state. Enforces org isolation, and
    workspace isolation when ``workspace_id`` is set."""
    job = await _get_job_for_update(job_id, db)
    if job is None:
        raise _job_not_found(job_id)
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
    if workspace_id is not None and job.workspace_id != workspace_id:
        raise _job_not_found(job_id)
    if is_terminal(job.status):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "job_already_terminal",
                    "message": (
                        f"Job is already in terminal state: {job.status.value}. Cannot cancel."
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
    cancelled_at = datetime.now(UTC)
    job.status = JobStatus.CANCELLED
    job.completed_at = cancelled_at
    job.error_message = None

    run = await _get_run_for_update(job.run_id, db)
    if run is not None and run.status not in {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    }:
        run.status = RunStatus.CANCELLED
        run.completed_at = cancelled_at
        run.error_message = "Job cancelled by user."
        await db.flush()
    await db.commit()
    await db.refresh(job)
    return job


async def get_job_result(
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
    workspace_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """Get the simulation result for a completed job, or None if not ready. Enforces
    org isolation, and workspace isolation when ``workspace_id`` is set."""
    job = await get_job(job_id, org_id, db, workspace_id=workspace_id)
    if job.status != JobStatus.COMPLETED:
        return None

    # Repository jobs (Wave B1) store their result inline rather than via SimulationRun.
    # A missing job_kind defaults to 'simulation' (matching the column server_default).
    if getattr(job, "job_kind", JobKind.SIMULATION.value) != JobKind.SIMULATION.value:
        return job.result_payload

    # Fetch associated SimulationRun
    run_result = await db.execute(select(SimulationRun).where(SimulationRun.id == job.run_id))
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

    locked_job = await _get_job_for_update(job.id, db)
    locked_run = await _get_run_for_update(run.id, db)
    if locked_job is None:
        raise ValueError(f"Job {job.id} not found during startup.")
    if locked_run is None:
        raise ValueError(f"SimulationRun {run.id} not found during startup.")

    job = locked_job
    run = locked_run

    if is_terminal(job.status):
        if job.status == JobStatus.CANCELLED and run.status != RunStatus.CANCELLED:
            run.status = RunStatus.CANCELLED
            run.completed_at = run.completed_at or datetime.now(UTC)
            run.error_message = run.error_message or "Job cancelled by user."
            await db.commit()
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
            run.simulation_model = str(envelope.simulation_model)
        except Exception as exc:
            logger.debug(
                "job_simulation_model_persist_failed",
                job_id=str(job.id),
                run_id=str(run.id),
                error=str(exc),
            )
        locked_job = await _get_job_for_update(job.id, db)
        locked_run = await _get_run_for_update(run.id, db)
        if locked_job is None:
            raise ValueError(f"Job {job.id} not found during completion.")
        if locked_run is None:
            raise ValueError(f"SimulationRun {run.id} not found during completion.")

        if locked_job.status == JobStatus.CANCELLED:
            if locked_run.status != RunStatus.CANCELLED:
                locked_run.status = RunStatus.CANCELLED
                locked_run.completed_at = locked_run.completed_at or datetime.now(UTC)
                locked_run.error_message = locked_run.error_message or "Job cancelled by user."
            await db.commit()
            return {
                "status": JobStatus.CANCELLED.value,
                "job_id": str(locked_job.id),
                "run_id": str(locked_job.run_id),
            }

        completed_at = datetime.now(UTC)
        locked_run.status = RunStatus.COMPLETED
        locked_run.engine_version = envelope.engine_version
        locked_run.scenarios_run = envelope.scenarios_run
        locked_run.billing_units = 1
        locked_run.completed_at = completed_at
        locked_run.duration_ms = envelope.execution_ms
        locked_run.result_hash = envelope.result_hash
        locked_run.recommended_action = envelope.recommended_action
        locked_run.confidence = envelope.confidence
        locked_run.expected_value = envelope.metrics.expected_value
        locked_run.probability_of_loss = envelope.metrics.probability_of_loss
        locked_run.std_deviation = envelope.metrics.std_deviation
        locked_run.rationale = envelope.rationale
        try:
            locked_run.simulation_model = str(envelope.simulation_model)
        except Exception as exc:
            logger.debug(
                "job_simulation_model_persist_failed",
                job_id=str(locked_job.id),
                run_id=str(locked_run.id),
                error=str(exc),
            )

        locked_job.status = JobStatus.COMPLETED
        locked_job.completed_at = completed_at
        locked_job.error_message = None
        await db.commit()
        job = locked_job
        run = locked_run

    await db.refresh(job)
    await db.refresh(run)
    if job.status == JobStatus.CANCELLED:
        run.status = RunStatus.CANCELLED
        run.completed_at = run.completed_at or datetime.now(UTC)
        run.error_message = run.error_message or "Job cancelled by user."
        await db.commit()
        return {
            "status": JobStatus.CANCELLED.value,
            "job_id": str(job.id),
            "run_id": str(job.run_id),
        }

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
        delivered, _status_code, _message = await deliver_webhook(
            job.callback_url,
            webhook_payload,
            audit_context=EgressAuditContext(org_id=job.org_id),
        )
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
    return await get_result(result_url, org_id=run.org_id)
