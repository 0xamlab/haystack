#!/usr/bin/env python3
"""Run one arena duel from the command line (validation / CI / docker).

Usage:
    python scripts/run_duel.py <duel_id> [S|M|L] [--quiet]

Prints the gate result, per-lane cold/warm timings, the hero speedup and the
final status. Exit code 0 = ok, 3 = held, 2 = error. This is the same
run_protocol the Gradio app uses — no separate code path.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena.duels import DUELS_BY_ID  # noqa: E402
from arena.harness import run_protocol  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("duel_id", choices=sorted(DUELS_BY_ID))
    parser.add_argument("size", nargs="?", default="M", choices=["S", "M", "L"])
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    duel = DUELS_BY_ID[args.duel_id]
    progress = (lambda m: None) if args.quiet else (lambda m: print(f"  … {m}", flush=True))
    outcome = run_protocol(duel, args.size, progress=progress)

    print(f"\n== {outcome.duel_title} [{outcome.size_key}] ==")
    print(f"status: {outcome.status}")
    print(f"gate: {'OK' if outcome.gate_ok else 'FAIL'} — {outcome.gate_detail}")
    if outcome.status == "ok":
        for t in outcome.lanes:
            print(
                f"  {t.name:>28}: cold {t.cold_s * 1e3:10.2f} ms | warm median "
                f"{t.warm_median_s * 1e3:10.2f} ms (min {t.warm_min_s * 1e3:.2f}, "
                f"max {t.warm_max_s * 1e3:.2f}, n={t.runs})"
            )
        print(f"hero: {outcome.hero_label}")
    else:
        print(f"reason: {outcome.held_reason}")
    print(f"hardware: {outcome.hardware}")
    print(f"wall: {outcome.elapsed_s:.1f}s")
    return {"ok": 0, "held": 3, "error": 2}[outcome.status]


if __name__ == "__main__":
    sys.exit(main())
