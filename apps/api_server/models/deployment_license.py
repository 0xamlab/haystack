"""DeploymentLicenseRegistration — tracks organization SERVER LICENSE deployments (Compute-Unit
scope). The deployment-scope counterpart to ``DeviceRegistration``.

Distinct from the unrelated ``deployment.py`` (cloud-isolation ``Deployment``): this is purely
a licensing record. Each row = one licensed server deployment identity, bound to a deployment
public-key thumbprint, carrying the purchased Compute-Unit ceiling. Kept separate from
``device_registrations`` so the device and deployment scopes never mix (a deployment never
consumes a device slot and vice versa).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin

DEPLOYMENT_ID_MAX_LENGTH = 128
DEPLOYMENT_PRODUCT_MAX_LENGTH = 32
DEPLOYMENT_PUBKEY_THUMBPRINT_MAX_LENGTH = 128


class DeploymentLicenseStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class DeploymentLicenseRegistration(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deployment_license_registrations"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "deployment_id", name="uq_deployment_license_org_deployment_id"
        ),
    )

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
    deployment_id: Mapped[str] = mapped_column(
        String(DEPLOYMENT_ID_MAX_LENGTH), nullable=False, index=True
    )
    product: Mapped[str] = mapped_column(
        String(DEPLOYMENT_PRODUCT_MAX_LENGTH), nullable=False, default=""
    )
    # Compute-Unit ceiling this deployment was licensed for (the purchased quantity).
    max_concurrent_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The deployment key thumbprint the license is bound to (a copied file alone can't run).
    deployment_pubkey_thumbprint: Mapped[str] = mapped_column(
        String(DEPLOYMENT_PUBKEY_THUMBPRINT_MAX_LENGTH), nullable=False, default=""
    )
    # jti of the most recent minted license (revocation / audit).
    license_jti: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[DeploymentLicenseStatus] = mapped_column(
        Enum(
            DeploymentLicenseStatus,
            name="deployment_license_status",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=DeploymentLicenseStatus.ACTIVE,
        nullable=False,
    )
    last_activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DeploymentNodeLease(UUIDMixin, TimestampMixin, Base):
    """L3 connected-pool authority: one row per engine node currently leasing Compute Units from a
    deployment's pool (server-side, DB-backed — the connected equivalent of the Relay ledger). A
    node is ACTIVE while its ``last_heartbeat_at`` is within the census window; the control plane
    admits a node only if the sum of active nodes' ``granted_units`` stays within the deployment's
    ``max_concurrent_units``."""

    __tablename__ = "deployment_node_leases"
    __table_args__ = (
        UniqueConstraint(
            "deployment_registration_id", "node_thumbprint", name="uq_deployment_node_lease"
        ),
    )

    deployment_registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployment_license_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_thumbprint: Mapped[str] = mapped_column(
        String(DEPLOYMENT_PUBKEY_THUMBPRINT_MAX_LENGTH), nullable=False, index=True
    )
    granted_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
