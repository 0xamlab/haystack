"""Record of dormant-account warning notices sent, so the sweep never double-sends.

One row per (email, notice_type) — e.g. ("ada@x.com", "warn_30"). The sweep checks this before
sending each stage's email and inserts on success.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class DormantNotification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dormant_notifications"
    __table_args__ = (UniqueConstraint("email", "notice_type", name="uq_dormant_notice"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notice_type: Mapped[str] = mapped_column(String(20), nullable=False)  # warn_30|warn_14|warn_7|warn_1|deleted
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
