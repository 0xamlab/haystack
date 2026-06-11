"""Wave B8 migration: the source archive through the object store.

On snapshot create, ``_mirror_source_archive_to_object_store`` writes the ``source.tar`` to the
durable, tenant-scoped object store when ``ALGENTA_RI_OBJECT_STORE=s3`` (and is a no-op, fully
backward compatible, in local mode). On materialize, ``materialized_snapshot`` falls back to the
object store when the archive isn't on this node — recovering a snapshot created on another replica
or after the local volume was lost. Both directions fail closed."""

from __future__ import annotations

import io
import tarfile

import pytest

from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_snapshot_workflow as snap
from apps.api_server.services import repository_intelligence_storage as storage
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_ARCHIVE_KEY = obj.artifact_key(
    org_id="o", repository_id="r", kind="archives", artifact_id="s1"
)


def _tar_bytes(name: str, body: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as handle:
        info = tarfile.TarInfo(name=name)
        info.size = len(body)
        handle.addfile(info, io.BytesIO(body))
    return buf.getvalue()


# --- write side: mirror on snapshot create ------------------------------------------------------


def test_mirror_is_noop_in_local_mode(monkeypatch, tmp_path):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"tar-bytes")
    key = snap._mirror_source_archive_to_object_store(
        org_id="o", repository_id="r", snapshot_id="s1", archive_path=archive
    )
    assert key is None


def test_mirror_writes_to_store_in_s3_mode(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"tar-bytes")

    key = snap._mirror_source_archive_to_object_store(
        org_id="o", repository_id="r", snapshot_id="s1", archive_path=archive
    )

    assert key == _ARCHIVE_KEY
    assert store.get_bytes(key) == b"tar-bytes"


def test_mirror_fails_closed_when_store_write_raises(monkeypatch, tmp_path):
    class _Boom:
        def put_bytes(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"tar-bytes")

    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        snap._mirror_source_archive_to_object_store(
            org_id="o", repository_id="r", snapshot_id="s1", archive_path=archive
        )
    assert excinfo.value.code == "snapshot_source_archive_persist_failed"
    assert excinfo.value.status_code == 502


# --- read side: materialized_snapshot fallback --------------------------------------------------


def test_materialize_uses_local_archive_when_present(monkeypatch, tmp_path):
    archive = tmp_path / "source.tar"
    archive.write_bytes(_tar_bytes("a.py", b"x = 1\n"))

    def _must_not_consult_store():
        raise AssertionError("object store must not be consulted when the local archive exists")

    monkeypatch.setattr(obj, "get_object_store", _must_not_consult_store)

    manifest = {
        "source_archive_path": str(archive),
        "source_archive_object_key": "should-not-be-read",
    }
    with storage.materialized_snapshot(manifest) as materialized:
        assert (materialized / "a.py").read_text() == "x = 1\n"


def test_materialize_recovers_from_object_store_when_local_missing(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    store.put_bytes(_ARCHIVE_KEY, _tar_bytes("main.py", b"print('hi')\n"))
    monkeypatch.setattr(obj, "get_object_store", lambda: store)

    manifest = {
        "source_archive_path": str(tmp_path / "absent" / "source.tar"),
        "source_archive_object_key": _ARCHIVE_KEY,
    }
    with storage.materialized_snapshot(manifest) as materialized:
        assert (materialized / "main.py").read_text() == "print('hi')\n"


def test_materialize_410_when_local_missing_and_no_key(tmp_path):
    manifest = {"source_archive_path": str(tmp_path / "absent.tar")}
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        with storage.materialized_snapshot(manifest):
            pass
    assert excinfo.value.code == "snapshot_source_unavailable"
    assert excinfo.value.status_code == 410


def test_materialize_410_when_object_missing(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")  # empty
    monkeypatch.setattr(obj, "get_object_store", lambda: store)

    manifest = {
        "source_archive_path": str(tmp_path / "absent.tar"),
        "source_archive_object_key": _ARCHIVE_KEY,
    }
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        with storage.materialized_snapshot(manifest):
            pass
    assert excinfo.value.code == "snapshot_source_unavailable"
    assert excinfo.value.status_code == 410


# --- write side: mirror the snapshot MANIFEST on snapshot create --------------------------------

_MANIFEST_KEY = obj.artifact_key(
    org_id="o", repository_id="r", kind="snapshots", artifact_id="s1"
)
_SNAPSHOT_MANIFEST = {"manifest_version": 2, "snapshot_id": "s1", "files": []}


def test_mirror_manifest_is_noop_in_local_mode(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    key = snap._mirror_snapshot_manifest_to_object_store(
        org_id="o", repository_id="r", snapshot_id="s1", manifest=_SNAPSHOT_MANIFEST
    )
    assert key is None


def test_mirror_manifest_writes_to_store_in_s3_mode(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)

    key = snap._mirror_snapshot_manifest_to_object_store(
        org_id="o", repository_id="r", snapshot_id="s1", manifest=_SNAPSHOT_MANIFEST
    )

    # distinct 'snapshots' kind — never collides with the source archive's 'archives' key
    assert key == _MANIFEST_KEY
    assert key != _ARCHIVE_KEY
    assert store.get_json(key) == _SNAPSHOT_MANIFEST


def test_mirror_manifest_fails_closed_when_store_write_raises(monkeypatch):
    class _Boom:
        def put_json(self, *args, **kwargs):
            raise RuntimeError("object store unreachable")

    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: _Boom())

    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        snap._mirror_snapshot_manifest_to_object_store(
            org_id="o", repository_id="r", snapshot_id="s1", manifest=_SNAPSHOT_MANIFEST
        )
    assert excinfo.value.code == "snapshot_manifest_persist_failed"
    assert excinfo.value.status_code == 502
