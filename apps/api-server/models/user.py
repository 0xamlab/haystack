"""User model — member of an Organization."""
import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.OWNER, nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.ACTIVE, nullable=False
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organization", back_populates="users"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "APIKey", back_populates="creator", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
