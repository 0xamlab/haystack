from __future__ import annotations

from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_s3_connector_supports_anonymous_boto3_fallback(monkeypatch) -> None:
    import boto3

    seen: dict[str, object] = {}

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

    monkeypatch.setattr(boto3, "client", _fake_client)

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
    assert "config" in seen["kwargs"]


@pytest.mark.asyncio
async def test_gcs_connector_supports_anonymous_client(monkeypatch) -> None:
    from google.cloud import storage

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

    monkeypatch.setattr(storage.Client, "create_anonymous_client", staticmethod(lambda: _FakeClient()))

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
    from azure.storage import blob as azure_blob

    class _FakeBlobClient:
        def download_blob(self) -> _FakeDownload:
            return _FakeDownload(b"damage_property\n0\n15\n")

        def get_blob_properties(self) -> SimpleNamespace:
            return SimpleNamespace(size=12)

    monkeypatch.setattr(
        azure_blob.BlobClient,
        "from_blob_url",
        classmethod(lambda cls, url: _FakeBlobClient()),
    )

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
