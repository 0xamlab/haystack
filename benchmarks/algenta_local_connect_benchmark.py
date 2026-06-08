from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = PROJECT_ROOT / "packages" / "algenta-core"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_local_connect_benchmark.json"


def _ensure_package_paths() -> None:
    for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(PROJECT_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _sample_rows() -> list[dict[str, object]]:
    return [
        {
            "product_line": "Electronics",
            "revenue": 42193221,
            "region": "US",
            "country": "United States",
            "channel": "Online",
            "units": 1200,
        },
        {
            "product_line": "Apparel",
            "revenue": 28114992,
            "region": "US",
            "country": "United States",
            "channel": "Retail",
            "units": 860,
        },
        {
            "product_line": "Electronics",
            "revenue": 1204000,
            "region": "CA",
            "country": "Canada",
            "channel": "Online",
            "units": 77,
        },
        {
            "product_line": "Home",
            "revenue": 830000,
            "region": "US",
            "country": "United States",
            "channel": "Marketplace",
            "units": 54,
        },
    ]


def _sample_ms(fn: Callable[[], Any], iterations: int) -> list[float]:
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


def _percentile_ms(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _summarize_ms(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.mean(samples) if samples else 0.0,
        "min_ms": min(samples) if samples else 0.0,
        "max_ms": max(samples) if samples else 0.0,
        "p90_ms": _percentile_ms(samples, 0.90) if samples else 0.0,
        "p95_ms": _percentile_ms(samples, 0.95) if samples else 0.0,
    }


def run_benchmark(*, iterations: int = 200) -> dict[str, Any]:
    _ensure_package_paths()

    from algenta import Runtime

    rows = _sample_rows()
    cold_runtime = Runtime(mode="local")
    cold_start = time.perf_counter()
    cold_registration = cold_runtime.connect(rows, name="orders")
    cold_ms = (time.perf_counter() - cold_start) * 1000.0

    def _single_connect() -> Any:
        runtime = Runtime(mode="local")
        return runtime.connect(rows, name="orders")

    def _connect_many() -> Any:
        runtime = Runtime(mode="local")
        return runtime.connect_many([rows, rows], names=["orders_a", "orders_b"])

    single_registration = _single_connect()
    many_registrations = _connect_many()
    return {
        "iterations": iterations,
        "row_count": cold_registration.row_count,
        "field_count": len(rows[0]),
        "cold_single_connect_ms": cold_ms,
        "warm_single_connect": _summarize_ms(_sample_ms(_single_connect, iterations)),
        "warm_connect_many": _summarize_ms(_sample_ms(_connect_many, iterations)),
        "single_registration": {
            "name": single_registration.name,
            "dataset_id": single_registration.dataset_id,
        },
        "connect_many_names": [registration.name for registration in many_registrations],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the local Runtime.connect/connect_many registration path."
    )
    parser.add_argument("--iterations", type=int, default=200, help="Samples per warm path.")
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
