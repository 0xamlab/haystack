"""Wave B8 migration: the simulation manifest through the object store.

Hydration-free, so it gets mirror-on-write + a local-first/object-store-fallback read. The write
helper imports the object-store primitives directly (NOT the injected write_json the workflow uses
for the local write), and hoists the previously-inline manifest dict so the local write and the
mirror serialize the identical object. seed=None Monte-Carlo runs are manifest-durability-only
(non-deterministic -> no cross-replica dedup)."""

from __future__ import annotations

import json

import pytest

from apps.api_server.services import repository_intelligence_execution_workflow as ew
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_storage as storage
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.storage_service import ResultStorageUnavailableError

_SIM_ID = "sim-123"
_SIM_KEY = obj.artifact_key(org_id="o", repository_id="r", kind="simulations", artifact_id=_SIM_ID)
_SIM_MANIFEST = {"simulation_id": _SIM_ID, "snapshot_id": "s1", "apply_gate": "pass", "envelope": {}}


def _mirror(**kw):
    return ew._mirror_simulation_manifest_to_object_store(
        org_id="o", repository_id="r", simulation_id=_SIM_ID, manifest=_SIM_MANIFEST, **kw
    )


def _load():
    return storage._load_simulation_manifest(org_id="o", repository_id="r", simulation_id=_SIM_ID)


# --- write side ---------------------------------------------------------------------------------


def test_mirror_simulation_is_noop_in_local_mode(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    assert _mirror() is None


def test_mirror_simulation_writes_to_store_in_s3_mode(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    assert _mirror() == _SIM_KEY
    assert store.get_json(_SIM_KEY) == _SIM_MANIFEST


def test_mirror_simulation_fails_closed_when_store_write_raises(monkeypatch):
    class _Boom:
        def put_json(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _mirror()
    assert excinfo.value.code == "simulation_manifest_persist_failed"
    assert excinfo.value.status_code == 502


# --- read side ----------------------------------------------------------------------------------


def test_load_simulation_uses_local_without_consulting_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_simulations_dir", lambda o, r: tmp_path)
    (tmp_path / f"{_SIM_ID}.json").write_text(json.dumps(_SIM_MANIFEST))

    def _boom():
        raise AssertionError("store must not be consulted when the local file exists")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    assert _load() == _SIM_MANIFEST


def test_load_simulation_recovers_from_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_simulations_dir", lambda o, r: tmp_path / "absent")
    store = obj.LocalFsBackend(tmp_path / "store")
    store.put_json(_SIM_KEY, _SIM_MANIFEST)
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    assert _load() == _SIM_MANIFEST


def test_load_simulation_missing_object_raises_existing_404(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_simulations_dir", lambda o, r: tmp_path / "absent")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: obj.LocalFsBackend(tmp_path / "store"))
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "repository_simulation_not_found"


def test_load_simulation_local_mode_404_without_consulting_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_simulations_dir", lambda o, r: tmp_path / "absent")
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)

    def _boom():
        raise AssertionError("store must not be consulted in local mode")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "repository_simulation_not_found"


def test_load_simulation_store_unavailable_raises_503(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_simulations_dir", lambda o, r: tmp_path / "absent")

    class _Unavailable:
        def get_json(self, key):
            raise ResultStorageUnavailableError("down")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Unavailable())
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 503
    assert excinfo.value.code == "simulations_manifest_store_unavailable"
