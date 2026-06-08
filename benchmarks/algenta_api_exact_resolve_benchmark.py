from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = PROJECT_ROOT / "packages" / "algenta-core"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_api_exact_resolve_benchmark.json"


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


def _summarize_counts(samples: list[int]) -> dict[str, float]:
    return {
        "mean": statistics.mean(samples),
        "min": min(samples),
        "max": max(samples),
    }


def _registration():
    from algenta.runtime_models import SourceRegistration

    return SourceRegistration(
        source_id="src_1",
        dataset_id="src_1",
        name="orders",
        status="ready",
        source_schema={"fields": ["amount", "customer"]},
        planner_schema_revision="planner_rev_1",
        row_count=3,
    )


class _FakeClient:
    def __init__(self) -> None:
        self.calls = {
            "source_schema": 0,
            "resolve": 0,
        }

    def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/sources/src_1"
        self.calls["source_schema"] += 1
        return {"entry": {"source_schema_revision": "source_rev_1"}}

    def resolve(self, request: dict[str, object]) -> object:
        self.calls["resolve"] += 1
        metric_hint = request.get("metric")
        return SimpleNamespace(
            model_dump=lambda: {
                "resolved_plan": {
                    "source_name": "orders",
                    "metric_column": "amount",
                    "aggregation": "sum",
                    "group_column": "customer",
                    "schema_revision": "schema_123",
                    "constraints": {},
                    "order": "desc",
                },
                "confidence": 0.91,
                "plan": ["Use source 'orders'."],
                "explanation": [f"Resolved fuzzy request {metric_hint!r} to 'amount'."],
                "latency_ms": 12.5,
                "decision_path": "schema_match",
                "schema_revision": "schema_123",
                "validated": True,
                "deterministic_scope": "api_registered_source",
                "confidence_source": "schema_match",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "intent_signature": "intent_123",
                "plan_hash": "plan_123",
                "source_set": ["orders"],
                "join_path": [],
                "planner_mode": "runtime",
                "resolved_source": "orders",
                "resolved_column": "amount",
                "resolved_role": "measure",
                "candidates": [],
                "source_scores": {"orders": 1.0},
            }
        )


def _runtime():
    from algenta import Runtime

    runtime = Runtime(mode="api", api_key="de_test")
    client = _FakeClient()
    runtime._client = lambda: client
    runtime._remember_api_registration(_registration())
    return runtime, client


def _benchmark_exact_resolve(*, iterations: int) -> dict[str, Any]:
    runtime, client = _runtime()
    request = {
        "source_name": "orders",
        "metric": "amount",
        "group_by": "customer",
        "aggregation": "sum",
    }

    cold_start = time.perf_counter()
    cold_result = runtime.resolve(request)
    cold_ms = (time.perf_counter() - cold_start) * 1000.0
    cold_source_schema_requests = client.calls["source_schema"]
    cold_resolve_requests = client.calls["resolve"]

    source_schema_counts: list[int] = []
    resolve_counts: list[int] = []
    timings: list[float] = []
    for _ in range(iterations):
        before_source = client.calls["source_schema"]
        before_resolve = client.calls["resolve"]
        start = time.perf_counter()
        runtime.resolve(request)
        timings.append((time.perf_counter() - start) * 1000.0)
        source_schema_counts.append(client.calls["source_schema"] - before_source)
        resolve_counts.append(client.calls["resolve"] - before_resolve)

    return {
        "planner_mode": cold_result.planner_mode,
        "cold_ms": cold_ms,
        "cold_source_schema_requests": cold_source_schema_requests,
        "cold_resolve_requests": cold_resolve_requests,
        "warm_timings": _summarize_ms(timings),
        "warm_source_schema_requests": _summarize_counts(source_schema_counts),
        "warm_resolve_requests": _summarize_counts(resolve_counts),
    }


def _benchmark_fuzzy_resolve(*, iterations: int) -> dict[str, Any]:
    runtime, client = _runtime()
    request = {
        "source_name": "orders",
        "metric": "gross_revenue",
        "group_by": "customer",
        "aggregation": "sum",
    }

    cold_start = time.perf_counter()
    cold_result = runtime.resolve(request)
    cold_ms = (time.perf_counter() - cold_start) * 1000.0
    cold_source_schema_requests = client.calls["source_schema"]
    cold_resolve_requests = client.calls["resolve"]

    source_schema_counts: list[int] = []
    resolve_counts: list[int] = []
    timings: list[float] = []
    for _ in range(iterations):
        before_source = client.calls["source_schema"]
        before_resolve = client.calls["resolve"]
        start = time.perf_counter()
        runtime.resolve(request)
        timings.append((time.perf_counter() - start) * 1000.0)
        source_schema_counts.append(client.calls["source_schema"] - before_source)
        resolve_counts.append(client.calls["resolve"] - before_resolve)

    return {
        "planner_mode": cold_result.planner_mode,
        "cold_ms": cold_ms,
        "cold_source_schema_requests": cold_source_schema_requests,
        "cold_resolve_requests": cold_resolve_requests,
        "warm_timings": _summarize_ms(timings),
        "warm_source_schema_requests": _summarize_counts(source_schema_counts),
        "warm_resolve_requests": _summarize_counts(resolve_counts),
    }


def run_benchmark(*, iterations: int = 200) -> dict[str, Any]:
    _ensure_package_paths()
    return {
        "iterations": iterations,
        "exact_resolve": _benchmark_exact_resolve(iterations=iterations),
        "fuzzy_resolve": _benchmark_fuzzy_resolve(iterations=iterations),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the algenta Runtime exact API resolve fast path."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Warm samples per resolve path.",
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
