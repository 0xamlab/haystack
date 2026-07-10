"""DB/SDK-free tests for the Azure Blob object-store backend (Build order 7).

A fake container client mimics azure-storage-blob semantics (download_blob raises a
ResourceNotFoundError-named exception on a miss; a different exception is a real fault) so the
round-trip, JSON path, secret redaction, and — critically — the fail-closed get semantics
(not-found → None, availability fault → propagate) are all verified without the Azure SDK.
"""

from __future__ import annotations

import json

import pytest

from apps.api_server.services.repository_intelligence_object_store import (
    AzureBlobBackend,
    artifact_key,
)


class ResourceNotFoundError(Exception):
    """Name matches azure.core.exceptions.ResourceNotFoundError (detected by class name)."""


class _ServiceError(Exception):
    status_code = 503


class _FakeDownload:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def readall(self) -> bytes:
        return self._data


class _FakeContainerClient:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.fault_on_get = False

    def upload_blob(self, *, name: str, data: bytes, overwrite: bool = False) -> None:
        if name in self.blobs and not overwrite:
            raise Exception("blob exists")
        self.blobs[name] = data

    def download_blob(self, name: str) -> _FakeDownload:
        if self.fault_on_get:
            raise _ServiceError("throttled")
        if name not in self.blobs:
            raise ResourceNotFoundError(name)
        return _FakeDownload(self.blobs[name])


def _backend() -> tuple[AzureBlobBackend, _FakeContainerClient]:
    fake = _FakeContainerClient()
    return AzureBlobBackend("artifacts", client_factory=lambda: fake), fake


KEY = artifact_key(org_id="org1", repository_id="repo1", kind="decision", artifact_id="a1")


def test_bytes_round_trip() -> None:
    b, _ = _backend()
    assert b.get_bytes(KEY) is None
    b.put_bytes(KEY, b"hello", content_type="text/plain")
    assert b.get_bytes(KEY) == b"hello"
    assert b.exists(KEY) is True


def test_json_round_trip() -> None:
    b, _ = _backend()
    b.put_json(KEY, {"z": 1, "a": 2})
    got = b.get_json(KEY)
    assert got == {"z": 1, "a": 2}


def test_json_is_stored_sorted_and_redacted() -> None:
    b, fake = _backend()
    b.put_json(KEY, {"password": "s3cret", "value": 10})
    raw = json.loads(fake.blobs[KEY].decode())
    assert raw["value"] == 10
    assert raw["password"] != "s3cret"  # secret_redaction applied (defense-in-depth)


def test_missing_blob_returns_none_not_error() -> None:
    b, _ = _backend()
    assert b.get_bytes("repository_intelligence/tenants/org1/repositories/r/k/missing") is None


def test_availability_fault_propagates_never_masked_as_miss() -> None:
    # fail-closed: a throttle/connectivity fault must NOT look like "no object".
    b, fake = _backend()
    b.put_bytes(KEY, b"x")
    fake.fault_on_get = True
    with pytest.raises(_ServiceError):
        b.get_bytes(KEY)
    with pytest.raises(_ServiceError):
        b.exists(KEY)


def test_overwrite_semantics() -> None:
    b, _ = _backend()
    b.put_bytes(KEY, b"v1")
    b.put_bytes(KEY, b"v2")  # overwrite=True in the backend
    assert b.get_bytes(KEY) == b"v2"


def test_missing_config_raises_clean_error() -> None:
    # No connection string / account URL / injected client → clear runtime error, not an SDK crash.
    b = AzureBlobBackend("artifacts")
    with pytest.raises(RuntimeError):
        b.get_bytes(KEY)


def test_get_object_store_selects_azure(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api_server.services import repository_intelligence_object_store as m

    monkeypatch.setenv("ALGENTA_RI_OBJECT_STORE", "azure_blob")
    monkeypatch.setenv("AZURE_BLOB_CONTAINER", "artifacts")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    store = m.get_object_store()
    assert store.name == "azure_blob"

    monkeypatch.delenv("AZURE_BLOB_CONTAINER")
    with pytest.raises(RuntimeError):
        m.get_object_store()  # azure_blob mode without a container is a clean error
