from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from apps.api_server.connectors.cloud_connector import AzureBlobConnector, GCSConnector, S3Connector


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _FakeDownload:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def readall(self) -> bytes:
        return self._payload


def _make_module(name: str, *, package: bool = False, **attrs: object) -> ModuleType:
    module = ModuleType(name)
    if package:
        module.__path__ = []  # type: ignore[attr-defined]
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


@pytest.mark.asyncio
async def test_s3_connector_supports_anonymous_boto3_fallback(monkeypatch) -> None:
    seen: dict[str, object] = {}
    unsigned_marker = "unsigned"

    class _FakeClient:
        def get_object(self, **kwargs: str) -> dict[str, object]:
            assert kwargs["Bucket"] == "public-bucket"
            assert kwargs["Key"] == "sales.csv"
            return {"Body": _FakeBody(b"amount\n10\n20\n")}

        def head_object(self, **kwargs: str) -> dict[str, object]:
            assert kwargs["Bucket"] == "public-bucket"
            assert kwargs["Key"] == "sales.csv"
            return {}

    def _fake_client(service_name: str, **kwargs):  # type: ignore[no-untyped-def]
        assert service_name == "s3"
        seen["kwargs"] = kwargs
        return _FakeClient()

    class _FakeBotoConfig:
        def __init__(self, *, signature_version: object) -> None:
            self.signature_version = signature_version

    monkeypatch.setitem(sys.modules, "aiobotocore", _make_module("aiobotocore"))

    boto3_module = _make_module("boto3", client=_fake_client)
    botocore_config_module = _make_module("botocore.config", Config=_FakeBotoConfig)
    botocore_module = _make_module(
        "botocore",
        package=True,
        UNSIGNED=unsigned_marker,
        config=botocore_config_module,
    )
    monkeypatch.setitem(sys.modules, "boto3", boto3_module)
    monkeypatch.setitem(sys.modules, "botocore", botocore_module)
    monkeypatch.setitem(sys.modules, "botocore.config", botocore_config_module)

    connector = S3Connector({
        "bucket": "public-bucket",
        "key": "sales.csv",
        "anonymous": True,
    })

    records = await connector.fetch_data()
    ok, message = await connector.validate_connection()

    assert len(records) == 2
    assert records[0]["amount"] == 10
    assert ok is True
    assert "accessible" in message
    assert isinstance(seen["kwargs"], dict)
    assert "config" in seen["kwargs"]
    assert isinstance(seen["kwargs"]["config"], _FakeBotoConfig)
    assert seen["kwargs"]["config"].signature_version == unsigned_marker


@pytest.mark.asyncio
async def test_gcs_connector_supports_anonymous_client(monkeypatch) -> None:
    class _FakeBlob:
        def download_as_bytes(self) -> bytes:
            return b"transaction_amount\n10.5\n20.25\n"

    class _FakeBucket:
        def blob(self, name: str) -> _FakeBlob:
            assert name == "transactions.csv"
            return _FakeBlob()

    class _FakeClient:
        def bucket(self, name: str) -> _FakeBucket:
            assert name == "public-bucket"
            return _FakeBucket()

    class _FakeStorageClientFactory:
        @staticmethod
        def create_anonymous_client() -> _FakeClient:
            return _FakeClient()

    storage_module = _make_module("google.cloud.storage", Client=_FakeStorageClientFactory)
    cloud_module = _make_module("google.cloud", package=True, storage=storage_module)
    google_module = _make_module("google", package=True, cloud=cloud_module)
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", storage_module)

    connector = GCSConnector({
        "bucket": "public-bucket",
        "blob": "transactions.csv",
        "anonymous": True,
    })

    records = await connector.fetch_data()
    ok, message = await connector.validate_connection()

    assert len(records) == 2
    assert records[1]["transaction_amount"] == pytest.approx(20.25)
    assert ok is True
    assert "accessible" in message


@pytest.mark.asyncio
async def test_azure_blob_connector_supports_public_blob_url(monkeypatch) -> None:
    class _FakeBlobClient:
        def download_blob(self) -> _FakeDownload:
            return _FakeDownload(b"damage_property\n0\n15\n")

        def get_blob_properties(self) -> SimpleNamespace:
            return SimpleNamespace(size=12)

    class _FakeBlobClientFactory:
        @classmethod
        def from_blob_url(cls, url: str) -> _FakeBlobClient:
            assert url == "https://example.blob.core.windows.net/samplefiles/storm.csv"
            return _FakeBlobClient()

    class _UnusedBlobServiceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("BlobServiceClient should not be used for blob_url access.")

    class _UnusedAsyncBlobServiceClient:
        @classmethod
        def from_connection_string(
            cls,
            *args: object,
            **kwargs: object,
        ) -> _UnusedAsyncBlobServiceClient:
            raise AssertionError(
                "AsyncBlobServiceClient should not be used for public blob validation."
            )

    azure_blob_aio_module = _make_module(
        "azure.storage.blob.aio",
        BlobServiceClient=_UnusedAsyncBlobServiceClient,
    )
    azure_blob_module = _make_module(
        "azure.storage.blob",
        package=True,
        BlobClient=_FakeBlobClientFactory,
        BlobServiceClient=_UnusedBlobServiceClient,
        aio=azure_blob_aio_module,
    )
    azure_storage_module = _make_module("azure.storage", package=True, blob=azure_blob_module)
    azure_module = _make_module("azure", package=True, storage=azure_storage_module)
    monkeypatch.setitem(sys.modules, "azure", azure_module)
    monkeypatch.setitem(sys.modules, "azure.storage", azure_storage_module)
    monkeypatch.setitem(sys.modules, "azure.storage.blob", azure_blob_module)
    monkeypatch.setitem(sys.modules, "azure.storage.blob.aio", azure_blob_aio_module)

    connector = AzureBlobConnector({
        "blob_url": "https://example.blob.core.windows.net/samplefiles/storm.csv",
        "anonymous": True,
    })

    records = await connector.fetch_data()
    ok, message = await connector.validate_connection()

    assert len(records) == 2
    assert records[1]["damage_property"] == 15
    assert ok is True
    assert "accessible" in message
