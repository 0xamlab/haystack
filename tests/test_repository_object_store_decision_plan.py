"""Wave B8 migration: the decision-plan + patch-impact manifests through the object store.

Both are hydration-free, so they get mirror-on-write + a local-first/object-store-fallback read
(via the shared storage._recover_manifest_from_object_store). The decision-plan mirror is
manifest-durability-only (non-deterministic planner -> no cross-replica dedup); patch-impact is a
deterministic recompute. The write helpers hoist their previously-inline manifest dicts so the
local write and the mirror serialize the identical in-memory object."""

from __future__ import annotations

import json

import pytest

from apps.api_server.services import repository_intelligence_decision_plan_workflow as dpw
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_storage as storage
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.storage_service import ResultStorageUnavailableError

_PLAN_ID = "plan-abc"
_PI_ID = "pi-xyz"
_PLAN_KEY = obj.artifact_key(org_id="o", repository_id="r", kind="decision_plans", artifact_id=_PLAN_ID)
_PI_KEY = obj.artifact_key(org_id="o", repository_id="r", kind="patch_impacts", artifact_id=_PI_ID)
_PLAN_MANIFEST = {"decision_plan_id": _PLAN_ID, "snapshot_id": "s1", "decision_plan": {"steps": []}}
_PI_MANIFEST = {"patch_impact_report_id": _PI_ID, "snapshot_id": "s1", "risk_score": 0.1, "records": []}


# --- write side ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mirror, ident_kwarg, ident_value, manifest, key, fail_code",
    [
        (dpw._mirror_decision_plan_manifest_to_object_store, "decision_plan_id", _PLAN_ID, _PLAN_MANIFEST, _PLAN_KEY, "decision_plan_manifest_persist_failed"),
        (dpw._mirror_patch_impact_manifest_to_object_store, "patch_impact_report_id", _PI_ID, _PI_MANIFEST, _PI_KEY, "patch_impact_manifest_persist_failed"),
    ],
)
def test_mirror_is_noop_in_local_mode(monkeypatch, mirror, ident_kwarg, ident_value, manifest, key, fail_code):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    assert mirror(org_id="o", repository_id="r", manifest=manifest, **{ident_kwarg: ident_value}) is None


@pytest.mark.parametrize(
    "mirror, ident_kwarg, ident_value, manifest, key, fail_code",
    [
        (dpw._mirror_decision_plan_manifest_to_object_store, "decision_plan_id", _PLAN_ID, _PLAN_MANIFEST, _PLAN_KEY, "decision_plan_manifest_persist_failed"),
        (dpw._mirror_patch_impact_manifest_to_object_store, "patch_impact_report_id", _PI_ID, _PI_MANIFEST, _PI_KEY, "patch_impact_manifest_persist_failed"),
    ],
)
def test_mirror_writes_to_store_in_s3_mode(monkeypatch, tmp_path, mirror, ident_kwarg, ident_value, manifest, key, fail_code):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    out = mirror(org_id="o", repository_id="r", manifest=manifest, **{ident_kwarg: ident_value})
    assert out == key
    assert store.get_json(key) == manifest


@pytest.mark.parametrize(
    "mirror, ident_kwarg, ident_value, manifest, key, fail_code",
    [
        (dpw._mirror_decision_plan_manifest_to_object_store, "decision_plan_id", _PLAN_ID, _PLAN_MANIFEST, _PLAN_KEY, "decision_plan_manifest_persist_failed"),
        (dpw._mirror_patch_impact_manifest_to_object_store, "patch_impact_report_id", _PI_ID, _PI_MANIFEST, _PI_KEY, "patch_impact_manifest_persist_failed"),
    ],
)
def test_mirror_fails_closed_when_store_write_raises(monkeypatch, mirror, ident_kwarg, ident_value, manifest, key, fail_code):
    class _Boom:
        def put_json(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        mirror(org_id="o", repository_id="r", manifest=manifest, **{ident_kwarg: ident_value})
    assert excinfo.value.code == fail_code
    assert excinfo.value.status_code == 502


# --- read side ----------------------------------------------------------------------------------


def _load_plan():
    return storage._load_decision_plan_manifest(org_id="o", repository_id="r", decision_plan_id=_PLAN_ID)


def _load_pi():
    return storage._load_patch_impact_manifest(org_id="o", repository_id="r", patch_impact_report_id=_PI_ID)


def test_load_decision_plan_uses_local_without_consulting_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_decision_plans_dir", lambda o, r: tmp_path)
    (tmp_path / f"{_PLAN_ID}.json").write_text(json.dumps(_PLAN_MANIFEST))

    def _boom():
        raise AssertionError("store must not be consulted when the local file exists")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    assert _load_plan() == _PLAN_MANIFEST


def test_load_decision_plan_recovers_from_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_decision_plans_dir", lambda o, r: tmp_path / "absent")
    store = obj.LocalFsBackend(tmp_path / "store")
    store.put_json(_PLAN_KEY, _PLAN_MANIFEST)
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    assert _load_plan() == _PLAN_MANIFEST


def test_load_decision_plan_missing_object_raises_existing_404(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_decision_plans_dir", lambda o, r: tmp_path / "absent")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: obj.LocalFsBackend(tmp_path / "store"))
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load_plan()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "decision_plan_not_found"


def test_load_decision_plan_store_unavailable_raises_503(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_decision_plans_dir", lambda o, r: tmp_path / "absent")

    class _Unavailable:
        def get_json(self, key):
            raise ResultStorageUnavailableError("down")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Unavailable())
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load_plan()
    assert excinfo.value.status_code == 503
    assert excinfo.value.code == "decision_plans_manifest_store_unavailable"


def test_load_patch_impact_recovers_from_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_patch_impact_dir", lambda o, r: tmp_path / "absent")
    store = obj.LocalFsBackend(tmp_path / "store")
    store.put_json(_PI_KEY, _PI_MANIFEST)
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    assert _load_pi() == _PI_MANIFEST


def test_load_patch_impact_missing_object_raises_existing_404(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_patch_impact_dir", lambda o, r: tmp_path / "absent")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: obj.LocalFsBackend(tmp_path / "store"))
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load_pi()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "patch_impact_report_not_found"


def test_load_patch_impact_local_mode_404_without_consulting_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_patch_impact_dir", lambda o, r: tmp_path / "absent")
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)

    def _boom():
        raise AssertionError("store must not be consulted in local mode")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load_pi()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "patch_impact_report_not_found"
