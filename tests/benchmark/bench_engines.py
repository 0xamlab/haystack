"""
bench_engines.py — Asyncio benchmark for all 11 engine types.

Records p50, p95, p99 latency for each engine via invoke_engine().
Outputs a markdown table to stdout.
Reports whether pool or subprocess path was used.

Usage:
    python -m tests.benchmark.bench_engines
    make bench
"""

from __future__ import annotations

import asyncio
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Number of requests per engine for the measured phase
N_WARMUP = int(os.environ.get("BENCH_WARMUP", "5"))
N_MEASURE = int(os.environ.get("BENCH_MEASURE", "20"))


# ── Engine payloads (minimal valid payload for each engine type) ───────────────


def _mc_payload(runs: int = 5000) -> dict[str, Any]:
    return {
        "engine_type": "monte_carlo",
        "runs": runs,
        "variables": [
            {"name": "rev", "distribution": "normal", "params": {"mean": 100000, "std": 20000}},
            {
                "name": "cost",
                "distribution": "triangular",
                "params": {"low": 40000, "mode": 60000, "high": 80000},
            },
            {"name": "units", "distribution": "uniform", "params": {"low": 100, "high": 500}},
        ],
        "objective_function": "rev - cost",
    }


def _qmc_payload(runs: int = 5000) -> dict[str, Any]:
    payload = _mc_payload(runs)
    payload["engine_type"] = "qmc_sobol"
    return payload


def _lhs_payload(runs: int = 5000) -> dict[str, Any]:
    payload = _mc_payload(runs)
    payload["engine_type"] = "lhs"
    return payload


def _bootstrap_payload(runs: int = 2000) -> dict[str, Any]:
    import random

    rng = random.Random(42)
    data = [rng.gauss(50000, 10000) for _ in range(100)]
    return {
        "engine_type": "bootstrap",
        "runs": runs,
        "bootstrap_config": {"historical_data": data, "statistic": "mean"},
    }


def _scenario_payload() -> dict[str, Any]:
    return {
        "engine_type": "scenario",
        "runs": 2000,
        "variables": [
            {"name": "rev", "distribution": "fixed", "params": {"value": 100000}},
        ],
        "objective_function": "rev",
        "scenario_config": {
            "scenarios": [
                {"name": "Bull", "probability": 0.3, "variables": {"rev": 150000}},
                {"name": "Base", "probability": 0.5, "variables": {"rev": 100000}},
                {"name": "Bear", "probability": 0.2, "variables": {"rev": 60000}},
            ]
        },
    }


def _sensitivity_payload(runs: int = 2000) -> dict[str, Any]:
    payload = _mc_payload(runs)
    payload["engine_type"] = "sensitivity"
    return payload


def _mcmc_payload(runs: int = 500) -> dict[str, Any]:
    import random

    rng = random.Random(42)
    data = [rng.gauss(50000, 8000) for _ in range(50)]
    return {
        "engine_type": "mcmc",
        "runs": runs,
        "mcmc_config": {"observed_data": data, "chains": 2, "burn_in": 200, "likelihood": "normal"},
    }


def _decision_tree_payload(runs: int = 3000) -> dict[str, Any]:
    return {
        "engine_type": "decision_tree",
        "runs": runs,
        "decision_tree_config": {
            "paths": [
                {
                    "label": "Success",
                    "probability": 0.6,
                    "variables": [
                        {
                            "name": "rev",
                            "distribution": "normal",
                            "params": {"mean": 200000, "std": 30000},
                        }
                    ],
                    "objective_function": "rev",
                },
                {
                    "label": "Failure",
                    "probability": 0.4,
                    "variables": [
                        {
                            "name": "rev",
                            "distribution": "normal",
                            "params": {"mean": 50000, "std": 10000},
                        }
                    ],
                    "objective_function": "rev",
                },
            ]
        },
    }


def _time_series_payload(runs: int = 1000) -> dict[str, Any]:
    return {
        "engine_type": "time_series",
        "runs": runs,
        "time_series_config": {
            "model": "gbm",
            "initial_value": 100.0,
            "horizons": [3, 6, 12],
            "dt": 0.0833,
            "drift": 0.07,
            "volatility": 0.20,
        },
    }


def _compare_payload(runs: int = 2000) -> dict[str, Any]:
    return {
        "engine_type": "compare",
        "runs": runs,
        "scenarios": [
            {
                "name": "Opt",
                "variables": [
                    {
                        "name": "rev",
                        "distribution": "normal",
                        "params": {"mean": 150000, "std": 20000},
                    }
                ],
                "objective_function": "rev",
            },
            {
                "name": "Base",
                "variables": [
                    {
                        "name": "rev",
                        "distribution": "normal",
                        "params": {"mean": 100000, "std": 20000},
                    }
                ],
                "objective_function": "rev",
            },
            {
                "name": "Pess",
                "variables": [
                    {
                        "name": "rev",
                        "distribution": "normal",
                        "params": {"mean": 60000, "std": 15000},
                    }
                ],
                "objective_function": "rev",
            },
        ],
    }


def _importance_sampling_payload(runs: int = 3000) -> dict[str, Any]:
    return {
        "engine_type": "importance_sampling",
        "runs": runs,
        "variables": [
            {"name": "rev", "distribution": "normal", "params": {"mean": 100000, "std": 20000}},
            {"name": "cost", "distribution": "normal", "params": {"mean": 80000, "std": 15000}},
        ],
        "objective_function": "rev - cost",
        "importance_sampling_config": {
            "target_threshold": -10000,
            "tail_direction": "lower",
        },
    }


ALL_PAYLOADS = {
    "monte_carlo": _mc_payload(),
    "qmc_sobol": _qmc_payload(),
    "lhs": _lhs_payload(),
    "bootstrap": _bootstrap_payload(),
    "scenario": _scenario_payload(),
    "sensitivity": _sensitivity_payload(),
    "mcmc": _mcmc_payload(),
    "decision_tree": _decision_tree_payload(),
    "time_series": _time_series_payload(),
    "compare": _compare_payload(),
    "importance_sampling": _importance_sampling_payload(),
}

_invoke_fn = None
_runtime_mode: str = "unknown"


async def _setup_engine() -> None:
    """Initialize the Mojo runtime for standalone benchmark execution."""
    global _invoke_fn, _runtime_mode

    try:
        from apps.api_server.compute.mojo_pool import MojoWorkerPool, set_pool

        pool = MojoWorkerPool(size=max(1, (os.cpu_count() or 4) - 1))
        await pool.start()
        if pool._running:
            set_pool(pool)
            from apps.api_server.compute.mojo_adapter import invoke_engine

            _invoke_fn = invoke_engine
            _runtime_mode = "pool"
            print(f"  ✅ Mojo pool started ({pool.size} workers)")
            return
        print("  ⚠️  Mojo pool could not start (binary may lack --server mode)")
    except Exception as exc:
        print(f"  ⚠️  Mojo pool init failed: {exc}")

    try:
        from apps.api_server.compute.mojo_adapter import _BINARY_PATH, _invoke_subprocess

        if _BINARY_PATH.exists():
            _invoke_fn = _invoke_subprocess
            _runtime_mode = "subprocess"
            print("  ⚠️  Using subprocess fallback (binary works but no pool)")
            return
        print(f"  ❌ Mojo binary not found at {_BINARY_PATH}")
    except Exception as exc:
        print(f"  ❌ Could not initialize subprocess fallback: {exc}")

    _invoke_fn = None
    _runtime_mode = "unavailable"


async def _teardown_engine() -> None:
    """Stop the Mojo pool if this benchmark started it."""
    try:
        from apps.api_server.compute.mojo_pool import get_pool_sync

        pool = get_pool_sync()
        if pool._running:
            await pool.stop()
    except Exception:
        pass


async def _time_invoke(engine_type: str, payload: dict[str, Any]) -> tuple[float, str]:
    """Invoke engine and return (elapsed_seconds, runtime_mode)."""
    if _invoke_fn is None:
        raise RuntimeError("engine unavailable")

    t0 = time.perf_counter()
    _ = await _invoke_fn(payload)
    elapsed = time.perf_counter() - t0
    return elapsed, _runtime_mode


async def benchmark_engine(
    engine_type: str,
    payload: dict[str, Any],
    n_warmup: int = N_WARMUP,
    n_measure: int = N_MEASURE,
) -> dict[str, Any]:
    """Run one engine benchmark. Returns stats dict."""
    # Warmup
    for _ in range(n_warmup):
        try:
            await _time_invoke(engine_type, payload)
        except Exception:
            pass  # warmup failures are non-fatal

    # Measured runs
    latencies: list[float] = []
    mode = "unknown"
    errors = 0
    for _ in range(n_measure):
        try:
            elapsed, m = await _time_invoke(engine_type, payload)
            latencies.append(elapsed * 1000)  # convert to ms
            mode = m
        except Exception:
            errors += 1

    if not latencies:
        return {"engine_type": engine_type, "error": "all requests failed", "mode": mode}

    latencies.sort()
    n = len(latencies)
    return {
        "engine_type": engine_type,
        "n_measured": n,
        "errors": errors,
        "p50_ms": round(latencies[n // 2], 2),
        "p95_ms": round(latencies[int(n * 0.95)], 2),
        "p99_ms": round(latencies[int(n * 0.99)], 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(latencies[0], 2),
        "max_ms": round(latencies[-1], 2),
        "mode": mode,
    }


async def run_all_benchmarks() -> list[dict[str, Any]]:
    """Run benchmarks for all 11 engine types sequentially."""
    await _setup_engine()
    results = []
    try:
        for engine_type, payload in ALL_PAYLOADS.items():
            print(f"  Benchmarking {engine_type}...", flush=True)
            stats = await benchmark_engine(engine_type, payload)
            results.append(stats)
        return results
    finally:
        await _teardown_engine()


def print_markdown_table(results: list[dict[str, Any]]) -> None:
    """Print benchmark results as a markdown table."""
    print("\n## Engine Benchmark Results\n")
    print(f"Configuration: {N_WARMUP} warmup + {N_MEASURE} measured requests per engine\n")
    print("| Engine | Mode | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Errors |")
    print("|--------|------|----------|----------|----------|-----------|--------|")
    for r in results:
        if "error" in r:
            print(f"| {r['engine_type']:<22} | {r.get('mode', '?'):>10} | FAILED | | | | |")
        else:
            mode_icon = "🚀" if r["mode"] == "pool" else "🐢"
            print(
                f"| {r['engine_type']:<22} | {mode_icon} {r['mode']:<8} | "
                f"{r['p50_ms']:>8} | {r['p95_ms']:>8} | {r['p99_ms']:>8} | "
                f"{r['mean_ms']:>9} | {r['errors']:>6} |"
            )

    # Summary
    pool_count = sum(1 for r in results if r.get("mode") == "pool")
    sub_count = sum(1 for r in results if r.get("mode") == "subprocess")
    print(f"\n**Runtime modes:** {pool_count}/11 pool, {sub_count}/11 subprocess")
    if sub_count > 0:
        print(
            f"\n⚠️  {sub_count} engine(s) used subprocess fallback. "
            "Set MOJO_ALLOW_SUBPROCESS_FALLBACK=false in production."
        )


if __name__ == "__main__":
    print("Codna Engine Benchmark — all 11 engine types")
    print(
        f"Warmup: {N_WARMUP} req  |  Measured: {N_MEASURE} req  |  MOJO_ALLOW_SUBPROCESS_FALLBACK={os.environ.get('MOJO_ALLOW_SUBPROCESS_FALLBACK', 'true')}"
    )
    print()
    results = asyncio.run(run_all_benchmarks())
    print_markdown_table(results)
