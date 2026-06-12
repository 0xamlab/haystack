"""Wave-C perf-dedup: the DETERMINISTIC lookup index (snapshot/triage/simulation/graph_query)
through the durable object store.

Unlike the non-deterministic decision_plan_lookup (fail-CLOSED), these lookups are deterministic, so
the shared layer is pure BEST-EFFORT: a miss OR an availability fault both degrade to ``None`` (the
caller recomputes the identical result), and a failed mirror is swallowed. In local mode every call
is a no-op, so single-replica behavior is byte-identical. Redaction of the persisted payload must not
drop legitimate response fields (e.g. token estimates / resolved revisions)."""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_lookup_store as lookup_store
from apps.api_server.services import repository_intelligence_object_store as obj

_KINDS = ["snapshot_lookup", "triage_lookup", "simulation_lookup", "graph_query_lookup"]


class _FaultyBackend:
    """An object store whose every op raises an availability fault (not a genuine miss)."""

    def put_json(self, key, payload):  # noqa: ANN001
        raise ConnectionError("object store unavailable")

    def get_json(self, key):  # noqa: ANN001
        raise ConnectionError("object store unavailable")


def _use_s3(monkeypatch, backend) -> None:
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)


# --- local mode is a byte-identical no-op --------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
def test_read_is_none_in_local_mode(monkeypatch, kind):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    assert lookup_store.read_lookup_shared(
        org_id="o", repository_id="r", kind=kind, lookup_key="k"
    ) is None


@pytest.mark.parametrize("kind", _KINDS)
def test_mirror_is_noop_in_local_mode(monkeypatch, tmp_path, kind):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    store = obj.LocalFsBackend(tmp_path / "store")
    # In local mode the helper must not even consult the (s3) store — patch it to a faulty backend
    # to prove the no-op short-circuits before any object-store call.
    monkeypatch.setattr(obj, "get_object_store", lambda: _FaultyBackend())
    lookup_store.mirror_lookup(
        org_id="o", repository_id="r", kind=kind, lookup_key="k", payload={"response": {"x": 1}}
    )
    # Nothing was written to the real local-fs store either.
    assert store.get_json(obj.artifact_key(org_id="o", repository_id="r", kind=kind, artifact_id="k")) is None


# --- s3 mode: round-trip + key shape -------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
def test_mirror_then_read_round_trips_in_s3(monkeypatch, tmp_path, kind):
    store = obj.LocalFsBackend(tmp_path / "store")
    _use_s3(monkeypatch, store)
    payload = {"snapshot_id": "s1", "response": {"resolved_revision": "abc123", "ok": True}}

    lookup_store.mirror_lookup(
        org_id="o", repository_id="r", kind=kind, lookup_key="lk", payload=payload
    )
    # written under the kind-scoped, tenant-scoped artifact key
    expected_key = obj.artifact_key(org_id="o", repository_id="r", kind=kind, artifact_id="lk")
    assert store.get_json(expected_key) == payload
    # and read back through the helper
    assert lookup_store.read_lookup_shared(
        org_id="o", repository_id="r", kind=kind, lookup_key="lk"
    ) == payload


def test_read_returns_none_on_genuine_miss_in_s3(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    _use_s3(monkeypatch, store)
    assert lookup_store.read_lookup_shared(
        org_id="o", repository_id="r", kind="snapshot_lookup", lookup_key="absent"
    ) is None


# --- best-effort degradation: faults never propagate ---------------------------------------------


def test_read_degrades_to_none_on_availability_fault(monkeypatch):
    """A deterministic lookup recomputes on any object-store fault — the read must NOT propagate
    (contrast decision_plan_lookup, which fails closed)."""
    _use_s3(monkeypatch, _FaultyBackend())
    assert lookup_store.read_lookup_shared(
        org_id="o", repository_id="r", kind="simulation_lookup", lookup_key="k"
    ) is None


def test_mirror_swallows_write_fault(monkeypatch):
    """A failed mirror must never fail an otherwise-successful operation — a sibling just recomputes."""
    _use_s3(monkeypatch, _FaultyBackend())
    # must not raise
    lookup_store.mirror_lookup(
        org_id="o", repository_id="r", kind="triage_lookup", lookup_key="k", payload={"response": {}}
    )


# --- guard: the non-deterministic decision_plan_lookup may NOT use this best-effort path ----------


def test_decision_plan_lookup_kind_is_rejected():
    with pytest.raises(ValueError):
        lookup_store.read_lookup_shared(
            org_id="o", repository_id="r", kind="decision_plan_lookup", lookup_key="k"
        )
    with pytest.raises(ValueError):
        lookup_store.mirror_lookup(
            org_id="o", repository_id="r", kind="decision_plan_lookup", lookup_key="k", payload={}
        )


# --- redaction must not corrupt legitimate response fields ---------------------------------------


def test_redaction_preserves_legit_response_fields(monkeypatch, tmp_path):
    """put_json redacts secret-named keys; assert it does NOT strip/alter legitimate lookup fields
    such as token estimates, counts, ids, and resolved revisions."""
    store = obj.LocalFsBackend(tmp_path / "store")
    _use_s3(monkeypatch, store)
    payload = {
        "snapshot_id": "s1",
        "resolved_revision": "rev-abc",
        "response": {
            "raw_repo_token_estimate": 12345,
            "token_estimate": 678,
            "token_count": 90,
            "simulation_id": "sim-1",
            "decision_plan_id": "dp-1",
            "runs": 5000,
            "seed": 42,
            "resolved_revision": "rev-abc",
        },
    }
    lookup_store.mirror_lookup(
        org_id="o", repository_id="r", kind="simulation_lookup", lookup_key="lk", payload=payload
    )
    got = lookup_store.read_lookup_shared(
        org_id="o", repository_id="r", kind="simulation_lookup", lookup_key="lk"
    )
    assert got == payload, "redaction corrupted a legitimate deterministic-lookup field"
