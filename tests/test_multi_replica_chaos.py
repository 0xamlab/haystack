"""Wave-C PR-5 (C4): multi-replica chaos verification under a REAL Redis.

The unit tests use an in-memory FakeRedis; these run the ACTUAL coordination primitives against a
real Redis (the CI `redis:7-alpine` service / a local Redis) with genuinely concurrent execution —
the only way to prove the cross-replica race is closed. The cross-node lock lives IN Redis, so N
concurrent asyncio "replicas" contending on one real Redis exercise exactly the same mutual
exclusion N separate processes/containers would. Skips cleanly when no Redis is reachable.

Verifies: #94 (decision-plan dedup) — N concurrent replicas run the non-deterministic planner
EXACTLY once and all serve the SAME plan (no divergence); the run_once_distributed waiter under real
concurrency; and the fail-closed-when-the-lock-backend-is-down degrade (no silent divergent regen).
The full multi-CONTAINER harness (real HTTP/LB/worker) is infra/docker/docker-compose.replicas.yml,
for manual/operator chaos testing."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from apps.api_server.services.repository_intelligence_coordination import (
    CoordinationTimeout,
    coordinated_generation_lock,
    run_once_distributed,
)

REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
_REPLICAS = 6


@pytest.fixture
async def real_redis():
    try:
        import redis.asyncio as aioredis
    except Exception:  # noqa: BLE001
        pytest.skip("redis library unavailable")
    client = aioredis.from_url(
        REDIS_URL, encoding="utf-8", decode_responses=False,
        socket_connect_timeout=1, socket_timeout=3,
    )
    try:
        await client.ping()
    except Exception:  # noqa: BLE001
        pytest.skip("no Redis reachable for the multi-replica chaos suite")
    try:
        yield client
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass


async def test_concurrent_replicas_run_decision_plan_once_and_agree(real_redis):
    """The literal #94 scenario: N replicas race to generate a NON-deterministic decision plan,
    sharing one real Redis lock + one shared lookup. Exactly one planner runs; every replica serves
    the SAME plan (no divergent persisted plans)."""
    key = f"dp-{uuid.uuid4().hex}"  # unique namespace per run
    shared_lookup: dict[str, str] = {}  # stands in for the cross-replica object-store lookup
    generations = {"n": 0}

    async def replica(i: int) -> str:
        if "plan" in shared_lookup:  # fast path (pre-lock)
            return shared_lookup["plan"]
        async with coordinated_generation_lock(
            redis=real_redis, key=key, ttl_seconds=30, wait_timeout_seconds=20.0, deterministic=False
        ):
            if "plan" in shared_lookup:  # in-lock re-check — the loser serves the winner's plan
                return shared_lookup["plan"]
            await asyncio.sleep(0.15)  # the (non-deterministic) planner work
            generations["n"] += 1
            plan = f"plan-{i}-{uuid.uuid4().hex}"  # divergent if more than one replica generated
            shared_lookup["plan"] = plan  # publish to the shared lookup
            return plan

    results = await asyncio.gather(*(replica(i) for i in range(_REPLICAS)))
    assert generations["n"] == 1, "exactly ONE planner run across replicas"
    assert len(set(results)) == 1, "all replicas served the same plan — #94 divergence closed"


async def test_run_once_distributed_single_generation_under_real_concurrency(real_redis):
    key = f"ro-{uuid.uuid4().hex}"
    shared: dict[str, str] = {}
    generations = {"n": 0}

    async def load():
        return shared.get("v")

    async def generate():
        generations["n"] += 1
        await asyncio.sleep(0.15)
        return f"v-{uuid.uuid4().hex}"

    async def publish(r):
        shared["v"] = r

    results = await asyncio.gather(
        *(
            run_once_distributed(
                redis=real_redis, key=key, ttl_seconds=30, wait_timeout_seconds=20.0,
                deterministic=False, load=load, generate=generate, publish=publish,
            )
            for _ in range(_REPLICAS)
        )
    )
    assert generations["n"] == 1
    assert len(set(results)) == 1


async def test_lock_backend_down_fails_closed_without_divergence():
    """When the lock backend is unreachable mid-operation, the non-deterministic tier must FAIL
    CLOSED (no plan) rather than silently regenerate on a local no-op — preserving correctness over
    availability (a retry recovers once Redis is back). No real Redis needed."""

    class _DownRedis:
        async def set(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def get(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def eval(self, *args, **kwargs):
            raise ConnectionError("redis down")

    generations = {"n": 0}

    async def load():
        return None

    async def generate():
        generations["n"] += 1
        return "x"

    async def publish(r):
        pass

    with pytest.raises(CoordinationTimeout):
        await run_once_distributed(
            redis=_DownRedis(), key=f"down-{uuid.uuid4().hex}", ttl_seconds=5,
            wait_timeout_seconds=0.3, deterministic=False, load=load, generate=generate, publish=publish,
        )
    assert generations["n"] == 0  # never generated -> no divergent artifact while the backend is down
