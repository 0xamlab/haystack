from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TypeVar

from apps.api_server.services.connectors import preview_cache_distributed_state
from apps.api_server.services.connectors.preview_cache_distributed_state import (
    DistributedPreviewRedisClient,
    distributed_inline_preview_lock_exists,
    get_distributed_inline_preview_result,
    put_distributed_inline_preview_result,
    refresh_distributed_inline_preview_lock_loop,
    release_distributed_inline_preview_lock,
    try_acquire_distributed_inline_preview_lock,
)
from apps.api_server.services.connectors.preview_cache_local import (
    _inline_preview_cache_key,
    put_cached_inline_preview_browse_outcome,
    put_cached_inline_preview_test_outcome,
)
from apps.api_server.services.connectors.preview_outcomes import (
    ConnectorBrowsePreviewOutcome,
    deserialize_browse_outcome,
    deserialize_test_outcome,
    serialize_browse_outcome,
    serialize_test_outcome,
)
from apps.api_server.services.connectors.tester import ConnectorTestOutcome

T = TypeVar("T")


async def _run_distributed_inline_preview_once(  # noqa: UP047
    *,
    redis_client: DistributedPreviewRedisClient | None,
    operation: str,
    org_id: str,
    connector_type: str,
    config: dict[str, object],
    load: Callable[[], Awaitable[T]],
    serialize: Callable[[T], dict[str, object]],
    deserialize: Callable[[dict[str, object]], T],
    should_store: Callable[[T], bool] | None = None,
    result_ttl_seconds: int = (
        preview_cache_distributed_state._DISTRIBUTED_INLINE_PREVIEW_RESULT_TTL_SECONDS
    ),
) -> T:
    if redis_client is None:
        return await load()

    cache_key = _inline_preview_cache_key(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    deadline = (
        time.monotonic()
        + preview_cache_distributed_state._DISTRIBUTED_INLINE_PREVIEW_WAIT_TIMEOUT_SECONDS
    )

    while True:
        cached = await get_distributed_inline_preview_result(
            redis_client=redis_client,
            operation=operation,
            cache_key=cache_key,
            deserialize=deserialize,
        )
        if cached is not None:
            return cached

        acquired, token = await try_acquire_distributed_inline_preview_lock(
            redis_client=redis_client,
            operation=operation,
            cache_key=cache_key,
        )
        if acquired is None:
            return await load()
        if acquired and token is not None:
            stop_event = asyncio.Event()
            refresh_task = asyncio.create_task(
                refresh_distributed_inline_preview_lock_loop(
                    redis_client=redis_client,
                    operation=operation,
                    cache_key=cache_key,
                    token=token,
                    ttl_seconds=preview_cache_distributed_state._DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS,
                    stop_event=stop_event,
                )
            )
            try:
                result = await load()
                if should_store is None or should_store(result):
                    with suppress(Exception):
                        await put_distributed_inline_preview_result(
                            redis_client=redis_client,
                            operation=operation,
                            cache_key=cache_key,
                            payload=serialize(result),
                            ttl_seconds=result_ttl_seconds,
                        )
                return result
            finally:
                stop_event.set()
                with suppress(Exception):
                    await refresh_task
                await release_distributed_inline_preview_lock(
                    redis_client=redis_client,
                    operation=operation,
                    cache_key=cache_key,
                    token=token,
                )

        if time.monotonic() >= deadline:
            return await load()

        while time.monotonic() < deadline:
            cached = await get_distributed_inline_preview_result(
                redis_client=redis_client,
                operation=operation,
                cache_key=cache_key,
                deserialize=deserialize,
            )
            if cached is not None:
                return cached
            lock_exists = await distributed_inline_preview_lock_exists(
                redis_client=redis_client,
                operation=operation,
                cache_key=cache_key,
            )
            if lock_exists is None:
                return await load()
            if not lock_exists:
                break
            await asyncio.sleep(
                preview_cache_distributed_state._DISTRIBUTED_INLINE_PREVIEW_POLL_INTERVAL_SECONDS
            )

        if time.monotonic() >= deadline:
            return await load()


async def run_distributed_inline_preview_test_once(
    *,
    redis_client: DistributedPreviewRedisClient | None,
    org_id: str,
    connector_type: str,
    config: dict[str, object],
    load: Callable[[], Awaitable[ConnectorTestOutcome]],
) -> ConnectorTestOutcome:
    outcome = await _run_distributed_inline_preview_once(
        redis_client=redis_client,
        operation="test",
        org_id=org_id,
        connector_type=connector_type,
        config=config,
        load=load,
        serialize=serialize_test_outcome,
        deserialize=deserialize_test_outcome,
        should_store=lambda outcome: outcome.success,
    )
    if outcome.success:
        return put_cached_inline_preview_test_outcome(
            org_id=org_id,
            connector_type=connector_type,
            config=config,
            outcome=outcome,
        )
    return outcome


async def run_distributed_inline_preview_browse_once(
    *,
    redis_client: DistributedPreviewRedisClient | None,
    org_id: str,
    connector_type: str,
    config: dict[str, object],
    load: Callable[[], Awaitable[ConnectorBrowsePreviewOutcome]],
) -> ConnectorBrowsePreviewOutcome:
    outcome = await _run_distributed_inline_preview_once(
        redis_client=redis_client,
        operation="browse",
        org_id=org_id,
        connector_type=connector_type,
        config=config,
        load=load,
        serialize=serialize_browse_outcome,
        deserialize=deserialize_browse_outcome,
    )
    return put_cached_inline_preview_browse_outcome(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
        outcome=outcome,
    )


async def run_distributed_saved_connector_test_once(
    *,
    redis_client: DistributedPreviewRedisClient | None,
    org_id: str,
    connector_id: str,
    connector_type: str,
    config: dict[str, object],
    load: Callable[[], Awaitable[ConnectorTestOutcome]],
) -> ConnectorTestOutcome:
    return await _run_distributed_inline_preview_once(
        redis_client=redis_client,
        operation="saved_test",
        org_id=org_id,
        connector_type=connector_type,
        config={
            "connector_id": connector_id,
            "config": config,
        },
        load=load,
        serialize=serialize_test_outcome,
        deserialize=deserialize_test_outcome,
        should_store=lambda outcome: outcome.success,
        result_ttl_seconds=preview_cache_distributed_state._DISTRIBUTED_SAVED_CONNECTOR_RESULT_TTL_SECONDS,
    )


async def run_distributed_saved_connector_browse_once(
    *,
    redis_client: DistributedPreviewRedisClient | None,
    org_id: str,
    connector_id: str,
    connector_type: str,
    config: dict[str, object],
    load: Callable[[], Awaitable[ConnectorBrowsePreviewOutcome]],
) -> ConnectorBrowsePreviewOutcome:
    return await _run_distributed_inline_preview_once(
        redis_client=redis_client,
        operation="saved_browse",
        org_id=org_id,
        connector_type=connector_type,
        config={
            "connector_id": connector_id,
            "config": config,
        },
        load=load,
        serialize=serialize_browse_outcome,
        deserialize=deserialize_browse_outcome,
        result_ttl_seconds=preview_cache_distributed_state._DISTRIBUTED_SAVED_CONNECTOR_RESULT_TTL_SECONDS,
    )


__all__ = [
    "run_distributed_inline_preview_browse_once",
    "run_distributed_inline_preview_test_once",
    "run_distributed_saved_connector_browse_once",
    "run_distributed_saved_connector_test_once",
]
