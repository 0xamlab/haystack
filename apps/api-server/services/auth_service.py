"""API key generation, hashing, and verification service."""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import TypedDict

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings
from apps.api_server.models.api_key import APIKey, APIKeyStatus

logger = structlog.get_logger(__name__)
settings = get_settings()

# Redis cache TTL for API key lookups
_CACHE_TTL_SECONDS = 300  # 5 minutes
_CACHE_KEY_PREFIX = "apikey:"


class AuthContext(TypedDict):
    """Auth context attached to request.state after successful verification."""
    org_id: uuid.UUID
    key_id: uuid.UUID
    plan: str


def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of raw API key. This is what's stored in DB."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(*, test: bool = False) -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        (raw_key, key_prefix, hashed_key)
        - raw_key: full key shown to user ONCE
        - key_prefix: first 8 chars for display in UI
        - hashed_key: SHA-256 hash stored in DB
    """
    prefix = settings.api_key_test_prefix if test else settings.api_key_prefix
    random_part = secrets.token_urlsafe(32)[:32]  # 32 chars of URL-safe base64
    raw_key = f"{prefix}{random_part}"
    key_prefix = raw_key[:12]  # e.g. "de_live_ab12"
    hashed = hash_api_key(raw_key)
    return raw_key, key_prefix, hashed


async def verify_api_key(
    raw_key: str,
    db: AsyncSession,
    redis_client: aioredis.Redis,  # type: ignore[type-arg]
) -> AuthContext | None:
    """
    Verify an API key and return its auth context.

    Flow:
    1. Hash the raw key
    2. Check Redis cache: if hit, return cached context
    3. On miss: query Postgres, cache result, return
    4. If key not found or revoked: return None

    Never logs the raw key.
    """
    hashed = hash_api_key(raw_key)
    cache_key = f"{_CACHE_KEY_PREFIX}{hashed}"

    # ── 1. Redis cache lookup ──────────────────────────────────────────────────
    try:
        cached = await redis_client.hgetall(cache_key)
        if cached:
            status = cached.get(b"status", b"").decode()
            if status == APIKeyStatus.ACTIVE.value:
                return AuthContext(
                    org_id=uuid.UUID(cached[b"org_id"].decode()),
                    key_id=uuid.UUID(cached[b"key_id"].decode()),
                    plan=cached[b"plan"].decode(),
                )
            # Revoked key in cache → reject immediately
            logger.warning("api_key_revoked_cache_hit", key_prefix=raw_key[:12])
            return None
    except Exception as exc:
        logger.warning("redis_cache_read_failed", error=str(exc))

    # ── 2. Database lookup ─────────────────────────────────────────────────────
    try:
        result = await db.execute(
            select(APIKey)
            .join(APIKey.organization)
            .where(APIKey.hashed_key == hashed)
            .where(APIKey.status == APIKeyStatus.ACTIVE)
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            logger.warning("api_key_not_found", key_prefix=raw_key[:12])
            return None

        # Import here to avoid circular import
        from apps.api_server.models.organization import Organization

        org_result = await db.execute(
            select(Organization).where(Organization.id == api_key.org_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            return None

        # ── 3. Update last_used_at async (fire and forget) ────────────────────
        try:
            await db.execute(
                update(APIKey)
                .where(APIKey.id == api_key.id)
                .values(last_used_at=datetime.now(timezone.utc))
            )
        except Exception:
            pass  # non-fatal

        # ── 4. Cache the result ───────────────────────────────────────────────
        try:
            await redis_client.hset(
                cache_key,
                mapping={
                    "org_id": str(api_key.org_id),
                    "key_id": str(api_key.id),
                    "plan": org.plan.value,
                    "status": api_key.status.value,
                },
            )
            await redis_client.expire(cache_key, _CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning("redis_cache_write_failed", error=str(exc))

        return AuthContext(
            org_id=api_key.org_id,
            key_id=api_key.id,
            plan=org.plan.value,
        )
    except Exception as exc:
        logger.error("api_key_verification_failed", error=str(exc))
        return None


async def invalidate_api_key_cache(hashed_key: str, redis_client: aioredis.Redis) -> None:  # type: ignore[type-arg]
    """Remove a revoked key from Redis cache."""
    try:
        await redis_client.delete(f"{_CACHE_KEY_PREFIX}{hashed_key}")
    except Exception as exc:
        logger.warning("redis_cache_invalidation_failed", error=str(exc))
