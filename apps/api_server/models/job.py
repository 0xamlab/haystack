"""Job model — tracks async simulation job lifecycle."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class JobStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WebhookStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class JobKind(StrEnum):
    """Discriminator for the generic async-job lifecycle (Wave B1). Simulation jobs
    use run_id/SimulationRun; repository jobs carry request/result payloads inline."""

    SIMULATION = "simulation"
    REPOSITORY_DECISION_PLAN = "repository_decision_plan"
    REPOSITORY_PIPELINE = "repository_pipeline"
    # GitHub App events (codna watches CI / issues / PR reviews). The raw event is
    # carried in request_payload; the worker drives the fix->PR pipeline.
    GITHUB_EVENT_CHECK = "github_event_check"
    GITHUB_EVENT_ISSUE = "github_event_issue"
    GITHUB_EVENT_PR_REVIEW = "github_event_pr_review"


# Valid state transitions
_VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.VALIDATING, JobStatus.CANCELLED},
    JobStatus.VALIDATING: {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: {JobStatus.EXPIRED},
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
    JobStatus.EXPIRED: set(),
}


def is_valid_transition(current: JobStatus, next_status: JobStatus) -> bool:
    """Return True if transitioning from current → next_status is valid."""
    return next_status in _VALID_TRANSITIONS.get(current, set())


def is_terminal(status: JobStatus) -> bool:
    """Return True if this status is a terminal state (no further transitions)."""
    return status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    # Nullable: repository jobs (decision-plan / pipeline) have no SimulationRun and
    # carry their input/output in request_payload/result_payload instead (Wave B1).
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    job_kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=JobKind.SIMULATION.value,
        server_default="simulation",
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Workspace sub-tenant scope (platform key via X-Workspace-Id). NULL = org-wide.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda obj: [e.value for e in obj]),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    callback_status: Mapped[WebhookStatus] = mapped_column(
        Enum(
            WebhookStatus,
            name="webhook_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=WebhookStatus.NOT_CONFIGURED,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Generic async-job payloads (Wave B1): the original request body and the computed
    # result for non-simulation kinds (simulation still uses run_id/SimulationRun).
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ttl_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status}>"
