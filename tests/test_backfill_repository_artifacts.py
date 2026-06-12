"""The artifact-backfill job mirrors local snapshot/triage/simulation artifacts + their dedup
lookups into the object store (s3 mode), so pre-s3 artifacts become cross-replica-recoverable and
dedup-able. Verified against a LocalFsBackend standing in for s3."""

from __future__ import annotations

from apps.api_server.services import repository_intelligence_object_store as obj
from scripts.backfill_repository_artifacts_to_object_store import main as backfill_main
from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def _enable_s3(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    return store


def _snapshot_locally(tmp_path):
    connector = _connector_for_repo(_sample_repo(tmp_path))
    snap = repository_service.create_repository_snapshot(
        connector=connector, request=RepositorySnapshotCreateRequest()
    )
    return str(connector.org_id), str(connector.id), snap.snapshot_id


def test_backfill_mirrors_snapshot_artifacts_and_lookup(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    org, repo, snapshot_id = _snapshot_locally(tmp_path)  # created in LOCAL mode (no mirror)
    store = _enable_s3(monkeypatch, tmp_path)

    assert backfill_main([org]) == 0

    def _key(kind):
        return obj.artifact_key(org_id=org, repository_id=repo, kind=kind, artifact_id=snapshot_id)

    assert store.get_json(_key("snapshots")) is not None, "manifest mirrored"
    assert store.get_bytes(_key("snapshot_parquet")) is not None, "Parquet mirrored"
    assert store.get_bytes(_key("archives")) is not None, "source archive mirrored"
    # the snapshot dedup lookup is re-published so a sibling can dedup without a re-clone
    assert any(
        "snapshot_lookup" in str(p) for p in (tmp_path / "store").rglob("*") if p.is_file()
    ), "snapshot_lookup re-published"


def test_backfill_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    org, repo, snapshot_id = _snapshot_locally(tmp_path)
    store = _enable_s3(monkeypatch, tmp_path)

    assert backfill_main([org, "--dry-run"]) == 0
    assert (
        store.get_json(obj.artifact_key(org_id=org, repository_id=repo, kind="snapshots", artifact_id=snapshot_id))
        is None
    ), "dry-run must not write anything"


def test_backfill_refuses_in_local_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    # local object-store mode → nothing to mirror → exit 2 (and never touches a store)
    assert backfill_main([]) == 2
