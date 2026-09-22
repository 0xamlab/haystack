"""algenta_spaces.ratelimit — token buckets with a fake clock, request keys."""

from __future__ import annotations

import threading

import pytest
from algenta_spaces import ratelimit


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_bucket_capacity_refill_and_retry_after():
    clock = Clock()
    bucket = ratelimit.TokenBucket(capacity=3, refill_per_s=1.0, clock=clock)
    assert [bucket.try_acquire("a") for _ in range(3)] == [True, True, True]
    assert bucket.try_acquire("a") is False
    assert bucket.remaining("a") == 0
    assert bucket.retry_after("a") == pytest.approx(1.0)
    assert bucket.retry_after("a", tokens=3) == pytest.approx(3.0)
    clock.now = 0.5
    assert bucket.try_acquire("a") is False
    assert bucket.retry_after("a") == pytest.approx(0.5)
    clock.now = 1.0
    assert bucket.try_acquire("a") is True
    assert bucket.retry_after("a") == pytest.approx(1.0)
    # a full idle period refills to capacity and never beyond
    clock.now = 100.0
    assert bucket.remaining("a") == 3
    assert bucket.retry_after("a", tokens=3) == 0.0
    assert [bucket.try_acquire("a") for _ in range(4)] == [True, True, True, False]


def test_buckets_are_per_key_and_a_failed_acquire_leaves_tokens_untouched():
    clock = Clock()
    bucket = ratelimit.TokenBucket(capacity=2, refill_per_s=10.0, clock=clock)
    assert bucket.try_acquire("a") and bucket.try_acquire("a")
    assert bucket.try_acquire("b")
    assert bucket.try_acquire("a") is False
    assert bucket.remaining("b") == 1
    assert bucket.try_acquire("b", tokens=2) is False
    assert bucket.remaining("b") == 1
    assert len(bucket) == 2


def test_prune_drops_idle_keys():
    clock = Clock()
    bucket = ratelimit.TokenBucket(capacity=1, refill_per_s=1.0, clock=clock)
    bucket.try_acquire("old")
    clock.now = 50.0
    bucket.try_acquire("new")
    assert bucket.prune(idle_s=30.0) == 1
    assert len(bucket) == 1
    assert bucket.prune(idle_s=30.0) == 0


def test_bucket_validation():
    with pytest.raises(ValueError):
        ratelimit.TokenBucket(0, 1.0)
    with pytest.raises(ValueError):
        ratelimit.TokenBucket(1, 0.0)
    bucket = ratelimit.TokenBucket(2, 1.0, clock=Clock())
    with pytest.raises(ValueError):
        bucket.try_acquire("a", tokens=3)
    with pytest.raises(ValueError):
        bucket.retry_after("a", tokens=0)


def test_bucket_is_thread_safe():
    clock = Clock()
    bucket = ratelimit.TokenBucket(capacity=100, refill_per_s=0.001, clock=clock)
    granted = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(50):
            ok = bucket.try_acquire("shared")
            with lock:
                granted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(granted) == 100
    assert len(granted) == 400


def test_key_from_request_header_precedence_and_ports():
    assert ratelimit.key_from_request({"X-Forwarded-For": "203.0.113.9, 10.0.0.1"}) == "203.0.113.9"
    assert ratelimit.key_from_request({"x-forwarded-for": "203.0.113.9:4123"}) == "203.0.113.9"
    assert ratelimit.key_from_request({"x-forwarded-for": "[2001:db8::1]:443"}) == "2001:db8::1"
    assert ratelimit.key_from_request({"x-forwarded-for": "2001:db8::1"}) == "2001:db8::1"
    assert ratelimit.key_from_request({"x-real-ip": "198.51.100.7"}) == "198.51.100.7"
    assert (
        ratelimit.key_from_request({"x-forwarded-for": " , "}, client_host="127.0.0.1:5000")
        == "127.0.0.1"
    )
    assert ratelimit.key_from_request({}, client_host="192.0.2.4") == "192.0.2.4"
    assert ratelimit.key_from_request({}) == "anonymous"
    assert ratelimit.key_from_request({}, fallback="session") == "session"
