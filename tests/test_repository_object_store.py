"""Wave B8 foundation: the RI object-store abstraction — tenant-scoped, path-safe keys; a
node-local backend that round-trips json/bytes and confines writes to its root; and opt-in
S3 selection."""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_object_store as obj


def test_artifact_key_is_tenant_scoped_and_validated():
    k = obj.artifact_key(org_id="org1", repository_id="repo1", kind="snapshots", artifact_id="snap-abc")
    assert k == "repository_intelligence/tenants/org1/repositories/repo1/snapshots/snap-abc"
    for bad in (
        {"org_id": "../x", "repository_id": "r", "kind": "k", "artifact_id": "a"},
        {"org_id": "o", "repository_id": "a/b", "kind": "k", "artifact_id": "a"},
        {"org_id": "o", "repository_id": "r", "kind": "k", "artifact_id": "x y"},
    ):
        with pytest.raises(ValueError):
            obj.artifact_key(**bad)


def test_local_fs_backend_round_trips(tmp_path):
    be = obj.LocalFsBackend(tmp_path)
    assert be.name == "local_fs"
    key = obj.artifact_key(org_id="o", repository_id="r", kind="snapshots", artifact_id="s1")
    assert be.get_json(key) is None
    assert be.exists(key) is False
    be.put_json(key, {"a": 1, "b": [2, 3]})
    assert be.get_json(key) == {"a": 1, "b": [2, 3]}
    assert be.exists(key) is True
    bkey = obj.artifact_key(org_id="o", repository_id="r", kind="archives", artifact_id="src")
    be.put_bytes(bkey, b"tar-bytes")
    assert be.get_bytes(bkey) == b"tar-bytes"


def test_local_fs_backend_rejects_path_escape(tmp_path):
    be = obj.LocalFsBackend(tmp_path)
    with pytest.raises(ValueError):
        be.put_json("../escape.json", {"x": 1})


def test_get_object_store_defaults_to_local(monkeypatch, tmp_path):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "allow")
    from apps.api_server.services import repository_intelligence_runtime as rt

    rt._RUNTIME_FALLBACK_CACHE = None
    try:
        store = obj.get_object_store()
        assert isinstance(store, obj.LocalFsBackend)
    finally:
        rt._RUNTIME_FALLBACK_CACHE = None


def test_get_object_store_s3_opt_in(monkeypatch):
    monkeypatch.setenv("ALGENTA_RI_OBJECT_STORE", "s3")
    from apps.api_server.services import storage_service

    monkeypatch.setattr(storage_service, "_bucket_name", lambda: "test-bucket")
    store = obj.get_object_store()
    assert isinstance(store, obj.S3Backend)
    assert store.name == "s3"
    assert store._bucket == "test-bucket"


def test_artifact_key_kinds_are_disjoint_for_same_id():
    """The snapshot MANIFEST ('snapshots') and its source archive ('archives') share a snapshot_id
    but must land on distinct keys so the JSON never overwrites source.tar."""
    snapshot_id = "snap-abc"
    manifest_key = obj.artifact_key(org_id="o", repository_id="r", kind="snapshots", artifact_id=snapshot_id)
    archive_key = obj.artifact_key(org_id="o", repository_id="r", kind="archives", artifact_id=snapshot_id)
    assert manifest_key != archive_key


class _FakeClientError(Exception):
    """Mimics botocore.exceptions.ClientError: carries response['Error']['Code']."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeS3Client:
    def __init__(self, *, raises: Exception) -> None:
        self._raises = raises

    def get_object(self, **kwargs):
        raise self._raises


def _s3_backend_with_client(monkeypatch, client) -> "obj.S3Backend":
    be = obj.S3Backend("bucket")
    monkeypatch.setattr(be, "_client", lambda: client)
    return be


def test_s3_get_bytes_returns_none_only_on_genuine_not_found(monkeypatch):
    for code in ("NoSuchKey", "404", "NotFound"):
        be = _s3_backend_with_client(monkeypatch, _FakeS3Client(raises=_FakeClientError(code)))
        assert be.get_bytes("k") is None


def test_s3_get_bytes_reraises_non_not_found_client_error(monkeypatch):
    # An auth/throttling/5xx fault must NOT be masked as a miss.
    be = _s3_backend_with_client(monkeypatch, _FakeS3Client(raises=_FakeClientError("AccessDenied")))
    with pytest.raises(_FakeClientError):
        be.get_bytes("k")


def test_s3_get_bytes_propagates_unavailability_from_client(monkeypatch):
    # _client() (storage_service._get_client/_ensure_bucket) raising ResultStorageUnavailableError
    # must PROPAGATE — never collapse to None (which a caller would misread as 404/410).
    from apps.api_server.services.storage_service import ResultStorageUnavailableError

    be = obj.S3Backend("bucket")

    def _boom():
        raise ResultStorageUnavailableError("object storage unreachable")

    monkeypatch.setattr(be, "_client", _boom)
    with pytest.raises(ResultStorageUnavailableError):
        be.get_bytes("k")
