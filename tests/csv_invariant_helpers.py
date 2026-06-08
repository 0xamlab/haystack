from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import uuid
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.ipc as pa_ipc

from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.query import (
    _CACHE_LOCK,
    _DF_CACHE,
    _PLANNER_CACHE,
    _RESOLVE_CACHE,
    _RESULT_CACHE,
    _SOURCE_CACHE,
    _VERIFY_CACHE,
    QueryRequest,
    _select_count_anchor_column,
    query_sources,
)
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services import source_registry as reg
from apps.api_server.services.columnar_loader import (
    _choose_delimiter,
    delimited_text_to_arrow_table,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import (
    canonicalize_delimited_headers,
    coerce_scalar,
    is_identifier_field,
    looks_like_header_alias_row,
)
from tests.go_live_behavior_contract import schema_fingerprint

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = ROOT / "test_files"

CsvParseMode = Literal["strict", "multiline", "salvage"]


@dataclass(frozen=True)
class CsvParseReport:
    mode: CsvParseMode
    rows_read: int
    rows_emitted: int
    rows_rejected: int
    rejection_reasons: dict[str, int]
    header_detected: bool
    delimiter_detected: str


@dataclass(frozen=True)
class CsvLoadResult:
    rows: list[dict[str, Any]] | None
    row_count: int
    columns: tuple[str, ...]
    schema_columns: list[dict[str, str]]
    schema_hash: str
    row_order_hash: str
    report: CsvParseReport


@dataclass(frozen=True)
class GeneratedCsvCase:
    name: str
    delimiter: str
    content: str
    headers_present: bool
    successful_modes: tuple[CsvParseMode, ...]
    registration_modes: tuple[CsvParseMode, ...] = ()
    round_trip_modes: tuple[CsvParseMode, ...] = ()
    malformed: bool = False
    notes: str = ""


@dataclass(frozen=True)
class RegistrationCheckResult:
    dataset_id: str
    loader_count: int
    query_count: int
    schema_columns: list[dict[str, str]]
    schema_hash: str
    registered_schema_columns: list[dict[str, str]]
    registered_schema_hash: str
    count_anchor: str


@dataclass(frozen=True)
class IdentifierPreservationIssue:
    column: str
    physical_type: str
    reason: str


class CsvModeError(ValueError):
    def __init__(self, code: str, message: str, report: CsvParseReport) -> None:
        super().__init__(message)
        self.code = code
        self.report = report


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in sorted(value.items())}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return str(value)


def _stable_json(value: Any) -> str:
    return json.dumps(_json_ready(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _schema_columns_from_table(table: Any) -> list[dict[str, str]]:
    return [
        {
            "name": str(schema_field.name),
            "physical_type": str(schema_field.type),
        }
        for schema_field in table.schema
    ]


def schema_hash_from_table(table: Any) -> str:
    return schema_fingerprint(_schema_columns_from_table(table))


def stable_row_order_hash(rows: list[dict[str, Any]]) -> str:
    normalized_rows = [
        {str(key): _json_ready(value) for key, value in sorted(row.items())} for row in rows
    ]
    return _hash_text(_stable_json(normalized_rows))


def stable_table_hash(table: pa.Table) -> str:
    sink = pa.BufferOutputStream()
    with pa_ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()


def discover_csv_paths(*, include_processed_variants: bool = False) -> list[Path]:
    paths = sorted(TEST_FILES.glob("*.csv"))
    if include_processed_variants:
        paths.extend(sorted((TEST_FILES / "Processed").glob("*.csv")))
    return paths


def load_regression_csv(text: str) -> CsvLoadResult:
    table = delimited_text_to_arrow_table(text, delimiter=",", sniff=True)
    schema_columns = _schema_columns_from_table(table)
    return CsvLoadResult(
        rows=None,
        row_count=table.num_rows,
        columns=tuple(table.column_names),
        schema_columns=schema_columns,
        schema_hash=schema_fingerprint(schema_columns),
        row_order_hash=stable_table_hash(table),
        report=CsvParseReport(
            mode="multiline",
            rows_read=table.num_rows,
            rows_emitted=table.num_rows,
            rows_rejected=0,
            rejection_reasons={},
            header_detected=bool(table.column_names),
            delimiter_detected=_choose_delimiter(text.lstrip("\ufeff"), delimiter=",", sniff=True),
        ),
    )


def _identifier_headers_with_values(text: str, *, delimiter: str) -> dict[str, bool]:
    normalized = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(normalized), delimiter=delimiter)
    reader.fieldnames = canonicalize_delimited_headers(reader.fieldnames or [])
    first_row = next(reader, None)
    if first_row is None:
        return {}
    if looks_like_header_alias_row(
        list(reader.fieldnames or []),
        [first_row.get(field_name) for field_name in reader.fieldnames or []],
    ):
        rows_iter = reader
    else:
        rows_iter = chain((first_row,), reader)
    identifier_presence = {
        field_name: False
        for field_name in reader.fieldnames or []
        if is_identifier_field(field_name)
    }
    if not identifier_presence:
        return {}
    for row in rows_iter:
        for field_name, has_value in list(identifier_presence.items()):
            if has_value:
                continue
            raw_value = row.get(field_name)
            if raw_value is not None and str(raw_value).strip():
                identifier_presence[field_name] = True
        if all(identifier_presence.values()):
            break
    return identifier_presence


def identifier_preservation_issues(
    text: str,
    loaded: CsvLoadResult,
) -> list[IdentifierPreservationIssue]:
    delimiter = _choose_delimiter(text.lstrip("\ufeff"), delimiter=",", sniff=True)
    field_names = _identifier_headers_with_values(text, delimiter=delimiter)
    schema_types = {
        str(column["name"]): str(column["physical_type"]) for column in loaded.schema_columns
    }
    issues: list[IdentifierPreservationIssue] = []
    for field_name, has_non_empty_values in field_names.items():
        if not has_non_empty_values:
            continue
        physical_type = schema_types.get(field_name, "")
        if physical_type != "string":
            issues.append(
                IdentifierPreservationIssue(
                    column=field_name,
                    physical_type=physical_type,
                    reason="identifier-like column did not remain string",
                )
            )
    return issues


def _records_to_csv(
    rows: list[dict[str, Any]],
    *,
    columns: tuple[str, ...],
    delimiter: str,
) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if row.get(column) is None else row.get(column) for column in columns])
    return output.getvalue()


def load_generated_csv_case(case: GeneratedCsvCase, *, mode: CsvParseMode) -> CsvLoadResult:
    if mode not in {"strict", "multiline", "salvage"}:
        raise ValueError(f"Unsupported CSV parse mode: {mode}")

    normalized = case.content.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(normalized), delimiter=case.delimiter)
    first_row = next(reader, None)
    if first_row is None:
        report = CsvParseReport(
            mode=mode,
            rows_read=0,
            rows_emitted=0,
            rows_rejected=0,
            rejection_reasons={},
            header_detected=case.headers_present,
            delimiter_detected=case.delimiter,
        )
        return CsvLoadResult(
            rows=[],
            row_count=0,
            columns=(),
            schema_columns=[],
            schema_hash=schema_fingerprint([]),
            row_order_hash=stable_row_order_hash([]),
            report=report,
        )

    if case.headers_present:
        headers = tuple(canonicalize_delimited_headers(first_row))
        data_rows = list(reader)
    else:
        headers = tuple(f"column_{index + 1}" for index in range(len(first_row)))
        data_rows = [first_row, *list(reader)]

    records: list[dict[str, Any]] = []
    rows_read = 0
    rows_rejected = 0
    rejection_reasons: dict[str, int] = {}
    header_count = len(headers)

    for row in data_rows:
        rows_read += 1
        if len(row) != header_count:
            reason = "row_length_mismatch"
            if mode in {"strict", "multiline"}:
                report = CsvParseReport(
                    mode=mode,
                    rows_read=rows_read,
                    rows_emitted=len(records),
                    rows_rejected=rows_rejected + 1,
                    rejection_reasons={reason: 1},
                    header_detected=case.headers_present,
                    delimiter_detected=case.delimiter,
                )
                raise CsvModeError(reason, f"{case.name} contains a ragged row", report)
            rows_rejected += 1
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            continue

        if mode == "strict" and any(
            "\n" in value or "\r" in value for value in row if isinstance(value, str)
        ):
            reason = "multiline_value"
            report = CsvParseReport(
                mode=mode,
                rows_read=rows_read,
                rows_emitted=len(records),
                rows_rejected=rows_rejected + 1,
                rejection_reasons={reason: 1},
                header_detected=case.headers_present,
                delimiter_detected=case.delimiter,
            )
            raise CsvModeError(reason, f"{case.name} contains a multiline value", report)

        record = {
            header: coerce_scalar(header, value, preserve_identifiers=True)
            for header, value in zip(headers, row, strict=True)
        }
        records.append(record)

    if records:
        table = records_to_arrow_table(records, assume_coerced=True)
    else:
        table = pa.table(
            {
                header: pa.array(
                    [], type=pa.string() if is_identifier_field(header) else pa.string()
                )
                for header in headers
            }
        )
    rows = table.to_pylist()
    schema_columns = _schema_columns_from_table(table)
    report = CsvParseReport(
        mode=mode,
        rows_read=rows_read,
        rows_emitted=len(rows),
        rows_rejected=rows_rejected,
        rejection_reasons=dict(sorted(rejection_reasons.items())),
        header_detected=case.headers_present,
        delimiter_detected=case.delimiter,
    )
    return CsvLoadResult(
        rows=rows,
        row_count=len(rows),
        columns=tuple(table.column_names),
        schema_columns=schema_columns,
        schema_hash=schema_fingerprint(schema_columns),
        row_order_hash=stable_row_order_hash(rows),
        report=report,
    )


def round_trip_generated_case(
    case: GeneratedCsvCase,
    *,
    mode: CsvParseMode,
) -> tuple[CsvLoadResult, CsvLoadResult]:
    loaded = load_generated_csv_case(case, mode=mode)
    canonical_csv = _records_to_csv(loaded.rows, columns=loaded.columns, delimiter=case.delimiter)
    round_trip_case = GeneratedCsvCase(
        name=f"{case.name}_round_trip",
        delimiter=case.delimiter,
        content=canonical_csv,
        headers_present=True,
        successful_modes=(mode,),
        registration_modes=(),
        round_trip_modes=(),
    )
    reloaded = load_generated_csv_case(round_trip_case, mode=mode)
    return loaded, reloaded


def build_generated_csv_cases() -> list[GeneratedCsvCase]:
    wide_headers = [f"field_{index:03d}" for index in range(120)]
    wide_rows = [
        ",".join(wide_headers),
        *[
            ",".join(str(row_index + col_index) for col_index in range(120))
            for row_index in range(5)
        ],
    ]
    medium_rows = ["row_id,account_code,amount,ratio,status,region,qty,flag"]
    for index in range(200):
        medium_rows.append(
            f"R{index:03d},00{index:03d},{100 + index},{round((index % 10) / 10, 2)},"
            f"{'Open' if index % 2 == 0 else 'Closed'},R{index % 5},{index % 7},{'Y' if index % 3 == 0 else 'N'}"
        )

    return [
        GeneratedCsvCase(
            name="simple_numeric_comma",
            delimiter=",",
            content="order_id,amount,qty\nA100,10.5,2\nA101,12.0,4\n",
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="identifier_tab",
            delimiter="\t",
            content="part_number\tzip_code\tmeasure_total\n00123\t02108\t10\n00456\t02109\t20\n",
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="sparse_semicolon",
            delimiter=";",
            content="account_code;local_group;measure_total;ratio\n00123;g_a;10.5;0.4\n00456;;nan;0.6\n",
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="pipe_mixed",
            delimiter="|",
            content="customer_id|status|balance|notes\nC100|Open|101.5|ready\nC200|Closed|0|hold\n",
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="quoted_comma",
            delimiter=",",
            content='customer_id,customer_name,amount\nC100,"Smith, John",10\nC200,"Doe, Jane",12\n',
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="escaped_quotes",
            delimiter=",",
            content='record_id,description\nA1,"She said ""hello""" \nA2,"Normal text"\n',
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="multiline_quoted",
            delimiter=",",
            content='record_id,description,amount\nA1,"line one\nline two",10\nA2,"single line",20\n',
            headers_present=True,
            successful_modes=("multiline", "salvage"),
            registration_modes=("multiline",),
            round_trip_modes=("multiline",),
        ),
        GeneratedCsvCase(
            name="no_header_pipe",
            delimiter="|",
            content="A100|10|Open\nA101|20|Closed\n",
            headers_present=False,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=(),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="wide_120_columns",
            delimiter=",",
            content="\n".join(wide_rows) + "\n",
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="moderate_large_dataset",
            delimiter=",",
            content="\n".join(medium_rows) + "\n",
            headers_present=True,
            successful_modes=("strict", "multiline", "salvage"),
            registration_modes=("strict",),
            round_trip_modes=("strict",),
        ),
        GeneratedCsvCase(
            name="ragged_missing_fields",
            delimiter=",",
            content="record_id,amount,status\nA1,10,Open\nA2,11\nA3,12,Closed\n",
            headers_present=True,
            successful_modes=("salvage",),
            registration_modes=(),
            round_trip_modes=(),
            malformed=True,
        ),
        GeneratedCsvCase(
            name="ragged_extra_fields",
            delimiter=",",
            content="record_id,amount,status\nA1,10,Open\nA2,11,Closed,EXTRA\nA3,12,Open\n",
            headers_present=True,
            successful_modes=("salvage",),
            registration_modes=(),
            round_trip_modes=(),
            malformed=True,
        ),
    ]


async def reset_runtime_state(registry_dir: Path) -> None:
    reg._SOURCES_DIR = registry_dir
    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()
    _RESULT_CACHE.clear()
    _VERIFY_CACHE.clear()
    _DF_CACHE.clear()
    _RESOLVE_CACHE.clear()


async def register_csv_and_query_count(
    *,
    csv_text: str,
    source_name: str,
    auth: dict[str, str],
) -> RegistrationCheckResult:
    response = await register_source(
        RegisterRequest(source=DataSource(name=source_name, csv=csv_text)),
        auth=auth,
    )
    schema_meta = dict(response.get("schema") or {})
    count_anchor = _select_count_anchor_column(schema_meta)
    if count_anchor is None:
        raise RuntimeError(f"{source_name} did not produce a count anchor column")
    dataset_id = str(response.get("dataset_id") or response.get("source_id") or "")
    if not dataset_id:
        raise RuntimeError(f"{source_name} registration response did not include a dataset id")
    query_response = await query_sources(
        QueryRequest(dataset_id=dataset_id, metric_column=count_anchor[0], aggregation="count"),
        auth=auth,
    )
    result = query_response.result
    if isinstance(result, dict) and "value" in result:
        query_count = int(result["value"])
    else:
        query_count = int(result)
    loader_table = delimited_text_to_arrow_table(csv_text, delimiter=",", sniff=True)
    schema_columns = _schema_columns_from_table(loader_table)
    registered_schema_columns = [
        {
            "name": str(column.get("name", "")),
            "physical_type": str(column.get("physical_type", "")),
        }
        for column in (schema_meta.get("columns") or [])
        if str(column.get("name", "")).strip()
    ]
    return RegistrationCheckResult(
        dataset_id=dataset_id,
        loader_count=loader_table.num_rows,
        query_count=query_count,
        schema_columns=schema_columns,
        schema_hash=schema_fingerprint(schema_columns),
        registered_schema_columns=registered_schema_columns,
        registered_schema_hash=schema_fingerprint(registered_schema_columns),
        count_anchor=count_anchor[0],
    )


def temporary_registry_dir(prefix: str = "csv-invariants-") -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix=prefix)


def unique_auth(prefix: str) -> dict[str, str]:
    return {
        "org_id": f"{prefix}_{uuid.uuid4().hex[:8]}",
        "role": "owner",
        "key_id": str(uuid.uuid4()),
    }
