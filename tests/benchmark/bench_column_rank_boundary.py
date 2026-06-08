# ruff: noqa: E402
"""
bench_column_rank_boundary.py — Planner column-rank boundary benchmark.

Measures the warm planner resolver path for:
1. Single-field scalar resolution
2. Batched multi-field resolution
3. Concurrent batched resolution under many-file load

The benchmark compares Python-only resolver mode against resident Mojo
`column_rank` mode on the repo's real local source corpus. It exists to keep
the Python<->Mojo planner boundary measurable after transport or payload
changes.

Usage:
    python -m tests.benchmark.bench_column_rank_boundary
    python -m tests.benchmark.bench_column_rank_boundary --source-limit 65
    python -m tests.benchmark.bench_column_rank_boundary --include-force --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEST_FILES = ROOT / "test_files"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services import auto_planner as auto_planner_module
from apps.api_server.services import mojo_column_rank_resolver as rank_resolver_module

DEFAULT_SCALAR_REQUEST = ("unit price", None, "unit_measure")
DEFAULT_BATCH_REQUESTS = [
    ("unit price", None, "unit_measure"),
    ("extended price", None, "derived_measure"),
    ("quantity", None, "base_measure"),
    ("unit cost", None, "unit_measure"),
    ("extended cost", None, "derived_measure"),
    ("line total", None, "derived_measure"),
]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, int((len(ordered) - 1) * pct))
    return float(ordered[rank])


def _summarize_latencies(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        raise ValueError("Benchmark latencies must not be empty")
    ordered = sorted(latencies)
    return {
        "mean_ms": float(statistics.mean(ordered)),
        "p50_ms": _percentile(ordered, 0.50),
        "p95_ms": _percentile(ordered, 0.95),
        "p99_ms": _percentile(ordered, 0.99),
        "min_ms": float(ordered[0]),
        "max_ms": float(ordered[-1]),
        "n": float(len(ordered)),
    }


def _select_source_map(limit: int) -> dict[str, str]:
    discovered = auto_planner_module._discover_local_source_map(TEST_FILES)
    if limit <= 0 or limit >= len(discovered):
        return discovered
    items = list(discovered.items())[:limit]
    return dict(items)


def _scalar_top_match(result: Any) -> str | None:
    source = getattr(result, "source", None)
    column = getattr(result, "column", None)
    if isinstance(source, str) and isinstance(column, str):
        return f"{source}.{column}"
    return None


def _batch_top_matches(results: Any) -> list[str]:
    matches: list[str] = []
    if not isinstance(results, list):
        return matches
    for result in results:
        match = _scalar_top_match(result)
        if match:
            matches.append(match)
    return matches


@contextmanager
def _planner_rank_mode(mode: str):
    original_mode = auto_planner_module._MOJO_COLUMN_RANK_MODE
    auto_planner_module._MOJO_COLUMN_RANK_MODE = mode
    try:
        yield
    finally:
        auto_planner_module._MOJO_COLUMN_RANK_MODE = original_mode


def _build_planner(*, mode: str, source_limit: int, max_rows: int) -> Any:
    source_map = _select_source_map(source_limit)
    with _planner_rank_mode(mode):
        planner = auto_planner_module.AutoPlanner(data_dir=TEST_FILES, max_rows=max_rows)
        planner.build_knowledge(source_map)
    return planner


def _measure_sync(fn: Any, *, warmup: int, iterations: int) -> dict[str, float]:
    for _ in range(max(warmup, 0)):
        fn()
    latencies: list[float] = []
    for _ in range(max(iterations, 1)):
        start = time.perf_counter()
        fn()
        latencies.append((time.perf_counter() - start) * 1000.0)
    return _summarize_latencies(latencies)


def _measure_concurrent(fn: Any, *, workers: int, tasks: int) -> dict[str, float]:
    latencies: list[float] = []
    total_start = time.perf_counter()

    def _one() -> float:
        start = time.perf_counter()
        fn()
        return (time.perf_counter() - start) * 1000.0

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        futures = [executor.submit(_one) for _ in range(max(tasks, 1))]
        for future in as_completed(futures):
            latencies.append(float(future.result()))

    total_ms = (time.perf_counter() - total_start) * 1000.0
    summary = _summarize_latencies(latencies)
    summary["workers"] = float(max(workers, 1))
    summary["tasks"] = float(max(tasks, 1))
    summary["rps"] = float(max(tasks, 1) / max(total_ms / 1000.0, 1e-9))
    summary["wall_ms"] = float(total_ms)
    return summary


def _resolver_column_count(planner: Any) -> int:
    resolver = planner._vector_resolver
    entries = getattr(resolver, "_entries", None)
    if isinstance(entries, list):
        return len(entries)
    base_resolver = getattr(resolver, "_base_resolver", None)
    base_entries = getattr(base_resolver, "_entries", None)
    if isinstance(base_entries, list):
        return len(base_entries)
    graph = getattr(planner, "graph", {})
    if isinstance(graph, dict):
        return sum(len(columns) for columns in graph.values())
    return 0


def _graph_column_count(planner: Any) -> int:
    graph = getattr(planner, "graph", {})
    if isinstance(graph, dict):
        return sum(len(columns) for columns in graph.values())
    return 0


def _resolve_modes(include_force: bool) -> list[str]:
    modes = ["disabled", "auto"]
    if include_force:
        modes.append("force")
    return modes


def run_mode_benchmark(
    planner: Any,
    *,
    mode: str,
    scalar_request: tuple[str, str | None, str | None] = DEFAULT_SCALAR_REQUEST,
    batch_requests: list[tuple[str, str | None, str | None]] = DEFAULT_BATCH_REQUESTS,
    warmup: int,
    iterations: int,
    concurrency_workers: int,
    concurrency_tasks: int,
) -> dict[str, Any]:
    resolver = getattr(planner, "_vector_resolver", None)
    if resolver is None:
        raise RuntimeError("Planner benchmark requires an initialized vector resolver")

    def scalar_runner() -> Any:
        return resolver.resolve(*scalar_request)

    def batch_runner() -> Any:
        return resolver.resolve_batch(batch_requests)

    scalar_probe = scalar_runner()
    batch_probe = batch_runner()
    scalar_stats = _measure_sync(scalar_runner, warmup=warmup, iterations=iterations)
    batch_stats = _measure_sync(batch_runner, warmup=warmup, iterations=iterations)
    concurrent_stats = _measure_concurrent(
        batch_runner,
        workers=concurrency_workers,
        tasks=concurrency_tasks,
    )

    return {
        "mode": mode,
        "resolver_class": type(resolver).__name__,
        "source_count": len(getattr(planner, "graph", {})),
        "resolver_columns": _resolver_column_count(planner),
        "graph_columns": _graph_column_count(planner),
        "mojo_engines": list(getattr(planner, "mojo_engines", [])),
        "scalar": scalar_stats,
        "batch": batch_stats,
        "concurrency": concurrent_stats,
        "probe": {
            "scalar_top_match": _scalar_top_match(scalar_probe),
            "batch_top_matches": _batch_top_matches(batch_probe),
        },
    }


def benchmark_mode(
    *,
    mode: str,
    source_limit: int,
    max_rows: int,
    warmup: int,
    iterations: int,
    concurrency_workers: int,
    concurrency_tasks: int,
) -> dict[str, Any]:
    planner = _build_planner(mode=mode, source_limit=source_limit, max_rows=max_rows)
    return run_mode_benchmark(
        planner,
        mode=mode,
        warmup=warmup,
        iterations=iterations,
        concurrency_workers=concurrency_workers,
        concurrency_tasks=concurrency_tasks,
    )


def _print_human_summary(results: list[dict[str, Any]]) -> None:
    print("=" * 72)
    print("Column-Rank Boundary Benchmark")
    print("=" * 72)
    for result in results:
        scalar = result["scalar"]
        batch = result["batch"]
        concurrency = result["concurrency"]
        print(
            f"mode={result['mode']}  resolver={result['resolver_class']}  "
            f"sources={result['source_count']}  "
            f"resolver_columns={result['resolver_columns']}  "
            f"graph_columns={result['graph_columns']}"
        )
        print(
            "  scalar: "
            f"mean={scalar['mean_ms']:.3f}ms "
            f"p50={scalar['p50_ms']:.3f}ms "
            f"p95={scalar['p95_ms']:.3f}ms"
        )
        print(
            "  batch:  "
            f"mean={batch['mean_ms']:.3f}ms "
            f"p50={batch['p50_ms']:.3f}ms "
            f"p95={batch['p95_ms']:.3f}ms"
        )
        print(
            "  conc:   "
            f"workers={int(concurrency['workers'])} "
            f"tasks={int(concurrency['tasks'])} "
            f"rps={concurrency['rps']:.2f} "
            f"p50={concurrency['p50_ms']:.3f}ms "
            f"p95={concurrency['p95_ms']:.3f}ms"
        )
        print(f"  probe:   scalar={result['probe']['scalar_top_match']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Planner column-rank boundary benchmark")
    parser.add_argument("--source-limit", type=int, default=15)
    parser.add_argument("--max-rows", type=int, default=3000)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--concurrency-workers", type=int, default=8)
    parser.add_argument("--concurrency-tasks", type=int, default=1000)
    parser.add_argument("--include-force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for mode in _resolve_modes(args.include_force):
        results.append(
            benchmark_mode(
                mode=mode,
                source_limit=args.source_limit,
                max_rows=args.max_rows,
                warmup=args.warmup,
                iterations=args.iterations,
                concurrency_workers=args.concurrency_workers,
                concurrency_tasks=args.concurrency_tasks,
            )
        )

    payload = {
        "benchmark": "column_rank_boundary",
        "source_limit": args.source_limit,
        "max_rows": args.max_rows,
        "planner_mojo_pool_size": rank_resolver_module._PLANNER_MOJO_POOL_SIZE,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    _print_human_summary(results)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
