"""Wave B8 final slice (PR11f): cross-replica hydration of v2 snapshots through the object store.

On snapshot create the 5 Parquet artifacts are mirrored to the durable store (the exact in-memory
bytes that were hashed into the manifest, so the recovery-side sha256 check matches by
construction). On a manifest-recovery read, the 3 hydration-critical Parquet
(symbol_graph/dependency_graph/symbol_reference) are materialized node-locally — content-verified,
atomic temp-then-rename — and the manifest storage_path is rewritten to the local path before
hydrate (which does an UNGUARDED Parquet read). Every failure mode fails closed with a retryable
503; v1 / empty-files manifests short-circuit without any object read."""

from __future__ import annotations

import hashlib

import pytest

from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_snapshot_workflow as snap
from apps.api_server.services import repository_intelligence_storage as storage
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.runtime_internal_contracts import (
    DependencyGraphRecord,
    SymbolGraphRecord,
    SymbolReferenceRecord,
    parquet_bytes_from_records,
)
from apps.api_server.services.storage_service import ResultStorageUnavailableError

_ORG, _REPO, _SNAP = "o", "r", "snap1"

# Real (empty) Parquet for the 3 hydration record types — what hydrate_snapshot_manifest reads.
_SYMBOL_PARQUET = parquet_bytes_from_records([], record_type=SymbolGraphRecord)
_DEP_PARQUET = parquet_bytes_from_records([], record_type=DependencyGraphRecord)
_REF_PARQUET = parquet_bytes_from_records([], record_type=SymbolReferenceRecord)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshots_key() -> str:
    return obj.artifact_key(org_id=_ORG, repository_id=_REPO, kind="snapshots", artifact_id=_SNAP)


def _parquet_key(kind: str) -> str:
    return obj.artifact_key(org_id=_ORG, repository_id=_REPO, kind=kind, artifact_id=_SNAP)


def _paths(tmp_path):
    """A _snapshot_paths-shaped dict rooted under tmp_path (nothing exists yet)."""
    root = tmp_path / "snapshots" / _SNAP
    return {
        "dir": root,
        "manifest": root / "snapshot.json",
        "snapshot_parquet": root / "repository_snapshot.parquet",
        "repository_graph_parquet": root / "repository_graph.parquet",
        "symbol_graph_parquet": root / "symbol_graph.parquet",
        "dependency_graph_parquet": root / "dependency_graph.parquet",
        "symbol_reference_parquet": root / "symbol_reference.parquet",
    }


def _v2_manifest():
    """A slim v2 manifest with one file + the 3 hydration artifacts (content_hash matches the
    empty Parquet bytes above). storage_path points at an ORIGINAL-node path that won't exist on
    the recovering replica (forcing the rewrite)."""
    return {
        "manifest_version": 2,
        "snapshot_id": _SNAP,
        "files": [{"file_path": "a.py", "language": "python", "content_hash": "h"}],
        "symbol_graph_artifact": {"storage_path": "/original/symbol_graph.parquet", "content_hash": _sha(_SYMBOL_PARQUET)},
        "dependency_graph_artifact": {"storage_path": "/original/dependency_graph.parquet", "content_hash": _sha(_DEP_PARQUET)},
        "symbol_reference_artifact": {"storage_path": "/original/symbol_reference.parquet", "content_hash": _sha(_REF_PARQUET)},
    }


def _seed_store(*, with_parquet=True, manifest=None):
    backend = obj.LocalFsBackend(_seed_store.root)
    backend.put_json(_snapshots_key(), manifest if manifest is not None else _v2_manifest())
    if with_parquet:
        backend.put_bytes(_parquet_key("symbol_graph_parquet"), _SYMBOL_PARQUET)
        backend.put_bytes(_parquet_key("dependency_graph_parquet"), _DEP_PARQUET)
        backend.put_bytes(_parquet_key("symbol_reference_parquet"), _REF_PARQUET)
    return backend


@pytest.fixture
def s3_env(monkeypatch, tmp_path):
    """Patch object-store mode/backend + _snapshot_paths so the snapshot is ABSENT locally."""
    _seed_store.root = tmp_path / "store"
    paths = _paths(tmp_path)
    monkeypatch.setattr(storage, "_snapshot_paths", lambda o, r, s: paths)
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    return {"paths": paths, "tmp_path": tmp_path}


def _load():
    return storage._load_snapshot_manifest(org_id=_ORG, repository_id=_REPO, snapshot_id=_SNAP)


# --- write side ---------------------------------------------------------------------------------


def test_mirror_parquet_is_noop_in_local_mode(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)

    def _boom():
        raise AssertionError("store must not be consulted in local mode")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    # returns None and never touches the store
    assert snap._mirror_snapshot_parquet_to_object_store(
        org_id=_ORG, repository_id=_REPO, snapshot_id=_SNAP, parquet_by_kind={"snapshot_parquet": b"x"}
    ) is None


def test_mirror_parquet_writes_all_five_distinct_keys(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    by_kind = {
        "snapshot_parquet": b"a",
        "symbol_graph_parquet": b"b",
        "dependency_graph_parquet": b"c",
        "repository_graph_parquet": b"d",
        "symbol_reference_parquet": b"e",
    }
    snap._mirror_snapshot_parquet_to_object_store(
        org_id=_ORG, repository_id=_REPO, snapshot_id=_SNAP, parquet_by_kind=by_kind
    )
    keys = {kind: _parquet_key(kind) for kind in by_kind}
    # all distinct, and distinct from the manifest ('snapshots') + archive ('archives') keys
    archive_key = obj.artifact_key(org_id=_ORG, repository_id=_REPO, kind="archives", artifact_id=_SNAP)
    assert len(set(keys.values())) == 5
    assert _snapshots_key() not in keys.values() and archive_key not in keys.values()
    for kind, data in by_kind.items():
        assert store.get_bytes(keys[kind]) == data


def test_mirror_parquet_fails_closed_when_store_write_raises(monkeypatch):
    class _Boom:
        def put_bytes(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        snap._mirror_snapshot_parquet_to_object_store(
            org_id=_ORG, repository_id=_REPO, snapshot_id=_SNAP, parquet_by_kind={"snapshot_parquet": b"x"}
        )
    assert excinfo.value.code == "snapshot_parquet_persist_failed"
    assert excinfo.value.status_code == 502


# --- read side: cross-replica recovery ----------------------------------------------------------


def test_v2_cross_replica_recovery_materializes_and_hydrates(s3_env, monkeypatch):
    backend = _seed_store(with_parquet=True)
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)

    out = _load()

    # hydrated: the file entry gained the (empty) hydration arrays
    assert out["files"][0]["symbols"] == []
    assert out["files"][0]["dependencies"] == []
    assert out["files"][0]["symbol_references"] == []
    # the 3 hydration Parquet were materialized node-locally and storage_path rewritten to them
    for field, key in (
        ("symbol_graph_artifact", "symbol_graph_parquet"),
        ("dependency_graph_artifact", "dependency_graph_parquet"),
        ("symbol_reference_artifact", "symbol_reference_parquet"),
    ):
        local = s3_env["paths"][key]
        assert local.exists()
        assert out[field]["storage_path"] == str(local)


def test_recovery_is_idempotent_and_reuses_local_parquet(s3_env, monkeypatch):
    backend = _seed_store(with_parquet=True)
    calls = {"parquet": 0}
    real_get = backend.get_bytes
    snapshots_key = _snapshots_key()

    def _counting_get(key):
        # count only Parquet fetches (the manifest recovery also goes through get_bytes via get_json)
        if key != snapshots_key:
            calls["parquet"] += 1
        return real_get(key)

    backend.get_bytes = _counting_get  # type: ignore[assignment]
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)

    _load()
    assert calls["parquet"] == 3  # 3 hydration Parquet downloaded on first recovery
    _load()  # second recovery: local Parquet now present -> no re-download
    assert calls["parquet"] == 3


def test_empty_v2_short_circuits_without_object_read(s3_env, monkeypatch):
    manifest = _v2_manifest()
    manifest["files"] = []
    backend = _seed_store(with_parquet=False, manifest=manifest)

    def _no_parquet(key):
        if key != _snapshots_key():
            raise AssertionError("empty v2 must not fetch any Parquet object")
        return obj.LocalFsBackend(_seed_store.root).get_bytes(key)

    backend.get_bytes = _no_parquet  # type: ignore[assignment]
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)
    out = _load()
    assert out["files"] == []


def test_v1_recovery_needs_no_parquet(s3_env, monkeypatch):
    manifest = {"manifest_version": 1, "snapshot_id": _SNAP, "files": [{"file_path": "a.py", "symbols": []}]}
    backend = _seed_store(with_parquet=False, manifest=manifest)

    def _no_parquet(key):
        if key != _snapshots_key():
            raise AssertionError("v1 must not fetch any Parquet object")
        return obj.LocalFsBackend(_seed_store.root).get_bytes(key)

    backend.get_bytes = _no_parquet  # type: ignore[assignment]
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)
    out = _load()
    assert out["files"][0]["file_path"] == "a.py"


# --- read side: fail-closed branches ------------------------------------------------------------


def test_object_missing_raises_503(s3_env, monkeypatch):
    backend = _seed_store(with_parquet=False)  # manifest present, Parquet missing
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 503
    assert excinfo.value.code == "snapshot_hydration_unavailable"


def test_availability_fault_raises_503(s3_env, monkeypatch):
    backend = _seed_store(with_parquet=True)
    real_get = backend.get_bytes

    def _faulty(key):
        if key == _snapshots_key():
            return real_get(key)
        raise ResultStorageUnavailableError("object store unreachable")

    backend.get_bytes = _faulty  # type: ignore[assignment]
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 503
    assert excinfo.value.code == "snapshot_hydration_unavailable"


def test_integrity_mismatch_raises_503_and_does_not_write_local(s3_env, monkeypatch):
    manifest = _v2_manifest()
    manifest["symbol_graph_artifact"]["content_hash"] = "deadbeef"  # wrong
    backend = _seed_store(with_parquet=True, manifest=manifest)
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 503
    assert excinfo.value.code == "snapshot_hydration_corrupt"
    # verify-before-write: the corrupt artifact's local target was NOT created
    assert not s3_env["paths"]["symbol_graph_parquet"].exists()


def test_recovery_leaves_no_tmp_residue(s3_env, monkeypatch):
    backend = _seed_store(with_parquet=True)
    monkeypatch.setattr(obj, "get_object_store", lambda: backend)
    _load()
    residue = list(s3_env["paths"]["dir"].glob("*.tmp.*"))
    assert residue == []


def test_local_mode_snapshot_absent_raises_404(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_snapshot_paths", lambda o, r, s: _paths(tmp_path))
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)  # local mode

    def _boom():
        raise AssertionError("store must not be consulted in local mode")

    monkeypatch.setattr(obj, "get_object_store", _boom)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        _load()
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "snapshot_not_found"
