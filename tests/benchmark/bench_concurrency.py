"""
bench_concurrency.py — Concurrency benchmark for the Mojo worker pool.

Tests pool behavior under concurrent load at 1, 10, 100, and 500 simultaneous
requests. Reports p50/p95/p99 latency and error rate at each concurrency level.

This benchmark is required before claiming "persistent Mojo decision runtime"
under concurrent production load (Phase 0 + Phase 8 exit criteria).

Usage:
    python -m tests.benchmark.bench_concurrency
    make bench-concurrency

Environment variables:
    BENCH_CONCURRENCY_LEVELS  — comma-separated levels, default "1,10,100,500"
    BENCH_CONCURRENCY_RUNS    — requests per level, default "50"
    MOJO_ALLOW_SUBPROCESS_FALLBACK — set "false" to enforce pool-only
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from typing import Any

# Parse concurrency levels from env or use defaults
_LEVELS_STR = os.environ.get("BENCH_CONCURRENCY_LEVELS", "1,10,100,500")
CONCURRENCY_LEVELS = [int(x) for x in _LEVELS_STR.split(",")]

# Number of total requests per concurrency level
REQUESTS_PER_LEVEL = int(os.environ.get("BENCH_CONCURRENCY_RUNS", "50"))

# Warmup requests before measurement
N_WARMUP = int(os.environ.get("BENCH_CONCURRENCY_WARMUP", "10"))


# Representative 3-variable Monte Carlo payload (10k runs)
_PAYLOAD: dict[str, Any] = {
    "engine_type": "monte_carlo",
    "runs": 10000,
    "variables": [
        {"name": "rev", "distribution": "normal", "params": {"mean": 100000, "std": 20000}},
        {
            "name": "cost",
            "distribution": "triangular",
            "params": {"low": 40000, "mode": 55000, "high": 70000},
        },
        {"name": "vol", "distribution": "lognormal", "params": {"mean": 11.0, "std": 0.15}},
    ],
    "objective_function": "rev - cost",
}


async def _invoke_one(semaphore: asyncio.Semaphore) -> tuple[float, bool, str]:
    """
    Invoke engine under semaphore concurrency control.
    Returns (elapsed_ms, success, runtime_mode).
    """
    from apps.api_server.compute.mojo_adapter import invoke_engine

    async with semaphore:
        t0 = time.perf_counter()
        try:
            result = await invoke_engine(_PAYLOAD)
            elapsed = (time.perf_counter() - t0) * 1000
            mode = "pool" if result.get("_proto") == 1 else "subprocess"
            return elapsed, True, mode
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            return elapsed, False, "error"


async def benchmark_at_concurrency(
    concurrency: int,
    n_requests: int,
) -> dict[str, Any]:
    """
    Run n_requests with `concurrency` simultaneous requests in flight.
    Returns latency stats dict.
    """
    semaphore = asyncio.Semaphore(concurrency)

    # Fire all requests concurrently (limited by semaphore)
    tasks = [_invoke_one(semaphore) for _ in range(n_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    latencies: list[float] = []
    errors = 0
    mode = "unknown"
    for r in results:
        if isinstance(r, BaseException):
            errors += 1
            continue
        elapsed, success, m = r  # type: ignore[misc]  # narrowed by BaseException guard above
        if success:
            latencies.append(elapsed)
            mode = m
        else:
            errors += 1

    if not latencies:
        return {
            "concurrency": concurrency,
            "n_requests": n_requests,
            "errors": errors,
            "error": "all requests failed",
        }

    latencies.sort()
    n = len(latencies)
    return {
        "concurrency": concurrency,
        "n_requests": n_requests,
        "n_succeeded": n,
        "errors": errors,
        "error_rate_pct": round(errors / n_requests * 100, 1),
        "p50_ms": round(latencies[n // 2], 2),
        "p95_ms": round(latencies[max(0, int(n * 0.95) - 1)], 2),
        "p99_ms": round(latencies[max(0, int(n * 0.99) - 1)], 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(latencies[0], 2),
        "max_ms": round(latencies[-1], 2),
        "mode": mode,
    }


async def run_concurrency_benchmarks() -> list[dict[str, Any]]:
    """Warmup, then run all concurrency levels sequentially."""
    from apps.api_server.compute.mojo_adapter import invoke_engine

    print(f"[warmup] {N_WARMUP} requests...", flush=True)
    warmup_tasks = [invoke_engine(_PAYLOAD) for _ in range(N_WARMUP)]
    await asyncio.gather(*warmup_tasks, return_exceptions=True)

    results = []
    for level in CONCURRENCY_LEVELS:
        print(f"  Testing concurrency={level} ({REQUESTS_PER_LEVEL} requests)...", flush=True)
        stats = await benchmark_at_concurrency(level, REQUESTS_PER_LEVEL)
        results.append(stats)

    return results


def print_concurrency_table(results: list[dict[str, Any]]) -> None:
    print("\n## Concurrency Benchmark Results\n")
    print(
        f"Payload: 10k Monte Carlo, 3 variables  |  "
        f"Requests/level: {REQUESTS_PER_LEVEL}  |  "
        f"Levels: {CONCURRENCY_LEVELS}\n"
    )
    print("| Concurrency | Mode | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Errors | Error% |")
    print("|-------------|------|----------|----------|----------|-----------|--------|--------|")
    for r in results:
        if "error" in r and "p50_ms" not in r:
            print(f"| {r['concurrency']:>11} | {'?':>4} | FAILED | | | | | |")
            continue
        mode_icon = "🚀" if r["mode"] == "pool" else "🐢"
        print(
            f"| {r['concurrency']:>11} | {mode_icon} {r['mode']:<6} | "
            f"{r['p50_ms']:>8} | {r['p95_ms']:>8} | {r['p99_ms']:>8} | "
            f"{r['mean_ms']:>9} | {r['errors']:>6} | {r['error_rate_pct']:>5}% |"
        )

    # Summary
    print()
    any_errors = any(r.get("error_rate_pct", 0) > 0 for r in results if "p50_ms" in r)
    all_pool = all(r.get("mode") == "pool" for r in results if "p50_ms" in r)
    if all_pool:
        print("✅ All concurrency levels used pool runtime (no subprocess fallback)")
    else:
        print("⚠️  Some levels used subprocess fallback — ensure pool is running")
    if any_errors:
        print("⚠️  Errors detected under load — check MOJO_POOL_SIZE and MOJO_ACQUIRE_TIMEOUT_S")
    else:
        print("✅ Zero errors across all concurrency levels")

    # Latency degradation check (p99 at max concurrency vs p50 at concurrency=1)
    if len(results) >= 2 and "p50_ms" in results[0] and "p99_ms" in results[-1]:
        base_p50 = results[0]["p50_ms"]
        peak_p99 = results[-1]["p99_ms"]
        degradation = peak_p99 / base_p50 if base_p50 > 0 else 0
        print(
            f"\nLatency degradation: p50@{CONCURRENCY_LEVELS[0]}={base_p50}ms → "
            f"p99@{CONCURRENCY_LEVELS[-1]}={peak_p99}ms  "
            f"(ratio: {degradation:.1f}x)"
        )
        if degradation > 10:
            print("⚠️  High degradation — increase MOJO_POOL_SIZE or review worker saturation")
        else:
            print("✅ Degradation within acceptable range")


if __name__ == "__main__":
    print("Codna Concurrency Benchmark")
    print(f"Levels: {CONCURRENCY_LEVELS}  |  Requests/level: {REQUESTS_PER_LEVEL}")
    print(
        f"MOJO_ALLOW_SUBPROCESS_FALLBACK={os.environ.get('MOJO_ALLOW_SUBPROCESS_FALLBACK', 'true')}"
    )
    print()
    results = asyncio.run(run_concurrency_benchmarks())
    print_concurrency_table(results)
