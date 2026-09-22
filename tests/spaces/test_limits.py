"""algenta_spaces.limits — bursts, daily caps and size caps with a fake clock and store."""

from __future__ import annotations

import pytest
from _rules import _assert_clean_copy
from algenta_spaces import limits
from algenta_spaces.limits import DEFAULT_POLICY, LanePolicy, Limits, MemoryStore, Policy

NOON = 1_790_000_000.0  # 2026-09-21 11:33:20 UTC


class Clock:
    def __init__(self, now: float = NOON) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class RecordingStore:
    """A `CounterStore` that logs every call, for the Dataset writer's contract."""

    def __init__(self) -> None:
        self.inner = MemoryStore()
        self.log: list[tuple[str, str, str]] = []

    def get(self, name: str, day: str) -> int:
        self.log.append(("get", name, day))
        return self.inner.get(name, day)

    def incr(self, name: str, day: str, amount: int = 1) -> int:
        self.log.append(("incr", name, day))
        return self.inner.incr(name, day, amount)


def small(**overrides: int | float) -> Policy:
    lane = {"burst": 2, "window_s": 10.0, "per_day": 3, "daily_cap": 5}
    lane.update(overrides)
    return Policy({"governed": LanePolicy(**lane)})


def test_default_policy_matches_the_plan():
    gov = DEFAULT_POLICY.lane("governed")
    assert (gov.burst, gov.window_s, gov.per_day, gov.daily_cap) == (10, 60.0, 60, 2_000)
    agent = DEFAULT_POLICY.lane("agent")
    assert (agent.burst, agent.window_s, agent.per_day, agent.daily_cap) == (10, 600.0, 60, 3_000)
    assert (agent.max_tokens, agent.max_prompt_chars) == (320, 10_000)
    gen = DEFAULT_POLICY.lane("generation")
    assert (gen.burst, gen.per_day, gen.daily_cap, gen.max_tokens) == (6, 60, 3_000, 256)
    with pytest.raises(KeyError, match="unknown lane"):
        DEFAULT_POLICY.lane("nope")


def test_policy_validation():
    with pytest.raises(ValueError):
        LanePolicy(burst=0, window_s=60, per_day=1, daily_cap=1)
    with pytest.raises(ValueError):
        LanePolicy(burst=1, window_s=0, per_day=1, daily_cap=1)
    with pytest.raises(ValueError):
        LanePolicy(burst=1, window_s=60, per_day=0, daily_cap=1)
    with pytest.raises(ValueError, match="per_day cannot exceed"):
        LanePolicy(burst=1, window_s=60, per_day=5, daily_cap=4)
    with pytest.raises(ValueError, match="max_tokens"):
        LanePolicy(burst=1, window_s=60, per_day=1, daily_cap=1, max_tokens=0)
    with pytest.raises(ValueError):
        Policy({})


def test_burst_then_retry_after_from_the_bucket():
    clock = Clock()
    lim = Limits(small(), clock=clock)
    first = lim.check("1.2.3.4|s", "governed")
    assert first.allowed and first.retry_after_s == 0.0 and first.reason == ""
    assert (first.remaining_today, first.org_remaining_today) == (2, 4)
    assert lim.check("1.2.3.4|s", "governed").allowed
    third = lim.check("1.2.3.4|s", "governed")
    assert not third.allowed
    assert third.retry_after_s == pytest.approx(5.0)  # 2 tokens per 10 s → one every 5 s
    assert "try again in 5 s" in third.reason
    _assert_clean_copy(third.reason)
    assert lim.used_today("governed", "1.2.3.4|s") == 2
    clock.now += 5.0
    assert lim.check("1.2.3.4|s", "governed").allowed
    # a denied burst does not count towards the day
    assert lim.used_today("governed", "1.2.3.4|s") == 3


def test_per_key_daily_allowance_resets_at_utc_midnight():
    clock = Clock()
    lim = Limits(small(burst=10), clock=clock)
    assert [lim.check("k", "governed").allowed for _ in range(3)] == [True, True, True]
    denied = lim.check("k", "governed")
    assert not denied.allowed
    assert denied.remaining_today == 0
    assert denied.retry_after_s == pytest.approx(limits.seconds_to_midnight(NOON))
    assert "resets at 00:00 UTC" in denied.reason
    _assert_clean_copy(denied.reason)
    assert lim.check("other", "governed").allowed  # another visitor is unaffected
    clock.now += denied.retry_after_s
    assert limits.utc_day(clock.now) != limits.utc_day(NOON)
    again = lim.check("k", "governed")
    assert again.allowed and again.remaining_today == 2


def test_org_cap_is_shared_by_every_visitor_and_checked_first():
    clock = Clock()
    lim = Limits(small(burst=10, per_day=5, daily_cap=5), clock=clock)
    for key in ("a", "b", "c", "d", "e"):
        assert lim.check(key, "governed").allowed
    assert lim.used_today("governed") == 5
    denied = lim.check("fresh", "governed")
    assert not denied.allowed
    assert denied.org_remaining_today == 0
    assert denied.remaining_today == 5  # the visitor's own allowance is untouched
    assert "for this Space is used up" in denied.reason
    _assert_clean_copy(denied.reason)
    assert lim.used_today("governed") == 5  # denials are not counted


def test_a_fresh_visitor_gets_the_full_burst_but_never_more_than_the_day_allows():
    lim = Limits(small(burst=4, per_day=2, daily_cap=9), clock=Clock())
    results = [lim.check("k", "governed").allowed for _ in range(4)]
    assert results == [True, True, False, False]


def test_counters_go_through_the_injected_store_keyed_by_utc_day():
    store = RecordingStore()
    clock = Clock()
    lim = Limits(small(), store=store, clock=clock)
    assert lim.check("v", "governed").allowed
    day = limits.utc_day(NOON)
    assert store.log == [
        ("get", "governed:org", day),
        ("get", "governed:v", day),
        ("incr", "governed:org", day),
        ("incr", "governed:v", day),
    ]
    assert store.inner.get("governed:org", day) == 1


def test_memory_store_forgets_earlier_days_on_write():
    store = MemoryStore()
    assert store.get("x", "2026-09-21") == 0
    assert store.incr("x", "2026-09-21") == 1
    assert store.incr("x", "2026-09-21", 2) == 3
    assert len(store) == 1
    assert store.incr("x", "2026-09-22") == 1
    assert store.get("x", "2026-09-21") == 0
    assert len(store) == 1


def test_utc_day_and_seconds_to_midnight():
    assert limits.utc_day(NOON) == "2026-09-21"
    to_midnight = limits.seconds_to_midnight(NOON)
    assert 0 < to_midnight <= 86_400
    assert limits.utc_day(NOON + to_midnight) == "2026-09-22"
    assert limits.utc_day(NOON + to_midnight - 1) == "2026-09-21"
    # exactly at midnight the next reset is a full day away, never zero
    midnight = NOON + to_midnight
    assert limits.seconds_to_midnight(midnight) == pytest.approx(86_400)


def test_key_from_request_combines_the_forwarded_address_and_the_session():
    headers = {"X-Forwarded-For": "203.0.113.9:4432, 10.0.0.1", "x-real-ip": "10.0.0.2"}
    assert limits.key_from_request(headers, session_hash="abc") == "203.0.113.9|abc"
    assert limits.key_from_request({}, client_host="[2001:db8::1]:443") == "2001:db8::1|-"
    assert limits.key_from_request({}, session_hash="  ") == "anonymous|-"


def test_caps_are_data_and_unknown_lanes_or_empty_keys_are_errors():
    lim = Limits(clock=Clock())
    assert lim.caps("agent").max_tokens == 320
    assert lim.caps("governed").max_tokens is None
    with pytest.raises(KeyError):
        lim.check("k", "nope")
    with pytest.raises(ValueError):
        lim.check("  ", "governed")


def test_prune_drops_idle_buckets_only():
    clock = Clock()
    lim = Limits(small(), clock=clock)
    lim.check("old", "governed")
    clock.now += 100.0
    lim.check("new", "governed")
    assert lim.prune(idle_s=50.0) == 1
    assert lim.prune(idle_s=50.0) == 0
    assert lim.used_today("governed") == 2  # counters are not pruned


def test_wait_text_scales_to_minutes_and_hours():
    clock = Clock()
    lim = Limits(
        Policy({"g": LanePolicy(burst=1, window_s=7_200.0, per_day=9, daily_cap=9)}), clock=clock
    )
    assert lim.check("k", "g").allowed
    assert "try again in 2 h 0 min" in lim.check("k", "g").reason
    clock.now += 7_200.0 - 90.0
    assert "try again in 1 min 30 s" in lim.check("k", "g").reason
