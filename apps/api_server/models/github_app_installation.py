"""GitHub App installation — binds a GitHub App install to a codna org.

Inbound GitHub webhooks resolve ``installation_id`` -> org via this table. The cached
installation access token (~1h, short-lived) is stored encrypted and refreshed on
demand by the token minter. The whole surface is inert until the GitHub App is
configured (``GITHUB_APP_*`` settings).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class GithubAppInstallation(UUIDMixin, TimestampMixin, Base):
    """One GitHub App installation, bound to the org that installed it."""

    __tablename__ = "github_app_installations"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installation_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    account_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Mirrors Job.workspace_id semantics for multi-workspace tenancy.
    workspace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Cached short-lived installation token (encrypted via config_crypto), refreshed on demand.
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )


class GithubWebhookDelivery(UUIDMixin, TimestampMixin, Base):
    """Durable, first-writer-wins dedup of GitHub webhook deliveries.

    GitHub delivers at-least-once (it re-delivers on its own), and the inbound route's
    Redis SETNX dedup is best-effort — it falls through on a Redis outage and two API
    replicas can both miss it during a blip. The UNIQUE ``delivery_id`` makes the claim
    durable + atomic so one CI failure can never be turned into two billed fix-PR jobs."""

    __tablename__ = "github_webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    # The job this delivery produced. Lets a GitHub re-delivery re-enqueue a job that was
    # committed but never ran (a crash in the commit->enqueue gap) instead of dropping it.
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
