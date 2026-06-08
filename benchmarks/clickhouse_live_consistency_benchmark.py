from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from typing import Any

from apps.api_server.connectors.sql_connector import SQLConnector
from apps.api_server.services.connectors.tester import test_connector_real_detailed
from tests.go_live_secret_resolver import populate_go_live_test_env_from_keys_txt
from tests.integration.connector_validation_catalog import (
    _build_clickhouse_sql_connection,
    _load_sql_records,
)

populate_go_live_test_env_from_keys_txt()


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, round((pct / 100.0) * (len(ordered) - 1)))
    return float(ordered[min(index, len(ordered) - 1)])


def _summarize_series(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "values_ms": [round(value, 3) for value in values],
        "min_ms": round(min(values), 3) if values else 0.0,
        "max_ms": round(max(values), 3) if values else 0.0,
        "mean_ms": round(statistics.mean(values), 3) if values else 0.0,
        "median_ms": round(statistics.median(values), 3) if values else 0.0,
        "p90_ms": round(_percentile(values, 90), 3) if values else 0.0,
        "p95_ms": round(_percentile(values, 95), 3) if values else 0.0,
    }


def _summarize_run(values: list[float]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "all_ms": _summarize_series(values),
    }
    if values:
        payload["cold_first_ms"] = round(values[0], 3)
    if len(values) > 1:
        payload["warm_ms"] = _summarize_series(values[1:])
    return payload


def _build_probe_config_from_env() -> dict[str, Any]:
    return {
        "url": str(os.environ.get("DE_TEST_CLICKHOUSE_URL", "")).strip(),
        "user": str(os.environ.get("DE_TEST_CLICKHOUSE_USER", "default")).strip() or "default",
        "password": str(os.environ.get("DE_TEST_CLICKHOUSE_PASSWORD", "")).strip(),
        "database": str(os.environ.get("DE_TEST_CLICKHOUSE_DATABASE", "default")).strip()
        or "default",
    }


async def _measure_probe(iterations: int) -> dict[str, Any]:
    config = _build_probe_config_from_env()
    latencies_ms: list[float] = []
    for _ in range(iterations):
        started_at = time.perf_counter()
        outcome = await test_connector_real_detailed("clickhouse", config)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if not outcome.success:
            raise RuntimeError(outcome.message)
        latencies_ms.append(elapsed_ms)
    return _summarize_run(latencies_ms)


async def _measure_validate_fetch_and_load(iterations: int) -> dict[str, Any]:
    sql_config = _build_clickhouse_sql_connection()
    connector = SQLConnector(sql_config)
    validate_ms: list[float] = []
    fetch_ms: list[float] = []
    load_ms: list[float] = []
    for _ in range(iterations):
        validate_started_at = time.perf_counter()
        ok, message = await connector.validate_connection()
        validate_elapsed_ms = (time.perf_counter() - validate_started_at) * 1000.0
        if not ok:
            raise RuntimeError(message)
        validate_ms.append(validate_elapsed_ms)

        fetch_started_at = time.perf_counter()
        rows = await connector.fetch_data()
        fetch_elapsed_ms = (time.perf_counter() - fetch_started_at) * 1000.0
        if not rows:
            raise RuntimeError("ClickHouse fetch returned no rows during consistency benchmark.")
        fetch_ms.append(fetch_elapsed_ms)

        load_started_at = time.perf_counter()
        loaded_rows = _load_sql_records(sql_config)
        load_elapsed_ms = (time.perf_counter() - load_started_at) * 1000.0
        if not loaded_rows:
            raise RuntimeError(
                "ClickHouse validation loader returned no rows during consistency benchmark."
            )
        load_ms.append(load_elapsed_ms)

    return {
        "validate_ms": _summarize_run(validate_ms),
        "fetch_ms": _summarize_run(fetch_ms),
        "catalog_load_ms": _summarize_run(load_ms),
    }


async def _run(iterations: int) -> dict[str, Any]:
    SQLConnector._clear_clickhouse_client_pools()
    probe_summary = await _measure_probe(iterations)
    SQLConnector._clear_clickhouse_client_pools()
    data_summary = await _measure_validate_fetch_and_load(iterations)
    return {
        "connector": "clickhouse",
        "iterations": iterations,
        "probe_ms": probe_summary,
        **data_summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure live ClickHouse probe, validate, and exact-query consistency."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=6,
        help="Number of repeated measurements to run for each path.",
    )
    args = parser.parse_args(argv)
    if args.iterations <= 0:
        raise ValueError("--iterations must be greater than zero.")
    payload = asyncio.run(_run(args.iterations))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
