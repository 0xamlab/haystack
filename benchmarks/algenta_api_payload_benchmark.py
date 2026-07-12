from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_PACKAGE = PROJECT_ROOT / "packages" / "algenta"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_api_payload_benchmark.json"


def _ensure_package_paths() -> None:
    for path in (str(ALGENTA_PACKAGE), str(PYTHON_SDK), str(PROJECT_ROOT)):
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


def _request_fixture() -> dict[str, object]:
    return {
        "source_name": "orders",
        "metric": "gross_revenue",
        "group_by": "customer",
        "aggregation": "sum",
        "metric_column": "amount",
        "resolved_plan": {"ignored": True},
    }


def _resolved_plan_fixture():
    from algenta.runtime_models import ResolvedPlan

    return ResolvedPlan(
        source_name="orders",
        metric_column="amount",
        aggregation="sum",
        group_column="customer",
        schema_revision="schema_123",
    )


def _resolve_output_fixture():
    from algenta.runtime_models import ResolveOutput

    return ResolveOutput(
        resolved_plan=_resolved_plan_fixture(),
        confidence=1.0,
        plan=["Use exact source 'orders'."],
        explanation=["Using exact metric column 'amount'."],
        latency_ms=1.0,
        decision_path="exact_spec",
        schema_revision="schema_123",
        validated=True,
        deterministic_scope="api_registered_source",
        confidence_source="runtime_exact_spec",
        planner_mode="runtime_exact_spec",
        resolved_source="orders",
        resolved_column="amount",
        resolved_role="measure",
    )


def _exact_plan_mapping() -> dict[str, object]:
    return {
        "source_name": "orders",
        "metric_column": "amount",
        "aggregation": "sum",
        "group_column": "customer",
        "schema_revision": "schema_123",
    }


def _benchmark_operation(fn, *, iterations: int):  # type: ignore[no-untyped-def]
    cold_start = time.perf_counter()
    cold_result = fn()
    cold_ms = (time.perf_counter() - cold_start) * 1000.0

    timings: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - start) * 1000.0)

    return {
        "cold_ms": cold_ms,
        "warm_timings": _summarize_ms(timings),
        "result_keys": sorted(cold_result.keys()) if isinstance(cold_result, dict) else [],
    }


def run_benchmark(*, iterations: int = 500) -> dict[str, object]:
    _ensure_package_paths()

    from algenta.runtime_api_payloads import (
        coerce_api_query_payload,
        coerce_api_resolve_payload,
        coerce_plan,
    )

    request = _request_fixture()
    resolve_output = _resolve_output_fixture()
    exact_plan = _exact_plan_mapping()

    return {
        "iterations": iterations,
        "resolve_payload": _benchmark_operation(
            lambda: coerce_api_resolve_payload(request),
            iterations=iterations,
        ),
        "query_payload_from_resolve_output": _benchmark_operation(
            lambda: coerce_api_query_payload(resolve_output, {}),
            iterations=iterations,
        ),
        "query_payload_from_exact_mapping": _benchmark_operation(
            lambda: coerce_api_query_payload(exact_plan, {}),
            iterations=iterations,
        ),
        "plan_from_exact_mapping": _benchmark_operation(
            lambda: coerce_plan(exact_plan, {}).to_dict(),
            iterations=iterations,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark algenta Runtime API payload coercion helpers."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=500,
        help="Warm samples per payload helper.",
    )
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
    print(f"Wrote benchmark artifact to {args.output}")


if __name__ == "__main__":
    main()
