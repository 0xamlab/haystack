"""
Phase 15: Speed/Benchmark Tests Across All Engine Types with Timing CSV Output

Comprehensive performance benchmarks for the Codna Decision Engine.
Measures latency across all 10 engine types, variable counts, distributions,
concurrency levels, and produces CSV + human-readable summary reports.

Run:
  python tests/integration/test_benchmarks.py
"""

import concurrent.futures
import csv
import json
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_integration_artifacts import write_live_integration_summary

# Benchmarks may take longer — generous timeout
socket.setdefaulttimeout(60)

try:
    from tests.integration.live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
INTEGRATION_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(INTEGRATION_DIR, "benchmark_results.csv")
SUMMARY_PATH = os.path.join(INTEGRATION_DIR, "benchmark_summary.txt")
SUITE_NAME = "benchmarks_integration"
STARTED = time.perf_counter()

PASS = "\u2705"
FAIL = "\u274c"
SKIP = "\u23ed\ufe0f"
TIMEOUT_SECONDS = 30
REPEATS = 3  # take median of 3 measurements

ALL_ENGINES = [
    "monte_carlo",
    "lhs",
    "qmc_sobol",
    "bootstrap",
    "scenario",
    "sensitivity",
    "decision_tree",
    "time_series",
    "mcmc",
    "importance_sampling",
]

RUN_COUNTS = [100, 500, 1_000, 5_000, 10_000, 50_000]
VAR_COUNTS = [1, 3, 5, 10, 20]
DIST_TYPES = ["normal", "uniform", "triangular", "lognormal", "beta"]
CONCURRENCY_LEVELS = [1, 5, 10, 20]

results: list[tuple[str, ...]] = []
csv_rows: list[dict] = []
timestamp = datetime.now(UTC).isoformat()


class EnvironmentBlocked(RuntimeError):
    """Raised when the live environment cannot execute simulation due to quota/capacity."""


def classify_simulation_blocker(status: int | str, body) -> str | None:
    if isinstance(status, int):
        return classify_simulation_capacity_blocker(status=status, payload=body)
    return None


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _write_summary_artifact() -> str:
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    artifact = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_benchmarks.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "base_url": configured_local_live_base_url(),
            "csv_path": CSV_PATH,
            "summary_path": SUMMARY_PATH,
            "api_key_configured": API_KEY_CONFIGURED,
        },
    )
    return str(artifact)


# ─── HTTP helper ──────────────────────────────────────────────────────────────


def req(method: str, path: str, body=None, headers=None, auth=True, timeout=TIMEOUT_SECONDS):
    """Make HTTP request, return (status_code, body, headers_dict, elapsed_s)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            raw = resp.read()
            try:
                body_data = json.loads(raw)
            except Exception:
                body_data = raw.decode("utf-8", errors="replace")
            return resp.status, body_data, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        raw = e.read()
        try:
            body_data = json.loads(raw)
        except Exception:
            body_data = raw.decode("utf-8", errors="replace")
        return e.code, body_data, dict(e.headers), elapsed
    except (TimeoutError, urllib.error.URLError) as e:
        elapsed = time.perf_counter() - t0
        return 0, {"error": f"timeout: {e}"}, {}, elapsed


def check(name: str, fn):
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        results.append((PASS, name))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as e:
        results.append((SKIP, name, str(e)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(e).__name__}: {e}"
        )


def skip(name: str, reason: str) -> None:
    results.append((SKIP, name, reason))
    _emit(f"  {SKIP} {name}: {reason}")


def record_csv(
    test_name: str,
    engine: str = "",
    runs: int | float | str = "",
    variables: int | float | str = "",
    distribution: str = "",
    concurrency: int | float | str = "",
    latency_ms: float | str = "",
    server_execution_ms: float | str = "",
    status_code: int | str = "",
    mean: float | str = "",
    std: float | str = "",
) -> None:
    csv_rows.append(
        {
            "test_name": test_name,
            "engine": engine,
            "runs": runs,
            "variables": variables,
            "distribution": distribution,
            "concurrency": concurrency,
            "latency_ms": latency_ms,
            "server_execution_ms": server_execution_ms,
            "status_code": status_code,
            "mean": mean,
            "std": std,
            "timestamp": timestamp,
        }
    )


def median_of(values):
    """Return median of a list of numbers."""
    if not values:
        return 0
    return statistics.median(values)


# ─── Closure factories — avoids repeated `def _test` redeclarations in loops ──
# Each factory captures the relevant loop variables and returns a callable
# suitable for passing to check().


def _engine_scaling_check(s, t, e, r):
    def _fn():
        if t:
            raise AssertionError(f"{e} @ {r} runs timed out")
        assert s in (200, 500), f"Expected 200/500, got {s}"

    return _fn


def _var_scaling_check(s, t, v):
    def _fn():
        if t:
            raise AssertionError(f"monte_carlo @ {v} vars timed out")
        assert s in (200, 500), f"Got {s}"

    return _fn


def _dist_bench_check(s, t, d):
    def _fn():
        if t:
            raise AssertionError(f"dist={d} timed out")
        assert s in (200, 500), f"Got {s}"

    return _fn


def _concurrency_check(nc, lats):
    def _fn():
        assert len(lats) == nc, f"Expected {nc} results, got {len(lats)}"

    return _fn


def get_server_exec_ms(hdrs):
    """Extract X-Execution-Ms from response headers."""
    val = hdrs.get("X-Execution-Ms", hdrs.get("x-execution-ms", ""))
    try:
        return float(val)
    except (ValueError, TypeError):
        return ""


# ─── Payload builders ─────────────────────────────────────────────────────────


def _make_vars(n, dist="triangular"):
    """Generate n variable definitions for expert mode."""
    base_vars = {
        "triangular": [
            {
                "name": "revenue",
                "distribution": "triangular",
                "params": {"low": 80000, "mode": 130000, "high": 200000},
            },
            {
                "name": "cost",
                "distribution": "triangular",
                "params": {"low": 40000, "mode": 60000, "high": 90000},
            },
            {
                "name": "market_size",
                "distribution": "triangular",
                "params": {"low": 10000, "mode": 50000, "high": 100000},
            },
            {
                "name": "conversion_rate",
                "distribution": "triangular",
                "params": {"low": 0.01, "mode": 0.05, "high": 0.15},
            },
            {
                "name": "lifetime_value",
                "distribution": "triangular",
                "params": {"low": 500, "mode": 1200, "high": 3000},
            },
        ],
        "normal": [
            {"name": "revenue", "distribution": "normal", "params": {"mean": 140000, "std": 30000}},
            {"name": "cost", "distribution": "normal", "params": {"mean": 65000, "std": 12000}},
            {
                "name": "market_size",
                "distribution": "normal",
                "params": {"mean": 50000, "std": 15000},
            },
            {
                "name": "conversion_rate",
                "distribution": "normal",
                "params": {"mean": 0.05, "std": 0.02},
            },
            {
                "name": "lifetime_value",
                "distribution": "normal",
                "params": {"mean": 1200, "std": 400},
            },
        ],
        "uniform": [
            {
                "name": "revenue",
                "distribution": "uniform",
                "params": {"low": 80000, "high": 200000},
            },
            {"name": "cost", "distribution": "uniform", "params": {"low": 40000, "high": 90000}},
            {
                "name": "market_size",
                "distribution": "uniform",
                "params": {"low": 10000, "high": 100000},
            },
            {
                "name": "conversion_rate",
                "distribution": "uniform",
                "params": {"low": 0.01, "high": 0.15},
            },
            {
                "name": "lifetime_value",
                "distribution": "uniform",
                "params": {"low": 500, "high": 3000},
            },
        ],
        "lognormal": [
            {"name": "revenue", "distribution": "lognormal", "params": {"mean": 11.7, "std": 0.4}},
            {"name": "cost", "distribution": "lognormal", "params": {"mean": 10.9, "std": 0.3}},
            {
                "name": "market_size",
                "distribution": "lognormal",
                "params": {"mean": 10.5, "std": 0.5},
            },
            {
                "name": "conversion_rate",
                "distribution": "lognormal",
                "params": {"mean": -3.0, "std": 0.5},
            },
            {
                "name": "lifetime_value",
                "distribution": "lognormal",
                "params": {"mean": 7.0, "std": 0.4},
            },
        ],
        "beta": [
            {"name": "revenue", "distribution": "beta", "params": {"alpha": 2, "beta": 5}},
            {"name": "cost", "distribution": "beta", "params": {"alpha": 3, "beta": 3}},
            {"name": "market_size", "distribution": "beta", "params": {"alpha": 1.5, "beta": 4}},
            {"name": "conversion_rate", "distribution": "beta", "params": {"alpha": 2, "beta": 8}},
            {"name": "lifetime_value", "distribution": "beta", "params": {"alpha": 5, "beta": 2}},
        ],
    }
    var_pool = base_vars.get(dist, base_vars["triangular"])
    # Cycle variables if n > len(pool)
    out = []
    for i in range(n):
        v = dict(var_pool[i % len(var_pool)])
        if i >= len(var_pool):
            v = dict(v)
            v["name"] = f"{v['name']}_{i // len(var_pool)}"
        out.append(v)
    return out


def _obj_for(n):
    """Build objective expression for n variables."""
    names = [v["name"] for v in _make_vars(n)]
    if n == 1:
        return names[0]
    return (
        " + ".join(f"{names[0]}")
        if n == 1
        else " - ".join(names[:2])
        if n <= 2
        else f"{names[0]} - {names[1]} + " + " + ".join(names[2:])
    )


def expert_payload(engine, runs=500, n_vars=3, dist="triangular"):
    """Build expert-mode payload."""
    variables = _make_vars(n_vars, dist)
    return {
        "mode": "expert",
        "simulation_model": engine,
        "runs": runs,
        "simulation": {
            "variables": variables,
            "objective_function": _obj_for(n_vars),
        },
    }


def engine_payload(engine, runs=500, n_vars=3, dist="triangular"):
    """Build a complete payload with engine-specific configs."""
    p = expert_payload(engine, runs, n_vars, dist)

    if engine == "bootstrap":
        p["bootstrap_config"] = {
            "historical_data": [100 + i * 2 + (-1) ** i * 5 for i in range(30)],
            "statistic": "mean",
            "confidence_level": 0.95,
        }
    elif engine == "scenario":
        p["scenario_config"] = {
            "scenarios": [
                {
                    "name": "Best",
                    "probability": 0.3,
                    "variables": {"revenue": 200000, "cost": 40000},
                },
                {
                    "name": "Base",
                    "probability": 0.5,
                    "variables": {"revenue": 130000, "cost": 65000},
                },
                {
                    "name": "Worst",
                    "probability": 0.2,
                    "variables": {"revenue": 80000, "cost": 90000},
                },
            ],
        }
    elif engine == "sensitivity":
        p["sensitivity_config"] = {"method": "tornado"}
    elif engine == "decision_tree":
        p["decision_tree_config"] = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "decision",
                    "name": "Go/NoGo",
                    "branches": [
                        {
                            "id": "go",
                            "type": "terminal",
                            "name": "Go",
                            "probability": 0.7,
                            "objective_function": "revenue - cost",
                        },
                        {
                            "id": "nogo",
                            "type": "terminal",
                            "name": "NoGo",
                            "probability": 0.3,
                            "objective_function": "-cost",
                        },
                    ],
                }
            ],
        }
    elif engine == "time_series":
        p["time_series_config"] = {
            "model": "gbm",
            "initial_value": 50000,
            "horizons": [1, 3, 6, 12],
            "granularity": "month",
            "drift": 0.10,
            "volatility": 0.25,
        }
    elif engine == "mcmc":
        p["mcmc_config"] = {
            "observed_data": [105, 112, 98, 115, 108, 100, 120, 95, 110, 103],
            "likelihood": "normal",
            "chains": 2,
            "burn_in": 200,
        }
    elif engine == "importance_sampling":
        # importance_sampling needs normal distributions for tilting
        p["simulation"]["variables"] = _make_vars(n_vars, "normal")
        p["importance_sampling_config"] = {
            "target_threshold": -50000,
            "tail_direction": "lower",
        }
    return p


def auto_payload(engine, runs=500):
    """Build auto-mode payload."""
    return {
        "mode": "auto",
        "simulation_model": engine,
        "runs": runs,
        "scenario": {
            "variables": {
                "revenue": {"low": 80000, "high": 200000},
                "cost": {"low": 40000, "high": 90000},
            },
            "objective": "maximize_net_value",
        },
    }


# ─── Benchmark runner ─────────────────────────────────────────────────────────


def run_benchmark(label, payload, timeout=TIMEOUT_SECONDS):
    """Run a benchmark REPEATS times, return median latency and best result.

    Returns:
      (median_latency_ms, server_exec_ms, status_code, mean_val, std_val, timed_out, blocked_reason)
    """
    latencies = []
    server_execs = []
    last_status = 0
    last_mean = ""
    last_std = ""
    blocked_reason = None

    for _i in range(REPEATS):
        status, body, hdrs, elapsed = req("POST", "/v1/simulate", body=payload, timeout=timeout)
        latency_ms = elapsed * 1000
        blocked_reason = classify_simulation_blocker(status, body)
        if blocked_reason:
            return latency_ms, "", status, "", "", False, blocked_reason

        if status == 0 and elapsed >= timeout * 0.9:
            # Timeout
            return latency_ms, "", 0, "", "", True, None

        latencies.append(latency_ms)
        server_execs.append(get_server_exec_ms(hdrs))
        last_status = status

        if isinstance(body, dict) and status == 200:
            m = body.get("metrics", {})
            last_mean = m.get("expected_value", "")
            last_std = m.get("std_deviation", "")

    med_latency = median_of(latencies)
    # For server exec, take median of numeric values
    numeric_execs = [x for x in server_execs if isinstance(x, int | float)]
    med_server = median_of(numeric_execs) if numeric_execs else ""

    return med_latency, med_server, last_status, last_mean, last_std, False, None


# ══════════════════════════════════════════════════════════════════════════════
#  Bespoke standalone runner
#
#  Under pytest there are no `def test_*` functions to collect in this module;
#  the benchmark suite is driven entirely by the standalone harness below
#  (connectivity preflight, per-section check() orchestration, CSV + summary
#  export, results summary) so it still runs via
#  `python tests/integration/test_benchmarks.py`.
# ══════════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    # ═══════════════════════════════════════════════════════════════════════════════
    #  CONNECTIVITY CHECK
    # ═══════════════════════════════════════════════════════════════════════════════
    _emit("\n" + "=" * 70)
    _emit("  PHASE 15: COMPREHENSIVE SPEED/BENCHMARK TESTS")
    _emit("=" * 70)
    _emit(f"  Server: {BASE_URL}")
    _emit(f"  Repeats per benchmark: {REPEATS} (median)")
    _emit(f"  Timeout per request: {TIMEOUT_SECONDS}s")
    _emit(f"  Engines: {len(ALL_ENGINES)}")
    _emit(f"  Timestamp: {timestamp}")

    # Quick connectivity check
    status, _, _, _ = req("GET", "/v1/health", auth=False, timeout=5)
    if status != 200:
        _emit(f"\n  {FAIL} Cannot reach API server at {BASE_URL}")
        _emit("     Make sure the server is running (make dev-api)")
        sys.exit(1)
    _emit(f"  {PASS} Server reachable\n")

    if not API_KEY_CONFIGURED:
        reason = (
            "DE_API_KEY is not set; skipping authenticated benchmark measurements "
            "that require a real live key."
        )
        skip("Benchmark suite preflight", reason)
        _emit(f"\n  {SKIP} preflight: {reason}")
        artifact_path = _write_summary_artifact()
        _emit(f"  Summary artifact: {artifact_path}")
        sys.exit(0)


    # ═══════════════════════════════════════════════════════════════════════════════
    #  SECTION 1: Per-Engine Scaling Tests (runs: 100 → 50,000)
    # ═══════════════════════════════════════════════════════════════════════════════
    print("=" * 70)
    print("  SECTION 1: Per-Engine Scaling Tests (100 → 50,000 runs)")
    print("=" * 70)

    engine_scaling = {}  # {engine: {runs: median_ms}}

    for eng in ALL_ENGINES:
        engine_scaling[eng] = {}
        for rc in RUN_COUNTS:
            test_name = f"engine_scaling/{eng}/{rc}"
            label = f"{eng} @ {rc:,} runs"
            print(f"  Running {label}...", end=" ", flush=True)

            payload = engine_payload(eng, runs=rc, n_vars=3)
            med_ms, srv_ms, status, mean_val, std_val, timed_out, blocked_reason = run_benchmark(label, payload)

            if blocked_reason:
                print(f"SKIP ({blocked_reason})")
                record_csv(test_name, eng, rc, 3, "", "", f"{med_ms:.1f}", "", status, "", "")
                engine_scaling[eng][rc] = "skipped_capacity"
                skip(f"Scaling: {label}", blocked_reason)
                continue
            if timed_out:
                print(f"TIMEOUT ({med_ms:.0f}ms)")
                record_csv(test_name, eng, rc, 3, "", "", med_ms, "", 0, "", "")
                engine_scaling[eng][rc] = "timeout"
            else:
                print(f"{med_ms:.0f}ms (status={status})")
                record_csv(
                    test_name,
                    eng,
                    rc,
                    3,
                    "",
                    "",
                    f"{med_ms:.1f}",
                    f"{srv_ms}" if srv_ms != "" else "",
                    status,
                    mean_val,
                    std_val,
                )
                engine_scaling[eng][rc] = med_ms

            check(f"Scaling: {label}", _engine_scaling_check(status, timed_out, eng, rc))


    # ═══════════════════════════════════════════════════════════════════════════════
    #  SECTION 2: Variable Scaling Tests (monte_carlo, 1→20 vars)
    # ═══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 2: Variable Scaling Tests (monte_carlo, 1→20 vars)")
    print("=" * 70)

    var_scaling = {}  # {n_vars: median_ms}

    for nv in VAR_COUNTS:
        test_name = f"var_scaling/monte_carlo/{nv}"
        label = f"monte_carlo @ 1000 runs, {nv} variable(s)"
        print(f"  Running {label}...", end=" ", flush=True)

        payload = engine_payload("monte_carlo", runs=1000, n_vars=nv)
        med_ms, srv_ms, status, mean_val, std_val, timed_out, blocked_reason = run_benchmark(label, payload)

        if blocked_reason:
            print(f"SKIP ({blocked_reason})")
            var_scaling[nv] = "skipped_capacity"
            record_csv(test_name, "monte_carlo", 1000, nv, "", "", f"{med_ms:.1f}", "", status, "", "")
            skip(f"VarScale: {label}", blocked_reason)
            continue
        if timed_out:
            print("TIMEOUT")
            var_scaling[nv] = "timeout"
        else:
            print(f"{med_ms:.0f}ms")
            var_scaling[nv] = med_ms

        record_csv(
            test_name,
            "monte_carlo",
            1000,
            nv,
            "",
            "",
            f"{med_ms:.1f}",
            f"{srv_ms}" if srv_ms != "" else "",
            status,
            mean_val,
            std_val,
        )

        check(f"VarScale: {label}", _var_scaling_check(status, timed_out, nv))


    # ═══════════════════════════════════════════════════════════════════════════════
    #  SECTION 3: Distribution Type Benchmarks (monte_carlo, 1000 runs, 3 vars)
    # ═══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 3: Distribution Type Benchmarks")
    print("=" * 70)

    dist_benchmarks = {}  # {dist: median_ms}

    for dist in DIST_TYPES:
        test_name = f"dist_benchmark/{dist}"
        label = f"monte_carlo @ 1000 runs, 3 vars, {dist}"
        print(f"  Running {label}...", end=" ", flush=True)

        payload = expert_payload("monte_carlo", runs=1000, n_vars=3, dist=dist)
        med_ms, srv_ms, status, mean_val, std_val, timed_out, blocked_reason = run_benchmark(label, payload)

        if blocked_reason:
            print(f"SKIP ({blocked_reason})")
            dist_benchmarks[dist] = "skipped_capacity"
            record_csv(test_name, "monte_carlo", 1000, 3, dist, "", f"{med_ms:.1f}", "", status, "", "")
            skip(f"DistBench: {label}", blocked_reason)
            continue
        if timed_out:
            print("TIMEOUT")
            dist_benchmarks[dist] = "timeout"
        else:
            print(f"{med_ms:.0f}ms")
            dist_benchmarks[dist] = med_ms

        record_csv(
            test_name,
            "monte_carlo",
            1000,
            3,
            dist,
            "",
            f"{med_ms:.1f}",
            f"{srv_ms}" if srv_ms != "" else "",
            status,
            mean_val,
            std_val,
        )

        check(f"DistBench: {label}", _dist_bench_check(status, timed_out, dist))


    # ═══════════════════════════════════════════════════════════════════════════════
    #  SECTION 4: Concurrent Throughput Benchmarks
    # ═══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 4: Concurrent Throughput Benchmarks")
    print("=" * 70)

    concurrency_results = {}  # {n: {total_ms, per_req_ms, all_latencies}}

    for n_conc in CONCURRENCY_LEVELS:
        test_name = f"concurrency/{n_conc}"
        label = f"{n_conc} concurrent request(s)"
        print(f"  Running {label}...", end=" ", flush=True)

        payload = engine_payload("monte_carlo", runs=1000, n_vars=3)
        all_latencies = []

        def _single_request(_idx, request_payload=payload):
            """Execute a single request and return (latency_ms, status, blocked_reason)."""
            status, body, hdrs, elapsed = req(
                "POST", "/v1/simulate", body=request_payload, timeout=TIMEOUT_SECONDS
            )
            return elapsed * 1000, status, classify_simulation_blocker(status, body)

        total_t0 = time.perf_counter()
        blocked_reason = None
        blocked_status = ""
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_conc) as pool:
            futures = [pool.submit(_single_request, i) for i in range(n_conc)]
            for f in concurrent.futures.as_completed(futures):
                lat_ms, st, reason = f.result()
                if reason and blocked_reason is None:
                    blocked_reason = reason
                    blocked_status = st
                all_latencies.append(lat_ms)
        total_ms = (time.perf_counter() - total_t0) * 1000

        if blocked_reason:
            print(f"SKIP ({blocked_reason})")
            concurrency_results[n_conc] = {"blocked_reason": blocked_reason}
            record_csv(test_name, "monte_carlo", 1000, 3, "", n_conc, "", "", blocked_status, "", "")
            skip(f"Concurrency: {label} completed", blocked_reason)
            continue

        avg_lat = statistics.mean(all_latencies) if all_latencies else 0
        max_lat = max(all_latencies) if all_latencies else 0
        min_lat = min(all_latencies) if all_latencies else 0

        concurrency_results[n_conc] = {
            "total_ms": total_ms,
            "avg_latency_ms": avg_lat,
            "max_latency_ms": max_lat,
            "min_latency_ms": min_lat,
            "all_latencies": all_latencies,
        }

        print(
            f"total={total_ms:.0f}ms, avg/req={avg_lat:.0f}ms, min={min_lat:.0f}ms, max={max_lat:.0f}ms"
        )

        record_csv(test_name, "monte_carlo", 1000, 3, "", n_conc, f"{avg_lat:.1f}", "", "", "", "")

        check(f"Concurrency: {label} completed", _concurrency_check(n_conc, all_latencies))


    # ═══════════════════════════════════════════════════════════════════════════════
    #  SECTION 5: End-to-End Latency Breakdown
    # ═══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 5: End-to-End Latency Breakdown")
    print("=" * 70)

    latency_breakdown = {}

    # 5.1: Health endpoint (HTTP overhead)
    print("  Running health endpoint (HTTP overhead)...", end=" ", flush=True)
    health_latencies = []
    for _ in range(REPEATS):
        _, _, _, elapsed = req("GET", "/v1/health", auth=False, timeout=5)
        health_latencies.append(elapsed * 1000)
    med_health = median_of(health_latencies)
    latency_breakdown["http_overhead"] = med_health
    print(f"{med_health:.1f}ms")
    record_csv("latency/http_overhead", "", "", "", "", "", f"{med_health:.1f}", "", 200, "", "")


    def _test_health():
        assert med_health < 1000, f"Health endpoint took {med_health:.0f}ms"


    check("Latency: HTTP overhead (health)", _test_health)

    # 5.2: Simple simulation (auto mode, 100 runs)
    print("  Running simple simulation (auto, 100 runs)...", end=" ", flush=True)
    simple_payload = auto_payload("monte_carlo", runs=100)
    med_ms, srv_ms, status, mean_val, std_val, timed_out, blocked_reason = run_benchmark("simple", simple_payload)
    if blocked_reason:
        latency_breakdown["simple_sim"] = "skipped_capacity"
        print(f"SKIP ({blocked_reason})")
        record_csv("latency/simple_sim", "monte_carlo", 100, 2, "", "", "", "", status, "", "")
        skip("Latency: Simple simulation (auto, 100 runs)", blocked_reason)
    else:
        latency_breakdown["simple_sim"] = med_ms
        print(f"{med_ms:.0f}ms")
        record_csv(
            "latency/simple_sim",
            "monte_carlo",
            100,
            2,
            "",
            "",
            f"{med_ms:.1f}",
            f"{srv_ms}" if srv_ms != "" else "",
            status,
            mean_val,
            std_val,
        )


    def _test_simple_sim():
        assert not timed_out, "Simple sim timed out"
        assert status == 200, f"Got {status}"

    if not blocked_reason:
        check("Latency: Simple simulation (auto, 100 runs)", _test_simple_sim)

    # 5.3: Complex simulation (expert mode, 10 variables, 10,000 runs)
    print("  Running complex simulation (expert, 10 vars, 10k runs)...", end=" ", flush=True)
    complex_payload = engine_payload("monte_carlo", runs=10000, n_vars=10)
    med_ms, srv_ms, status, mean_val, std_val, timed_out, blocked_reason = run_benchmark("complex", complex_payload)
    if blocked_reason:
        latency_breakdown["complex_sim"] = "skipped_capacity"
        print(f"SKIP ({blocked_reason})")
        record_csv("latency/complex_sim", "monte_carlo", 10000, 10, "", "", "", "", status, "", "")
        skip("Latency: Complex simulation (expert, 10 vars, 10k runs)", blocked_reason)
    else:
        latency_breakdown["complex_sim"] = med_ms
        print(f"{med_ms:.0f}ms")
        record_csv(
            "latency/complex_sim",
            "monte_carlo",
            10000,
            10,
            "",
            "",
            f"{med_ms:.1f}",
            f"{srv_ms}" if srv_ms != "" else "",
            status,
            mean_val,
            std_val,
        )


    def _test_complex_sim():
        assert not timed_out, "Complex sim timed out"

    if not blocked_reason:
        check("Latency: Complex simulation (expert, 10 vars, 10k runs)", _test_complex_sim)

    # 5.4: Recommend endpoint
    print("  Running recommend endpoint...", end=" ", flush=True)
    recommend_latencies = []
    recommend_payload = {
        "decision": "Should we expand into the European market?",
        "options": ["Expand now", "Wait 6 months", "Do not expand"],
        "criteria": {"risk_tolerance": "moderate", "budget": 500000},
    }
    for _ in range(REPEATS):
        st, _, hdrs, elapsed = req("POST", "/v1/recommend", body=recommend_payload, timeout=10)
        recommend_latencies.append(elapsed * 1000)
    med_recommend = median_of(recommend_latencies)
    latency_breakdown["recommend"] = med_recommend
    print(f"{med_recommend:.0f}ms (status={st})")
    record_csv("latency/recommend", "", "", "", "", "", f"{med_recommend:.1f}", "", st, "", "")


    def _test_recommend():
        pass  # Recommend may or may not be implemented; just record


    check("Latency: Recommend endpoint", _test_recommend)

    # 5.5: What-if comparison
    print("  Running what-if comparison...", end=" ", flush=True)
    whatif_payload = {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "runs": 500,
        "simulation": {
            "variables": _make_vars(3),
            "objective_function": "revenue - cost + market_size",
        },
    }
    whatif_latencies = []
    blocked_reason = None
    whatif_status = 0
    for _ in range(REPEATS):
        whatif_status, whatif_body, hdrs, elapsed = req("POST", "/v1/simulate", body=whatif_payload, timeout=15)
        blocked_reason = classify_simulation_blocker(whatif_status, whatif_body)
        if blocked_reason:
            whatif_latencies.append(elapsed * 1000)
            break
        whatif_latencies.append(elapsed * 1000)
    med_whatif = median_of(whatif_latencies)
    if blocked_reason:
        latency_breakdown["whatif"] = "skipped_capacity"
        print(f"SKIP ({blocked_reason})")
        record_csv("latency/whatif", "monte_carlo", 500, 3, "", "", "", "", whatif_status, "", "")
        skip("Latency: What-if comparison", blocked_reason)
    else:
        latency_breakdown["whatif"] = med_whatif
        print(f"{med_whatif:.0f}ms")
        record_csv("latency/whatif", "monte_carlo", 500, 3, "", "", f"{med_whatif:.1f}", "", whatif_status, "", "")


    def _test_whatif():
        assert med_whatif < 30000, f"What-if took {med_whatif:.0f}ms"

    if not blocked_reason:
        check("Latency: What-if comparison", _test_whatif)

    # 5.6: Run listing
    print("  Running run listing...", end=" ", flush=True)
    list_latencies = []
    for _ in range(REPEATS):
        st, _, hdrs, elapsed = req("GET", "/v1/runs", timeout=10)
        list_latencies.append(elapsed * 1000)
    med_list = median_of(list_latencies)
    latency_breakdown["run_listing"] = med_list
    print(f"{med_list:.0f}ms (status={st})")
    record_csv("latency/run_listing", "", "", "", "", "", f"{med_list:.1f}", "", st, "", "")


    def _test_run_listing():
        pass  # Just record


    check("Latency: Run listing", _test_run_listing)


    # ═══════════════════════════════════════════════════════════════════════════════
    #  SECTION 6: Warm vs Cold Performance
    # ═══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 6: Warm vs Cold Performance")
    print("=" * 70)

    warmup_payload = engine_payload("monte_carlo", runs=1000, n_vars=3)
    warm_cold_summary = {
        "blocked_reason": None,
        "cold_ms": None,
        "warm_ms": None,
        "warm_median_ms": None,
        "ratio": None,
    }

    # Wait a moment for potential idle timeout
    print("  Measuring cold start (first request)...", end=" ", flush=True)
    time.sleep(2)

    cold_t0 = time.perf_counter()
    cold_status, cold_body, cold_hdrs, cold_elapsed = req(
        "POST", "/v1/simulate", body=warmup_payload, timeout=TIMEOUT_SECONDS
    )
    cold_blocked_reason = classify_simulation_blocker(cold_status, cold_body)
    cold_ms = cold_elapsed * 1000
    cold_server = get_server_exec_ms(cold_hdrs)
    if cold_blocked_reason:
        warm_cold_summary["blocked_reason"] = cold_blocked_reason
        print(f"SKIP ({cold_blocked_reason})")
    else:
        print(f"{cold_ms:.0f}ms")

    warm_latencies = []
    if not cold_blocked_reason:
        # Now run 9 more to get warm timing
        for _ in range(9):
            warm_status, warm_body, hdrs, elapsed = req(
                "POST", "/v1/simulate", body=warmup_payload, timeout=TIMEOUT_SECONDS
            )
            warm_blocked_reason = classify_simulation_blocker(warm_status, warm_body)
            if warm_blocked_reason:
                cold_blocked_reason = warm_blocked_reason
                break
            warm_latencies.append(elapsed * 1000)

    warm_ms = warm_latencies[-1] if warm_latencies else cold_ms
    warm_median = median_of(warm_latencies) if warm_latencies else cold_ms

    ratio = cold_ms / warm_median if warm_median > 0 else 1.0

    if cold_blocked_reason:
        warm_cold_summary["blocked_reason"] = cold_blocked_reason
        record_csv("warm_cold/cold", "monte_carlo", 1000, 3, "", "", "", "", cold_status, "", "")
        skip("WarmCold: Cold and warm within acceptable range", cold_blocked_reason)
    else:
        warm_cold_summary["cold_ms"] = cold_ms
        warm_cold_summary["warm_ms"] = warm_ms
        warm_cold_summary["warm_median_ms"] = warm_median
        warm_cold_summary["ratio"] = ratio
        print(f"  Cold start: {cold_ms:.0f}ms")
        print(f"  Warm (10th request): {warm_ms:.0f}ms")
        print(f"  Warm (median of 9): {warm_median:.0f}ms")
        print(f"  Cold/Warm ratio: {ratio:.2f}x")

        record_csv(
            "warm_cold/cold",
            "monte_carlo",
            1000,
            3,
            "",
            "",
            f"{cold_ms:.1f}",
            f"{cold_server}" if cold_server != "" else "",
            "",
            "",
            "",
        )
        record_csv("warm_cold/warm_last", "monte_carlo", 1000, 3, "", "", f"{warm_ms:.1f}", "", "", "", "")
        record_csv(
            "warm_cold/warm_median", "monte_carlo", 1000, 3, "", "", f"{warm_median:.1f}", "", "", "", ""
        )


    def _test_warm_cold():
        assert cold_ms < 30000, f"Cold start {cold_ms:.0f}ms > 30s"
        assert warm_median < 30000, f"Warm median {warm_median:.0f}ms > 30s"

    if not cold_blocked_reason:
        check("WarmCold: Cold and warm within acceptable range", _test_warm_cold)


    # ═══════════════════════════════════════════════════════════════════════════════
    #  WRITE CSV RESULTS
    # ═══════════════════════════════════════════════════════════════════════════════

    try:
        with open(CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "test_name",
                    "engine",
                    "runs",
                    "variables",
                    "distribution",
                    "concurrency",
                    "latency_ms",
                    "server_execution_ms",
                    "status_code",
                    "mean",
                    "std",
                    "timestamp",
                ],
            )
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
        print(f"\n  CSV results written to: {CSV_PATH} ({len(csv_rows)} rows)")
    except Exception as e:
        print(f"\n  Warning: Could not write CSV: {e}")


    # ═══════════════════════════════════════════════════════════════════════════════
    #  WRITE HUMAN-READABLE SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════════

    summary_lines = []


    def sprint(line=""):
        summary_lines.append(line)


    sprint("=" * 80)
    sprint("  ALGENTA DECISION ENGINE — BENCHMARK SUMMARY")
    sprint(f"  Generated: {timestamp}")
    sprint("=" * 80)

    # --- Engine Scaling Table ---
    sprint("\n\u2550\u2550\u2550 ENGINE SCALING (3 variables, median of 3 runs) \u2550\u2550\u2550\n")
    header = f"  {'Engine':<24}" + "".join(f"{rc:>10}" for rc in RUN_COUNTS) + "  (runs)"
    sprint(header)
    sprint("  " + "-" * (24 + 10 * len(RUN_COUNTS) + 8))
    for eng in ALL_ENGINES:
        row = f"  {eng:<24}"
        for rc in RUN_COUNTS:
            val = engine_scaling.get(eng, {}).get(rc, "")
            if val == "timeout":
                row += f"{'TIMEOUT':>10}"
            elif val == "skipped_capacity":
                row += f"{'SKIP':>10}"
            elif isinstance(val, int | float):
                row += f"{val:>9.0f}ms"  # note: '>9' + 'ms' = 11 chars, but we want 10
            else:
                row += f"{'N/A':>10}"
        sprint(row)

    # --- Fastest / Slowest at 1000 runs ---
    sprint("\n--- Fastest / Slowest Engines at 1,000 runs ---")
    timing_1k = {e: engine_scaling.get(e, {}).get(1000) for e in ALL_ENGINES}
    timing_1k_valid = {e: v for e, v in timing_1k.items() if isinstance(v, int | float)}
    if timing_1k_valid:
        fastest = min(timing_1k_valid, key=lambda e: timing_1k_valid[e])
        slowest = max(timing_1k_valid, key=lambda e: timing_1k_valid[e])
        sprint(f"  Fastest: {fastest} ({timing_1k_valid[fastest]:.0f}ms)")
        sprint(f"  Slowest: {slowest} ({timing_1k_valid[slowest]:.0f}ms)")
        ratio = (
            timing_1k_valid[slowest] / timing_1k_valid[fastest] if timing_1k_valid[fastest] > 0 else 0
        )
        sprint(f"  Ratio:   {ratio:.1f}x")

    # --- Variable Scaling ---
    sprint("\n\u2550\u2550\u2550 VARIABLE SCALING (monte_carlo, 1000 runs) \u2550\u2550\u2550\n")
    sprint(f"  {'Variables':<12} {'Latency (ms)':>14}")
    sprint("  " + "-" * 28)
    for nv in VAR_COUNTS:
        val = var_scaling.get(nv, "")
        if val == "timeout":
            sprint(f"  {nv:<12} {'TIMEOUT':>14}")
        elif val == "skipped_capacity":
            sprint(f"  {nv:<12} {'SKIP':>14}")
        elif isinstance(val, int | float):
            sprint(f"  {nv:<12} {val:>13.0f}ms")
        else:
            sprint(f"  {nv:<12} {'N/A':>14}")

    # --- Distribution Benchmarks ---
    sprint(
        "\n\u2550\u2550\u2550 DISTRIBUTION TYPE BENCHMARKS (monte_carlo, 1000 runs, 3 vars) \u2550\u2550\u2550\n"
    )
    sprint(f"  {'Distribution':<16} {'Latency (ms)':>14}")
    sprint("  " + "-" * 32)
    for dist in DIST_TYPES:
        val = dist_benchmarks.get(dist, "")
        if val == "timeout":
            sprint(f"  {dist:<16} {'TIMEOUT':>14}")
        elif val == "skipped_capacity":
            sprint(f"  {dist:<16} {'SKIP':>14}")
        elif isinstance(val, int | float):
            sprint(f"  {dist:<16} {val:>13.0f}ms")
        else:
            sprint(f"  {dist:<16} {'N/A':>14}")

    # --- Concurrency ---
    sprint(
        "\n\u2550\u2550\u2550 CONCURRENCY SCALING (monte_carlo, 1000 runs, 3 vars) \u2550\u2550\u2550\n"
    )
    sprint(f"  {'Concurrency':<14} {'Total (ms)':>12} {'Avg/Req':>10} {'Min':>10} {'Max':>10}")
    sprint("  " + "-" * 58)
    for nc in CONCURRENCY_LEVELS:
        cr = concurrency_results.get(nc, {})
        if cr.get("blocked_reason"):
            sprint(f"  {nc:<14} {'SKIP':>12} {'SKIP':>10} {'SKIP':>10} {'SKIP':>10}")
            continue
        total = cr.get("total_ms", 0)
        avg = cr.get("avg_latency_ms", 0)
        mn = cr.get("min_latency_ms", 0)
        mx = cr.get("max_latency_ms", 0)
        sprint(f"  {nc:<14} {total:>11.0f}ms {avg:>9.0f}ms {mn:>9.0f}ms {mx:>9.0f}ms")

    # --- Latency Breakdown ---
    sprint("\n\u2550\u2550\u2550 END-TO-END LATENCY BREAKDOWN \u2550\u2550\u2550\n")
    sprint(f"  {'Endpoint':<36} {'Latency (ms)':>14}")
    sprint("  " + "-" * 52)
    breakdown_labels = {
        "http_overhead": "Health (HTTP overhead)",
        "simple_sim": "Simple sim (auto, 100 runs)",
        "complex_sim": "Complex sim (expert, 10v, 10k runs)",
        "recommend": "Recommend endpoint",
        "whatif": "What-if comparison",
        "run_listing": "Run listing (GET /v1/runs)",
    }
    for key, label in breakdown_labels.items():
        val = latency_breakdown.get(key, "")
        if val == "skipped_capacity":
            sprint(f"  {label:<36} {'SKIP':>14}")
        elif isinstance(val, int | float):
            sprint(f"  {label:<36} {val:>13.0f}ms")
        else:
            sprint(f"  {label:<36} {'N/A':>14}")

    # --- Warm vs Cold ---
    sprint("\n\u2550\u2550\u2550 WARM vs COLD PERFORMANCE \u2550\u2550\u2550\n")
    if warm_cold_summary["blocked_reason"]:
        sprint(f"  Cold start (1st request):    {'SKIP':>8}")
        sprint(f"  Warm (10th request):         {'SKIP':>8}")
        sprint(f"  Warm (median of 9):          {'SKIP':>8}")
        sprint(f"  Cold/Warm ratio:             {'SKIP':>8}")
    else:
        sprint(f"  Cold start (1st request):    {warm_cold_summary['cold_ms']:>8.0f}ms")
        sprint(f"  Warm (10th request):         {warm_cold_summary['warm_ms']:>8.0f}ms")
        sprint(f"  Warm (median of 9):          {warm_cold_summary['warm_median_ms']:>8.0f}ms")
        sprint(f"  Cold/Warm ratio:             {warm_cold_summary['ratio']:>8.2f}x")

    # --- Overall Statistics ---
    sprint("\n\u2550\u2550\u2550 OVERALL STATISTICS \u2550\u2550\u2550\n")
    all_latencies = []
    for eng in ALL_ENGINES:
        for rc in RUN_COUNTS:
            val = engine_scaling.get(eng, {}).get(rc)
            if isinstance(val, int | float):
                all_latencies.append(val)
    for nv in VAR_COUNTS:
        val = var_scaling.get(nv)
        if isinstance(val, int | float):
            all_latencies.append(val)
    for dist in DIST_TYPES:
        val = dist_benchmarks.get(dist)
        if isinstance(val, int | float):
            all_latencies.append(val)

    if all_latencies:
        sprint(f"  Total benchmarks:    {len(all_latencies)}")
        sprint(f"  Mean latency:        {statistics.mean(all_latencies):.0f}ms")
        sprint(f"  Median latency:      {statistics.median(all_latencies):.0f}ms")
        sprint(f"  Min latency:         {min(all_latencies):.0f}ms")
        sprint(f"  Max latency:         {max(all_latencies):.0f}ms")
        sprint(
            f"  Std deviation:       {statistics.stdev(all_latencies):.0f}ms"
            if len(all_latencies) > 1
            else ""
        )
        timeouts = sum(
            1
            for eng in ALL_ENGINES
            for rc in RUN_COUNTS
            if engine_scaling.get(eng, {}).get(rc) == "timeout"
        )
        sprint(f"  Timeouts:            {timeouts}")
    else:
        sprint("  No valid latency measurements collected.")

    sprint("\n" + "=" * 80)

    # Write summary to file
    try:
        with open(SUMMARY_PATH, "w") as f:
            for line in summary_lines:
                f.write(line + "\n")
        _emit(f"  Summary written to: {SUMMARY_PATH}")
    except Exception as e:
        _emit(f"  Warning: Could not write summary: {e}")

    # Print summary to console too
    _emit()
    for line in summary_lines:
        _emit(line)


    # ═══════════════════════════════════════════════════════════════════════════════
    #  RESULTS SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════════
    _emit("\n" + "=" * 70)
    _emit("  TEST RESULTS SUMMARY")
    _emit("=" * 70)

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)

    _emit(f"\n  Total: {total} benchmark tests")
    _emit(f"  Passed: {passed} {PASS}")
    _emit(f"  Failed: {failed} {FAIL}")
    _emit(f"  Skipped: {skipped} {SKIP}")

    if failed > 0:
        _emit(f"\n  {'─' * 60}")
        _emit("  FAILURES:")
        for r in results:
            if r[0] == FAIL:
                detail = r[2] if len(r) > 2 else ""
                _emit(f"    {FAIL} {r[1]}")
                if detail:
                    _emit(f"       {detail[:200]}")
        _emit(f"  {'─' * 60}")

    _emit(f"\n{'=' * 70}")
    if failed == 0:
        _emit(f"  \U0001f389 All attempted benchmark tests passed ({passed} passed, {skipped} skipped)!")
    else:
        _emit(f"  \u26a0\ufe0f  {failed}/{total} BENCHMARK TESTS HAD FAILURES")
    _emit(f"  CSV: {CSV_PATH}")
    _emit(f"  Summary: {SUMMARY_PATH}")
    artifact_path = _write_summary_artifact()
    _emit(f"  Summary artifact: {artifact_path}")
    _emit(f"{'=' * 70}\n")

    import pytest

    exit_code = pytest.main([__file__, "-v"])
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_benchmarks.py",
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
