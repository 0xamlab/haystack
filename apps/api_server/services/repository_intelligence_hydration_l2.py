"""Wave-C PR-4: an OPT-IN L2 Redis cache behind the in-process L1 hydration LRU.

The hydration index (grouped symbols / dependencies / symbol_references for a snapshot) is memoized
in the small in-process LRU in ``repository_intelligence_manifest_reader``. That L1 cache only helps
a warm process; a cold process (restart, or evicted from the 6-entry LRU) re-reads the Parquet and
re-groups it. This module adds an optional L2 keyed by the SAME content-hash cache key, so a cold
process can fetch a grouped index a sibling/prior process already built and skip the Parquet
read+group entirely.

This is the most MARGINAL of the Wave-C slices and is **off by default**:

* B8 already materializes the Parquet locally on a cold replica, so L2 only saves the parse+group
  CPU, not a network fetch of the data. The L1 LRU already covers the warm case.
* The hydrator is synchronous and runs inline on the async request path (same blocking class as the
  existing local Parquet read). A Redis round-trip has worse tail latency than a local read, so the
  client uses SHORT socket timeouts and a circuit breaker, and the whole layer FAILS OPEN — any L2
  error degrades to the normal Parquet path. Large indexes are not pushed through Redis.

Presence-gated on ``ALGENTA_HYDRATION_L2=redis`` (default unset → every function is a no-op), so it
is purely an operator lever and never a hard new dependency. When unset, single-process behavior is
byte-identical to before this module existed.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_KEY_PREFIX = "ri:hydration:v1:"
_ENTRY_TTL_SECONDS = 24 * 60 * 60
# The exact top-level shape a grouped hydration index must have; a decoded value missing any of these
# is treated as a miss (the consumer indexes these keys unguarded on the request path).
_INDEX_KEYS = frozenset({"symbols", "dependencies", "symbol_references"})
# Don't push very large grouped indexes through Redis — the round-trip would lose to a local Parquet
# read, and we don't want to bloat Redis. (Serialized JSON size of the grouped index.)
_MAX_INDEX_BYTES = 4 * 1024 * 1024
# Circuit breaker: after N consecutive faults, stop calling Redis for a cooldown so a slow/down
# backend can't keep adding latency to the (synchronous, on-request) hydration path.
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_COOLDOWN_SECONDS = 30.0

Index = dict[str, dict[str, list[dict[str, Any]]]]


def hydration_l2_mode() -> str:
    return (os.environ.get("ALGENTA_HYDRATION_L2") or "off").strip().lower()


def hydration_l2_enabled() -> bool:
    """True only when the L2 is explicitly opted in AND a redis_url is configured."""
    if hydration_l2_mode() != "redis":
        return False
    from apps.api_server.config import get_settings

    return bool((get_settings().redis_url or "").strip())


_redis_singleton: Any | None = None
_redis_resolved = False
_consecutive_failures = 0
_circuit_open_until = 0.0


def _get_redis() -> Any | None:
    """Lazily build a process-global SYNC Redis client, or None when the L2 is disabled / a client
    can't be constructed. Short socket timeouts bound the inline blocking on the hydration path.
    Never raises — a construction error degrades to None (the caller uses the Parquet path)."""
    global _redis_singleton, _redis_resolved
    if _redis_resolved:
        return _redis_singleton
    _redis_resolved = True
    if not hydration_l2_enabled():
        _redis_singleton = None
        return None
    try:
        import redis as sync_redis

        from apps.api_server.config import get_settings

        _redis_singleton = sync_redis.from_url(
            get_settings().redis_url,
            decode_responses=False,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    except Exception as exc:  # noqa: BLE001 — degrade to the Parquet path, never crash
        logger.warning("ri_hydration_l2_unavailable", error=str(exc))
        _redis_singleton = None
    return _redis_singleton


def _circuit_open() -> bool:
    return time.monotonic() < _circuit_open_until


def _record_failure() -> None:
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures += 1
    if _consecutive_failures >= _CIRCUIT_FAILURE_THRESHOLD:
        _circuit_open_until = time.monotonic() + _CIRCUIT_COOLDOWN_SECONDS


def _record_success() -> None:
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures = 0
    _circuit_open_until = 0.0


def _redis_key(cache_key: tuple[str, ...]) -> str:
    return _KEY_PREFIX + ":".join(cache_key)


def get_index(cache_key: tuple[str, ...]) -> Index | None:
    """Best-effort L2 read of a grouped hydration index (None when disabled / miss / any fault)."""
    if not hydration_l2_enabled() or _circuit_open():
        return None
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(_redis_key(cache_key))
        _record_success()
    except Exception as exc:  # noqa: BLE001 — fail open to the Parquet path
        logger.debug("ri_hydration_l2_get_degraded", error=str(exc))
        _record_failure()
        return None
    if raw is None:
        return None
    try:
        decoded = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — a corrupt entry is just a miss
        logger.debug("ri_hydration_l2_decode_degraded", error=str(exc))
        return None
    # Structure-validate before handing it to the (unguarded) consumer: a value that decodes as JSON
    # but is not the expected {symbols,dependencies,symbol_references} dict — a foreign entry under a
    # shared key namespace, a future writer, a poisoned key — would otherwise KeyError/TypeError in
    # hydrate_snapshot_manifest on the live request path. Treat any wrong shape as a miss (fail open).
    if not (isinstance(decoded, dict) and _INDEX_KEYS <= decoded.keys()):
        logger.debug("ri_hydration_l2_shape_degraded", keys=list(decoded) if isinstance(decoded, dict) else type(decoded).__name__)
        return None
    return decoded


def put_index(cache_key: tuple[str, ...], index: Index) -> None:
    """Best-effort L2 write of a freshly-grouped index. Skips oversized indexes; never raises."""
    if not hydration_l2_enabled() or _circuit_open():
        return
    client = _get_redis()
    if client is None:
        return
    try:
        serialized = json.dumps(index).encode("utf-8")
    except Exception as exc:  # noqa: BLE001 — non-serializable index: skip silently
        logger.debug("ri_hydration_l2_encode_degraded", error=str(exc))
        return
    if len(serialized) > _MAX_INDEX_BYTES:
        logger.debug("ri_hydration_l2_skip_oversized", bytes=len(serialized))
        return
    try:
        client.set(_redis_key(cache_key), serialized, ex=_ENTRY_TTL_SECONDS)
        _record_success()
    except Exception as exc:  # noqa: BLE001 — fail open; the index is still cached in L1
        logger.debug("ri_hydration_l2_set_degraded", error=str(exc))
        _record_failure()


def reset_hydration_l2_for_test() -> None:
    """Drop the process-global client + circuit-breaker state (test/maintenance hook)."""
    global _redis_singleton, _redis_resolved, _consecutive_failures, _circuit_open_until
    _redis_singleton = None
    _redis_resolved = False
    _consecutive_failures = 0
    _circuit_open_until = 0.0
