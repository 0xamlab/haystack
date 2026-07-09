"""Offline enforcement of active_node_limit — the runtime node_broker (L1 device-binding + L2 peer census).

No hardware, no network: a dict-backed fake Redis implements the atomic census; node identity + time are
injected. Proves the fail-CLOSED semantics that stop one self-host license from running across a fleet.
"""
from __future__ import annotations

import pytest

from apps.runtime import coordination, node_broker
from apps.runtime.node_broker import (
    NodeAdmissionError,
    assert_node_binding,
    assert_node_census,
)

THUMB = "ed25519:THIS-NODE"
OTHER = "ed25519:OTHER-NODE"


class _FakeRedis:
    """Minimal async Redis for the census ZSET; eval() reimplements the admit Lua semantics atomically."""

    def __init__(self) -> None:
        self.z: dict[str, dict[str, float]] = {}

    def _zset(self, key: str) -> dict[str, float]:
        return self.z.setdefault(key, {})

    async def eval(self, script, numkeys, *args):  # noqa: ANN001
        key, member, now, window, limit = args[0], args[1], float(args[2]), float(args[3]), int(args[4])
        z = self._zset(key)
        for m in [m for m, s in z.items() if s <= now - window]:  # prune stale
            del z[m]
        if member in z:  # refresh — never evict a live member
            z[member] = now
            return 1
        if len(z) < limit:
            z[member] = now
            return 1
        return 0

    async def zremrangebyscore(self, key, lo, hi):  # noqa: ANN001
        z = self._zset(key)
        for m in [m for m, s in z.items() if s <= float(hi)]:
            del z[m]
        return 1

    async def zcard(self, key):  # noqa: ANN001
        return len(self._zset(key))

    async def zrem(self, key, member):  # noqa: ANN001
        return int(self._zset(key).pop(member, None) is not None)


class _RaisingRedis:
    async def eval(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("redis down")


class _Lic:
    def __init__(self, *, node_limit=0, thumbprint="", license_id="lic-1"):  # noqa: ANN001
        self._nl = node_limit
        self.device_pubkey_thumbprint = thumbprint
        self.license_id = license_id

    def node_limit(self) -> int:
        return self._nl


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    node_broker.reset_node_broker()
    coordination.reset_runtime_coordination_for_test()
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: THUMB)
    yield
    node_broker.reset_node_broker()
    coordination.reset_runtime_coordination_for_test()


def _use_redis(monkeypatch, redis):  # noqa: ANN001
    monkeypatch.setattr(coordination, "get_runtime_coordination_redis", lambda: redis)
    monkeypatch.setenv("ALGENTA_ENFORCE_PEER_NODE_CAP", "1")


# ── L1 device-binding (sync, air-gap-safe) ─────────────────────────────────────────
def test_l1_dark_when_not_enforcing_or_limit_zero() -> None:
    assert_node_binding(_Lic(node_limit=1, thumbprint=OTHER), enforcing=False)  # dark → no raise
    assert_node_binding(_Lic(node_limit=0, thumbprint=OTHER), enforcing=True)   # limit 0 → no raise


def test_l1_bound_match_boots() -> None:
    assert_node_binding(_Lic(node_limit=1, thumbprint=THUMB), enforcing=True)  # this machine == bound node


def test_l1_bound_mismatch_fails_closed() -> None:
    with pytest.raises(NodeAdmissionError, match="not the licensed node"):
        assert_node_binding(_Lic(node_limit=1, thumbprint=OTHER), enforcing=True)


def test_l1_unbound_is_noop_here() -> None:
    assert_node_binding(_Lic(node_limit=3, thumbprint=""), enforcing=True)  # census (L2) handles unbound


def test_l1_identity_unavailable_fails_closed_only_when_enforcing(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("no keypair")

    monkeypatch.setattr(node_broker, "resolve_node_identity", _boom)
    with pytest.raises(NodeAdmissionError, match="device identity unavailable"):
        assert_node_binding(_Lic(node_limit=1, thumbprint=THUMB), enforcing=True)
    assert_node_binding(_Lic(node_limit=1, thumbprint=THUMB), enforcing=False)  # dark → swallowed


# ── L2 peer census (async) ─────────────────────────────────────────────────────────
async def test_l2_dark_without_peer_flag(monkeypatch) -> None:
    monkeypatch.setattr(coordination, "get_runtime_coordination_redis", lambda: _FakeRedis())
    monkeypatch.delenv("ALGENTA_ENFORCE_PEER_NODE_CAP", raising=False)
    assert await assert_node_census(_Lic(node_limit=1, license_id="l"), enforcing=True) is None


async def test_l2_admits_up_to_n_then_blocks(monkeypatch) -> None:
    redis = _FakeRedis()
    _use_redis(monkeypatch, redis)
    lic = _Lic(node_limit=2, thumbprint="", license_id="cluster")
    # node A
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:A")
    assert await assert_node_census(lic, enforcing=True, now=1000.0) == "ed25519:A"
    # node B
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:B")
    assert await assert_node_census(lic, enforcing=True, now=1000.0) == "ed25519:B"
    # node C — over the cap of 2
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:C")
    with pytest.raises(NodeAdmissionError, match="active node limit reached"):
        await assert_node_census(lic, enforcing=True, now=1000.0)


async def test_l2_never_evicts_existing_member(monkeypatch) -> None:
    redis = _FakeRedis()
    _use_redis(monkeypatch, redis)
    lic = _Lic(node_limit=1, thumbprint="", license_id="c")
    assert await assert_node_census(lic, enforcing=True, now=1000.0) == THUMB
    # same node re-admits at full capacity (heartbeat / restart) — refreshed, not blocked
    assert await assert_node_census(lic, enforcing=True, now=1001.0) == THUMB


async def test_l2_colocated_replicas_count_as_one_node(monkeypatch) -> None:
    redis = _FakeRedis()
    _use_redis(monkeypatch, redis)
    lic = _Lic(node_limit=1, thumbprint="", license_id="c")
    # two replicas on one machine share the key → same thumbprint → one census slot
    assert await assert_node_census(lic, enforcing=True, now=1000.0) == THUMB
    assert await assert_node_census(lic, enforcing=True, now=1000.0) == THUMB
    assert await coordination.census_count(redis, "c", now=1000.0, window=600) == 1


async def test_l2_stale_member_pruned_frees_a_slot(monkeypatch) -> None:
    redis = _FakeRedis()
    _use_redis(monkeypatch, redis)
    lic = _Lic(node_limit=1, thumbprint="", license_id="c")
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:OLD")
    assert await assert_node_census(lic, enforcing=True, now=1000.0) == "ed25519:OLD"
    # much later, the old node is stale (beyond the window) → a new node admits
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:NEW")
    assert await assert_node_census(lic, enforcing=True, now=1_000_000.0) == "ed25519:NEW"
    assert await coordination.census_count(redis, "c", now=1_000_000.0, window=600) == 1


async def test_l2_last_slot_is_atomic(monkeypatch) -> None:
    redis = _FakeRedis()
    _use_redis(monkeypatch, redis)
    lic = _Lic(node_limit=2, thumbprint="", license_id="c")
    await redis.eval(coordination._CENSUS_ADMIT_LUA, 1, "algenta:nodecap:v1:census:c", "ed25519:X", "1000", "600", "2")
    # one slot left; two distinct new nodes contend → exactly one wins
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:A")
    await assert_node_census(lic, enforcing=True, now=1000.0)
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:B")
    with pytest.raises(NodeAdmissionError):
        await assert_node_census(lic, enforcing=True, now=1000.0)


async def test_l2_no_backend_bound_boots_unbound_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(coordination, "get_runtime_coordination_redis", lambda: None)
    monkeypatch.setenv("ALGENTA_ENFORCE_PEER_NODE_CAP", "1")
    # bound token: L1 already authorized this exact machine → boots even with no census backend
    assert await assert_node_census(_Lic(node_limit=1, thumbprint=THUMB, license_id="c"), enforcing=True) is None
    # unbound token with a finite pool + no way to count → fail closed
    with pytest.raises(NodeAdmissionError, match="requires a coordination backend"):
        await assert_node_census(_Lic(node_limit=3, thumbprint="", license_id="c"), enforcing=True)


async def test_l2_census_error_bound_boots_unbound_fails_closed(monkeypatch) -> None:
    _use_redis(monkeypatch, _RaisingRedis())
    assert await assert_node_census(_Lic(node_limit=1, thumbprint=THUMB, license_id="c"), enforcing=True) is None
    with pytest.raises(NodeAdmissionError, match="census unavailable"):
        await assert_node_census(_Lic(node_limit=3, thumbprint="", license_id="c"), enforcing=True)


# ── window derivation ───────────────────────────────────────────────────────────────
def test_window_seconds_floor_and_override(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_NODE_CAP_WINDOW_SECONDS", raising=False)
    assert node_broker._window_seconds() == node_broker._DEFAULT_WINDOW_SECONDS
    monkeypatch.setenv("ALGENTA_NODE_CAP_WINDOW_SECONDS", "5")
    assert node_broker._window_seconds() == 120  # floored so a missed heartbeat never evicts a live node
    monkeypatch.setenv("ALGENTA_NODE_CAP_WINDOW_SECONDS", "3600")
    assert node_broker._window_seconds() == 3600
    assert node_broker._heartbeat_interval(3600) == 1200
