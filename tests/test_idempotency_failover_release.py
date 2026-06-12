"""The idempotency write-lock release must free the lock on whichever backend acquired it, even
after a mid-request Redis->local failover.

Scenario the fix closes: Redis is healthy at acquire_write_lock (the lock token lands in Redis), then
Redis flaps during store_response and the resilient store fails over to the local fallback for the
rest of the request. The release, routed only to the now-active LOCAL store, would not touch the
Redis-held lock — stranding it until its TTL and 409-ing a same-key retry within that window. The
release now targets BOTH backends best-effort (token-compare makes the non-holding one a no-op)."""

from __future__ import annotations

import threading
import time

from apps.api_server.middleware.idempotency import (
    _LocalCoordinationStore,
    _RedisCoordinationStore,
    _ResilientCoordinationStore,
    _write_lock_storage_key,
)


class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[object, float | None]] = {}
        self._lock = threading.Lock()

    async def get(self, key: str):
        with self._lock:
            entry = self._values.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and expires_at <= time.time():
                self._values.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: object, ex: int | None = None, nx: bool = False):
        with self._lock:
            existing = self._values.get(key)
            if nx and existing is not None:
                _, expires_at = existing
                if expires_at is None or expires_at > time.time():
                    return False
            self._values[key] = (value, time.time() + ex if ex is not None else None)
            return True

    async def delete(self, key: str) -> int:
        with self._lock:
            existed = key in self._values
            self._values.pop(key, None)
            return 1 if existed else 0

    async def eval(self, script: str, numkeys: int, *args: object) -> int:
        key = str(args[0])
        token = args[1]
        with self._lock:
            entry = self._values.get(key)
            if entry is None:
                return 0
            value, _ = entry
            stored = value.decode("utf-8") if isinstance(value, bytes) else str(value)
            want = token.decode("utf-8") if isinstance(token, bytes) else str(token)
            if stored == want:
                self._values.pop(key, None)
                return 1
            return 0


def _resilient(redis):
    return _ResilientCoordinationStore(
        primary=_RedisCoordinationStore(redis), fallback=_LocalCoordinationStore()
    )


async def test_release_frees_redis_lock_after_midrequest_failover() -> None:
    redis = _FakeRedis()
    store = _resilient(redis)
    lock_key = _write_lock_storage_key("k")

    token = await store.acquire_write_lock("k", ttl_seconds=30)
    assert token is not None
    assert await redis.get(lock_key) is not None  # the lock lives in Redis

    # A mid-request Redis flap fails the store over to the local fallback for subsequent ops.
    store._active = store._fallback

    await store.release_write_lock("k", token)
    assert await redis.get(lock_key) is None, "the Redis-held lock must be released, not stranded"


async def test_retry_after_failover_release_does_not_409() -> None:
    """After the failover release frees the Redis lock, a fresh request (Redis recovered) must be
    able to acquire the same key — i.e. no stranded lock causing a spurious write-conflict 409."""
    redis = _FakeRedis()
    first = _resilient(redis)
    token = await first.acquire_write_lock("k", ttl_seconds=30)
    assert token is not None
    first._active = first._fallback  # mid-request failover
    await first.release_write_lock("k", token)

    second = _resilient(redis)  # the retry builds a fresh store (Redis healthy again)
    assert await second.acquire_write_lock("k", ttl_seconds=30) is not None


async def test_release_is_a_no_op_on_the_non_holding_backend() -> None:
    """Dual-backend release must not delete a DIFFERENT holder's lock on the backend that doesn't
    hold this token (token-compare protects both backends)."""
    redis = _FakeRedis()
    store = _resilient(redis)
    lock_key = _write_lock_storage_key("k")

    # Redis holds the lock under token A; the local fallback independently holds the SAME key under a
    # different token B (e.g. a later request that ran fully local).
    token_a = await store.acquire_write_lock("k", ttl_seconds=30)
    await store._fallback.acquire_write_lock("k", ttl_seconds=30)  # token B, local

    # Releasing token A must clear Redis (match) but leave the local holder's lock intact.
    await store.release_write_lock("k", token_a)
    assert await redis.get(lock_key) is None
    # The local lock (token B) survives — a stale token-A release didn't blow it away.
    assert await store._fallback.acquire_write_lock("k", ttl_seconds=30) is None


async def test_release_local_acquired_lock_when_redis_down() -> None:
    """When acquire fell to local (Redis down at acquire), release still frees the local lock and a
    Redis fault during release is swallowed."""

    class _DownRedis:
        async def get(self, *a, **k):
            raise ConnectionError("down")

        async def set(self, *a, **k):
            raise ConnectionError("down")

        async def eval(self, *a, **k):
            raise ConnectionError("down")

        async def delete(self, *a, **k):
            raise ConnectionError("down")

    store = _ResilientCoordinationStore(
        primary=_RedisCoordinationStore(_DownRedis()), fallback=_LocalCoordinationStore()
    )
    token = await store.acquire_write_lock("k", ttl_seconds=30)  # falls over to local
    assert token is not None
    await store.release_write_lock("k", token)  # must not raise despite the down Redis
    # the local lock is freed -> re-acquire succeeds
    assert await store._fallback.acquire_write_lock("k", ttl_seconds=30) is not None
