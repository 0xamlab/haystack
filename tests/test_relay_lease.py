"""Algenta Relay lease ledger (apps/runtime/relay_lease.py) — the floating-pool enforcement.

Covers plan §9 Relay gates that live in the pool math: idempotent acquire (autoscale race-safe),
pool ceiling fail-closed, borrow-with-expiry reservation, TTL reclaim, never-evict-a-peer, and
the node-count safety ceiling. Deterministic ``now`` throughout.
"""
from __future__ import annotations

import pytest

from apps.runtime.relay_lease import LeaseError, LeaseLedger


def test_acquire_within_pool() -> None:
    led = LeaseLedger(max_units=64)
    le = led.acquire("node-a", 16, now=1000)
    assert le.granted_units == 16
    assert led.used_units(1000) == 16
    assert led.available_units(1000) == 48


def test_pool_ceiling_fails_closed() -> None:
    led = LeaseLedger(max_units=32)
    led.acquire("node-a", 24, now=0)
    with pytest.raises(LeaseError, match="pool exhausted"):
        led.acquire("node-b", 16, now=0)  # 24 + 16 > 32
    # the existing node is untouched (never evicted)
    assert led.used_units(0) == 24


def test_acquire_is_idempotent_no_double_count() -> None:
    led = LeaseLedger(max_units=32)
    led.acquire("node-a", 16, now=0)
    led.acquire("node-a", 16, now=1)  # retry / re-register — must NOT become 32
    assert led.used_units(2) == 16


def test_reacquire_can_change_grant_within_pool() -> None:
    led = LeaseLedger(max_units=32)
    led.acquire("node-a", 8, now=0)
    led.acquire("node-a", 20, now=1)  # scale up, replacing the old 8
    assert led.used_units(2) == 20


def test_reacquire_over_pool_excluding_self_rejected() -> None:
    led = LeaseLedger(max_units=32)
    led.acquire("node-a", 16, now=0)
    led.acquire("node-b", 16, now=0)  # pool full (32)
    with pytest.raises(LeaseError, match="pool exhausted"):
        led.acquire("node-a", 20, now=1)  # a(20) + b(16) = 36 > 32


def test_borrow_reserves_units_for_silent_node() -> None:
    led = LeaseLedger(max_units=16)
    led.acquire("node-a", 16, now=0, ttl=100, borrow=1000)
    # past TTL but within borrow window → units still reserved, pool still full
    assert led.used_units(200) == 16
    with pytest.raises(LeaseError):
        led.acquire("node-b", 16, now=200)


def test_units_reclaimed_after_borrow_window() -> None:
    led = LeaseLedger(max_units=16)
    led.acquire("node-a", 16, now=0, ttl=100, borrow=1000)
    # past both TTL and borrow → reclaimed; a new node can take the pool
    le = led.acquire("node-b", 16, now=2000)
    assert le.granted_units == 16
    assert led.used_units(2000) == 16


def test_renew_extends_without_changing_grant() -> None:
    led = LeaseLedger(max_units=16)
    led.acquire("node-a", 8, now=0, ttl=100, borrow=100)
    led.renew("node-a", now=90, ttl=100, borrow=100)  # heartbeat before expiry
    assert led.used_units(150) == 8  # still active well past the original expiry


def test_renew_unknown_node_raises() -> None:
    led = LeaseLedger(max_units=16)
    with pytest.raises(LeaseError, match="re-acquire"):
        led.renew("ghost", now=0)


def test_release_frees_immediately_ignoring_borrow() -> None:
    led = LeaseLedger(max_units=16)
    led.acquire("node-a", 16, now=0, ttl=100, borrow=10_000)
    led.release("node-a", now=5)
    assert led.used_units(5) == 0  # graceful give-back beats the borrow window
    led.acquire("node-b", 16, now=6)  # pool immediately reusable


def test_rolling_replacement_overlap_within_pool() -> None:
    # old + new pod briefly coexist; both fit → both admitted (no false over-cap during rollout)
    led = LeaseLedger(max_units=32)
    led.acquire("pod-old", 16, now=0)
    led.acquire("pod-new", 16, now=1)  # 32 total, fits
    assert led.used_units(2) == 32
    led.release("pod-old", now=3)  # old drains
    assert led.available_units(3) == 16


def test_node_ceiling_safety_cap() -> None:
    led = LeaseLedger(max_units=100, node_ceiling=2)
    led.acquire("a", 1, now=0)
    led.acquire("b", 1, now=0)
    with pytest.raises(LeaseError, match="node ceiling"):
        led.acquire("c", 1, now=0)


def test_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        LeaseLedger(max_units=0)
    led = LeaseLedger(max_units=8)
    with pytest.raises(LeaseError):
        led.acquire("", 4, now=0)
    with pytest.raises(LeaseError):
        led.acquire("a", 0, now=0)
