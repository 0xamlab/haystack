"""Per-key token buckets for the public endpoints, keyed by the visitor's address.

A bucket holds `capacity` tokens and refills continuously at `refill_per_s`.
Every acquisition is atomic under one lock; the clock is injectable so the
arithmetic is tested without waiting. `key_from_request` derives the key from
the proxy headers the Hub forwards (`x-forwarded-for` first hop, then
`x-real-ip`), falling back to the socket address.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

ANONYMOUS = "anonymous"


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucket:
    def __init__(
        self,
        capacity: int,
        refill_per_s: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if refill_per_s <= 0:
            raise ValueError("refill_per_s must be positive")
        self.capacity = capacity
        self.refill_per_s = float(refill_per_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}

    def _refilled(self, key: str, now: float) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(self.capacity), updated=now)
            self._buckets[key] = bucket
            return bucket
        elapsed = max(0.0, now - bucket.updated)
        bucket.tokens = min(float(self.capacity), bucket.tokens + elapsed * self.refill_per_s)
        bucket.updated = now
        return bucket

    def try_acquire(self, key: str, tokens: int = 1) -> bool:
        """Take `tokens` from `key`'s bucket if available; False leaves the bucket untouched."""
        if tokens < 1 or tokens > self.capacity:
            raise ValueError(f"tokens must be between 1 and {self.capacity}")
        with self._lock:
            bucket = self._refilled(key, self._clock())
            if bucket.tokens + 1e-9 >= tokens:
                bucket.tokens -= tokens
                return True
            return False

    def retry_after(self, key: str, tokens: int = 1) -> float:
        """Seconds until `tokens` will be available for `key` (0.0 when they already are)."""
        if tokens < 1 or tokens > self.capacity:
            raise ValueError(f"tokens must be between 1 and {self.capacity}")
        with self._lock:
            bucket = self._refilled(key, self._clock())
            missing = tokens - bucket.tokens
            return 0.0 if missing <= 0 else missing / self.refill_per_s

    def remaining(self, key: str) -> int:
        with self._lock:
            return int(self._refilled(key, self._clock()).tokens)

    def prune(self, idle_s: float) -> int:
        """Drop buckets untouched for `idle_s` seconds; returns how many were dropped."""
        now = self._clock()
        with self._lock:
            stale = [key for key, b in self._buckets.items() if now - b.updated >= idle_s]
            for key in stale:
                del self._buckets[key]
        return len(stale)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buckets)


def _strip_port(address: str) -> str:
    address = address.strip()
    if address.startswith("["):  # [ipv6]:port
        return address[1:].split("]", 1)[0]
    if address.count(":") == 1:  # ipv4:port
        return address.split(":", 1)[0]
    return address


def key_from_request(
    headers: Mapping[str, str], *, client_host: str = "", fallback: str = ANONYMOUS
) -> str:
    """The rate-limit key for one request: first forwarded hop, real ip, socket, fallback."""
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    forwarded = lowered.get("x-forwarded-for", "")
    if forwarded:
        first = _strip_port(forwarded.split(",", 1)[0])
        if first:
            return first
    real = _strip_port(lowered.get("x-real-ip", ""))
    if real:
        return real
    host = _strip_port(client_host)
    return host or fallback
