"""Organization model — top-level multi-tenant entity."""

from enum import StrEnum

from sqlalchemy import Boolean, Enum, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class OrgPlan(StrEnum):
    FREE = "free"  # maps to STARTER tier on pricing page
    DEVELOPER = "developer"  # legacy / internal — treat as PRO for billing
    PRO = "pro"
    PROPLUS = "proplus"  # power-solo tier ($60) — bigger managed-usage pool, single seat
    ULTRA = "ultra"  # max-solo tier ($200) — highest single-seat throughput
    TEAM = "team"
    ENTERPRISE = "enterprise"
    TELYS_DEVELOPER = "telys_developer"  # free, 1-device, local/non-commercial Telys runtime dev license
    TELYS_PRO = "telys_pro"      # paid Telys runtime — commercial, multi-device
    TELYS_TEAM = "telys_team"    # paid Telys runtime — team/server seats
    ALGENTA_FREE = "algenta_free"    # Community — free forever, self-hosted, 1 device · 1 worker, 1 seat
    ALGENTA_PRO = "algenta_pro"      # Pro — self-hosted, PER DEVICE ($99/device), 5 workers/device, 1 seat
    ALGENTA_TEAM = "algenta_team"    # Team — self-hosted, PER DEVICE ($499/device), 20 workers/device, 15 seats
    # NOTE: `algenta_selfhost` was removed (2026-07). All paid Algenta tiers are self-hosted + per-device;
    # there is no separate self-host plan. The Postgres org_plan enum still carries the orphaned value
    # (migration 0050) — Postgres can't DROP an enum value — but it is unused and no longer offered.


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
    # Seats purchased on the Team (per-seat) subscription — synced from the Stripe
    # subscription item quantity by the webhook; drives the team seat cap. 1 for solo plans.
    seats: Mapped[int] = mapped_column(Integer(), nullable=False, default=1, server_default="1")
    # Licensed DEVICE count for per-device plans (algenta_pro/algenta_team) — synced from the Stripe
    # subscription item quantity (usage=licensed → quantity = # devices). Distinct from `seats` (people).
    # 0 = not synced yet → enforcement falls back to the static plan device cap (never a lockout).
    licensed_devices: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )

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
