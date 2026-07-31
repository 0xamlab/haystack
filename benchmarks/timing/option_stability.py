#!/usr/bin/env python3
"""Rung 4 — option-contrast stability, the claim that IS provable at F1's sample size.

WHY THIS RUNG AND NOT MORE OUTCOME FORECASTING

The power analysis settles it. F1 produces ~23 races a year, so a Brier effect below about 0.002 is
permanently beyond prospective proof on public data — the theta-ensemble's +0.00066 would need 717 races.
Outcome calibration (rung 3) is therefore close to exhausted as a place to make progress.

Option contrast is different in kind. It compares FOUR OPTIONS WITHIN ONE RACE under common random
numbers, so race difficulty, field strength, circuit and era all cancel exactly rather than statistically.
Every decision snapshot is an independent measurement of the same question, and one race supplies dozens.
That is why the same corpus that cannot resolve a 0.0007 Brier difference can resolve an option contrast
to a fraction of a percentage point.

WHAT THIS MEASURES, and each is a thing a pit wall would actually want to know:

  CI WIDTH vs N            must fall as 1/sqrt(N). If it does not, the intervals are not sampling
                           intervals and the abstention rule is resting on nothing.
  RECOMMENDATION STABILITY does the board still say the same thing at 50,000 replications that it said at
                           2,000? A recommendation that flips with N is a recommendation about the random
                           seed. This is the number that decides what N the live board must run.
  DELTA CONVERGENCE        the paired delta itself must settle, not wander. Reported as absolute drift
                           from the highest-N estimate.
  CRN VARIANCE RATIO       measured, not assumed. The whole design rests on pairing actually working.
  ABSTENTION BEHAVIOUR     how often the board declines. A board that never abstains is not applying the
                           rule; one that always abstains is useless.

Snapshots come from real races through the as-of replay, so the states are ones that actually occurred.

Usage:
    python3 -m benchmarks.timing.option_stability
    python3 -m benchmarks.timing.option_stability --snapshots 40 --json docs/timing/option_stability.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
sys.path.insert(0, str(ROOT / "benchmarks" / "timing"))
from inrace_backtest import as_of_state, build_snapshot  # noqa: E402
from kernel_probe import Worker  # noqa: E402

OPT = ("STAY", "BOX NOW", "BOX+1", "BOX+2")
VERDICT = {0: "STAY", 1: "RECOMMENDED", 2: "INCONCLUSIVE"}
FROZEN_TEST_SEASON = 2025


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024")
    ap.add_argument("--snapshots", type=int, default=30)
    ap.add_argument("--fracs", default="0.3,0.55,0.8")
    ap.add_argument("--ladder", default="1000,2000,5000,10000,20000,50000")
    ap.add_argument("--boot", type=int, default=400)
    ap.add_argument("--theta-json", default="docs/timing/calibration.json")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    seasons = {int(x) for x in args.seasons.split(",") if x.strip().isdigit()}
    if FROZEN_TEST_SEASON in seasons:
        print(f"refusing: {FROZEN_TEST_SEASON} is the frozen final test season", file=sys.stderr)
        return 2
    fracs = [float(x) for x in args.fracs.split(",") if x.strip()]
    ladder = [int(x) for x in args.ladder.split(",") if x.strip()]
    root = Path(args.root).expanduser()

    sessions = [p.parent for p in sorted(root.glob("*/*/*_Race/_laps.parquet"))
                if int(p.parts[-4]) in seasons]
    if not sessions:
        print("no sessions", file=sys.stderr)
        return 2

    w = Worker(ROOT / args.binary)
    try:
        p = [float(x) for x in w.execute("contest_strategy",
                                         "default_contest_params")["result"]]
        if args.theta_json:
            cal = json.loads((ROOT / args.theta_json).read_text())
            import calibrate as _c
            for nm, (v, _why) in _c.MEASURED.items():
                for dn, di, *_r in _c.SEARCH_DIMS:
                    if dn == nm and di >= 0:
                        p[di] = v
            for rec in cal["parameters"]:
                if rec["param_index"] >= 0:
                    p[rec["param_index"]] = rec["fitted"]

        # collect real decision states
        snaps = []
        for sess in sessions:
            if len(snaps) >= args.snapshots:
                break
            for frac in fracs:
                if len(snaps) >= args.snapshots:
                    break
                st = as_of_state(sess, frac)
                if st is None:
                    continue
                s = build_snapshot(st, {}, p[0], 2, p[22])
                if s["remaining"] < 8 or s["n"] < 12:
                    continue
                # focal: a midfield car with a decision to make; rival: the car directly ahead
                order = sorted(range(s["n"]), key=lambda k: s["elapsed"][k])
                focal = order[min(6, len(order) - 1)]
                rival = order[max(0, order.index(focal) - 1)]
                snaps.append({"s": s, "focal": focal, "rival": rival,
                              "race": sess.parts[-2][:26], "frac": frac})
        if not snaps:
            print("no usable snapshots", file=sys.stderr)
            return 2
        print(f"{len(snaps)} real decision snapshots from {len({x['race'] for x in snaps})} races")
        print(f"replication ladder: {', '.join(f'{n:,}' for n in ladder)}\n")

        rows = []
        t0 = time.perf_counter()
        for k, sn in enumerate(snaps):
            s = sn["s"]
            per_n = {}
            for N in ladder:
                r = w.execute("contest_strategy", "option_board",
                              [s["pace"], [0.010] * s["n"], s["elapsed"], s["age"], s["active"],
                               sn["focal"], sn["rival"], s["remaining"], p, N, args.boot,
                               42, 1000 + k])
                if "error" in r:
                    continue
                v = r["result"]["v"]
                per_n[N] = {
                    "delta": v[1], "ci_lo": v[2], "ci_hi": v[3],
                    "recommended": v[7], "verdict": v[8], "crn": v[10],
                    "widest_ci": max(v[3][o] - v[2][o] for o in range(1, 4)),
                }
            if len(per_n) == len(ladder):
                rows.append({**{kk: sn[kk] for kk in ("race", "frac")}, "by_n": per_n})
            if (k + 1) % 10 == 0:
                print(f"  {k+1}/{len(snaps)} snapshots", file=sys.stderr)
        elapsed = time.perf_counter() - t0

        ref = ladder[-1]
        print(f"{'N':>8} {'CI width pp':>12} {'vs 1/sqrt(N)':>13} {'rec == ref':>11} "
              f"{'|delta drift| pp':>17} {'CRN ratio':>10}")
        summary = []
        base_w = statistics.mean(r["by_n"][ladder[0]]["widest_ci"] for r in rows)
        for N in ladder:
            widths = [r["by_n"][N]["widest_ci"] * 100 for r in rows]
            agree = sum(1 for r in rows
                        if r["by_n"][N]["recommended"] == r["by_n"][ref]["recommended"])
            drift = [abs(r["by_n"][N]["delta"][r["by_n"][ref]["recommended"]]
                         - r["by_n"][ref]["delta"][r["by_n"][ref]["recommended"]]) * 100
                     for r in rows]
            crn = statistics.mean(r["by_n"][N]["crn"] for r in rows)
            predicted = base_w * 100 * math.sqrt(ladder[0] / N)
            actual = statistics.mean(widths)
            summary.append({"n": N, "ci_width_pp": actual, "predicted_pp": predicted,
                            "rec_agreement": agree / len(rows), "delta_drift_pp":
                            statistics.mean(drift), "crn": crn})
            print(f"{N:>8,} {actual:>12.3f} {predicted:>13.3f} "
                  f"{100*agree/len(rows):>10.0f}% {statistics.mean(drift):>17.3f} {crn:>10.3f}")

        print(f"\nCI width must fall as 1/sqrt(N) or the intervals are not sampling intervals and the")
        print(f"abstention rule rests on nothing. Observed against predicted, above.")

        verd = {}
        for N in ladder:
            for r in rows:
                verd.setdefault(N, []).append(r["by_n"][N]["verdict"])
        print(f"\nabstention behaviour (a board that never abstains is not applying the rule):")
        for N in (ladder[0], ladder[len(ladder) // 2], ref):
            c = verd[N]
            print(f"  N={N:>6,}  " + "  ".join(
                f"{VERDICT[v]} {100*c.count(v)/len(c):.0f}%" for v in sorted(set(c))))

        flips = [r for r in rows
                 if r["by_n"][ladder[0]]["recommended"] != r["by_n"][ref]["recommended"]]
        print(f"\nrecommendation stability: {len(rows)-len(flips)}/{len(rows)} snapshots give the SAME")
        print(f"recommendation at N={ladder[0]:,} as at N={ref:,}.")
        if flips:
            print(f"  {len(flips)} flipped, e.g. "
                  + "; ".join(f"{f['race']} @{f['frac']:.0%}: "
                              f"{OPT[f['by_n'][ladder[0]]['recommended']]} -> "
                              f"{OPT[f['by_n'][ref]['recommended']]}" for f in flips[:3]))
            print(f"  A recommendation that moves with N is a recommendation about the seed, so the")
            print(f"  operational N must be at least where agreement saturates.")

        # smallest N whose recommendation matches the reference for >= 95% of snapshots
        ok = [s["n"] for s in summary if s["rec_agreement"] >= 0.95]
        if ok:
            print(f"\nSMALLEST N REACHING 95% AGREEMENT WITH N={ref:,}: {min(ok):,}")
            print(f"  That is the operational replication count the live board should run, and the")
            print(f"  benchmark ladder says a 1-second budget buys far more than that.")
        print(f"\n{len(rows)} snapshots x {len(ladder)} replication levels in {elapsed:.1f} s")

        if args.json:
            Path(args.json).write_text(json.dumps({
                "snapshots": len(rows), "ladder": ladder, "summary": summary,
                "flips": len(flips), "seconds": elapsed,
                "theta": args.theta_json,
            }, indent=2))
            print(f"wrote {args.json}", file=sys.stderr)
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
