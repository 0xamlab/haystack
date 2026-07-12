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
ALGENTA_PACKAGE = PROJECT_ROOT / "packages" / "algenta"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_local_runtime_exact_benchmark.json"


def _ensure_package_paths() -> None:
    for path in (str(ALGENTA_PACKAGE), str(PYTHON_SDK), str(PROJECT_ROOT)):
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
            "margin": 0.42,
            "discount": 0.05,
            "gross_revenue": 44413916,
            "net_revenue": 42193221,
            "cost": 24472000,
            "tax": 2120000,
            "shipping": 980000,
        },
        {
            "product_line": "Apparel",
            "revenue": 28114992,
            "region": "US",
            "country": "United States",
            "channel": "Retail",
            "units": 860,
            "margin": 0.37,
            "discount": 0.08,
            "gross_revenue": 30559774,
            "net_revenue": 28114992,
            "cost": 17624000,
            "tax": 1450000,
            "shipping": 540000,
        },
        {
            "product_line": "Electronics",
            "revenue": 1204000,
            "region": "CA",
            "country": "Canada",
            "channel": "Online",
            "units": 77,
            "margin": 0.28,
            "discount": 0.02,
            "gross_revenue": 1271400,
            "net_revenue": 1204000,
            "cost": 867500,
            "tax": 61000,
            "shipping": 22000,
        },
        {
            "product_line": "Home",
            "revenue": 830000,
            "region": "US",
            "country": "United States",
            "channel": "Marketplace",
            "units": 54,
            "margin": 0.31,
            "discount": 0.04,
            "gross_revenue": 864583,
            "net_revenue": 830000,
            "cost": 572700,
            "tax": 41000,
            "shipping": 17000,
        },
    ]


def _percentile_ms(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _sample_ms(fn: Callable[[], Any], iterations: int) -> list[float]:
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


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

    request = {"metric": "revenue", "group_by": "product_line"}
    rows = _sample_rows()

    cold_start = time.perf_counter()
    cold_runtime = Runtime(mode="local")
    cold_runtime.connect(rows, name="orders")
    cold_resolve = cold_runtime.resolve(request)
    cold_query = cold_runtime.query(cold_resolve)
    cold_verify = cold_runtime.verify(cold_resolve)
    cold_ms = (time.perf_counter() - cold_start) * 1000.0

    runtime = Runtime(mode="local")
    registration = runtime.connect(rows, name="orders")
    resolved = runtime.resolve(request)

    return {
        "iterations": iterations,
        "source_name": registration.name,
        "row_count": registration.row_count,
        "field_count": len(rows[0]),
        "cold_round_trip_ms": cold_ms,
        "warm_resolve": _summarize_ms(_sample_ms(lambda: runtime.resolve(request), iterations)),
        "warm_query": _summarize_ms(_sample_ms(lambda: runtime.query(resolved), iterations)),
        "warm_verify": _summarize_ms(_sample_ms(lambda: runtime.verify(resolved), iterations)),
        "resolved_plan": resolved.resolved_plan.to_dict() if resolved.resolved_plan else None,
        "cold_query_result_type": cold_query.result_type,
        "cold_verify_valid": cold_verify.valid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the local exact resolve/query/verify Runtime path."
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
