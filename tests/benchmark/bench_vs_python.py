"""
bench_vs_python.py — Mojo vs Python/NumPy/SciPy baseline comparison.

Compares Mojo engine runtime against equivalent pure-Python NumPy/SciPy
implementations for Monte Carlo, LHS, and Bootstrap across three workload tiers:

  - Light:      10k runs ×  3 variables  (original — IPC-dominated)
  - Production: 50k runs × 10 variables  (realistic for 500k users/day)
  - Heavy:     100k runs × 10 variables  (stress test — compute-dominated)

As N_RUNS increases, Mojo's SIMD+parallel advantage grows while IPC overhead
stays constant at ~0.6ms.

Outputs a markdown table with speedup ratios per tier.

Usage:
    python -m tests.benchmark.bench_vs_python
    make bench-vs-python

Requirements:
    pip install numpy scipy
"""

from __future__ import annotations

import asyncio
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

N_WARMUP = int(os.environ.get("BENCH_VS_PYTHON_WARMUP", "5"))
N_MEASURE = int(os.environ.get("BENCH_VS_PYTHON_MEASURE", "20"))

# ── Tier 1: Light (original — IPC-dominated) ──────────────────────────────────

LIGHT_RUNS = 10_000
LIGHT_VARIABLES = [
    {"name": "rev", "distribution": "normal", "params": {"mean": 100_000, "std": 20_000}},
    {
        "name": "cost",
        "distribution": "triangular",
        "params": {"low": 40_000, "mode": 55_000, "high": 70_000},
    },
    {"name": "vol", "distribution": "lognormal", "params": {"mean": 11.0, "std": 0.15}},
]
LIGHT_OBJ = "rev - cost"

# ── Tier 2: Production (realistic — 500k users/day workload) ──────────────────

PROD_RUNS = 50_000
PROD_VARIABLES = [
    {"name": "revenue", "distribution": "normal", "params": {"mean": 500000, "std": 100000}},
    {
        "name": "cogs",
        "distribution": "triangular",
        "params": {"low": 200000, "mode": 280000, "high": 350000},
    },
    {"name": "opex", "distribution": "lognormal", "params": {"mean": 11.5, "std": 0.3}},
    {"name": "headcount", "distribution": "uniform", "params": {"low": 50, "high": 120}},
    {"name": "churn", "distribution": "beta", "params": {"alpha": 2, "beta": 10}},
    {"name": "conversion", "distribution": "beta", "params": {"alpha": 5, "beta": 20}},
    {"name": "price", "distribution": "triangular", "params": {"low": 45, "mode": 65, "high": 95}},
    {"name": "volume", "distribution": "normal", "params": {"mean": 10000, "std": 2000}},
    {"name": "discount", "distribution": "uniform", "params": {"low": 0.05, "high": 0.25}},
    {
        "name": "tax_rate",
        "distribution": "triangular",
        "params": {"low": 0.15, "mode": 0.22, "high": 0.35},
    },
]
PROD_OBJ = "revenue - cogs - opex + price * volume * (1 - discount) - tax_rate * revenue"

# ── Tier 3: Heavy (stress test — compute-dominated) ───────────────────────────

HEAVY_RUNS = 100_000
# Same 10 variables as production, just 2x the runs
HEAVY_VARIABLES = PROD_VARIABLES
HEAVY_OBJ = PROD_OBJ

# Bootstrap shared
BOOTSTRAP_DATA_SIZE = 500


# ── Python / NumPy baseline implementations ───────────────────────────────────

# -- Light tier baselines --


def _python_mc_light(n: int = LIGHT_RUNS) -> float:
    """Pure NumPy Monte Carlo — light tier (3 vars)."""
    import numpy as np

    rng = np.random.default_rng(42)
    rev = rng.normal(100_000, 20_000, n)
    cost = rng.triangular(40_000, 55_000, 70_000, n)
    vol = rng.lognormal(11.0, 0.15, n)
    out = rev - cost
    _ = vol.mean(), out.mean(), np.percentile(out, [5, 25, 50, 75, 95])
    return float(out.mean())


def _python_lhs_light(n: int = LIGHT_RUNS) -> float:
    """Latin Hypercube Sampling — light tier (3 vars)."""
    import numpy as np
    from scipy.stats import lognorm, norm, triang  # type: ignore[import]

    rng = np.random.default_rng(42)
    n_vars = 3
    samples = np.zeros((n, n_vars))
    for j in range(n_vars):
        perm = rng.permutation(n)
        u = (perm + rng.random(n)) / n
        samples[:, j] = u
    rev = norm.ppf(samples[:, 0], loc=100_000, scale=20_000)
    c_val = (55_000 - 40_000) / (70_000 - 40_000)
    cost = triang.ppf(samples[:, 1], c=c_val, loc=40_000, scale=30_000)
    vol = lognorm.ppf(samples[:, 2], s=0.15, scale=np.exp(11.0))
    out = rev - cost
    _ = vol.mean(), out.mean(), np.percentile(out, [5, 50, 95])
    return float(out.mean())


def _python_bootstrap_light(n: int = LIGHT_RUNS) -> float:
    """Bootstrap resampling — light tier."""
    import numpy as np

    rng = np.random.default_rng(42)
    data = rng.normal(50_000, 10_000, BOOTSTRAP_DATA_SIZE)
    idx = rng.integers(0, BOOTSTRAP_DATA_SIZE, size=(n, BOOTSTRAP_DATA_SIZE))
    stats = data[idx].mean(axis=1)
    _ = stats.mean(), np.percentile(stats, [2.5, 97.5])
    return float(stats.mean())


# -- Production tier baselines (10 vars) --


def _python_mc_production(n: int = PROD_RUNS) -> float:
    """Pure NumPy Monte Carlo — production tier (10 vars, complex expression)."""
    import numpy as np

    rng = np.random.default_rng(42)
    revenue = rng.normal(500000, 100000, n)
    cogs = rng.triangular(200000, 280000, 350000, n)
    opex = rng.lognormal(11.5, 0.3, n)
    headcount = rng.uniform(50, 120, n)
    churn = rng.beta(2, 10, n)
    conversion = rng.beta(5, 20, n)
    price = rng.triangular(45, 65, 95, n)
    volume = rng.normal(10000, 2000, n)
    discount = rng.uniform(0.05, 0.25, n)
    tax_rate = rng.triangular(0.15, 0.22, 0.35, n)
    out = revenue - cogs - opex + price * volume * (1 - discount) - tax_rate * revenue
    _ = (
        headcount.mean(),
        churn.mean(),
        conversion.mean(),
        out.mean(),
        np.percentile(out, [5, 25, 50, 75, 95]),
    )
    return float(out.mean())


def _python_lhs_production(n: int = PROD_RUNS) -> float:
    """Latin Hypercube Sampling — production tier (10 vars)."""
    import numpy as np
    from scipy.stats import beta, lognorm, norm, triang, uniform  # type: ignore[import]

    rng = np.random.default_rng(42)
    n_vars = 10
    samples = np.zeros((n, n_vars))
    for j in range(n_vars):
        perm = rng.permutation(n)
        u = (perm + rng.random(n)) / n
        samples[:, j] = u
    revenue = norm.ppf(samples[:, 0], loc=500000, scale=100000)
    c_cogs = (280000 - 200000) / (350000 - 200000)
    cogs = triang.ppf(samples[:, 1], c=c_cogs, loc=200000, scale=150000)
    opex = lognorm.ppf(samples[:, 2], s=0.3, scale=np.exp(11.5))
    headcount = uniform.ppf(samples[:, 3], loc=50, scale=70)
    churn = beta.ppf(samples[:, 4], 2, 10)
    conversion = beta.ppf(samples[:, 5], 5, 20)
    c_price = (65 - 45) / (95 - 45)
    price = triang.ppf(samples[:, 6], c=c_price, loc=45, scale=50)
    volume = norm.ppf(samples[:, 7], loc=10000, scale=2000)
    discount = uniform.ppf(samples[:, 8], loc=0.05, scale=0.20)
    c_tax = (0.22 - 0.15) / (0.35 - 0.15)
    tax_rate = triang.ppf(samples[:, 9], c=c_tax, loc=0.15, scale=0.20)
    out = revenue - cogs - opex + price * volume * (1 - discount) - tax_rate * revenue
    _ = (
        headcount.mean(),
        churn.mean(),
        conversion.mean(),
        out.mean(),
        np.percentile(out, [5, 50, 95]),
    )
    return float(out.mean())


def _python_bootstrap_production(n: int = PROD_RUNS) -> float:
    """Bootstrap resampling — production tier."""
    import numpy as np

    rng = np.random.default_rng(42)
    data = rng.normal(50_000, 10_000, BOOTSTRAP_DATA_SIZE)
    idx = rng.integers(0, BOOTSTRAP_DATA_SIZE, size=(n, BOOTSTRAP_DATA_SIZE))
    stats = data[idx].mean(axis=1)
    _ = stats.mean(), np.percentile(stats, [2.5, 97.5])
    return float(stats.mean())


# -- Heavy tier baselines (10 vars, 100k runs) --


def _python_mc_heavy(n: int = HEAVY_RUNS) -> float:
    """Pure NumPy Monte Carlo — heavy tier (10 vars, 100k runs)."""
    return _python_mc_production(n)


def _python_lhs_heavy(n: int = HEAVY_RUNS) -> float:
    """Latin Hypercube Sampling — heavy tier (10 vars, 100k runs)."""
    return _python_lhs_production(n)


def _python_bootstrap_heavy(n: int = HEAVY_RUNS) -> float:
    """Bootstrap resampling — heavy tier (100k runs)."""
    return _python_bootstrap_production(n)


# ── Shared timing helper ──────────────────────────────────────────────────────


def _bench_python_fn(fn: Any, n_warmup: int, n_measure: int) -> dict[str, float]:
    """Time a Python baseline function."""
    for _ in range(n_warmup):
        fn()
    latencies = []
    for _ in range(n_measure):
        t0 = time.perf_counter()
        fn()
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    n = len(latencies)
    return {
        "p50_ms": statistics.median(latencies),
        "p95_ms": latencies[int(n * 0.95)],
        "mean_ms": statistics.mean(latencies),
        "min_ms": latencies[0],
        "max_ms": latencies[-1],
    }


# ── Engine lifecycle (pool/subprocess) ─────────────────────────────────────────

_invoke_fn = None
_runtime_mode: str = "unknown"


async def _setup_engine() -> None:
    """Initialize the Mojo engine: try pool first, fall back to subprocess.

    This mirrors what bench_ci_gate.py does — standalone lifecycle management
    so we don't need a running FastAPI server.
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

    # Fall back to subprocess invocation
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


# ── Mojo benchmarks via _invoke_fn ────────────────────────────────────────────


async def _bench_mojo(payload: dict[str, Any], n_warmup: int, n_measure: int) -> dict[str, Any]:
    """Time the Mojo engine via the initialized _invoke_fn (pool or subprocess)."""
    if _invoke_fn is None:
        return {"error": "engine unavailable (no binary)", "mode": _runtime_mode}

    for _ in range(n_warmup):
        try:
            await _invoke_fn(payload)
        except Exception:
            pass

    latencies = []
    errors = 0
    for _ in range(n_measure):
        t0 = time.perf_counter()
        try:
            _ = await _invoke_fn(payload)
            elapsed = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed)
        except Exception:
            errors += 1

    if not latencies:
        return {"error": "all Mojo invocations failed", "mode": _runtime_mode}

    latencies.sort()
    n = len(latencies)
    return {
        "p50_ms": statistics.median(latencies),
        "p95_ms": latencies[int(n * 0.95)],
        "mean_ms": statistics.mean(latencies),
        "min_ms": latencies[0],
        "max_ms": latencies[-1],
        "errors": errors,
        "mode": _runtime_mode,
    }


# ── Tier runner ────────────────────────────────────────────────────────────────


async def _run_tier(
    tier_name: str,
    n_runs: int,
    variables: list[dict],
    obj_fn: str,
    py_mc_fn: Any,
    py_lhs_fn: Any,
    py_bs_fn: Any,
) -> list[dict[str, Any]]:
    """Run MC, LHS, Bootstrap comparison for one tier."""
    results = []
    label = f"[{tier_name}]"

    # 1. Monte Carlo
    print(f"  {label} Monte Carlo — Python/NumPy baseline...", flush=True)
    py_mc = _bench_python_fn(py_mc_fn, N_WARMUP, N_MEASURE)
    print(f"  {label} Monte Carlo — Mojo...", flush=True)
    mojo_mc = await _bench_mojo(
        {
            "engine_type": "monte_carlo",
            "runs": n_runs,
            "variables": variables,
            "objective_function": obj_fn,
        },
        N_WARMUP,
        N_MEASURE,
    )
    results.append(
        {
            "tier": tier_name,
            "engine": "monte_carlo",
            "runs": n_runs,
            "n_vars": len(variables),
            "python": py_mc,
            "mojo": mojo_mc,
            "speedup_p50": round(py_mc["p50_ms"] / mojo_mc["p50_ms"], 1)
            if "p50_ms" in mojo_mc
            else None,
        }
    )

    # 2. LHS
    print(f"  {label} LHS — Python/NumPy+SciPy baseline...", flush=True)
    try:
        py_lhs = _bench_python_fn(py_lhs_fn, N_WARMUP, N_MEASURE)
    except ImportError:
        py_lhs = {"error": "scipy not installed — run: pip install scipy"}
    print(f"  {label} LHS — Mojo...", flush=True)
    mojo_lhs = await _bench_mojo(
        {
            "engine_type": "lhs",
            "runs": n_runs,
            "variables": variables,
            "objective_function": obj_fn,
        },
        N_WARMUP,
        N_MEASURE,
    )
    speedup_lhs = None
    if "p50_ms" in py_lhs and "p50_ms" in mojo_lhs:
        speedup_lhs = round(py_lhs["p50_ms"] / mojo_lhs["p50_ms"], 1)
    results.append(
        {
            "tier": tier_name,
            "engine": "lhs",
            "runs": n_runs,
            "n_vars": len(variables),
            "python": py_lhs,
            "mojo": mojo_lhs,
            "speedup_p50": speedup_lhs,
        }
    )

    # 3. Bootstrap
    print(f"  {label} Bootstrap — Python/NumPy baseline...", flush=True)
    rng = random.Random(42)
    hist = [rng.gauss(50_000, 10_000) for _ in range(BOOTSTRAP_DATA_SIZE)]
    py_bs = _bench_python_fn(py_bs_fn, N_WARMUP, N_MEASURE)
    print(f"  {label} Bootstrap — Mojo...", flush=True)
    mojo_bs = await _bench_mojo(
        {
            "engine_type": "bootstrap",
            "runs": n_runs,
            "bootstrap_config": {"historical_data": hist, "statistic": "mean"},
        },
        N_WARMUP,
        N_MEASURE,
    )
    results.append(
        {
            "tier": tier_name,
            "engine": "bootstrap",
            "runs": n_runs,
            "n_vars": len(variables) if variables else 0,
            "python": py_bs,
            "mojo": mojo_bs,
            "speedup_p50": round(py_bs["p50_ms"] / mojo_bs["p50_ms"], 1)
            if "p50_ms" in mojo_bs
            else None,
        }
    )

    return results


# ── Main comparison runner ─────────────────────────────────────────────────────


async def run_comparison() -> list[dict[str, Any]]:
    """Run all three tiers: light, production, heavy."""
    # Initialize engine (pool or subprocess)
    print("Engine setup:")
    await _setup_engine()
    if _invoke_fn is None:
        print("\n❌ No usable Mojo engine found. Only Python baselines will run.")
    print(f"  Runtime mode: {_runtime_mode}\n")

    all_results: list[dict[str, Any]] = []

    # ── Tier 1: Light (original) ──
    print("━" * 60)
    print("  TIER 1: Light — 10k runs × 3 variables (IPC-dominated)")
    print("━" * 60)
    tier1 = await _run_tier(
        "light",
        LIGHT_RUNS,
        LIGHT_VARIABLES,
        LIGHT_OBJ,
        _python_mc_light,
        _python_lhs_light,
        _python_bootstrap_light,
    )
    all_results.extend(tier1)

    # ── Tier 2: Production ──
    print()
    print("━" * 60)
    print("  TIER 2: Production — 50k runs × 10 variables (realistic)")
    print("━" * 60)
    tier2 = await _run_tier(
        "production",
        PROD_RUNS,
        PROD_VARIABLES,
        PROD_OBJ,
        _python_mc_production,
        _python_lhs_production,
        _python_bootstrap_production,
    )
    all_results.extend(tier2)

    # ── Tier 3: Heavy ──
    print()
    print("━" * 60)
    print("  TIER 3: Heavy — 100k runs × 10 variables (stress test)")
    print("━" * 60)
    tier3 = await _run_tier(
        "heavy",
        HEAVY_RUNS,
        HEAVY_VARIABLES,
        HEAVY_OBJ,
        _python_mc_heavy,
        _python_lhs_heavy,
        _python_bootstrap_heavy,
    )
    all_results.extend(tier3)

    # Teardown
    await _teardown_engine()

    return all_results


def print_comparison_table(results: list[dict[str, Any]]) -> None:
    """Print a multi-tier markdown results table."""
    print("\n## Mojo vs Python/NumPy Baseline Comparison\n")
    print(f"Measured iterations: {N_MEASURE}  |  Warmup: {N_WARMUP}\n")

    # Group by tier
    tiers: dict[str, list[dict]] = {}
    for r in results:
        tiers.setdefault(r["tier"], []).append(r)

    for tier_name, tier_results in tiers.items():
        n_runs = tier_results[0]["runs"]
        n_vars = tier_results[0]["n_vars"]
        print(f"### {tier_name.upper()} tier — {n_runs:,} runs × {n_vars} variables\n")
        print("| Engine | Python p50 (ms) | Mojo p50 (ms) | Speedup | Mode |")
        print("|--------|----------------|--------------|---------|------|")
        for r in tier_results:
            py = r["python"]
            mojo = r["mojo"]
            py_p50 = f"{py['p50_ms']:.2f}" if "p50_ms" in py else "N/A"
            mojo_p50 = f"{mojo['p50_ms']:.2f}" if "p50_ms" in mojo else "FAILED"
            speedup = f"{r['speedup_p50']}x" if r["speedup_p50"] else "—"
            mode_icon = "🚀" if mojo.get("mode") == "pool" else "🐢"
            print(
                f"| {r['engine']:<12} | {py_p50:>15} | {mojo_p50:>12} | {speedup:>7} | {mode_icon} {mojo.get('mode', '?')} |"
            )
        print()

    # Summary
    print("### Summary\n")
    for r in results:
        sp = r["speedup_p50"]
        tag = f"[{r['tier']}] {r['engine']}"
        if sp and sp >= 5:
            print(f"✅ {tag}: {sp}x faster than NumPy baseline")
        elif sp and sp >= 2:
            print(f"⚠️  {tag}: {sp}x faster (target: ≥5x for compute-dominated workloads)")
        elif sp and sp >= 1:
            print(f"⚠️  {tag}: {sp}x — IPC overhead may dominate at this workload size")
        elif sp:
            print(f"❌ {tag}: {sp}x — Mojo slower than NumPy. Investigate SIMD/vectorization.")

    print()
    print("Key insight: as N_RUNS increases, Mojo's SIMD+parallel advantage grows")
    print("while IPC overhead stays constant at ~0.6ms.")


if __name__ == "__main__":
    print("=" * 60)
    print("  Codna: Mojo vs Python/NumPy Baseline Comparison")
    print("  Phase 8 — Multi-Tier Workload Benchmark")
    print("=" * 60)
    print(f"  Warmup: {N_WARMUP}  |  Measured: {N_MEASURE}")
    print("  Tiers: light (10k×3), production (50k×10), heavy (100k×10)")
    print()
    results = asyncio.run(run_comparison())
    print_comparison_table(results)
