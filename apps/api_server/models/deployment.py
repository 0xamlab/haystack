"""Deployment model — per-org cloud isolation with pass-through billing."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class CloudProvider(str, enum.Enum):
    ALGENTA_SHARED = "algenta_shared"  # Default multi-tenant pool
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class DeploymentStatus(str, enum.Enum):
    REQUESTED = "requested"           # User submitted request
    PROVISIONING = "provisioning"     # Control plane is creating cloud resources
    ACTIVE = "active"                 # Deployment is live and routing traffic
    UPDATING = "updating"             # In-place update in progress
    DEPROVISIONING = "deprovisioning"
    DEPROVISIONED = "deprovisioned"
    FAILED = "failed"


class Deployment(UUIDMixin, TimestampMixin, Base):
    """
    Per-org cloud deployment.

    Each org can have at most one ACTIVE deployment.
    When no deployment exists, traffic routes to the Algenta shared pool.

    Partial unique index (enforced by migration 0012, not here):
      CREATE UNIQUE INDEX uq_deployments_org_active ON deployments (org_id)
      WHERE status = 'active';

    Cost pass-through:
      - Cloud provider costs are pulled nightly via Cost Explorer / Billing API
      - `cost_usd_month_cents` is updated with current month's spend
      - Stripe usage records are created for pass-through billing (with markup)
    """

    __tablename__ = "deployments"
    # Partial unique index is managed by migration 0012 (WHERE status='active')
    # SQLAlchemy UniqueConstraint does not support partial WHERE clauses

    # ─── Ownership ─────────────────────────────────────────────────────────────
    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ─── Cloud target ──────────────────────────────────────────────────────────
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CloudProvider.ALGENTA_SHARED.value,
    )
    region: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="algenta-shared",
        comment="e.g. us-east-1, westeurope, us-central1",
    )

    # ─── Status + endpoint ─────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DeploymentStatus.REQUESTED.value,
        index=True,
    )
    endpoint_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Data plane API URL — traffic is proxied here when active",
    )
    provisioning_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Cloud resource references ─────────────────────────────────────────────
    cloud_resource_ids: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Cloud-specific resource IDs. "
            "AWS: {task_arn, rds_instance_id, ecr_image}. "
            "Azure: {container_group_id, postgres_server_id, resource_group}. "
            "GCP: {cloud_run_service, cloud_sql_instance, project_id}."
        ),
    )

    # ─── Configuration overrides ───────────────────────────────────────────────
    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Provider-specific config: instance size, storage GB, max_concurrent, etc.",
    )

    # ─── Cost tracking ─────────────────────────────────────────────────────────
    cost_usd_month_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Current calendar month cloud cost in USD cents (updated nightly)",
    )
    billing_markup_pct: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=20.0,
        comment="Pass-through billing markup percentage (default 20%)",
    )
    stripe_meter_event_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Last Stripe usage record event ID for idempotency",
    )

    # ─── Audit ─────────────────────────────────────────────────────────────────
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Deployment id={self.id} org={self.org_id} "
            f"provider={self.provider} region={self.region} status={self.status}>"
        )

    @property
    def is_active(self) -> bool:
        return self.status == DeploymentStatus.ACTIVE

    @property
    def cost_usd_month(self) -> float:
        return self.cost_usd_month_cents / 100.0

    @property
    def billable_cost_usd_month(self) -> float:
        """Cost with markup applied."""
        return self.cost_usd_month * (1 + float(self.billing_markup_pct) / 100)
