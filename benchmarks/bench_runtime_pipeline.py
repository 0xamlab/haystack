#!/usr/bin/env python3
"""Measure chained kernel execution: one pipeline frame vs threading via Python.

The claim under test: when each step consumes the previous step's output, doing it
with unary calls pays a frame *and* a full encode/decode of every intermediate,
while a pipeline keeps intermediates inside the worker and pays one frame total.

Chain used: sort_values -> median -> compute_mean, repeated to the requested depth,
so every step genuinely depends on its predecessor.

Local only — no server, no cloud. Usage:
    python3 benchmarks/bench_runtime_pipeline.py [--depths 2,4,8,16] [--reps 9]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

SEED_VALUES = [5.0, 3.0, 9.0, 1.0, 7.0, 2.0, 8.0, 4.0]


def _chain_nodes(depth: int) -> list[dict]:
    """A genuinely dependent chain: each node consumes the previous node's list."""
    nodes = [
        {
            "module": "stats",
            "function": "sort_values",
            "args": [list(SEED_VALUES), len(SEED_VALUES)],
        }
    ]
    for step in range(1, depth):
        # sort_values -> List[Float64], so it can feed itself indefinitely.
        nodes.append(
            {
                "module": "stats",
                "function": "sort_values",
                "args": [f"${step - 1}", len(SEED_VALUES)],
            }
        )
    return nodes


def _median_ms(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1000, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depths", default="2,4,8,16")
    parser.add_argument("--reps", type=int, default=9)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from algenta import MojoRuntime

    runtime = MojoRuntime(mode="local")
    health = runtime.health()
    if health.get("status") != "ok":
        print(f"runtime unavailable: {health}", file=sys.stderr)
        return 1

    # Warm the contract parse, worker spawn, session and routing cache.
    runtime.execute("stats", "sort_values", [list(SEED_VALUES), len(SEED_VALUES)])
    runtime.run_pipeline(_chain_nodes(2))

    rows = []
    for depth in [int(part) for part in args.depths.split(",") if part.strip()]:
        nodes = _chain_nodes(depth)

        # Unary: every intermediate crosses the boundary and comes back.
        def unary_chain(steps: int = depth) -> None:
            current = list(SEED_VALUES)
            for _ in range(steps):
                out = runtime.execute("stats", "sort_values", [current, len(SEED_VALUES)])
                if not out.get("success"):
                    raise SystemExit(f"unary chain failed: {out}")
                current = out["result"]

        unary_samples = []
        for _ in range(args.reps):
            started = perf_counter()
            unary_chain()
            unary_samples.append(perf_counter() - started)

        pipeline_samples = []
        envelope = None
        for _ in range(args.reps):
            started = perf_counter()
            envelope = runtime.run_pipeline(nodes)
            pipeline_samples.append(perf_counter() - started)
            if not envelope.get("success"):
                print(f"pipeline failed: {envelope}", file=sys.stderr)
                return 1

        unary_ms = _median_ms(unary_samples)
        pipeline_ms = _median_ms(pipeline_samples)
        rows.append(
            {
                "depth": depth,
                "unary_ms": unary_ms,
                "pipeline_ms": pipeline_ms,
                "speedup_x": round(unary_ms / pipeline_ms, 2) if pipeline_ms > 0 else None,
                "frames_unary": depth,
                "frames_pipeline": 1,
                "plan_hash": (envelope or {}).get("plan_hash", "")[:12],
            }
        )

    if args.json:
        print(json.dumps({"reps": args.reps, "rows": rows}, indent=2))
        return 0

    print(f"chained execution (median of {args.reps} reps, single shard)")
    print(f"{'depth':>6}  {'unary ms':>10}  {'pipeline ms':>12}  {'speedup':>8}  frames  plan_hash")
    for row in rows:
        print(
            f"{row['depth']:>6}  {row['unary_ms']:>10.3f}  {row['pipeline_ms']:>12.3f}  "
            f"{row['speedup_x']:>7}x  {row['frames_unary']}→1     {row['plan_hash']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
