from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from apps.api_server.services.connectors.preview_outcomes import (
    ConnectorBrowsePreviewOutcome,
    copy_browse_outcome,
)
from apps.api_server.services.connectors.tester import ConnectorTestOutcome

_INLINE_PREVIEW_TEST_CACHE_TTL_SECONDS = 5.0
_INLINE_PREVIEW_TEST_CACHE_MAX_ENTRIES = 256
_INLINE_PREVIEW_TEST_CACHE: OrderedDict[str, tuple[float, ConnectorTestOutcome]] = OrderedDict()
_INLINE_PREVIEW_TEST_CACHE_LOCK = Lock()

_INLINE_PREVIEW_BROWSE_CACHE_TTL_SECONDS = 5.0
_INLINE_PREVIEW_BROWSE_CACHE_MAX_ENTRIES = 256
_INLINE_PREVIEW_BROWSE_CACHE: OrderedDict[str, tuple[float, ConnectorBrowsePreviewOutcome]] = (
    OrderedDict()
)
_INLINE_PREVIEW_BROWSE_CACHE_LOCK = Lock()


@dataclass
class _InlinePreviewInFlightEntry:
    event: asyncio.Event
    result: Any | None = None
    error: Exception | None = None


_INLINE_PREVIEW_IN_FLIGHT_LOCK = Lock()
_INLINE_PREVIEW_IN_FLIGHT: dict[str, _InlinePreviewInFlightEntry] = {}


def _inline_preview_cache_key(
    *,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
) -> str:
    canonical_payload = json.dumps(
        {
            "org_id": org_id,
            "connector_type": connector_type,
            "config": config,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _inline_preview_inflight_key(
    *,
    operation: str,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
) -> str:
    cache_key = _inline_preview_cache_key(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    return f"{operation}:{cache_key}"


def _get_cached_preview_value(
    *,
    cache: OrderedDict[str, tuple[float, Any]],
    lock: Lock,
    cache_key: str,
) -> Any | None:
    now = time.monotonic()
    with lock:
        cached = cache.get(cache_key)
        if cached is None:
            return None
        expires_at, value = cached
        if expires_at <= now:
            cache.pop(cache_key, None)
            return None
        cache.move_to_end(cache_key)
        return value


def _put_cached_preview_value(
    *,
    cache: OrderedDict[str, tuple[float, Any]],
    lock: Lock,
    cache_key: str,
    value: Any,
    ttl_seconds: float,
    max_entries: int,
) -> Any:
    expires_at = time.monotonic() + ttl_seconds
    with lock:
        cache.pop(cache_key, None)
        cache[cache_key] = (expires_at, value)
        while len(cache) > max_entries:
            cache.popitem(last=False)
    return value


async def run_inline_preview_once(
    *,
    operation: str,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
    load: Callable[[], Awaitable[Any]],
) -> Any:
    inflight_key = _inline_preview_inflight_key(
        operation=operation,
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    with _INLINE_PREVIEW_IN_FLIGHT_LOCK:
        entry = _INLINE_PREVIEW_IN_FLIGHT.get(inflight_key)
        owner = entry is None
        if owner:
            entry = _InlinePreviewInFlightEntry(event=asyncio.Event())
            _INLINE_PREVIEW_IN_FLIGHT[inflight_key] = entry
    assert entry is not None

    if not owner:
        await entry.event.wait()
        if entry.error is not None:
            raise entry.error
        return entry.result

    try:
        result = await load()
        entry.result = result
        return result
    except Exception as exc:
        entry.error = exc
        raise
    finally:
        entry.event.set()
        with _INLINE_PREVIEW_IN_FLIGHT_LOCK:
            current = _INLINE_PREVIEW_IN_FLIGHT.get(inflight_key)
            if current is entry:
                _INLINE_PREVIEW_IN_FLIGHT.pop(inflight_key, None)


def get_cached_inline_preview_test_outcome(
    *,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
) -> ConnectorTestOutcome | None:
    cache_key = _inline_preview_cache_key(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    cached = _get_cached_preview_value(
        cache=_INLINE_PREVIEW_TEST_CACHE,
        lock=_INLINE_PREVIEW_TEST_CACHE_LOCK,
        cache_key=cache_key,
    )
    return cached if isinstance(cached, ConnectorTestOutcome) else None


def put_cached_inline_preview_test_outcome(
    *,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
    outcome: ConnectorTestOutcome,
) -> ConnectorTestOutcome:
    cache_key = _inline_preview_cache_key(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    cached = _put_cached_preview_value(
        cache=_INLINE_PREVIEW_TEST_CACHE,
        lock=_INLINE_PREVIEW_TEST_CACHE_LOCK,
        cache_key=cache_key,
        value=outcome,
        ttl_seconds=_INLINE_PREVIEW_TEST_CACHE_TTL_SECONDS,
        max_entries=_INLINE_PREVIEW_TEST_CACHE_MAX_ENTRIES,
    )
    return cached if isinstance(cached, ConnectorTestOutcome) else outcome


def get_cached_inline_preview_browse_outcome(
    *,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
) -> ConnectorBrowsePreviewOutcome | None:
    cache_key = _inline_preview_cache_key(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    cached = _get_cached_preview_value(
        cache=_INLINE_PREVIEW_BROWSE_CACHE,
        lock=_INLINE_PREVIEW_BROWSE_CACHE_LOCK,
        cache_key=cache_key,
    )
    if not isinstance(cached, ConnectorBrowsePreviewOutcome):
        return None
    return copy_browse_outcome(cached)


def put_cached_inline_preview_browse_outcome(
    *,
    org_id: str,
    connector_type: str,
    config: dict[str, Any],
    outcome: ConnectorBrowsePreviewOutcome,
) -> ConnectorBrowsePreviewOutcome:
    cache_key = _inline_preview_cache_key(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    cached = _put_cached_preview_value(
        cache=_INLINE_PREVIEW_BROWSE_CACHE,
        lock=_INLINE_PREVIEW_BROWSE_CACHE_LOCK,
        cache_key=cache_key,
        value=copy_browse_outcome(outcome),
        ttl_seconds=_INLINE_PREVIEW_BROWSE_CACHE_TTL_SECONDS,
        max_entries=_INLINE_PREVIEW_BROWSE_CACHE_MAX_ENTRIES,
    )
    if not isinstance(cached, ConnectorBrowsePreviewOutcome):
        return outcome
    return copy_browse_outcome(cached)


def clear_inline_preview_test_cache() -> None:
    with _INLINE_PREVIEW_TEST_CACHE_LOCK:
        _INLINE_PREVIEW_TEST_CACHE.clear()


def clear_inline_preview_browse_cache() -> None:
    with _INLINE_PREVIEW_BROWSE_CACHE_LOCK:
        _INLINE_PREVIEW_BROWSE_CACHE.clear()


def clear_inline_preview_inflight() -> None:
    with _INLINE_PREVIEW_IN_FLIGHT_LOCK:
        _INLINE_PREVIEW_IN_FLIGHT.clear()


__all__ = [
    "clear_inline_preview_browse_cache",
    "clear_inline_preview_inflight",
    "clear_inline_preview_test_cache",
    "get_cached_inline_preview_browse_outcome",
    "get_cached_inline_preview_test_outcome",
    "put_cached_inline_preview_browse_outcome",
    "put_cached_inline_preview_test_outcome",
    "run_inline_preview_once",
]
