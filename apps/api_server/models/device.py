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

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin

DEVICE_ID_MAX_LENGTH = 64
DEVICE_PLATFORM_MAX_LENGTH = 50
DEVICE_PLATFORM_VERSION_MAX_LENGTH = 50
DEVICE_HOSTNAME_HASH_MAX_LENGTH = 64
DEVICE_SDK_VERSION_MAX_LENGTH = 128
DEVICE_BINDING_TOKEN_HASH_MAX_LENGTH = 128
DEVICE_PUBKEY_THUMBPRINT_MAX_LENGTH = 128


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


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
    device_id: Mapped[str] = mapped_column(
        String(DEVICE_ID_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    # Display metadata (non-PII)
    platform: Mapped[str] = mapped_column(
        String(DEVICE_PLATFORM_MAX_LENGTH),
        nullable=False,
        default="",
    )
    platform_version: Mapped[str] = mapped_column(
        String(DEVICE_PLATFORM_VERSION_MAX_LENGTH),
        nullable=False,
        default="",
    )
    hostname_hash: Mapped[str] = mapped_column(
        String(DEVICE_HOSTNAME_HASH_MAX_LENGTH),
        nullable=False,
        default="",
    )
    sdk_version: Mapped[str] = mapped_column(
        String(DEVICE_SDK_VERSION_MAX_LENGTH),
        nullable=False,
        default="",
    )
    binding_token_hash: Mapped[str] = mapped_column(
        String(DEVICE_BINDING_TOKEN_HASH_MAX_LENGTH),
        nullable=False,
        default="",
    )
    # Cryptographic activation binding: the device's Ed25519 public-key thumbprint
    # ("ed25519:<b64url(sha256(pub))>"). Bound on first keypair-aware registration; a
    # later registration of the same device that presents a DIFFERENT thumbprint is a
    # clone attempt and is rejected. Empty = legacy/fingerprint-only client (unbound).
    device_pubkey_thumbprint: Mapped[str] = mapped_column(
        String(DEVICE_PUBKEY_THUMBPRINT_MAX_LENGTH),
        nullable=False,
        default="",
    )

    # Lifecycle
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(
            DeviceStatus,
            name="device_status",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
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
