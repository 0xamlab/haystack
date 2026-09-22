"""Cost-abuse limits for the public lanes: per-visitor buckets, daily caps, size caps as data.

A `Policy` names lanes (`governed`, `agent`, `generation` by default) and gives
each a `LanePolicy`: a burst per window for one visitor key, a per-key daily
allowance, an org-wide daily cap shared by every visitor, and the size caps the
UI enforces before a request is built (`max_tokens`, `max_prompt_chars`). The
numbers here are the plan's launch values; a Space passes its own `Policy` to
change them — nothing is read from the environment.

`Limits.check(key, kind)` is check-and-take: an allowed call is counted the
moment it is allowed, in one lock, so two concurrent visitors cannot both
squeeze through the last slot. The answer is a `Decision` with `allowed`, a
`retry_after_s` the UI can show and one `reason` sentence. Bursts use the
package's `TokenBucket`; daily counters live behind the `CounterStore`
protocol — `MemoryStore` by default, the Dataset-backed writer later — keyed by
UTC date so they roll over at midnight without a timer.

`key_from_request` builds the visitor key from the proxy headers (via
`ratelimit.key_from_request`) plus the Gradio session hash, so two tabs of one
visitor share a budget and one NAT does not starve a whole office.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from . import ratelimit

SECONDS_PER_DAY = 86_400
DEFAULT_LANE = "governed"


@dataclass(frozen=True)
class LanePolicy:
    """The limits of one lane. `daily_cap` is org-wide; `per_day` is per visitor key."""

    burst: int
    window_s: float
    per_day: int
    daily_cap: int
    max_tokens: int | None = None
    max_prompt_chars: int | None = None

    def __post_init__(self) -> None:
        if self.burst < 1:
            raise ValueError("burst must be at least 1")
        if self.window_s <= 0:
            raise ValueError("window_s must be positive")
        if self.per_day < 1 or self.daily_cap < 1:
            raise ValueError("per_day and daily_cap must be at least 1")
        if self.per_day > self.daily_cap:
            raise ValueError("per_day cannot exceed the org-wide daily_cap")
        for name in ("max_tokens", "max_prompt_chars"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"{name} must be at least 1 when set")


@dataclass(frozen=True)
class Policy:
    lanes: Mapping[str, LanePolicy]

    def __post_init__(self) -> None:
        if not self.lanes:
            raise ValueError("a policy needs at least one lane")
        object.__setattr__(self, "lanes", dict(self.lanes))

    def lane(self, kind: str) -> LanePolicy:
        try:
            return self.lanes[kind]
        except KeyError:
            raise KeyError(f"unknown lane {kind!r}; expected one of {sorted(self.lanes)}") from None


# Launch values from the plan: 10 governed calls a minute and 60 a day per visitor, 2,000 a
# day for the shared demo tenant; 10 agent turns per 10 minutes, 60 a day, 320 output tokens;
# 6 generations a minute on the GPU stage, 60 a day, 3,000 a day for the whole Space.
DEFAULT_POLICY = Policy(
    {
        "governed": LanePolicy(burst=10, window_s=60.0, per_day=60, daily_cap=2_000),
        "agent": LanePolicy(
            burst=10,
            window_s=600.0,
            per_day=60,
            daily_cap=3_000,
            max_tokens=320,
            max_prompt_chars=10_000,
        ),
        "generation": LanePolicy(
            burst=6, window_s=60.0, per_day=60, daily_cap=3_000, max_tokens=256
        ),
    }
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_s: float
    reason: str
    remaining_today: int
    org_remaining_today: int


class CounterStore(Protocol):
    """Daily counters. `incr` returns the new value; `get` returns 0 for an unknown counter."""

    def get(self, name: str, day: str) -> int: ...

    def incr(self, name: str, day: str, amount: int = 1) -> int: ...


class MemoryStore:
    """In-process counters; forgets every day but the current one on each write."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str], int] = {}

    def get(self, name: str, day: str) -> int:
        with self._lock:
            return self._counts.get((name, day), 0)

    def incr(self, name: str, day: str, amount: int = 1) -> int:
        with self._lock:
            value = self._counts.get((name, day), 0) + amount
            self._counts[(name, day)] = value
            stale = [k for k in self._counts if k[1] != day]
            for k in stale:
                del self._counts[k]
            return value

    def __len__(self) -> int:
        with self._lock:
            return len(self._counts)


def utc_day(now: float) -> str:
    """`2026-09-22` for a POSIX timestamp."""
    return datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d")


def seconds_to_midnight(now: float) -> float:
    """Seconds from `now` to the next 00:00 UTC (never zero)."""
    moment = datetime.fromtimestamp(now, UTC)
    midnight = (moment + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1.0, (midnight - moment).total_seconds())


def key_from_request(
    headers: Mapping[str, str], *, client_host: str = "", session_hash: str = ""
) -> str:
    """`<ip>|<session>` — the visitor address from the proxy headers plus the Gradio session."""
    address = ratelimit.key_from_request(headers, client_host=client_host)
    session = session_hash.strip() or "-"
    return f"{address}|{session}"


class Limits:
    """Per-visitor bursts, per-visitor and org-wide daily caps, size caps as data."""

    def __init__(
        self,
        policy: Policy = DEFAULT_POLICY,
        *,
        store: CounterStore | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.policy = policy
        self._store: CounterStore = MemoryStore() if store is None else store
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets = {
            kind: ratelimit.TokenBucket(
                lane.burst, lane.burst / lane.window_s, clock=self._monotonic
            )
            for kind, lane in policy.lanes.items()
        }

    def _monotonic(self) -> float:
        # The bucket only needs a monotone clock; the injected wall clock serves both.
        return self._clock()

    def caps(self, kind: str) -> LanePolicy:
        """The lane's limits as data, for `max_tokens` and prompt-size checks in the UI."""
        return self.policy.lane(kind)

    def check(self, key: str, kind: str) -> Decision:
        """Allow and count one call for `key` on lane `kind`, or say when to retry."""
        if not key.strip():
            raise ValueError("key is empty")
        lane = self.policy.lane(kind)
        now = self._clock()
        day = utc_day(now)
        org_name = f"{kind}:org"
        key_name = f"{kind}:{key}"
        with self._lock:
            org_used = self._store.get(org_name, day)
            key_used = self._store.get(key_name, day)
            org_left = max(0, lane.daily_cap - org_used)
            key_left = max(0, lane.per_day - key_used)
            if org_left == 0:
                return Decision(
                    False,
                    seconds_to_midnight(now),
                    f"Today's {kind} allowance for this Space is used up; it resets at 00:00 UTC.",
                    key_left,
                    0,
                )
            if key_left == 0:
                return Decision(
                    False,
                    seconds_to_midnight(now),
                    f"Your {kind} allowance for today is used up; it resets at 00:00 UTC.",
                    0,
                    org_left,
                )
            bucket = self._buckets[kind]
            if not bucket.try_acquire(key):
                wait = bucket.retry_after(key)
                return Decision(
                    False,
                    wait,
                    f"Too many {kind} calls in a row; try again in {_fmt_wait(wait)}.",
                    key_left,
                    org_left,
                )
            self._store.incr(org_name, day)
            self._store.incr(key_name, day)
        return Decision(True, 0.0, "", key_left - 1, org_left - 1)

    def used_today(self, kind: str, key: str | None = None) -> int:
        """Calls counted today on `kind`, org-wide or for one visitor key."""
        day = utc_day(self._clock())
        name = f"{kind}:org" if key is None else f"{kind}:{key}"
        return self._store.get(name, day)

    def prune(self, idle_s: float = SECONDS_PER_DAY) -> int:
        """Drop visitor buckets idle for `idle_s`; the daily counters roll over on their own."""
        return sum(bucket.prune(idle_s) for bucket in self._buckets.values())


def _fmt_wait(seconds: float) -> str:
    whole = max(1, int(seconds + 0.999))
    if whole >= 3600:
        return f"{whole // 3600} h {whole % 3600 // 60} min"
    if whole >= 60:
        return f"{whole // 60} min {whole % 60} s"
    return f"{whole} s"
