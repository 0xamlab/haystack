"""AuditEvent model — immutable audit trail for every important action."""
import enum
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class AuditAction(str, enum.Enum):
    # Auth
    LOGIN              = "login"
    LOGOUT             = "logout"
    SIGNUP             = "signup"
    # API Keys
    API_KEY_CREATE     = "api_key.create"
    API_KEY_REVOKE     = "api_key.revoke"
    # Simulation
    SIMULATE           = "simulate"
    JOB_SUBMIT         = "job.submit"
    JOB_CANCEL         = "job.cancel"
    # Billing
    PLAN_UPGRADE       = "plan.upgrade"
    PLAN_DOWNGRADE     = "plan.downgrade"
    # Org / team
    MEMBER_INVITE      = "member.invite"
    MEMBER_REMOVE      = "member.remove"
    MEMBER_ROLE_CHANGE = "member.role_change"
    # Connectors
    CONNECTOR_CREATE   = "connector.create"
    CONNECTOR_DELETE   = "connector.delete"
    CONNECTOR_TEST     = "connector.test"


class AuditEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} action={self.action}>"
