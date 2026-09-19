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
from fastapi import HTTPException
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
from apps.api_server.config import get_settings
from apps.api_server.routers.data_map import DataSource
from apps.privacy_policy import parse_egress_destination
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
from tests.go_live_behavior_contract import P0_METRIC_BUDGETS, P2_METRIC_BUDGETS
from tests.integration.connector_validation_catalog import PUBLIC_VALIDATION_CASES
from tests.integration.live_local_surface_env import configure_local_live_server_env

DEFAULT_DB_URL_SYNC = os.environ.get("DATABASE_URL_SYNC", "postgresql://angel:@localhost:5432/decision_engine")
_AZURE_SAMPLE_BLOB_URL = "https://azureopendatastorage.blob.core.windows.net/mlsamples/diabetes/part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-bddf5f6d57ca-1951182-c000.snappy.parquet"

RESOLVE_MISS_CEILING_MS = 500.0
RESOLVED_QUERY_HIT_TARGET_MS = 50.0


async def _setup_mojo_runtime() -> str:
    """Initialize the shared Mojo runtime the same way FastAPI lifespan would."""
    try:
        from apps.api_server.compute.mojo_pool import MojoWorkerPool, set_pool

        pool = MojoWorkerPool(size=max(1, (os.cpu_count() or 4) - 1))
        await pool.start()
        if pool.running:
            set_pool(pool)
            return "pool"
    except Exception as exc:
        print(f"⚠️  Mojo pool init failed: {exc}", file=sys.stderr)

    try:
        from apps.api_server.compute.mojo_adapter import _BINARY_PATH

        if _BINARY_PATH.exists():
            return "subprocess"
    except Exception as exc:
        print(f"⚠️  Mojo subprocess probe failed: {exc}", file=sys.stderr)

    return "unavailable"


async def _teardown_mojo_runtime() -> None:
    """Stop any initialized Mojo pool and clear the global singleton."""
    try:
        from apps.api_server.compute.mojo_pool import get_pool_sync

        pool = get_pool_sync()
        if pool.running:
            await pool.stop()
    except Exception as exc:
        print(f"⚠️  Mojo pool teardown check failed: {exc}", file=sys.stderr)
    finally:
        try:
            from apps.api_server.compute.mojo_pool import set_pool

            set_pool(None)
        except Exception as exc:
            print(f"⚠️  Mojo pool singleton reset failed: {exc}", file=sys.stderr)


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


def _public_case_origin(case: Any, connection: dict[str, Any]) -> str:
    if case.docs_url:
        return case.docs_url
    connector_type = str(case.connector_type or "")
    if connector_type == "s3":
        bucket = str(connection.get("bucket", "")).strip()
        key = str(connection.get("key", "")).strip()
        return f"s3://{bucket}/{key}".rstrip("/")
    if connector_type == "gcs":
        bucket = str(connection.get("bucket", "")).strip()
        blob = str(connection.get("blob", "")).strip()
        return f"gs://{bucket}/{blob}".rstrip("/")
    if connector_type == "azure_blob":
        return str(connection.get("blob_url", "") or _AZURE_SAMPLE_BLOB_URL).strip()
    return str(connection.get("url", "") or "").strip()


def _public_case_category(case: Any) -> str:
    if str(case.connector_type or "") in {"s3", "gcs", "azure_blob"}:
        return "public_object"
    return "public_rest"


def _public_case_source_name(index: int, case: Any) -> str:
    prefix = "PublicObject" if _public_case_category(case) == "public_object" else "PublicRest"
    return f"{prefix}{index:02d}"


def _active_public_validation_cases() -> tuple[Any, ...]:
    return tuple(
        case
        for case in PUBLIC_VALIDATION_CASES
        if case.enabled_by_default and case.benchmark_enabled and case.is_configured()
    )


def _warm_public_validation_case(case: Any, connection: dict[str, Any]) -> None:
    records = case.load_runtime_records_for_connection(connection)
    if not isinstance(records, list):
        raise RuntimeError(f"{case.case_id} warmup did not return a record list")


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
    from sqlalchemy import create_engine
    from sqlalchemy.schema import CreateSchema

    df = pd.DataFrame(records)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            # DDL construct, not textual SQL: SQLAlchemy quotes the identifier itself.
            conn.execute(CreateSchema(schema, if_not_exists=True))
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
    expected_count: int | None,
) -> PreparedSourceCase:
    response = await register_source(RegisterRequest(source=source), auth=auth)
    if response["status"] not in {"registered", "already_registered"}:
        raise RuntimeError(f"{label} registration failed: {response}")
    schema = response["schema"]
    runtime_row_count = int(response.get("row_count") or schema.get("row_count") or 0)
    if expected_count is None:
        if runtime_row_count <= 0:
            raise RuntimeError(f"{label} registration returned no runtime row count anchor")
        expected_count = runtime_row_count
    dataset_id = str(response.get("dataset_id") or response.get("source_id") or "")
    canonical_entry = reg.get_source_entry(str(auth["org_id"]), dataset_id) if dataset_id else None
    canonical_source_name = (
        str(canonical_entry.get("name") or source.name) if canonical_entry else source.name
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


def _is_empty_source_error(exc: HTTPException) -> bool:
    detail = exc.detail
    if not isinstance(detail, dict):
        return False
    error = detail.get("error")
    if not isinstance(error, dict):
        return False
    return str(error.get("code", "")).strip() == "empty_source"


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
        csv_text = path.read_text(encoding="utf-8-sig", errors="replace")
        relative = path.relative_to(ROOT)
        try:
            prepared.append(
                await _register_case(
                    auth=auth,
                    label=f"Local CSV {relative}",
                    category="local_csv",
                    origin=str(relative),
                    source=DataSource(name=f"LocalCsv{index:03d}", csv=csv_text),
                    expected_count=None,
                )
            )
        except HTTPException as exc:
            if not _is_empty_source_error(exc):
                raise
            skipped_empty.append(str(relative))
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
                expected_count=None,
            )
        )

    for index, path in enumerate(_discover_local_workbook_paths(), start=1):
        workbook_b64 = base64.b64encode(path.read_bytes()).decode()
        try:
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
                    expected_count=None,
                )
            )
        except HTTPException as exc:
            if not _is_empty_source_error(exc):
                raise

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
    for index, case in enumerate(_active_public_validation_cases(), start=1):
        connection = case.build_connection()
        await asyncio.to_thread(_warm_public_validation_case, case, connection)
        prepared.append(
            await _register_case(
                auth=auth,
                label=case.label,
                category=_public_case_category(case),
                origin=_public_case_origin(case, connection),
                source=DataSource(
                    name=_public_case_source_name(index, case),
                    connection=connection,
                ),
                expected_count=None,
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
        QueryRequest(dataset_id=case.dataset_id, resolved_plan=resolved_first.resolved_plan),
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
        QueryRequest(dataset_id=case.dataset_id, resolved_plan=resolved_first.resolved_plan),
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
                "source_total_ms": round(case.register_ms + case.prewarm_ms, 3),
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
        "avg_source_total_ms": round(
            sum(item["source_total_ms"] for item in measurements) / len(measurements), 3
        ),
        "p95_source_total_ms": round(
            _percentile([item["source_total_ms"] for item in measurements], 95), 3
        ),
        "p95_resolve_miss_ms": round(
            _percentile([item["resolve_miss_ms"] for item in measurements], 95), 3
        ),
        "max_resolve_miss_ms": round(max(item["resolve_miss_ms"] for item in measurements), 3),
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
                f"{item['source_name']}={item['resolve_miss_ms']}ms" for item in slow_resolves[:10]
            )
        )

    if any(not item["exact_result_cache_hit"] for item in measurements):
        failures.append("missing exact result-cache hit on repeat query")
    if any(not item["resolve_cache_hit"] for item in measurements):
        failures.append("missing resolve-cache hit on repeat resolve")
    if any(not item["resolved_query_cache_hit"] for item in measurements):
        failures.append("missing result-cache hit on repeat resolved-plan query")

    resolve_hit_p95 = _percentile([item["resolve_hit_ms"] for item in measurements], 95)
    exact_hit_p95 = _percentile([item["exact_hit_ms"] for item in measurements], 95)
    resolved_query_hit_p95 = _percentile(
        [item["resolved_query_hit_ms"] for item in measurements],
        95,
    )
    slow_hot_paths = []
    if resolve_hit_p95 > float(P0_METRIC_BUDGETS["resolve_hit_ms"].p95 or 0.0):
        slow_hot_paths.append(f"resolve hit p95={resolve_hit_p95:.3f}ms")
    if exact_hit_p95 > float(P0_METRIC_BUDGETS["exact_hit_ms"].p95 or 0.0):
        slow_hot_paths.append(f"exact hit p95={exact_hit_p95:.3f}ms")
    if resolved_query_hit_p95 > RESOLVED_QUERY_HIT_TARGET_MS:
        slow_hot_paths.append(f"resolved query hit p95={resolved_query_hit_p95:.3f}ms")
    if slow_hot_paths:
        failures.append("hot-path latency target missed: " + ", ".join(slow_hot_paths))

    if failures:
        raise RuntimeError("; ".join(failures))


async def _run(
    include_processed_variants: bool,
    skip_public: bool,
    skip_db: bool,
    local_limit: int | None,
    csv_only: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="source-matrix-runtime-") as tmp_dir:
        workdir = Path(tmp_dir)
        configure_local_live_server_env(
            os.environ,
            root_dir=workdir,
            extra_hosts=(parse_egress_destination(DEFAULT_DB_URL_SYNC).normalized,),
        )
        get_settings.cache_clear()
        registry_dir = workdir / "registry"
        mojo_runtime_mode = await _setup_mojo_runtime()
        try:
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
            local_non_csv_cases = (
                [] if csv_only else await _prepare_local_non_csv_cases(auth=local_auth)
            )
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
        finally:
            await _teardown_mojo_runtime()

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
        "csv_only": csv_only,
        "mojo_runtime_mode": mojo_runtime_mode,
        "totals": {
            "sources": len(measurements),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "mojo_runtime_mode": mojo_runtime_mode,
            "avg_source_ms": round(
                sum(item["source_total_ms"] for item in measurements) / len(measurements),
                3,
            ),
            "p95_source_total_ms": round(
                _percentile([item["source_total_ms"] for item in measurements], 95),
                3,
            ),
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
            "p2_budgets": {
                "avg_source_ms_budget": P2_METRIC_BUDGETS["source_matrix.avg_source_ms"].p95,
                "p95_source_total_ms_budget": (
                    P2_METRIC_BUDGETS["source_matrix.p95_source_total_ms"].p95
                ),
            },
        },
        "categories": {
            name: _summarize_category(items) for name, items in sorted(categories.items())
        },
        "slowest_resolve_miss": sorted(
            measurements,
            key=lambda item: float(item["resolve_miss_ms"]),
            reverse=True,
        )[:10],
        "slowest_register": sorted(
            measurements,
            key=lambda item: float(item["register_ms"]),
            reverse=True,
        )[:10],
        "slowest_prewarm": sorted(
            measurements,
            key=lambda item: float(item["prewarm_ms"]),
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
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Benchmark only the local CSV corpus and skip local non-CSV sources.",
    )
    args = parser.parse_args()

    summary = asyncio.run(
        _run(
            include_processed_variants=args.include_processed_variants,
            skip_public=args.skip_public,
            skip_db=args.skip_db,
            local_limit=args.local_limit,
            csv_only=args.csv_only,
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
        print(f"  - {item['source_name']}: {item['resolve_miss_ms']}ms ({item['origin']})")
    print("\nSlowest registrations:")
    for item in summary["slowest_register"]:
        print(
            f"  - {item['source_name']}: register={item['register_ms']}ms "
            f"prewarm={item['prewarm_ms']}ms ({item['origin']})"
        )
    print("\nSlowest prewarms:")
    for item in summary["slowest_prewarm"]:
        print(
            f"  - {item['source_name']}: prewarm={item['prewarm_ms']}ms "
            f"register={item['register_ms']}ms ({item['origin']})"
        )


if __name__ == "__main__":
    main()
