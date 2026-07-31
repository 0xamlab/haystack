#!/usr/bin/env python3
"""Fit per-stint pace and degradation on real session data, via the Mojo kernel over the socket.

Every number reported here is computed by degradation_state in Mojo. Python selects laps, marks
exclusion flags from observed state, and prints -- it performs no estimation.

Lap flags are derived from what the feed stated: pit_out marks an out-lap, in_pit an in-lap, and any
non-green track regime marks the lap neutralised. Those laps are excluded from the filter because a car
behind a safety car or on cold tyres is not revealing its pace.

Usage:
    python3 scripts/timing/fit_pace.py \
        --dir ~/.algenta/f1/raw/2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
from kernel_probe import Worker  # noqa: E402

LAP_GREEN, LAP_OUT, LAP_IN, LAP_NEUTRALISED, LAP_DIRTY_AIR = 0, 1, 2, 4, 8

# Filter priors. lap_noise is the reference default; drift lets the slope move slowly.
LAP_NOISE = 0.18
DRIFT = 0.0005
VAR0, VAR1 = 4.0, 0.02


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--min-laps", type=int, default=5)
    args = ap.parse_args()

    d = Path(args.dir).expanduser()
    laps = pq.read_table(d / "_laps.parquet").to_pydict()
    n = len(laps["car_number"])

    # group by (car, stint), in lap order
    stints: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for i in range(n):
        if laps["lap_time_s"][i] is None:
            continue
        stints[(laps["car_number"][i], laps["stint_index"][i])].append({
            "lap": laps["lap_number"][i],
            "t": laps["lap_time_s"][i],
            "age": laps["tyre_age"][i],
            "compound": laps["compound"][i],
            "out": laps["pit_out"][i],
            "inp": laps["in_pit"][i],
            "regime": laps["track_regime"][i],
            "interval": laps["interval_ahead_s"][i],
        })

    w = Worker(Path(args.binary))
    try:
        ver = w.execute("degradation_state", "degradation_state_version")["result"]
        st = w.execute("degradation_state", "degradation_state_selftest")["result"]
        print(f"kernel {ver}   selftest slope {st:.5f} (truth 0.05)\n")

        rows = []
        for (car, si), recs in sorted(stints.items()):
            recs.sort(key=lambda r: r["lap"])
            if len(recs) < args.min_laps:
                continue
            times, ages, flags = [], [], []
            last_lap = recs[-1]["lap"]
            for r in recs:
                f = LAP_GREEN
                # Out-lap = the FIRST lap of any non-initial stint. Two rejected alternatives:
                #
                #   PitOut boolean -- transient, true only while the car exits the pit lane and already
                #   false by lap completion. Left every out-lap unflagged, and one 105 s observation
                #   among 85 s laps fits a steeply negative slope with an inflated intercept.
                #
                #   tyre_age == 0 -- fails on USED tyre sets, which start at nonzero age. Car 1's
                #   fourth stint opens at age 3 on a used soft, so an age-based rule silently misses
                #   exactly the stints where a scrubbed set is fitted. That is why SOFT degradation
                #   stayed negative after the PitOut fix while HARD and MEDIUM came right.
                if si > 0 and r["lap"] == recs[0]["lap"]:
                    f |= LAP_OUT
                # the final lap of a stint that is not the last stint is the in-lap
                if si < max(k[1] for k in stints if k[0] == car) and r["lap"] == last_lap:
                    f |= LAP_IN
                if r["inp"]:
                    f |= LAP_IN
                if r["regime"] != 1:
                    f |= LAP_NEUTRALISED
                # within 1.2 s of the car ahead is the reference dirty-air window
                if r["interval"] is not None and 0.0 < r["interval"] <= 1.2:
                    f |= LAP_DIRTY_AIR
                times.append(float(r["t"]))
                ages.append(float(r["age"]))
                flags.append(f)

            res = w.execute("degradation_state", "pace_kalman_run",
                            [times, ages, flags, times[0], 0.0, VAR0, VAR1, LAP_NOISE, DRIFT])
            if "error" in res:
                print(f"  car {car} stint {si}: {res['error']}")
                continue
            v = res["result"]["v"]
            beta0, beta1, p00, p11, upd, exc = v[0], v[1], v[2], v[4], v[5], v[6]
            rows.append({
                "car": car, "stint": si, "compound": recs[0]["compound"],
                "laps": len(recs), "used": upd, "excl": exc,
                "beta0": beta0, "beta1": beta1, "se1": p11 ** 0.5,
            })

        rows.sort(key=lambda r: r["beta0"])
        print(f"{'car':>4} {'st':>3} {'compound':<8} {'laps':>5} {'used':>5} {'excl':>5} "
              f"{'pace s/lap':>11} {'deg s/lap²':>11} {'se(deg)':>9}")
        for r in rows:
            print(f"{r['car']:>4} {r['stint']:>3} {r['compound'][:8]:<8} {r['laps']:>5} "
                  f"{r['used']:>5} {r['excl']:>5} {r['beta0']:>11.3f} {r['beta1']:>11.4f} "
                  f"{r['se1']:>9.4f}")

        deg = [r["beta1"] for r in rows]
        pace = [r["beta0"] for r in rows]
        print(f"\nstints fitted            {len(rows)}")
        print(f"pace  range              {min(pace):.3f} .. {max(pace):.3f} s/lap")
        print(f"deg   range              {min(deg):+.4f} .. {max(deg):+.4f} s/lap per lap of age")
        print(f"negative slopes          {sum(1 for x in deg if x < 0)}/{len(deg)} "
              f"(clamped to 0 at prediction time)")
        by_comp: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            by_comp[r["compound"]].append(r["beta1"])
        print("\nmean degradation by compound:")
        for comp, xs in sorted(by_comp.items()):
            print(f"  {comp:<8} n={len(xs):>3}  {sum(xs) / len(xs):+.4f}")
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
