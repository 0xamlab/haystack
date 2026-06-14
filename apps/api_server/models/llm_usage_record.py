"""LLMUsageRecord model — per-call managed-LLM spend attribution (D3).

One row per LLM provider call routed through the platform, so managed (pooled-key) spend can be
attributed (org / backend / model / tokens) and capped per org (llm_spend_service). Distinct from
``UsageRecord`` (which counts billable *simulations*): this is dollar-denominated LLM cost, recorded
in **micro-dollars** (1 USD = 1_000_000 µ$) so a fraction-of-a-cent call never rounds to zero.

``key_type`` distinguishes BYOK (the org's own provider key — the customer pays the provider
directly, so ``cost_usd_micros`` is 0 and it never counts toward the managed cap) from MANAGED (the
platform's pooled key — metered + billed). Recording BYOK rows too gives the org full usage
visibility without polluting the managed-spend total.
"""

import uuid
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin

# 1 USD expressed in the integer micro-dollar unit used by cost_usd_micros.
USD_MICROS = 1_000_000


class LLMKeyType(StrEnum):
    BYOK = "byok"  # org's own provider key — customer pays the provider; not platform-metered
    MANAGED = "managed"  # platform pooled key — metered + counted toward the managed spend cap


class LLMUsageRecord(UUIDMixin, TimestampMixin, Base):
    """One row per platform-routed LLM call. Source of truth for managed-LLM monthly spend."""

    __tablename__ = "llm_usage_records"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )

    # "YYYY-MM" — same monthly window as UsageRecord; indexed for the per-org per-period spend sum.
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    backend: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    key_type: Mapped[str] = mapped_column(String(16), nullable=False)

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Platform cost in micro-dollars. 0 for BYOK (customer pays the provider directly). BigInteger:
    # it's a money column that gets SUM'd over a month — never risk an int4 overflow on accounting.
    cost_usd_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organization", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<LLMUsageRecord id={self.id} org={self.org_id} period={self.billing_period} "
            f"backend={self.backend} model={self.model} key_type={self.key_type} "
            f"cost_usd_micros={self.cost_usd_micros}>"
        )
