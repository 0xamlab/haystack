"""Organization model — top-level multi-tenant entity."""

from enum import StrEnum

from sqlalchemy import Boolean, Enum, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class OrgPlan(StrEnum):
    FREE = "free"  # maps to STARTER tier on pricing page
    DEVELOPER = "developer"  # legacy / internal — treat as PRO for billing
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class OrgStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    plan: Mapped[OrgPlan] = mapped_column(
        Enum(OrgPlan, name="org_plan", values_callable=lambda obj: [e.value for e in obj]),
        default=OrgPlan.FREE,
        nullable=False,
    )
    status: Mapped[OrgStatus] = mapped_column(
        Enum(OrgStatus, name="org_status", values_callable=lambda obj: [e.value for e in obj]),
        default=OrgStatus.ACTIVE,
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # ── Managed-LLM pass-through (D3) ─────────────────────────────────────────
    # When the deployment runs in managed-LLM mode (ALGENTA_MANAGED_LLM=1, hosted), an org may use
    # the platform's pooled provider key ONLY if managed_llm_enabled is set — and every such call is
    # metered + capped (llm_spend_service). managed_llm_quota_usd_month overrides the plan's default
    # llm_spend_cap_usd_month when > 0 (0 = inherit the plan cap). Both default off/0 so existing
    # single-tenant + BYOK deployments are unchanged until an org is explicitly opted into managed.
    managed_llm_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False, server_default=false()
    )
    managed_llm_quota_usd_month: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )

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
