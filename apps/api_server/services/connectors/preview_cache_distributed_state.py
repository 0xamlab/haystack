from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

_DISTRIBUTED_INLINE_PREVIEW_RESULT_TTL_SECONDS = 5
_DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS = 10
_DISTRIBUTED_INLINE_PREVIEW_WAIT_TIMEOUT_SECONDS = 10.0
_DISTRIBUTED_INLINE_PREVIEW_POLL_INTERVAL_SECONDS = 0.05
_DISTRIBUTED_SAVED_CONNECTOR_RESULT_TTL_SECONDS = 1
_COMPARE_AND_EXPIRE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""
T = TypeVar("T")


class DistributedPreviewRedisClient(Protocol):
    async def get(self, key: str) -> object: ...

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        nx: bool = False,
    ) -> object: ...

    async def delete(self, key: str) -> object: ...

    async def expire(self, key: str, ttl_seconds: int) -> object: ...

    async def eval(self, script: str, numkeys: int, *args: object) -> object: ...


def distributed_inline_preview_result_key(*, operation: str, cache_key: str) -> str:
    return f"connector_preview:v1:{operation}:result:{cache_key}"


def distributed_inline_preview_lock_key(*, operation: str, cache_key: str) -> str:
    return f"connector_preview:v1:{operation}:lock:{cache_key}"


def decode_redis_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def get_distributed_inline_preview_result(  # noqa: UP047
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
    deserialize: Callable[[dict[str, Any]], T],
) -> T | None:
    try:
        raw = await redis_client.get(
            distributed_inline_preview_result_key(
                operation=operation,
                cache_key=cache_key,
            )
        )
    except Exception:
        return None
    decoded = decode_redis_value(raw)
    if not decoded:
        return None
    try:
        payload = json.loads(decoded)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return deserialize(payload)
    except (KeyError, TypeError, ValueError):
        return None


async def put_distributed_inline_preview_result(
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
    payload: dict[str, Any],
    ttl_seconds: int = _DISTRIBUTED_INLINE_PREVIEW_RESULT_TTL_SECONDS,
) -> None:
    await redis_client.set(
        distributed_inline_preview_result_key(
            operation=operation,
            cache_key=cache_key,
        ),
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
        ex=ttl_seconds,
    )


async def try_acquire_distributed_inline_preview_lock(
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
) -> tuple[bool | None, str | None]:
    token = uuid.uuid4().hex
    try:
        acquired = await redis_client.set(
            distributed_inline_preview_lock_key(
                operation=operation,
                cache_key=cache_key,
            ),
            token,
            ex=_DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS,
            nx=True,
        )
    except Exception:
        return None, None
    return bool(acquired), token if acquired else None


async def distributed_inline_preview_lock_exists(
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
) -> bool | None:
    try:
        value = await redis_client.get(
            distributed_inline_preview_lock_key(
                operation=operation,
                cache_key=cache_key,
            )
        )
    except Exception:
        return None
    return bool(decode_redis_value(value))


async def release_distributed_inline_preview_lock(
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
    token: str,
) -> None:
    lock_key = distributed_inline_preview_lock_key(
        operation=operation,
        cache_key=cache_key,
    )
    try:
        current = await redis_client.get(lock_key)
    except Exception:
        return
    if decode_redis_value(current) != token:
        return
    try:
        await redis_client.delete(lock_key)
    except Exception:
        return


async def refresh_distributed_inline_preview_lock(
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
    token: str,
    ttl_seconds: int,
) -> bool | None:
    lock_key = distributed_inline_preview_lock_key(
        operation=operation,
        cache_key=cache_key,
    )
    try:
        eval_fn = getattr(redis_client, "eval", None)
        if callable(eval_fn):
            refreshed = await eval_fn(
                _COMPARE_AND_EXPIRE_SCRIPT,
                1,
                lock_key,
                token,
                ttl_seconds,
            )
            return bool(refreshed)

        current = await redis_client.get(lock_key)
        if decode_redis_value(current) != token:
            return False
        refreshed = await redis_client.expire(lock_key, ttl_seconds)
        return bool(refreshed)
    except Exception:
        return None


def distributed_inline_preview_lock_refresh_interval(ttl_seconds: int) -> float:
    return max(0.1, ttl_seconds / 3)


async def refresh_distributed_inline_preview_lock_loop(
    *,
    redis_client: DistributedPreviewRedisClient,
    operation: str,
    cache_key: str,
    token: str,
    ttl_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    refresh_interval = distributed_inline_preview_lock_refresh_interval(ttl_seconds)
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=refresh_interval)
            return
        except TimeoutError:
            refreshed = await refresh_distributed_inline_preview_lock(
                redis_client=redis_client,
                operation=operation,
                cache_key=cache_key,
                token=token,
                ttl_seconds=ttl_seconds,
            )
            if refreshed is not True:
                return


__all__ = [
    "_DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS",
    "_DISTRIBUTED_INLINE_PREVIEW_POLL_INTERVAL_SECONDS",
    "_DISTRIBUTED_INLINE_PREVIEW_RESULT_TTL_SECONDS",
    "_DISTRIBUTED_INLINE_PREVIEW_WAIT_TIMEOUT_SECONDS",
    "_DISTRIBUTED_SAVED_CONNECTOR_RESULT_TTL_SECONDS",
    "distributed_inline_preview_lock_exists",
    "distributed_inline_preview_lock_refresh_interval",
    "distributed_inline_preview_lock_key",
    "distributed_inline_preview_result_key",
    "get_distributed_inline_preview_result",
    "put_distributed_inline_preview_result",
    "refresh_distributed_inline_preview_lock",
    "refresh_distributed_inline_preview_lock_loop",
    "release_distributed_inline_preview_lock",
    "try_acquire_distributed_inline_preview_lock",
]
