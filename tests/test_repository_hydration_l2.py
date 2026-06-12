"""Wave-C PR-4: the OPT-IN L2 Redis hydration cache behind the in-process L1 LRU.

L2 is OFF by default (presence-gated on ALGENTA_HYDRATION_L2=redis) and FAILS OPEN — any Redis
miss/fault degrades to the normal Parquet path. A circuit breaker stops calling a slow/down backend
after a few faults, and oversized indexes are never pushed through Redis. When L2 holds a grouped
index, a cold process must serve it WITHOUT re-reading the Parquet."""

from __future__ import annotations

import json

import pytest

from apps.api_server.services import repository_intelligence_hydration_l2 as l2
from apps.api_server.services import repository_intelligence_manifest_reader as reader


class _FakeSyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.gets = 0
        self.sets = 0

    def get(self, key):  # noqa: ANN001
        self.gets += 1
        return self.store.get(key)

    def set(self, key, value, ex=None):  # noqa: ANN001
        self.sets += 1
        self.store[key] = value
        return True


class _FaultySyncRedis:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, key):  # noqa: ANN001
        self.calls += 1
        raise ConnectionError("redis down")

    def set(self, key, value, ex=None):  # noqa: ANN001
        self.calls += 1
        raise ConnectionError("redis down")


@pytest.fixture(autouse=True)
def _reset_l2():
    l2.reset_hydration_l2_for_test()
    yield
    l2.reset_hydration_l2_for_test()


def _enable(monkeypatch, client) -> None:
    monkeypatch.setattr(l2, "hydration_l2_enabled", lambda: True)
    monkeypatch.setattr(l2, "_get_redis", lambda: client)


_KEY = ("snap1", "h_sym", "h_dep", "h_ref")
_INDEX = {
    "symbols": {"a.py": [{"symbol_id": "s1", "symbol_name": "f", "start_line": 1, "end_line": 2}]},
    "dependencies": {"a.py": [{"dependency_edge_id": "d1", "target_file": "b.py"}]},
    "symbol_references": {"a.py": [{"source_symbol_id": "s1", "target_symbol_id": "s2"}]},
}


# --- default-off no-op ---------------------------------------------------------------------------


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALGENTA_HYDRATION_L2", raising=False)
    assert l2.hydration_l2_enabled() is False
    assert l2.get_index(_KEY) is None
    # put is a silent no-op; building a client is never attempted
    monkeypatch.setattr(l2, "_get_redis", lambda: (_ for _ in ()).throw(AssertionError("built!")))
    l2.put_index(_KEY, _INDEX)  # must not raise / must not build a client


# --- enabled round-trip ---------------------------------------------------------------------------


def test_put_then_get_round_trips(monkeypatch):
    fake = _FakeSyncRedis()
    _enable(monkeypatch, fake)
    l2.put_index(_KEY, _INDEX)
    assert fake.sets == 1
    got = l2.get_index(_KEY)
    assert got == _INDEX  # JSON round-trip preserves the grouped index exactly


def test_get_returns_none_on_miss(monkeypatch):
    _enable(monkeypatch, _FakeSyncRedis())
    assert l2.get_index(_KEY) is None


def test_corrupt_entry_is_treated_as_miss(monkeypatch):
    fake = _FakeSyncRedis()
    fake.store[l2._redis_key(_KEY)] = b"{not-json"
    _enable(monkeypatch, fake)
    assert l2.get_index(_KEY) is None


# --- fail-open + circuit breaker ------------------------------------------------------------------


def test_get_fails_open_on_fault(monkeypatch):
    _enable(monkeypatch, _FaultySyncRedis())
    assert l2.get_index(_KEY) is None  # must not raise


def test_put_swallows_fault(monkeypatch):
    _enable(monkeypatch, _FaultySyncRedis())
    l2.put_index(_KEY, _INDEX)  # must not raise


def test_circuit_opens_after_repeated_faults(monkeypatch):
    faulty = _FaultySyncRedis()
    _enable(monkeypatch, faulty)
    # Drive consecutive faults up to the threshold.
    for _ in range(l2._CIRCUIT_FAILURE_THRESHOLD):
        assert l2.get_index(_KEY) is None
    calls_after_open = faulty.calls
    assert calls_after_open == l2._CIRCUIT_FAILURE_THRESHOLD
    # Circuit is now open — further calls short-circuit WITHOUT touching Redis.
    assert l2.get_index(_KEY) is None
    assert l2.put_index(_KEY, _INDEX) is None
    assert faulty.calls == calls_after_open, "circuit-open calls must not hit Redis"


# --- oversized indexes are not pushed -------------------------------------------------------------


def test_put_skips_oversized_index(monkeypatch):
    fake = _FakeSyncRedis()
    _enable(monkeypatch, fake)
    monkeypatch.setattr(l2, "_MAX_INDEX_BYTES", 10)  # force "oversized"
    l2.put_index(_KEY, _INDEX)
    assert fake.sets == 0  # skipped, not written
    assert l2.get_index(_KEY) is None


# --- integration: an L2 hit skips the Parquet read ------------------------------------------------


def test_hydration_index_serves_l2_without_parquet_read(monkeypatch):
    """On an L1 miss + L2 hit, _hydration_index must serve the L2 index and NEVER touch _read_grouped
    (the Parquet path)."""
    reader.clear_hydration_cache()
    fake = _FakeSyncRedis()
    # pre-seed L2 with the grouped index for this manifest's content-hash key
    manifest = {
        "snapshot_id": "snap1",
        "symbol_graph_artifact": {"content_hash": "h_sym", "storage_path": "/nonexistent/sym"},
        "dependency_graph_artifact": {"content_hash": "h_dep", "storage_path": "/nonexistent/dep"},
        "symbol_reference_artifact": {"content_hash": "h_ref", "storage_path": "/nonexistent/ref"},
    }
    key = reader._cache_key(manifest)
    # The L2 key is prefixed with the projection-schema fingerprint (see #8 fix).
    l2_key = (reader._PROJECTION_FINGERPRINT, *key)
    fake.store[l2._redis_key(l2_key)] = json.dumps(_INDEX).encode("utf-8")
    _enable(monkeypatch, fake)

    def _boom(*args, **kwargs):
        raise AssertionError("_read_grouped must not run on an L2 hit")

    monkeypatch.setattr(reader, "_read_grouped", _boom)

    index = reader._hydration_index(manifest)
    assert index == _INDEX
    # and it was promoted into L1 (under the content-hash key, without the fingerprint prefix)
    assert reader._hydration_cache.get(key) == _INDEX
    reader.clear_hydration_cache()


def test_l2_key_includes_projection_fingerprint(monkeypatch):
    """A build that changes a projection key set must not read a sibling's old-shaped L2 entry: the
    L2 key folds in a fingerprint of the projection sets, so it rotates when the projection changes."""
    reader.clear_hydration_cache()
    manifest = {
        "snapshot_id": "snap1",
        "symbol_graph_artifact": {"content_hash": "h_sym", "storage_path": "/x/sym"},
        "dependency_graph_artifact": {"content_hash": "h_dep", "storage_path": "/x/dep"},
        "symbol_reference_artifact": {"content_hash": "h_ref", "storage_path": "/x/ref"},
    }
    key = reader._cache_key(manifest)
    fake = _FakeSyncRedis()
    _enable(monkeypatch, fake)
    # Seed under the OLD fingerprint (simulating an entry written by a different projection schema).
    fake.store[l2._redis_key(("oldfingerprint00", *key))] = json.dumps(_INDEX).encode("utf-8")

    calls = {"n": 0}

    def _count(*args, **kwargs):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(reader, "_read_grouped", _count)
    # Current build's fingerprint differs → the old-shaped entry is NOT served; Parquet path runs.
    reader._hydration_index(manifest)
    assert calls["n"] == 3, "a mismatched-projection L2 entry must not be served; recompute instead"
    reader.clear_hydration_cache()


# --- structure validation: a valid-JSON wrong-shape entry must fail open, not crash ---------------


@pytest.mark.parametrize("bad", [b"{}", b"[]", b"123", b'"x"', b'{"symbols": {}}'])
def test_wrong_shape_entry_is_treated_as_miss(monkeypatch, bad):
    """A value that decodes as JSON but is not a {symbols,dependencies,symbol_references} dict (a
    foreign/poisoned entry under a shared key) must be treated as a miss — never handed to the
    consumer, which would KeyError/TypeError on the request path."""
    fake = _FakeSyncRedis()
    fake.store[l2._redis_key(_KEY)] = bad
    _enable(monkeypatch, fake)
    assert l2.get_index(_KEY) is None
    reader.clear_hydration_cache()
