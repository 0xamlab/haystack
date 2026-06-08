#!/usr/bin/env python3
"""
benchmarks/bench_10q.py — 10-question cross-reference speed benchmark.

Tests: metric resolution, dimension resolution, join detection, and execution
across 4 real sources (Bookings, Quotes, POS, Inventory).

Each question runs COLD (no cache) and HOT (repeat plan + execute).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── ANSI ──────────────────────────────────────────────────────────────────────
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
B = "\033[1m"
D = "\033[2m"
X = "\033[0m"

W = 72

QUESTIONS = [
    # (
    #   label, description, metric_hint, dim_hint, agg,
    #   preferred_source, cross_source, expected_error
    # )
    (
        "Q1",
        "Revenue by product line (Bookings)",
        "revenue",
        "product line",
        "sum",
        "Bookings",
        False,
        None,
    ),
    (
        "Q2",
        "Revenue by customer type (Quotes)",
        "revenue",
        "customer type",
        "sum",
        "Quotes",
        False,
        None,
    ),
    (
        "Q3",
        "Revenue by business unit (Bookings)",
        "revenue",
        "business unit",
        "sum",
        "Bookings",
        False,
        None,
    ),
    (
        "Q4",
        "Revenue by sales rep (Bookings)",
        "revenue",
        "sales rep",
        "sum",
        "Bookings",
        False,
        None,
    ),
    (
        "Q5",
        "Unit price by manufacturer (Bookings)",
        "unit price",
        "manufacturer",
        "avg",
        "Bookings",
        False,
        None,
    ),
    (
        "Q6",
        "Extended cost by vendor (Inventory)",
        "extended cost",
        "vendor",
        "sum",
        "Inventory",
        False,
        None,
    ),
    (
        "Q7",
        "Quantity by condition (Inventory)",
        "quantity",
        "condition",
        "sum",
        "Inventory",
        False,
        None,
    ),
    (
        "Q8",
        "Revenue by product line [POS → cross join Quotes]",
        "revenue",
        "product line",
        "sum",
        "POS",
        True,
        None,
    ),
    (
        "Q9",
        "AAR margin % by customer type (Quotes cross-source, expected reject)",
        "aar margin percent",
        "customer type",
        "avg",
        "Quotes",
        True,
        "No safe join path",
    ),
    (
        "Q10",
        "Revenue total scalar (Bookings no dim)",
        "revenue",
        None,
        "sum",
        "Bookings",
        False,
        None,
    ),
]


def fmt_ms(s: float) -> str:
    return f"{s * 1000:7.1f}ms" if s < 1 else f"{s:6.2f}s "


def bar(v: float, w: int = 10) -> str:
    f = round(min(max(v, 0.0), 1.0) * w)
    return G + "▓" * f + D + "░" * (w - f) + X


def result_preview(result, agg: str, metric_col: str) -> str:
    if isinstance(result, int | float):
        return f"scalar={result:,.2f}"
    if isinstance(result, list) and result:
        top = result[:3]
        parts = [f"{r['group']}={r['value']:,.2f}" for r in top]
        tail = f"  +{len(result) - 3} more" if len(result) > 3 else ""
        return " | ".join(parts) + tail
    return "(empty)"


def run_benchmark():
    from apps.api_server.services.auto_planner import AutoPlanner

    print(f"\n{B}{'═' * W}{X}")
    print(f"{B}{C}  Decision Engine — 10-Question Cross-Reference Benchmark{X}")
    print(f"{B}{'═' * W}{X}")

    # ── Build knowledge ──────────────────────────────────────────────────────
    print(f"\n{B}[0] Loading sources + probing Mojo engines…{X}")
    t0 = time.perf_counter()

    planner = AutoPlanner(
        data_dir=ROOT / "test_files",
        mojo_binary=ROOT / "mojo_build" / "simulate",
    )
    planner.build_knowledge(
        source_map={
            "Bookings": "Bookings.csv",
            "Quotes": "Quotes_Combined_20241116.csv",
            "Inventory": "Available_Inventory.csv",
            "POS": "POS.csv",
        }
    )

    load_ms = (time.perf_counter() - t0) * 1000
    print(f"    engines : {C}{', '.join(planner.mojo_engines)}{X}")
    for src, rows in [(s, planner.tables[s]) for s in planner.tables]:
        cols = len(planner.graph.get(src, {}))
        print(f"    {src:<12}  {len(rows):>6,} rows  {cols:3d} cols")
    print(f"    {D}total load + probe: {load_ms:.0f}ms{X}")

    # ── Per-question results ─────────────────────────────────────────────────
    timings: list[dict] = []

    for (
        label,
        desc,
        metric_hint,
        dim_hint,
        agg,
        preferred,
        is_cross,
        expected_error,
    ) in QUESTIONS:
        print(f"\n{B}{'─' * W}{X}")
        cross_tag = f"  {Y}[cross-source]{X}" if is_cross else ""
        print(f"{B}{C}  {label}{X}  {desc}{cross_tag}")
        print(f"  {D}metric='{metric_hint}'  dim={dim_hint!r}  agg={agg}  pref={preferred}{X}")

        # ── Cold: plan ────────────────────────────────────────────────────────
        t_plan = time.perf_counter()
        plan = planner.plan(
            metric_hint=metric_hint,
            dim_hint=dim_hint,
            agg=agg,
            preferred_source=preferred,
        )
        plan_ms = time.perf_counter() - t_plan

        if plan.error:
            error_matches = expected_error is not None and expected_error in plan.error
            sym = f"{G}✓{X}" if error_matches else f"{R}✗{X}"
            qualifier = "expected reject" if error_matches else "plan error"
            print(f"  {sym} {qualifier}: {plan.error}{X}")
            timings.append(
                {
                    "label": label,
                    "ok": error_matches,
                    "expected_reject": bool(expected_error),
                    "cold_plan_ms": plan_ms * 1000,
                    "cold_exec_ms": 0.0,
                    "cold_total_ms": plan_ms * 1000,
                    "hot_total_ms": 0.0,
                    "speedup": 0.0,
                    "rows": 0,
                    "join": False,
                }
            )
            continue

        mojo_tag = f"  {D}mojo=[{' · '.join(plan.mojo_ops) or 'python'}]{X}"
        print(f"  {D}plan {X}{fmt_ms(plan_ms)}{mojo_tag}")

        # Metric + dim + join info
        print(
            f"  {D}  metric → {plan.metric_src}.{plan.metric_col}"
            f"  conf={plan.metric_conf:.3f}  role={plan.metric_role}{X}"
        )
        if plan.group_col:
            print(
                f"  {D}  dim    → {plan.group_src}.{plan.group_col}  conf={plan.group_conf:.3f}{X}"
            )
        if plan.join_key_metric:
            print(
                f"  {D}  join   → {plan.metric_src}.{plan.join_key_metric}"
                f" ↔ {plan.group_src}.{plan.join_key_group}"
                f"  conf={plan.join_conf:.3f}  card={plan.join_cardinality}{X}"
            )

        # ── Cold: execute ─────────────────────────────────────────────────────
        t_exec = time.perf_counter()
        result, row_count, trace = planner.execute_plan(plan, limit=10)
        exec_ms = time.perf_counter() - t_exec

        cold_total = plan_ms + exec_ms
        prev = result_preview(result, agg, plan.metric_col)
        print(f"  {D}exec {X}{fmt_ms(exec_ms)}  {D}{row_count} rows{X}")
        print(f"  {D}  → {prev}{X}")

        # ── Hot: repeat plan + execute ─────────────────────────────────────────
        hot_runs = 3
        hot_plan_total = 0.0
        hot_exec_total = 0.0
        for _ in range(hot_runs):
            t = time.perf_counter()
            planner.plan(
                metric_hint=metric_hint,
                dim_hint=dim_hint,
                agg=agg,
                preferred_source=preferred,
            )
            hot_plan_total += time.perf_counter() - t

            t = time.perf_counter()
            planner.execute_plan(plan, limit=10)
            hot_exec_total += time.perf_counter() - t

        hot_plan_ms = hot_plan_total / hot_runs
        hot_exec_ms = hot_exec_total / hot_runs
        hot_total = hot_plan_ms + hot_exec_ms
        speedup = cold_total / max(hot_total, 1e-6)

        ok = bool(result) or isinstance(result, int | float)
        sym = f"{G}✓{X}" if ok else f"{R}✗{X}"

        print(
            f"\n  {sym}  {B}{label}{X}  "
            f"cold={fmt_ms(cold_total).strip()}  "
            f"hot={fmt_ms(hot_total).strip()}  "
            f"speedup={speedup:.1f}×"
        )
        print(f"     {bar(plan.metric_conf)}  conf={plan.metric_conf:.3f}")

        timings.append(
            {
                "label": label,
                "ok": ok,
                "cold_plan_ms": plan_ms * 1000,
                "cold_exec_ms": exec_ms * 1000,
                "cold_total_ms": cold_total * 1000,
                "hot_total_ms": hot_total * 1000,
                "speedup": speedup,
                "rows": row_count,
                "mojo_ops": plan.mojo_ops,
                "join": bool(plan.join_key_metric),
            }
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    passed = sum(1 for t in timings if t.get("ok"))
    failed = len(timings) - passed
    joined = sum(1 for t in timings if t.get("join"))

    cold_times = [t["cold_total_ms"] for t in timings if "cold_total_ms" in t]
    hot_times = [t["hot_total_ms"] for t in timings if "hot_total_ms" in t]
    plan_times = [t["cold_plan_ms"] for t in timings if "cold_plan_ms" in t]
    exec_times = [t["cold_exec_ms"] for t in timings if "cold_exec_ms" in t]

    avg_cold = sum(cold_times) / len(cold_times) if cold_times else 0
    avg_hot = sum(hot_times) / len(hot_times) if hot_times else 0
    avg_plan = sum(plan_times) / len(plan_times) if plan_times else 0
    avg_exec = sum(exec_times) / len(exec_times) if exec_times else 0
    avg_spdup = avg_cold / max(avg_hot, 1e-6)

    print(f"\n{B}{'═' * W}{X}")
    print(f"{B}{C}  SUMMARY{X}")
    print(f"{B}{'═' * W}{X}")
    print(
        f"  Questions   : {len(timings)}   "
        f"{G}pass={passed}{X}   {R}fail={failed}{X}   "
        f"cross-join={joined}"
    )
    print(f"\n  Cold  avg   : {avg_cold:7.1f}ms   (plan={avg_plan:.1f}ms  exec={avg_exec:.1f}ms)")
    print(f"  Hot   avg   : {avg_hot:7.1f}ms   (3-run mean)")
    print(f"  Speedup     : {avg_spdup:6.1f}×   (cold→hot)")
    print("\n  Per-question breakdown:")
    print(
        f"  {'Label':<5}  {'Cold':>8}  {'Hot':>7}  {'Speedup':>8}  "
        f"{'Rows':>6}  {'Join?':>6}  Result"
    )
    print(f"  {'─' * 5}  {'─' * 8}  {'─' * 7}  {'─' * 8}  {'─' * 6}  {'─' * 6}  {'─' * 6}")
    for t in timings:
        if "cold_total_ms" not in t:
            print(f"  {t['label']:<5}  {'FAIL':>8}")
            continue
        jflag = f"{Y}yes{X}" if t["join"] else f"{D}no {X}"
        ok_s = f"{G}✓{X}" if t["ok"] else f"{R}✗{X}"
        print(
            f"  {t['label']:<5}  {t['cold_total_ms']:7.1f}ms  "
            f"{t['hot_total_ms']:6.1f}ms  "
            f"{t['speedup']:7.1f}×  "
            f"{t['rows']:6d}  "
            f"{jflag}     {ok_s}"
        )

    print(f"\n{B}{'═' * W}{X}\n")


if __name__ == "__main__":
    import logging

    logging.disable(logging.CRITICAL)
    run_benchmark()
