#!/usr/bin/env python3
"""Measure batched vs unary kernel dispatch on the local bundled runtime.

The claim under test: frame I/O dominates a small kernel call, so N unary
`execute()` calls cost roughly N x per-dispatch overhead while one
`execute_batch()` of the same N calls costs roughly one. Reports the speedup and
per-call cost for a few batch sizes.

Local only — no server, no cloud. Usage:
    python3 benchmarks/bench_runtime_batch.py [--sizes 1,4,16,64] [--reps 5]
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

# All in one module so the batch routes to a single shard — the case worth measuring.
CALLS = [
    ("stats", "compute_mean", [[1.0, 2.0, 3.0, 4.0], 4]),
    ("stats", "median", [[3.0, 1.0, 2.0], 3]),
    ("stats", "compute_variance", [[1.0, 2.0, 3.0], 3, 2.0]),
    ("stats", "count_below_zero", [[-1.0, 2.0, -3.0], 3]),
]


def _items(count: int) -> list[dict]:
    out = []
    for index in range(count):
        module, function, args = CALLS[index % len(CALLS)]
        out.append({"module": module, "function": function, "args": args})
    return out


def _median_ms(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1000, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="1,4,16,64")
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from algenta import MojoRuntime

    runtime = MojoRuntime(mode="local")
    health = runtime.health()
    if health.get("status") != "ok":
        print(f"runtime unavailable: {health}", file=sys.stderr)
        return 1

    # Warm everything that is one-time cost, so it is not attributed to the first
    # measurement: the contract parse (495 modules / 4873 functions), worker spawn,
    # the socket session, and the shard-routing cache. Under-warming here is what
    # made an earlier version of this benchmark report ~1.2x instead of ~8x.
    for module, function, call_args in CALLS:
        runtime.execute(module, function, call_args)
    runtime.execute_batch(_items(8))

    rows = []
    for size in [int(part) for part in args.sizes.split(",") if part.strip()]:
        items = _items(size)

        unary_samples = []
        for _ in range(args.reps):
            started = perf_counter()
            for item in items:
                result = runtime.execute(item["module"], item["function"], item["args"])
                if not result.get("success"):
                    print(f"unary call failed: {result}", file=sys.stderr)
                    return 1
            unary_samples.append(perf_counter() - started)

        batch_samples = []
        for _ in range(args.reps):
            started = perf_counter()
            envelope = runtime.execute_batch(items)
            batch_samples.append(perf_counter() - started)
            if envelope["failed"]:
                print(f"batch failed: {envelope['results'][:2]}", file=sys.stderr)
                return 1

        unary_ms = _median_ms(unary_samples)
        batch_ms = _median_ms(batch_samples)
        rows.append(
            {
                "batch_size": size,
                "unary_total_ms": unary_ms,
                "batch_total_ms": batch_ms,
                "unary_per_call_ms": round(unary_ms / size, 4),
                "batch_per_call_ms": round(batch_ms / size, 4),
                "speedup_x": round(unary_ms / batch_ms, 2) if batch_ms > 0 else None,
                "frames_unary": size,
                "frames_batch": envelope["frames"],
            }
        )

    if args.json:
        print(json.dumps({"reps": args.reps, "rows": rows}, indent=2))
        return 0

    print(f"batched vs unary dispatch (median of {args.reps} reps, single shard)")
    print(
        f"{'N':>5}  {'unary ms':>10}  {'batch ms':>10}  "
        f"{'unary/call':>11}  {'batch/call':>11}  {'speedup':>8}  frames"
    )
    for row in rows:
        print(
            f"{row['batch_size']:>5}  {row['unary_total_ms']:>10.3f}  "
            f"{row['batch_total_ms']:>10.3f}  "
            f"{row['unary_per_call_ms']:>11.4f}  {row['batch_per_call_ms']:>11.4f}  "
            f"{row['speedup_x']:>7}x  {row['frames_unary']}→{row['frames_batch']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
