"""UsageRecord model — per-request billing unit tracking."""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class UsageEndpoint(StrEnum):
    SIMULATE = "simulate"
    RECOMMEND = "recommend"
    SCORE = "score"
    BATCH = "batch"
    COMPARE = "compare"
    JOB = "job"


class UsageRecord(UUIDMixin, TimestampMixin, Base):
    """
    One row per billable API call.
    Written synchronously in the hot path (simulation service).
    Used for:
    - Monthly quota checks (count rows per org per billing_period)
    - Usage dashboard in the external web interface (group by day/endpoint)
    - Stripe metered billing hooks (future)
    """

    __tablename__ = "usage_records"

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
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    simulation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Billing dimensions
    billing_period: Mapped[str] = mapped_column(
        String(7),  # "YYYY-MM"
        nullable=False,
        index=True,
    )
    endpoint: Mapped[UsageEndpoint] = mapped_column(
        Enum(
            UsageEndpoint,
            name="usage_endpoint",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    billing_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scenarios_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Wave-C exactly-once billing: a logical-run idempotency key (e.g. "sim:<run_id>"). A retried
    # persist upserts exactly ONE UsageRecord per logical run. Nullable + PARTIAL-unique (see
    # migration 0034): NULL-keyed rows (heartbeat / credits writers) are exempt from the constraint.
    usage_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organization", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<UsageRecord id={self.id} org={self.org_id} "
            f"period={self.billing_period} endpoint={self.endpoint}>"
        )
