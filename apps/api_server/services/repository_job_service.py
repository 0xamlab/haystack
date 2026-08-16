"""Async execution of repository-intelligence jobs (Wave B1).

Decision-plan and pipeline runs are multi-minute LLM/agent operations; serving them
synchronously held an API worker for the whole run. They now execute here, off the
request path, via the generic Job lifecycle (a worker task, or a fire-and-forget
in-process fallback where no worker is configured). The proven simulation execute_job
path is deliberately untouched — dispatch happens at the task layer by job_kind.

The worker reconstructs the (connector, request) from job.request_payload — an external
caller's POST body — and stores the response in job.result_payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.models.job import Job, JobKind, JobStatus, WebhookStatus, is_terminal
from apps.api_server.services.egress_guard import EgressAuditContext

logger = structlog.get_logger(__name__)

# A job stuck RUNNING longer than this is treated as a crashed prior run and reclaimed on
# redelivery. Must exceed the worst-case job wall-clock so an in-flight job is never double-run.
_RUNNING_RECLAIM_AFTER_S = 3600


def _running_is_stale(job: object) -> bool:
    """True if a RUNNING job has exceeded the reclaim window (a crashed prior run)."""
    started = getattr(job, "started_at", None)
    if started is None:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (datetime.now(UTC) - started).total_seconds() > _RUNNING_RECLAIM_AFTER_S


async def _load_connector(
    db: AsyncSession,
    repository_id: uuid.UUID,
    org_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
) -> DataConnector | None:
    """Worker-safe connector fetch by (id, org[, workspace]) — no AuthContext available
    off the request path, but org/workspace isolation is preserved."""
    stmt = select(DataConnector).where(
        DataConnector.id == repository_id,
        DataConnector.org_id == org_id,
    )
    if workspace_id is not None:
        stmt = stmt.where(DataConnector.workspace_id == workspace_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _run_repository_kind(job: Job, connector: DataConnector) -> dict[str, Any]:
    """Dispatch a repository job kind to its RI service function via the public seam."""
    from apps.api_server.schemas.repositories import (
        RepositoryDecisionPlanCreateRequest,
        RepositoryPipelineRequest,
    )

    body = (job.request_payload or {}).get("request") or {}
    if job.job_kind == JobKind.REPOSITORY_DECISION_PLAN.value:
        from apps.api_server.services.repository_intelligence import (
            create_repository_decision_plan,
        )

        request = RepositoryDecisionPlanCreateRequest.model_validate(body)
        response = await create_repository_decision_plan(connector=connector, request=request)
        return response.model_dump(mode="json")
    if job.job_kind == JobKind.REPOSITORY_PIPELINE.value:
        from apps.api_server.services.repository_intelligence_pipeline import (
            run_repository_pipeline,
        )

        request = RepositoryPipelineRequest.model_validate(body)
        response = await run_repository_pipeline(connector=connector, request=request)
        return response.model_dump(mode="json")
    if job.job_kind == JobKind.REPOSITORY_SECURITY_ANALYSES.value:
        from apps.api_server.schemas.repositories import SecurityAnalysisRequest
        from apps.api_server.services.repository_intelligence import (
            analyze_repository_security,
        )

        # the reachability proof is sync CPU/graph work (no await)
        response = analyze_repository_security(
            connector=connector, request=SecurityAnalysisRequest.model_validate(body)
        )
        return response.model_dump(mode="json")
    if job.job_kind == JobKind.REPOSITORY_SECURITY_ANALYSES_CLOSURE.value:
        from apps.api_server.schemas.repositories import SecurityAnalysisClosureRequest
        from apps.api_server.services.repository_intelligence import (
            analyze_repository_security_closure,
        )

        response = analyze_repository_security_closure(
            connector=connector, request=SecurityAnalysisClosureRequest.model_validate(body)
        )
        return response.model_dump(mode="json")
    raise ValueError(f"unsupported repository job_kind: {job.job_kind}")


async def _deliver_completion_webhook(job: Job, result: dict[str, Any], db: AsyncSession) -> None:
    """Best-effort completion webhook — never fails the job."""
    if not job.callback_url:
        return
    try:
        from apps.api_server.services.webhook_service import (
            build_webhook_payload,
            deliver_webhook,
        )

        payload = build_webhook_payload(
            event="job.completed",
            job_id=job.id,
            run_id=job.run_id or job.id,
            org_id=job.org_id,
            result=result,
        )
        delivered, _status, _message = await deliver_webhook(
            job.callback_url,
            payload,
            audit_context=EgressAuditContext(org_id=job.org_id),
        )
        await db.refresh(job)
        job.callback_status = WebhookStatus.DELIVERED if delivered else WebhookStatus.FAILED
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — webhook delivery is best-effort
        logger.warning("repository_job_webhook_failed", job_id=str(job.id), error=str(exc))


async def execute_job_by_kind(job_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
    """Route a queued job to its executor by kind.

    Both the Celery worker and the in-process fallback enter here so dispatch lives in one
    place. GitHub-App-event job kinds (``github_event_*``) are retired — the codna-ai App's
    real webhook traffic is handled by codna's own separate service, never by this backend —
    so any such kind now falls through to ``execute_repository_job``, which raises a clear
    "unsupported job_kind" error rather than importing the deleted handler."""
    return await execute_repository_job(job_id=job_id, db=db)


async def execute_repository_job(job_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
    """Execute a repository decision-plan/pipeline job end-to-end (worker or fallback).

    Idempotent on re-delivery: a terminal job returns its stored result rather than
    re-running (and re-billing) the LLM agent."""
    job = (
        await db.execute(
            select(Job)
            .where(Job.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    # Idempotent on a terminal job; refuse re-entry on an in-flight RUNNING job (Celery
    # redelivery / concurrent worker) so the billable agent run is never duplicated. A job stuck
    # RUNNING past the reclaim window is a crashed prior run — fall through and re-execute so the
    # work is not lost (acks_late + reject-on-worker-lost depend on this recovery).
    if is_terminal(job.status):
        return job.result_payload or {"status": job.status.value, "job_id": str(job.id)}
    if job.status == JobStatus.RUNNING and not _running_is_stale(job):
        return {"status": job.status.value, "job_id": str(job.id)}

    job.status = JobStatus.VALIDATING
    await db.flush()

    payload = job.request_payload or {}
    try:
        repository_id = uuid.UUID(str(payload.get("repository_id")))
    except (TypeError, ValueError) as exc:
        job.status = JobStatus.FAILED
        job.error_message = f"invalid repository_id in job payload: {exc}"
        job.completed_at = datetime.now(UTC)
        await db.commit()
        raise ValueError(job.error_message) from exc

    connector = await _load_connector(db, repository_id, job.org_id, job.workspace_id)
    if connector is None:
        job.status = JobStatus.FAILED
        job.error_message = f"repository connector {repository_id} not found for org"
        job.completed_at = datetime.now(UTC)
        await db.commit()
        raise ValueError(job.error_message)

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    await db.commit()

    # B10 PR11: this runs in the worker / fire-and-forget context, OUTSIDE any request — so the
    # API auth hook's ContextVar isn't here. Re-resolve the tenant's keys from job.org_id (NEVER
    # carried in the job payload) and bind them for the run; reset in finally.
    from apps.api_server.services.tenant_key_store import resolve_org_keys
    from apps.api_server.services.tenant_keys import (
        reset_org_keys_override,
        set_org_keys_override,
    )

    _tenant_keys_token = set_org_keys_override(await resolve_org_keys(job.org_id))
    try:
        result = await _run_repository_kind(job, connector)
    except Exception as exc:
        await db.refresh(job)
        if job.status != JobStatus.CANCELLED:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            await db.commit()
        raise
    finally:
        reset_org_keys_override(_tenant_keys_token)

    await db.refresh(job)
    if job.status == JobStatus.CANCELLED:
        await db.commit()
        return {"status": JobStatus.CANCELLED.value, "job_id": str(job.id)}

    job.result_payload = result
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.error_message = None
    await db.commit()

    await _deliver_completion_webhook(job, result, db)
    return result
