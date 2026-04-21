#!/usr/bin/env python3
# ruff: noqa: E402
"""
Real source-matrix runtime benchmark for breadth, correctness, and speed.

Coverage goals:
- register the repo's local CSV corpus through the real source registry
- exercise local SQLite and Postgres connector-backed sources
- exercise trusted public object-storage and REST sources
- validate exact count queries and resolve -> query correctness
- measure warm/hot latency separately from registration

This benchmark is intentionally breadth-first and speed-aware:
- registration is done once up front for each matrix segment
- execution uses count aggregates to keep the breadth run deterministic
- resolve must stay bounded and never exceed the hard latency ceiling
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import math
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).parent.parent
TEST_FILES = ROOT / "test_files"
_LOCAL_PARQUET_CACHE_DIR = TEST_FILES / ".algenta_cache"
_LOCAL_WORKBOOKS = (
    "2024.08.13 Leach Part Master.xlsx",
    "AAR Electronics - Part Number Master.xlsx",
    "Distribution Price List_AAR_Expires 20250401_Revised 20241120.xlsx",
    "Electronics CAGE Codes.xlsx",
    "Grayhill - Full Price Book - 01-01-24.xlsx",
    "QPL Price List_AAR_Expires 20241230.xlsx",
    "Server Performance Current Month - Full 0415_917 AM.xlsx",
)
_LOCAL_PARQUET_FILES = (
    "Backlog.parquet",
    "Bookings.parquet",
    "BookingsNew.parquet",
    "Inventory.parquet",
    "POS.parquet",
    "POSNew.parquet",
    "Quotes.parquet",
    "QuotesNew.parquet",
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.connectors.file_connector import FileConnector
from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.query import (
    _CACHE_LOCK,
    _DF_CACHE,
    _PLANNER_CACHE,
    _RESOLVE_CACHE,
    _RESULT_CACHE,
    _SOURCE_CACHE,
    _VERIFY_CACHE,
    MetricSpec,
    QueryRequest,
    ResolveRequest,
    _resolve_registered_intent,
    _select_count_anchor_column,
    query_sources,
)
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services import source_registry as reg
from apps.api_server.services.columnar_loader import records_to_arrow_table
from apps.api_server.services.data_coercion import parse_delimited_records
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from tests.integration.connector_validation_catalog import THIRD_PARTY_PUBLIC_CASES

DEFAULT_DB_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://angel:@localhost:5432/decision_engine",
)
_AZURE_SAMPLE_BLOB_URL = (
    "https://azureopendatastorage.blob.core.windows.net/"
    "mlsamples/diabetes/"
    "part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-"
    "bddf5f6d57ca-1951182-c000.snappy.parquet"
)

RESOLVE_MISS_CEILING_MS = 500.0
HOT_PATH_TARGET_MS = 50.0


@dataclass(frozen=True)
class PreparedSourceCase:
    label: str
    category: str
    origin: str
    source_name: str
    dataset_id: str
    metric_column: str
    metric_role: str
    expected_count: int
    register_ms: float
    prewarm_ms: float
    schema_columns: int


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil((pct / 100.0) * len(ordered)) - 1)
    return float(ordered[min(rank, len(ordered) - 1)])


def _as_scalar_count(result: Any) -> float:
    if isinstance(result, dict) and "value" in result:
        return float(result["value"])
    return float(result)


_COUNT_ROLE_PRIORITY = (
    "identifier",
    "base_measure",
    "metric",
    "derived_measure",
    "unit_measure",
    "text",
    "category",
    "time",
)


def _choose_count_target(schema: dict[str, Any]) -> tuple[str, str]:
    columns = schema.get("columns", [])
    normalized: list[dict[str, Any]] = []
    for column in columns:
        name = str(column.get("name", "")).strip()
        if name:
            normalized.append(column)
    if not normalized:
        raise RuntimeError(f"No usable schema columns found: {schema}")

    for role in _COUNT_ROLE_PRIORITY:
        for column in normalized:
            if str(column.get("role", "")).strip() == role:
                return str(column["name"]), role

    first = normalized[0]
    fallback_role = str(first.get("role", "")).strip() or "metric"
    if fallback_role not in _COUNT_ROLE_PRIORITY:
        fallback_role = "metric"
    return str(first["name"]), fallback_role


def _discover_local_csv_paths(
    include_processed_variants: bool,
    *,
    local_limit: int | None = None,
) -> list[Path]:
    paths = sorted(TEST_FILES.glob("*.csv"))
    if include_processed_variants:
        paths.extend(sorted((TEST_FILES / "Processed").glob("*.csv")))
    if local_limit is not None:
        return paths[: max(local_limit, 0)]
    return paths


def _discover_local_workbook_paths() -> list[Path]:
    return [path for path in (TEST_FILES / name for name in _LOCAL_WORKBOOKS) if path.exists()]


def _discover_local_parquet_paths() -> list[Path]:
    return [
        path
        for path in (_LOCAL_PARQUET_CACHE_DIR / name for name in _LOCAL_PARQUET_FILES)
        if path.exists()
    ]


def _parse_csv_records(
    path: Path,
    *,
    allow_empty: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    records = parse_delimited_records(text, delimiter=",", sniff=True)
    if not records and not allow_empty:
        raise RuntimeError(f"{path} parsed to zero records")
    return text, records


def _fetch_public_s3_records() -> list[dict[str, Any]]:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED), region_name="us-east-1")
    body = s3.get_object(Bucket="noaa-global-hourly-pds", Key="1901/02907099999.csv")["Body"].read()
    text = body.decode("utf-8", errors="replace")
    return parse_delimited_records(text, delimiter=",", sniff=True)


def _fetch_public_gcs_records() -> list[dict[str, Any]]:
    from google.cloud import storage

    client = storage.Client.create_anonymous_client()
    body = (
        client.bucket("cloud-samples-data")
        .blob("bigquery/sample-transactions/transactions.csv")
        .download_as_bytes()
    )
    text = body.decode("utf-8", errors="replace")
    return parse_delimited_records(text, delimiter=",", sniff=True)


def _fetch_public_azure_records() -> list[dict[str, Any]]:
    from azure.storage.blob import BlobClient

    body = BlobClient.from_blob_url(_AZURE_SAMPLE_BLOB_URL).download_blob().readall()
    initialize_pyarrow_parquet_runtime()
    table = pq.read_table(io.BytesIO(body))
    return table.to_pylist()


def _create_sqlite_fixture(records: list[dict[str, Any]], path: Path, *, table_name: str) -> None:
    df = pd.DataFrame(records)
    with sqlite3.connect(path) as conn:
        df.to_sql(table_name, conn, if_exists="replace", index=False)


def _create_postgres_fixture(
    records: list[dict[str, Any]],
    database_url: str,
    *,
    schema: str,
    table: str,
) -> str:
    from sqlalchemy import create_engine, text

    df = pd.DataFrame(records)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        df.to_sql(table, engine, schema=schema, if_exists="replace", index=False)
    finally:
        engine.dispose()
    return f"{schema}.{table}"


async def _reset_runtime_state(registry_dir: Path) -> None:
    reg._SOURCES_DIR = registry_dir
    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _DF_CACHE.clear()
    _PLANNER_CACHE.clear()
    _RESULT_CACHE.clear()
    _RESOLVE_CACHE.clear()
    _VERIFY_CACHE.clear()


async def _register_case(
    *,
    auth: dict[str, str],
    label: str,
    category: str,
    origin: str,
    source: DataSource,
    expected_count: int,
) -> PreparedSourceCase:
    response = await register_source(RegisterRequest(source=source), auth=auth)
    if response["status"] not in {"registered", "already_registered"}:
        raise RuntimeError(f"{label} registration failed: {response}")
    schema = response["schema"]
    dataset_id = str(response.get("dataset_id") or response.get("source_id") or "")
    canonical_entry = reg.get_source_entry(str(auth["org_id"]), dataset_id) if dataset_id else None
    canonical_source_name = (
        str(canonical_entry.get("name") or source.name)
        if canonical_entry
        else source.name
    )
    count_anchor = _select_count_anchor_column(schema)
    if count_anchor is not None:
        metric_column, metric_role = count_anchor
    else:
        metric_column, metric_role = _choose_count_target(schema)
    return PreparedSourceCase(
        label=label,
        category=category,
        origin=origin,
        source_name=canonical_source_name,
        dataset_id=dataset_id,
        metric_column=metric_column,
        metric_role=metric_role,
        expected_count=expected_count,
        register_ms=float(response.get("latency_ms", 0.0)),
        prewarm_ms=float(response.get("planner_prewarm_ms", 0.0)),
        schema_columns=len(schema.get("columns", [])),
    )


async def _prepare_local_csv_cases(
    *,
    auth: dict[str, str],
    include_processed_variants: bool,
    local_limit: int | None,
) -> tuple[list[PreparedSourceCase], list[str]]:
    prepared: list[PreparedSourceCase] = []
    skipped_empty: list[str] = []
    for index, path in enumerate(
        _discover_local_csv_paths(
            include_processed_variants,
            local_limit=local_limit,
        ),
        start=1,
    ):
        csv_text, records = _parse_csv_records(path, allow_empty=True)
        if not records:
            skipped_empty.append(str(path.relative_to(ROOT)))
            continue
        relative = path.relative_to(ROOT)
        prepared.append(
            await _register_case(
                auth=auth,
                label=f"Local CSV {relative}",
                category="local_csv",
                origin=str(relative),
                source=DataSource(name=f"LocalCsv{index:03d}", csv=csv_text),
                expected_count=len(records),
            )
        )
    return prepared, skipped_empty


async def _prepare_local_non_csv_cases(*, auth: dict[str, str]) -> list[PreparedSourceCase]:
    prepared: list[PreparedSourceCase] = []

    backlog_text, backlog_records = _parse_csv_records(TEST_FILES / "Backlog.csv")
    del backlog_text

    prepared.append(
        await _register_case(
            auth=auth,
            label="Local JSON backlog payload",
            category="local_json",
            origin="test_files/Backlog.csv -> json_str",
            source=DataSource(
                name="LocalJsonBacklog",
                json_str=json.dumps(backlog_records),
            ),
            expected_count=len(backlog_records),
        )
    )

    backlog_table = records_to_arrow_table(backlog_records)
    backlog_buf = io.BytesIO()
    pq.write_table(backlog_table, backlog_buf)
    prepared.append(
        await _register_case(
            auth=auth,
            label="Local Parquet backlog payload",
            category="local_parquet",
            origin="test_files/Backlog.csv -> parquet_b64",
            source=DataSource(
                name="LocalParquetBacklog",
                parquet_b64=base64.b64encode(backlog_buf.getvalue()).decode(),
            ),
            expected_count=len(backlog_records),
        )
    )

    for index, path in enumerate(_discover_local_parquet_paths(), start=1):
        parquet_bytes = path.read_bytes()
        initialize_pyarrow_parquet_runtime()
        table = pq.read_table(io.BytesIO(parquet_bytes))
        prepared.append(
            await _register_case(
                auth=auth,
                label=f"Local parquet cache {path.name}",
                category="local_parquet_file",
                origin=str(path.relative_to(ROOT)),
                source=DataSource(
                    name=f"LocalParquetFile{index:02d}",
                    parquet_b64=base64.b64encode(parquet_bytes).decode(),
                ),
                expected_count=table.num_rows,
            )
        )

    for index, path in enumerate(_discover_local_workbook_paths(), start=1):
        workbook_b64 = base64.b64encode(path.read_bytes()).decode()
        workbook_records = await FileConnector(
            {"file_type": "excel", "content": workbook_b64}
        ).fetch_data()
        if not workbook_records:
            continue
        prepared.append(
            await _register_case(
                auth=auth,
                label=f"Local workbook {path.name}",
                category="local_excel",
                origin=str(path.relative_to(ROOT)),
                source=DataSource(
                    name=f"LocalWorkbook{index:02d}",
                    excel_b64=workbook_b64,
                ),
                expected_count=len(workbook_records),
            )
        )

    return prepared


async def _prepare_db_cases(
    *,
    auth: dict[str, str],
    workdir: Path,
) -> list[PreparedSourceCase]:
    backlog_text, backlog_records = _parse_csv_records(TEST_FILES / "Backlog.csv")
    del backlog_text

    sqlite_path = workdir / "source_matrix_backlog.db"
    _create_sqlite_fixture(backlog_records, sqlite_path, table_name="backlog_matrix")

    postgres_schema = "algenta_source_matrix"
    postgres_table_name = "backlog_matrix"
    postgres_table = _create_postgres_fixture(
        backlog_records,
        DEFAULT_DB_URL_SYNC,
        schema=postgres_schema,
        table=postgres_table_name,
    )

    sqlite_case = await _register_case(
        auth=auth,
        label="SQLite backlog connection",
        category="database",
        origin=str(sqlite_path),
        source=DataSource(
            name="MatrixSqliteBacklog",
            connection={
                "type": "sql",
                "connection_string": f"sqlite+pysqlite:///{sqlite_path}",
                "query": 'SELECT * FROM "backlog_matrix"',
            },
        ),
        expected_count=len(backlog_records),
    )
    postgres_case = await _register_case(
        auth=auth,
        label="Postgres backlog connection",
        category="database",
        origin=postgres_table,
        source=DataSource(
            name="MatrixPostgresBacklog",
            connection={
                "type": "sql",
                "connection_string": DEFAULT_DB_URL_SYNC.replace(
                    "postgresql://",
                    "postgresql+psycopg2://",
                ),
                "query": 'SELECT * FROM "algenta_source_matrix"."backlog_matrix"',
            },
        ),
        expected_count=len(backlog_records),
    )
    return [sqlite_case, postgres_case]


async def _prepare_public_cases(*, auth: dict[str, str]) -> list[PreparedSourceCase]:
    prepared: list[PreparedSourceCase] = []

    public_object_cases = [
        (
            "Public S3 NOAA hourly sample",
            "public_object",
            "s3://noaa-global-hourly-pds/1901/02907099999.csv",
            DataSource(
                name="PublicS3Noaa",
                connection={
                    "type": "s3",
                    "bucket": "noaa-global-hourly-pds",
                    "key": "1901/02907099999.csv",
                    "region": "us-east-1",
                    "anonymous": True,
                    "file_type": "csv",
                },
            ),
            _fetch_public_s3_records,
        ),
        (
            "Public GCS sample transactions",
            "public_object",
            "gs://cloud-samples-data/bigquery/sample-transactions/transactions.csv",
            DataSource(
                name="PublicGcsTransactions",
                connection={
                    "type": "gcs",
                    "bucket": "cloud-samples-data",
                    "blob": "bigquery/sample-transactions/transactions.csv",
                    "anonymous": True,
                    "file_type": "csv",
                },
            ),
            _fetch_public_gcs_records,
        ),
        (
            "Public Azure ML sample parquet",
            "public_object",
            _AZURE_SAMPLE_BLOB_URL,
            DataSource(
                name="PublicAzureMlSample",
                connection={
                    "type": "azure_blob",
                    "account_url": "https://azureopendatastorage.blob.core.windows.net",
                    "container": "mlsamples",
                    "blob": (
                        "diabetes/"
                        "part-00000-tid-6082354649623433283-5a3d3599-0872-"
                        "4a3e-a027-bddf5f6d57ca-1951182-c000.snappy.parquet"
                    ),
                    "blob_url": _AZURE_SAMPLE_BLOB_URL,
                    "anonymous": True,
                    "file_type": "parquet",
                },
            ),
            _fetch_public_azure_records,
        ),
    ]

    for label, category, origin, source, loader in public_object_cases:
        records = loader()
        prepared.append(
            await _register_case(
                auth=auth,
                label=label,
                category=category,
                origin=origin,
                source=source,
                expected_count=len(records),
            )
        )

    for index, case in enumerate(THIRD_PARTY_PUBLIC_CASES, start=1):
        records = case.load_expected_records()
        prepared.append(
            await _register_case(
                auth=auth,
                label=case.label,
                category="public_rest",
                origin=case.docs_url or case.connection.get("url", ""),
                source=DataSource(
                    name=f"PublicRest{index:02d}",
                    connection=case.build_connection(),
                ),
                expected_count=len(records),
            )
        )

    return prepared


async def _run_exact_query(
    *,
    auth: dict[str, str],
    case: PreparedSourceCase,
) -> tuple[float, float, bool]:
    _RESULT_CACHE.clear()

    request = QueryRequest(
        dataset_id=case.dataset_id,
        metric_column=case.metric_column,
        aggregation="count",
    )
    t0 = time.perf_counter()
    first = await query_sources(request, auth=auth)
    first_ms = (time.perf_counter() - t0) * 1000
    if not math.isclose(_as_scalar_count(first.result), float(case.expected_count), abs_tol=1e-9):
        raise RuntimeError(
            f"{case.label} exact count mismatch: expected {case.expected_count}, got {first.result}"
        )

    t0 = time.perf_counter()
    second = await query_sources(
        QueryRequest(
            dataset_id=case.dataset_id,
            metric_column=case.metric_column,
            aggregation="count",
        ),
        auth=auth,
    )
    second_ms = (time.perf_counter() - t0) * 1000
    cache_hit = any("Result cache HIT" in step for step in second.plan)
    return first_ms, second_ms, cache_hit


async def _run_resolve_query(
    *,
    auth: dict[str, str],
    case: PreparedSourceCase,
) -> tuple[float, float, float, float, bool, bool]:
    _RESOLVE_CACHE.clear()
    _RESULT_CACHE.clear()

    request = ResolveRequest(
        dataset_id=case.dataset_id,
        metric=MetricSpec(role=case.metric_role, hint=case.metric_column),
        aggregation="count",
        reject_on_ambiguity=True,
        include_explanation=False,
    )
    t0 = time.perf_counter()
    resolved_first = await _resolve_registered_intent(request, auth=auth, request_id=None)
    resolve_first_ms = (time.perf_counter() - t0) * 1000
    if resolved_first.resolved_plan is None:
        raise RuntimeError(
            f"{case.label} failed to resolve exact count plan: {resolved_first.rejection_reason}"
        )
    if resolved_first.resolved_plan.source_name != case.source_name:
        raise RuntimeError(
            f"{case.label} resolved to wrong source: {resolved_first.resolved_plan.source_name}"
        )

    t0 = time.perf_counter()
    resolved_second = await _resolve_registered_intent(request, auth=auth, request_id=None)
    resolve_second_ms = (time.perf_counter() - t0) * 1000
    resolve_cache_hit = any("Resolve cache HIT" in step for step in resolved_second.plan)

    t0 = time.perf_counter()
    query_first = await query_sources(
        QueryRequest(resolved_plan=resolved_first.resolved_plan),
        auth=auth,
    )
    query_first_ms = (time.perf_counter() - t0) * 1000
    actual_count = _as_scalar_count(query_first.result)
    if not math.isclose(actual_count, float(case.expected_count), abs_tol=1e-9):
        raise RuntimeError(
            f"{case.label} resolved-plan count mismatch: "
            f"expected {case.expected_count}, got {query_first.result}"
        )

    t0 = time.perf_counter()
    query_second = await query_sources(
        QueryRequest(resolved_plan=resolved_first.resolved_plan),
        auth=auth,
    )
    query_second_ms = (time.perf_counter() - t0) * 1000
    result_cache_hit = any("Result cache HIT" in step for step in query_second.plan)

    return (
        resolve_first_ms,
        resolve_second_ms,
        query_first_ms,
        query_second_ms,
        resolve_cache_hit,
        result_cache_hit,
    )


async def _measure_cases(
    *,
    auth: dict[str, str],
    prepared_cases: list[PreparedSourceCase],
) -> list[dict[str, Any]]:
    measurements: list[dict[str, Any]] = []
    for case in prepared_cases:
        exact_first_ms, exact_hit_ms, exact_result_cache_hit = await _run_exact_query(
            auth=auth,
            case=case,
        )
        (
            resolve_miss_ms,
            resolve_hit_ms,
            resolved_query_first_ms,
            resolved_query_hit_ms,
            resolve_cache_hit,
            resolved_query_cache_hit,
        ) = await _run_resolve_query(auth=auth, case=case)
        measurements.append(
            {
                "label": case.label,
                "category": case.category,
                "origin": case.origin,
                "source_name": case.source_name,
                "metric_column": case.metric_column,
                "metric_role": case.metric_role,
                "expected_count": case.expected_count,
                "schema_columns": case.schema_columns,
                "register_ms": round(case.register_ms, 3),
                "prewarm_ms": round(case.prewarm_ms, 3),
                "exact_first_ms": round(exact_first_ms, 3),
                "exact_hit_ms": round(exact_hit_ms, 3),
                "resolve_miss_ms": round(resolve_miss_ms, 3),
                "resolve_hit_ms": round(resolve_hit_ms, 3),
                "resolved_query_first_ms": round(resolved_query_first_ms, 3),
                "resolved_query_hit_ms": round(resolved_query_hit_ms, 3),
                "exact_result_cache_hit": exact_result_cache_hit,
                "resolve_cache_hit": resolve_cache_hit,
                "resolved_query_cache_hit": resolved_query_cache_hit,
            }
        )
    return measurements


def _summarize_category(measurements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sources": len(measurements),
        "avg_register_ms": round(
            sum(item["register_ms"] for item in measurements) / len(measurements), 3
        ),
        "p95_register_ms": round(
            _percentile([item["register_ms"] for item in measurements], 95), 3
        ),
        "avg_prewarm_ms": round(
            sum(item["prewarm_ms"] for item in measurements) / len(measurements), 3
        ),
        "p95_resolve_miss_ms": round(
            _percentile([item["resolve_miss_ms"] for item in measurements], 95), 3
        ),
        "max_resolve_miss_ms": round(
            max(item["resolve_miss_ms"] for item in measurements), 3
        ),
        "p95_resolve_hit_ms": round(
            _percentile([item["resolve_hit_ms"] for item in measurements], 95), 3
        ),
        "p95_exact_hit_ms": round(
            _percentile([item["exact_hit_ms"] for item in measurements], 95), 3
        ),
        "p95_resolved_query_hit_ms": round(
            _percentile([item["resolved_query_hit_ms"] for item in measurements], 95), 3
        ),
        "exact_result_cache_hits": sum(
            1 for item in measurements if item["exact_result_cache_hit"]
        ),
        "resolve_cache_hits": sum(1 for item in measurements if item["resolve_cache_hit"]),
        "resolved_query_cache_hits": sum(
            1 for item in measurements if item["resolved_query_cache_hit"]
        ),
    }


def _validate_measurements(measurements: list[dict[str, Any]]) -> None:
    failures: list[str] = []

    slow_resolves = [
        item for item in measurements if float(item["resolve_miss_ms"]) > RESOLVE_MISS_CEILING_MS
    ]
    if slow_resolves:
        failures.append(
            "resolve budget exceeded: "
            + ", ".join(
                f"{item['source_name']}={item['resolve_miss_ms']}ms"
                for item in slow_resolves[:10]
            )
        )

    if any(not item["exact_result_cache_hit"] for item in measurements):
        failures.append("missing exact result-cache hit on repeat query")
    if any(not item["resolve_cache_hit"] for item in measurements):
        failures.append("missing resolve-cache hit on repeat resolve")
    if any(not item["resolved_query_cache_hit"] for item in measurements):
        failures.append("missing result-cache hit on repeat resolved-plan query")

    hot_metrics = {
        "resolve hit": _percentile([item["resolve_hit_ms"] for item in measurements], 95),
        "exact hit": _percentile([item["exact_hit_ms"] for item in measurements], 95),
        "resolved query hit": _percentile(
            [item["resolved_query_hit_ms"] for item in measurements],
            95,
        ),
    }
    slow_hot_paths = [
        f"{label} p95={value:.3f}ms"
        for label, value in hot_metrics.items()
        if value > HOT_PATH_TARGET_MS
    ]
    if slow_hot_paths:
        failures.append("hot-path latency target missed: " + ", ".join(slow_hot_paths))

    if failures:
        raise RuntimeError("; ".join(failures))


async def _run(
    include_processed_variants: bool,
    skip_public: bool,
    skip_db: bool,
    local_limit: int | None,
) -> dict[str, Any]:
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="source-matrix-runtime-") as tmp_dir:
        workdir = Path(tmp_dir)
        registry_dir = workdir / "registry"
        await _reset_runtime_state(registry_dir)

        local_auth = {
            "org_id": f"source_matrix_local_{uuid.uuid4().hex[:8]}",
            "role": "owner",
            "key_id": str(uuid.uuid4()),
        }
        local_cases, skipped_empty_local_csvs = await _prepare_local_csv_cases(
            auth=local_auth,
            include_processed_variants=include_processed_variants,
            local_limit=local_limit,
        )
        local_non_csv_cases = await _prepare_local_non_csv_cases(auth=local_auth)
        local_measurements = await _measure_cases(
            auth=local_auth,
            prepared_cases=local_cases + local_non_csv_cases,
        )

        db_measurements: list[dict[str, Any]] = []
        if not skip_db:
            db_auth = {
                "org_id": f"source_matrix_db_{uuid.uuid4().hex[:8]}",
                "role": "owner",
                "key_id": str(uuid.uuid4()),
            }
            db_cases = await _prepare_db_cases(auth=db_auth, workdir=workdir)
            db_measurements = await _measure_cases(auth=db_auth, prepared_cases=db_cases)

        public_measurements: list[dict[str, Any]] = []
        if not skip_public:
            public_auth = {
                "org_id": f"source_matrix_public_{uuid.uuid4().hex[:8]}",
                "role": "owner",
                "key_id": str(uuid.uuid4()),
            }
            public_cases = await _prepare_public_cases(auth=public_auth)
            public_measurements = await _measure_cases(
                auth=public_auth,
                prepared_cases=public_cases,
            )

    measurements = local_measurements + db_measurements + public_measurements
    if not measurements:
        raise RuntimeError("no source-matrix cases were executed")
    _validate_measurements(measurements)

    categories: dict[str, list[dict[str, Any]]] = {}
    for item in measurements:
        categories.setdefault(item["category"], []).append(item)

    summary = {
        "benchmark": "source_matrix_runtime_benchmark",
        "local_csv_files": len(local_cases),
        "skipped_empty_local_csv_files": skipped_empty_local_csvs,
        "local_non_csv_sources": len(local_non_csv_cases),
        "database_sources": len(db_measurements),
        "public_sources": len(public_measurements),
        "include_processed_variants": include_processed_variants,
        "skip_public": skip_public,
        "skip_db": skip_db,
        "totals": {
            "sources": len(measurements),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "p95_resolve_miss_ms": round(
                _percentile([item["resolve_miss_ms"] for item in measurements], 95),
                3,
            ),
            "p95_resolve_hit_ms": round(
                _percentile([item["resolve_hit_ms"] for item in measurements], 95),
                3,
            ),
            "p95_exact_hit_ms": round(
                _percentile([item["exact_hit_ms"] for item in measurements], 95),
                3,
            ),
            "p95_resolved_query_hit_ms": round(
                _percentile([item["resolved_query_hit_ms"] for item in measurements], 95),
                3,
            ),
        },
        "categories": {
            name: _summarize_category(items)
            for name, items in sorted(categories.items())
        },
        "slowest_resolve_miss": sorted(
            measurements,
            key=lambda item: float(item["resolve_miss_ms"]),
            reverse=True,
        )[:10],
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Real source-matrix runtime benchmark")
    parser.add_argument(
        "--include-processed-variants",
        action="store_true",
        help="Include test_files/Processed/*.csv in addition to the root local CSV corpus.",
    )
    parser.add_argument(
        "--skip-public",
        action="store_true",
        help="Skip live public object and REST sources.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip local SQLite/Postgres connection cases.",
    )
    parser.add_argument(
        "--local-limit",
        type=int,
        default=None,
        help="Optional cap for debugging the local CSV matrix.",
    )
    args = parser.parse_args()

    summary = asyncio.run(
        _run(
            include_processed_variants=args.include_processed_variants,
            skip_public=args.skip_public,
            skip_db=args.skip_db,
            local_limit=args.local_limit,
        )
    )

    print("\nSource Matrix Runtime Benchmark")
    print("=" * 72)
    print(json.dumps(summary["totals"], indent=2))
    print()
    for name, item in summary["categories"].items():
        print(
            f"{name:<13} "
            f"sources={item['sources']:<3} "
            f"p95_resolve_miss_ms={item['p95_resolve_miss_ms']:<8} "
            f"p95_resolve_hit_ms={item['p95_resolve_hit_ms']:<8} "
            f"p95_exact_hit_ms={item['p95_exact_hit_ms']:<8} "
            f"p95_resolved_query_hit_ms={item['p95_resolved_query_hit_ms']:<8}"
        )
    print("\nSlowest resolve misses:")
    for item in summary["slowest_resolve_miss"]:
        print(
            f"  - {item['source_name']}: {item['resolve_miss_ms']}ms "
            f"({item['origin']})"
        )


if __name__ == "__main__":
    main()
