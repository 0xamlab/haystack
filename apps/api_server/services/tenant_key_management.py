"""B10 PR11c: the self-serve write path for per-tenant provider/engine keys (BYOK onboarding).

Admin-only CRUD over ``tenant_provider_keys`` — the write side of the seam whose read/cache side is
``tenant_key_store``:

- set/rotate: encrypted at rest. REQUIRES the config encryption key (``ALGENTA_CONFIG_ENCRYPTION_KEY``)
  — refuses to store a plaintext key, so "encrypted at rest" is a hard guarantee for tenant keys
  (stricter than connector configs, which allow a plaintext-passthrough rollout).
- delete.
- list: backends only. Key material is WRITE-ONLY — never read back, never returned.

Writes commit then invalidate the resolve cache (process-local; other replicas/the worker converge
within the store's short TTL). The single per-org engine key uses the API label ``engine`` (mapped
to the reserved store backend ``algenta_engine``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.tenant_provider_key import ENGINE_BACKEND, TenantProviderKey
from apps.api_server.services.audit_service import write_audit_event
from apps.api_server.services.config_crypto import encrypt_secret, is_config_encryption_enabled
from apps.api_server.services.llm_provider_service._config import _SUPPORTED_PROVIDER_BACKENDS
from apps.api_server.services.tenant_key_store import KEY_AAD_CONTEXT, invalidate_org_keys

logger = structlog.get_logger(__name__)

# API label for the engine key (mapped to the reserved store backend so the API never exposes the
# sentinel, and a caller can't write to the sentinel slot directly).
ENGINE_API_LABEL = "engine"
_VALID_API_BACKENDS = frozenset(_SUPPORTED_PROVIDER_BACKENDS) | {ENGINE_API_LABEL}


class TenantKeyError(ValueError):
    """A client/config error in the key-management API (mapped to 4xx by the router)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _store_backend(api_backend: str) -> str:
    """Map an API backend label to the stored backend; reject unknown labels and the raw sentinel."""
    label = (api_backend or "").strip().lower()
    if label == ENGINE_API_LABEL:
        return ENGINE_BACKEND
    if label not in _VALID_API_BACKENDS or label == ENGINE_BACKEND:
        raise TenantKeyError("invalid_backend", f"unsupported backend '{api_backend}'")
    return label


def _api_backend(store_backend: str) -> str:
    return ENGINE_API_LABEL if store_backend == ENGINE_BACKEND else store_backend


async def set_org_key(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    api_backend: str,
    api_key: str,
    actor_email: str,
) -> bool:
    """Set or rotate the key for (org, backend). Returns True if this rotated an existing key.

    Refuses to store anything unless encryption is enabled — a tenant key is never stored in plaintext."""
    if not is_config_encryption_enabled():
        raise TenantKeyError(
            "encryption_key_required",
            "per-tenant keys require ALGENTA_CONFIG_ENCRYPTION_KEY (refusing to store a plaintext key)",
        )
    secret = (api_key or "").strip()
    if not secret:
        raise TenantKeyError("empty_key", "api_key must be non-empty")
    backend = _store_backend(api_backend)
    encrypted = encrypt_secret(secret, org_id=org_id, context=KEY_AAD_CONTEXT)
    row = (
        await db.execute(
            select(TenantProviderKey).where(
                TenantProviderKey.org_id == org_id, TenantProviderKey.backend == backend
            )
        )
    ).scalar_one_or_none()
    rotated = row is not None
    if row is not None:
        row.encrypted_key = encrypted
    else:
        db.add(TenantProviderKey(org_id=org_id, backend=backend, encrypted_key=encrypted))
    await write_audit_event(
        db=db,
        org_id=org_id,
        action="tenant_provider_key.set",
        actor_email=actor_email,
        resource_type="tenant_provider_key",
        resource_id=backend,
        metadata={"backend": _api_backend(backend), "rotated": rotated},  # NEVER the key value
    )
    await db.commit()
    invalidate_org_keys(org_id)  # after commit, so no concurrent resolve re-caches the stale value
    return rotated


async def delete_org_key(
    db: AsyncSession, *, org_id: uuid.UUID, api_backend: str, actor_email: str
) -> bool:
    """Delete the key for (org, backend). Returns False if there was nothing to delete."""
    backend = _store_backend(api_backend)
    row = (
        await db.execute(
            select(TenantProviderKey).where(
                TenantProviderKey.org_id == org_id, TenantProviderKey.backend == backend
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await write_audit_event(
        db=db,
        org_id=org_id,
        action="tenant_provider_key.delete",
        actor_email=actor_email,
        resource_type="tenant_provider_key",
        resource_id=backend,
        metadata={"backend": _api_backend(backend)},
    )
    await db.commit()
    invalidate_org_keys(org_id)
    return True


async def list_org_key_backends(
    db: AsyncSession, *, org_id: uuid.UUID
) -> list[tuple[str, datetime]]:
    """List the configured backends + when each was last set. Selects NO key material (write-only)."""
    rows = (
        await db.execute(
            select(TenantProviderKey.backend, TenantProviderKey.updated_at).where(
                TenantProviderKey.org_id == org_id
            )
        )
    ).all()
    return [(_api_backend(backend), updated_at) for (backend, updated_at) in rows]
