"""SimulationRun model — record of every simulation execution."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionType(str, enum.Enum):
    SYNC = "sync"
    ASYNC = "async"


class SimulationMode(str, enum.Enum):
    AUTO = "auto"
    EXPERT = "expert"


class SimulationRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "simulation_runs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mode: Mapped[SimulationMode] = mapped_column(
        Enum(SimulationMode, name="simulation_mode"),
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False, default="0.1.0")
    # SHA-256 of the request payload — used for deduplication
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"),
        default=RunStatus.RUNNING,
        nullable=False,
        index=True,
    )
    execution_type: Mapped[ExecutionType] = mapped_column(
        Enum(ExecutionType, name="execution_type"),
        default=ExecutionType.SYNC,
        nullable=False,
    )
    # S3 object key for large input payloads (> 512KB); null = inline
    input_blob_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # S3 object key for large result payloads; null = stored inline in job result
    output_blob_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenarios_run: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organization", back_populates="simulation_runs"
    )

    def __repr__(self) -> str:
        return f"<SimulationRun id={self.id} status={self.status} mode={self.mode}>"
