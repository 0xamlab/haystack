#!/usr/bin/env python3
"""Measure a whole query plan in one call against the same work done step by step.

The claim under test: a query is one job made of several steps, and each step's output
is the next step's entire input — so running it as N separate calls pays N frame
crossings AND re-encodes every intermediate table. `runtime.query` sends the plan once
and keeps the intermediates inside Mojo.

The step-by-step arm is a real alternative, not a straw man: it uses the same operators
via the same message type, one op per call, feeding each result forward as the next
call's rows. That is what a caller would actually have to do without a plan.

Local only — no server, no cloud. Usage:
    python3 benchmarks/bench_query_plane.py [--rows 1000,10000] [--reps 5]

A repo-dev binary is unsigned, so point at it and relax verification:
    ALGENTA_RUNTIME_WORKER=$PWD/mojo_build/simulate_queryplane \\
      ALGENTA_RUNTIME_FALLBACK_MODE=allow python3 benchmarks/bench_query_plane.py
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

COLUMNS = ["region", "month", "amount"]


def _rows(count: int, groups: int = 8) -> list[list[float | None]]:
    """Synthetic sales. Every 17th amount is absent, so the validity path is real.

    An all-present benchmark measures a branch the production path does not take.
    """
    out: list[list[float | None]] = []
    for index in range(count):
        amount = None if index % 17 == 0 else float((index * 7919) % 1000) * 0.5
        out.append([float(index % groups), float(index % 12), amount])
    return out


def _one_call(runtime, rows, threshold: float):
    """The whole plan in a single dispatch."""
    from algenta.query import Query, col

    return (
        Query(columns=COLUMNS, rows=rows)
        .filter(col("amount") > threshold)
        .group_by("region", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .top_k("sum_amount", 5)
        .run(runtime, routing_module="stats")
    )


def _step_by_step(runtime, rows, threshold: float):
    """The same four operators, one call each, threading rows through by hand.

    What a caller without a plan has to write. Each step re-encodes the whole
    intermediate table on the way out and the way back in.
    """
    from algenta.query import Query, col

    filtered = (
        Query(columns=COLUMNS, rows=rows)
        .filter(col("amount") > threshold)
        .run(runtime, routing_module="stats")
    )
    grouped = (
        Query(columns=filtered.columns, rows=filtered.rows)
        .group_by("region", "amount", agg="sum")
        .run(runtime, routing_module="stats")
    )
    sorted_result = (
        Query(columns=grouped.columns, rows=grouped.rows)
        .sort("sum_amount", desc=True)
        .run(runtime, routing_module="stats")
    )
    return (
        Query(columns=sorted_result.columns, rows=sorted_result.rows)
        .top_k("sum_amount", 5)
        .run(runtime, routing_module="stats")
    )


def _resident(runtime, handle, columns, threshold: float):
    """One call, and the table never crosses the boundary at all."""
    from algenta.query import Query, col

    return (
        Query(columns=columns, dataset=handle)
        .filter(col("amount") > threshold)
        .group_by("region", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .top_k("sum_amount", 5)
        .run(runtime, routing_module="stats")
    )


def _median_ms(fn, reps: int) -> float:
    samples = []
    for _ in range(reps):
        started = perf_counter()
        fn()
        samples.append((perf_counter() - started) * 1000)
    return statistics.median(samples)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", default="1000,10000,50000")
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from algenta import MojoRuntime

    runtime = MojoRuntime(mode="local")
    health = runtime.health()
    if health.get("status") != "ok":
        print(f"runtime unavailable: {health}", file=sys.stderr)
        return 1

    sizes = [int(part) for part in args.rows.split(",") if part.strip()]
    threshold = 200.0
    records = []

    print("whole plan vs step-by-step (4 operators, median of "
          f"{args.reps} reps)")
    print(
        f"{'rows':>8} {'stepwise ms':>12} {'one call ms':>12} "
        f"{'resident ms':>12} {'speedup':>9} {'vs resident':>12} {'frames':>8}"
    )

    for size in sizes:
        rows = _rows(size)

        # Warm: first call spawns the worker, builds the routing cache and parses the
        # contract. Timing that would report startup, not throughput.
        one = _one_call(runtime, rows, threshold)
        stepwise = _step_by_step(runtime, rows, threshold)
        if one.rows != stepwise.rows:
            print(
                f"  MISMATCH at {size} rows: {one.rows} != {stepwise.rows}",
                file=sys.stderr,
            )
            return 1

        handle = runtime.open_dataset(rows, name="sales", routing_module="stats")
        try:
            resident = _resident(runtime, handle, COLUMNS, threshold)
            if resident.rows != one.rows:
                print(
                    f"  MISMATCH (resident) at {size} rows: "
                    f"{resident.rows} != {one.rows}",
                    file=sys.stderr,
                )
                return 1

            stepwise_ms = _median_ms(
                lambda: _step_by_step(runtime, rows, threshold), args.reps
            )
            one_ms = _median_ms(lambda: _one_call(runtime, rows, threshold), args.reps)
            resident_ms = _median_ms(
                lambda: _resident(runtime, handle, COLUMNS, threshold), args.reps
            )
        finally:
            runtime.close_dataset(handle, routing_module="stats")

        speedup = stepwise_ms / one_ms if one_ms else 0.0
        vs_resident = stepwise_ms / resident_ms if resident_ms else 0.0
        print(
            f"{size:>8} {stepwise_ms:>12.3f} {one_ms:>12.3f} {resident_ms:>12.3f} "
            f"{speedup:>8.2f}x {vs_resident:>11.2f}x {'4→1':>8}"
        )
        records.append(
            {
                "rows": size,
                "stepwise_ms": round(stepwise_ms, 3),
                "one_call_ms": round(one_ms, 3),
                "resident_ms": round(resident_ms, 3),
                "speedup": round(speedup, 2),
                "speedup_resident": round(vs_resident, 2),
                "result_rows": one.rows,
                "plan_hash": one.plan_hash,
            }
        )

    # A plan identifies the computation, not the data, so every size shares one hash.
    hashes = {record["plan_hash"] for record in records}
    print()
    if len(hashes) == 1:
        print(f"plan_hash identical across every size: {hashes.pop()[:16]}…")
    else:
        print(f"WARNING: plan_hash differed across sizes: {hashes}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(records, indent=2))

    regressions = [r for r in records if r["speedup"] < 1.0]
    if regressions:
        print(
            "WARNING: one call was slower than stepwise at "
            f"{[r['rows'] for r in regressions]} rows",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
