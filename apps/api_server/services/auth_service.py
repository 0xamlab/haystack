"""API key generation, hashing, and verification service."""

import hashlib
import secrets
import time
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Protocol, TypedDict, cast

import structlog

from apps.api_server.config import SettingsProxy
from apps.api_server.services.plan_limits import effective_device_limit

logger = structlog.get_logger(__name__)
settings = SettingsProxy()

_CACHE_TTL_SECONDS = 300
_CACHE_KEY_PREFIX = "apikey:"
_SESSION_DIRTY_INFO_KEY = "auth_session_dirty"

# In-process auth cache: hashed_key -> (AuthContext, monotonic_expiry). Removes the per-request
# apikey+organizations Postgres SELECT from the fix hot path and works with NO Redis (offline /
# single-device). Bounded staleness == _CACHE_TTL_SECONDS, same as the Redis cache; cleared
# alongside Redis on revocation (invalidate_api_key_cache).
_INPROC_AUTH_CACHE: dict = {}


class AuthContext(TypedDict):
    org_id: uuid.UUID
    key_id: uuid.UUID
    key_prefix: str
    user_id: uuid.UUID | None
    plan: str
    device_limit: int
    device_limit_configured: bool
    role: str  # UserRole value: owner | admin | member | viewer
    email: str  # actor email for audit logs; "api_key" when no user linked
    # Sub-tenancy: platform keys (Mission's company key) may act on behalf of a
    # workspace via the X-Workspace-Id header; tenant keys may not.
    is_platform: bool
    # Service keys (the agent's engine-callback key) are forced to the `viewer` role above and
    # get a narrow org-scoped repository-connector visibility allowance (data_visibility.py).
    is_service: bool
    # The active workspace scope for this request (set by get_current_org from the
    # X-Workspace-Id header for platform keys only). None = org-wide.
    workspace_id: uuid.UUID | None
    # Account-status + email-verification gates (Wave 2). Carried on the AuthContext so
    # get_current_org can enforce suspension on EVERY request (both the DB and the Redis-cache
    # path) and require_verified_email can gate agentic/expensive endpoints.
    org_status: str  # OrgStatus value: active | suspended | deleted
    user_status: str  # UserStatus value: active | suspended (… "active" when no linked user)
    email_verified: bool  # linked user's email_verified; True when no user is linked (key-only/service)


class _AsyncRedisHashClientProtocol(Protocol):
    def hgetall(self, key: str) -> Awaitable[dict[bytes, bytes]]: ...

    def hset(self, key: str, *, mapping: dict[str, str]) -> Awaitable[int]: ...

    def expire(self, key: str, ttl_seconds: int) -> Awaitable[bool]: ...

    def delete(self, key: str) -> Awaitable[int]: ...


def mark_auth_session_dirty(db: object) -> None:
    info = getattr(db, "info", None)
    if isinstance(info, dict):
        info[_SESSION_DIRTY_INFO_KEY] = True


def consume_auth_session_dirty(db: object) -> bool:
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        return False
    return bool(info.pop(_SESSION_DIRTY_INFO_KEY, False))


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


def is_api_key_expired(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when an API key has reached or passed its expiry timestamp."""
    if expires_at is None:
        return False
    normalized_expiry = (
        expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    )
    reference_time = now or datetime.now(UTC)
    return normalized_expiry <= reference_time


def api_key_expiry_epoch(expires_at: datetime | None) -> int | None:
    """Serialize a timezone-aware expiry timestamp for cache storage."""
    if expires_at is None:
        return None
    normalized_expiry = (
        expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    )
    return int(normalized_expiry.timestamp())


async def verify_api_key(
    raw_key: str,
    db: object,
    redis_client: object,
) -> AuthContext | None:
    """Verify an API key.

    In-process TTL cache FIRST (no Redis, no Postgres on a hit) so the per-request
    apikey+organizations SELECT never lands on the fix hot path — and it works with NO
    Redis (offline / single-device). Falls through to Redis+DB on a cold/expired entry.
    """
    hashed = hash_api_key(raw_key)
    now = time.monotonic()
    hit = _INPROC_AUTH_CACHE.get(hashed)
    if hit is not None and hit[1] > now:
        return hit[0]
    ctx = await _verify_api_key_impl(raw_key, db, redis_client)
    if ctx is not None:
        _INPROC_AUTH_CACHE[hashed] = (ctx, now + _CACHE_TTL_SECONDS)
    return ctx


async def _verify_api_key_impl(
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
        from sqlalchemy import select, update
        from sqlalchemy.ext.asyncio import AsyncSession

        hashed = hash_api_key(raw_key)
        cache_key = f"{_CACHE_KEY_PREFIX}{hashed}"
        session: AsyncSession = db  # type: ignore[assignment]
        redis: _AsyncRedisHashClientProtocol = cast(_AsyncRedisHashClientProtocol, redis_client)

        # ── Redis cache lookup ────────────────────────────────────────────────
        try:
            cached = await redis.hgetall(cache_key)
            if cached:
                cached_expiry = cached.get(b"expires_at")
                if cached_expiry is None:
                    await redis.delete(cache_key)
                else:
                    cache_entry_invalid = False
                    if cached_expiry:
                        try:
                            if int(cached_expiry.decode()) <= int(datetime.now(UTC).timestamp()):
                                logger.info(
                                    "api_key_expired",
                                    key_prefix=raw_key[:12],
                                    source="cache",
                                )
                                await redis.delete(cache_key)
                                return None
                        except ValueError:
                            await redis.delete(cache_key)
                            cache_entry_invalid = True
                    if cache_entry_invalid:
                        cached = {}
                    else:
                        status = cached.get(b"status", b"").decode()
                        if status == "active":
                            cached_device_limit = cached.get(b"device_limit", b"0")
                            cached_device_limit_configured = cached.get(
                                b"device_limit_configured",
                                b"",
                            )
                            try:
                                device_limit = int(cached_device_limit.decode())
                            except ValueError:
                                await redis.delete(cache_key)
                                return None
                            return AuthContext(
                                org_id=uuid.UUID(cached[b"org_id"].decode()),
                                key_id=uuid.UUID(cached[b"key_id"].decode()),
                                key_prefix=cached.get(
                                    b"key_prefix",
                                    raw_key[:12].encode(),
                                ).decode(),
                                user_id=(
                                    uuid.UUID(cached[b"user_id"].decode())
                                    if cached.get(b"user_id")
                                    else None
                                ),
                                plan=cached[b"plan"].decode(),
                                device_limit=device_limit,
                                device_limit_configured=(
                                    cached_device_limit_configured.decode() == "1"
                                ),
                                role=cached.get(b"role", b"owner").decode(),
                                email=cached.get(b"email", b"api_key").decode(),
                                is_platform=cached.get(b"is_platform", b"").decode() == "1",
                                is_service=cached.get(b"is_service", b"").decode() == "1",
                                workspace_id=None,
                                # Default missing fields (entries cached before Wave 2) to the
                                # permissive value so a stale cache never locks out a live session;
                                # the DB path writes the real values on the next cache miss (≤TTL).
                                org_status=cached.get(b"org_status", b"active").decode(),
                                user_status=cached.get(b"user_status", b"active").decode(),
                                email_verified=cached.get(b"email_verified", b"1").decode() != "0",
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
        if is_api_key_expired(api_key.expires_at):
            logger.info("api_key_expired", key_prefix=raw_key[:12], source="database")
            return None

        org_result = await session.execute(
            select(Organization).where(Organization.id == api_key.org_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            return None
        plan = org.plan.value
        org_status = org.status.value if hasattr(org.status, "value") else str(org.status)
        stored_device_limit = getattr(api_key, "device_limit", None)
        resolved_device_limit = effective_device_limit(plan, stored_device_limit)

        # Fetch linked user's role + email (if any)
        from apps.api_server.models.user import User

        actor_email = "api_key"
        # API keys without a linked user keep least-privilege member access.
        actor_role = "member"
        actor_user_id: uuid.UUID | None = None
        # Key-only / service contexts have no human user: treat as active + verified (the key's
        # existence implies a prior authenticated, verified creation flow).
        user_status = "active"
        email_verified = True
        if api_key.user_id is not None:
            user_result = await session.execute(select(User).where(User.id == api_key.user_id))
            user = user_result.scalar_one_or_none()
            if user is not None:
                actor_email = user.email
                actor_role = user.role.value if hasattr(user.role, "value") else str(user.role)
                actor_user_id = user.id
                user_status = user.status.value if hasattr(user.status, "value") else str(user.status)
                email_verified = bool(getattr(user, "email_verified", True))

        # Service keys are machine-to-machine credentials: pin them to the lowest role regardless
        # of any linked user, so a leaked service key can never reach role-gated management
        # (api-keys, provider-keys, members, billing). Its (narrow) data access comes solely from
        # the org-scoped repository-connector allowance in data_visibility, keyed on is_service.
        is_service = bool(getattr(api_key, "is_service", False))
        if is_service:
            actor_role = "viewer"

        # Update last_used_at
        try:
            await session.execute(
                update(APIKey).where(APIKey.id == api_key.id).values(last_used_at=datetime.now(UTC))
            )
            mark_auth_session_dirty(session)
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
                    "key_prefix": api_key.key_prefix,
                    "plan": plan,
                    "device_limit": str(resolved_device_limit),
                    "device_limit_configured": "1" if stored_device_limit is not None else "",
                    "status": api_key.status.value,
                    "role": actor_role,
                    "email": actor_email,
                    "user_id": str(actor_user_id) if actor_user_id else "",
                    "is_platform": "1" if getattr(api_key, "is_platform", False) else "",
                    "is_service": "1" if is_service else "",
                    "org_status": org_status,
                    "user_status": user_status,
                    "email_verified": "1" if email_verified else "0",
                    "expires_at": (
                        str(api_key_expiry_epoch(api_key.expires_at))
                        if api_key.expires_at is not None
                        else ""
                    ),
                },
            )
            await redis.expire(cache_key, _CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning("redis_cache_write_failed", error=str(exc))

        return AuthContext(
            org_id=api_key.org_id,
            key_id=api_key.id,
            key_prefix=api_key.key_prefix,
            user_id=actor_user_id,
            plan=plan,
            device_limit=resolved_device_limit,
            device_limit_configured=stored_device_limit is not None,
            role=actor_role,
            email=actor_email,
            is_platform=bool(getattr(api_key, "is_platform", False)),
            is_service=is_service,
            workspace_id=None,
            org_status=org_status,
            user_status=user_status,
            email_verified=email_verified,
        )
    except Exception as exc:
        logger.error("api_key_verification_failed", error=str(exc))
        return None


async def invalidate_api_key_cache(hashed_key: str, redis_client: object) -> None:
    """Remove a revoked key from BOTH the in-process cache and Redis."""
    _INPROC_AUTH_CACHE.pop(hashed_key, None)
    try:
        import redis.asyncio as aioredis

        redis: aioredis.Redis = redis_client  # type: ignore[assignment]
        await redis.delete(f"{_CACHE_KEY_PREFIX}{hashed_key}")
    except Exception as exc:
        logger.warning("redis_cache_invalidation_failed", error=str(exc))


async def invalidate_user_api_key_caches(
    session: object, user_id: object, redis_client: object
) -> int:
    """Bust the cached AuthContext for every API key linked to a user.

    The auth cache is keyed per key-hash, so a status/verification change for the user (suspend,
    email-verify) only takes effect after the per-key TTL (≤ _CACHE_TTL_SECONDS) unless we delete
    each of the user's cache entries here. Returns the number of keys invalidated. Best-effort:
    never raises (a Redis hiccup just falls back to TTL expiry).
    """
    from sqlalchemy import select as _select

    from apps.api_server.models.api_key import APIKey

    try:
        result = await session.execute(  # type: ignore[attr-defined]
            _select(APIKey.hashed_key).where(APIKey.user_id == user_id)
        )
        hashed_keys = [row[0] for row in result.all()]
    except Exception as exc:
        logger.warning("invalidate_user_api_key_caches_lookup_failed", error=str(exc))
        return 0
    for hashed_key in hashed_keys:
        await invalidate_api_key_cache(hashed_key, redis_client)
    return len(hashed_keys)


async def invalidate_org_api_key_caches(
    session: object, org_id: object, redis_client: object
) -> int:
    """Bust the cached AuthContext for EVERY API key in an org (e.g. on org suspend/delete), so the
    status change takes effect immediately rather than after the per-key TTL. Best-effort: never
    raises (a Redis hiccup just falls back to TTL expiry). Returns the number of keys invalidated."""
    from sqlalchemy import select as _select

    from apps.api_server.models.api_key import APIKey

    try:
        result = await session.execute(  # type: ignore[attr-defined]
            _select(APIKey.hashed_key).where(APIKey.org_id == org_id)
        )
        hashed_keys = [row[0] for row in result.all()]
    except Exception as exc:
        logger.warning("invalidate_org_api_key_caches_lookup_failed", error=str(exc))
        return 0
    for hashed_key in hashed_keys:
        await invalidate_api_key_cache(hashed_key, redis_client)
    return len(hashed_keys)
