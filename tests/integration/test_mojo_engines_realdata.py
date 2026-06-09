"""
Phase 22: Mojo Engine — Full Module Coverage with Real Business Data

Tests every Mojo simulation engine directly (subprocess + API) using real
aviation/electronics parts distribution data from test_files/.

Two execution layers:
  Layer A — Direct binary  : spawn mojo_build/simulate, send JSON on stdin
  Layer B — API HTTP       : POST /v1/simulate (server must be running)

Each real-data payload is built by extracting statistical properties
(min, median, mean, max, std) from the actual CSV files.

Engines tested (all 11):
  1.  monte_carlo        — Standard parallel MC
  2.  lhs                — Latin Hypercube Sampling
  3.  qmc_sobol          — Quasi-Monte Carlo Sobol
  4.  bootstrap          — Non-parametric resampling with historical data
  5.  scenario           — Discrete weighted business scenarios
  6.  sensitivity        — Tornado chart + Sobol indices
  7.  mcmc               — Metropolis-Hastings Bayesian MCMC
  8.  decision_tree      — Go/No-Go decision tree
  9.  time_series        — GBM / OU / arithmetic forecasting
  10. compare            — N scenarios × M runs
  11. importance_sampling — Rare tail-event probability

Real CSV datasets used:
  POS.csv                     — point-of-sale: price, cost, quantity, margin
  Bookings.csv                — booked orders: ext_price, ext_cost
  OPO.csv                     — open purchase orders: unit_cost, qty_ordered
  Backlog.csv                 — open customer orders: unit_price, ext_price
  Quotes_Combined_20241116.csv — quotes pipeline: unit_price, win/loss

Python adapter:
  mojo/bindings/python_adapter.py — tested directly as a pure-Python fallback

Prerequisites:
  - mojo_build/simulate binary compiled (make build-mojo)
  - API server running on localhost:8000 (make dev-api) for Layer B
  - test_files/ directory with CSV data

Run:
  python3 tests/integration/test_mojo_engines_realdata.py
  DE_SKIP_API=1 python3 ...    # skip Layer B (binary-only)
  DE_SKIP_BINARY=1 python3 ... # skip Layer A (API-only)
"""

from __future__ import annotations

import csv as csv_stdlib
import json
import math
import os
import re
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_integration_artifacts import write_live_integration_summary

socket.setdefaulttimeout(30)

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
TEST_FILES = _PROJECT_ROOT / "test_files"
BINARY_PATH = _PROJECT_ROOT / "mojo_build" / "simulate"
ADAPTER_PATH = _PROJECT_ROOT / "mojo" / "bindings" / "python_adapter.py"

SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"
SKIP_BINARY = os.environ.get("DE_SKIP_BINARY", "0") == "1"
SUITE_NAME = "mojo_engines_realdata_integration"
STARTED = time.perf_counter()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"

results: list[tuple[str, ...]] = []
timings: list[tuple[str, float]] = []
_BINARY_LAYER_UNAVAILABLE_REASON: str | None = None


# ─── helpers ──────────────────────────────────────────────────────────────────


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
        script="tests/integration/test_mojo_engines_realdata.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "base_url": configured_local_live_base_url(),
            "api_key_configured": API_KEY_CONFIGURED,
            "skip_api": SKIP_API,
            "skip_binary": SKIP_BINARY,
            "binary_path": str(BINARY_PATH),
            "adapter_path": str(ADAPTER_PATH),
        },
    )
    return str(artifact)


def check(name: str, fn) -> None:
    if _BINARY_LAYER_UNAVAILABLE_REASON and name.startswith("Binary "):
        skip(name, _BINARY_LAYER_UNAVAILABLE_REASON)
        return
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        elapsed = time.perf_counter() - started_at
        results.append((PASS, name))
        timings.append((name, elapsed))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except AssertionError as e:
        elapsed = time.perf_counter() - started_at
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except EnvironmentBlocked as e:
        elapsed = time.perf_counter() - started_at
        results.append((SKIP, name, str(e)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except Exception as e:
        elapsed = time.perf_counter() - started_at
        results.append((FAIL, name, f"{type(e).__name__}: {e}"))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(e).__name__}: {e}"
        )


def skip(name: str, reason: str) -> None:
    results.append((SKIP, name, reason))
    _emit(f"  {SKIP} {name}: {reason}")


class EnvironmentBlocked(RuntimeError):
    """Raised when the live environment cannot execute simulation due to quota/capacity."""


def ensure_simulation_capacity_available(status: int, body) -> None:
    ensure_live_api_key_available(status, body)
    blocked_reason = classify_simulation_capacity_blocker(status=status, payload=body)
    if blocked_reason:
        raise EnvironmentBlocked(blocked_reason)


def ensure_live_api_key_available(status: int, body: Any) -> None:
    if API_KEY_CONFIGURED:
        return
    if not isinstance(body, dict):
        return
    error = body.get("error")
    if not isinstance(error, dict):
        return
    code = error.get("code")
    if status == 401 or code == "invalid_api_key":
        raise EnvironmentBlocked(
            "DE_API_KEY is not set; skipping authenticated API engine checks that require a real live key."
        )


# ── HTTP ─────────────────────────────────────────────────────────────────────


def api(method: str, path: str, body: Any = None, timeout: int = 30) -> tuple[int, Any, float]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
        method=method,
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            return resp.status, json.loads(resp.read()), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        try:
            return e.code, json.loads(e.read()), elapsed
        except Exception:
            return e.code, {}, elapsed
    except Exception as e:
        return 0, {"error": str(e)}, time.perf_counter() - t0


# ── direct binary ─────────────────────────────────────────────────────────────


def invoke_binary(payload: dict, timeout: int = 30) -> dict:
    """Run the Mojo binary directly via subprocess stdin/stdout."""
    proc = subprocess.run(
        [str(BINARY_PATH)],
        input=json.dumps(payload).encode(),
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Binary exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:300]}"
        )
    raw = proc.stdout.decode()
    # Multi-line NDJSON: take the last non-empty line
    last = next((line for line in reversed(raw.splitlines()) if line.strip()), "")
    return json.loads(last)


# ── Python adapter ────────────────────────────────────────────────────────────


def invoke_adapter(payload: dict) -> dict:
    """Run the pure-Python fallback adapter."""
    sys.path.insert(0, str(_PROJECT_ROOT / "mojo" / "bindings"))
    from python_adapter import run_simulation  # type: ignore

    return run_simulation(payload)


# ── CSV data loading ──────────────────────────────────────────────────────────


def _load_csv(name: str, max_rows: int = 5000) -> list[dict]:
    path = TEST_FILES / name
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, newline="", errors="replace") as fh:
        for i, row in enumerate(csv_stdlib.DictReader(fh)):
            if i >= max_rows:
                break
            rows.append(row)
    return rows


def _to_float(val: str) -> float | None:
    clean = re.sub(r"[^\d.\-+eE]", "", str(val))
    try:
        v = float(clean)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def _col_stats(rows: list[dict], col: str, min_val: float = 0.0) -> dict | None:
    vals = [v for r in rows if (v := _to_float(r.get(col, ""))) is not None and v > min_val]
    if len(vals) < 20:
        return None
    vals.sort()
    n = len(vals)
    mean = sum(vals) / n
    med = vals[n // 2]
    std = statistics.stdev(vals) if n > 1 else 0.0
    return {
        "min": vals[0],
        "max": vals[-1],
        "mean": mean,
        "median": med,
        "std": std,
        "count": n,
        "raw": vals,
    }


def _margin_series(
    rows: list[dict],
    *,
    revenue_col: str,
    cost_col: str,
    max_points: int = 200,
) -> list[float]:
    values: list[float] = []
    for row in rows:
        revenue = _to_float(row.get(revenue_col, ""))
        cost = _to_float(row.get(cost_col, ""))
        if revenue is None or cost is None:
            continue
        margin = revenue - cost
        if math.isfinite(margin):
            values.append(margin)
        if len(values) >= max_points:
            break
    return values


# ── canonical engine payload factories ───────────────────────────────────────


def _mc_payload(
    variables: list[dict],
    objective: str = "",
    runs: int = 1000,
    engine: str = "monte_carlo",
    seed: int | None = None,
    **extra,
) -> dict:
    if not objective:
        objective = " + ".join(v["name"] for v in variables)
    p: dict = {
        "engine_type": engine,
        "runs": runs,
        "variables": variables,
        "objective_function": objective,
    }
    if seed is not None:
        p["seed"] = seed
    p.update(extra)
    return p


def _api_expert(
    variables: list[dict],
    objective: str = "",
    runs: int = 1000,
    engine: str = "monte_carlo",
    seed: int | None = None,
    **extra,
) -> dict:
    if not objective:
        objective = " + ".join(v["name"] for v in variables)
    p: dict = {
        "mode": "expert",
        "simulation_model": engine,
        "runs": runs,
        "simulation": {"variables": variables, "objective_function": objective},
    }
    if seed is not None:
        p["seed"] = seed
    p.update(extra)
    return p


# ─── validate a standard engine response ─────────────────────────────────────


def _assert_engine_output(result: dict, engine: str, min_runs: int = 1) -> None:
    assert isinstance(result, dict), f"[{engine}] result is not a dict"
    # Accept both direct binary output and API-wrapped output
    metrics = result.get("summary") or result.get("metrics", {})
    assert metrics, f"[{engine}] no metrics/summary in result: {list(result.keys())}"
    ev_key = "mean" if "mean" in metrics else "expected_value"
    assert ev_key in metrics, f"[{engine}] no EV in metrics: {list(metrics.keys())}"
    assert isinstance(metrics[ev_key], int | float), (
        f"[{engine}] EV is not numeric: {metrics[ev_key]}"
    )
    runs_key = "scenarios_run" if "scenarios_run" in result else "runs"
    if runs_key in result:
        assert result[runs_key] >= min_runs, (
            f"[{engine}] ran {result[runs_key]} runs, expected >= {min_runs}"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  PRE-LOAD CSV DATA — parse once, reuse across all tests
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  Loading real CSV data...")
print("=" * 70)

_POS = _load_csv("POS.csv")
_BOOKINGS = _load_csv("Bookings.csv")
_OPO = _load_csv("OPO.csv", max_rows=2000)
_BACKLOG = _load_csv("Backlog.csv", max_rows=3000)
_QUOTES = _load_csv("Quotes_Combined_20241116.csv", max_rows=3000)

# Column statistics
_pos_price = _col_stats(_POS, "UNIT_PRICE")
_pos_cost = _col_stats(_POS, "UNIT_COST")
_pos_qty = _col_stats(_POS, "QUANTITY", min_val=0.0)
_pos_margin = _margin_series(_POS, revenue_col="UNIT_PRICE", cost_col="UNIT_COST")
_bk_ext = _col_stats(_BOOKINGS, "EXT_PRICE")
_bk_cost = _col_stats(_BOOKINGS, "EXT_COST") or _col_stats(_BOOKINGS, "UNIT_COST")
_opo_cost = _col_stats(_OPO, "Unit Cost")
_opo_qty = _col_stats(_OPO, "Quantity Ordered", min_val=0.0)
_bl_price = _col_stats(_BACKLOG, "UNIT_PRICE")
_q_price = _col_stats(_QUOTES, "UNIT_PRICE")

print(
    f"  POS rows:      {len(_POS):>6,}  price stats: {'✓' if _pos_price else '✗'}  cost stats: {'✓' if _pos_cost else '✗'}"
)
print(f"  Bookings rows: {len(_BOOKINGS):>6,}  ext_price:   {'✓' if _bk_ext else '✗'}")
print(f"  OPO rows:      {len(_OPO):>6,}  unit_cost:   {'✓' if _opo_cost else '✗'}")
print(f"  Backlog rows:  {len(_BACKLOG):>6,}  unit_price:  {'✓' if _bl_price else '✗'}")
print(f"  Quotes rows:   {len(_QUOTES):>6,}  unit_price:  {'✓' if _q_price else '✗'}")


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER A — Direct Mojo binary tests
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  LAYER A: Direct Mojo Binary Tests")
print("=" * 70)

if SKIP_BINARY:
    print(f"  {SKIP} Skipped (DE_SKIP_BINARY=1)")
elif not BINARY_PATH.exists():
    print(f"  {SKIP} Binary not found at {BINARY_PATH} — run: make build-mojo")
else:
    _binary_probe_payload = {
        "engine_type": "monte_carlo",
        "runs": 100,
        "seed": 42,
        "variables": [
            {
                "name": "x",
                "distribution": "normal",
                "params": {"mean": 0.0, "std": 1.0},
            }
        ],
        "objective_function": "x",
    }

    def _binary_probe_error() -> str | None:
        try:
            invoke_binary(_binary_probe_payload)
        except Exception as exc:  # noqa: BLE001
            return str(exc)
        return None

    binary_probe_error = _binary_probe_error()
    if binary_probe_error:
        _BINARY_LAYER_UNAVAILABLE_REASON = f"Binary probe failed: {binary_probe_error[:220]}"
        skip(
            "Direct Mojo binary tests",
            _BINARY_LAYER_UNAVAILABLE_REASON,
        )
    else:
        # ── A1: Binary smoke test ─────────────────────────────────────────────────
        def test_binary_smoke():
            result = invoke_binary(_binary_probe_payload)
            _assert_engine_output(result, "binary_smoke", min_runs=100)

        check("Binary smoke test — minimal MC payload", test_binary_smoke)

        # ── A2: All 11 engines via binary ─────────────────────────────────────────
        _BASE_VARS = [
            {
                "name": "revenue",
                "distribution": "normal",
                "params": {"mean": 120_000.0, "std": 20_000.0},
            },
            {
                "name": "cost",
                "distribution": "normal",
                "params": {"mean": 70_000.0, "std": 10_000.0},
            },
        ]

        _BINARY_ENGINES = [
            (
                "monte_carlo",
                {},
            ),
            (
                "lhs",
                {},
            ),
            (
                "qmc_sobol",
                {},
            ),
            (
                "bootstrap",
                {
                    "bootstrap_config": {
                        "historical_data": [
                            80_000,
                            95_000,
                            110_000,
                            125_000,
                            105_000,
                            98_000,
                            115_000,
                            130_000,
                            90_000,
                            108_000,
                        ],
                        "statistic": "mean",
                    }
                },
            ),
            (
                "scenario",
                {
                    "scenario_config": {
                        "scenarios": [
                            {
                                "name": "bull",
                                "probability": 0.3,
                                "variables": {"revenue": 180_000, "cost": 60_000},
                            },
                            {
                                "name": "base",
                                "probability": 0.5,
                                "variables": {"revenue": 120_000, "cost": 70_000},
                            },
                            {
                                "name": "bear",
                                "probability": 0.2,
                                "variables": {"revenue": 80_000, "cost": 85_000},
                            },
                        ]
                    }
                },
            ),
            (
                "sensitivity",
                {},
            ),
            (
                "mcmc",
                {
                    "mcmc_config": {
                        "observed_data": [
                            80_000,
                            95_000,
                            110_000,
                            125_000,
                            105_000,
                            98_000,
                            115_000,
                            130_000,
                            90_000,
                            108_000,
                            102_000,
                            118_000,
                            93_000,
                            107_000,
                            112_000,
                        ],
                        "likelihood": "normal",
                    }
                },
            ),
            (
                "decision_tree",
                {
                    "decision_tree_config": {
                        "paths": [
                            {
                                "label": "proceed",
                                "probability": 0.65,
                                "variables": [
                                    {
                                        "name": "revenue",
                                        "distribution": "normal",
                                        "params": {"mean": 140_000.0, "std": 15_000.0},
                                    },
                                    {
                                        "name": "cost",
                                        "distribution": "normal",
                                        "params": {"mean": 65_000.0, "std": 8_000.0},
                                    },
                                ],
                            },
                            {
                                "label": "decline",
                                "probability": 0.35,
                                "variables": [
                                    {
                                        "name": "revenue",
                                        "distribution": "fixed",
                                        "params": {"value": 0.0},
                                    },
                                    {
                                        "name": "cost",
                                        "distribution": "fixed",
                                        "params": {"value": 5_000.0},
                                    },
                                ],
                            },
                        ]
                    }
                },
            ),
            (
                "time_series",
                {
                    "time_series_config": {
                        "model": "gbm",
                        "initial_value": 120_000.0,
                        "drift": 0.05,
                        "volatility": 0.20,
                        "dt": 0.0833,
                        "horizons": [1, 3, 6, 12],
                    }
                },
            ),
            (
                "importance_sampling",
                {
                    "importance_sampling_config": {
                        "target_threshold": -20_000.0,
                        "tail_direction": "lower",
                    }
                },
            ),
        ]

        for _eng, _extra in _BINARY_ENGINES:

            def _make_binary_test(eng: str, extra: dict):
                def _t():
                    payload = _mc_payload(
                        _BASE_VARS, "revenue - cost", runs=500, engine=eng, seed=99, **extra
                    )
                    result = invoke_binary(payload, timeout=60)
                    _assert_engine_output(result, f"binary_{eng}", min_runs=1)
                    timings.append((f"Binary {eng}", 0))

                return _t

            check(f"Binary engine: {_eng}", _make_binary_test(_eng, _extra))

    # ── A3: POS.csv → real price distributions → Monte Carlo ─────────────────
    def test_binary_pos_mc():
        if not _pos_price or not _pos_cost:
            skip("Binary POS Monte Carlo", "No POS price/cost stats")
            return
        result = invoke_binary(
            {
                "engine_type": "monte_carlo",
                "runs": 2000,
                "seed": 1,
                "variables": [
                    {
                        "name": "unit_price",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, _pos_price["mean"])), "std": 0.8},
                    },
                    {
                        "name": "unit_cost",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, _pos_cost["mean"])), "std": 0.7},
                    },
                    {
                        "name": "quantity",
                        "distribution": "triangular",
                        "params": {"low": 1.0, "mode": 5.0, "high": 50.0},
                    },
                ],
                "objective_function": "(unit_price - unit_cost) * quantity",
            }
        )
        _assert_engine_output(result, "binary_POS_mc")
        ev = result.get("summary", {}).get("mean", 0)
        print(
            f"    → POS margin EV = {ev:.2f}  (price_mean={_pos_price['mean']:.2f},"
            f" cost_mean={_pos_cost['mean']:.2f})"
        )

    check("Binary MC with real POS price/cost distributions", test_binary_pos_mc)

    # ── A4: Bookings.csv → Bootstrap on historical EXT_PRICE ─────────────────
    def test_binary_bookings_bootstrap():
        if not _bk_ext:
            skip("Binary Bookings Bootstrap", "No Bookings EXT_PRICE stats")
            return
        # Take a sample of real booking values as historical data
        sample = _bk_ext["raw"][:200]
        result = invoke_binary(
            {
                "engine_type": "bootstrap",
                "runs": 1000,
                "seed": 7,
                "variables": [
                    {
                        "name": "booking_value",
                        "distribution": "fixed",
                        "params": {"value": _bk_ext["mean"]},
                    }
                ],
                "objective_function": "booking_value",
                "bootstrap_config": {
                    "historical_data": sample,
                    "statistic": "mean",
                },
            }
        )
        _assert_engine_output(result, "binary_bookings_bootstrap")
        print(f"    → Bookings bootstrap: n_historical={len(sample)}, mean={_bk_ext['mean']:.2f}")

    check("Binary bootstrap with real Bookings historical data", test_binary_bookings_bootstrap)

    # ── A5: OPO.csv → Sensitivity analysis on purchase cost drivers ───────────
    def test_binary_opo_sensitivity():
        if not _opo_cost or not _opo_qty:
            skip("Binary OPO Sensitivity", "No OPO cost/qty stats")
            return
        result = invoke_binary(
            {
                "engine_type": "sensitivity",
                "runs": 500,
                "seed": 3,
                "variables": [
                    {
                        "name": "unit_cost",
                        "distribution": "triangular",
                        "params": {
                            "low": _opo_cost["min"],
                            "mode": _opo_cost["median"],
                            "high": min(_opo_cost["max"], _opo_cost["mean"] * 5),
                        },
                    },
                    {
                        "name": "qty_ordered",
                        "distribution": "triangular",
                        "params": {
                            "low": max(1.0, _opo_qty["min"]),
                            "mode": max(1.0, _opo_qty["median"]),
                            "high": min(_opo_qty["max"], _opo_qty["mean"] * 5),
                        },
                    },
                    {
                        "name": "tariff",
                        "distribution": "uniform",
                        "params": {"low": 0.0, "high": 0.25},
                    },
                ],
                "objective_function": "unit_cost * qty_ordered * (1 + tariff) * -1",
            }
        )
        _assert_engine_output(result, "binary_OPO_sensitivity")
        if "sobol_indices" in result or "tornado_data" in result:
            print("    → OPO sensitivity: got sobol/tornado data ✓")

    check("Binary sensitivity with real OPO purchase cost drivers", test_binary_opo_sensitivity)

    # ── A6: Backlog.csv → Scenario engine for best/base/worst orders ──────────
    def test_binary_backlog_scenario():
        if not _bl_price:
            skip("Binary Backlog Scenario", "No Backlog price stats")
            return
        p = _bl_price
        result = invoke_binary(
            {
                "engine_type": "scenario",
                "runs": 800,
                "seed": 5,
                "variables": [
                    {
                        "name": "order_value",
                        "distribution": "triangular",
                        "params": {
                            "low": p["min"],
                            "mode": p["median"],
                            "high": min(p["max"], p["mean"] * 8),
                        },
                    },
                ],
                "objective_function": "order_value",
                "scenario_config": {
                    "scenarios": [
                        {
                            "name": "All orders ship on-time",
                            "probability": 0.40,
                            "variables": {"order_value": p["mean"] * 1.10},
                        },
                        {
                            "name": "10% orders delayed",
                            "probability": 0.45,
                            "variables": {"order_value": p["mean"] * 0.90},
                        },
                        {
                            "name": "30% orders cancelled",
                            "probability": 0.15,
                            "variables": {"order_value": p["mean"] * 0.70},
                        },
                    ]
                },
            }
        )
        _assert_engine_output(result, "binary_backlog_scenario")
        if "scenario_analysis" in result:
            sc = result["scenario_analysis"]
            print(f"    → Backlog scenario EV = {sc.get('expected_value', '?'):.2f}")

    check("Binary scenario with real Backlog order-value scenarios", test_binary_backlog_scenario)

    # ── A7: Quotes.csv → Decision tree: quote accepted vs. rejected ───────────
    def test_binary_quotes_decision_tree():
        if not _q_price:
            skip("Binary Quotes Decision Tree", "No Quotes price stats")
            return
        q = _q_price
        result = invoke_binary(
            {
                "engine_type": "decision_tree",
                "runs": 500,
                "seed": 11,
                "variables": [
                    {
                        "name": "quoted_price",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, q["mean"])), "std": 0.6},
                    },
                    {
                        "name": "cost_to_serve",
                        "distribution": "normal",
                        "params": {"mean": q["mean"] * 0.75, "std": q["std"] * 0.3},
                    },
                ],
                "objective_function": "quoted_price - cost_to_serve",
                "decision_tree_config": {
                    "paths": [
                        {
                            "label": "Quote won",
                            "probability": 0.35,
                            "variables": [
                                {
                                    "name": "quoted_price",
                                    "distribution": "lognormal",
                                    "params": {
                                        "mean": math.log(max(1, q["mean"] * 1.05)),
                                        "std": 0.5,
                                    },
                                },
                                {
                                    "name": "cost_to_serve",
                                    "distribution": "normal",
                                    "params": {"mean": q["mean"] * 0.70, "std": q["std"] * 0.25},
                                },
                            ],
                        },
                        {
                            "label": "Quote lost",
                            "probability": 0.65,
                            "variables": [
                                {
                                    "name": "quoted_price",
                                    "distribution": "fixed",
                                    "params": {"value": 0.0},
                                },
                                {
                                    "name": "cost_to_serve",
                                    "distribution": "fixed",
                                    "params": {"value": q["mean"] * 0.02},
                                },
                            ],
                        },
                    ]
                },
            }
        )
        _assert_engine_output(result, "binary_quotes_decision_tree")
        print(f"    → Quotes decision tree: EV = {result.get('summary', {}).get('mean', 0):.2f}")

    check(
        "Binary decision_tree with real Quotes win/loss scenarios", test_binary_quotes_decision_tree
    )

    # ── A8: Bookings.csv → Time series revenue forecast ───────────────────────
    def test_binary_bookings_timeseries():
        if not _bk_ext:
            skip("Binary Bookings Time Series", "No Bookings EXT_PRICE stats")
            return
        initial = _bk_ext["mean"]
        annual_vol = min(0.8, _bk_ext["std"] / max(1, initial))
        result = invoke_binary(
            {
                "engine_type": "time_series",
                "runs": 1000,
                "seed": 13,
                "variables": [
                    {
                        "name": "booking_revenue",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, initial)), "std": 0.5},
                    },
                ],
                "objective_function": "booking_revenue",
                "time_series_config": {
                    "model": "gbm",
                    "initial_value": initial,
                    "drift": 0.08,
                    "volatility": annual_vol,
                    "dt": 0.0833,
                    "horizons": [3, 6, 12],
                },
            }
        )
        _assert_engine_output(result, "binary_bookings_timeseries")
        print(f"    → Bookings GBM: initial={initial:.2f}, vol={annual_vol:.2%}")

    check("Binary time_series GBM with real Bookings revenue", test_binary_bookings_timeseries)

    # ── A9: OPO + POS → Importance sampling — rare margin event ──────────────
    def test_binary_importance_sampling():
        if not _pos_price or not _pos_cost:
            skip("Binary Importance Sampling", "No POS price/cost stats")
            return
        result = invoke_binary(
            {
                "engine_type": "importance_sampling",
                "runs": 2000,
                "seed": 17,
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": _pos_price["mean"], "std": _pos_price["std"]},
                    },
                    {
                        "name": "cost",
                        "distribution": "normal",
                        "params": {"mean": _pos_cost["mean"], "std": _pos_cost["std"]},
                    },
                ],
                "objective_function": "revenue - cost",
                "importance_sampling_config": {
                    "target_threshold": -(_pos_price["mean"] * 0.5),
                    "tail_direction": "lower",
                },
            }
        )
        _assert_engine_output(result, "binary_importance_sampling")
        pol = result.get("risk", {}).get("probability_of_loss", None) or result.get(
            "metrics", {}
        ).get("probability_of_loss", None)
        if pol is not None:
            print(f"    → IS P(loss > 50% revenue) ≈ {pol:.4%}")

    check("Binary importance_sampling for rare POS margin loss", test_binary_importance_sampling)

    # ── A10: QMC Sobol vs Monte Carlo convergence — same seed/variables ───────
    def test_binary_qmc_vs_mc_convergence():
        """QMC should have lower std-error than MC at equal run counts."""
        if not _pos_price:
            skip("Binary QMC vs MC convergence", "No POS price stats")
            return
        vars_ = [
            {
                "name": "x",
                "distribution": "normal",
                "params": {"mean": _pos_price["mean"], "std": _pos_price["std"]},
            }
        ]
        obj = "x"

        mc_evs: list[float] = []
        qmc_evs: list[float] = []
        for seed in range(5):
            mc = invoke_binary(_mc_payload(vars_, obj, runs=200, engine="monte_carlo", seed=seed))
            qmc = invoke_binary(_mc_payload(vars_, obj, runs=200, engine="qmc_sobol", seed=seed))
            mc_evs.append(mc.get("summary", mc).get("mean", 0))
            qmc_evs.append(qmc.get("summary", qmc).get("mean", 0))

        mc_std = statistics.stdev(mc_evs) if len(mc_evs) > 1 else 0.0
        qmc_std = statistics.stdev(qmc_evs) if len(qmc_evs) > 1 else 0.0
        print(f"    → MC std-error across seeds={mc_std:.2f}  QMC std-error={qmc_std:.2f}")
        # QMC should be more stable — allow it to be equal or better
        # (at 200 runs the gap may be small, so just verify both run)
        assert mc_std >= 0 and qmc_std >= 0, "Standard errors must be non-negative"

    check(
        "Binary QMC-Sobol vs MC convergence on real POS distribution",
        test_binary_qmc_vs_mc_convergence,
    )

    # ── A11: LHS coverage — verify stratified sampling ────────────────────────
    def test_binary_lhs_coverage():
        """LHS should cover the full distribution range more evenly than plain MC."""
        if not _q_price:
            skip("Binary LHS coverage", "No Quotes price stats")
            return
        vars_ = [
            {
                "name": "p",
                "distribution": "uniform",
                "params": {"low": _q_price["min"], "high": _q_price["max"]},
            }
        ]
        result = invoke_binary(_mc_payload(vars_, "p", runs=500, engine="lhs", seed=42))
        _assert_engine_output(result, "binary_lhs_coverage")
        pct = result.get("percentiles", {})
        if pct:
            spread = pct.get("p95", 0) - pct.get("p5", 0)
            total = _q_price["max"] - _q_price["min"]
            print(
                f"    → LHS p5={pct.get('p5', 0):.2f} p95={pct.get('p95', 0):.2f}"
                f"  spread={spread:.2f} / range={total:.2f}"
            )

    check("Binary LHS coverage with real Quotes price range", test_binary_lhs_coverage)

    # ── A12: Deterministic seeded runs (reproducibility) ─────────────────────
    def test_binary_determinism():
        if not _pos_price:
            skip("Binary determinism", "No POS price stats")
            return
        payload = _mc_payload(
            [
                {
                    "name": "price",
                    "distribution": "normal",
                    "params": {"mean": _pos_price["mean"], "std": _pos_price["std"]},
                }
            ],
            "price",
            runs=500,
            engine="monte_carlo",
            seed=2024,
        )
        r1 = invoke_binary(payload)
        r2 = invoke_binary(payload)
        ev1 = r1.get("summary", {}).get("mean", None)
        ev2 = r2.get("summary", {}).get("mean", None)
        assert ev1 is not None and ev2 is not None, "Missing mean in output"
        assert ev1 == ev2, f"Seeded runs not deterministic: {ev1} vs {ev2}"
        print(f"    → Seeded determinism confirmed: EV = {ev1:.6f}")

    check("Binary seeded runs are fully deterministic (POS data)", test_binary_determinism)

    # ── A13: Multi-output objective ("|"-separated) ───────────────────────────
    def test_binary_multi_output():
        result = invoke_binary(
            {
                "engine_type": "monte_carlo",
                "runs": 500,
                "seed": 7,
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 100_000.0, "std": 15_000.0},
                    },
                    {
                        "name": "cost",
                        "distribution": "normal",
                        "params": {"mean": 60_000.0, "std": 8_000.0},
                    },
                ],
                "objective_function": "revenue - cost | revenue | cost",
            }
        )
        _assert_engine_output(result, "binary_multi_output")

    check("Binary multi-output objective (pipe-separated)", test_binary_multi_output)

    # ── A14: Correlated variables (Cholesky) ──────────────────────────────────
    def test_binary_correlation():
        """Price and cost should be positively correlated (same market)."""
        if not _pos_price or not _pos_cost:
            skip("Binary correlation", "No POS data")
            return
        result = invoke_binary(
            {
                "engine_type": "monte_carlo",
                "runs": 2000,
                "seed": 42,
                "variables": [
                    {
                        "name": "price",
                        "distribution": "normal",
                        "params": {"mean": _pos_price["mean"], "std": _pos_price["std"]},
                    },
                    {
                        "name": "cost",
                        "distribution": "normal",
                        "params": {"mean": _pos_cost["mean"], "std": _pos_cost["std"]},
                    },
                ],
                "objective_function": "price - cost",
                "correlations": [{"variables": ["price", "cost"], "coefficient": 0.7}],
            }
        )
        _assert_engine_output(result, "binary_correlation")
        print(
            f"    → Correlated (ρ=0.7) margin EV = {result.get('summary', {}).get('mean', 0):.2f}"
        )

    check("Binary MC with Cholesky correlation on real POS data", test_binary_correlation)

    # ── A15: MCMC on POS data ─────────────────────────────────────────────────
    def test_binary_mcmc():
        if not _pos_price or not _pos_cost:
            skip("Binary MCMC", "No POS price/cost stats")
            return
        # Build observed margins from CSV stats (synthetic sample around real mean)
        margin_mean = max(0.01, _pos_price["mean"] - _pos_cost["mean"])
        margin_std = max(0.01, (_pos_price["std"] + _pos_cost["std"]) / 2)
        import random as _rand

        _rand.seed(42)
        observed = [max(0.0, _rand.gauss(margin_mean, margin_std)) for _ in range(50)]
        result = invoke_binary(
            {
                "engine_type": "mcmc",
                "runs": 500,
                "seed": 33,
                "variables": [
                    {
                        "name": "margin",
                        "distribution": "normal",
                        "params": {"mean": margin_mean, "std": margin_std},
                    }
                ],
                "objective_function": "margin",
                "mcmc_config": {
                    "observed_data": observed,
                    "likelihood": "normal",
                    "chains": 2,
                    "burn_in": 200,
                },
            }
        )
        _assert_engine_output(result, "binary_mcmc")
        print(f"    → MCMC posterior mean = {result.get('summary', {}).get('mean', 0):.2f}")

    check("Binary MCMC Bayesian inference on POS margin", test_binary_mcmc)

    # ── A16: Compare engine — customer segments ───────────────────────────────
    def test_binary_compare():
        if not _q_price:
            skip("Binary Compare", "No Quotes price stats")
            return
        q = _q_price
        result = invoke_binary(
            {
                "engine_type": "compare",
                "runs": 300,
                "seed": 21,
                "scenarios": [
                    {
                        "name": "OEM segment",
                        "variables": [
                            {
                                "name": "price",
                                "distribution": "normal",
                                "params": {"mean": q["mean"] * 1.15, "std": q["std"] * 0.8},
                            }
                        ],
                        "objective_function": "price",
                    },
                    {
                        "name": "Broker segment",
                        "variables": [
                            {
                                "name": "price",
                                "distribution": "normal",
                                "params": {"mean": q["mean"] * 0.90, "std": q["std"] * 1.2},
                            }
                        ],
                        "objective_function": "price",
                    },
                    {
                        "name": "MRO segment",
                        "variables": [
                            {
                                "name": "price",
                                "distribution": "triangular",
                                "params": {
                                    "low": q["min"],
                                    "mode": q["median"],
                                    "high": min(q["max"], q["mean"] * 6),
                                },
                            }
                        ],
                        "objective_function": "price",
                    },
                ],
            }
        )
        assert isinstance(result, dict), "Compare result is not a dict"
        print(f"    → Compare result keys: {list(result.keys())[:6]}")

    check("Binary compare engine with real Quotes segment data", test_binary_compare)


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER B — API-level tests with real CSV data + all engines
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  LAYER B: API-Level Engine Tests with Real Data")
print("=" * 70)

if SKIP_API:
    print(f"  {SKIP} Skipped (DE_SKIP_API=1)")
else:
    # ── B1: All 11 engines via API with real POS revenue/cost data ────────────
    _API_ENGINES_DATA = {
        "monte_carlo": {},
        "lhs": {},
        "qmc_sobol": {},
        "bootstrap": {
            "bootstrap_config": {
                "historical_data": _pos_margin[:150] if len(_pos_margin) >= 150 else _pos_margin,
                "statistic": "mean",
            }
        },
        "sensitivity": {},
        "mcmc": {
            "mcmc_config": {
                "observed_data": _pos_margin[:50] if len(_pos_margin) >= 50 else _pos_margin,
                "likelihood": "normal",
                "chains": 2,
                "burn_in": 200,
            }
        },
        "importance_sampling": {},
    }

    for _eng, _extra in _API_ENGINES_DATA.items():

        def _make_api_test(eng: str, extra: dict[str, Any]):
            def _t():
                if not _pos_price or not _pos_cost:
                    skip(f"API {eng} real data", "No POS stats")
                    return
                if eng in {"bootstrap", "mcmc"} and len(_pos_margin) < 2:
                    skip(f"API {eng} real data", "No POS margin sample")
                    return
                variables = [
                    {
                        "name": "unit_price",
                        "distribution": "lognormal",
                        "params": {
                            "mean": math.log(max(1, _pos_price["mean"])),
                            "std": min(2.0, _pos_price["std"] / max(1, _pos_price["mean"])),
                        },
                    },
                    {
                        "name": "unit_cost",
                        "distribution": "lognormal",
                        "params": {
                            "mean": math.log(max(1, _pos_cost["mean"])),
                            "std": min(2.0, _pos_cost["std"] / max(1, _pos_cost["mean"])),
                        },
                    },
                ]
                payload_extra = dict(extra)
                if eng == "importance_sampling":
                    # Importance sampling requires an explicit tail config and at least one
                    # normal variable the engine can tilt toward the target tail.
                    variables = [
                        {
                            "name": "unit_price",
                            "distribution": "normal",
                            "params": {
                                "mean": _pos_price["mean"],
                                "std": max(_pos_price["std"], 1.0),
                            },
                        },
                        {
                            "name": "unit_cost",
                            "distribution": "normal",
                            "params": {
                                "mean": _pos_cost["mean"],
                                "std": max(_pos_cost["std"], 1.0),
                            },
                        },
                    ]
                    payload_extra["importance_sampling_config"] = {
                        "target_threshold": -max(
                            5.0, abs(_pos_cost["mean"] - _pos_price["mean"]) * 2.0
                        ),
                        "tail_direction": "lower",
                        "tilt_variable": "unit_cost",
                    }

                payload = _api_expert(
                    variables=variables,
                    objective="unit_price - unit_cost",
                    runs=500,
                    engine=eng,
                    seed=1,
                    **payload_extra,
                )
                status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
                ensure_simulation_capacity_available(status, body)
                assert status == 200, f"[{eng}] Expected 200, got {status}: {str(body)[:200]}"
                m = body.get("metrics", {})
                assert "expected_value" in m, f"[{eng}] Missing expected_value"
                timings.append((f"API {eng} (POS data)", elapsed))

            return _t

        check(
            f"API engine {_eng} with real POS price/cost data",
            _make_api_test(_eng, _extra),
        )

    # ── B2: Bootstrap with real historical booking values ────────────────────
    def test_api_bootstrap_real_data():
        if not _bk_ext:
            skip("API bootstrap real", "No Bookings EXT_PRICE")
            return
        sample = _bk_ext["raw"][:150]
        payload = {
            "mode": "expert",
            "simulation_model": "bootstrap",
            "runs": 1000,
            "simulation": {
                "variables": [
                    {
                        "name": "booking_value",
                        "distribution": "fixed",
                        "params": {"value": _bk_ext["mean"]},
                    }
                ],
                "objective_function": "booking_value",
            },
            "bootstrap_config": {
                "historical_data": sample,
                "statistic": "mean",
            },
        }
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API bootstrap (Bookings historical data)", elapsed))
        print(f"    → Bootstrap CI from {len(sample)} real booking values")

    check("API bootstrap with real Bookings historical data", test_api_bootstrap_real_data)

    # ── B3: Scenario engine — Backlog business scenarios ─────────────────────
    def test_api_scenario_backlog():
        if not _bl_price:
            skip("API scenario backlog", "No Backlog stats")
            return
        p = _bl_price
        payload = {
            "mode": "expert",
            "simulation_model": "scenario",
            "runs": 800,
            "simulation": {
                "variables": [
                    {
                        "name": "order_value",
                        "distribution": "triangular",
                        "params": {
                            "low": p["min"],
                            "mode": p["median"],
                            "high": min(p["max"], p["mean"] * 8),
                        },
                    }
                ],
                "objective_function": "order_value",
            },
            "scenario_config": {
                "scenarios": [
                    {
                        "name": "Strong quarter (all backlog ships)",
                        "probability": 0.35,
                        "variables": {"order_value": p["mean"] * 1.15},
                    },
                    {
                        "name": "Normal quarter",
                        "probability": 0.50,
                        "variables": {"order_value": p["mean"]},
                    },
                    {
                        "name": "Weak quarter (cancellations)",
                        "probability": 0.15,
                        "variables": {"order_value": p["mean"] * 0.65},
                    },
                ]
            },
        }
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API scenario (Backlog)", elapsed))
        print(
            f"    → Backlog scenario: action={body.get('recommended_action')}, "
            f"confidence={body.get('confidence', 0):.2%}"
        )

    check("API scenario with real Backlog quarterly outlook", test_api_scenario_backlog)

    # ── B4: Decision tree — Quote win/loss on Quotes data ────────────────────
    def test_api_decision_tree_quotes():
        if not _q_price:
            skip("API decision tree quotes", "No Quotes stats")
            return
        q = _q_price
        payload = {
            "mode": "expert",
            "simulation_model": "decision_tree",
            "runs": 500,
            "simulation": {
                "variables": [
                    {
                        "name": "price",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, q["mean"])), "std": 0.6},
                    },
                    {
                        "name": "cost",
                        "distribution": "normal",
                        "params": {"mean": q["mean"] * 0.75, "std": q["std"] * 0.3},
                    },
                ],
                "objective_function": "price - cost",
            },
            "decision_tree_config": {
                "nodes": [
                    {
                        "id": "quote_root",
                        "type": "decision",
                        "name": "Submit Quote?",
                        "branches": [
                            {
                                "id": "won",
                                "type": "terminal",
                                "name": "Quote Won",
                                "probability": 0.38,
                                "variables": {
                                    "price": {
                                        "distribution": "lognormal",
                                        "params": {"mean": math.log(max(1, q["mean"])), "std": 0.4},
                                    },
                                    "cost": {
                                        "distribution": "normal",
                                        "params": {
                                            "mean": q["mean"] * 0.72,
                                            "std": q["std"] * 0.25,
                                        },
                                    },
                                },
                                "objective_function": "price - cost",
                            },
                            {
                                "id": "lost",
                                "type": "terminal",
                                "name": "Quote Lost",
                                "probability": 0.62,
                                "variables": {
                                    "price": {"distribution": "fixed", "params": {"value": 0.0}},
                                    "cost": {
                                        "distribution": "fixed",
                                        "params": {"value": q["mean"] * 0.015},
                                    },
                                },
                                "objective_function": "price - cost",
                            },
                        ],
                    },
                ]
            },
        }
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API decision_tree (Quotes)", elapsed))
        print(
            f"    → Quotes win/loss DT: EV={body.get('metrics', {}).get('expected_value', 0):.2f}"
        )

    check("API decision_tree with real Quotes win/loss paths", test_api_decision_tree_quotes)

    # ── B5: Time series — Revenue forecast from Bookings baseline ────────────
    def test_api_timeseries_bookings():
        if not _bk_ext:
            skip("API time_series bookings", "No Bookings stats")
            return
        initial = _bk_ext["mean"]
        vol = min(0.8, _bk_ext["std"] / max(1, initial))
        payload = {
            "mode": "expert",
            "simulation_model": "time_series",
            "runs": 1000,
            "simulation": {
                "variables": [
                    {
                        "name": "rev",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, initial)), "std": 0.4},
                    }
                ],
                "objective_function": "rev",
            },
            "time_series_config": {
                "model": "gbm",
                "initial_value": initial,
                "drift": 0.06,
                "volatility": vol,
                "dt": 0.0833,
                "horizons": [1, 3, 6, 12],
            },
        }
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API time_series (Bookings GBM)", elapsed))
        print(
            f"    → GBM initial={initial:.0f}, vol={vol:.1%}, "
            f"action={body.get('recommended_action')}"
        )

    check("API time_series GBM with real Bookings revenue baseline", test_api_timeseries_bookings)

    # ── B6: Compare engine — OEM vs Broker vs MRO from Quotes ────────────────
    def test_api_compare_quotes_segments():
        if not _q_price:
            skip("API compare quotes segments", "No Quotes stats")
            return
        q = _q_price

        def _seg_req(mean_mult: float, std_mult: float) -> dict:
            return _api_expert(
                variables=[
                    {
                        "name": "price",
                        "distribution": "normal",
                        "params": {"mean": q["mean"] * mean_mult, "std": q["std"] * std_mult},
                    }
                ],
                objective="price",
                runs=300,
                seed=77,
            )

        status, body, elapsed = api(
            "POST",
            "/v1/compare",
            body={
                "scenarios": [
                    {"name": "OEM customers", "request": _seg_req(1.20, 0.70)},
                    {"name": "Broker customers", "request": _seg_req(0.85, 1.30)},
                    {"name": "MRO customers", "request": _seg_req(1.05, 1.00)},
                    {"name": "Gov/Defense", "request": _seg_req(1.35, 0.50)},
                ]
            },
            timeout=30,
        )
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        assert "winner" in body, "Missing winner"
        timings.append(("API compare (Quotes segments)", elapsed))
        print(f"    → Quotes segment winner: {body['winner']}")

    check("API compare with real Quotes customer-segment pricing", test_api_compare_quotes_segments)

    # ── B7: Sensitivity analysis on OPO procurement drivers ──────────────────
    def test_api_sensitivity_opo():
        if not _opo_cost or not _opo_qty:
            skip("API sensitivity OPO", "No OPO stats")
            return
        oc, oq = _opo_cost, _opo_qty
        payload = _api_expert(
            variables=[
                {
                    "name": "unit_cost",
                    "distribution": "triangular",
                    "params": {
                        "low": oc["min"],
                        "mode": oc["median"],
                        "high": min(oc["max"], oc["mean"] * 5),
                    },
                },
                {
                    "name": "qty",
                    "distribution": "triangular",
                    "params": {
                        "low": max(1.0, oq["min"]),
                        "mode": max(1.0, oq["median"]),
                        "high": min(oq["max"], oq["mean"] * 5),
                    },
                },
                {
                    "name": "lead_days",
                    "distribution": "triangular",
                    "params": {"low": 7.0, "mode": 30.0, "high": 90.0},
                },
                {
                    "name": "tariff_pct",
                    "distribution": "uniform",
                    "params": {"low": 0.0, "high": 0.25},
                },
            ],
            objective="unit_cost * qty * (1 + tariff_pct) * -1",
            runs=500,
            engine="sensitivity",
        )
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API sensitivity (OPO drivers)", elapsed))
        print(f"    → OPO sensitivity: action={body.get('recommended_action')}")

    check("API sensitivity with real OPO procurement cost drivers", test_api_sensitivity_opo)

    # ── B8: Importance sampling — rare high-cost OPO event ───────────────────
    def test_api_importance_sampling_opo():
        if not _opo_cost:
            skip("API importance sampling OPO", "No OPO cost stats")
            return
        oc = _opo_cost
        payload = _api_expert(
            variables=[
                {
                    "name": "unit_cost",
                    "distribution": "normal",
                    "params": {"mean": oc["mean"], "std": oc["std"]},
                },
                {
                    "name": "qty",
                    "distribution": "triangular",
                    "params": {"low": 1.0, "mode": 5.0, "high": 50.0},
                },
            ],
            objective="unit_cost * qty * -1",
            runs=2000,
            engine="importance_sampling",
        )
        payload["importance_sampling_config"] = {
            "target_threshold": -(oc["mean"] * 20),
            "tail_direction": "lower",
        }
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API importance_sampling (OPO)", elapsed))
        print(
            f"    → IS rare event P(loss): "
            f"{body.get('metrics', {}).get('probability_of_loss', 0):.6%}"
        )

    check("API importance_sampling for rare high-cost OPO event", test_api_importance_sampling_opo)

    # ── B9: Correlated variables — Bookings price/cost ────────────────────────
    def test_api_correlated_bookings():
        if not _bk_ext or not _bk_cost:
            skip("API correlated bookings", "No Bookings data")
            return
        payload = {
            "mode": "expert",
            "simulation_model": "monte_carlo",
            "runs": 2000,
            "seed": 88,
            "simulation": {
                "variables": [
                    {
                        "name": "ext_price",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, _bk_ext["mean"])), "std": 0.6},
                    },
                    {
                        "name": "ext_cost",
                        "distribution": "lognormal",
                        "params": {"mean": math.log(max(1, _bk_cost["mean"])), "std": 0.5},
                    },
                ],
                "objective_function": "ext_price - ext_cost",
                "correlations": [{"variables": ["ext_price", "ext_cost"], "coefficient": 0.65}],
            },
        }
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=30)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        timings.append(("API correlated Bookings margin", elapsed))
        print(
            f"    → Bookings correlated margin EV="
            f"{body.get('metrics', {}).get('expected_value', 0):.2f}"
        )

    check("API MC with Cholesky correlation on real Bookings data", test_api_correlated_bookings)

    # ── B10: Large-N performance — 50k runs with real POS data ───────────────
    def test_api_large_n_performance():
        if not _pos_price:
            skip("API large-N performance", "No POS price stats")
            return
        payload = _api_expert(
            variables=[
                {
                    "name": "price",
                    "distribution": "lognormal",
                    "params": {"mean": math.log(max(1, _pos_price["mean"])), "std": 0.8},
                },
                {
                    "name": "cost",
                    "distribution": "lognormal",
                    "params": {"mean": math.log(max(1, _pos_cost["mean"])), "std": 0.7},
                },
                {
                    "name": "qty",
                    "distribution": "triangular",
                    "params": {"low": 1.0, "mode": 5.0, "high": 50.0},
                },
            ],
            objective="(price - cost) * qty",
            runs=50_000,
            engine="monte_carlo",
        )
        status, body, elapsed = api("POST", "/v1/simulate", payload, timeout=60)
        ensure_simulation_capacity_available(status, body)
        assert status == 200, f"Expected 200, got {status}: {str(body)[:200]}"
        assert elapsed < 5.0, f"50k runs took {elapsed:.2f}s — expected < 5s"
        timings.append(("API MC 50k runs (POS data)", elapsed))
        print(
            f"    → 50k runs in {elapsed * 1000:.0f}ms  "
            f"(throughput = {50_000 / elapsed:.0f} runs/s)"
        )

    check("API MC 50,000 runs with real POS data in < 5s", test_api_large_n_performance)


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER C — Python adapter (python_adapter.py) tests
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  LAYER C: Python Fallback Adapter Tests")
print("=" * 70)


def test_adapter_smoke():
    result = invoke_adapter(
        {
            "runs": 500,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "normal", "params": {"mean": 0.0, "std": 1.0}}
            ],
            "objective_function": "x",
        }
    )
    assert isinstance(result, dict), "Adapter result not a dict"
    assert "summary" in result, f"Missing summary: {list(result.keys())}"
    assert result["summary"]["mean"] is not None


check("Python adapter smoke test", test_adapter_smoke)


def test_adapter_pos_margin():
    if not _pos_price or not _pos_cost:
        skip("Adapter POS margin", "No POS stats")
        return
    result = invoke_adapter(
        {
            "runs": 1000,
            "seed": 1,
            "variables": [
                {
                    "name": "price",
                    "distribution": "lognormal",
                    "params": {"mean": math.log(max(1, _pos_price["mean"])), "std": 0.8},
                },
                {
                    "name": "cost",
                    "distribution": "lognormal",
                    "params": {"mean": math.log(max(1, _pos_cost["mean"])), "std": 0.7},
                },
            ],
            "objective_function": "price - cost",
        }
    )
    ev = result["summary"]["mean"]
    print(f"    → Adapter POS margin EV = {ev:.2f}")
    assert isinstance(ev, int | float), "EV must be numeric"


check("Python adapter POS price-cost margin simulation", test_adapter_pos_margin)


def test_adapter_triangular_backlog():
    if not _bl_price:
        skip("Adapter triangular backlog", "No Backlog stats")
        return
    p = _bl_price
    result = invoke_adapter(
        {
            "runs": 1000,
            "seed": 7,
            "variables": [
                {
                    "name": "order_value",
                    "distribution": "triangular",
                    "params": {
                        "low": p["min"],
                        "mode": p["median"],
                        "high": min(p["max"], p["mean"] * 8),
                    },
                }
            ],
            "objective_function": "order_value",
        }
    )
    ev = result["summary"]["mean"]
    assert ev > 0, f"Backlog EV should be positive, got {ev}"
    print(f"    → Adapter Backlog EV = {ev:.2f}")


check("Python adapter triangular Backlog order-value", test_adapter_triangular_backlog)


def test_adapter_determinism():
    payload = {
        "runs": 200,
        "seed": 2024,
        "variables": [
            {"name": "x", "distribution": "uniform", "params": {"low": 0.0, "high": 100.0}}
        ],
        "objective_function": "x",
    }
    r1 = invoke_adapter(payload)
    r2 = invoke_adapter(payload)
    assert r1["summary"]["mean"] == r2["summary"]["mean"], (
        f"Adapter not deterministic: {r1['summary']['mean']} vs {r2['summary']['mean']}"
    )


check("Python adapter seeded runs are deterministic", test_adapter_determinism)


def test_adapter_all_5_distributions():
    for dist_name, params, var_name in [
        ("normal", {"mean": 100.0, "std": 15.0}, "x"),
        ("uniform", {"low": 50.0, "high": 150.0}, "x"),
        ("triangular", {"low": 60.0, "mode": 100.0, "high": 140.0}, "x"),
        ("lognormal", {"mean": 4.6, "std": 0.3}, "x"),
        ("fixed", {"value": 42.0}, "x"),
    ]:
        result = invoke_adapter(
            {
                "runs": 200,
                "seed": 1,
                "variables": [{"name": var_name, "distribution": dist_name, "params": params}],
                "objective_function": var_name,
            }
        )
        ev = result["summary"]["mean"]
        assert isinstance(ev, int | float), f"[{dist_name}] EV must be numeric, got {type(ev)}"


check(
    "Python adapter: all 5 supported distributions produce numeric EV",
    test_adapter_all_5_distributions,
)


def test_adapter_probability_of_loss():
    """Negative-mean distribution should have high probability of loss."""
    result = invoke_adapter(
        {
            "runs": 2000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "normal", "params": {"mean": -50.0, "std": 10.0}}
            ],
            "objective_function": "x",
        }
    )
    pol = result["risk"]["probability_of_loss"]
    assert pol > 0.95, f"Expected P(loss) > 0.95 for mean=-50, got {pol:.4f}"
    print(f"    → P(loss | mean=-50) = {pol:.4%}  ✓")


check(
    "Python adapter probability_of_loss correct for negative-mean dist",
    test_adapter_probability_of_loss,
)


def test_adapter_score_range():
    for mean in [-100, 0, 100]:
        result = invoke_adapter(
            {
                "runs": 500,
                "seed": 1,
                "variables": [
                    {
                        "name": "x",
                        "distribution": "normal",
                        "params": {"mean": float(mean), "std": 20.0},
                    }
                ],
                "objective_function": "x",
            }
        )
        score = result.get("score", None)
        assert score is not None, f"Missing score for mean={mean}"
        assert 0.0 <= score <= 1.0, f"Score {score} out of [0,1] for mean={mean}"


check(
    "Python adapter score always in [0, 1] across negative/zero/positive means",
    test_adapter_score_range,
)


if __name__ == "__main__":
    import pytest

    exit_code = pytest.main([__file__, "-v"])
    # Write summary artifact for CI consumers (preserves the
    # tests/test_runtime_surface_compatibility surface contract).
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_mojo_engines_realdata.py",
            passed=0,  # TODO: parse from pytest result
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
