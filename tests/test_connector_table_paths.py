from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from apps.api_server.connectors import file_connector as file_connector_module
from apps.api_server.connectors.cloud_connector import AzureBlobConnector, GCSConnector, S3Connector
from apps.api_server.connectors.file_connector import FileConnector
from apps.api_server.connectors.rest_connector import RESTConnector


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


def _tiny_excel_b64() -> str:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["part_number", "measure_total", "region"])
    ws.append(["00123", 10, "NE"])
    ws.append(["00456", 20, "SW"])
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def _write_tiny_excel(path: Path) -> None:
    path.write_bytes(base64.b64decode(_tiny_excel_b64()))


@pytest.mark.asyncio
async def test_file_connector_fetch_table_supports_json_records() -> None:
    connector = FileConnector(
        {
            "file_type": "json",
            "content": '[{"amount": 10, "region": "east"}, {"amount": 20, "region": "west"}]',
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["amount", "region"]


@pytest.mark.asyncio
async def test_file_connector_fetch_table_supports_excel_without_row_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("excel fetch_table should use direct workbook-to-arrow path")

    monkeypatch.setattr(FileConnector, "_parse_excel", staticmethod(_should_not_run))

    connector = FileConnector(
        {
            "file_type": "excel",
            "content": _tiny_excel_b64(),
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.to_pylist() == [
        {"part_number": "00123", "measure_total": 10, "region": "NE"},
        {"part_number": "00456", "measure_total": 20, "region": "SW"},
    ]


@pytest.mark.asyncio
async def test_file_connector_fetch_table_uses_raw_excel_bytes_for_file_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyarrow as pa

    workbook_path = tmp_path / "tiny.xlsx"
    _write_tiny_excel(workbook_path)
    seen: dict[str, object] = {}

    def _capture(content: str | bytes, sheet: int | str = 0):  # type: ignore[no-untyped-def]
        seen["content_type"] = type(content)
        seen["sheet"] = sheet
        return pa.table({"part_number": ["00123"]})

    monkeypatch.setattr(FileConnector, "_excel_to_arrow_table", staticmethod(_capture))

    connector = FileConnector(
        {
            "file_type": "excel",
            "file_path": str(workbook_path),
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 1
    assert seen == {"content_type": bytes, "sheet": 0}


@pytest.mark.asyncio
async def test_file_connector_fetch_table_caches_repeated_excel_text_coercions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["region", "status"])
    ws.append(["NE", "Open"])
    ws.append(["NE", "Open"])
    ws.append(["NE", "Open"])
    buf = io.BytesIO()
    wb.save(buf)
    workbook_b64 = base64.b64encode(buf.getvalue()).decode()
    calls: list[tuple[str, str, bool]] = []

    def _fake_text_coerce(field_name: str, value: str, *, preserve_identifiers: bool):  # type: ignore[no-untyped-def]
        calls.append((field_name, value, preserve_identifiers))
        return value

    monkeypatch.setattr(file_connector_module, "_coerce_text_scalar", _fake_text_coerce)

    connector = FileConnector({"file_type": "excel", "content": workbook_b64})
    table = await connector.fetch_table()

    assert table is not None
    assert table.to_pylist() == [
        {"region": "NE", "status": "Open"},
        {"region": "NE", "status": "Open"},
        {"region": "NE", "status": "Open"},
    ]
    assert calls == [
        ("region", "NE", False),
        ("status", "Open", False),
    ]


@pytest.mark.asyncio
async def test_rest_connector_fetch_table_returns_arrow(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_fetch_data(self) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
        return [{"score": 1.5, "system": "a"}, {"score": 2.5, "system": "b"}]

    monkeypatch.setattr(RESTConnector, "fetch_data", _fake_fetch_data)

    connector = RESTConnector({"url": "https://example.com/data"})
    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["score", "system"]


@pytest.mark.asyncio
async def test_s3_connector_fetch_table_uses_columnar_path(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    unsigned_marker = "unsigned"

    class _FakeClient:
        def get_object(self, **kwargs: str) -> dict[str, object]:
            assert kwargs["Bucket"] == "public-bucket"
            assert kwargs["Key"] == "sales.csv"
            return {"Body": _FakeBody(b"amount\n10\n20\n")}

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

    connector = S3Connector(
        {
            "bucket": "public-bucket",
            "key": "sales.csv",
            "anonymous": True,
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["amount"]
    assert isinstance(seen["kwargs"], dict)
    assert isinstance(seen["kwargs"]["config"], _FakeBotoConfig)
    assert seen["kwargs"]["config"].signature_version == unsigned_marker


@pytest.mark.asyncio
async def test_gcs_connector_fetch_table_uses_columnar_path(monkeypatch: pytest.MonkeyPatch) -> None:
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

    connector = GCSConnector(
        {
            "bucket": "public-bucket",
            "blob": "transactions.csv",
            "anonymous": True,
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["transaction_amount"]


@pytest.mark.asyncio
async def test_azure_blob_connector_fetch_table_uses_columnar_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                "AsyncBlobServiceClient should not be used for public blob access."
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

    connector = AzureBlobConnector(
        {
            "blob_url": "https://example.blob.core.windows.net/samplefiles/storm.csv",
            "anonymous": True,
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["damage_property"]
