#!/usr/bin/env python3
"""Measure resident datasets: send a large input once vs. with every call.

The claim under test: referencing a resident dataset by handle makes per-call
payload O(1) in rows rather than O(rows), so the gap widens with dataset size —
unlike batching, whose win is bounded by frame count.

Compares, for the same K kernel calls over the same N-row input:
  inline    — the array is embedded in every call (K x N values on the wire)
  resident  — opened once, then referenced as "@handle" (N values once, then K x O(1))

Local only — no server, no cloud. Usage:
    python3 benchmarks/bench_runtime_session.py [--rows 1000,10000] [--calls 8]
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

# All in `stats`, so everything routes to one shard.
FUNCTIONS = ["compute_mean", "median", "count_below_zero"]


def _median_ms(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1000, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", default="100,1000,10000")
    parser.add_argument("--calls", type=int, default=8)
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from algenta import MojoRuntime

    runtime = MojoRuntime(mode="local")
    health = runtime.health()
    if health.get("status") != "ok":
        print(f"runtime unavailable: {health}", file=sys.stderr)
        return 1

    # Warm contract parse, worker spawn, session and routing.
    runtime.execute("stats", "compute_mean", [[1.0, 2.0], 2])
    runtime.execute_batch([{"module": "stats", "function": "median", "args": [[1.0], 1]}])

    rows_list = [int(part) for part in args.rows.split(",") if part.strip()]
    calls = args.calls
    out_rows = []

    for n_rows in rows_list:
        values = [float(i % 97) for i in range(n_rows)]

        inline_items = [
            {
                "module": "stats",
                "function": FUNCTIONS[i % len(FUNCTIONS)],
                "args": [values, n_rows],
            }
            for i in range(calls)
        ]

        inline_samples = []
        for _ in range(args.reps):
            started = perf_counter()
            envelope = runtime.execute_batch(inline_items)
            inline_samples.append(perf_counter() - started)
            if envelope["failed"]:
                print(f"inline failed: {envelope['results'][:1]}", file=sys.stderr)
                return 1

        # Resident: open once outside the measured region, then reference by handle.
        handle = runtime.open_dataset(values, name="bench", routing_module="stats")
        resident_items = [
            {
                "module": "stats",
                "function": FUNCTIONS[i % len(FUNCTIONS)],
                "args": [f"@{handle}", n_rows],
            }
            for i in range(calls)
        ]
        try:
            resident_samples = []
            for _ in range(args.reps):
                started = perf_counter()
                envelope = runtime.execute_batch(resident_items)
                resident_samples.append(perf_counter() - started)
                if envelope["failed"]:
                    print(f"resident failed: {envelope['results'][:1]}", file=sys.stderr)
                    return 1
        finally:
            runtime.close_dataset(handle, routing_module="stats")

        inline_ms = _median_ms(inline_samples)
        resident_ms = _median_ms(resident_samples)
        # Wire volume is the mechanism: what actually shrinks.
        inline_bytes = len(json.dumps(inline_items))
        resident_bytes = len(json.dumps(resident_items))
        out_rows.append(
            {
                "rows": n_rows,
                "calls": calls,
                "inline_ms": inline_ms,
                "resident_ms": resident_ms,
                "speedup_x": round(inline_ms / resident_ms, 2) if resident_ms > 0 else None,
                "inline_request_bytes": inline_bytes,
                "resident_request_bytes": resident_bytes,
                "bytes_ratio": round(inline_bytes / max(resident_bytes, 1), 1),
            }
        )

    if args.json:
        print(json.dumps({"reps": args.reps, "rows": out_rows}, indent=2))
        return 0

    print(f"resident vs inline input ({calls} calls, median of {args.reps} reps)")
    print(
        f"{'rows':>7}  {'inline ms':>10}  {'resident ms':>12}  {'speedup':>8}  "
        f"{'req bytes inline':>17}  {'resident':>9}  {'ratio':>6}"
    )
    for row in out_rows:
        print(
            f"{row['rows']:>7}  {row['inline_ms']:>10.3f}  {row['resident_ms']:>12.3f}  "
            f"{row['speedup_x']:>7}x  {row['inline_request_bytes']:>17}  "
            f"{row['resident_request_bytes']:>9}  {row['bytes_ratio']:>5}x"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
