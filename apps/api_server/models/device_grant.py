"""OAuth 2.0 Device Authorization Grant (RFC 8628) state for CLI logins (e.g. ``telys login``).

Short-lived + single-use. The flow:
  1. CLI  → POST /oauth/device/code  → a (device_code, user_code) pair is minted here (status="pending").
  2. User → accounts.thyn.ai/device  signs in (Supabase) and approves; the approval binds their Supabase
     access_token onto this row (status="approved").
  3. CLI  → POST /oauth/device/token (polling) → on approval the stored access_token is returned ONCE and
     cleared. The CLI then uses it as the Bearer for the existing control-plane calls (/v1/api-keys, …).

Rows are bounded by ``expires_at`` (a sweeper/`WHERE expires_at > now()` guards every read) and the
access_token is cleared the moment it is redeemed, so a plaintext Supabase JWT never lingers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin

# Grant lifecycle.
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"


class DeviceGrant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "device_grants"

    device_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_PENDING, server_default=STATUS_PENDING
    )
    # The approving user's Supabase identity (audit) + the access_token the CLI redeems once (then cleared).
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
