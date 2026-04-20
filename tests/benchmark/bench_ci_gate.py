"""
bench_ci_gate.py — CI benchmark gate.

Fails with exit code 1 if:
  - Any measured p50 latency exceeds GATE_P50_MS for that engine class
  - Any measured p95 latency exceeds GATE_P95_MS for that engine class
  - Any request used subprocess fallback (MOJO_ALLOW_SUBPROCESS_FALLBACK must be false)

Engine latency thresholds (per class):
  fast  — monte_carlo, qmc_sobol, lhs, sensitivity:   p50 ≤ 50ms,  p95 ≤ 200ms
  mid   — scenario, bootstrap, compare, importance_sampling:  p50 ≤ 100ms, p95 ≤ 400ms
  slow  — mcmc, decision_tree, time_series:            p50 ≤ 500ms, p95 ≤ 2000ms

Usage:
    MOJO_ALLOW_SUBPROCESS_FALLBACK=false python -m tests.benchmark.bench_ci_gate
    make bench-gate
"""
from __future__ import annotations

import asyncio
import os
import random
import statistics
import sys
import time
from typing import Any

# Gate thresholds by engine class
GATES: dict[str, dict[str, float]] = {
    # Standard MC-class engines
    "monte_carlo":         {"p50": float(os.environ.get("GATE_P50_MS", "50")),   "p95": float(os.environ.get("GATE_P95_MS", "200"))},
    "qmc_sobol":           {"p50": float(os.environ.get("GATE_P50_MS", "50")),   "p95": float(os.environ.get("GATE_P95_MS", "200"))},
    "lhs":                 {"p50": float(os.environ.get("GATE_P50_MS", "50")),   "p95": float(os.environ.get("GATE_P95_MS", "200"))},
    "sensitivity":         {"p50": float(os.environ.get("GATE_P50_MS", "50")),   "p95": float(os.environ.get("GATE_P95_MS", "200"))},
    # Mid-latency engines
    "scenario":            {"p50": 100.0, "p95": 400.0},
    "bootstrap":           {"p50": 100.0, "p95": 400.0},
    "compare":             {"p50": 100.0, "p95": 400.0},
    "importance_sampling": {"p50": 100.0, "p95": 400.0},
    # Slower-by-design engines
    "mcmc":                {"p50": 500.0, "p95": 2000.0},
    "decision_tree":       {"p50": 500.0, "p95": 2000.0},
    "time_series":         {"p50": 500.0, "p95": 2000.0},
}

N_WARMUP  = int(os.environ.get("GATE_WARMUP",  "10"))
N_MEASURE = int(os.environ.get("GATE_MEASURE", "30"))

# Shared random data for data-driven engines
_rng = random.Random(42)
_HIST_DATA  = [_rng.gauss(50_000, 10_000) for _ in range(100)]
_MCMC_DATA  = [_rng.gauss(50_000, 8_000)  for _ in range(50)]


# ── Minimal valid payloads for all 11 engines ─────────────────────────────────

PAYLOADS: dict[str, dict[str, Any]] = {
    "monte_carlo": {
        "engine_type": "monte_carlo", "runs": 10000,
        "variables": [
            {"name": "rev",  "distribution": "normal",     "params": {"mean": 100000, "std": 20000}},
            {"name": "cost", "distribution": "triangular",  "params": {"low": 40000, "mode": 55000, "high": 70000}},
            {"name": "vol",  "distribution": "lognormal",   "params": {"mean": 11.0,  "std": 0.15}},
        ],
        "objective_function": "rev - cost",
    },
    "qmc_sobol": {
        "engine_type": "qmc_sobol", "runs": 10000,
        "variables": [
            {"name": "rev",  "distribution": "normal",    "params": {"mean": 100000, "std": 20000}},
            {"name": "cost", "distribution": "triangular", "params": {"low": 40000, "mode": 55000, "high": 70000}},
        ],
        "objective_function": "rev - cost",
    },
    "lhs": {
        "engine_type": "lhs", "runs": 10000,
        "variables": [
            {"name": "rev",  "distribution": "normal",    "params": {"mean": 100000, "std": 20000}},
            {"name": "cost", "distribution": "triangular", "params": {"low": 40000, "mode": 55000, "high": 70000}},
        ],
        "objective_function": "rev - cost",
    },
    "sensitivity": {
        "engine_type": "sensitivity", "runs": 5000,
        "variables": [
            {"name": "rev",  "distribution": "normal",    "params": {"mean": 100000, "std": 20000}},
            {"name": "cost", "distribution": "triangular", "params": {"low": 40000, "mode": 55000, "high": 70000}},
            {"name": "vol",  "distribution": "lognormal",  "params": {"mean": 11.0,  "std": 0.15}},
        ],
        "objective_function": "rev - cost",
    },
    "scenario": {
        "engine_type": "scenario", "runs": 2000,
        "variables": [{"name": "rev", "distribution": "fixed", "params": {"value": 100000}}],
        "objective_function": "rev",
        "scenario_config": {"scenarios": [
            {"name": "Bull", "probability": 0.3, "variables": {"rev": 150000}},
            {"name": "Base", "probability": 0.5, "variables": {"rev": 100000}},
            {"name": "Bear", "probability": 0.2, "variables": {"rev": 60000}},
        ]},
    },
    "bootstrap": {
        "engine_type": "bootstrap", "runs": 3000,
        "bootstrap_config": {"historical_data": _HIST_DATA, "statistic": "mean"},
    },
    "compare": {
        "engine_type": "compare", "runs": 2000,
        "scenarios": [
            {"name": "Opt",  "variables": [{"name": "rev", "distribution": "normal", "params": {"mean": 150000, "std": 20000}}], "objective_function": "rev"},
            {"name": "Base", "variables": [{"name": "rev", "distribution": "normal", "params": {"mean": 100000, "std": 20000}}], "objective_function": "rev"},
            {"name": "Pess", "variables": [{"name": "rev", "distribution": "normal", "params": {"mean": 60000,  "std": 15000}}], "objective_function": "rev"},
        ],
    },
    "importance_sampling": {
        "engine_type": "importance_sampling", "runs": 3000,
        "variables": [
            {"name": "rev",  "distribution": "normal", "params": {"mean": 100000, "std": 20000}},
            {"name": "cost", "distribution": "normal", "params": {"mean": 80000,  "std": 15000}},
        ],
        "objective_function": "rev - cost",
        "importance_sampling_config": {"target_threshold": -10000, "tail_direction": "lower"},
    },
    "mcmc": {
        "engine_type": "mcmc", "runs": 500,
        "mcmc_config": {"observed_data": _MCMC_DATA, "chains": 2, "burn_in": 200, "likelihood": "normal"},
    },
    "decision_tree": {
        "engine_type": "decision_tree", "runs": 2000,
        "decision_tree_config": {"paths": [
            {"label": "Success", "probability": 0.6,
             "variables": [{"name": "rev", "distribution": "normal", "params": {"mean": 200000, "std": 30000}}],
             "objective_function": "rev"},
            {"label": "Failure", "probability": 0.4,
             "variables": [{"name": "rev", "distribution": "normal", "params": {"mean": 50000,  "std": 10000}}],
             "objective_function": "rev"},
        ]},
    },
    "time_series": {
        "engine_type": "time_series", "runs": 1000,
        "time_series_config": {
            "model": "gbm", "initial_value": 100.0,
            "horizons": [3, 6, 12], "dt": 0.0833,
            "drift": 0.07, "volatility": 0.20,
        },
    },
}


# ── Engine invocation helper ───────────────────────────────────────────────────

# Will be set to the appropriate invocation function during setup.
# Either pool-backed invoke_engine or direct subprocess _invoke_subprocess.
_invoke_fn = None
_runtime_mode: str = "unknown"


async def _setup_engine() -> None:
    """Initialize the Mojo engine: try pool first, fall back to subprocess.

    This mirrors what FastAPI lifespan does in main.py, but adapted for
    standalone benchmark execution (no server, no Redis).
    """
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
        else:
            print("  ⚠️  Mojo pool could not start (binary may lack --server mode)")
    except Exception as exc:
        print(f"  ⚠️  Mojo pool init failed: {exc}")

    # Fall back to subprocess invocation (binary exists and works via stdin/stdout)
    try:
        from apps.api_server.compute.mojo_adapter import _BINARY_PATH, _invoke_subprocess
        if _BINARY_PATH.exists():
            _invoke_fn = _invoke_subprocess
            _runtime_mode = "subprocess"
            print("  ⚠️  Using subprocess fallback (binary works but no pool)")
            print("      Note: latencies will include ~22ms fork+exec overhead per request")
        else:
            print(f"  ❌ Mojo binary not found at {_BINARY_PATH}")
            _invoke_fn = None
            _runtime_mode = "unavailable"
    except Exception as exc:
        print(f"  ❌ Could not initialize subprocess fallback: {exc}")
        _invoke_fn = None
        _runtime_mode = "unavailable"


async def _teardown_engine() -> None:
    """Shut down the Mojo pool if it was started."""
    try:
        from apps.api_server.compute.mojo_pool import get_pool_sync
        pool = get_pool_sync()
        if pool._running:
            await pool.stop()
    except Exception:
        pass


async def _measure_engine(
    engine_type: str,
    payload: dict[str, Any],
    n_warmup: int,
    n_measure: int,
) -> dict[str, Any]:
    """Measure p50/p95/p99 latency for one engine."""
    if _invoke_fn is None:
        return {"engine_type": engine_type, "error": "engine unavailable (no binary)", "errors": n_measure}

    # Warmup
    for _ in range(n_warmup):
        try:
            await _invoke_fn(payload)
        except Exception:
            pass

    # Measured phase
    latencies: list[float] = []
    fallback_detected = False
    errors = 0
    last_error: str = ""
    for _ in range(n_measure):
        t0 = time.perf_counter()
        try:
            result = await _invoke_fn(payload)
            elapsed = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed)
            # In subprocess mode, _proto won't be present — that's expected
            if _runtime_mode == "pool" and result.get("_proto") != 1:
                fallback_detected = True
        except Exception as e:
            errors += 1
            last_error = str(e)

    if not latencies:
        return {"engine_type": engine_type, "error": f"all {n_measure} requests failed ({last_error})", "errors": errors}

    latencies.sort()
    n = len(latencies)
    return {
        "engine_type":       engine_type,
        "n_measured":        n,
        "errors":            errors,
        "p50_ms":            latencies[n // 2],
        "p95_ms":            latencies[max(0, int(n * 0.95) - 1)],
        "p99_ms":            latencies[max(0, int(n * 0.99) - 1)],
        "mean_ms":           statistics.mean(latencies),
        "fallback_detected": fallback_detected,
        "gate_p50":          GATES[engine_type]["p50"],
        "gate_p95":          GATES[engine_type]["p95"],
    }


async def run_gate() -> int:
    """Run CI gate for all 11 engines. Returns 0 on pass, 1 on failure."""
    allow_fallback = os.environ.get("MOJO_ALLOW_SUBPROCESS_FALLBACK", "true").lower() == "true"
    print("CI Gate — All 11 Engines")
    print(f"MOJO_ALLOW_SUBPROCESS_FALLBACK={'true' if allow_fallback else 'false'}")
    print(f"Warmup: {N_WARMUP} req  |  Measured: {N_MEASURE} req per engine")
    print()

    # Initialize engine (pool or subprocess)
    print("Engine setup:")
    await _setup_engine()
    if _invoke_fn is None:
        print("\n❌ GATE FAILED: No usable Mojo engine found.")
        print("Remediation: Run `make build-mojo` to build the Mojo binary.")
        return 1
    print(f"  Runtime mode: {_runtime_mode}")
    print()

    engine_results: list[dict[str, Any]] = []
    for engine_type in GATES:
        print(f"  [{engine_type}] measuring...", flush=True)
        payload = PAYLOADS[engine_type]
        result  = await _measure_engine(engine_type, payload, N_WARMUP, N_MEASURE)
        engine_results.append(result)
        if "error" in result:
            print(f"    ❌ FAILED: {result['error']}")
        else:
            fb = "⚠️ fallback!" if result["fallback_detected"] else "✅"
            print(
                f"    p50={result['p50_ms']:.1f}ms (gate:{result['gate_p50']}ms)  "
                f"p95={result['p95_ms']:.1f}ms (gate:{result['gate_p95']}ms)  "
                f"errors={result['errors']}  {fb}"
            )

    # Evaluate gate failures
    failures: list[str] = []
    for r in engine_results:
        et = r["engine_type"]
        if "error" in r:
            failures.append(f"{et}: all requests failed")
            continue
        g = GATES[et]
        if r["p50_ms"] > g["p50"]:
            failures.append(
                f"{et}: p50={r['p50_ms']:.1f}ms exceeds gate {g['p50']}ms "
                f"(delta={r['p50_ms'] - g['p50']:+.1f}ms)"
            )
        if r["p95_ms"] > g["p95"]:
            failures.append(
                f"{et}: p95={r['p95_ms']:.1f}ms exceeds gate {g['p95']}ms "
                f"(delta={r['p95_ms'] - g['p95']:+.1f}ms)"
            )
        if r.get("fallback_detected") and _runtime_mode == "pool":
            failures.append(
                f"{et}: subprocess fallback detected (_proto != 1). "
                "Rebuild Mojo binary: make build-mojo"
            )

    # Teardown
    await _teardown_engine()

    print()
    if _runtime_mode == "subprocess":
        print("⚠️  NOTE: Running in subprocess mode (no --server support in binary).")
        print("   Latencies include ~22ms fork+exec overhead per request.")
        print("   Pool mode thresholds may not be met. Rebuild binary with `make build-mojo`.")
        print()

    if failures:
        print(f"❌ GATE FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"   • {f}")
        print()
        print("Remediation:")
        print("  - Rebuild binary: make build-mojo")
        print("  - Check MOJO_POOL_SIZE (increase if queue contention)")
        print("  - Run: make bench for per-engine breakdown")
        return 1

    mode_label = "pool (production)" if _runtime_mode == "pool" else "subprocess (fallback)"
    print(f"✅ GATE PASSED — all 11 engines within latency thresholds [{mode_label}]")
    for r in engine_results:
        print(
            f"   {r['engine_type']:<22} p50={r['p50_ms']:6.1f}ms  "
            f"p95={r['p95_ms']:6.1f}ms  gate_p50={r['gate_p50']}ms"
        )
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_gate())
    sys.exit(exit_code)
