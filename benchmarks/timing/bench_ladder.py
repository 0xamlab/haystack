#!/usr/bin/env python3
"""Benchmark ladder for the option board — measured through the production transport.

Deliberately a LADDER rather than a single latency number. The plan forbids a headline sub-10-ms claim
because the arithmetic never supported it: a four-option board at N=100,000 over 20 cars and 30 laps is
240 million car-lap state updates, and primitive per-function nanosecond figures say nothing about a
stateful simulation with memory movement and interaction logic.

Everything is timed over the framed-JSON socket the worker pool actually uses, not via `mojo run`. The
JIT path measures faster; publishing that would be measuring the wrong thing.

The two rows that carry the honest story are the last two. The feed updates about once per second, so
what the engine buys is replications inside that second, and the resulting interval width.

Usage:
    python3 -m benchmarks.timing.bench_ladder
    python3 -m benchmarks.timing.bench_ladder --cars 20 --laps 30 --json ladder.json
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
from kernel_probe import Worker  # noqa: E402


def field(n: int) -> tuple[list, list, list, list, list]:
    pace = [83.8 + i * 0.06 for i in range(n)]
    deg = [0.05 + (i % 5) * 0.01 for i in range(n)]
    el = [i * 2.5 for i in range(n)]
    age = [float(10 + i % 12) for i in range(n)]
    act = [1.0] * n
    return pace, deg, el, age, act


def hardware() -> dict:
    cpu = platform.processor() or platform.machine()
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True, timeout=5).stdout.strip() or cpu
    except Exception:
        pass
    return {"cpu": cpu, "platform": platform.platform(), "python": platform.python_version()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--cars", type=int, default=20)
    ap.add_argument("--laps", type=int, default=30)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--budget", type=float, default=1.0, help="fixed-budget row, seconds")
    ap.add_argument("--target-ci", type=float, default=0.5, help="fixed-confidence row, pp")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    binary = ROOT / args.binary
    if not binary.exists():
        print(f"binary not found: {binary}", file=sys.stderr)
        return 2

    pace, deg, el, age, act = field(args.cars)
    w = Worker(binary)
    rows: list[dict] = []
    try:
        workers = w.execute("contest_strategy", "contest_worker_count")["result"]
        ver = w.execute("contest_strategy", "contest_strategy_version")["result"]
        rng = w.execute("counter_rng", "rng_version")["result"]
        p = w.execute("contest_strategy", "default_contest_params")["result"]

        def run(N: int) -> dict:
            # warm the pool, then measure
            w.execute("contest_strategy", "option_board",
                      [pace, deg, el, age, act, 3, 2, args.laps, p, 500, 100, 42, 11])
            best = None
            for _ in range(3):
                t0 = time.perf_counter()
                r = w.execute("contest_strategy", "option_board",
                              [pace, deg, el, age, act, 3, 2, args.laps, p, N, args.boot, 42, 11])
                dt = time.perf_counter() - t0
                if best is None or dt < best[0]:
                    best = (dt, r)
            dt, r = best
            v = r["result"]["v"]
            updates = N * 4 * args.cars * args.laps
            return {
                "n": N, "wall_ms": dt * 1000.0,
                "car_lap_updates": updates,
                "updates_per_s": updates / dt,
                "ci_width_pp": (v[3][1] - v[2][1]) * 100.0,
                "delta_pp": v[1][1] * 100.0,
                "crn_variance_ratio": v[10],
                "verdict": v[8],
            }

        print(f"engine {ver}   rng {rng}   workers {workers}")
        print(f"workload: {args.cars} cars, {args.laps} laps remaining, 4 options, B={args.boot}")
        print(f"transport: framed JSON over a Unix socket (the production path)\n")
        print(f"{'N':>9} {'wall ms':>10} {'car-lap upd':>14} {'M upd/s':>9} "
              f"{'CI width pp':>12} {'CRN ratio':>10}")
        for N in (2000, 10000, 100000):
            r = run(N)
            rows.append(r)
            print(f"{r['n']:>9,} {r['wall_ms']:>10.1f} {r['car_lap_updates']:>14,} "
                  f"{r['updates_per_s']/1e6:>9.1f} {r['ci_width_pp']:>12.3f} "
                  f"{r['crn_variance_ratio']:>10.3f}")

        # fixed budget: largest N that fits, found by scaling from a measurement
        probe = run(20000)
        per_rep = probe["wall_ms"] / 1000.0 / probe["n"]
        n_budget = max(500, int(args.budget / per_rep))
        rb = run(n_budget)
        print(f"\nfixed {args.budget:.1f} s budget -> N={rb['n']:,} "
              f"(measured {rb['wall_ms']/1000:.3f} s), CI width {rb['ci_width_pp']:.3f} pp")

        # fixed confidence: CI width scales as 1/sqrt(N)
        ref = rows[1]
        n_target = int(ref["n"] * (ref["ci_width_pp"] / args.target_ci) ** 2)
        rc = run(max(500, n_target))
        print(f"fixed {args.target_ci:.2f} pp target -> N={rc['n']:,} "
              f"in {rc['wall_ms']/1000:.3f} s, achieved {rc['ci_width_pp']:.3f} pp")

        print(f"\nThe last two rows are the claim. The feed updates about once per second, so the")
        print(f"engine spends that second on ~{rb['n']:,} full-field race continuations across four")
        print(f"options -- {rb['car_lap_updates']:,} car-lap state updates -- and reports the interval")
        print(f"that buys. Not that a board takes nanoseconds.")

        if args.json:
            Path(args.json).write_text(json.dumps({
                "engine_version": ver, "rng_version": rng, "workers": workers,
                "hardware": hardware(),
                "workload": {"cars": args.cars, "laps_remaining": args.laps,
                             "options": 4, "bootstrap": args.boot,
                             "transport": "framed JSON over Unix socket"},
                "ladder": rows,
                "fixed_budget": {"seconds": args.budget, **rb},
                "fixed_confidence": {"target_ci_pp": args.target_ci, **rc},
            }, indent=2))
            print(f"\nwrote {args.json}", file=sys.stderr)
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
