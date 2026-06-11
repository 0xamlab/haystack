"""Wave B8 migration: the triage (workspace-evidence-bundle) manifest through the object store.

Triage is hydration-free + deterministic, so it gets the FULL cross-replica treatment: a
mirror-on-write at the graph-workflow write site and a local-first/object-store-fallback read in
the storage loader. The read fallback (shared by the later decision-plan/patch-impact/simulation
loaders) distinguishes a genuine miss (existing 404) from an availability fault (retryable 503),
and never consults the store in local mode."""

from __future__ import annotations

import json

import pytest

from apps.api_server.services import repository_intelligence_graph_workflow as graph
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_storage as storage
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_REF = "ebr1"
_TRIAGE_KEY = obj.artifact_key(org_id="o", repository_id="r", kind="triage", artifact_id=_REF)
_TRIAGE_MANIFEST = {
    "repository_id": "r",
    "snapshot_id": "s1",
    "workspace_evidence_bundle_ref": _REF,
    "suspect_files": ["a.py"],
    "evidence_items": [],
}


def _load() -> dict:
    return storage._load_triage_manifest(org_id="o", repository_id="r", evidence_bundle_ref=_REF)


# --- write side ---------------------------------------------------------------------------------


def test_mirror_triage_is_noop_in_local_mode(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    key = graph._mirror_triage_manifest_to_object_store(
        org_id="o", repository_id="r", evidence_bundle_ref=_REF, manifest=_TRIAGE_MANIFEST
    )
    assert key is None


def test_mirror_triage_writes_to_store_in_s3_mode(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)

    key = graph._mirror_triage_manifest_to_object_store(
        org_id="o", repository_id="r", evidence_bundle_ref=_REF, manifest=_TRIAGE_MANIFEST
    )

    assert key == _TRIAGE_KEY
    assert store.get_json(key) == _TRIAGE_MANIFEST


def test_mirror_triage_fails_closed_when_store_write_raises(monkeypatch):
    class _Boom:
        def put_json(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())

    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        graph._mirror_triage_manifest_to_object_store(
            org_id="o", repository_id="r", evidence_bundle_ref=_REF, manifest=_TRIAGE_MANIFEST
        )
    assert excinfo.value.code == "triage_manifest_persist_failed"
    assert excinfo.value.status_code == 502


# --- read side ----------------------------------------------------------------------------------


def test_load_triage_uses_local_file_without_consulting_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_triage_dir", lambda org_id, repository_id: tmp_path)
    (tmp_path / f"{_REF}.json").write_text(json.dumps(_TRIAGE_MANIFEST))

    def _must_not_consult():
        raise AssertionError("object store must not be consulted when the local file exists")

    monkeypatch.setattr(obj, "get_object_store", _must_not_consult)
    assert _load() == _TRIAGE_MANIFEST


def test_load_triage_recovers_from_store_when_local_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_triage_dir", lambda org_id, repository_id: tmp_path / "absent")
    store = obj.LocalFsBackend(tmp_path / "store")
    store.put_json(_TRIAGE_KEY, _TRIAGE_MANIFEST)
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)

    assert _load() == _TRIAGE_MANIFEST


def test_load_triage_missing_object_raises_existing_404_not_410(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_triage_dir", lambda org_id, repository_id: tmp_path / "absent")
    store = obj.LocalFsBackend(tmp_path / "store")  # empty
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)

    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 404  # NOT 410 — the re-derived key can't prove prior existence
    assert excinfo.value.code == "workspace_evidence_bundle_not_found"


def test_load_triage_local_mode_404_without_consulting_store(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_triage_dir", lambda org_id, repository_id: tmp_path / "absent")
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)  # local mode

    def _must_not_consult():
        raise AssertionError("object store must not be consulted in local mode")

    monkeypatch.setattr(obj, "get_object_store", _must_not_consult)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "workspace_evidence_bundle_not_found"


def test_load_triage_store_unavailable_raises_retryable_503(monkeypatch, tmp_path):
    from apps.api_server.services.storage_service import ResultStorageUnavailableError

    monkeypatch.setattr(storage, "_triage_dir", lambda org_id, repository_id: tmp_path / "absent")

    class _Unavailable:
        def get_json(self, key):
            raise ResultStorageUnavailableError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Unavailable())

    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 503  # retryable — NOT 404/410
    assert excinfo.value.code == "triage_manifest_store_unavailable"


def test_triage_object_and_local_round_trip_equal(monkeypatch, tmp_path):
    """The durable object and the on-disk file decode to identical dicts (both writers use
    json.dumps(indent=2, sort_keys=True))."""
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    key = graph._mirror_triage_manifest_to_object_store(
        org_id="o", repository_id="r", evidence_bundle_ref=_REF, manifest=_TRIAGE_MANIFEST
    )
    local = tmp_path / f"{_REF}.json"
    local.write_text(json.dumps(_TRIAGE_MANIFEST, indent=2, sort_keys=True))
    assert store.get_json(key) == json.loads(local.read_text())
