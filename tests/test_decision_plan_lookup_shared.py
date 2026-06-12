"""Wave-C PR-W: the cross-replica decision-plan dedup lookup helpers.

The shared lookup (object store, s3 mode) is what lets a losing replica serve the winner's plan
instead of regenerating a divergent one. Local mode is a no-op (single-process flock path). The
mirror fails closed (the shared lookup IS the dedup mechanism); the read propagates availability
faults (never a fail-open that would diverge)."""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_decision_plan_workflow as dpw
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services.repository_intelligence_contracts import RepositoryIntelligenceError
from apps.api_server.services.storage_service import ResultStorageUnavailableError

_KEY = "dp_lookup_abc"
_PAYLOAD = {"decision_plan_id": "dp1", "response": {"recommended_action": "proceed"}}


def test_local_mode_mirror_is_noop_and_read_returns_none(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)

    def _boom():
        raise AssertionError("object store must not be consulted in local mode")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    dpw._mirror_decision_plan_lookup("o", "r", _KEY, _PAYLOAD)  # no-op
    assert dpw._read_decision_plan_lookup_shared("o", "r", _KEY) is None


def test_s3_mode_round_trips_cross_replica(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    dpw._mirror_decision_plan_lookup("o", "r", _KEY, _PAYLOAD)
    assert dpw._read_decision_plan_lookup_shared("o", "r", _KEY) == _PAYLOAD
    assert dpw._read_decision_plan_lookup_shared("o", "r", "other-key") is None  # genuine miss


def test_mirror_fails_closed_on_put_error(monkeypatch):
    class _Boom:
        def put_json(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        dpw._mirror_decision_plan_lookup("o", "r", _KEY, _PAYLOAD)
    assert excinfo.value.code == "decision_plan_lookup_persist_failed"
    assert excinfo.value.status_code == 502


def test_shared_read_propagates_availability_fault(monkeypatch):
    # an availability fault must NOT fail-open into a divergent regeneration — it propagates so the
    # caller fails closed and retries.
    class _Unavailable:
        def get_json(self, key):
            raise ResultStorageUnavailableError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Unavailable())
    with pytest.raises(ResultStorageUnavailableError):
        dpw._read_decision_plan_lookup_shared("o", "r", _KEY)
