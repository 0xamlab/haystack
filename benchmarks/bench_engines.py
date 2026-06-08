#!/usr/bin/env python3
"""
benchmarks/bench_engines.py — End-to-end timing for all Mojo data engines.

Tests: CSV load → column profile → column match → join detect → relation detect

Run:
    python3 benchmarks/bench_engines.py
    python3 benchmarks/bench_engines.py --no-cache   # force cold run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
BINARY = ROOT / "mojo_build" / "simulate"
TEST_FILES = ROOT / "test_files"
CACHE_DIR = ROOT / ".bench_cache"

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

SOURCES = [
    ("POS", "POS.csv"),
    ("Bookings", "Bookings.csv"),
    ("Quotes", "Quotes_Combined_20241116.csv"),
    ("Backlog", "Backlog.csv"),
    ("Inventory", "Available_Inventory.csv"),
]

# Rows to load for profiling/matching (500-1000 is plenty for statistics)
PROFILE_ROWS = 1000
# Rows to pass as sample values to Mojo engines
SAMPLE_ROWS = 500


# ── helpers ───────────────────────────────────────────────────────────────────


def ms(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.2f}s"


def bar(v: float, width: int = 12) -> str:
    filled = round(v * width)
    return "█" * filled + "░" * (width - filled)


def _file_fingerprint(path: Path) -> str:
    st = path.stat()
    return hashlib.sha256(f"{path}|{st.st_mtime}|{st.st_size}".encode()).hexdigest()[:12]


def _cache_path(name: str, fingerprint: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{name}_{fingerprint}.json"


def call_mojo(payload: dict[str, Any]) -> tuple[dict | None, float]:
    """Call Mojo binary with JSON payload. Returns (result, elapsed_seconds)."""
    raw = json.dumps(payload)
    t0 = time.perf_counter()
    try:
        result = subprocess.run(  # noqa: S603
            [str(BINARY)],
            input=raw.encode(),
            capture_output=True,
            timeout=60,
        )
        elapsed = time.perf_counter() - t0
        if result.returncode != 0:
            return None, elapsed
        return json.loads(result.stdout), elapsed
    except Exception:
        return None, time.perf_counter() - t0


def load_csv(path: Path, max_rows: int = PROFILE_ROWS) -> tuple[list[dict], float]:
    t0 = time.perf_counter()
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
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
    elapsed = time.perf_counter() - t0
    return rows, elapsed


def _load_csv_cached(name: str, path: Path, use_cache: bool) -> tuple[list[dict], float, bool]:
    """Load CSV, using JSON cache if available. Returns (records, elapsed, was_cached)."""
    fp = _file_fingerprint(path)
    cp = _cache_path(name, fp)
    if use_cache and cp.exists():
        t0 = time.perf_counter()
        with cp.open(encoding="utf-8") as f:
            records = json.load(f)
        return records, time.perf_counter() - t0, True

    records, elapsed = load_csv(path, max_rows=PROFILE_ROWS)
    if use_cache:
        with cp.open("w", encoding="utf-8") as f:
            json.dump(records, f)
    return records, elapsed, False


def profile_columns(records: list[dict], max_rows: int = PROFILE_ROWS) -> dict[str, dict]:
    """Extract numeric/string profiles per column."""
    if not records:
        return {}
    profile: dict[str, dict] = {}
    n = min(len(records), max_rows)

    for field in records[0].keys():
        all_nums: list[float] = []
        all_strs: list[str] = []
        for rec in records[:n]:
            v = rec.get(field)
            if v is None:
                continue
            if isinstance(v, int | float):
                all_nums.append(float(v))
            else:
                all_strs.append(str(v))

        profile[field] = {
            "numeric": all_nums,
            "strings": all_strs,
            "is_numeric": len(all_nums) > len(all_strs),
            "unique_count": len({str(v) for v in (all_nums or all_strs)[:200]}),
            "total_count": len(all_nums) + len(all_strs),
            "sample_values": [str(v) for v in all_nums[:SAMPLE_ROWS]] + all_strs[:SAMPLE_ROWS],
        }
        if all_nums:
            nn = len(all_nums)
            mean = sum(all_nums) / nn
            profile[field]["mean"] = mean
            profile[field]["std"] = math.sqrt(
                sum((x - mean) ** 2 for x in all_nums) / max(nn - 1, 1)
            )
    return profile


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 70}{RESET}")


def row_result(label: str, value: str, timing: str, extra: str = "") -> None:
    print(f"  {BOLD}{label:<22}{RESET} {value:<30} {GREEN}{timing:>10}{RESET}  {DIM}{extra}{RESET}")


# ── parallel Mojo caller ──────────────────────────────────────────────────────


def call_mojo_parallel(payloads: list[dict]) -> list[tuple[dict | None, float]]:
    """Run multiple Mojo calls concurrently via ThreadPoolExecutor."""
    results = [None] * len(payloads)
    with ThreadPoolExecutor(max_workers=min(len(payloads), os.cpu_count() or 4)) as ex:
        futures = {ex.submit(call_mojo, p): idx for idx, p in enumerate(payloads)}
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
    return results  # type: ignore[return-value]


# ── main benchmark ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force cold run, ignore JSON cache",
    )
    args = parser.parse_args()
    use_cache = not args.no_cache

    if not BINARY.exists():
        print(f"{RED}Mojo binary not found at {BINARY}{RESET}")
        print(
            "Build with: cd mojo_env && pixi run mojo build "
            "../mojo/engine/main.mojo -o ../mojo_build/simulate"
        )
        sys.exit(1)

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  Algenta Decision Engine — Full Pipeline Benchmark{RESET}")
    if use_cache:
        print(
            f"{DIM}  Cache: ON  (run with --no-cache to force cold)  Cache dir: {CACHE_DIR}{RESET}"
        )
    else:
        print(f"{YELLOW}  Cache: OFF (cold run){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    # ── Stage 1: Load all CSVs (parallel) ────────────────────────────────────
    section("Stage 1 · CSV Loading  [parallel + cache]")
    loaded: dict[str, tuple[list[dict], int]] = {}
    load_times: dict[str, float] = {}
    file_list = [
        (name, TEST_FILES / fname) for name, fname in SOURCES if (TEST_FILES / fname).exists()
    ]

    t_load_start = time.perf_counter()

    def _load_one(args_):
        name, path = args_
        records, elapsed, was_cached = _load_csv_cached(name, path, use_cache)
        return name, path, records, elapsed, was_cached

    with ThreadPoolExecutor(max_workers=len(file_list)) as ex:
        futures = list(ex.map(_load_one, file_list))

    total_load = time.perf_counter() - t_load_start
    for name, path, records, elapsed, was_cached in futures:
        size_mb = path.stat().st_size / 1_048_576
        ncols = len(records[0]) if records else 0
        loaded[name] = (records, ncols)
        load_times[name] = elapsed
        cache_tag = f"(cached {ms(elapsed)})" if was_cached else ""
        row_result(
            name,
            f"{len(records):,} rows × {ncols} cols",
            ms(elapsed),
            f"{size_mb:.1f} MB  {cache_tag}",
        )
    print(
        f"\n  {BOLD}Wall-clock total:{RESET} {GREEN}{ms(total_load)}{RESET}  {DIM}(parallel){RESET}"
    )

    # ── Stage 2: Column profiling (Python) ───────────────────────────────────
    section("Stage 2 · Column Profiling (Python)")
    profiles: dict[str, dict] = {}
    total_prof = 0.0
    for name, (records, ncols) in loaded.items():
        t0 = time.perf_counter()
        prof = profile_columns(records)
        elapsed = time.perf_counter() - t0
        total_prof += elapsed
        profiles[name] = prof
        num_numeric = sum(1 for v in prof.values() if v["is_numeric"])
        row_result(name, f"{num_numeric} numeric / {ncols} total cols", ms(elapsed))
    print(f"\n  {BOLD}Total profile time:{RESET} {GREEN}{ms(total_prof)}{RESET}")

    # ── Stage 3: Mojo column_profile (parallel) ──────────────────────────────
    section("Stage 3 · Mojo column_profile  [parallel]")
    payloads_prof = []
    order_prof = []
    for name, prof in profiles.items():
        cols_input = {
            field: {
                "values": info["sample_values"][:30],
                "strings": info["strings"][:20],
                "sample_size": info["total_count"],
            }
            for field, info in prof.items()
        }
        payloads_prof.append({"engine_type": "column_profile", "columns": cols_input})
        order_prof.append(name)

    t_mp_start = time.perf_counter()
    results_prof = call_mojo_parallel(payloads_prof)
    total_mp = time.perf_counter() - t_mp_start

    mojo_profiles: dict[str, dict] = {}
    for name, (result, elapsed) in zip(order_prof, results_prof, strict=False):
        if result and "profiles" in result:
            mojo_profiles[name] = result["profiles"]
            types: dict[str, int] = {}
            for fp in result["profiles"].values():
                t = fp.get("semantic_type", "?")
                types[t] = types.get(t, 0) + 1
            type_str = ", ".join(f"{t}:{n}" for t, n in sorted(types.items()))
            row_result(name, type_str[:45], ms(elapsed))
        else:
            row_result(name, f"{RED}ERROR{RESET}", ms(elapsed))

    print(
        f"\n  {BOLD}Wall-clock total:{RESET} {GREEN}{ms(total_mp)}{RESET}  "
        f"{DIM}(parallel, vs sequential Python: {ms(total_prof)}){RESET}"
    )

    # ── Stage 4: Mojo column_match (parallel) ─────────────────────────────────
    section("Stage 4 · Mojo column_match  [parallel, N×M + Hungarian]")
    pairs = [
        ("POS", "Bookings"),
        ("Bookings", "Quotes"),
        ("POS", "Backlog"),
        ("Bookings", "Backlog"),
    ]

    def build_cols(prof, mp):
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

    payloads_cm = []
    order_cm = []
    for src_a, src_b in pairs:
        if src_a not in profiles or src_b not in profiles:
            continue
        cols_a = build_cols(profiles[src_a], mojo_profiles.get(src_a, {}))
        cols_b = build_cols(profiles[src_b], mojo_profiles.get(src_b, {}))
        payloads_cm.append(
            {
                "engine_type": "column_match",
                "source_a": src_a,
                "source_b": src_b,
                "columns_a": cols_a,
                "columns_b": cols_b,
                "min_confidence": 0.5,
            }
        )
        order_cm.append((src_a, src_b, len(cols_a), len(cols_b)))

    t_cm_start = time.perf_counter()
    results_cm = call_mojo_parallel(payloads_cm)
    total_cm = time.perf_counter() - t_cm_start

    for (src_a, src_b, na, nb), (result, elapsed) in zip(order_cm, results_cm, strict=False):
        if result and "matches" in result:
            matches = result["matches"]
            total_pairs = result.get("total_pairs", na * nb)
            strong = [m for m in matches if m["score"] >= 0.85]
            row_result(
                f"{src_a} ↔ {src_b}",
                f"{len(matches)} matches / {total_pairs} pairs  ({len(strong)} strong)",
                ms(elapsed),
                f"{na}×{nb}",
            )
            for m in sorted(matches, key=lambda x: x["score"], reverse=True)[:4]:
                conf_bar = bar(m["score"])
                tier = (
                    "strong" if m["score"] >= 0.85 else "suggest" if m["score"] >= 0.60 else "weak"
                )
                print(
                    f"    {DIM}{m['field_a']:<25} -> {m['field_b']:<25} "
                    f"[{conf_bar}] {m['score']:.3f}  [{tier}]{RESET}"
                )
        else:
            row_result(f"{src_a} ↔ {src_b}", f"{RED}ERROR{RESET}", ms(elapsed))

    print(
        f"\n  {BOLD}Wall-clock total:{RESET} {GREEN}{ms(total_cm)}{RESET}  {DIM}(parallel){RESET}"
    )

    # ── Stage 5: Mojo join_detect (parallel) ──────────────────────────────────
    section("Stage 5 · Mojo join_detect  [parallel]")

    payloads_jd = []
    order_jd = []
    for src_a, src_b in pairs:
        if src_a not in profiles or src_b not in profiles:
            continue
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
        payloads_jd.append(
            {
                "engine_type": "join_detect",
                "source_a": src_a,
                "source_b": src_b,
                "min_confidence": 0.4,
                "columns": join_cols,
            }
        )
        order_jd.append((src_a, src_b))

    t_jd_start = time.perf_counter()
    results_jd = call_mojo_parallel(payloads_jd)
    total_jd = time.perf_counter() - t_jd_start

    for (src_a, src_b), (result, elapsed) in zip(order_jd, results_jd, strict=False):
        if result and "join_keys" in result:
            keys = result["join_keys"]
            row_result(
                f"{src_a} ↔ {src_b}",
                f"{len(keys)} join key(s) found",
                ms(elapsed),
            )
            for jk in sorted(keys, key=lambda x: x["confidence"], reverse=True)[:3]:
                print(
                    f"    {DIM}{jk['field_a']:<25} <-> {jk['field_b']:<25} "
                    f"conf={jk['confidence']:.3f}  card={jk['cardinality']}{RESET}"
                )
        else:
            row_result(f"{src_a} ↔ {src_b}", "0 keys", ms(elapsed))

    print(
        f"\n  {BOLD}Wall-clock total:{RESET} {GREEN}{ms(total_jd)}{RESET}  {DIM}(parallel){RESET}"
    )

    # ── Stage 6: Mojo relation_detect (parallel) ──────────────────────────────
    section("Stage 6 · Mojo relation_detect  [parallel + magnitude pre-filter]")

    payloads_rd = []
    order_rd = []
    for name, prof in profiles.items():
        numeric_fields = [f for f, info in prof.items() if info["is_numeric"]]
        if len(numeric_fields) < 3:
            continue
        records, _ = loaded[name]
        n_sample = min(len(records), SAMPLE_ROWS)
        cols: dict[str, list[float]] = {}
        for f in numeric_fields:
            vals: list[float] = []
            for idx in range(n_sample):
                v = records[idx].get(f, 0)
                try:
                    vals.append(float(v) if v else 0.0)
                except (TypeError, ValueError):
                    vals.append(0.0)
            cols[f] = vals
        payloads_rd.append(
            {
                "engine_type": "relation_detect",
                "source": name,
                "min_confidence": 0.70,
                "columns": cols,
            }
        )
        order_rd.append((name, len(numeric_fields)))

    t_rd_start = time.perf_counter()
    results_rd = call_mojo_parallel(payloads_rd)
    total_rd = time.perf_counter() - t_rd_start

    for (name, nnum), (result, elapsed) in zip(order_rd, results_rd, strict=False):
        if result is not None:
            rels = result.get("relationships", [])
            triples = result.get("triples_tested", 0)
            evaluated = result.get("triples_evaluated", triples)
            ncols = result.get("columns_scanned", nnum)
            pct = f"{evaluated / max(triples, 1) * 100:.0f}% evaluated" if triples > 0 else ""
            row_result(
                name,
                f"{len(rels)} formula(s)  {triples:,} triples",
                ms(elapsed),
                f"{ncols} cols · {pct}",
            )
            for r in rels[:4]:
                conf = r["confidence"]
                print(f"    {DIM}{r['formula']:<55} conf={conf:.3f}{RESET}")
        else:
            row_result(name, f"{RED}ERROR{RESET}", ms(elapsed))

    print(
        f"\n  {BOLD}Wall-clock total:{RESET} {GREEN}{ms(total_rd)}{RESET}  {DIM}(parallel){RESET}"
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    section("Pipeline Summary")
    stages = [
        ("CSV loading (wall)", total_load),
        ("Column profiling (Py)", total_prof),
        ("Mojo column_profile (wall)", total_mp),
        ("Mojo column_match (wall)", total_cm),
        ("Mojo join_detect (wall)", total_jd),
        ("Mojo relation_detect (wall)", total_rd),
    ]
    grand_total = sum(t for _, t in stages)
    max_t = max(t for _, t in stages)
    for label, t in stages:
        pct = t / grand_total * 100
        b = bar(t / max_t, 20)
        print(f"  {label:<32} {GREEN}{ms(t):>10}{RESET}  {DIM}{b}  {pct:.1f}%{RESET}")
    print(f"\n  {BOLD}Grand total (wall-clock):{RESET}  {GREEN}{BOLD}{ms(grand_total)}{RESET}")
    print()


if __name__ == "__main__":
    main()
