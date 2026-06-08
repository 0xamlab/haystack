#!/usr/bin/env python3
"""
benchmarks/test_live.py — Live Q&A test against real aerospace tables.

Calls the mapping pipeline directly (no HTTP, no auth overhead) and asks
real questions about the data:

  • What fields map between POS and Bookings?
  • What formulas exist in Bookings?
  • What join keys connect Quotes to Backlog?
  • How long does each stage take?

Run:
    python3 benchmarks/test_live.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
BINARY = ROOT / "mojo_build" / "simulate"
TEST_FILES = ROOT / "test_files"

sys.path.insert(0, str(ROOT))

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# ── Inline copies of the pipeline helpers (no FastAPI/auth needed) ────────────


def _load_csv(path: Path, max_rows: int = 1000) -> list[dict[str, Any]]:
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


def _profile(records: list[dict[str, Any]]) -> dict[str, dict]:
    if not records:
        return {}
    profile: dict[str, dict] = {}
    n = min(len(records), 1000)
    for field in records[0].keys():
        nums: list[float] = []
        strs: list[str] = []
        for rec in records[:n]:
            v = rec.get(field)
            if v is None:
                continue
            if isinstance(v, int | float):
                nums.append(float(v))
            else:
                strs.append(str(v))
        profile[field] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "unique_count": len({str(v) for v in (nums or strs)[:200]}),
            "total_count": len(nums) + len(strs),
            "sample_values": [str(v) for v in nums[:30]] + strs[:30],
        }
        if nums:
            nn = len(nums)
            mean = sum(nums) / nn
            profile[field]["mean"] = mean
            profile[field]["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(nn - 1, 1))
    return profile


def _call_mojo(payload: dict) -> tuple[dict | None, float]:
    raw = json.dumps(payload)
    t0 = time.perf_counter()
    try:
        r = subprocess.run(  # noqa: S603
            [str(BINARY)],
            input=raw.encode(),
            capture_output=True,
            timeout=60,
        )
        elapsed = time.perf_counter() - t0
        if r.returncode != 0:
            return None, elapsed
        return json.loads(r.stdout), elapsed
    except Exception:
        return None, time.perf_counter() - t0


# ── Parallel Mojo helpers (asyncio + run_in_executor) ────────────────────────


async def _mojo_async(payload: dict) -> tuple[dict | None, float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call_mojo, payload)


async def _mojo_gather(*payloads: dict) -> list[tuple[dict | None, float]]:
    return list(await asyncio.gather(*[_mojo_async(p) for p in payloads]))


# ── Formatting helpers ────────────────────────────────────────────────────────


def ms(s: float) -> str:
    return f"{s * 1000:.0f}ms" if s < 1 else f"{s:.2f}s"


def bar(v: float, w: int = 10) -> str:
    f = round(v * w)
    return "█" * f + "░" * (w - f)


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 72}{RESET}")


def answer(q: str, a: str, t: float = 0.0) -> None:
    timing = f"  {GREEN}{ms(t)}{RESET}" if t else ""
    print(f"\n  {BOLD}Q: {q}{RESET}")
    print(f"  {GREEN}A:{RESET} {a}{timing}")


def bullet(items: list[str], indent: int = 5) -> None:
    for item in items:
        print(" " * indent + f"• {item}")


# ── Main ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    if not BINARY.exists():
        print(f"{RED}Mojo binary not found: {BINARY}{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}  Decision Engine — Live Q&A Test (real aerospace data){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}")

    # ── Load tables ───────────────────────────────────────────────────────────
    section("Loading tables")
    tables: dict[str, list[dict]] = {}
    profiles: dict[str, dict] = {}
    t_load = time.perf_counter()

    sources = [
        ("POS", "POS.csv"),
        ("Bookings", "Bookings.csv"),
        ("Quotes", "Quotes_Combined_20241116.csv"),
        ("Backlog", "Backlog.csv"),
        ("Inventory", "Available_Inventory.csv"),
    ]

    for name, fname in sources:
        path = TEST_FILES / fname
        if not path.exists():
            print(f"  {YELLOW}SKIP{RESET} {fname}")
            continue
        t0 = time.perf_counter()
        records = _load_csv(path)
        prof = _profile(records)
        tables[name] = records
        profiles[name] = prof
        ncols = len(records[0]) if records else 0
        nnum = sum(1 for v in prof.values() if v["is_numeric"])
        print(
            f"  {BOLD}{name:<12}{RESET} {len(records):>5,} rows  "
            f"{ncols:>4} cols  {nnum:>3} numeric   "
            f"{GREEN}{ms(time.perf_counter() - t0)}{RESET}"
        )

    total_load = time.perf_counter() - t_load
    print(f"\n  {BOLD}Total load + profile:{RESET} {GREEN}{ms(total_load)}{RESET}")

    # ── Mojo column profiling (all sources in parallel) ───────────────────────
    section("Mojo semantic type detection (parallel)")
    mojo_profiles: dict[str, dict] = {}

    profiler_payloads = [
        {
            "engine_type": "column_profile",
            "columns": {
                field: {
                    "values": info["sample_values"][:30],
                    "strings": info["strings"][:20],
                    "sample_size": info["total_count"],
                }
                for field, info in profiles[name].items()
            },
        }
        for name in tables
    ]

    t0 = time.perf_counter()
    profiler_results = await _mojo_gather(*profiler_payloads)
    t_prof = time.perf_counter() - t0

    for name, (result, elapsed) in zip(tables.keys(), profiler_results, strict=False):
        if result and "profiles" in result:
            mojo_profiles[name] = result["profiles"]
            types: dict[str, int] = {}
            for fp in result["profiles"].values():
                t = fp.get("semantic_type", "?")
                types[t] = types.get(t, 0) + 1
            ts = "  ".join(f"{t}:{n}" for t, n in sorted(types.items()))
            print(f"  {BOLD}{name:<12}{RESET} {ts[:60]}  {DIM}{ms(elapsed)}{RESET}")
        else:
            print(f"  {RED}{name}: ERROR{RESET}")

    print(f"\n  {BOLD}Wall-clock (parallel):{RESET} {GREEN}{ms(t_prof)}{RESET}")

    # ── Q1: What fields map between POS and Bookings? ─────────────────────────
    section("Q&A — Column Mapping")

    def build_cols(name: str) -> list[dict]:
        prof = profiles[name]
        mp = mojo_profiles.get(name, {})
        return [
            {
                "name": f,
                "semantic_type": mp.get(f, {}).get(
                    "semantic_type",
                    "metric" if info["is_numeric"] else "category",
                ),
                "polarity": mp.get(f, {}).get("polarity", 0),
                "distribution": mp.get(f, {}).get("distribution", ""),
                "mean": info.get("mean", 0.0),
                "std": info.get("std", 0.0),
            }
            for f, info in prof.items()
        ]

    match_pairs = [
        ("POS", "Bookings"),
        ("Bookings", "Quotes"),
        ("POS", "Backlog"),
        ("Quotes", "Backlog"),
    ]

    match_payloads = [
        {
            "engine_type": "column_match",
            "source_a": a,
            "source_b": b,
            "columns_a": build_cols(a),
            "columns_b": build_cols(b),
            "min_confidence": 0.50,
        }
        for a, b in match_pairs
        if a in tables and b in tables
    ]

    t0 = time.perf_counter()
    match_results = await _mojo_gather(*match_payloads)
    t_match = time.perf_counter() - t0

    valid_pairs = [(a, b) for a, b in match_pairs if a in tables and b in tables]
    for (src_a, src_b), (result, elapsed) in zip(valid_pairs, match_results, strict=False):
        question = f"What fields map between {src_a} and {src_b}?"
        if not (result and "matches" in result):
            answer(question, f"{RED}Engine error{RESET}", elapsed)
            continue

        matches = result["matches"]
        strong = [m for m in matches if m["score"] >= 0.85]
        suggest = [m for m in matches if 0.60 <= m["score"] < 0.85]
        total_p = result.get("total_pairs", len(build_cols(src_a)) * len(build_cols(src_b)))

        summary = f"{len(strong)} strong + {len(suggest)} suggested  out of {total_p:,} pairs"
        answer(question, summary, elapsed)

        if strong:
            print(f"  {DIM}  Strong matches (≥0.85):{RESET}")
            for m in sorted(strong, key=lambda x: x["score"], reverse=True)[:6]:
                b_str = bar(m["score"])
                print(
                    f"    {DIM}{m['field_a']:<28} → {m['field_b']:<28} "
                    f"[{b_str}] {m['score']:.3f}{RESET}"
                )
        if suggest:
            print(f"  {DIM}  Suggested (0.60–0.85):{RESET}")
            for m in sorted(suggest, key=lambda x: x["score"], reverse=True)[:4]:
                b_str = bar(m["score"])
                print(
                    f"    {DIM}{m['field_a']:<28} → {m['field_b']:<28} "
                    f"[{b_str}] {m['score']:.3f}{RESET}"
                )

        print(
            f"\n  {BOLD}All {len(valid_pairs)} pairs wall-clock (parallel):{RESET} "
            f"{GREEN}{ms(t_match)}{RESET}"
        )

    # ── Q2: What join keys connect the tables? ────────────────────────────────
    section("Q&A — Join Keys")

    join_payloads = []
    join_pair_labels = []
    for src_a, src_b in valid_pairs:
        join_cols: dict[str, Any] = {}
        for src_n in (src_a, src_b):
            for field, info in profiles[src_n].items():
                all_vals = [str(v) for v in info["numeric"][:100]] + info["strings"][:100]
                ur = info["unique_count"] / max(info["total_count"], 1)
                join_cols[f"{src_n}.{field}"] = {
                    "values": all_vals[:200],
                    "unique_ratio": ur,
                    "sample_size": info["total_count"],
                }
        join_payloads.append(
            {
                "engine_type": "join_detect",
                "source_a": src_a,
                "source_b": src_b,
                "min_confidence": 0.4,
                "columns": join_cols,
            }
        )
        join_pair_labels.append((src_a, src_b))

    t0 = time.perf_counter()
    join_results = await _mojo_gather(*join_payloads)
    t_join = time.perf_counter() - t0

    for (src_a, src_b), (result, elapsed) in zip(join_pair_labels, join_results, strict=False):
        question = f"What join keys connect {src_a} ↔ {src_b}?"
        if not (result and "join_keys" in result):
            answer(question, "No keys detected", elapsed)
            continue
        keys = sorted(result["join_keys"], key=lambda x: x["confidence"], reverse=True)
        top = keys[:5]
        answer(question, f"{len(keys)} join key candidates  (top shown)", elapsed)
        for jk in top:
            print(
                f"    {DIM}{jk['field_a']:<30} ↔ {jk['field_b']:<30}"
                f"  conf={jk['confidence']:.3f}  cardinality={jk['cardinality']}{RESET}"
            )

    print(
        f"\n  {BOLD}All {len(join_pair_labels)} pairs wall-clock (parallel):{RESET} "
        f"{GREEN}{ms(t_join)}{RESET}"
    )

    # ── Q3: What formulas exist in each table? ────────────────────────────────
    section("Q&A — Derived Formulas (A×B≈C, A+B≈C)")

    rel_payloads = []
    rel_labels = []
    for name, records in tables.items():
        prof = profiles[name]
        num_fields = [f for f, info in prof.items() if info["is_numeric"]]
        if len(num_fields) < 3:
            continue
        n_sample = min(len(records), 500)
        cols: dict[str, list[float]] = {}
        for f in num_fields:
            vals: list[float] = []
            for idx in range(n_sample):
                v = records[idx].get(f, 0)
                try:
                    vals.append(float(v) if v else 0.0)
                except (TypeError, ValueError):
                    vals.append(0.0)
            cols[f] = vals
        rel_payloads.append(
            {
                "engine_type": "relation_detect",
                "source": name,
                "min_confidence": 0.70,
                "columns": cols,
            }
        )
        rel_labels.append(name)

    t0 = time.perf_counter()
    rel_results = await _mojo_gather(*rel_payloads)
    t_rel = time.perf_counter() - t0

    for name, (result, elapsed) in zip(rel_labels, rel_results, strict=False):
        question = f"What derived formulas exist in {name}?"
        if result is None:
            answer(question, f"{RED}Engine error{RESET}", elapsed)
            continue
        rels = result.get("relationships", [])
        triples = result.get("triples_tested", 0)
        evaled = result.get("triples_evaluated", triples)
        pct = f"{evaled / max(triples, 1) * 100:.0f}%"

        if not rels:
            answer(
                question,
                f"No formulas found  ({triples:,} triples, {pct} evaluated)",
                elapsed,
            )
        else:
            top = sorted(rels, key=lambda r: r["confidence"], reverse=True)
            answer(
                question, f"{len(rels)} formula(s)  ({triples:,} triples, {pct} evaluated)", elapsed
            )
            for r in top[:6]:
                conf_bar = bar(r["confidence"])
                print(f"    {DIM}{r['formula']:<55} [{conf_bar}] {r['confidence']:.3f}{RESET}")
            if len(rels) > 6:
                print(f"    {DIM}  … and {len(rels) - 6} more{RESET}")

    print(
        f"\n  {BOLD}All {len(rel_labels)} sources wall-clock (parallel):{RESET} "
        f"{GREEN}{ms(t_rel)}{RESET}"
    )

    # ── Q4: Spot questions ────────────────────────────────────────────────────
    section("Q&A — Spot Questions")

    # What numeric columns does Inventory have?
    if "Inventory" in profiles:
        num_cols = [f for f, info in profiles["Inventory"].items() if info["is_numeric"]]
        answer(
            "What numeric columns are in Inventory?",
            f"{len(num_cols)} numeric columns out of {len(profiles['Inventory'])} total",
        )
        bullet(num_cols[:12])
        if len(num_cols) > 12:
            print(f"     {DIM}… and {len(num_cols) - 12} more{RESET}")

    # What semantic types did Mojo find in Bookings?
    if "Bookings" in mojo_profiles:
        type_groups: dict[str, list[str]] = {}
        for field, fp in mojo_profiles["Bookings"].items():
            t = fp.get("semantic_type", "?")
            type_groups.setdefault(t, []).append(field)
        answer(
            "What semantic types did Mojo detect in Bookings?",
            f"{len(type_groups)} distinct types across {len(mojo_profiles['Bookings'])} fields",
        )
        for t, fields in sorted(type_groups.items()):
            print(
                f"    {DIM}{t:<15} {', '.join(fields[:5])}"
                f"{'  …+' + str(len(fields) - 5) if len(fields) > 5 else ''}{RESET}"
            )

    # What's the highest-confidence formula across all tables?
    if rel_results:
        all_rels: list[tuple[str, dict]] = []
        for name, (result, _) in zip(rel_labels, rel_results, strict=False):
            if result:
                for r in result.get("relationships", []):
                    all_rels.append((name, r))
        if all_rels:
            all_rels.sort(key=lambda x: x[1]["confidence"], reverse=True)
            best_src, best_r = all_rels[0]
            answer(
                "What is the highest-confidence derived formula?",
                f"[{best_src}]  {best_r['formula']}   conf={best_r['confidence']:.3f}",
            )

    # ── Grand summary ─────────────────────────────────────────────────────────
    section("Timing Summary")
    stages = [
        ("Load + profile (5 tables)", total_load),
        ("Mojo semantic typing (parallel)", t_prof),
        ("Column matching (parallel)", t_match),
        ("Join detection (parallel)", t_join),
        ("Relation detection (parallel)", t_rel),
    ]
    grand = sum(t for _, t in stages)
    mx = max(t for _, t in stages)
    for label, t in stages:
        pct = t / grand * 100
        b_str = bar(t / mx, 16)
        print(f"  {label:<38} {GREEN}{ms(t):>8}{RESET}  {DIM}{b_str}  {pct:.0f}%{RESET}")
    print(f"\n  {BOLD}Grand total:{RESET}  {GREEN}{BOLD}{ms(grand)}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
