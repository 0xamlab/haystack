import base64
import io
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import apps.api_server.routers.data_map as data_map_router
import apps.api_server.services.columnar_loader as columnar_loader_module
import apps.api_server.services.source_artifact_cache as source_artifact_cache
from apps.api_server.connectors.file_connector import FileConnector
from apps.api_server.routers.data_map import DataSource, _load_source, _load_source_table
from apps.api_server.routers.query import _load_profiled_source, _source_cache_key
from apps.api_server.services.columnar_loader import (
    delimited_text_to_arrow_table,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import _coerce_text_scalar as real_coerce_text_scalar


def _serve_directory(path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


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


def test_source_cache_key_is_content_keyed_for_excel_and_parquet_payloads() -> None:
    excel_b64 = _tiny_excel_b64()
    excel_left = DataSource(name="ExcelLeft", excel_b64=excel_b64)
    excel_right = DataSource(name="ExcelRight", excel_b64=excel_b64)

    excel_left_key, excel_left_content = _source_cache_key(excel_left)
    excel_right_key, excel_right_content = _source_cache_key(excel_right)
    assert excel_left_content is True
    assert excel_right_content is True
    assert excel_left_key == excel_right_key

    parquet_buf = io.BytesIO()
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"entity_key": "A", "measure_total": 10.0},
                {"entity_key": "B", "measure_total": 20.0},
            ]
        ),
        parquet_buf,
    )
    parquet_b64 = base64.b64encode(parquet_buf.getvalue()).decode()
    parquet_left = DataSource(name="ParquetLeft", parquet_b64=parquet_b64)
    parquet_right = DataSource(name="ParquetRight", parquet_b64=parquet_b64)

    parquet_left_key, parquet_left_content = _source_cache_key(parquet_left)
    parquet_right_key, parquet_right_content = _source_cache_key(parquet_right)

    assert parquet_left_content is True
    assert parquet_right_content is True
    assert parquet_left_key == parquet_right_key


def test_records_to_arrow_table_does_not_recoerce_precoerced_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_coerce(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("coerce_scalar should not run for already-coerced rows")

    monkeypatch.setattr(
        "apps.api_server.services.columnar_loader.coerce_scalar",
        _unexpected_coerce,
    )

    table = records_to_arrow_table(
        [
            {"part_number": "00123", "measure_total": 10},
            {"part_number": "00456", "measure_total": 20},
        ],
        assume_coerced=True,
    )

    assert table.to_pylist() == [
        {"part_number": "00123", "measure_total": 10},
        {"part_number": "00456", "measure_total": 20},
    ]


@pytest.mark.asyncio
async def test_load_source_table_csv_preserves_identifier_columns_and_numeric_measures():
    src = DataSource(
        name="S0",
        csv=(
            "part_number,measure_total,zip_code,ratio\n"
            "00123,10,02108,0.5\n"
            "00456,20,02109,0.7\n"
        ),
    )

    table = await _load_source_table(src)

    rows = table.to_pylist()
    assert rows == [
        {"part_number": "00123", "measure_total": 10, "zip_code": "02108", "ratio": 0.5},
        {"part_number": "00456", "measure_total": 20, "zip_code": "02109", "ratio": 0.7},
    ]
    assert str(table.schema.field("part_number").type) == "string"
    assert str(table.schema.field("zip_code").type) == "string"
    assert str(table.schema.field("measure_total").type) in {"int64", "int32"}


@pytest.mark.asyncio
async def test_load_source_table_records_normalizes_blank_like_values_and_coerces_numbers():
    src = DataSource(
        name="S1",
        records=[
            {
                "account_code": "00123",
                "measure_total": "10.5",
                "local_group": "none",
                "ratio": "0.4",
            },
            {
                "account_code": "00456",
                "measure_total": "12.0",
                "local_group": "?",
                "ratio": "0.6",
            },
        ],
    )

    table = await _load_source_table(src)
    rows = table.to_pylist()

    assert rows == [
        {
            "account_code": "00123",
            "measure_total": 10.5,
            "local_group": None,
            "ratio": 0.4,
        },
        {
            "account_code": "00456",
            "measure_total": 12.0,
            "local_group": None,
            "ratio": 0.6,
        },
    ]


@pytest.mark.asyncio
async def test_load_profiled_source_prefers_columnar_for_arrow_friendly_csv():
    src = DataSource(
        name="S2",
        csv=(
            "part_number,measure_total,zip_code,ratio\n"
            "00123,10,02108,0.5\n"
            "00456,20,02109,0.7\n"
        ),
    )

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "columnar"
    assert loaded.row_count == 2
    assert loaded.arrow_table is not None
    assert loaded.profile["measure_total"]["is_numeric"] is True
    assert loaded.profile["part_number"]["is_numeric"] is False


@pytest.mark.asyncio
async def test_load_profiled_source_salvages_wide_csv_with_arrow_retry():
    headers = [f"col_{i:03d}" for i in range(97)]
    csv_text = ",".join(headers) + "\n" + ",".join(str(i) for i in range(97)) + "\n"
    src = DataSource(name="S3", csv=csv_text)

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "columnar"
    assert loaded.row_count == 1
    assert loaded.arrow_table is not None
    assert loaded.profile["col_000"]["is_numeric"] is True


@pytest.mark.asyncio
async def test_load_profiled_source_falls_back_to_rows_when_arrow_retry_still_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    src = DataSource(
        name="S4",
        csv="part_number,measure_total\n00123,10\n00456,20\n",
    )

    def _raise_arrow_parse(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ValueError("forced-arrow-failure")

    monkeypatch.setattr(data_map_router, "delimited_text_to_arrow_table", _raise_arrow_parse)

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "rows"
    assert loaded.row_count == 2
    assert loaded.arrow_table is not None
    assert loaded.profile["measure_total"]["is_numeric"] is True


@pytest.mark.asyncio
async def test_load_profiled_source_uses_columnar_retry_for_real_local_inventory_csv():
    csv_text = (
        Path(__file__).resolve().parents[1] / "test_files" / "Available_Inventory.csv"
    ).read_text(encoding="utf-8-sig", errors="replace")
    src = DataSource(name="RealInventoryCsv", csv=csv_text)

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "columnar"
    assert loaded.row_count == 5820
    assert loaded.arrow_table is not None
    assert loaded.profile["PART_NUMBER"]["is_numeric"] is False


@pytest.mark.parametrize(
    ("filename", "expected_rows", "expected_columns"),
    [
        ("POS.csv", 12504, 144),
        ("Quotes_Combined_20241116.csv", 33125, 79),
        ("pos_new.csv", 16730, 147),
        ("quotes_new.csv", 45237, 80),
    ],
)
def test_delimited_text_to_arrow_table_salvages_real_multiline_local_csvs(
    filename: str,
    expected_rows: int,
    expected_columns: int,
) -> None:
    csv_text = (
        Path(__file__).resolve().parents[1] / "test_files" / filename
    ).read_text(encoding="utf-8-sig", errors="replace")

    table = delimited_text_to_arrow_table(csv_text, delimiter=",", sniff=True)

    assert table.num_rows == expected_rows
    assert table.num_columns == expected_columns


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected_rows", "expected_columns"),
    [
        ("POS.csv", 12504, 144),
        ("Quotes_Combined_20241116.csv", 33125, 79),
        ("pos_new.csv", 16730, 147),
        ("quotes_new.csv", 45237, 80),
    ],
)
async def test_load_profiled_source_keeps_real_multiline_local_csvs_on_columnar_path(
    filename: str,
    expected_rows: int,
    expected_columns: int,
) -> None:
    csv_text = (
        Path(__file__).resolve().parents[1] / "test_files" / filename
    ).read_text(encoding="utf-8-sig", errors="replace")
    src = DataSource(name=f"RealLocalCsv::{filename}", csv=csv_text)

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "columnar"
    assert loaded.row_count == expected_rows
    assert loaded.arrow_table is not None
    assert loaded.arrow_table.num_columns == expected_columns


def test_delimited_text_to_arrow_table_ignores_ragged_extra_fields_without_crashing() -> None:
    table = delimited_text_to_arrow_table(
        "col_a,col_b,col_c\n1,2\n3,4,5,6\n",
        delimiter=",",
        sniff=True,
    )

    assert table.to_pylist() == [
        {"col_a": 1, "col_b": 2, "col_c": None},
        {"col_a": 3, "col_b": 4, "col_c": 5},
    ]


def test_delimited_text_to_arrow_table_makes_duplicate_headers_unique() -> None:
    table = delimited_text_to_arrow_table(
        "dup,dup,,\n1,2,3,4\n",
        delimiter=",",
        sniff=True,
    )

    assert table.schema.names == [
        "dup",
        "dup__2",
        "Unnamed_Column",
        "Unnamed_Column__2",
    ]
    assert table.to_pylist() == [
        {
            "dup": 1,
            "dup__2": 2,
            "Unnamed_Column": 3,
            "Unnamed_Column__2": 4,
        }
    ]


def test_delimited_text_to_arrow_table_python_fallback_still_returns_arrow_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyarrow.csv as pacsv

    calls = {"count": 0}

    def _raise_read_csv(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        raise pa.ArrowInvalid("forced parser failure")

    monkeypatch.setattr(pacsv, "read_csv", _raise_read_csv)

    table = delimited_text_to_arrow_table(
        "part_number,measure_total\n00123,10\n00456,20\n",
        delimiter=",",
        sniff=True,
    )

    assert calls["count"] >= 1
    assert table.to_pylist() == [
        {"part_number": "00123", "measure_total": 10},
        {"part_number": "00456", "measure_total": 20},
    ]


def test_delimited_text_to_arrow_table_python_fallback_reuses_per_column_coercions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyarrow.csv as pacsv

    calls: list[tuple[str, object]] = []

    def _raise_read_csv(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise pa.ArrowInvalid("forced parser failure")

    def _counting_coerce_text(
        field_name: str,
        value: str,
        *,
        preserve_identifiers: bool = True,
    ) -> object:
        calls.append((field_name, value))
        return real_coerce_text_scalar(
            field_name,
            value,
            preserve_identifiers=preserve_identifiers,
        )

    monkeypatch.setattr(pacsv, "read_csv", _raise_read_csv)
    monkeypatch.setattr(
        "apps.api_server.services.columnar_loader._coerce_text_scalar",
        _counting_coerce_text,
    )

    table = delimited_text_to_arrow_table(
        (
            "status,part_number,measure_total\n"
            "Open,00123,10\n"
            "Open,00123,10\n"
            "Open,00123,10\n"
        ),
        delimiter=",",
        sniff=True,
    )

    assert table.to_pylist() == [
        {"status": "Open", "part_number": "00123", "measure_total": 10},
        {"status": "Open", "part_number": "00123", "measure_total": 10},
        {"status": "Open", "part_number": "00123", "measure_total": 10},
    ]
    assert calls == [
        ("status", "Open"),
        ("measure_total", "10"),
    ]


def test_delimited_text_to_arrow_table_large_fallback_handles_real_quotes_new_with_pandas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyarrow.csv as pacsv

    csv_text = (
        Path(__file__).resolve().parents[1]
        / "test_files"
        / "quotes_new.csv"
    ).read_text(encoding="utf-8-sig", errors="replace")

    def _raise_read_csv(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise pa.ArrowInvalid("forced parser failure")

    def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("large malformed fallback should use pandas before python fallback")

    monkeypatch.setattr(pacsv, "read_csv", _raise_read_csv)
    monkeypatch.setattr(columnar_loader_module, "_PANDAS_FALLBACK_MIN_BYTES", 0)
    monkeypatch.setattr(
        columnar_loader_module,
        "_python_delimited_text_to_arrow_table",
        _should_not_run,
    )

    table = delimited_text_to_arrow_table(
        csv_text,
        delimiter=",",
        sniff=True,
    )

    assert table.num_rows == 45237
    assert table.num_columns == 80
    assert str(table.schema.field("CH_NUMBER").type) == "string"


def test_delimited_text_to_arrow_table_large_fallback_uses_pandas_c_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pandas as pd
    import pyarrow.csv as pacsv

    csv_text = (
        Path(__file__).resolve().parents[1]
        / "test_files"
        / "quotes_new.csv"
    ).read_text(encoding="utf-8-sig", errors="replace")

    read_csv_kwargs: dict[str, object] = {}
    real_read_csv = pd.read_csv

    def _raise_read_csv(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise pa.ArrowInvalid("forced parser failure")

    def _tracking_read_csv(*args, **kwargs):  # type: ignore[no-untyped-def]
        read_csv_kwargs.update(kwargs)
        return real_read_csv(*args, **kwargs)

    monkeypatch.setattr(pacsv, "read_csv", _raise_read_csv)
    monkeypatch.setattr(columnar_loader_module, "_PANDAS_FALLBACK_MIN_BYTES", 0)
    monkeypatch.setattr(pd, "read_csv", _tracking_read_csv)

    table = delimited_text_to_arrow_table(
        csv_text,
        delimiter=",",
        sniff=True,
    )

    assert table.num_rows == 45237
    assert read_csv_kwargs["engine"] == "c"
    assert read_csv_kwargs["low_memory"] is False


@pytest.mark.asyncio
async def test_load_source_table_excel_returns_arrow_table():
    src = DataSource(name="ExcelTiny", excel_b64=_tiny_excel_b64())

    table = await _load_source_table(src)

    assert table is not None
    assert table.to_pylist() == [
        {"part_number": "00123", "measure_total": 10, "region": "NE"},
        {"part_number": "00456", "measure_total": 20, "region": "SW"},
    ]


@pytest.mark.asyncio
async def test_load_source_table_reuses_persisted_csv_artifact_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", str(tmp_path))
    src = DataSource(
        name="CsvCached",
        csv="part_number,measure_total\n00123,10\n00456,20\n",
    )

    first_table = await _load_source_table(src)
    cache_key = source_artifact_cache.source_content_artifact_key(src)

    assert cache_key is not None
    assert (tmp_path / f"{cache_key}.parquet").exists()

    def _should_not_parse(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("cached inline CSV should not be reparsed")

    monkeypatch.setattr(data_map_router, "delimited_text_to_arrow_table", _should_not_parse)

    second_table = await _load_source_table(src)

    assert second_table.to_pylist() == first_table.to_pylist()


@pytest.mark.asyncio
async def test_load_source_table_reuses_persisted_excel_artifact_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", str(tmp_path))
    src = DataSource(name="ExcelCached", excel_b64=_tiny_excel_b64())

    first_table = await _load_source_table(src)
    cache_key = source_artifact_cache.source_content_artifact_key(src)

    assert cache_key is not None
    assert (tmp_path / f"{cache_key}.parquet").exists()

    async def _should_not_fetch(self):  # type: ignore[no-untyped-def]
        raise AssertionError("cached inline workbook should not refetch from connector")

    monkeypatch.setattr(FileConnector, "fetch_table", _should_not_fetch)

    second_table = await _load_source_table(src)

    assert second_table.to_pylist() == first_table.to_pylist()


@pytest.mark.asyncio
async def test_load_source_table_does_not_persist_artifacts_for_url_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", str(tmp_path))
    calls = {"count": 0}

    def _fake_read_url_text(_url: str) -> tuple[str, str]:
        calls["count"] += 1
        return "part_number,measure_total\n00123,10\n00456,20\n", "text/csv"

    monkeypatch.setattr(data_map_router, "_read_url_text", _fake_read_url_text)
    src = DataSource(name="UrlMutable", url="https://example.com/facts.csv")

    first_table = await _load_source_table(src)
    second_table = await _load_source_table(src)

    assert first_table.to_pylist() == second_table.to_pylist()
    assert calls["count"] == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_load_profiled_source_prefers_columnar_for_excel_b64():
    src = DataSource(name="ExcelTinyProfiled", excel_b64=_tiny_excel_b64())

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "columnar"
    assert loaded.row_count == 2
    assert loaded.arrow_table is not None
    assert loaded.profile["measure_total"]["is_numeric"] is True
    assert loaded.profile["part_number"]["is_numeric"] is False


@pytest.mark.asyncio
async def test_load_profiled_source_prefers_columnar_for_real_local_parquet_cache():
    parquet_bytes = (
        Path(__file__).resolve().parents[1]
        / "test_files"
        / ".algenta_cache"
        / "Backlog.parquet"
    ).read_bytes()
    src = DataSource(
        name="RealBacklogParquet",
        parquet_b64=base64.b64encode(parquet_bytes).decode(),
    )

    loaded = await _load_profiled_source(src)

    assert loaded.ingest_mode == "columnar"
    assert loaded.row_count == 1535
    assert loaded.arrow_table is not None
    assert loaded.profile["PART_NUMBER"]["is_numeric"] is False


@pytest.mark.asyncio
async def test_load_source_url_csv_uses_real_csv_http_path(tmp_path):
    data_dir = tmp_path / "http"
    data_dir.mkdir()
    (data_dir / "facts.csv").write_text(
        "part_number,measure_total\n00123,10\n00456,20\n",
        encoding="utf-8",
    )
    server = _serve_directory(data_dir)
    try:
        port = server.server_address[1]
        src = DataSource(name="UrlCsv", url=f"http://127.0.0.1:{port}/facts.csv")

        rows = await _load_source(src)

        assert rows == [
            {"part_number": "00123", "measure_total": 10},
            {"part_number": "00456", "measure_total": 20},
        ]
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_load_source_table_url_json_builds_arrow_table(tmp_path):
    data_dir = tmp_path / "http"
    data_dir.mkdir()
    (data_dir / "facts.json").write_text(
        json.dumps(
            [
                {"account_code": "00123", "measure_total": 10.5},
                {"account_code": "00456", "measure_total": 12.0},
            ]
        ),
        encoding="utf-8",
    )
    server = _serve_directory(data_dir)
    try:
        port = server.server_address[1]
        src = DataSource(name="UrlJson", url=f"http://127.0.0.1:{port}/facts.json")

        table = await _load_source_table(src)

        assert table.to_pylist() == [
            {"account_code": "00123", "measure_total": 10.5},
            {"account_code": "00456", "measure_total": 12.0},
        ]
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_load_source_source_id_reads_registered_parquet(tmp_path):
    from apps.api_server.services import source_registry as reg

    original_sources_dir = reg._SOURCES_DIR
    reg._SOURCES_DIR = tmp_path
    try:
        org_id = "org_source_id_rows"
        source_id = "src_rows_001"
        rows = [
            {"account_code": "00123", "measure_total": 10.5},
            {"account_code": "00456", "measure_total": 12.0},
        ]
        table = records_to_arrow_table(rows)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        reg.register_source(
            org_id,
            source_id,
            "RegisteredRows",
            buf.getvalue(),
            {
                "row_count": 2,
                "columns": [
                    {"name": "account_code", "role": "identifier"},
                    {"name": "measure_total", "role": "metric"},
                ],
                "roles_summary": {"identifier": 1, "metric": 1},
            },
            graph_nodes={},
            profile={},
        )

        src = DataSource(name="RegisteredRows", source_id=source_id)

        loaded_rows = await _load_source(src, org_id=org_id)

        assert loaded_rows == rows
    finally:
        reg._SOURCES_DIR = original_sources_dir


@pytest.mark.asyncio
async def test_load_source_table_source_id_reads_registered_parquet(tmp_path):
    from apps.api_server.services import source_registry as reg

    original_sources_dir = reg._SOURCES_DIR
    reg._SOURCES_DIR = tmp_path
    try:
        org_id = "org_source_id_table"
        source_id = "src_table_001"
        rows = [
            {"part_number": "00123", "measure_total": 10},
            {"part_number": "00456", "measure_total": 20},
        ]
        table = records_to_arrow_table(rows)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        reg.register_source(
            org_id,
            source_id,
            "RegisteredTable",
            buf.getvalue(),
            {
                "row_count": 2,
                "columns": [
                    {"name": "part_number", "role": "identifier"},
                    {"name": "measure_total", "role": "metric"},
                ],
                "roles_summary": {"identifier": 1, "metric": 1},
            },
            graph_nodes={},
            profile={},
        )

        src = DataSource(name="RegisteredTable", source_id=source_id)

        loaded_table = await _load_source_table(src, org_id=org_id)

        assert loaded_table.to_pylist() == rows
    finally:
        reg._SOURCES_DIR = original_sources_dir
