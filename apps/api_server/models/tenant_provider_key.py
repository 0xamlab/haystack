"""TenantProviderKey — per-(org, backend) encrypted LLM-provider / engine key (BYOK).

B10 PR11: the store the per-tenant key-resolution seam (services/tenant_keys.py) plugs into. One
row per (org_id, backend); ``encrypted_key`` is AES-256-GCM ciphertext (config_crypto, AAD-bound to
org + a tenant-key context). The single per-org ENGINE key is stored under the reserved backend
``algenta_engine`` (so one table + a single unique (org_id, backend) constraint covers both). The
key value is NEVER returned to clients, logged, or serialized into job payloads — the worker
re-resolves from org_id."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin

# Reserved ``backend`` value for the single per-org Algenta-engine key (not a provider backend).
ENGINE_BACKEND = "algenta_engine"


class TenantProviderKey(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenant_provider_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # An LLM provider backend (openai/anthropic/google_genai/...) or the reserved ENGINE_BACKEND.
    backend: Mapped[str] = mapped_column(String(64), nullable=False)
    # AES-256-GCM ciphertext (config_crypto.encrypt_secret); plaintext only if encryption is off.
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "backend", name="uq_tenant_provider_keys_org_backend"),
    )

    def __repr__(self) -> str:  # never expose the key material
        return f"<TenantProviderKey org_id={self.org_id} backend={self.backend}>"
