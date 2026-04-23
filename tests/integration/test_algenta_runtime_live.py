"""
Live Python Runtime integration tests against a real API server.

This validates the published primary path:
  - local Runtime import/resolve/query on real repo CSVs
  - API-mode Runtime connect/resolve/verify/query on public REST, S3,
    SQLite, and Postgres descriptors

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \
    PYTHONPATH=. python3 tests/integration/test_algenta_runtime_live.py
"""
from __future__ import annotations

import os
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

socket.setdefaulttimeout(20)

ROOT = Path(__file__).resolve().parents[2]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
TEST_FILES = ROOT / "test_files"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# ruff: noqa: E402
from algenta import Runtime
from algenta.runtime import QueryOutput, ResolveOutput, SourceRegistration

from tests.integration.runtime_live_db_helpers import (
    postgres_canonical_connector,
    temporary_postgres_fixture,
)

BASE_URL = os.environ.get("DE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.environ.get("DE_API_KEY", "")

REAL_MARCH_ORDERS = (
    TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
)
REAL_MARCH_FINANCIAL = (
    TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
)
REAL_MARCH_INACCURATE = (
    TEST_FILES / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
)
REAL_LOCAL_PARQUET = TEST_FILES / ".algenta_cache" / "BookingsNew.parquet"
REAL_LOCAL_WORKBOOK = TEST_FILES / "QPL Price List_AAR_Expires 20241230.xlsx"

PUBLIC_S3_CONNECTION = {
    "type": "s3",
    "bucket": "noaa-global-hourly-pds",
    "key": "1901/02907099999.csv",
    "region": "us-east-1",
    "anonymous": True,
    "format": "csv",
}
PUBLIC_REST_CONNECTION = {
    "type": "rest",
    "base_url": "https://api.weather.gov",
    "path": "/stations",
    "method": "GET",
    "headers": {
        "User-Agent": "algenta-runtime-live/1.0",
        "Accept": "application/geo+json",
    },
    "params": {"state": "CO"},
    "data_path": "features",
    "timeout": 60,
}

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, str, str]] = []


def check(name: str, fn) -> Any:
    try:
        out = fn()
        results.append((PASS, name, ""))
        print(f"  {PASS} {name}")
        return out
    except AssertionError as exc:
        results.append((FAIL, name, str(exc)))
        print(f"  {FAIL} {name}: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        message = f"{type(exc).__name__}: {exc}"
        results.append((FAIL, name, message))
        print(f"  {FAIL} {name}: {message}")
        return None


def _preflight() -> None:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live Runtime integration.")
    response = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert response.status_code == 200, f"/v1/health returned {response.status_code}"


def _write_sqlite_fixture(path: Path) -> None:
    rows = [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]
    connection = sqlite3.connect(path)
    try:
        connection.execute('DROP TABLE IF EXISTS "orders"')
        connection.execute(
            'CREATE TABLE "orders" ("product_line" TEXT, "revenue" REAL, "region" TEXT)'
        )
        connection.executemany(
            'INSERT INTO "orders" ("product_line", "revenue", "region") VALUES (?, ?, ?)',
            [(row["product_line"], row["revenue"], row["region"]) for row in rows],
        )
        connection.commit()
    finally:
        connection.close()


def _postgres_fixture_rows() -> list[dict[str, object]]:
    return [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]


def _registration_metric_field(registration: SourceRegistration) -> str:
    fields = registration.source_schema.get("fields", []) if registration.source_schema else []
    if not fields and registration.source_schema:
        fields = [
            str(column.get("name"))
            for column in registration.source_schema.get("columns", [])
            if isinstance(column, dict) and isinstance(column.get("name"), str)
        ]
    if not fields:
        raise AssertionError("Registration returned no queryable schema fields.")
    return str(fields[0])


def _result_scalar_value(result: QueryOutput) -> float:
    value = result.result
    if isinstance(value, dict):
        return float(value.get("value"))
    return float(value)


def _local_numeric_metric_field(runtime: Runtime, registration: SourceRegistration) -> str:
    source = runtime._local_sources.get(registration.name or "")  # type: ignore[attr-defined]
    if source is None:
        raise AssertionError("Connected local source is missing from runtime state.")
    for field in source.fields:
        if any(isinstance(row.get(field), int | float) for row in source.records):
            return str(field)
    raise AssertionError("Connected local source has no numeric field for deterministic count.")


def _local_numeric_value_count(
    runtime: Runtime,
    registration: SourceRegistration,
    field: str,
) -> int:
    source = runtime._local_sources.get(registration.name or "")  # type: ignore[attr-defined]
    if source is None:
        raise AssertionError("Connected local source is missing from runtime state.")
    return sum(1 for row in source.records if isinstance(row.get(field), int | float))


def _count_query(
    runtime: Runtime,
    registration: SourceRegistration,
    *,
    metric_field: str | None = None,
) -> dict[str, Any]:
    plan = runtime.resolve(
        {
            "source_name": registration.name,
            "metric": metric_field or _registration_metric_field(registration),
            "aggregation": "count",
        }
    )
    assert isinstance(plan, ResolveOutput)
    verified = runtime.verify(plan)
    result = runtime.query(plan)
    return {
        "plan_hash": plan.plan_hash,
        "schema_revision": plan.schema_revision,
        "valid": verified.valid,
        "row_count": registration.row_count,
        "scalar": _result_scalar_value(result),
        "latency_ms": result.latency_ms,
    }


def run_local_runtime_real_csv_flow() -> None:
    runtime = Runtime()
    imported = runtime.import_preview(
        REAL_MARCH_ORDERS,
        name="orders_detail",
        source_ref=REAL_MARCH_ORDERS.name,
    )
    metric_field = _local_numeric_metric_field(runtime, imported.registration)
    expected_count = _local_numeric_value_count(runtime, imported.registration, metric_field)
    summary = _count_query(runtime, imported.registration, metric_field=metric_field)
    bundle = runtime.import_bundle_preview(
        [REAL_MARCH_ORDERS, REAL_MARCH_FINANCIAL, REAL_MARCH_INACCURATE],
        names=["orders_detail_bundle", "orders_financial_bundle", "top_inaccurate_items_bundle"],
        source_refs=[
            REAL_MARCH_ORDERS.name,
            REAL_MARCH_FINANCIAL.name,
            REAL_MARCH_INACCURATE.name,
        ],
    )

    assert imported.registration.status == "ready"
    assert imported.registration.row_count is not None
    assert imported.registration.row_count > 0
    assert summary["valid"] is True
    assert float(summary["scalar"]) == float(expected_count)
    assert "Algenta Source Import" in imported.preview
    assert "Origin:" in imported.preview
    assert REAL_MARCH_ORDERS.stem in imported.preview

    assert len(bundle.registrations) == 3
    assert not bundle.failures
    assert "Algenta Source Bundle" in bundle.preview
    assert "orders_detail_bundle" in bundle.preview
    assert "orders_financial_bundle" in bundle.preview
    assert "top_inaccurate_items_bundle" in bundle.preview


def run_local_runtime_real_file_matrix() -> None:
    runtime = Runtime()

    parquet_import = runtime.import_preview(
        REAL_LOCAL_PARQUET,
        name="bookings_parquet",
        source_ref=REAL_LOCAL_PARQUET.name,
    )
    parquet_metric = _local_numeric_metric_field(runtime, parquet_import.registration)
    parquet_expected_count = _local_numeric_value_count(
        runtime,
        parquet_import.registration,
        parquet_metric,
    )
    parquet_summary = _count_query(
        runtime,
        parquet_import.registration,
        metric_field=parquet_metric,
    )

    workbook_import = runtime.import_preview(
        REAL_LOCAL_WORKBOOK,
        name="qpl_workbook",
        source_ref=REAL_LOCAL_WORKBOOK.name,
    )
    workbook_metric = _local_numeric_metric_field(runtime, workbook_import.registration)
    workbook_expected_count = _local_numeric_value_count(
        runtime,
        workbook_import.registration,
        workbook_metric,
    )
    workbook_summary = _count_query(
        runtime,
        workbook_import.registration,
        metric_field=workbook_metric,
    )

    assert parquet_import.registration.row_count is not None
    assert parquet_import.registration.row_count > 0
    assert parquet_import.registration.name == "bookings_parquet"
    assert "Algenta Source Import" in parquet_import.preview
    assert REAL_LOCAL_PARQUET.name in parquet_import.preview
    assert parquet_summary["valid"] is True
    assert float(parquet_summary["scalar"]) == float(parquet_expected_count)

    assert workbook_import.registration.row_count is not None
    assert workbook_import.registration.row_count > 0
    assert workbook_import.registration.name == "qpl_workbook"
    assert "Algenta Source Import" in workbook_import.preview
    assert REAL_LOCAL_WORKBOOK.name in workbook_import.preview
    assert workbook_summary["valid"] is True
    assert float(workbook_summary["scalar"]) == float(workbook_expected_count)


def run_api_runtime_connector_matrix() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)
    with tempfile.TemporaryDirectory(prefix="algenta-runtime-live-") as tmp_dir:
        sqlite_path = Path(tmp_dir) / "orders.db"
        _write_sqlite_fixture(sqlite_path)
        sqlite_descriptor = {
            "type": "sqlite",
            "path": str(sqlite_path.resolve()),
            "table": "orders",
        }
        with temporary_postgres_fixture(
            _postgres_fixture_rows(),
            table="orders",
        ) as postgres_descriptor:
            postgres_connector = postgres_canonical_connector(postgres_descriptor)
            rest_registration = runtime.connect(PUBLIC_REST_CONNECTION, name="weather_stations")
            rest = _count_query(runtime, rest_registration)

            imported = runtime.import_preview(
                PUBLIC_S3_CONNECTION,
                name="noaa_hourly",
                source_ref="s3://noaa-global-hourly-pds/1901/02907099999.csv",
            )
            s3 = _count_query(runtime, imported.registration)

            sqlite_registration = runtime.connect(sqlite_descriptor, name="orders_sqlite")
            sqlite = _count_query(runtime, sqlite_registration)

            postgres_registration = runtime.connect(
                postgres_connector,
                name="orders_postgres",
            )
            postgres = _count_query(runtime, postgres_registration)

            bundle = runtime.import_bundle_preview(
                [
                    sqlite_descriptor,
                    postgres_connector,
                    PUBLIC_S3_CONNECTION,
                    PUBLIC_REST_CONNECTION,
                ],
                names=[
                    "orders_sqlite_bundle",
                    "orders_postgres_bundle",
                    "noaa_hourly_bundle",
                    "weather_stations_bundle",
                ],
                source_refs=[
                    f"{sqlite_path.name}#orders",
                    f"postgres://{postgres_descriptor['schema']}.{postgres_descriptor['table']}",
                    "s3://noaa-global-hourly-pds/1901/02907099999.csv",
                    "https://api.weather.gov/stations?state=CO",
                ],
            )

    assert rest["valid"] is True
    assert rest["row_count"] is not None
    assert rest["row_count"] > 0
    assert float(rest["scalar"]) == float(rest["row_count"])

    assert s3["valid"] is True
    assert s3["row_count"] is not None
    assert s3["row_count"] > 0
    assert float(s3["scalar"]) == float(s3["row_count"])
    assert "Algenta Source Import" in imported.preview
    assert "s3://noaa-global-hourly-pds/1901/02907099999.csv" in imported.preview

    assert sqlite["valid"] is True
    assert sqlite["row_count"] == 3
    assert float(sqlite["scalar"]) == 3.0

    assert postgres["valid"] is True
    assert postgres["row_count"] == 3
    assert float(postgres["scalar"]) == 3.0

    assert len(bundle.registrations) == 4
    assert not bundle.failures
    assert "Algenta Source Bundle" in bundle.preview
    assert "orders_sqlite_bundle" in bundle.preview
    assert "orders_postgres_bundle" in bundle.preview
    assert "noaa_hourly_bundle" in bundle.preview
    assert "weather_stations_bundle" in bundle.preview


def main() -> int:
    print("\n" + "=" * 70)
    print("  LIVE PYTHON RUNTIME INTEGRATION")
    print("=" * 70)

    _preflight()

    check("Local Runtime real CSV import/query path", run_local_runtime_real_csv_flow)
    check("Local Runtime real Parquet/Excel import/query path", run_local_runtime_real_file_matrix)
    check("API Runtime connector matrix", run_api_runtime_connector_matrix)

    failed = [result for result in results if result[0] == FAIL]
    print("\n" + "=" * 70)
    print(f"Passed: {len(results) - len(failed)}")
    print(f"Failed: {len(failed)}")
    if failed:
        print("Failures:")
        for _, name, message in failed:
            print(f"  - {name}: {message}")
    print("=" * 70)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
