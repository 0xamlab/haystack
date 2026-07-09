"""Runtime-side cross-node coordination — the medium a customer's OWN self-hosted engine nodes use to
count each other for ``active_node_limit`` enforcement, WITHOUT phoning home to Algenta.

This is the runtime-plane sibling of ``apps/api_server/services/repository_intelligence_coordination.py``.
It deliberately imports NOTHING from ``apps.api_server`` (the runtime plane must stand alone in a
self-hosted deployment) and reads its config straight from the environment:

  * ``ALGENTA_COORDINATION=redis``           opt-in presence signal (default ``local`` ⇒ disabled)
  * ``ALGENTA_COORDINATION_REDIS_URL``       the census medium (falls back to ``REDIS_URL``)

When coordination is off / unreachable, ``get_runtime_coordination_redis()`` returns ``None`` and the
caller (``node_broker``) applies its fail-closed fallback. A construction / op error NEVER raises here —
it degrades to ``None`` / a sentinel so a Redis hiccup can't crash a booting node.

The census is a Redis **sorted set per license** (``score`` = last-seen epoch, ``member`` = the node's
public-key thumbprint). Admission is a single atomic Lua eval that (a) prunes members older than the
window, (b) always refreshes an already-present member (never evicts a live node — mirrors the control
plane's ``node_admission_block_count``), and (c) admits a new member only while ``ZCARD < limit``. The one
eval kills the last-slot TOCTOU.
"""
from __future__ import annotations

import os

import structlog

logger = structlog.get_logger(__name__)

_CENSUS_KEY_PREFIX = "algenta:nodecap:v1:census:"

# Atomic admit/refresh. KEYS[1]=census zset. ARGV: 1=member 2=now 3=window_seconds 4=limit.
# Returns 1 (admitted or refreshed) or 0 (over cap). Never evicts an existing live member.
_CENSUS_ADMIT_LUA = (
    "local now = tonumber(ARGV[2]) "
    "local window = tonumber(ARGV[3]) "
    "local limit = tonumber(ARGV[4]) "
    "redis.call('zremrangebyscore', KEYS[1], '-inf', now - window) "
    "if redis.call('zscore', KEYS[1], ARGV[1]) then "
    "  redis.call('zadd', KEYS[1], now, ARGV[1]) "
    "  redis.call('expire', KEYS[1], window * 2) "
    "  return 1 "
    "end "
    "if redis.call('zcard', KEYS[1]) < limit then "
    "  redis.call('zadd', KEYS[1], now, ARGV[1]) "
    "  redis.call('expire', KEYS[1], window * 2) "
    "  return 1 "
    "end "
    "return 0"
)


def coordination_mode() -> str:
    return (os.environ.get("ALGENTA_COORDINATION") or "local").strip().lower()


def _redis_url() -> str:
    return (
        os.environ.get("ALGENTA_COORDINATION_REDIS_URL") or os.environ.get("REDIS_URL") or ""
    ).strip()


def coordination_enabled() -> bool:
    """True only when coordination is explicitly ``redis`` AND a usable url is set. Default ``local`` ⇒
    a single self-hosted node needs no Redis (its own node-cap is device-binding, air-gap-safe)."""
    return coordination_mode() == "redis" and bool(_redis_url())


_redis_singleton: object | None = None
_redis_resolved = False


def get_runtime_coordination_redis() -> object | None:
    """Lazily build a process-global async Redis client for the node census, or ``None`` when
    coordination is disabled / unconstructable. NEVER raises — a bad url degrades to ``None`` and the
    caller falls back (a bound token still boots; an unbound token fails closed)."""
    global _redis_singleton, _redis_resolved
    if _redis_resolved:
        return _redis_singleton
    _redis_resolved = True
    if not coordination_enabled():
        _redis_singleton = None
        return None
    try:
        import redis.asyncio as aioredis

        _redis_singleton = aioredis.from_url(
            _redis_url(),
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    except Exception as exc:  # noqa: BLE001 — degrade to None, never crash a booting node
        logger.warning("runtime_coordination_redis_unavailable", error=str(exc))
        _redis_singleton = None
    return _redis_singleton


def reset_runtime_coordination_for_test() -> None:
    global _redis_singleton, _redis_resolved
    _redis_singleton = None
    _redis_resolved = False


def _census_key(license_id: str) -> str:
    return _CENSUS_KEY_PREFIX + license_id


async def census_admit(
    redis: object, license_id: str, member: str, *, now: float, window: int, limit: int
) -> bool | None:
    """Atomically admit/refresh ``member`` in the license's census. Returns True (admitted or refreshed
    live member), False (over the cap), or ``None`` on a Redis error (census unavailable → caller decides
    fail-closed vs bound-token-ok). Never raises."""
    try:
        result = await redis.eval(  # type: ignore[attr-defined]
            _CENSUS_ADMIT_LUA, 1, _census_key(license_id), member, str(now), str(int(window)), str(int(limit))
        )
        return bool(int(result))
    except Exception as exc:  # noqa: BLE001
        logger.warning("node_census_admit_error", error=str(exc))
        return None


async def census_count(redis: object, license_id: str, *, now: float, window: int) -> int | None:
    """Live member count after pruning stale entries (observability / tests). ``None`` on error."""
    try:
        await redis.zremrangebyscore(_census_key(license_id), "-inf", now - window)  # type: ignore[attr-defined]
        return int(await redis.zcard(_census_key(license_id)))  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.debug("node_census_count_error", error=str(exc))
        return None


async def census_release(redis: object, license_id: str, member: str) -> None:
    """Remove this node from the census on graceful shutdown (frees a slot immediately). Never raises."""
    try:
        await redis.zrem(_census_key(license_id), member)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.debug("node_census_release_error", error=str(exc))
