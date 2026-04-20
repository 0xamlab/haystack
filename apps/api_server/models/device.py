"""
DeviceRegistration — tracks which machines have registered under an API key.

Each row = one machine that has called /v1/device/register.
Used to:
  - enforce per-plan device limits
  - count active devices per org / API key
  - feed usage metering
  - allow owners to revoke specific devices

Device lifecycle:
  registered  → device called /register, license issued
  active      → device sent a heartbeat within the last 30 days
  inactive    → no heartbeat for 30+ days (still counts against limit until revoked)
  revoked     → owner explicitly removed the device
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class DeviceStatus(str, enum.Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    REVOKED  = "revoked"


class DeviceRegistration(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "device_registrations"

    # Which org and API key this device belongs to
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Device identity — hashed fingerprint, never the raw machine ID
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Display metadata (non-PII)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    platform_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    hostname_hash: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    sdk_version: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    # Lifecycle
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status",
             values_callable=lambda obj: [e.value for e in obj],
             native_enum=False),
        default=DeviceStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organization"
    )
    api_key: Mapped[APIKey] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "APIKey"
    )

    # One device_id per API key — prevents duplicate registration
    __table_args__ = (
        UniqueConstraint("api_key_id", "device_id", name="uq_device_per_api_key"),
        Index("ix_device_org_status", "org_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceRegistration device={self.device_id[:8]}... "
            f"platform={self.platform} status={self.status}>"
        )
