"""Job model — tracks async simulation job lifecycle."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WebhookStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


# Valid state transitions
_VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED:     {JobStatus.VALIDATING, JobStatus.CANCELLED},
    JobStatus.VALIDATING: {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.RUNNING:    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED:  {JobStatus.EXPIRED},
    JobStatus.FAILED:     set(),
    JobStatus.CANCELLED:  set(),
    JobStatus.EXPIRED:    set(),
}


def is_valid_transition(current: JobStatus, next_status: JobStatus) -> bool:
    """Return True if transitioning from current → next_status is valid."""
    return next_status in _VALID_TRANSITIONS.get(current, set())


def is_terminal(status: JobStatus) -> bool:
    """Return True if this status is a terminal state (no further transitions)."""
    return status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
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
        Enum(WebhookStatus, name="webhook_status", values_callable=lambda obj: [e.value for e in obj]),
        default=WebhookStatus.NOT_CONFIGURED,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ttl_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status}>"
