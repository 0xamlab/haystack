from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from typing import Any

from apps.api_server.connectors.elasticsearch_connector import ElasticsearchConnector
from apps.api_server.services.connectors.tester import test_connector_real_detailed
from apps.api_server.services.data_connection_specs import browse_connector_real
from tests.go_live_secret_resolver import populate_go_live_test_env_from_keys_txt

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
    payload: dict[str, Any] = {"all_ms": _summarize_series(values)}
    if values:
        payload["cold_first_ms"] = round(values[0], 3)
    if len(values) > 1:
        payload["warm_ms"] = _summarize_series(values[1:])
    return payload


def _build_probe_config_from_env() -> dict[str, Any]:
    return {
        "url": str(os.environ.get("DE_TEST_ELASTICSEARCH_URL", "")).strip(),
        "api_key": str(os.environ.get("DE_TEST_ELASTICSEARCH_API_KEY", "")).strip(),
        "index": str(os.environ.get("DE_TEST_ELASTICSEARCH_INDEX", "")).strip(),
        "query": str(os.environ.get("DE_TEST_ELASTICSEARCH_QUERY", "")).strip(),
        "limit": int(os.environ.get("DE_TEST_ELASTICSEARCH_LIMIT", "100") or "100"),
    }


async def _measure_probe(iterations: int) -> dict[str, Any]:
    config = _build_probe_config_from_env()
    latencies_ms: list[float] = []
    for _ in range(iterations):
        started_at = time.perf_counter()
        outcome = await test_connector_real_detailed("elasticsearch", config)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if not outcome.success:
            raise RuntimeError(outcome.message)
        latencies_ms.append(elapsed_ms)
    return _summarize_run(latencies_ms)


async def _measure_validate_fetch_and_browse(iterations: int) -> dict[str, Any]:
    base_config = _build_probe_config_from_env()
    connector = ElasticsearchConnector(base_config)
    validate_ms: list[float] = []
    fetch_ms: list[float] = []
    browse_ms: list[float] = []
    for _ in range(iterations):
        validate_started_at = time.perf_counter()
        ok, message = await connector.validate_connection()
        validate_elapsed_ms = (time.perf_counter() - validate_started_at) * 1000.0
        if not ok:
            raise RuntimeError(message)
        validate_ms.append(validate_elapsed_ms)

        if base_config.get("index"):
            fetch_started_at = time.perf_counter()
            rows = await connector.fetch_data()
            fetch_elapsed_ms = (time.perf_counter() - fetch_started_at) * 1000.0
            if not rows:
                raise RuntimeError(
                    "Elasticsearch fetch returned no rows during consistency benchmark."
                )
            fetch_ms.append(fetch_elapsed_ms)

        browse_started_at = time.perf_counter()
        items, _message = await browse_connector_real("elasticsearch", {**base_config, "limit": 10})
        browse_elapsed_ms = (time.perf_counter() - browse_started_at) * 1000.0
        if not items:
            raise RuntimeError(
                "Elasticsearch browse returned no items during consistency benchmark."
            )
        browse_ms.append(browse_elapsed_ms)

    payload: dict[str, Any] = {
        "validate_ms": _summarize_run(validate_ms),
        "browse_ms": _summarize_run(browse_ms),
    }
    if fetch_ms:
        payload["fetch_ms"] = _summarize_run(fetch_ms)
    return payload


async def _run(iterations: int) -> dict[str, Any]:
    ElasticsearchConnector._clear_client_cache()
    probe_summary = await _measure_probe(iterations)
    data_summary = await _measure_validate_fetch_and_browse(iterations)
    ElasticsearchConnector._clear_client_cache()
    return {
        "connector": "elasticsearch",
        "iterations": iterations,
        "probe_ms": probe_summary,
        **data_summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure live Elasticsearch probe, validate, fetch, and browse consistency."
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
