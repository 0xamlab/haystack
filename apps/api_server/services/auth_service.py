"""API key generation, hashing, and verification service."""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import TypedDict

import structlog

from apps.api_server.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_CACHE_TTL_SECONDS = 300
_CACHE_KEY_PREFIX = "apikey:"


class AuthContext(TypedDict):
    org_id: uuid.UUID
    key_id: uuid.UUID
    user_id: uuid.UUID | None
    plan: str
    role: str  # UserRole value: owner | admin | member | viewer
    email: str  # actor email for audit logs; "api_key" when no user linked


def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(*, test: bool = False) -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (raw_key, key_prefix, hashed_key)
    """
    prefix = settings.api_key_test_prefix if test else settings.api_key_prefix
    random_part = secrets.token_urlsafe(32)[:32]
    raw_key = f"{prefix}{random_part}"
    key_prefix = raw_key[:12]
    hashed = hash_api_key(raw_key)
    return raw_key, key_prefix, hashed


async def verify_api_key(
    raw_key: str,
    db: object,
    redis_client: object,
) -> AuthContext | None:
    """
    Verify an API key. Returns AuthContext or None if invalid.

    Flow: hash key → Redis cache check → Postgres lookup → cache result.
    Never logs the raw key.
    """
    try:
        import redis.asyncio as aioredis
        from sqlalchemy import select, update
        from sqlalchemy.ext.asyncio import AsyncSession

        hashed = hash_api_key(raw_key)
        cache_key = f"{_CACHE_KEY_PREFIX}{hashed}"
        session: AsyncSession = db  # type: ignore[assignment]
        redis: aioredis.Redis = redis_client  # type: ignore[assignment]

        # ── Redis cache lookup ────────────────────────────────────────────────
        try:
            cached = await redis.hgetall(cache_key)
            if cached:
                status = cached.get(b"status", b"").decode()
                if status == "active":
                    return AuthContext(
                        org_id=uuid.UUID(cached[b"org_id"].decode()),
                        key_id=uuid.UUID(cached[b"key_id"].decode()),
                        user_id=(
                            uuid.UUID(cached[b"user_id"].decode())
                            if cached.get(b"user_id")
                            else None
                        ),
                        plan=cached[b"plan"].decode(),
                        role=cached.get(b"role", b"owner").decode(),
                        email=cached.get(b"email", b"api_key").decode(),
                    )
                return None
        except Exception as exc:
            logger.warning("redis_cache_read_failed", error=str(exc))

        # ── Database lookup ───────────────────────────────────────────────────
        from apps.api_server.models.api_key import APIKey, APIKeyStatus
        from apps.api_server.models.organization import Organization

        result = await session.execute(
            select(APIKey)
            .where(APIKey.hashed_key == hashed)
            .where(APIKey.status == APIKeyStatus.ACTIVE)
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            logger.warning("api_key_not_found", key_prefix=raw_key[:12])
            return None

        org_result = await session.execute(
            select(Organization).where(Organization.id == api_key.org_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            return None

        # Fetch linked user's role + email (if any)
        from apps.api_server.models.user import User
        actor_email = "api_key"
        # API keys without a linked user keep least-privilege member access.
        actor_role = "member"
        actor_user_id: uuid.UUID | None = None
        if api_key.user_id is not None:
            user_result = await session.execute(
                select(User).where(User.id == api_key.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user is not None:
                actor_email = user.email
                actor_role = (
                    user.role.value if hasattr(user.role, "value") else str(user.role)
                )
                actor_user_id = user.id

        # Update last_used_at
        try:
            await session.execute(
                update(APIKey)
                .where(APIKey.id == api_key.id)
                .values(last_used_at=datetime.now(UTC))
            )
        except Exception as exc:
            logger.debug(
                "api_key_last_used_update_failed",
                key_id=str(api_key.id),
                error=str(exc),
            )

        # Cache the result
        try:
            await redis.hset(
                cache_key,
                mapping={
                    "org_id": str(api_key.org_id),
                    "key_id": str(api_key.id),
                    "plan": org.plan.value,
                    "status": api_key.status.value,
                    "role": actor_role,
                    "email": actor_email,
                    "user_id": str(actor_user_id) if actor_user_id else "",
                },
            )
            await redis.expire(cache_key, _CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning("redis_cache_write_failed", error=str(exc))

        return AuthContext(
            org_id=api_key.org_id,
            key_id=api_key.id,
            user_id=actor_user_id,
            plan=org.plan.value,
            role=actor_role,
            email=actor_email,
        )
    except Exception as exc:
        logger.error("api_key_verification_failed", error=str(exc))
        return None


async def invalidate_api_key_cache(hashed_key: str, redis_client: object) -> None:
    """Remove a revoked key from Redis cache."""
    try:
        import redis.asyncio as aioredis
        redis: aioredis.Redis = redis_client  # type: ignore[assignment]
        await redis.delete(f"{_CACHE_KEY_PREFIX}{hashed_key}")
    except Exception as exc:
        logger.warning("redis_cache_invalidation_failed", error=str(exc))
