"""Celery task for async repository-intelligence jobs (Wave B1).

run_repository_job executes a repository decision-plan / pipeline job off the API
request path. It reuses simulation_task's celery_app and per-PID NullPool session
factory (acks_late + reject-on-worker-lost give restart-safe, at-least-once delivery;
execute_repository_job is idempotent on a terminal job). New queue: ``repository``.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from apps.worker.tasks.simulation_task import _get_worker_session_factory, celery_app

logger = structlog.get_logger(__name__)


def enqueue_repository_job(job_id: str) -> bool:
    """Best-effort enqueue; returns False so the caller falls back to in-process."""
    if celery_app is None or run_repository_job is None:
        return False
    try:
        run_repository_job.delay(job_id)
        return True
    except Exception as exc:  # noqa: BLE001 — degrade to in-process on broker issues
        logger.warning("repository_job_enqueue_unavailable", job_id=job_id, error=str(exc))
        return False


def _make_repository_job_task() -> Any | None:
    if celery_app is None:
        return None

    @celery_app.task(  # type: ignore[misc]
        name="apps.worker.tasks.repository_task.run_repository_job",
        bind=True,
        queue="repository",
        acks_late=True,
        max_retries=1,
    )
    def _run_repository_job(self: Any, job_id: str) -> dict[str, Any]:
        """Execute an async repository decision-plan/pipeline job end-to-end."""
        from apps.api_server.services.repository_job_service import execute_repository_job

        session_factory = _get_worker_session_factory()

        async def _run() -> dict[str, Any]:
            async with session_factory() as db:
                return await execute_repository_job(job_id=uuid.UUID(job_id), db=db)

        try:
            return asyncio.run(_run())
        except Exception as exc:
            logger.error(
                "repository_job_execution_failed", job_id=job_id, error=str(exc), exc_info=True
            )
            raise self.retry(exc=exc) from exc

    return _run_repository_job


run_repository_job = _make_repository_job_task()
