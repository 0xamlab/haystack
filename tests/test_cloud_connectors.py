from __future__ import annotations

import pytest

from apps.api_server.connectors import cloud_connector as cloud_connector_module
from apps.api_server.connectors.cloud_connector import AzureBlobConnector, GCSConnector, S3Connector


@pytest.mark.anyio
async def test_s3_connector_prefers_public_http_for_anonymous_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    async def _fake_get_bytes(url: str) -> bytes:
        seen["get_url"] = url
        return b"amount\n10\n20\n"

    async def _fake_validate_access(url: str) -> None:
        seen["head_url"] = url

    monkeypatch.setattr(cloud_connector_module, "_http_get_bytes", _fake_get_bytes)
    monkeypatch.setattr(cloud_connector_module, "_http_validate_access", _fake_validate_access)

    connector = S3Connector(
        {
            "bucket": "public-bucket",
            "key": "sales.csv",
            "anonymous": True,
        }
    )

    records = await connector.fetch_data()
    ok, message = await connector.validate_connection()

    assert records == [{"amount": 10}, {"amount": 20}]
    assert ok is True
    assert "accessible" in message
    assert seen == {
        "get_url": "https://public-bucket.s3.amazonaws.com/sales.csv",
        "head_url": "https://public-bucket.s3.amazonaws.com/sales.csv",
    }


@pytest.mark.anyio
async def test_gcs_connector_prefers_public_http_for_anonymous_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    async def _fake_get_bytes(url: str) -> bytes:
        seen["get_url"] = url
        return b"transaction_amount\n10.5\n20.25\n"

    async def _fake_validate_access(url: str) -> None:
        seen["head_url"] = url

    monkeypatch.setattr(cloud_connector_module, "_http_get_bytes", _fake_get_bytes)
    monkeypatch.setattr(cloud_connector_module, "_http_validate_access", _fake_validate_access)

    connector = GCSConnector(
        {
            "bucket": "public-bucket",
            "blob": "transactions.csv",
            "anonymous": True,
        }
    )

    records = await connector.fetch_data()
    ok, message = await connector.validate_connection()

    assert len(records) == 2
    assert records[1]["transaction_amount"] == pytest.approx(20.25)
    assert ok is True
    assert "accessible" in message
    assert seen == {
        "get_url": "https://storage.googleapis.com/public-bucket/transactions.csv",
        "head_url": "https://storage.googleapis.com/public-bucket/transactions.csv",
    }


@pytest.mark.anyio
async def test_gcs_connector_rejects_invalid_bucket_identifier_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _should_not_run(_url: str) -> bytes:
        raise AssertionError("network should not be reached for invalid bucket identifiers")

    async def _should_not_validate(_url: str) -> None:
        raise AssertionError("network should not be reached for invalid bucket identifiers")

    monkeypatch.setattr(cloud_connector_module, "_http_get_bytes", _should_not_run)
    monkeypatch.setattr(cloud_connector_module, "_http_validate_access", _should_not_validate)

    connector = GCSConnector(
        {
            "bucket": "invalid bucket",
            "blob": "transactions.csv",
            "anonymous": True,
        }
    )

    with pytest.raises(ValueError, match="invalid identifier"):
        await connector.fetch_data()

    ok, message = await connector.validate_connection()
    assert ok is False
    assert "invalid identifier" in message.lower()


@pytest.mark.anyio
async def test_azure_blob_connector_prefers_public_http_for_blob_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    async def _fake_get_bytes(url: str) -> bytes:
        seen["get_url"] = url
        return b"damage_property\n0\n15\n"

    async def _fake_validate_access(url: str) -> None:
        seen["head_url"] = url

    monkeypatch.setattr(cloud_connector_module, "_http_get_bytes", _fake_get_bytes)
    monkeypatch.setattr(cloud_connector_module, "_http_validate_access", _fake_validate_access)

    blob_url = "https://example.blob.core.windows.net/samplefiles/storm.csv"
    connector = AzureBlobConnector(
        {
            "blob_url": blob_url,
            "anonymous": True,
        }
    )

    records = await connector.fetch_data()
    ok, message = await connector.validate_connection()

    assert len(records) == 2
    assert records[1]["damage_property"] == 15
    assert ok is True
    assert "accessible" in message
    assert seen == {"get_url": blob_url, "head_url": blob_url}
