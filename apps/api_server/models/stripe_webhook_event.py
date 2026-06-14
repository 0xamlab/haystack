"""StripeWebhookEvent — exactly-once processing ledger for Stripe webhooks (Wave 2).

One row per processed Stripe event id. The event_id primary key is the idempotency mechanism: a
duplicate webhook delivery (Stripe retries aggressively, and at-least-once is its contract) conflicts
on insert, so a state transition (plan upgrade/downgrade, usage reset) is applied exactly once.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<StripeWebhookEvent {self.event_id} type={self.event_type}>"
