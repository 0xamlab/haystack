#!/usr/bin/env python3
"""
Generated-schema query benchmark.

This benchmark is intentionally schema-agnostic:
- sources are synthetic (`S0`, `S1`, `S2`, `S3`)
- columns use generic semantic aliases
- data is generated at runtime

It is a benchmark fixture for universal matching behavior, not a proof tied to any
industry dataset.
"""
from __future__ import annotations

import csv
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from apps.api_server.services.auto_planner import AutoPlanner

BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
RESET = "\033[0m"
W = 66

QUERIES = [
    ("Q1", "total value by local group", "total value", "local group", "sum", "S0"),
    ("Q2", "total value by segment", "total value", "segment", "sum", "S0"),
    ("Q3", "total value by region", "total value", "region", "sum", "S0"),
    ("Q4", "total value by country", "total value", "country", "sum", "S0"),
    ("Q5", "average unit rate by local group", "unit rate", "local group", "avg", "S0"),
    ("Q6", "average unit rate by segment", "unit rate", "segment", "avg", "S0"),
    ("Q7", "quantity by local group", "quantity", "local group", "sum", "S0"),
    ("Q8", "quantity by segment", "quantity", "segment", "sum", "S0"),
    ("Q9", "record count by country", "quantity", "country", "count", "S0"),
    ("Q10", "scalar total value", "total value", None, "sum", "S0"),
    ("Q11", "scalar quantity", "quantity", None, "sum", "S0"),
    ("Q12", "segment count", "quantity", "segment", "count", "S0"),
    ("Q13", "total value by bridge label", "total value", "bridge label", "sum", "S0"),
    ("Q14", "country count", "quantity", "country", "count", "S0"),
    # ── Cost-field ambiguity: UNIT_COST vs EXT_COST vs OH_COST ─────────────────
    # These queries stress typed disambiguation: the planner must pick the correct
    # column from three cost fields that are all numeric and similar in name.
    ("Q15", "avg unit cost (must prefer UNIT_COST)",      "unit cost",     "local group", "avg",   "C0"),
    ("Q16", "sum extended cost (must prefer EXT_COST)",   "extended cost", "local group", "sum",   "C0"),
    ("Q17", "sum overhead cost (must prefer OH_COST)",    "overhead cost", "local group", "sum",   "C0"),
    ("Q18", "total cost scalar (must prefer EXT_COST)",   "total cost",    None,          "sum",   "C0"),
    ("Q19", "unit cost by category",                      "unit cost",     "category",    "avg",   "C0"),
    ("Q20", "cost count by category",                     "cost",          "category",    "count", "C0"),
]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _generate_sources(tmp: Path) -> dict[str, str]:
    rng = random.Random(7)
    s0: list[dict[str, object]] = []
    s1: list[dict[str, object]] = []
    s2: list[dict[str, object]] = []
    s3: list[dict[str, object]] = []

    entity_map: dict[str, tuple[str, str]] = {}
    bridge_map: dict[str, tuple[str, str]] = {}
    region_map: dict[str, tuple[str, str]] = {}

    groups = ["g_a", "g_b", "g_c", "g_d"]
    segments = ["seg_1", "seg_2", "seg_3"]
    regions = [("region_east", "country_us"), ("region_west", "country_ca"), ("region_south", "country_mx")]

    for i in range(240):
        entity_key = f"e_{i:04d}"
        bridge_key = f"bridge_{i % 12:03d}"
        local_group = groups[i % len(groups)]
        qty = float((i % 9) + 1)
        unit_rate = round(10 + (i % 17) * 1.75, 2)
        measure_total = round(qty * unit_rate, 2)

        segment = segments[i % len(segments)]
        geo_key = f"geo_{i % 24:03d}"
        region, country = regions[i % len(regions)]
        entity_map[entity_key] = (segment, bridge_key)
        bridge_map.setdefault(bridge_key, (geo_key, f"label_{rng.randint(1, 4)}"))
        region_map[geo_key] = (region, country)

        s0.append({
            "entity_key": entity_key,
            "local_group": local_group,
            "quantity": qty,
            "unit_rate": unit_rate,
            "measure_total": measure_total,
        })

    for entity_key, (segment, bridge_key) in entity_map.items():
        s1.append({
            "entity_key": entity_key,
            "segment_label": segment,
            "bridge_key": bridge_key,
        })

    for geo_key, (region, country) in region_map.items():
        s2.append({"geo_key": geo_key, "region_label": region, "country_code": country})

    for bridge_key, (geo_key, bridge_label) in bridge_map.items():
        s3.append({"bridge_key": bridge_key, "geo_key": geo_key, "bridge_label": bridge_label})

    # C0: cost-field ambiguity source — three cost columns + a category dimension
    c0: list[dict[str, object]] = []
    cats = ["Alpha", "Beta", "Gamma", "Delta"]
    for i in range(200):
        qty_i      = float((i % 8) + 1)
        unit_cost  = round(5.0 + (i % 20) * 0.75, 2)
        oh_rate    = round(0.12 + (i % 5) * 0.02, 4)
        oh_cost    = round(unit_cost * oh_rate, 2)
        ext_cost   = round(unit_cost * qty_i, 2)
        c0.append({
            "item_id":    f"item_{i:04d}",
            "category":   cats[i % len(cats)],
            "qty":        qty_i,
            "UNIT_COST":  unit_cost,
            "OH_COST":    oh_cost,
            "EXT_COST":   ext_cost,
        })

    _write_csv(tmp / "S0.csv", s0)
    _write_csv(tmp / "S1.csv", s1)
    _write_csv(tmp / "S2.csv", s2)
    _write_csv(tmp / "S3.csv", s3)
    _write_csv(tmp / "C0.csv", c0)
    return {"S0": "S0.csv", "S1": "S1.csv", "S2": "S2.csv", "S3": "S3.csv", "C0": "C0.csv"}


def _preview(result) -> str:
    if isinstance(result, list):
        return f"rows={len(result)}"
    return f"scalar={result}"


def main() -> None:
    print(f"\n{BOLD}{'═'*W}{RESET}")
    print(f"{BOLD}{CYAN}  Generated-Schema Query Benchmark{RESET}")
    print(f"{BOLD}{'═'*W}{RESET}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        source_map = _generate_sources(tmp)
        planner = AutoPlanner(data_dir=tmp, max_rows=500)

        t0 = time.perf_counter()
        planner.build_knowledge(source_map=source_map)
        load_ms = (time.perf_counter() - t0) * 1000
        print(f"{DIM}load={load_ms:.1f}ms  sources={', '.join(source_map)}{RESET}")

        cold_total = 0.0
        hot_total = 0.0
        passed = 0
        failed = 0
        cache: dict[tuple[str, str | None, str, str], object] = {}

        for label, desc, metric_hint, dim_hint, agg, preferred in QUERIES:
            print(f"\n{BOLD}{label}{RESET}  {desc}")
            key = (metric_hint, dim_hint, agg, preferred)

            t1 = time.perf_counter()
            plan = planner.plan(metric_hint=metric_hint, dim_hint=dim_hint, agg=agg, preferred_source=preferred)
            result, row_count, _ = planner.execute_plan(plan, limit=10)
            elapsed = (time.perf_counter() - t1) * 1000
            cold_total += elapsed

            t2 = time.perf_counter()
            plan2 = planner.plan(metric_hint=metric_hint, dim_hint=dim_hint, agg=agg, preferred_source=preferred)
            result2, row_count2, _ = planner.execute_plan(plan2, limit=10)
            hot_elapsed = (time.perf_counter() - t2) * 1000
            hot_total += hot_elapsed

            ok = (row_count > 0 or isinstance(result, (int, float))) and plan.error is None
            if ok:
                passed += 1
                cache[key] = result2
                print(f"{GREEN}✓{RESET} cold={elapsed:.1f}ms hot={hot_elapsed:.1f}ms {_preview(result)}")
            else:
                failed += 1
                print(f"{RED}✗{RESET} cold={elapsed:.1f}ms hot={hot_elapsed:.1f}ms error={plan.error}")

        print(f"\n{BOLD}{'═'*W}{RESET}")
        print(f"{BOLD}  Generated benchmark summary{RESET}")
        print(f"{BOLD}{'═'*W}{RESET}")
        print(f"passed={passed} failed={failed} total={len(QUERIES)}")
        print(f"cold_total_ms={cold_total:.1f} hot_total_ms={hot_total:.1f}")


if __name__ == "__main__":
    main()
