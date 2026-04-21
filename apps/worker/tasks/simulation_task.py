"""
Celery tasks for simulation persistence and async job execution.

persist_simulation — called by the simulate endpoint after HTTP 200 is sent.
                     Writes SimulationRun, AuditEvent, UsageRecord to DB.

run_simulation_job  — executes a full async simulation job (existing behavior).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ─── Celery app ───────────────────────────────────────────────────────────────

try:
    from celery import Celery

    from apps.api_server.config import get_settings
    _settings = get_settings()
    celery_app = Celery(
        "algenta_worker",
        broker=_settings.redis_url,
        backend=_settings.redis_url,
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,           # Acknowledge only after successful execution
        task_reject_on_worker_lost=True,
        task_routes={
            "apps.worker.tasks.simulation_task.persist_simulation": {"queue": "persist"},
            "apps.worker.tasks.simulation_task.run_simulation_job":  {"queue": "simulate"},
        },
        worker_prefetch_multiplier=1,  # One task at a time per worker (CPU-bound)
        task_max_retries=3,
        task_default_retry_delay=5,
    )
except Exception:
    # Celery not installed or Redis not available — graceful degradation
    celery_app = None  # type: ignore[assignment]


# ─── persist_simulation ───────────────────────────────────────────────────────

def _make_persist_task():  # type: ignore[return]
    if celery_app is None:
        return None

    @celery_app.task(
        name="apps.worker.tasks.simulation_task.persist_simulation",
        bind=True,
        queue="persist",
        acks_late=True,
        max_retries=3,
        default_retry_delay=5,
    )
    def _persist_simulation(
        self: Any,
        persist_meta: dict[str, Any],
        plan: str,
        actor_email: str,
        client_ip: str,
    ) -> None:
        """
        Persist a completed simulation result to the database.
        Called after the HTTP 200 has already been sent to the client.

        Args:
            persist_meta: Dict from run_simulation_fast() containing run data.
            plan:         Org plan name (for quota tracking).
            actor_email:  Email for audit trail.
            client_ip:    Client IP for audit trail.
        """
        import redis.asyncio as aioredis

        from apps.api_server.config import get_settings
        from apps.api_server.db.session import AsyncSessionLocal
        from apps.api_server.services._persist_helpers import persist_simulation_run

        settings = get_settings()

        async def _run() -> None:
            redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=False,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            try:
                async with AsyncSessionLocal() as db:
                    await persist_simulation_run(
                        db=db,
                        persist_meta=persist_meta,
                        plan=plan,
                        actor_email=actor_email,
                        client_ip=client_ip,
                        redis_client=redis_client,
                    )
                    await db.commit()
            finally:
                await redis_client.aclose()

        try:
            asyncio.run(_run())
        except Exception as exc:
            logger.error(
                "persist_simulation_failed",
                run_id=persist_meta.get("run_id"),
                error=str(exc),
                exc_info=True,
            )
            raise self.retry(exc=exc) from exc

    return _persist_simulation


persist_simulation = _make_persist_task()


# ─── run_simulation_job ───────────────────────────────────────────────────────

def enqueue_simulation_job(job_id: str, request_payload: dict[str, Any]) -> bool:
    """
    Best-effort enqueue for async jobs.

    Returns True when a Celery task was accepted, False when the caller should
    fall back to in-process execution.
    """
    if celery_app is None:
        return False
    task = run_simulation_job
    if task is None:
        return False
    try:
        task.delay(job_id, request_payload)
        return True
    except Exception as exc:
        logger.warning("job_enqueue_unavailable", job_id=job_id, error=str(exc))
        return False


def _make_job_task():  # type: ignore[return]
    if celery_app is None:
        return None

    @celery_app.task(
        name="apps.worker.tasks.simulation_task.run_simulation_job",
        bind=True,
        queue="simulate",
        acks_late=True,
        max_retries=1,
    )
    def _run_simulation_job(
        self: Any,
        job_id: str,
        request_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an async simulation job end-to-end."""
        from apps.api_server.db.session import AsyncSessionLocal
        from apps.api_server.services.job_service import execute_job

        async def _run() -> dict[str, Any]:
            async with AsyncSessionLocal() as db:
                return await execute_job(
                    job_id=uuid.UUID(job_id),
                    request_payload=request_payload,
                    db=db,
                )

        try:
            return asyncio.run(_run())
        except Exception as exc:
            logger.error("job_execution_failed", job_id=job_id, error=str(exc), exc_info=True)
            raise self.retry(exc=exc) from exc

    return _run_simulation_job


run_simulation_job = _make_job_task()
