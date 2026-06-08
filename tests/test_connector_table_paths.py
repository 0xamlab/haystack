from __future__ import annotations

import base64
import io
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

from apps.api_server.connectors import cloud_connector as cloud_connector_module
from apps.api_server.connectors import file_connector as file_connector_module
from apps.api_server.connectors.cloud_connector import AzureBlobConnector, GCSConnector, S3Connector
from apps.api_server.connectors.file_connector import FileConnector
from apps.api_server.connectors.rest_connector import RESTConnector


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
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


def _multi_sheet_excel_b64() -> str:
    import openpyxl

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "First"
    ws1.append(["part_number", "measure_total"])
    ws1.append(["00123", 10])

    ws2 = wb.create_sheet("Second")
    ws2.append(["part_number", "measure_total"])
    ws2.append(["00456", 20])
    ws2.append(["00789", 30])

    ws3 = wb.create_sheet("Third")
    ws3.append(["part_number", "measure_total"])
    ws3.append(["00001", 1])

    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_file_connector_fetch_table_supports_excel_without_row_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("excel fetch_table should use direct workbook-to-arrow path")

    monkeypatch.setattr(FileConnector, "_parse_excel", staticmethod(_should_not_run))
    monkeypatch.setattr(
        FileConnector,
        "_fast_xlsx_to_arrow_table",
        staticmethod(_should_not_run),
    )

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


@pytest.mark.anyio
async def test_file_connector_fetch_data_prefers_openpyxl_excel_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("excel fetch_data should prefer openpyxl sheet loading")

    monkeypatch.setattr(FileConnector, "_iter_fast_xlsx_rows", staticmethod(_should_not_run))

    connector = FileConnector(
        {
            "file_type": "excel",
            "content": _tiny_excel_b64(),
        }
    )

    records = await connector.fetch_data()

    assert records == [
        {"part_number": "00123", "measure_total": 10, "region": "NE"},
        {"part_number": "00456", "measure_total": 20, "region": "SW"},
    ]


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_file_connector_fast_excel_path_preserves_typed_values() -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["created_at", "active", "measure_total"])
    ws.append([datetime(2026, 3, 1, 14, 30, 0), True, 10.5])
    ws.append([datetime(2026, 3, 2, 9, 15, 0), False, 12])
    buf = io.BytesIO()
    wb.save(buf)
    workbook_b64 = base64.b64encode(buf.getvalue()).decode()

    connector = FileConnector({"file_type": "excel", "content": workbook_b64})

    table = await connector.fetch_table()
    records = await connector.fetch_data()

    assert table is not None
    assert table.to_pylist() == [
        {
            "created_at": "2026-03-01 14:30:00",
            "active": True,
            "measure_total": 10.5,
        },
        {
            "created_at": "2026-03-02 09:15:00",
            "active": False,
            "measure_total": 12,
        },
    ]
    assert records == [
        {
            "created_at": "2026-03-01 14:30:00",
            "active": True,
            "measure_total": 10.5,
        },
        {
            "created_at": "2026-03-02 09:15:00",
            "active": False,
            "measure_total": 12,
        },
    ]


def test_open_excel_sheet_loads_only_requested_sheet() -> None:
    workbook_b64 = _multi_sheet_excel_b64()

    wb, ws = FileConnector._open_excel_sheet(workbook_b64, sheet=1)
    try:
        rows = ws.values
        headers = next(rows)
        records = [dict(zip(headers, row, strict=False)) for row in rows]
        assert ws.title == "Second"
        assert len(wb._sheets) == 1
        assert records == [
            {"part_number": "00456", "measure_total": 20},
            {"part_number": "00789", "measure_total": 30},
        ]
    finally:
        wb.close()


def test_open_excel_sheet_skips_nonessential_metadata_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openpyxl.reader import excel as excel_reader_module

    def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("nonessential workbook metadata should not be loaded")

    monkeypatch.setattr(excel_reader_module.ExcelReader, "read_properties", _should_not_run)
    monkeypatch.setattr(excel_reader_module.ExcelReader, "read_custom", _should_not_run)
    monkeypatch.setattr(excel_reader_module.ExcelReader, "read_theme", _should_not_run)
    monkeypatch.setattr(excel_reader_module, "apply_stylesheet", _should_not_run)

    wb, ws = FileConnector._open_excel_sheet(_tiny_excel_b64(), sheet=0)
    try:
        rows = ws.values
        headers = next(rows)
        records = [dict(zip(headers, row, strict=False)) for row in rows]
        assert ws.title == "Sheet1"
        assert records == [
            {"part_number": "00123", "measure_total": 10, "region": "NE"},
            {"part_number": "00456", "measure_total": 20, "region": "SW"},
        ]
    finally:
        wb.close()


@pytest.mark.anyio
async def test_file_connector_fetch_data_falls_back_to_fast_excel_parser_on_openpyxl_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_openpyxl(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise ValueError("openpyxl failed")

    monkeypatch.setattr(FileConnector, "_open_excel_sheet", staticmethod(_fail_openpyxl))

    connector = FileConnector(
        {
            "file_type": "excel",
            "content": _tiny_excel_b64(),
        }
    )

    table = await connector.fetch_table()
    records = await connector.fetch_data()

    assert table is not None
    assert table.to_pylist() == [
        {"part_number": "00123", "measure_total": 10, "region": "NE"},
        {"part_number": "00456", "measure_total": 20, "region": "SW"},
    ]
    assert records == [
        {"part_number": "00123", "measure_total": 10, "region": "NE"},
        {"part_number": "00456", "measure_total": 20, "region": "SW"},
    ]


@pytest.mark.anyio
async def test_file_connector_fetch_table_falls_back_to_fast_excel_parser_on_openpyxl_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_openpyxl(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise ValueError("openpyxl failed")

    monkeypatch.setattr(
        FileConnector,
        "_openpyxl_excel_to_arrow_table",
        staticmethod(_fail_openpyxl),
    )

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


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_rest_connector_fetch_table_returns_arrow(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_fetch_data(self) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
        return [{"score": 1.5, "system": "a"}, {"score": 2.5, "system": "b"}]

    monkeypatch.setattr(RESTConnector, "fetch_data", _fake_fetch_data)

    connector = RESTConnector({"url": "https://example.com/data"})
    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["score", "system"]


@pytest.mark.anyio
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
            "endpoint_url": "https://minio.example.com",
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["amount"]
    assert isinstance(seen["kwargs"], dict)
    assert isinstance(seen["kwargs"]["config"], _FakeBotoConfig)
    assert seen["kwargs"]["config"].signature_version == unsigned_marker


@pytest.mark.anyio
async def test_gcs_connector_fetch_table_uses_columnar_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "credentials": "{}",
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["transaction_amount"]


@pytest.mark.anyio
async def test_azure_blob_connector_fetch_table_uses_columnar_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    async def _should_not_run(_url: str) -> bytes:
        raise AssertionError("public HTTP path should not be used for connection-string access")

    monkeypatch.setattr(cloud_connector_module, "_http_get_bytes", _should_not_run)

    class _FakeStream:
        async def readall(self) -> bytes:
            return b"damage_property\n0\n15\n"

    class _FakeBlobClient:
        async def download_blob(self) -> _FakeStream:
            return _FakeStream()

    class _FakeAsyncBlobServiceClient:
        def __init__(self, connection_string: str) -> None:
            seen["connection_string"] = connection_string

        @classmethod
        def from_connection_string(
            cls,
            connection_string: str,
        ) -> _FakeAsyncBlobServiceClient:
            return cls(connection_string)

        async def __aenter__(self) -> _FakeAsyncBlobServiceClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        def get_blob_client(self, *, container: str, blob: str) -> _FakeBlobClient:
            seen["container"] = container
            seen["blob"] = blob
            return _FakeBlobClient()

    azure_blob_aio_module = _make_module(
        "azure.storage.blob.aio",
        BlobServiceClient=_FakeAsyncBlobServiceClient,
    )
    azure_blob_module = _make_module(
        "azure.storage.blob",
        package=True,
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
            "connection_string": "UseDevelopmentStorage=true",
            "container": "samplefiles",
            "blob": "storm.csv",
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["damage_property"]
    assert seen == {
        "connection_string": "UseDevelopmentStorage=true",
        "container": "samplefiles",
        "blob": "storm.csv",
    }
