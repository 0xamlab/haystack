"""Wave-C PR-0: the cross-node waiter lock (repository_intelligence_coordination).

run_once_distributed runs generate() at most once per key across replicas; losers WAIT and serve the
winner's published result. On a true wait-deadline it is tier-aware: deterministic falls through to
generate() (identical output), non-deterministic FAILS CLOSED (CoordinationTimeout). A lease lost
mid-generate aborts the non-deterministic holder rather than publishing a possibly-superseded
result. Presence-gated: default is single-process (no Redis); get_coordination_redis() returns None
unless ALGENTA_COORDINATION=redis."""

from __future__ import annotations

import asyncio

import pytest

from apps.api_server.services import repository_intelligence_coordination as coord
from apps.api_server.services.repository_intelligence_coordination import (
    CoordinationTimeout,
    coordinated_generation_lock,
    run_once_distributed,
)

_LOCK = "ri:coord:v1:lock:k"


class FakeRedis:
    """Minimal async Redis: SET NX EX, GET, and EVAL for the compare-and-{expire,delete} scripts."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, *, ex, nx=False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key):
        v = self.store.get(key)
        return v.encode() if isinstance(v, str) else v

    async def eval(self, script, numkeys, key, token, *args):
        cur = self.store.get(key)
        if cur == token:
            if "del" in script:
                self.store.pop(key, None)
            return 1
        return 0


class LeaseLostRedis(FakeRedis):
    async def eval(self, *args, **kwargs):  # every renewal/release "fails" the token compare
        return 0


async def _common(redis, *, deterministic, load, generate, publish, ttl=10, wait=1.0):
    return await run_once_distributed(
        redis=redis, key="k", ttl_seconds=ttl, wait_timeout_seconds=wait,
        deterministic=deterministic, load=load, generate=generate, publish=publish,
    )


async def test_winner_acquires_generates_publishes():
    redis = FakeRedis()
    state, calls = {}, {"gen": 0}

    async def load():
        return state.get("v")

    async def generate():
        calls["gen"] += 1
        return "RESULT"

    async def publish(r):
        state["v"] = r

    out = await _common(redis, deterministic=False, load=load, generate=generate, publish=publish)
    assert out == "RESULT"
    assert calls["gen"] == 1
    assert state["v"] == "RESULT"
    assert _LOCK not in redis.store  # released


async def test_existing_result_short_circuits_generate():
    redis = FakeRedis()

    async def load():
        return "PRE"

    async def generate():
        raise AssertionError("generate must not run when a result already exists")

    async def publish(r):
        raise AssertionError("publish must not run")

    assert await _common(redis, deterministic=False, load=load, generate=generate, publish=publish) == "PRE"


async def test_loser_waits_and_serves_winners_result():
    redis = FakeRedis()
    redis.store[_LOCK] = "foreign-token"  # another replica holds the lock
    calls = {"load": 0}

    async def load():
        calls["load"] += 1
        return "WINNER" if calls["load"] >= 2 else None  # winner publishes during our wait

    async def generate():
        raise AssertionError("loser must not generate")

    async def publish(r):
        raise AssertionError("loser must not publish")

    out = await _common(redis, deterministic=False, load=load, generate=generate, publish=publish, wait=2.0)
    assert out == "WINNER"


async def test_deterministic_timeout_falls_through_to_generate():
    redis = FakeRedis()
    redis.store[_LOCK] = "foreign-token"  # held forever; loser never sees a published result

    async def load():
        return None

    async def generate():
        return "FALLTHROUGH"

    async def publish(r):
        pass

    out = await _common(redis, deterministic=True, load=load, generate=generate, publish=publish, wait=0.2)
    assert out == "FALLTHROUGH"


async def test_nondeterministic_timeout_fails_closed():
    redis = FakeRedis()
    redis.store[_LOCK] = "foreign-token"

    async def load():
        return None

    async def generate():
        raise AssertionError("non-deterministic tier must NOT regenerate on timeout")

    async def publish(r):
        raise AssertionError("must not publish")

    with pytest.raises(CoordinationTimeout):
        await _common(redis, deterministic=False, load=load, generate=generate, publish=publish, wait=0.2)


async def test_holder_released_without_publishing_then_waiter_reacquires():
    redis = FakeRedis()
    redis.store[_LOCK] = "foreign-token"
    calls = {"load": 0, "gen": 0}

    async def load():
        calls["load"] += 1
        if calls["load"] == 2:
            redis.store.pop(_LOCK, None)  # holder "crashed" — lock gone, nothing published
        return None

    async def generate():
        calls["gen"] += 1
        return "REACQUIRED"

    async def publish(r):
        pass

    out = await _common(redis, deterministic=False, load=load, generate=generate, publish=publish, wait=2.0)
    assert out == "REACQUIRED"
    assert calls["gen"] == 1


async def test_lease_lost_during_generate_nondeterministic_fails_closed():
    redis = LeaseLostRedis()

    async def load():
        return None

    async def generate():
        await asyncio.sleep(0.4)  # > ttl/3 so a renewal fires and fails
        return "X"

    async def publish(r):
        raise AssertionError("must NOT publish after losing the lease (non-deterministic)")

    with pytest.raises(CoordinationTimeout):
        await _common(redis, deterministic=False, load=load, generate=generate, publish=publish, ttl=1, wait=2.0)


async def test_lease_lost_during_generate_deterministic_publishes_anyway():
    redis = LeaseLostRedis()
    state = {}

    async def load():
        return state.get("v")

    async def generate():
        await asyncio.sleep(0.4)
        return "DET"

    async def publish(r):
        state["v"] = r

    out = await _common(redis, deterministic=True, load=load, generate=generate, publish=publish, ttl=1, wait=2.0)
    assert out == "DET"
    assert state["v"] == "DET"  # deterministic output is identical, safe to publish


# --- presence signal ---------------------------------------------------------------------------


def test_coordination_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALGENTA_COORDINATION", raising=False)
    coord.reset_coordination_redis_for_test()
    assert coord.coordination_mode() == "local"
    assert coord.coordination_enabled() is False
    assert coord.get_coordination_redis() is None


def test_coordination_enabled_when_flag_set(monkeypatch):
    monkeypatch.setenv("ALGENTA_COORDINATION", "redis")
    coord.reset_coordination_redis_for_test()
    assert coord.coordination_enabled() is True  # redis_url defaults non-empty
    coord.reset_coordination_redis_for_test()


# --- coordinated_generation_lock (the blocking CM used by the decision-plan path) ---------------


async def test_generation_lock_serializes_concurrent_holders():
    redis = FakeRedis()
    inside = {"n": 0, "max": 0}

    async def worker():
        async with coordinated_generation_lock(
            redis=redis, key="k", ttl_seconds=10, wait_timeout_seconds=5.0, deterministic=False
        ):
            inside["n"] += 1
            inside["max"] = max(inside["max"], inside["n"])
            await asyncio.sleep(0.1)
            inside["n"] -= 1

    await asyncio.gather(worker(), worker())
    assert inside["max"] == 1  # never both inside the critical section at once


async def test_generation_lock_nondeterministic_timeout_fails_closed():
    redis = FakeRedis()
    redis.store[_LOCK] = "foreign-token"  # held by another replica, never released
    with pytest.raises(CoordinationTimeout):
        async with coordinated_generation_lock(
            redis=redis, key="k", ttl_seconds=10, wait_timeout_seconds=0.2, deterministic=False
        ):
            raise AssertionError("body must not run when the lock fails closed")


async def test_generation_lock_deterministic_timeout_proceeds_unlocked():
    redis = FakeRedis()
    redis.store[_LOCK] = "foreign-token"
    ran = {"v": False}
    async with coordinated_generation_lock(
        redis=redis, key="k", ttl_seconds=10, wait_timeout_seconds=0.2, deterministic=True
    ):
        ran["v"] = True
    assert ran["v"] is True  # deterministic tier proceeds best-effort on timeout


async def test_generation_lock_redis_none_uses_local_fallback():
    from contextlib import contextmanager

    used = {"v": False}

    @contextmanager
    def _fallback():
        used["v"] = True
        yield

    async with coordinated_generation_lock(
        redis=None, key="k", ttl_seconds=10, wait_timeout_seconds=1.0,
        deterministic=False, local_fallback=_fallback,
    ):
        pass
    assert used["v"] is True  # degraded to the caller's host-local flock


async def test_generation_lock_releases_after_block():
    redis = FakeRedis()
    async with coordinated_generation_lock(
        redis=redis, key="k", ttl_seconds=10, wait_timeout_seconds=1.0, deterministic=False
    ):
        assert _LOCK in redis.store  # held inside the block
    assert _LOCK not in redis.store  # released (atomic compare-and-delete) on exit
