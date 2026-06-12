"""Wave-C: cross-node coordination for repository-intelligence (the multi-replica dedup lock).

``run_once_distributed`` serializes a non-idempotent generation (e.g. the verified_agentic planner)
across API/worker replicas so two replicas don't both run it and persist DIVERGENT results
(the #94/#95 cross-replica dedup gap). It is a WAITER lock — modeled on the proven
``connectors/preview_cache_distributed_*`` helpers: the loser does NOT 409; it waits and serves the
winner's published result. Tier-aware on a true wait-deadline:
  - ``deterministic=True`` (sim / preview): fall through to its own ``generate()`` — identical
    output, only wasted work.
  - ``deterministic=False`` (the planner): FAIL CLOSED (raise ``CoordinationTimeout``, a retryable
    error) and NEVER regenerate a divergent artifact.

Redis is OPT-IN + presence-gated (``ALGENTA_COORDINATION=redis``, default ``local``, mirroring
``ALGENTA_RI_OBJECT_STORE``). When it is off or unreachable ``get_coordination_redis()`` returns
None and the CALLER keeps its existing host-local ``fcntl.flock`` path (correct for a single
process; self-hosted single-replica is unaffected — Redis never becomes a hard new dependency).
Every Redis op is individually guarded; acquire / renew / release are pinned to the SAME client and
are token-compare atomic (Lua), so only the holder mutates the lock and a failed renewal is treated
as lock-loss (the holder fails closed rather than continuing on an expired lease)."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")

_KEY_PREFIX = "ri:coord:v1:lock:"
_POLL_INTERVAL_SECONDS = 0.05
# atomic compare-and-{expire,delete}: only the token holder mutates the lock (no GET-then-op TOCTOU).
_COMPARE_AND_EXPIRE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('expire', KEYS[1], ARGV[2]) end return 0"
)
_COMPARE_AND_DELETE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)


class CoordinationTimeout(RuntimeError):
    """A non-deterministic generation could not be served within the wait deadline. The caller must
    fail closed with a RETRYABLE error rather than regenerate a divergent artifact."""


class _RedisClient(Protocol):
    async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> object: ...
    async def get(self, key: str) -> object: ...
    async def eval(self, script: str, numkeys: int, *args: object) -> object: ...


# --- presence signal + lazy guarded accessor ---------------------------------------------------


def coordination_mode() -> str:
    return (os.environ.get("ALGENTA_COORDINATION") or "local").strip().lower()


def coordination_enabled() -> bool:
    """True only when cross-node coordination is explicitly enabled AND a usable redis_url is set.
    Default is ``local`` (single-process flock), so a self-hosted single-replica deploy needs no
    Redis for the coordination path."""
    if coordination_mode() != "redis":
        return False
    from apps.api_server.config import get_settings

    return bool((get_settings().redis_url or "").strip())


_redis_singleton: _RedisClient | None = None
_redis_resolved = False


def get_coordination_redis() -> _RedisClient | None:
    """Lazily build a process-global async Redis client for coordination, or None when coordination
    is disabled / a client can't be constructed. Usable from HTTP, the pipeline, AND the worker (no
    ``app.state`` dependency). A construction error degrades to None (the caller uses its host-local
    flock) — it NEVER raises, so a bad/empty REDIS_URL can't break a request."""
    global _redis_singleton, _redis_resolved
    if _redis_resolved:
        return _redis_singleton
    _redis_resolved = True
    if not coordination_enabled():
        _redis_singleton = None
        return None
    try:
        import redis.asyncio as aioredis

        from apps.api_server.config import get_settings

        _redis_singleton = aioredis.from_url(
            get_settings().redis_url,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    except Exception as exc:  # noqa: BLE001 — degrade to local flock, never crash
        logger.warning("ri_coordination_redis_unavailable", error=str(exc))
        _redis_singleton = None
    return _redis_singleton


def reset_coordination_redis_for_test() -> None:
    global _redis_singleton, _redis_resolved
    _redis_singleton = None
    _redis_resolved = False


# --- lock primitives (token-compare atomic) -----------------------------------------------------


def _decode(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def _try_acquire(redis: _RedisClient, lock_key: str, token: str, ttl: int) -> bool:
    try:
        return bool(await redis.set(lock_key, token, ex=ttl, nx=True))
    except Exception as exc:  # noqa: BLE001
        logger.debug("ri_coord_acquire_error", error=str(exc))
        return False


async def _lock_held_by_someone(redis: _RedisClient, lock_key: str) -> bool:
    try:
        return bool(_decode(await redis.get(lock_key)))
    except Exception:  # noqa: BLE001
        return False


async def _compare_eval(
    redis: _RedisClient, script: str, lock_key: str, token: str, *args: object
) -> bool | None:
    try:
        return bool(await redis.eval(script, 1, lock_key, token, *args))
    except Exception as exc:  # noqa: BLE001
        logger.debug("ri_coord_eval_error", error=str(exc))
        return None


async def _renew_loop(
    redis: _RedisClient, lock_key: str, token: str, ttl: int, lost: asyncio.Event, stop: asyncio.Event
) -> None:
    """Renew the lease every ttl/3 via compare-and-expire; on a failed renewal set ``lost`` and
    stop. acquire == renew == release are the SAME client (no per-call failover), so a failed renew
    means the real lease is at risk — the holder treats that as lock-loss."""
    interval = max(0.1, ttl / 3)
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except TimeoutError:
            if await _compare_eval(redis, _COMPARE_AND_EXPIRE, lock_key, token, ttl) is not True:
                lost.set()
                return


# --- the waiter ---------------------------------------------------------------------------------


async def run_once_distributed(
    *,
    redis: _RedisClient,
    key: str,
    ttl_seconds: int,
    wait_timeout_seconds: float,
    deterministic: bool,
    load: Callable[[], Awaitable[T | None]],
    generate: Callable[[], Awaitable[T]],
    publish: Callable[[T], Awaitable[None]],
) -> T:
    """Run ``generate`` at most once across replicas for ``key``; losers wait and serve the winner's
    published result (via ``load``). ``redis`` MUST be live — the caller resolves it via
    ``get_coordination_redis()`` and uses its own flock path when that is None.

    Contract: ``load`` returns the already-published result or None; ``generate`` produces it (the
    expensive non-idempotent op, run only by the holder); ``publish`` stores it so a loser's
    ``load`` sees it. On a true wait-deadline: deterministic → fall through to ``generate``;
    non-deterministic → raise ``CoordinationTimeout`` (caller fails closed, retryable)."""
    existing = await load()
    if existing is not None:
        return existing

    lock_key = _KEY_PREFIX + key
    deadline = asyncio.get_event_loop().time() + wait_timeout_seconds

    while True:
        token = uuid.uuid4().hex
        if await _try_acquire(redis, lock_key, token, ttl_seconds):
            lost = asyncio.Event()
            stop = asyncio.Event()
            renew = asyncio.create_task(_renew_loop(redis, lock_key, token, ttl_seconds, lost, stop))
            try:
                # double-check inside the lock — another replica may have published just before us.
                existing = await load()
                if existing is not None:
                    return existing
                result = await generate()
            finally:
                stop.set()
                await renew
            if lost.is_set():
                # lease lost mid-generate (Redis trouble) — another replica may have taken over.
                await _compare_eval(redis, _COMPARE_AND_DELETE, lock_key, token)
                if deterministic:
                    await publish(result)  # output is identical; safe to publish
                    return result
                raise CoordinationTimeout(f"coordination lease lost during generation for '{key}'")
            await publish(result)
            await _compare_eval(redis, _COMPARE_AND_DELETE, lock_key, token)
            return result

        # did not acquire — another replica holds it. Wait for its published result.
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            published = await load()
            if published is not None:
                return published
            if not await _lock_held_by_someone(redis, lock_key):
                break  # holder released without publishing (crash/failure) — retry the acquire
        else:
            # true wait-deadline
            if deterministic:
                return await generate()
            raise CoordinationTimeout(
                f"timed out waiting {wait_timeout_seconds}s for another replica to produce '{key}'"
            )


@asynccontextmanager
async def coordinated_generation_lock(
    *,
    key: str,
    ttl_seconds: int,
    wait_timeout_seconds: float,
    deterministic: bool,
    redis: _RedisClient | None = None,
    local_fallback: Callable[[], Any] | None = None,
) -> AsyncIterator[None]:
    """Cross-node BLOCKING generation lock for the existing ``with lock: re-check; generate`` shape
    (used by the decision-plan path so the body is not restructured). The loser BLOCKS until the
    winner releases, then the caller's own in-lock re-check of the shared index serves the winner's
    result instead of regenerating.

    redis None -> the caller's host-local ``local_fallback`` (a sync flock CM factory), correct for a
    single process. Else acquire-wait (retry SET NX EX until acquired or the deadline) with
    lease renewal; on a true deadline: deterministic -> proceed unlocked (best-effort, identical
    output); non-deterministic -> raise CoordinationTimeout (the caller fails closed, retryable).
    acquire == renew == release are pinned to the same client; release is the atomic Lua
    compare-and-delete. NOTE: a lease lost mid-body (renewal fails for a full TTL — Redis trouble) is
    a documented residual mitigated by a TTL >= worst-case run + renewal + the caller's append-only
    artifact guard + the shared in-lock re-check on the retry; use run_once_distributed when a
    publish-time lost-lease check is required."""
    if redis is None:
        if local_fallback is None:
            yield
            return
        with local_fallback():
            yield
        return

    lock_key = _KEY_PREFIX + key
    token = uuid.uuid4().hex
    loop = asyncio.get_event_loop()
    deadline = loop.time() + wait_timeout_seconds
    acquired = False
    while True:
        if await _try_acquire(redis, lock_key, token, ttl_seconds):
            acquired = True
            break
        if loop.time() >= deadline:
            break
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    if not acquired:
        if deterministic:
            yield  # best-effort: proceed without the lock (output is identical)
            return
        raise CoordinationTimeout(f"timed out acquiring the coordination lock for '{key}'")

    lost = asyncio.Event()
    stop = asyncio.Event()
    renew = asyncio.create_task(_renew_loop(redis, lock_key, token, ttl_seconds, lost, stop))
    try:
        yield
    finally:
        stop.set()
        await renew
        await _compare_eval(redis, _COMPARE_AND_DELETE, lock_key, token)
