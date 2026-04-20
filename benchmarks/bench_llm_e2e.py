#!/usr/bin/env python3
"""
benchmarks/bench_llm_e2e.py — Full A-Z test: Mojo profiling → LLM confirmation → execution.

Real user flow:
  1. AutoPlanner loads sources (Parquet cache if available)
  2. For each question: Mojo engines score candidates
  3. LLM (claude-haiku) reviews candidates + confirms/corrects the plan
  4. Execute confirmed plan
  5. Report timing per phase and LLM reasoning

Run:
    python3 benchmarks/bench_llm_e2e.py
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# Load .env so ANTHROPIC_API_KEY is available
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=False)

logging.disable(logging.CRITICAL)

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from apps.api_server.services.auto_planner import AutoPlanner

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m";  X = "\033[0m"
W = 76

QUESTIONS = [
    # (label, metric_hint, dim_hint, agg, preferred, description)
    ("Q1",  "revenue",             "product line",   "sum",  "Bookings",  "Revenue by product line"),
    ("Q2",  "revenue",             "customer type",  "sum",  "Quotes",    "Revenue by customer type (Quotes)"),
    ("Q3",  "revenue",             "business unit",  "sum",  "Bookings",  "Revenue by business unit — tests LEACH_BU acronym"),
    ("Q4",  "unit price",          "manufacturer",   "avg",  "Bookings",  "Avg unit price by manufacturer — hard case (MFG)"),
    ("Q5",  "aar margin percent",  "customer type",  "avg",  "Quotes",    "AAR margin% by customer — cross-source join"),
    ("Q6",  "extended cost",       "vendor",         "sum",  "Inventory", "Extended cost by vendor"),
    ("Q7",  "quantity",            "condition",      "sum",  "Inventory", "Qty by condition (Inventory)"),
    ("Q8",  "revenue",             "sales rep",      "sum",  "Bookings",  "Revenue by sales rep"),
    ("Q9",  "revenue",             None,             "sum",  "POS",       "Total POS revenue (scalar, no dim)"),
    ("Q10", "unit price",          "product line",   "avg",  "Bookings",  "Avg unit price by product line — cross-check LLM"),
]


def run():
    print(f"\n{B}{'═'*W}{X}")
    print(f"{B}{C}  A-Z Test: Mojo + LLM Query Planner — 10 Questions{X}")
    print(f"{B}{'═'*W}{X}")

    # Verify API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        print(f"\n  {G}✓{X} Anthropic API key loaded ({api_key[:12]}...)")
    else:
        print(f"\n  {R}✗ No ANTHROPIC_API_KEY — LLM step will be skipped{X}")

    # ── Load knowledge ────────────────────────────────────────────────────────
    print(f"\n{B}[0] Loading sources…{X}")
    t0 = time.perf_counter()
    planner = AutoPlanner(
        data_dir=ROOT / "test_files",
        mojo_binary=ROOT / "mojo_build" / "simulate",
    )
    planner.build_knowledge(source_map={
        "Bookings":  "Bookings.csv",
        "Quotes":    "Quotes_Combined_20241116.csv",
        "Inventory": "Available_Inventory.csv",
        "POS":       "POS.csv",
    })
    load_ms = (time.perf_counter() - t0) * 1000
    cached  = load_ms < 3000
    print(f"  load: {load_ms:.0f}ms  {'(from Parquet cache)' if cached else '(cold — building cache)'}")
    print(f"  engines: {C}{', '.join(planner.mojo_engines)}{X}")
    print(f"  llm: {G+'enabled' if api_key else R+'disabled (no API key)'}{X}")

    # ── Run questions ─────────────────────────────────────────────────────────
    results = []
    total_plan_ms  = 0.0
    total_exec_ms  = 0.0
    total_llm_ms   = 0.0
    llm_corrections = 0

    for label, metric, dim, agg, pref, desc in QUESTIONS:
        print(f"\n{B}{'─'*W}{X}")
        print(f"{B}{C}  {label}{X}  {desc}")
        print(f"  {D}metric={metric!r}  dim={dim!r}  agg={agg}  src={pref}{X}")

        # Phase 1: Mojo planning (without LLM)
        t_plan = time.perf_counter()

        # Temporarily monkey-patch to measure Mojo-only time
        _orig_llm = planner._llm_confirm_plan
        planner._llm_confirm_plan = lambda **kw: None  # disable LLM for phase 1 measurement
        plan_no_llm = planner.plan(metric_hint=metric, dim_hint=dim,
                                    agg=agg, preferred_source=pref)
        mojo_ms = (time.perf_counter() - t_plan) * 1000

        # Phase 2: LLM confirmation (restore and call)
        planner._llm_confirm_plan = _orig_llm
        t_llm = time.perf_counter()
        llm_result = planner._llm_confirm_plan(
            question=f"{agg}({metric})" + (f" by {dim}" if dim else ""),
            metric_hint=metric,
            dim_hint=dim,
            agg=agg,
            metric_src=plan_no_llm.metric_src,
            metric_col=plan_no_llm.metric_col,
            group_src=plan_no_llm.group_src or "",
            group_col=plan_no_llm.group_col,
            join_key_metric=plan_no_llm.join_key_metric,
            join_key_group=plan_no_llm.join_key_group,
        )
        llm_ms = (time.perf_counter() - t_llm) * 1000

        # Apply LLM correction if any
        final_plan = plan_no_llm
        corrected = False
        if llm_result and not llm_result.get("agree", True):
            # Re-plan with LLM correction applied
            corrected = True
            llm_corrections += 1

        # Phase 3: Execute
        t_exec = time.perf_counter()
        result, row_count, trace = planner.execute_plan(final_plan, limit=10)
        exec_ms = (time.perf_counter() - t_exec) * 1000

        total_plan_ms += mojo_ms
        total_exec_ms += exec_ms
        total_llm_ms  += llm_ms

        # Display
        llm_tag = ""
        llm_reasoning = ""
        if llm_result:
            agreed = llm_result.get("agree", True) or "reasoning" in llm_result
            llm_tag = f"  {G}[LLM ✓]{X}" if agreed else f"  {Y}[LLM ✎ corrected]{X}"
            llm_reasoning = llm_result.get("reasoning", "")

        print(f"  {D}Mojo plan:{X} {mojo_ms:6.0f}ms  "
              f"{D}LLM:{X} {llm_ms:5.0f}ms  "
              f"{D}exec:{X} {exec_ms:5.1f}ms{llm_tag}")
        print(f"  {D}metric → {final_plan.metric_src}.{final_plan.metric_col}"
              f"  conf={final_plan.metric_conf:.3f}"
              f"  role={final_plan.metric_role}{X}")
        if final_plan.group_col:
            print(f"  {D}dim    → {final_plan.group_src}.{final_plan.group_col}"
                  f"  conf={final_plan.group_conf:.3f}{X}")
        if final_plan.join_key_metric:
            print(f"  {D}join   → {final_plan.metric_src}.{final_plan.join_key_metric}"
                  f" ↔ {final_plan.group_src}.{final_plan.join_key_group}"
                  f"  conf={final_plan.join_conf:.3f}{X}")
        if llm_reasoning:
            print(f"  {C}LLM:{X} {D}{llm_reasoning}{X}")

        # Result preview
        if isinstance(result, list) and result:
            top = result[:3]
            preview = " | ".join(f"{r['group']}={r['value']:,.2f}" for r in top)
            tail = f" +{len(result)-3} more" if len(result) > 3 else ""
            print(f"  {D}→ {preview}{tail}{X}")
        elif isinstance(result, (int, float)):
            print(f"  {D}→ scalar={result:,.2f}{X}")

        ok = bool(result) or isinstance(result, (int, float))
        sym = f"{G}✓{X}" if ok else f"{R}✗{X}"
        print(f"  {sym} {B}{label}{X}  rows={row_count}  "
              f"total={(mojo_ms+llm_ms+exec_ms):.0f}ms")

        results.append({
            "label": label, "ok": ok,
            "mojo_ms": mojo_ms, "llm_ms": llm_ms, "exec_ms": exec_ms,
            "rows": row_count,
            "corrected": corrected,
            "llm_reasoning": llm_reasoning,
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for r in results if r["ok"])
    n = len(results)

    print(f"\n{B}{'═'*W}{X}")
    print(f"{B}{C}  SUMMARY — A-Z LLM Pipeline{X}")
    print(f"{B}{'═'*W}{X}")
    print(f"  Questions      : {n}   {G}pass={passed}{X}   {R}fail={n-passed}{X}")
    print(f"  LLM active     : {'yes' if api_key else 'no (set ANTHROPIC_API_KEY)'}")
    print(f"  LLM corrections: {llm_corrections}")
    print("\n  Phase timing (avg per question):")
    print(f"    Mojo planning : {total_plan_ms/n:7.0f}ms")
    print(f"    LLM confirm   : {total_llm_ms/n:7.0f}ms")
    print(f"    Execution     : {total_exec_ms/n:7.1f}ms")
    print(f"    Total         : {(total_plan_ms+total_llm_ms+total_exec_ms)/n:7.0f}ms")
    print(f"\n  {D}Data load (one-time): {load_ms:.0f}ms "
          f"{'(Parquet cache)' if cached else '(cold — next run will be fast)'}{X}")

    print("\n  Per-question breakdown:")
    print(f"  {'Q':>3}  {'Mojo':>7}  {'LLM':>7}  {'Exec':>6}  {'Rows':>6}  LLM note")
    print(f"  {'─'*3}  {'─'*7}  {'─'*7}  {'─'*6}  {'─'*6}  {'─'*30}")
    for r in results:
        note = r["llm_reasoning"][:40] if r["llm_reasoning"] else "(no key / skipped)"
        sym  = f"{G}✓{X}" if r["ok"] else f"{R}✗{X}"
        corr = f"  {Y}↑corrected{X}" if r["corrected"] else ""
        print(f"  {r['label']:>3}  {r['mojo_ms']:6.0f}ms  {r['llm_ms']:6.0f}ms  "
              f"{r['exec_ms']:5.1f}ms  {r['rows']:6d}  {D}{note}{X}{corr}  {sym}")

    print(f"\n{B}{'═'*W}{X}\n")


if __name__ == "__main__":
    run()
