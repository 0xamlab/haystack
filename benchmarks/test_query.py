#!/usr/bin/env python3
"""
benchmarks/test_query.py — Test the structured query engine.

Simulates what an LLM would send to POST /v1/query.
No natural language parsing — structured intent only.

Run:
    python3 benchmarks/test_query.py
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
BINARY = ROOT / "mojo_build" / "simulate"
TEST_FILES = ROOT / "test_files"

sys.path.insert(0, str(ROOT))

from apps.api_server.routers.query import (  # noqa: E402
    BASE_MEASURE,
    CATEGORY,
    COMPONENT,
    DERIVED_MEASURE,
    IDENTIFIER,
    METRIC,
    RATIO,
    TEXT,
    TIME,
    UNIT_MEASURE,
    SchemaGraph,
    build_schema_graph,
    execute,
    find_time_column,
    resolve_group_column,
    resolve_metric_column,
    time_range,
)

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


# ── Data loading ───────────────────────────────────────────────────────────────


def _load_csv(path: Path, max_rows: int = 2000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i >= max_rows:
                break
            rec: dict[str, Any] = {}
            for k, v in row.items():
                v = (v or "").strip()
                try:
                    rec[k] = int(v)
                except ValueError:
                    try:
                        rec[k] = float(v.replace(",", "").lstrip("$£€¥"))
                    except ValueError:
                        rec[k] = v
            rows.append(rec)
    return rows


def _profile(records: list[dict]) -> dict[str, dict]:
    if not records:
        return {}
    profile: dict[str, dict] = {}
    n = min(len(records), 500)
    for f in records[0].keys():
        nums: list[float] = []
        strs: list[str] = []
        for rec in records[:n]:
            v = rec.get(f)
            if v is None:
                continue
            if isinstance(v, int | float):
                nums.append(float(v))
            else:
                strs.append(str(v))
        mean = sum(nums) / len(nums) if nums else 0.0
        std = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1)) if nums else 0.0
        profile[f] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "sample_values": [str(v) for v in nums[:30]] + strs[:30],
            "unique_count": len({str(v) for v in (nums or strs)[:200]}),
            "total_count": len(nums) + len(strs),
            "mean": mean,
            "std": std,
        }
    return profile


def _call_mojo(payload: dict) -> dict | None:
    try:
        r = subprocess.run(  # noqa: S603
            [str(BINARY)],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=30,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        return None
    return None


def _mojo_profile(prof: dict) -> dict:
    result = _call_mojo(
        {
            "engine_type": "column_profile",
            "columns": {
                col: {
                    "values": info["sample_values"][:30],
                    "strings": info["strings"][:20],
                    "sample_size": info["total_count"],
                }
                for col, info in prof.items()
            },
        }
    )
    return (result or {}).get("profiles", {})


def _detect_relations(source: str, prof: dict) -> list[dict]:
    numeric_cols = {f: i for f, i in prof.items() if i.get("is_numeric") and i.get("numeric")}
    if len(numeric_cols) < 3:
        return []
    n = min(min(len(i["numeric"]) for i in numeric_cols.values()), 500)
    result = _call_mojo(
        {
            "engine_type": "relation_detect",
            "source": source,
            "min_confidence": 0.70,
            "columns": {c: i["numeric"][:n] for c, i in numeric_cols.items()},
        }
    )
    return (result or {}).get("relationships", [])


def ms(s: float) -> str:
    return f"{s * 1000:.0f}ms" if s < 1 else f"{s:.2f}s"


# ── Structured query runner ────────────────────────────────────────────────────
# Simulates what an LLM sends to POST /v1/query


class Engine:
    def __init__(self, tables: dict, graph: SchemaGraph, profiles: dict):
        self.tables = tables
        self.graph = graph
        self.profiles = profiles

    def query(
        self,
        *,
        # What an LLM would provide:
        metric_role: str = DERIVED_MEASURE,
        metric_hint: str = "",  # weak signal from user question
        aggregation: str = "sum",
        group_by: list[str] | None = None,
        time_filter: str | None = None,
        limit: int | None = None,
        order: str = "desc",
        source: str | None = None,
        label: str = "",
    ) -> None:
        t0 = time.perf_counter()
        hint_tokens = set(metric_hint.lower().split()) if metric_hint else set()

        src, col, conf, candidates = resolve_metric_column(
            metric_role, hint_tokens, self.graph, source
        )
        if not col:
            print(f"\n  {BOLD}Q:{RESET} {label or metric_role}")
            print(f"  {RED}No column found for role={metric_role}{RESET}")
            return

        node = self.graph[src][col]

        group_col: str | None = None
        if group_by:
            group_col, _ = resolve_group_column(group_by, src, self.graph)

        date_col: str | None = None
        tr = None
        if time_filter:
            date_col = find_time_column(src, self.graph)
            tr = time_range(time_filter)

        result, row_count, _ = execute(
            records=self.tables[src],
            metric_col=col,
            agg=aggregation,
            group_col=group_col,
            date_col=date_col,
            tr=tr,
            limit=limit,
            order=order,
        )
        elapsed = time.perf_counter() - t0

        q_label = label or f"{aggregation}({metric_role})"
        cols_note = f"`{col}` [{node.role}/{node.magnitude_class}]"
        if group_col:
            cols_note += f" by `{group_col}`"

        print(f"\n  {BOLD}Q:{RESET} {q_label}")
        print(f"  {DIM}[{src}  {cols_note}  conf={conf:.2f}  {row_count:,} rows]{RESET}")

        if isinstance(result, list):
            for item in result[:5]:
                g = item.get("group", "?")
                v = item.get("value", 0)
                v_fmt = (
                    f"${v:,.2f}" if node.role in (DERIVED_MEASURE, UNIT_MEASURE) else f"{v:,.2f}"
                )
                print(f"  {GREEN}  {g:<32} {v_fmt}{RESET}")
            if len(result) > 5:
                print(f"  {DIM}  … and {len(result) - 5} more{RESET}")
        elif result is None:
            print(f"  {YELLOW}A: No data{RESET}  {DIM}{ms(elapsed)}{RESET}")
        else:
            v = result
            v_fmt = (
                f"${v:,.2f}"
                if isinstance(v, float) and node.role in (DERIVED_MEASURE, UNIT_MEASURE)
                else str(v)
            )
            if isinstance(v, float) and abs(v) >= 1_000_000:
                v_fmt = f"${v / 1_000_000:.2f}M"
            print(f"  {GREEN}A:{RESET} {v_fmt}  {GREEN}{ms(elapsed)}{RESET}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    if not BINARY.exists():
        print(f"{RED}Binary not found: {BINARY}{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}  Algenta Structured Query Engine — Direct API Simulation{RESET}")
    print(f"{BOLD}  (What an LLM sends to POST /v1/query){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}")

    # ── Load ──────────────────────────────────────────────────────────────────
    sources = [
        ("Bookings", "Bookings.csv"),
        ("POS", "POS.csv"),
        ("Backlog", "Backlog.csv"),
        ("Quotes", "Quotes_Combined_20241116.csv"),
        ("Inventory", "Available_Inventory.csv"),
    ]
    print(f"\n{DIM}Loading…{RESET}", end="", flush=True)
    t0 = time.perf_counter()
    tables: dict[str, list[dict]] = {}
    profiles: dict[str, dict] = {}
    for name, fname in sources:
        p = TEST_FILES / fname
        if p.exists():
            recs = _load_csv(p)
            tables[name] = recs
            profiles[name] = _profile(recs)
    print(
        f" {GREEN}{len(tables)} tables, {sum(len(v) for v in tables.values()):,} rows{RESET}  "
        f"({ms(time.perf_counter() - t0)})"
    )

    # ── Mojo (parallel) ───────────────────────────────────────────────────────
    print(f"{DIM}Mojo profile + relation detect…{RESET}", end="", flush=True)
    t1 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(tables) * 2) as ex:
        mp_futs = list(ex.map(lambda a: (a[0], _mojo_profile(a[1])), profiles.items()))
        rel_futs = list(ex.map(lambda a: (a[0], _detect_relations(*a)), profiles.items()))
    mojo_profiles = dict(mp_futs)
    relations_by_source = dict(rel_futs)
    print(f" {GREEN}done{RESET}  ({ms(time.perf_counter() - t1)})")

    # ── Schema graph ──────────────────────────────────────────────────────────
    graph = build_schema_graph(profiles, mojo_profiles, relations_by_source)

    # ── Print formulas detected ───────────────────────────────────────────────
    print(f"\n{BOLD}  Formulas detected (engine's ground truth):{RESET}")
    for src, rels in relations_by_source.items():
        if rels:
            top = rels[:3]
            print(
                f"  {DIM}{src}:{RESET} "
                + "  |  ".join(
                    f"{GREEN}{r['formula']}{RESET} conf={r['confidence']:.2f}" for r in top
                )
                + (f"  {DIM}+{len(rels) - 3} more{RESET}" if len(rels) > 3 else "")
            )

    # ── Schema summary ────────────────────────────────────────────────────────
    print(f"\n{BOLD}  Role assignments (Bookings):{RESET}")
    bk = graph.get("Bookings", {})
    role_groups: dict[str, list[str]] = {}
    for col, node in bk.items():
        role_groups.setdefault(node.role, []).append(col)
    colors = {
        DERIVED_MEASURE: GREEN,
        BASE_MEASURE: CYAN,
        UNIT_MEASURE: YELLOW,
        COMPONENT: CYAN,
        RATIO: YELLOW,
        IDENTIFIER: DIM,
        TIME: DIM,
        CATEGORY: DIM,
        TEXT: DIM,
        METRIC: RESET,
    }
    for role in [DERIVED_MEASURE, BASE_MEASURE, UNIT_MEASURE, RATIO, IDENTIFIER, TIME, CATEGORY]:
        cols = role_groups.get(role, [])
        if cols:
            c = colors.get(role, RESET)
            print(f"  {c}  {role:<18} {', '.join(cols[:6])}{'  …' if len(cols) > 6 else ''}{RESET}")

    # ── Role verification ─────────────────────────────────────────────────────
    print(f"\n{BOLD}  Verification — known ground truth:{RESET}")
    checks = [
        ("Bookings", "EXT_PRICE", DERIVED_MEASURE, "EXT_PRICE = QUANTITY × UNIT_PRICE"),
        ("Bookings", "QUANTITY", BASE_MEASURE, "discrete count factor"),
        ("Bookings", "UNIT_PRICE", UNIT_MEASURE, "rate/price factor"),
    ]
    for src, col, expected, note in checks:
        node = graph.get(src, {}).get(col)
        ok = node is not None and node.role == expected
        color = GREEN if ok else RED
        status = "OK  " if ok else "FAIL"
        actual = node.role if node else "NOT FOUND"
        print(f"  {color}  {status}  {src}.{col:<20} role={actual:<20}  ({note}){RESET}")

    # ── Queries ───────────────────────────────────────────────────────────────
    eng = Engine(tables, graph, profiles)

    print(f"\n{BOLD}{CYAN}{'─' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  Basic aggregations  (LLM → structured intent → engine){RESET}")
    print(f"{BOLD}{CYAN}{'─' * 72}{RESET}")

    # User: "total revenue" → LLM sends: metric.role=derived_measure, agg=sum
    eng.query(
        metric_role=DERIVED_MEASURE,
        aggregation="sum",
        source="Bookings",
        label="total revenue  [LLM: metric.role=derived_measure, agg=sum]",
    )

    # User: "average unit price" → LLM sends: metric.role=unit_measure, agg=avg
    eng.query(
        metric_role=UNIT_MEASURE,
        aggregation="avg",
        source="Bookings",
        label="average unit price  [LLM: metric.role=unit_measure, agg=avg]",
    )

    # User: "total quantity ordered" → LLM sends: metric.role=base_measure, agg=sum
    eng.query(
        metric_role=BASE_MEASURE,
        aggregation="sum",
        source="Bookings",
        label="total quantity  [LLM: metric.role=base_measure, agg=sum]",
    )

    # User: "highest price" → LLM sends: metric.role=unit_measure, agg=max
    eng.query(
        metric_role=UNIT_MEASURE,
        aggregation="max",
        source="Bookings",
        label="max price  [LLM: metric.role=unit_measure, agg=max]",
    )

    # User: "how many orders" → LLM sends: metric.role=derived_measure, agg=count
    eng.query(
        metric_role=DERIVED_MEASURE,
        aggregation="count",
        source="Bookings",
        label="count orders  [LLM: agg=count]",
    )

    print(f"\n{BOLD}{CYAN}{'─' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  Group-by  (LLM adds group_by=['customer']){RESET}")
    print(f"{BOLD}{CYAN}{'─' * 72}{RESET}")

    eng.query(
        metric_role=DERIVED_MEASURE,
        aggregation="sum",
        group_by=["customer"],
        source="Bookings",
        label="total revenue by customer",
    )

    eng.query(
        metric_role=BASE_MEASURE,
        aggregation="sum",
        group_by=["customer"],
        source="Bookings",
        label="total quantity by customer",
    )

    eng.query(
        metric_role=UNIT_MEASURE,
        aggregation="avg",
        group_by=["customer"],
        source="Bookings",
        label="average price by customer",
    )

    print(f"\n{BOLD}{CYAN}{'─' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  Top-N  (LLM adds limit=5){RESET}")
    print(f"{BOLD}{CYAN}{'─' * 72}{RESET}")

    eng.query(
        metric_role=DERIVED_MEASURE,
        aggregation="sum",
        group_by=["customer"],
        limit=5,
        source="Bookings",
        label="top 5 customers by revenue",
    )

    eng.query(
        metric_role=BASE_MEASURE,
        aggregation="sum",
        group_by=["part"],
        limit=5,
        source="Bookings",
        label="top 5 parts by quantity",
    )

    eng.query(
        metric_role=DERIVED_MEASURE,
        aggregation="sum",
        group_by=["customer"],
        limit=10,
        source="POS",
        label="top 10 customers by revenue  [POS]",
    )

    print(f"\n{BOLD}{CYAN}{'─' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  Cross-source  (LLM omits source — engine picks best){RESET}")
    print(f"{BOLD}{CYAN}{'─' * 72}{RESET}")

    eng.query(
        metric_role=DERIVED_MEASURE, aggregation="sum", label="total revenue  [auto-select source]"
    )

    eng.query(
        metric_role=DERIVED_MEASURE,
        aggregation="sum",
        group_by=["customer"],
        limit=5,
        label="top 5 customers by revenue  [auto-select source]",
    )

    print(f"\n{BOLD}{CYAN}{'─' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  Candidates list  (what LLM sees for disambiguation){RESET}")
    print(f"{BOLD}{CYAN}{'─' * 72}{RESET}")

    _, _, _, candidates = resolve_metric_column(DERIVED_MEASURE, set(), graph)
    print(f"\n  {BOLD}Candidates for role=derived_measure (all sources):{RESET}")
    for c in candidates[:8]:
        formula_note = f"  ← {c['formula']}" if c.get("formula") else ""
        print(
            f"  {DIM}{c['confidence']:.2f}  {c['source']:<12} {c['column']:<20} "
            f"[{c['magnitude']}]{formula_note}{RESET}"
        )

    print()


if __name__ == "__main__":
    main()
