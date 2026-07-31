#!/usr/bin/env python3
"""Fit pit_loss and sigma_pit per circuit across the corpus, from the reconciled sources.

Inclusion rule established by scripts/timing/reconcile_pitstops.py:
  pit_loss  <- PitLaneTimeCollection  (total pit-lane time; the complete set of entries)
  sigma_pit <- PitStop                (stationary time; the subset with that measurement)

Those are two different measurements from two feeds, not a lossy subset of one another. PitStop exists
only from 2025, so stationary time is a 2025+ quantity while lane time spans 2019+.

Neutralised stops are separated out rather than pooled: pit loss under a safety car is discounted
because the field is already slow, and the reference parameterisation prices that with a multiplier. A
pooled fit would blend two different regimes and understate the green-flag cost.

Statistics run in Mojo (stats_bootstrap for intervals); Python selects rows and prints.

Usage:
    python3 scripts/timing/fit_pit_loss.py
    python3 scripts/timing/fit_pit_loss.py --min-n 8 --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq


FROZEN_TEST_SEASON = 2025


def circuit_of(session_dir: Path) -> str:
    """Circuit name from the session path, stable across seasons."""
    name = session_dir.parent.name
    m = re.match(r"\d{4}-\d{2}-\d{2}_(.+)", name)
    return (m.group(1) if m else name).replace("_", " ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--min-n", type=int, default=6)
    ap.add_argument("--json", default="")
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024",
                    help="development seasons. 2025 is the frozen final test: a parameter or a model "
                         "FORM chosen with its help is the test helping select the system")
    args = ap.parse_args()
    if FROZEN_TEST_SEASON in {int(x) for x in str(args.seasons).split(",") if x.strip().isdigit()}:
        print(f"refusing: {FROZEN_TEST_SEASON} is the frozen final test season", file=sys.stderr)
        return 2
    want = {int(x) for x in str(args.seasons).split(",") if x.strip().isdigit()}
    root = Path(args.root).expanduser()

    # Plausibility window for a SERVICE pit-lane transit. Beyond it the record is not a tyre stop:
    # red-flag periods park the whole field in the pit lane for minutes, and a car retiring in the lane
    # accumulates the same way -- Duration then arrives as mm:ss and parses to values like 4754 s (79
    # minutes). Medians survive that, but p90, max and any mean do not, and sigma_pit is fitted from a
    # tail. So excluded explicitly and counted, rather than trusting a robust statistic to hide it.
    LANE_MIN, LANE_MAX = 12.0, 60.0
    STAT_MIN, STAT_MAX = 1.0, 30.0

    lane: dict[str, list[float]] = defaultdict(list)
    lane_neut: dict[str, list[float]] = defaultdict(list)
    stat: dict[str, list[float]] = defaultdict(list)
    seasons: dict[str, set[int]] = defaultdict(set)
    n_sessions = 0
    excluded = {"lane_long": 0, "lane_short": 0, "stat_out": 0}

    for p in sorted(root.rglob("_pit_events.parquet")):
        t = pq.read_table(p).to_pydict()
        rows = [dict(zip(t.keys(), v)) for v in zip(*t.values())]
        if not rows:
            continue
        circ = circuit_of(p.parent)
        # The filter has to be applied per ROW, not per file: a session directory carries its season in
        # the rows, and without this the artifact spanned 2019-2026 including the frozen test season.
        rows = [r for r in rows if int(r["season"]) in want]
        if not rows:
            continue
        n_sessions += 1
        for r in rows:
            seasons[circ].add(r["season"])
            if r["provider"] == "official_pitlane" and r["pit_lane_s"]:
                v = float(r["pit_lane_s"])
                if v > LANE_MAX:
                    excluded["lane_long"] += 1
                elif v < LANE_MIN:
                    excluded["lane_short"] += 1
                else:
                    (lane_neut if r["under_neutralisation"] else lane)[circ].append(v)
            elif r["provider"] == "official_pitstop" and r["stationary_s"]:
                v = float(r["stationary_s"])
                if not (STAT_MIN <= v <= STAT_MAX):
                    excluded["stat_out"] += 1
                elif not r["under_neutralisation"]:
                    stat[circ].append(v)

    def q(xs: list[float], f: float) -> float:
        s = sorted(xs)
        return s[min(int(f * len(s)), len(s) - 1)]

    tot_lane = sum(len(v) for v in lane.values()) + sum(len(v) for v in lane_neut.values())
    print(f"{n_sessions} sessions, {len(lane)} circuits, {tot_lane} usable lane times", file=sys.stderr)
    print(f"excluded: {excluded['lane_long']} lane > {LANE_MAX:.0f}s (red flag / pit-lane retirement), "
          f"{excluded['lane_short']} lane < {LANE_MIN:.0f}s, {excluded['stat_out']} stationary "
          f"outside [{STAT_MIN:.0f},{STAT_MAX:.0f}]s\n", file=sys.stderr)
    print(f"{'circuit':<30}{'seasons':>8}{'n':>5}{'p10':>7}{'median':>8}{'p90':>7}"
          f"{'max':>7}   {'neut n':>7}{'neut med':>9}")
    out: dict[str, dict] = {}
    for circ in sorted(lane, key=lambda c: -len(lane[c])):
        xs = lane[circ]
        if len(xs) < args.min_n:
            continue
        nx = lane_neut.get(circ, [])
        row = {
            "seasons": sorted(seasons[circ]),
            "pit_loss_n": len(xs),
            "pit_loss_p10": round(q(xs, 0.10), 3),
            "pit_loss_median": round(q(xs, 0.50), 3),
            "pit_loss_p90": round(q(xs, 0.90), 3),
            "pit_loss_max": round(max(xs), 3),
            "neutralised_n": len(nx),
            "neutralised_median": round(q(nx, 0.50), 3) if nx else None,
        }
        if nx and len(nx) >= 3:
            row["sc_pit_factor_observed"] = round(q(nx, 0.50) / q(xs, 0.50), 3)
        out[circ] = row
        nm = f"{row['neutralised_median']:.2f}" if row["neutralised_median"] else "—"
        print(f"{circ[:30]:<30}{len(seasons[circ]):>8}{len(xs):>5}{row['pit_loss_p10']:>7.2f}"
              f"{row['pit_loss_median']:>8.2f}{row['pit_loss_p90']:>7.2f}{row['pit_loss_max']:>7.2f}"
              f"   {len(nx):>7}{nm:>9}")

    all_lane = [x for xs in lane.values() for x in xs]
    all_neut = [x for xs in lane_neut.values() for x in xs]
    all_stat = [x for xs in stat.values() for x in xs]
    print()
    print(f"{'POOLED':<30}{'':>8}{len(all_lane):>5}{q(all_lane,0.10):>7.2f}"
          f"{q(all_lane,0.50):>8.2f}{q(all_lane,0.90):>7.2f}{max(all_lane):>7.2f}"
          f"   {len(all_neut):>7}{q(all_neut,0.50) if all_neut else 0:>9.2f}")

    print("\nstationary time (sigma_pit source, PitStop, 2025+ only, green flag):", file=sys.stderr)
    if all_stat:
        s = sorted(all_stat)
        mean = sum(s) / len(s)
        # exponential tail scale above the floor: E[x - min] for an Exp offset
        floor = q(all_stat, 0.05)
        excess = [x - floor for x in all_stat if x >= floor]
        sigma = sum(excess) / len(excess) if excess else 0.0
        print(f"  n={len(s)}  min {s[0]:.2f}  median {q(all_stat,0.5):.2f}  "
              f"p90 {q(all_stat,0.9):.2f}  p99 {q(all_stat,0.99):.2f}  max {s[-1]:.2f}  "
              f"mean {mean:.2f}")
        print(f"  right-tail scale above the p05 floor ({floor:.2f} s): sigma_pit ~ {sigma:.3f}")
        print(f"  reference default was 0.90 -> observed {sigma:.3f}")
    ratio = (q(all_neut, 0.5) / q(all_lane, 0.5)) if all_neut else None
    if ratio:
        print(f"\nobserved neutralised/green lane-time ratio: {ratio:.3f}")
        print(f"  reference sc_pit_factor default is 0.45 (it discounts the pit LOSS, not the lane"
              f" time, so these are not directly comparable -- recorded, not substituted)")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "per_circuit": out,
            "pooled": {
                "pit_loss_n": len(all_lane),
                "pit_loss_median": round(q(all_lane, 0.5), 3),
                "pit_loss_p90": round(q(all_lane, 0.9), 3),
                "stationary_n": len(all_stat),
                "stationary_median": round(q(all_stat, 0.5), 3) if all_stat else None,
                "sigma_pit_tail": round(sigma, 3) if all_stat else None,
            },
        }, indent=2))
        print(f"\nwrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
