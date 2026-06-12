"""The idempotency write-lock release must be an ATOMIC, token-scoped compare-and-delete.

Before this fix, ``_RedisCoordinationStore.release_write_lock`` did a separate GET then DELETE. In
the window between the two a Redis-side lock could expire and be re-acquired by a *different* request
(a fresh token), and the stale holder's unconditional DELETE would then blow away that new holder's
lock — letting two writers run concurrently under the same idempotency key. The fix issues a single
Lua ``compare-and-delete`` so the check and delete are indivisible: only the live token holder ever
removes the key, and there is no GET/DELETE window to race through.
"""

from __future__ import annotations

import threading
import time

from apps.api_server.middleware.idempotency import (
    _RedisCoordinationStore,
    _write_lock_storage_key,
)


class _FakeRedis:
    """In-memory async Redis supporting the exact ops the lock uses: set(nx,ex)/get/delete/eval."""

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
            value, expires_at = entry
            if expires_at is not None and expires_at <= time.time():
                self._values.pop(key, None)
                return 0
            stored = value.decode("utf-8") if isinstance(value, bytes) else str(value)
            want = token.decode("utf-8") if isinstance(token, bytes) else str(token)
            if stored == want:
                self._values.pop(key, None)
                return 1
            return 0


class _RecordingRedis(_FakeRedis):
    def __init__(self) -> None:
        super().__init__()
        self.ops: list[str] = []

    async def get(self, key: str):
        self.ops.append("get")
        return await super().get(key)

    async def delete(self, key: str) -> int:
        self.ops.append("delete")
        return await super().delete(key)

    async def eval(self, script: str, numkeys: int, *args: object) -> int:
        self.ops.append("eval")
        return await super().eval(script, numkeys, *args)


async def test_release_issues_a_single_atomic_eval_not_get_then_delete() -> None:
    """The structural guarantee: release is ONE round trip (eval), never a get + delete pair —
    so there is no TOCTOU window between reading the token and deleting the key."""
    redis = _RecordingRedis()
    store = _RedisCoordinationStore(redis)
    token = await store.acquire_write_lock("k", ttl_seconds=30)
    assert token is not None

    redis.ops.clear()
    await store.release_write_lock("k", token)

    assert redis.ops == ["eval"], f"expected a single atomic eval, got {redis.ops}"
    assert await redis.get(_write_lock_storage_key("k")) is None  # the holder's lock is gone


async def test_stale_holder_release_does_not_delete_a_new_holders_lock() -> None:
    """The bug this closes: after the original lock turns over to a new holder, the stale holder's
    release must be a no-op — it must NOT delete the lock the new holder now owns."""
    redis = _FakeRedis()
    store = _RedisCoordinationStore(redis)
    lock_key = _write_lock_storage_key("k")

    token_a = await store.acquire_write_lock("k", ttl_seconds=30)
    assert token_a is not None

    # The lock turns over: it expires/clears and another request acquires it under a fresh token.
    await redis.delete(lock_key)
    token_b = await store.acquire_write_lock("k", ttl_seconds=30)
    assert token_b is not None and token_b != token_a

    # The stale holder (token_a) releases — must NOT touch token_b's live lock.
    await store.release_write_lock("k", token_a)
    assert await redis.get(lock_key) is not None, "token_a's stale release wrongly deleted B's lock"

    # The real holder can still release its own lock.
    await store.release_write_lock("k", token_b)
    assert await redis.get(lock_key) is None


async def test_release_with_correct_token_clears_the_lock() -> None:
    redis = _FakeRedis()
    store = _RedisCoordinationStore(redis)
    token = await store.acquire_write_lock("k", ttl_seconds=30)
    assert token is not None
    assert await redis.get(_write_lock_storage_key("k")) is not None
    await store.release_write_lock("k", token)
    assert await redis.get(_write_lock_storage_key("k")) is None
    # A second acquire succeeds now that the lock is genuinely released.
    assert await store.acquire_write_lock("k", ttl_seconds=30) is not None
