"""AR-OPT-2 slim-manifest-v2 + Parquet hydration contract.

Locks the invariants the optimization depends on:
  * the on-disk manifest is slim (no inline symbols/dependencies/symbol_references),
  * loading hydrates the arrays back from Parquet so consumers are unchanged,
  * hydrated symbols match the EXACT v1 inline key set (no file_path — else reference
    resolution would diverge from v1),
  * the cold load is timed into parquet_read_ms and a warm load (content-hash cache hit)
    skips the Parquet read entirely.
"""
from __future__ import annotations

import json

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403

from apps.api_server.services import repository_intelligence_manifest_reader as manifest_reader
from apps.api_server.services import repository_intelligence_storage as repository_storage
from apps.api_server.services import repository_intelligence_telemetry as telemetry

_INLINE_SYMBOL_KEYS = {
    "symbol_id",
    "symbol_name",
    "symbol_kind",
    "start_line",
    "end_line",
    "parent_symbol_id",
    "signature",
}


def _make_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)  # noqa: F405
    connector = _connector_for_repo(repo_path)  # noqa: F405
    snapshot = repository_service.create_repository_snapshot(  # noqa: F405
        connector=connector,
        request=RepositorySnapshotCreateRequest(),  # noqa: F405
    )
    manifest_reader.clear_hydration_cache()
    return connector, snapshot


def _load_kwargs(connector, snapshot):
    return {
        "org_id": str(connector.org_id),
        "repository_id": str(connector.id),
        "snapshot_id": snapshot.snapshot_id,
    }


def test_v2_manifest_on_disk_is_slim(tmp_path, monkeypatch):
    connector, snapshot = _make_snapshot(tmp_path, monkeypatch)
    manifest_path = repository_storage._snapshot_paths(
        str(connector.org_id), str(connector.id), snapshot.snapshot_id
    )["manifest"]
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert on_disk["manifest_version"] == 2
    assert on_disk["files"], "fixture should index at least one file"
    for file_entry in on_disk["files"]:
        assert "symbols" not in file_entry
        assert "dependencies" not in file_entry
        assert "symbol_references" not in file_entry
    # the references artifact must be referenced so hydration has a Parquet source
    assert on_disk["symbol_reference_artifact"]["storage_path"]


def test_load_hydrates_v2_manifest_with_exact_inline_shape(tmp_path, monkeypatch):
    connector, snapshot = _make_snapshot(tmp_path, monkeypatch)

    with telemetry.collect() as data:
        hydrated = repository_storage._load_snapshot_manifest(**_load_kwargs(connector, snapshot))

    assert hydrated["manifest_version"] == 2
    assert hydrated["files"]
    for file_entry in hydrated["files"]:
        assert "symbols" in file_entry
        assert "dependencies" in file_entry
        assert "symbol_references" in file_entry

    symbol = next((s for fe in hydrated["files"] for s in fe["symbols"]), None)
    assert symbol is not None, "fixture should produce at least one symbol"
    # EXACT v1 inline key set — file_path must be absent (parity invariant).
    assert set(symbol.keys()) == _INLINE_SYMBOL_KEYS
    assert "file_path" not in symbol

    # cold load is timed into the parquet_read_ms span
    assert "parquet_read_ms" in data["spans_ms"]
    assert data["spans_ms"]["parquet_read_ms"] >= 0.0


def test_hydration_cache_warm_hit_skips_parquet_read(tmp_path, monkeypatch):
    connector, snapshot = _make_snapshot(tmp_path, monkeypatch)
    kwargs = _load_kwargs(connector, snapshot)

    with telemetry.collect() as cold:
        repository_storage._load_snapshot_manifest(**kwargs)
    assert "parquet_read_ms" in cold["spans_ms"], "cold load must read Parquet"

    with telemetry.collect() as warm:
        repository_storage._load_snapshot_manifest(**kwargs)
    # same content hashes -> cache hit -> no Parquet read on the warm path
    assert "parquet_read_ms" not in warm["spans_ms"]


def test_hydrate_is_noop_for_legacy_v1_inline_manifest():
    v1 = {
        "manifest_version": 1,
        "snapshot_id": "old-1",
        "files": [
            {
                "file_path": "a.py",
                "symbols": [{"symbol_id": "s1", "symbol_name": "f"}],
                "dependencies": [],
                "symbol_references": [],
            }
        ],
    }
    with telemetry.collect() as data:
        out = manifest_reader.hydrate_snapshot_manifest(v1)
    assert out is v1
    assert out["files"][0]["symbols"] == [{"symbol_id": "s1", "symbol_name": "f"}]
    assert "parquet_read_ms" not in data["spans_ms"]


def test_hydrate_is_noop_for_versionless_manifest():
    # manifests written before manifest_version existed default to v1 (inline).
    legacy = {
        "snapshot_id": "legacy-1",
        "files": [{"file_path": "a.py", "symbols": [], "dependencies": [], "symbol_references": []}],
    }
    out = manifest_reader.hydrate_snapshot_manifest(legacy)
    assert out is legacy
    assert manifest_reader.manifest_version(legacy) == 1
