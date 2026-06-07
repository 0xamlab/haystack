"""DecisionLog model — persistent record of decisions taken and their outcomes.

This is the feedback loop: capture what was decided, then later record what
actually happened. Enables self-improving accuracy measurement and audit trails.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class DecisionLog(UUIDMixin, TimestampMixin, Base):
    """
    One entry per decision made through the engine.

    Lifecycle:
      1. Created when a decision is taken (POST /v1/decisions)
      2. ``actual_outcome`` filled in later (PATCH /v1/decisions/{id}/outcome)
      3. ``outcome_delta`` = actual_outcome - expected_outcome (auto-computed)
    """

    __tablename__ = "decision_logs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # No FK to organizations — auth layer enforces org isolation.
        # Avoids requiring org row existence in test environments.
        nullable=False,
        index=True,
    )
    # Workspace sub-tenant scope (platform key via X-Workspace-Id). NULL = org-wide.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Link back to the simulation run that produced this decision (optional)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Human-readable context: what was the situation when this decision was made?
    context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The decision itself
    chosen_action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    options_considered: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON-encoded list of option names that were compared",
    )
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Risk profile at decision time
    risk_p5: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_pol: Mapped[float | None] = mapped_column(Float, nullable=True, doc="Probability of loss")

    # Integrity hashes (from DecisionEnvelope) for tamper detection
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    policy_snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    schema_snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    manifest_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Outcome recording — filled in later via PATCH /v1/decisions/{id}/outcome
    actual_outcome: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_delta: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="actual_outcome - expected_value; negative = worse than predicted",
    )
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Execution tracking — filled in via POST /v1/decisions/{id}/execute
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="dispatched | delivered | failed",
    )
    execution_webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    execution_response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_receipt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON blob — full webhook response details for audit",
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionLog id={self.id} action={self.chosen_action!r} "
            f"ev={self.expected_value} actual={self.actual_outcome}>"
        )
