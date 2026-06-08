from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = PROJECT_ROOT / "packages" / "algenta-core"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_runtime_read_cache_benchmark.json"


def _ensure_package_paths() -> None:
    for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(PROJECT_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _percentile_ms(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _summarize_ms(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.mean(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "p90_ms": _percentile_ms(samples, 0.90),
        "p95_ms": _percentile_ms(samples, 0.95),
    }


def _connector_payload(connector_id: str = "conn_123") -> dict[str, object]:
    return {
        "id": connector_id,
        "name": "Warehouse Postgres",
        "description": "analytics warehouse",
        "connector_type": "postgres",
        "status": "live",
        "visibility": "private",
        "last_tested_at": None,
        "error_message": None,
        "created_at": None,
    }


def _browse_payload(connector_id: str = "conn_123") -> dict[str, object]:
    return {
        "connector_type": "postgres",
        "items": [
            {
                "id": "public.orders",
                "label": "orders",
                "kind": "table",
                "selection": {"table": "orders"},
            }
        ],
        "total": 1,
        "message": "1 table available.",
        "labels": {"entity_noun": "table", "row_noun": "row"},
        "discovery": {"scope_noun": "schema", "returned_count": 1},
        "connector_id": connector_id,
    }


def _dataset_payload(dataset_id: str = "ds_123") -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "source_id": dataset_id,
        "dataset_name": "orders_dataset",
        "source_name": "orders_dataset",
        "description": "orders",
        "connection_id": "conn_123",
        "connection_type": "database",
        "provider": "postgres",
        "visibility": "private",
        "owner_user_id": "u1",
        "owner_key_id": "k1",
        "refreshable": True,
        "row_count": 42,
        "columns": 3,
        "roles_summary": {"dimensions": 2, "measures": 1},
        "discovery_labels": {"entity_noun": "table", "row_noun": "row"},
        "discovery_metadata": {"scope_noun": "schema"},
        "registered_at": None,
        "selection": {"table": "orders"},
    }


class _FakeClient:
    def __init__(self) -> None:
        self.calls = {
            "list_connectors": 0,
            "get_connector": 0,
            "browse_connector": 0,
            "list_datasets": 0,
            "get_dataset": 0,
        }

    def list_connectors(self, *, page: int, limit: int):
        self.calls["list_connectors"] += 1
        return SimpleNamespace(connectors=[_connector_payload()], page=page, limit=limit, pages=1)

    def get_connector(self, connector_id: str):
        self.calls["get_connector"] += 1
        return _connector_payload(connector_id)

    def browse_connector(self, connector_id: str):
        self.calls["browse_connector"] += 1
        return _browse_payload(connector_id)

    def list_datasets(self, *, page: int, limit: int):
        self.calls["list_datasets"] += 1
        return SimpleNamespace(datasets=[_dataset_payload()], page=page, limit=limit, pages=1)

    def get_dataset(self, dataset_id: str):
        self.calls["get_dataset"] += 1
        return {"dataset": _dataset_payload(dataset_id), "schema": {"fields": ["amount"]}}


def _runtime():
    from algenta import Runtime

    runtime = Runtime(mode="api", api_key="de_test")
    client = _FakeClient()
    runtime._client = lambda: client
    return runtime, client


def _benchmark_operation(
    warm_up: Callable[[], Any],
    run_call: Callable[[], Any],
    *,
    iterations: int,
    call_counter: Callable[[], int],
) -> dict[str, Any]:
    cold_before = call_counter()
    cold_start = time.perf_counter()
    warm_up()
    cold_ms = (time.perf_counter() - cold_start) * 1000.0
    cold_requests = call_counter() - cold_before

    request_counts: list[int] = []
    timings: list[float] = []
    for _ in range(iterations):
        before = call_counter()
        start = time.perf_counter()
        run_call()
        timings.append((time.perf_counter() - start) * 1000.0)
        request_counts.append(call_counter() - before)

    return {
        "cold_ms": cold_ms,
        "cold_requests": cold_requests,
        "warm_timings": _summarize_ms(timings),
        "warm_requests": {
            "mean": statistics.mean(request_counts),
            "max": max(request_counts),
            "min": min(request_counts),
        },
    }


def run_benchmark(*, iterations: int = 200) -> dict[str, Any]:
    _ensure_package_paths()

    runtime, client = _runtime()
    return {
        "iterations": iterations,
        "get_connector": _benchmark_operation(
            lambda: runtime.get_connector("conn_123"),
            lambda: runtime.get_connector("conn_123"),
            iterations=iterations,
            call_counter=lambda: client.calls["get_connector"],
        ),
        "browse_connector": _benchmark_operation(
            lambda: runtime.browse_connector("conn_123"),
            lambda: runtime.browse_connector("conn_123"),
            iterations=iterations,
            call_counter=lambda: client.calls["browse_connector"],
        ),
        "list_connectors": _benchmark_operation(
            lambda: runtime.list_connectors(),
            lambda: runtime.list_connectors(),
            iterations=iterations,
            call_counter=lambda: client.calls["list_connectors"],
        ),
        "get_dataset": _benchmark_operation(
            lambda: runtime.get_dataset("ds_123"),
            lambda: runtime.get_dataset("ds_123"),
            iterations=iterations,
            call_counter=lambda: client.calls["get_dataset"],
        ),
        "list_datasets": _benchmark_operation(
            lambda: runtime.list_datasets(),
            lambda: runtime.list_datasets(),
            iterations=iterations,
            call_counter=lambda: client.calls["list_datasets"],
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the algenta saved-read cache path.")
    parser.add_argument("--iterations", type=int, default=200, help="Warm samples per operation.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the benchmark JSON artifact.",
    )
    args = parser.parse_args()

    results = run_benchmark(iterations=args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
