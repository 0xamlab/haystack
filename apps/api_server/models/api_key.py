"""APIKey model — authenticates API requests on behalf of an Organization."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class APIKeyStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class APIKey(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Default")
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[APIKeyStatus] = mapped_column(
        Enum(APIKeyStatus, name="api_key_status", values_callable=lambda obj: [e.value for e in obj]),
        default=APIKeyStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organization", back_populates="api_keys"
    )
    creator: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="api_keys"
    )

    def __repr__(self) -> str:
        return f"<APIKey id={self.id} prefix={self.key_prefix} status={self.status}>"
