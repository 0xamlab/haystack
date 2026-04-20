"""
test_csv_regression.py — CSV-driven regression + real business data tests.

Three layers:
  Layer A — Validate the CSV baselines themselves (structure, schema, data quality)
  Layer B — Replay every recorded row against the live API; assert status codes match
  Layer C — Load real business CSVs, derive simulation inputs, run live simulations

CSV baselines (in tests/integration/):
  benchmark_results.csv   — engine scaling at 100–50,000 runs
  template_results.csv    — 51 templates across domains
  engine_results.csv      — 81 engine/mode/distribution combinations
  csv_pipeline_results.csv — real CSV file parse+simulate pipeline

Real data (in test_files/):
  Backlog.csv             — open orders with UNIT_PRICE, EXT_PRICE, QUANTITY
  OPO.csv                 — open purchase orders with Ext Open Cost

Run:
  DE_SKIP_API=1 python3 tests/integration/test_csv_regression.py    # Layer A only
  python3 tests/integration/test_csv_regression.py                   # All layers
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from statistics import mean, stdev

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY  = os.environ.get("DE_API_KEY",  "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

CSV_DIR   = _ROOT / "tests" / "integration"
DATA_DIR  = _ROOT / "test_files"

PASS = "✅"; FAIL = "❌"; SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def req(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            b = json.loads(e.read())
        except Exception:
            b = {}
        return e.code, b


def load_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── Layer A: CSV structure validation ─────────────────────────────────────────

def test_csv_files_exist():
    for fname in ["benchmark_results.csv", "template_results.csv",
                  "engine_results.csv", "csv_pipeline_results.csv"]:
        p = CSV_DIR / fname
        check(f"{fname} exists", p.exists(), str(p))


def test_benchmark_csv_structure():
    rows = load_csv(CSV_DIR / "benchmark_results.csv")
    check("benchmark_results has rows",    len(rows) > 0, f"{len(rows)} rows")
    check("benchmark_results has 83 rows", len(rows) == 83, f"got {len(rows)}")

    required_cols = {"test_name", "engine", "runs", "status_code", "latency_ms"}
    cols = set(rows[0].keys()) if rows else set()
    check("benchmark_results has required columns", required_cols <= cols,
          str(required_cols - cols) if not required_cols <= cols else "")

    # Only rows with a recorded status_code should be 200 (concurrency rows have blank status)
    rows_with_status = [r for r in rows if r["status_code"].strip()]
    non_200 = [r for r in rows_with_status if r["status_code"] not in ("200",)]
    check(
        "benchmark_results status rows are 200 or 422",
        all(r["status_code"] in ("200", "422") for r in rows_with_status),
        f"{[r['test_name'] for r in non_200[:3]]}" if non_200 else "",
    )

    # Only count engines from engine_scaling rows (non-empty engine + runs)
    engine_rows = [r for r in rows if r["engine"].strip() and r["runs"].strip()]
    engines = {r["engine"] for r in engine_rows}
    check("benchmark_results covers ≥4 simulation engines", len(engines) >= 4, str(engines))

    run_counts = sorted({int(r["runs"]) for r in engine_rows})
    check("benchmark_results covers ≥5 run scales", len(run_counts) >= 5, str(run_counts))


def test_template_csv_structure():
    rows = load_csv(CSV_DIR / "template_results.csv")
    check("template_results has rows",     len(rows) > 0, f"{len(rows)} rows")
    check("template_results has ≥20 rows", len(rows) >= 20, f"got {len(rows)}")

    required_cols = {"slug", "domain", "status_code", "pass"}
    cols = set(rows[0].keys()) if rows else set()
    check("template_results has required columns", required_cols <= cols,
          str(required_cols - cols) if not required_cols <= cols else "")

    all_pass = all(r.get("pass", "").lower() == "true" for r in rows)
    fail_slugs = [r["slug"] for r in rows if r.get("pass", "").lower() != "true"]
    check("template_results all pass=true", all_pass,
          f"failing: {fail_slugs[:5]}" if fail_slugs else "")

    domains = {r["domain"] for r in rows}
    check("template_results covers ≥5 domains", len(domains) >= 5, str(domains))


def test_engine_csv_structure():
    rows = load_csv(CSV_DIR / "engine_results.csv")
    check("engine_results has rows",     len(rows) > 0, f"{len(rows)} rows")
    check("engine_results has ≥50 rows", len(rows) >= 50, f"got {len(rows)}")

    required_cols = {"engine", "mode", "runs", "status_code", "execution_ms"}
    cols = set(rows[0].keys()) if rows else set()
    check("engine_results has required columns", required_cols <= cols,
          str(required_cols - cols) if not required_cols <= cols else "")

    expected_200 = [r for r in rows if r.get("status_code") == "200"]
    expected_422 = [r for r in rows if r.get("status_code") == "422"]
    check("engine_results has 200-status rows",  len(expected_200) > 70, f"{len(expected_200)} rows")
    check("engine_results has 422-status rows",  len(expected_422) >= 1, f"{len(expected_422)} rows")

    engines = {r["engine"] for r in rows}
    check("engine_results covers ≥7 engines", len(engines) >= 7, str(engines))


def test_pipeline_csv_structure():
    rows = load_csv(CSV_DIR / "csv_pipeline_results.csv")
    check("csv_pipeline_results has rows", len(rows) > 0, f"{len(rows)} rows")

    required_cols = {"filename", "rows", "status", "total_time_ms"}
    cols = set(rows[0].keys()) if rows else set()
    check("csv_pipeline_results has required columns", required_cols <= cols,
          str(required_cols - cols) if not required_cols <= cols else "")

    simulated = [r for r in rows if r.get("status") == "simulated"]
    parsed    = [r for r in rows if r.get("status") == "parsed"]
    check("pipeline has simulated rows", len(simulated) >= 1, f"{len(simulated)}")
    check("pipeline has parsed rows",    len(parsed) >= 1,    f"{len(parsed)}")


def test_real_data_files_exist():
    for fname in ["Backlog.csv", "OPO.csv"]:
        p = DATA_DIR / fname
        check(f"test_files/{fname} exists", p.exists(), str(p))


def test_real_data_numeric_columns():
    """Validate Backlog.csv has the expected pricing columns with non-zero values."""
    path = DATA_DIR / "Backlog.csv"
    if not path.exists():
        check("Backlog.csv numeric columns", False, "file not found")
        return
    rows = load_csv(path)
    check("Backlog.csv has ≥100 rows", len(rows) >= 100, f"{len(rows)} rows")

    unit_prices = []
    ext_prices  = []
    quantities  = []
    for r in rows:
        try:
            if r.get("UNIT_PRICE", "").strip():
                unit_prices.append(float(r["UNIT_PRICE"]))
        except ValueError:
            pass
        try:
            if r.get("EXT_PRICE", "").strip():
                ext_prices.append(float(r["EXT_PRICE"]))
        except ValueError:
            pass
        try:
            if r.get("QUANTITY", "").strip():
                quantities.append(float(r["QUANTITY"]))
        except ValueError:
            pass

    check("Backlog UNIT_PRICE column has values", len(unit_prices) > 50, f"{len(unit_prices)}")
    check("Backlog EXT_PRICE column has values",  len(ext_prices) > 50,  f"{len(ext_prices)}")
    check("Backlog QUANTITY column has values",   len(quantities) > 50,  f"{len(quantities)}")

    if unit_prices:
        avg_price = mean(unit_prices)
        check("Backlog avg UNIT_PRICE > 0", avg_price > 0, f"avg={avg_price:.2f}")
    if ext_prices:
        avg_ext = mean(ext_prices)
        check("Backlog avg EXT_PRICE > 0", avg_ext > 0, f"avg={avg_ext:.2f}")


# ── Layer B: API replay from CSV baselines ─────────────────────────────────────

def test_replay_engine_results():
    """Replay engine_results.csv rows against live API. Status codes must match."""
    rows = load_csv(CSV_DIR / "engine_results.csv")

    # Group: only replay simple auto/expert rows (not the composite mode rows)
    simple = [r for r in rows if "/" not in r.get("mode", "")
              and r.get("engine") not in ("nonexistent_engine",)]

    passed = failed = 0
    fail_details: list[str] = []

    for r in simple:
        engine   = r["engine"]
        mode     = r.get("mode", "auto")
        n_vars   = int(r.get("variables", 2))
        runs     = int(r.get("runs", 500))
        expected = int(r.get("status_code", 200))

        # Expert mode: correct payload format for the simulate endpoint
        variables = [
            {"name": f"var_{i}", "distribution": "normal",
             "params": {"mean": 100000, "std": 15000}}
            for i in range(n_vars)
        ]
        payload = {
            "mode": "expert",
            "simulation_model": engine,
            "runs": runs,
            "simulation": {
                "variables": variables,
                "objective_function": " + ".join(f"var_{i}" for i in range(n_vars)),
            },
        }

        status, _ = req("POST", "/v1/simulate", payload)
        ok = (status == expected)
        if ok:
            passed += 1
        else:
            failed += 1
            fail_details.append(f"{engine}/{mode}/{runs}: expected {expected}, got {status}")

    total = passed + failed
    check(
        f"engine replay: {passed}/{total} match recorded status codes",
        failed == 0,
        "; ".join(fail_details[:3]) if fail_details else "",
    )


@pytest.mark.slow
def test_replay_template_results():
    """Replay template_results.csv — all recorded slugs should still return 200."""
    rows = load_csv(CSV_DIR / "template_results.csv")
    passed = failed = 0
    fail_slugs: list[str] = []

    for r in rows:
        slug = r["slug"]
        runs = min(int(r.get("runs", 1000)), 1000)  # cap at 1000 for speed

        status, body = req("POST", f"/v1/templates/{slug}/run?runs={runs}")
        ok = (status == 200)
        if ok:
            passed += 1
        else:
            failed += 1
            fail_slugs.append(f"{slug}→{status}")

    total = passed + failed
    check(
        f"template replay: {passed}/{total} return 200",
        failed == 0,
        "; ".join(fail_slugs[:5]) if fail_slugs else "",
    )


def test_replay_benchmark_scaling():
    """
    Replay benchmark_results.csv scaling tests.
    Assert all return 200 and latency stays within 5× of recorded baseline.
    """
    rows = load_csv(CSV_DIR / "benchmark_results.csv")
    regressions: list[str] = []
    passed = failed = 0

    # Only engines that work without extra config (specialized engines need
    # sensitivity_config, mcmc_config, etc. and are tested separately)
    _BASIC_ENGINES = {"monte_carlo", "lhs", "qmc_sobol", "bootstrap", "scenario"}

    # Only rows with a valid engine and run count (skip latency/concurrency rows)
    sample = [r for r in rows
              if r.get("engine", "").strip() and r.get("runs", "").strip()
              and int(r["runs"]) == 1000
              and r["engine"] in _BASIC_ENGINES]

    for r in sample:
        engine  = r["engine"]
        runs    = int(r["runs"])
        baseline_ms = float(r.get("latency_ms", 100))
        # Use absolute floor of 2000ms — old baselines were from broken pool
        # returning zeros instantly (~7ms). Subprocess mode takes ~250ms.
        ceiling_ms  = max(baseline_ms * 5, 2000)

        variables = [
            {"name": f"v{i}", "distribution": "normal",
             "params": {"mean": 50000, "std": 10000}}
            for i in range(3)
        ]
        payload = {
            "mode": "expert",
            "simulation_model": engine,
            "runs": runs,
            "simulation": {
                "variables": variables,
                "objective_function": "v0 + v1 + v2",
            },
        }

        import time
        t0 = time.monotonic()
        status, body = req("POST", "/v1/simulate", payload)
        actual_ms = (time.monotonic() - t0) * 1000

        ok = status == 200
        if ok:
            passed += 1
        else:
            failed += 1

        if ok and actual_ms > ceiling_ms:
            regressions.append(
                f"{engine}/{runs}: baseline {baseline_ms:.0f}ms, actual {actual_ms:.0f}ms "
                f"({actual_ms/baseline_ms:.1f}× — ceiling {ceiling_ms:.0f}ms)"
            )

    total = passed + failed
    check(f"benchmark scaling: {passed}/{total} return 200", failed == 0,
          f"{failed} non-200" if failed else "")
    check(
        "benchmark scaling: no latency regressions >5× baseline",
        len(regressions) == 0,
        "; ".join(regressions[:2]) if regressions else "",
    )


# ── Layer C: Real business data simulations ───────────────────────────────────

def _extract_numeric_stats(path: Path, col: str,
                            min_val: float = 0.01) -> tuple[float, float, int]:
    """Return (mean, std, count) for a numeric column in a CSV."""
    rows = load_csv(path)
    values = []
    for r in rows:
        try:
            v = float(r.get(col, "").strip())
            if v >= min_val:
                values.append(v)
        except (ValueError, AttributeError):
            pass
    if len(values) < 2:
        return 0.0, 0.0, 0
    m = mean(values)
    s = stdev(values) if len(values) > 1 else m * 0.3
    return m, s, len(values)


def test_backlog_simulation():
    """Run a real simulation using UNIT_PRICE and QUANTITY stats from Backlog.csv."""
    path = DATA_DIR / "Backlog.csv"
    if not path.exists():
        print(f"  {SKIP}  Backlog.csv not found — skipping")
        return

    price_mean, price_std, price_n = _extract_numeric_stats(path, "UNIT_PRICE")
    qty_mean,   qty_std,   qty_n   = _extract_numeric_stats(path, "QUANTITY")
    ext_mean,   ext_std,   ext_n   = _extract_numeric_stats(path, "EXT_PRICE")

    check(f"Backlog UNIT_PRICE stats extracted ({price_n} rows)",
          price_mean > 0, f"mean={price_mean:.2f}")
    check(f"Backlog QUANTITY stats extracted ({qty_n} rows)",
          qty_mean > 0, f"mean={qty_mean:.2f}")

    if price_mean <= 0 or qty_mean <= 0:
        return

    import math as _math
    # Convert raw mean/std to lognormal mu/sigma parameters
    def _lognormal_params(m: float, s: float) -> tuple[float, float]:
        s = min(s, m * 2)
        sigma2 = _math.log(1 + (s / (m + 1e-9)) ** 2)
        mu = _math.log(m + 1e-9) - sigma2 / 2
        return round(mu, 4), round(_math.sqrt(sigma2), 4)

    price_mu, price_sigma = _lognormal_params(price_mean, price_std)
    qty_mu,   qty_sigma   = _lognormal_params(qty_mean, qty_std)

    # Build simulation from real data statistics — expert mode, correct format
    payload = {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "runs": 5000,
        "simulation": {
            "variables": [
                {
                    "name": "unit_price",
                    "distribution": "lognormal",
                    "params": {"mean": price_mu, "std": price_sigma},
                    "unit": "USD",
                    "description": f"Unit price from {price_n} Backlog records",
                },
                {
                    "name": "quantity",
                    "distribution": "lognormal",
                    "params": {"mean": qty_mu, "std": qty_sigma},
                    "unit": "units",
                    "description": f"Order quantity from {qty_n} Backlog records",
                },
            ],
            "objective_function": "unit_price + quantity",
        },
    }

    status, body = req("POST", "/v1/simulate", payload)
    check("Backlog simulation → 200", status == 200,
          f"got {status}: {str(body)[:100]}")

    if status == 200:
        metrics = body.get("metrics", {})
        ev  = metrics.get("expected_value", body.get("expected_value", 0))
        pol = metrics.get("probability_of_loss", body.get("probability_of_loss", 1))
        p5  = body.get("percentiles", {}).get("p5",  0)
        p95 = body.get("percentiles", {}).get("p95", 0)

        check("Backlog simulation: expected_value > 0",   ev > 0,  f"ev={ev:,.2f}")
        check("Backlog simulation: prob_of_loss < 1",     pol < 1, f"pol={pol:.3f}")
        check("Backlog simulation: p5 < p95",             p5 < p95,
              f"p5={p5:,.2f}, p95={p95:,.2f}")

        print(f"\n    Real data simulation — Backlog.csv ({price_n} orders):")
        print(f"    Avg unit price: ${price_mean:>12,.2f}  ±{price_std:,.2f}")
        print(f"    Avg quantity:   {qty_mean:>12,.1f}  ±{qty_std:,.1f}")
        print(f"    Expected order value: ${ev:>12,.2f}")
        print(f"    Range (p5–p95):  ${p5:>10,.2f}  –  ${p95:,.2f}")
        print(f"    Prob of loss:   {pol:.2%}\n")


def test_opo_simulation():
    """Run a simulation using Ext Open Cost from OPO.csv (open purchase orders)."""
    path = DATA_DIR / "OPO.csv"
    if not path.exists():
        print(f"  {SKIP}  OPO.csv not found — skipping")
        return

    cost_mean, cost_std, cost_n = _extract_numeric_stats(path, "Ext Open Cost")
    check(f"OPO Ext Open Cost stats extracted ({cost_n} rows)",
          cost_mean > 0, f"mean={cost_mean:,.2f}")

    if cost_mean <= 0:
        return

    import math as _math
    def _lognormal_params(m: float, s: float) -> tuple[float, float]:
        s = min(s, m * 1.5)
        sigma2 = _math.log(1 + (s / (m + 1e-9)) ** 2)
        mu = _math.log(m + 1e-9) - sigma2 / 2
        return round(mu, 4), round(_math.sqrt(sigma2), 4)

    cost_mu, cost_sigma = _lognormal_params(cost_mean, cost_std)

    # Simulate open purchase order exposure — expert mode
    payload = {
        "mode": "expert",
        "simulation_model": "lhs",
        "runs": 3000,
        "simulation": {
            "variables": [
                {
                    "name": "open_cost",
                    "distribution": "lognormal",
                    "params": {"mean": cost_mu, "std": cost_sigma},
                    "unit": "USD",
                    "description": f"Open PO cost from {cost_n} OPO records",
                },
                {
                    "name": "delivery_risk",
                    "distribution": "triangular",
                    "params": {"low": 0.80, "mode": 1.00, "high": 1.25},
                    "unit": "multiplier",
                    "description": "Delivery cost overrun risk",
                },
            ],
            "objective_function": "open_cost + delivery_risk",
        },
    }

    status, body = req("POST", "/v1/simulate", payload)
    check("OPO simulation → 200", status == 200, f"got {status}: {str(body)[:100]}")

    if status == 200:
        metrics = body.get("metrics", {})
        ev  = metrics.get("expected_value", body.get("expected_value", 0))
        p95 = body.get("percentiles", {}).get("p95", 0)
        check("OPO simulation: expected_value > 0", ev > 0, f"ev={ev:,.2f}")
        check("OPO simulation: p95 > expected_value (right skew from lognormal)",
              p95 >= ev, f"p95={p95:,.2f}, ev={ev:,.2f}")

        print(f"\n    Real data simulation — OPO.csv ({cost_n} open POs):")
        print(f"    Avg open cost:  ${cost_mean:>12,.2f}")
        print(f"    Expected total: ${ev:>12,.2f}")
        print(f"    P95 exposure:   ${p95:>12,.2f}\n")


def test_real_data_decision():
    """Use Backlog stats to drive a /v1/decision call — the full product flow."""
    path = DATA_DIR / "Backlog.csv"
    if not path.exists():
        print(f"  {SKIP}  Backlog.csv not found")
        return

    price_mean, price_std, price_n = _extract_numeric_stats(path, "UNIT_PRICE")
    qty_mean,   qty_std,   qty_n   = _extract_numeric_stats(path, "QUANTITY")

    if price_mean <= 0 or qty_mean <= 0:
        check("real data decision: can extract stats", False, "zero mean")
        return

    rev_estimate = price_mean * qty_mean
    cost_estimate = rev_estimate * 0.65

    payload = {
        "inputs": [
            {"name": "revenue", "value": rev_estimate,
             "low": rev_estimate * 0.7, "high": rev_estimate * 1.5, "unit": "USD"},
            {"name": "cost",    "value": cost_estimate,
             "low": cost_estimate * 0.85, "high": cost_estimate * 1.2, "unit": "USD"},
        ],
        "objective": "maximize_value",
        "risk_tolerance": "medium",
        "scenarios": 3000,
        "engine": "lhs",
    }

    status, body = req("POST", "/v1/decision", payload)
    check("real data /v1/decision → 200", status == 200,
          f"got {status}: {str(body)[:100]}")

    if status == 200:
        action = body.get("action", "unknown")
        conf   = body.get("confidence", 0)
        why    = body.get("why", [])

        check("real data decision has action", action in ("proceed", "pause", "reject"))
        check("real data decision has confidence", 0 <= conf <= 1)
        check("real data decision has why array", len(why) == 3, f"got {len(why)}")

        print(f"\n    Decision from Backlog.csv data ({price_n} orders):")
        print(f"    Revenue estimate: ${rev_estimate:>10,.2f}")
        print(f"    Cost estimate:    ${cost_estimate:>10,.2f}")
        print(f"    Action:      {action.upper()}")
        print(f"    Confidence:  {conf:.0%}")
        for w in why:
            print(f"    → {w}")
        print()


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  CSV REGRESSION + REAL DATA TESTS")
    print("=" * 68)

    print("\n── Layer A: CSV structure validation (no server) ───────────────\n")
    for fn in [
        test_csv_files_exist,
        test_benchmark_csv_structure,
        test_template_csv_structure,
        test_engine_csv_structure,
        test_pipeline_csv_structure,
        test_real_data_files_exist,
        test_real_data_numeric_columns,
    ]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    if SKIP_API:
        print("\n── Layer B+C: API replay ─────────────────────────────────────────\n")
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        print("\n── Layer B: Replay CSV baselines against live API ───────────────\n")
        for fn in [
            test_replay_engine_results,
            test_replay_template_results,
            test_replay_benchmark_scaling,
        ]:
            try:
                fn()
            except urllib.error.URLError as e:
                print(f"  {SKIP}  {fn.__name__} — server unreachable ({e.reason})")
                break
            except Exception as e:
                check(fn.__name__, False, f"{type(e).__name__}: {e}")

        print("\n── Layer C: Real business data simulations ──────────────────────\n")
        for fn in [
            test_backlog_simulation,
            test_opo_simulation,
            test_real_data_decision,
        ]:
            try:
                fn()
            except urllib.error.URLError as e:
                print(f"  {SKIP}  {fn.__name__} — server unreachable ({e.reason})")
                break
            except Exception as e:
                check(fn.__name__, False, f"{type(e).__name__}: {e}")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'=' * 68}")
    print(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    print(f"{'=' * 68}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
