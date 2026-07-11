"""Provider-agnostic identity → engine org pointer.

One row per Supabase user (the stable top-level JWT ``sub``), pointing at that identity's PERSONAL
("home") engine org. This is what makes org resolution provider-agnostic: GitHub / Google / Apple /
Microsoft logins for the SAME Supabase account share one ``sub`` → one link row → one org.

It is deliberately distinct from the GitHub-slug org key (``gh-user-{id}``): an existing GitHub
user's org is ADOPTED into a link row on first agnostic resolve (keyed on the immutable GitHub id),
never duplicated — so linking a second provider later still lands on the same org. The ``sub`` is the
only identity key here; email is intentionally NOT used (Apple privaterelay / GitHub noreply aliases
make it unsafe as an identity key).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class IdentityOrgLink(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "identity_org_links"

    # The Supabase user UUID (top-level JWT `sub`) — stable across all linked providers.
    supabase_uid: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # The identity's personal ("home") org.
    org_id: Mapped[object] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
