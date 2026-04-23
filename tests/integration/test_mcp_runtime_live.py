"""
Live MCP runtime compatibility tests against a real API server.

This validates the MCP data/query surface on the primary path using:
  - real repo CSV upload
  - live SQLite database descriptor selection/resume
  - live Postgres database descriptor selection/resume
  - public REST source
  - public S3 object source

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \
    PYTHONPATH=. python3 tests/integration/test_mcp_runtime_live.py
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import socket
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

socket.setdefaulttimeout(20)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("DE_API_KEY", "")
os.environ["ALGENTA_BASE_URL"] = BASE_URL
os.environ["ALGENTA_API_KEY"] = API_KEY

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
from apps.mcp_server.tools import data, query
from tests.integration.runtime_live_db_helpers import (
    postgres_canonical_connector,
    postgres_connection_config,
    temporary_postgres_fixture,
)

REAL_MARCH_ORDERS = (
    ROOT / "test_files" / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
)
PUBLIC_S3_CONNECTION = {
    "bucket": "noaa-global-hourly-pds",
    "region": "us-east-1",
    "anonymous": True,
    "file_type": "csv",
}
PUBLIC_S3_SELECTION = {"object_path": "1901/02907099999.csv"}
PUBLIC_REST_CONNECTION = {
    "url": "https://api.weather.gov/stations",
    "headers": {
        "User-Agent": "algenta-mcp-runtime-live/1.0",
        "Accept": "application/geo+json",
    },
    "params": {"state": "CO"},
    "data_path": "features",
    "timeout": 60,
}

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, str, str]] = []


def req(method: str, path: str, body: dict[str, Any] | None = None, *, auth: bool = True) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    data_bytes = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["X-API-Key"] = API_KEY
    request = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
            return response.status, payload
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            payload = json.loads(body_bytes)
        except Exception:  # noqa: BLE001
            payload = body_bytes.decode("utf-8", errors="replace")
        return exc.code, payload


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


def _sum_csv_column(path: Path, column: str) -> float:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return sum(float(str(row[column] or "0").strip() or 0.0) for row in reader)


def _write_sqlite_fixture(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute('DROP TABLE IF EXISTS "orders"')
        connection.execute('DROP TABLE IF EXISTS "customers"')
        connection.execute(
            """
            CREATE TABLE orders (
                order_id TEXT,
                region TEXT,
                revenue REAL
            )
            """
        )
        connection.executemany(
            "INSERT INTO orders (order_id, region, revenue) VALUES (?, ?, ?)",
            [
                ("ord_1", "US", 100.0),
                ("ord_2", "US", 220.5),
                ("ord_3", "CA", 95.5),
            ],
        )
        connection.execute(
            """
            CREATE TABLE customers (
                customer_id TEXT,
                segment TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO customers (customer_id, segment) VALUES (?, ?)",
            [("c_1", "enterprise"), ("c_2", "mid-market")],
        )
        connection.commit()
    finally:
        connection.close()


def _postgres_fixture_rows() -> list[dict[str, object]]:
    return [
        {"order_id": "ord_1", "region": "US", "revenue": 100.0},
        {"order_id": "ord_2", "region": "US", "revenue": 220.5},
        {"order_id": "ord_3", "region": "CA", "revenue": 95.5},
    ]


def _result_value(body: dict[str, Any]) -> float:
    result = body["result"]
    if isinstance(result, dict):
        value = result.get("value")
    else:
        value = result
    return float(value)


def _count_metric_column(schema: dict[str, Any]) -> str:
    columns = schema.get("columns", [])
    if not columns:
        raise AssertionError("Schema returned no columns.")
    return str(columns[0]["name"])


def _preflight() -> None:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live MCP runtime compatibility tests.")
    status, _ = req("GET", "/v1/health", auth=False)
    assert status == 200, f"/v1/health returned {status}"


def run_real_csv_upload_query_flow() -> None:
    expected_sum = _sum_csv_column(REAL_MARCH_ORDERS, "Sales (incl. tax)")
    csv_text = REAL_MARCH_ORDERS.read_text(encoding="utf-8")

    connected = json.loads(
        run_async(
            data.connect_handler(
                {
                    "connection_type": "file_upload",
                    "dataset_name": "orders_detail",
                    "csv": csv_text,
                }
            )
        )
    )
    assert connected["status"] == "ready"
    dataset_id = connected["dataset_id"]
    assert connected["schema_summary"]["row_count"] == 6097

    listed = json.loads(run_async(data.list_handler({})))
    assert any(item["dataset_id"] == dataset_id for item in listed["datasets"])

    schema = json.loads(run_async(data.schema_handler({"dataset_id": dataset_id})))
    assert schema["dataset"]["dataset_name"] == "orders_detail"
    assert schema["schema"]["row_count"] == 6097

    queried = json.loads(
        run_async(
            query.handler(
                {
                    "dataset_id": dataset_id,
                    "metric_column": "Sales (incl. tax)",
                    "aggregation": "sum",
                }
            )
        )
    )
    assert queried["validated"] is True
    assert queried["clarification_required"] is False
    assert queried["result_type"] == "scalar"
    assert queried["resolved_column"] == "Sales (incl. tax)"
    assert abs(_result_value(queried) - expected_sum) < 1e-6


def run_real_csv_canonical_connector_flow() -> None:
    expected_sum = _sum_csv_column(REAL_MARCH_ORDERS, "Sales (incl. tax)")

    connected = json.loads(
        run_async(
            data.connect_handler(
                {
                    "dataset_name": "orders_detail_canonical",
                    "connector": {
                        "type": "csv",
                        "location": {"path": str(REAL_MARCH_ORDERS)},
                        "options": {"delimiter": ","},
                    },
                }
            )
        )
    )
    assert connected["status"] == "ready"
    assert connected["schema_summary"]["row_count"] == 6097

    queried = json.loads(
        run_async(
            query.handler(
                {
                    "dataset_id": connected["dataset_id"],
                    "metric_column": "Sales (incl. tax)",
                    "aggregation": "sum",
                }
            )
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert queried["resolved_column"] == "Sales (incl. tax)"
    assert abs(_result_value(queried) - expected_sum) < 1e-6


def run_database_selection_resume_and_query_sqlite() -> None:
    with tempfile.TemporaryDirectory(prefix="algenta-mcp-sqlite-") as tmp_dir:
        db_path = Path(tmp_dir) / "orders.db"
        _write_sqlite_fixture(db_path)

        first = json.loads(
            run_async(
                data.connect_handler(
                    {
                        "connection_type": "database",
                        "provider": "sqlite",
                        "dataset_name": "orders_sqlite",
                        "connection_config": {"path": str(db_path)},
                    }
                )
            )
        )
        assert first["status"] == "needs_selection"
        assert len(first["choices"]) == 2
        orders_choice = next(
            (choice for choice in first["choices"] if choice.get("label") == "orders"),
            None,
        )
        assert orders_choice is not None, "SQLite browse did not return the orders table."

        ready = json.loads(
            run_async(
                data.connect_handler(
                    {
                        "connection_type": "database",
                        "provider": "sqlite",
                        "dataset_name": "orders_sqlite",
                        "connection_id": first["connection_id"],
                        "selection": orders_choice["selection"],
                    }
                )
            )
        )
        assert ready["status"] == "ready"
        assert ready["schema_summary"]["row_count"] == 3

        queried = json.loads(
            run_async(
                query.handler(
                    {
                        "dataset_id": ready["dataset_id"],
                        "metric_column": "revenue",
                        "aggregation": "sum",
                    }
                )
            )
        )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert _result_value(queried) == 416.0


def run_database_selection_resume_and_query_postgres() -> None:
    with temporary_postgres_fixture(
        _postgres_fixture_rows(),
        table="orders",
    ) as postgres_descriptor:
        first = json.loads(
            run_async(
                data.connect_handler(
                    {
                        "connection_type": "database",
                        "provider": "postgres",
                        "dataset_name": "orders_postgres",
                        "connection_config": postgres_connection_config(
                            postgres_descriptor["connection_string"]
                        ),
                    }
                )
            )
        )
        assert first["status"] == "needs_selection"
        assert len(first["choices"]) >= 1
        orders_choice = next(
            (
                choice
                for choice in first["choices"]
                if (choice.get("selection") or {}).get("table")
                == f"{postgres_descriptor['schema']}.{postgres_descriptor['table']}"
            ),
            None,
        )
        assert orders_choice is not None, "Postgres browse did not return the orders table."

        ready = json.loads(
            run_async(
                data.connect_handler(
                    {
                        "connection_type": "database",
                        "provider": "postgres",
                        "dataset_name": "orders_postgres",
                        "connection_id": first["connection_id"],
                        "selection": orders_choice["selection"],
                    }
                )
            )
        )
        assert ready["status"] == "ready"
        assert ready["schema_summary"]["row_count"] == 3

        queried = json.loads(
            run_async(
                query.handler(
                    {
                        "dataset_id": ready["dataset_id"],
                        "metric_column": "revenue",
                        "aggregation": "sum",
                    }
                )
            )
        )
        assert queried["validated"] is True
        assert queried["result_type"] == "scalar"
        assert _result_value(queried) == 416.0


def run_database_query_postgres_via_canonical_connector() -> None:
    with temporary_postgres_fixture(
        _postgres_fixture_rows(),
        table="orders",
    ) as postgres_descriptor:
        connector = postgres_canonical_connector(postgres_descriptor)
        ready = json.loads(
            run_async(
                data.connect_handler(
                    {
                        "dataset_name": "orders_postgres_canonical",
                        "connector": connector,
                    }
                )
            )
        )
        assert ready["status"] == "ready"
        assert ready["schema_summary"]["row_count"] == 3

        queried = json.loads(
            run_async(
                query.handler(
                    {
                        "dataset_id": ready["dataset_id"],
                        "metric_column": "revenue",
                        "aggregation": "sum",
                    }
                )
            )
        )
        assert queried["validated"] is True
        assert queried["result_type"] == "scalar"
        assert _result_value(queried) == 416.0


def run_public_rest_connect_and_count_query() -> None:
    connected = json.loads(
        run_async(
            data.connect_handler(
                {
                    "connection_type": "api",
                    "provider": "rest",
                    "dataset_name": "public_weather_stations",
                    "connection_config": PUBLIC_REST_CONNECTION,
                }
            )
        )
    )
    assert connected["status"] == "ready"
    assert connected["schema_summary"]["row_count"] > 0

    schema = json.loads(run_async(data.schema_handler({"dataset_id": connected["dataset_id"]})))
    metric_column = _count_metric_column(schema["schema"])
    queried = json.loads(
        run_async(
            query.handler(
                {
                    "dataset_id": connected["dataset_id"],
                    "metric_column": metric_column,
                    "aggregation": "count",
                }
            )
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert _result_value(queried) == float(connected["schema_summary"]["row_count"])


def run_public_s3_connect_and_count_query() -> None:
    connected = json.loads(
        run_async(
            data.connect_handler(
                {
                    "connection_type": "object_storage",
                    "provider": "s3",
                    "dataset_name": "public_noaa_hourly_sample",
                    "connection_config": PUBLIC_S3_CONNECTION,
                    "selection": PUBLIC_S3_SELECTION,
                }
            )
        )
    )
    assert connected["status"] == "ready"
    assert connected["schema_summary"]["row_count"] > 0

    schema = json.loads(run_async(data.schema_handler({"dataset_id": connected["dataset_id"]})))
    metric_column = _count_metric_column(schema["schema"])
    queried = json.loads(
        run_async(
            query.handler(
                {
                    "dataset_id": connected["dataset_id"],
                    "metric_column": metric_column,
                    "aggregation": "count",
                }
            )
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert _result_value(queried) == float(connected["schema_summary"]["row_count"])


def main() -> int:
    print("\n" + "=" * 70)
    print("  LIVE MCP RUNTIME COMPATIBILITY")
    print("=" * 70)

    _preflight()

    check("Real CSV upload/query flow", run_real_csv_upload_query_flow)
    check("Real CSV canonical connector flow", run_real_csv_canonical_connector_flow)
    check("SQLite selection/resume/query flow", run_database_selection_resume_and_query_sqlite)
    check("Postgres selection/resume/query flow", run_database_selection_resume_and_query_postgres)
    check(
        "Postgres canonical connector flow",
        run_database_query_postgres_via_canonical_connector,
    )
    check("Public REST connect/count flow", run_public_rest_connect_and_count_query)
    check("Public S3 connect/count flow", run_public_s3_connect_and_count_query)

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
