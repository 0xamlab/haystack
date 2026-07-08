from __future__ import annotations

import time
from collections.abc import Callable, MutableMapping
from datetime import UTC, datetime
from typing import Any

from algenta.runtime_connector_definitions import _inline_preview_capability_key
from algenta.runtime_errors import RuntimeValidationError

INLINE_PREVIEW_PREFIX = "algenta-inline-preview"
INLINE_PREVIEW_TTL_SECONDS = 300
INLINE_PREVIEW_RATE_LIMIT = 20
INLINE_PREVIEW_RATE_WINDOW_SECONDS = 60
INLINE_PREVIEW_CACHE_TTL_SECONDS = 5
INLINE_PREVIEW_CAPABILITY_TTL_SECONDS = 60


def consume_inline_preview_slot(
    events: list[float],
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> list[float]:
    now = now_monotonic()
    cutoff = now - INLINE_PREVIEW_RATE_WINDOW_SECONDS
    active_events = [stamp for stamp in events if stamp >= cutoff]
    if len(active_events) >= INLINE_PREVIEW_RATE_LIMIT:
        raise RuntimeValidationError(
            "inline_preview_rate_limited",
            (
                "Inline connector previews are rate limited. Create and reuse a saved "
                "connector for production workflows."
            ),
            {
                "limit": INLINE_PREVIEW_RATE_LIMIT,
                "window_seconds": INLINE_PREVIEW_RATE_WINDOW_SECONDS,
            },
        )
    active_events.append(now)
    return active_events


def inline_preview_description(
    *,
    connector_type: str,
    description: str | None,
    now_epoch: Callable[[], float] = time.time,
) -> tuple[str, float]:
    expires_at_epoch = now_epoch() + INLINE_PREVIEW_TTL_SECONDS
    expires_at = datetime.fromtimestamp(expires_at_epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = f"{INLINE_PREVIEW_PREFIX}:{connector_type}:expires_at={expires_at}"
    if description:
        return f"{prefix}\n{description}", expires_at_epoch
    return prefix, expires_at_epoch


def cleanup_inline_preview_cache(
    cache: MutableMapping[str, tuple[float, Any]],
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> None:
    now = now_monotonic()
    expired_keys = [
        cache_key for cache_key, (expires_at, _value) in cache.items() if expires_at <= now
    ]
    for cache_key in expired_keys:
        cache.pop(cache_key, None)


def get_inline_preview_cache(
    cache: MutableMapping[str, tuple[float, Any]],
    cache_key: str,
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> Any | None:
    cleanup_inline_preview_cache(cache, now_monotonic=now_monotonic)
    entry = cache.get(cache_key)
    if entry is None:
        return None
    _expires_at, value = entry
    return value


def put_inline_preview_cache(
    cache: MutableMapping[str, tuple[float, Any]],
    cache_key: str,
    value: Any,
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> Any:
    cache[cache_key] = (
        now_monotonic() + INLINE_PREVIEW_CACHE_TTL_SECONDS,
        value,
    )
    return value


def cleanup_inline_preview_capabilities(
    capabilities: MutableMapping[str, tuple[float, bool]],
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> None:
    now = now_monotonic()
    expired_operations = [
        operation
        for operation, (expires_at, _supported) in capabilities.items()
        if expires_at <= now
    ]
    for operation in expired_operations:
        capabilities.pop(operation, None)


def get_inline_preview_capability(
    capabilities: MutableMapping[str, tuple[float, bool]],
    *,
    operation: str,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> bool | None:
    cleanup_inline_preview_capabilities(capabilities, now_monotonic=now_monotonic)
    entry = capabilities.get(_inline_preview_capability_key(operation=operation))
    if entry is None:
        return None
    _expires_at, supported = entry
    return supported


def put_inline_preview_capability(
    capabilities: MutableMapping[str, tuple[float, bool]],
    *,
    operation: str,
    supported: bool,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> None:
    capabilities[_inline_preview_capability_key(operation=operation)] = (
        now_monotonic() + INLINE_PREVIEW_CAPABILITY_TTL_SECONDS,
        supported,
    )


__all__ = [
    "INLINE_PREVIEW_CACHE_TTL_SECONDS",
    "INLINE_PREVIEW_CAPABILITY_TTL_SECONDS",
    "INLINE_PREVIEW_PREFIX",
    "INLINE_PREVIEW_RATE_LIMIT",
    "INLINE_PREVIEW_RATE_WINDOW_SECONDS",
    "INLINE_PREVIEW_TTL_SECONDS",
    "cleanup_inline_preview_cache",
    "cleanup_inline_preview_capabilities",
    "consume_inline_preview_slot",
    "get_inline_preview_cache",
    "get_inline_preview_capability",
    "inline_preview_description",
    "put_inline_preview_cache",
    "put_inline_preview_capability",
]
