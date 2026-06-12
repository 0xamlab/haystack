"""B10 PR11: the per-org key store the tenant-key seam resolves through.

Process-independent (usable from BOTH the API request and the worker process — async repo runs
execute in a separate worker), reading ``tenant_provider_keys`` by ``org_id`` and decrypting each
row. Result is cached per-org with a short TTL; rotation busts the cache via
:func:`invalidate_org_keys`.

Resilience: any store/decrypt failure degrades to an EMPTY ``OrgKeys`` (never raises into the
request/run). That is safe — an empty override means single-tenant falls back to the pooled env
key and multi-tenant (``ALGENTA_REQUIRE_PER_TENANT_KEYS=1``) still FAILS CLOSED via the seam's
``require_per_tenant_keys`` guard. Keys live only in memory + the TTL cache; they are never logged,
returned to clients, or serialized into job payloads."""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.tenant_provider_key import ENGINE_BACKEND, TenantProviderKey
from apps.api_server.services.config_crypto import decrypt_secret
from apps.api_server.services.tenant_keys import OrgKeys

logger = structlog.get_logger(__name__)

# Context label bound into the secret AAD (must match what the write path / tests encrypt with).
KEY_AAD_CONTEXT = "tenant_provider_key"

_CACHE_TTL_S = 30.0
# org_id -> (expires_monotonic, OrgKeys). Process-local; the asyncio loop is single-threaded so a
# plain dict needs no lock.
_cache: dict[uuid.UUID, tuple[float, OrgKeys]] = {}


def invalidate_org_keys(org_id: uuid.UUID | None = None) -> None:
    """Drop cached keys for one org (on rotation) or all orgs (org_id=None)."""
    if org_id is None:
        _cache.clear()
    else:
        _cache.pop(org_id, None)


async def resolve_org_keys(org_id: uuid.UUID) -> OrgKeys:
    """Resolve a tenant's keys from the store (cached). Returns an empty OrgKeys on any failure.

    Reads on its OWN short-lived session — never the caller's request/job session — so a key-store
    DB error (table missing during a deploy window, deadlock, timeout, connection blip) can never
    poison the shared transaction and turn graceful degradation into a request-wide 500 / a
    failed-and-re-billed job. The session's context manager rolls back + closes on any exit."""
    cached = _cache.get(org_id)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]

    provider_keys: dict[str, str] = {}
    engine_key: str | None = None
    try:
        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    select(TenantProviderKey).where(TenantProviderKey.org_id == org_id)
                )
            ).scalars().all()
    except Exception:
        # DB error: degrade to empty (env fallback for single-tenant; multi-tenant still fails
        # closed). Isolated to this session, so the caller's request/job transaction is untouched.
        logger.debug("tenant_key_store_query_failed", org_id=str(org_id))
        return OrgKeys(org_id=org_id)

    for row in rows:
        try:
            secret = decrypt_secret(row.encrypted_key, org_id=org_id, context=KEY_AAD_CONTEXT)
        except Exception:
            logger.debug("tenant_key_decrypt_failed", org_id=str(org_id), backend=row.backend)
            continue
        if not secret:
            continue
        if row.backend == ENGINE_BACKEND:
            engine_key = secret
        else:
            provider_keys[row.backend] = secret

    keys = OrgKeys(org_id=org_id, provider_keys=provider_keys, engine_key=engine_key)
    _cache[org_id] = (time.monotonic() + _CACHE_TTL_S, keys)
    return keys
