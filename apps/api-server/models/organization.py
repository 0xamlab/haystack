"""Organization model — top-level multi-tenant entity."""
import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class OrgPlan(str, enum.Enum):
    FREE = "free"
    DEVELOPER = "developer"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class OrgStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    plan: Mapped[OrgPlan] = mapped_column(
        Enum(OrgPlan, name="org_plan"), default=OrgPlan.FREE, nullable=False
    )
    status: Mapped[OrgStatus] = mapped_column(
        Enum(OrgStatus, name="org_status"), default=OrgStatus.ACTIVE, nullable=False
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="organization", lazy="noload"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "APIKey", back_populates="organization", lazy="noload"
    )
    simulation_runs: Mapped[list["SimulationRun"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "SimulationRun", back_populates="organization", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug} plan={self.plan}>"
