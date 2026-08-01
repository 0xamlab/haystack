"""run_composed_interleaved.py — the COMPOSED route against polars and duckdb
on all six H2O group-by questions, interleaved, in one measurement window.

This is the authoritative measurement for the composed route. It supersedes
every per-attack number, because composition can lose what the pieces won and
each of those numbers was taken in a different window against a different
reference.

Why the interleaving is not optional here: on this host the load average moved
by 3x inside one afternoon, which is enough to invert a 1.06x claim — and the
published page's two narrowest cells are 1.06x and 1.10x. So the unit of
measurement is a (cycle, question) BLOCK, inside which all three engines run
back to back, and the engine ORDER ROTATES per cycle so no engine is
systematically first (cold) or last (warm).

Protocol, enforced in code rather than described:

  * versions ASSERTED at runtime — polars 1.43.1, duckdb 1.5.5 — because a
    number from a different build is not comparable to the published page.
  * the same seeded dataset `generate.py` wrote, loaded once, given to every
    engine as in-memory columns. No parse is timed anywhere.
  * REPS_PER_BLOCK reps per engine per block x CYCLES cycles. Headline is the
    MIN of all of them; the median and the max are printed too, because a route
    that wins only on the min is winning on luck.
  * rep 0 of every block is kept and reported: it IS the cold tier, and there
    is no warm-up call outside the record.
  * `os.getloadavg()` recorded before and after EVERY engine block.
  * CHECKSUMS from all three engines compared at the end. The Mojo binary
    additionally asserts BIT identity of the composed route against a SHIPPED
    engine on the full 1e7-row result and exits non-zero on a mismatch, which
    this script propagates as a hard failure rather than a warning.

Usage:
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/run_composed_interleaved.py \\
        --binary /tmp/bench_h2o_composed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

import duckdb
import numpy as np
import polars as pl

DATA_DIR = "/tmp/h2o_groupby"
EXPECTED_POLARS = "1.43.1"
EXPECTED_DUCKDB = "1.5.5"
CYCLES = 2
REPS_PER_BLOCK = 3
QUESTIONS = ("q1", "q2", "q3", "q4", "q5", "q7")

# Regime-W ceiling in ms: (bytes the query must touch, as the columnar plane
# stores them — every column Float64) / 350.9 GB/s McCalpin STREAM.
CEILING_MS = {
    "q1": 0.456,
    "q2": 0.684,
    "q3": 0.684,
    "q4": 0.912,
    "q5": 0.912,
    "q7": 0.684,
}

KEYS = {
    "q1": ["id1"],
    "q2": ["id1", "id2"],
    "q3": ["id3"],
    "q4": ["id4"],
    "q5": ["id6"],
    "q7": ["id3"],
}


def load_str() -> str:
    a, b, c = os.getloadavg()
    return f"{a:.2f} {b:.2f} {c:.2f}"


def assert_versions() -> None:
    """A number from the wrong build is not a number. Refuse, do not warn."""
    if pl.__version__ != EXPECTED_POLARS:
        raise SystemExit(
            f"polars {pl.__version__} != required {EXPECTED_POLARS}; "
            "the protocol pins the build the page compares against"
        )
    if duckdb.__version__ != EXPECTED_DUCKDB:
        raise SystemExit(f"duckdb {duckdb.__version__} != required {EXPECTED_DUCKDB}")
    print(f"versions OK: polars {pl.__version__}, duckdb {duckdb.__version__}")
    print(f"numpy {np.__version__}; python {sys.version.split()[0]} at {sys.executable}")


def build_engines():
    names = ["id1", "id2", "id3", "id4", "id6", "v1", "v2", "v3"]
    cols = {n: np.load(os.path.join(DATA_DIR, f"{n}.npy")) for n in names}
    for name, arr in cols.items():
        if arr.shape != (10_000_000,):
            raise SystemExit(f"{name}.npy has shape {arr.shape}, expected (1e7,)")
    df = pl.DataFrame(cols)
    con = duckdb.connect()
    con.register("df_view", df.to_pandas())
    con.execute("CREATE TABLE tbl AS SELECT * FROM df_view")
    return df, con


def polars_q(df, q: str):
    if q == "q1":
        return lambda: df.group_by("id1").agg(pl.sum("v1"))
    if q == "q2":
        return lambda: df.group_by("id1", "id2").agg(pl.sum("v1"))
    if q == "q3":
        return lambda: df.group_by("id3").agg(pl.sum("v1"), pl.mean("v3"))
    if q == "q4":
        return lambda: df.group_by("id4").agg(
            pl.mean("v1"), pl.mean("v2"), pl.mean("v3")
        )
    if q == "q5":
        return lambda: df.group_by("id6").agg(
            pl.sum("v1"), pl.sum("v2"), pl.sum("v3")
        )
    return lambda: df.group_by("id3").agg(pl.max("v1"), pl.min("v2"))


def duckdb_q(con, q: str):
    sql = {
        "q1": "SELECT id1, sum(v1) AS s FROM tbl GROUP BY id1",
        "q2": "SELECT id1, id2, sum(v1) AS s FROM tbl GROUP BY id1, id2",
        "q3": "SELECT id3, sum(v1) AS s, avg(v3) AS a FROM tbl GROUP BY id3",
        "q4": (
            "SELECT id4, avg(v1) AS a1, avg(v2) AS a2, avg(v3) AS a3 "
            "FROM tbl GROUP BY id4"
        ),
        "q5": (
            "SELECT id6, sum(v1) AS s1, sum(v2) AS s2, sum(v3) AS s3 "
            "FROM tbl GROUP BY id6"
        ),
        "q7": "SELECT id3, max(v1) AS mx, min(v2) AS mn FROM tbl GROUP BY id3",
    }[q]
    return lambda: con.execute(sql).fetchdf()


def checksum_frame(obj, q: str) -> float:
    """Sum of every aggregated column — exactly what the Mojo bench prints."""
    keys = set(KEYS[q])
    return float(sum(obj[c].sum() for c in obj.columns if c not in keys))


REP_RE = re.compile(
    r"^REP (\w+) (\d+) routed_ms=(?P<routed>[0-9.eE+-]+) "
    r"reference_ms=(?P<reference>[0-9.eE+-]+) "
    r"composed_ms=(?P<composed>[0-9.eE+-]+) "
    r"planned_ms=(?P<planned>[0-9.eE+-]+) "
    r"serialmrg_ms=(?P<serialmrg>[0-9.eE+-]+) "
    r"plan_ms=(?P<plan>[0-9.eE+-]+) "
    r"route=(?P<route>\w+) groups=(?P<groups>\d+) "
    r"identity_diffs=(?P<id>-?\d+) serialmrg_diffs=(?P<sm>-?\d+) "
    r"checksum=(?P<cs>[0-9.eE+-]+)"
)


def run_mojo(binary: str, q: str, reps: int, workers: int):
    out = subprocess.run(
        [binary, q, str(reps), str(workers)],
        capture_output=True,
        text=True,
        check=False,
        cwd="/tmp/h2o_groupby",
    )
    routed, composed, planned, serialmrg = [], [], [], []
    checksum, route, groups, plan_line = None, None, None, ""
    for line in out.stdout.splitlines():
        if line.startswith("BENCH question="):
            plan_line = line
        m = REP_RE.match(line)
        if m:
            if int(m.group("id")) != 0 or int(m.group("sm")) != 0:
                raise SystemExit(f"BENCH_GATE composed_identity: {line}")
            routed.append(float(m.group("routed")))
            composed.append(float(m.group("composed")))
            planned.append(float(m.group("planned")))
            sm = float(m.group("serialmrg"))
            if sm > 0.0:
                serialmrg.append(sm)
            checksum = float(m.group("cs"))
            route = m.group("route")
            groups = int(m.group("groups"))
        elif "BENCH_GATE" in line:
            raise SystemExit(f"BENCH_GATE from bench: {line}")
    if out.returncode != 0:
        raise SystemExit(
            f"{binary} {q} exited {out.returncode}\n{out.stdout}\n{out.stderr}"
        )
    if not composed:
        raise SystemExit(f"no REP lines from {binary} {q}:\n{out.stdout}")
    return routed, composed, planned, serialmrg, checksum, route, groups, plan_line


def timed(fn, reps: int):
    """Reps of one engine, all times kept. No warm-up outside the record: rep 0
    IS the cold tier and is reported as such."""
    out = []
    result = None
    for _ in range(reps):
        t = time.perf_counter()
        result = fn()
        out.append((time.perf_counter() - t) * 1000.0)
    return out, result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default="/tmp/bench_h2o_composed")
    ap.add_argument(
        "--workers",
        type=int,
        default=0,
        help="0 = the composed route's own default band count",
    )
    ap.add_argument("--cycles", type=int, default=CYCLES)
    ap.add_argument("--reps", type=int, default=REPS_PER_BLOCK)
    ap.add_argument(
        "--questions",
        default=",".join(QUESTIONS),
        help="comma-separated subset, for putting more samples on a contested cell",
    )
    args = ap.parse_args()

    questions = tuple(q.strip() for q in args.questions.split(",") if q.strip())
    for q in questions:
        if q not in CEILING_MS:
            raise SystemExit(f"unknown question {q}")

    assert_versions()
    print(f"load at start: {load_str()}")
    df, con = build_engines()
    print(f"data loaded; load now: {load_str()}")

    times: dict[tuple[str, str], list[float]] = {}
    cold: dict[tuple[str, str], list[float]] = {}
    checks: dict[tuple[str, str], float] = {}
    routes: dict[str, str] = {}
    plans: dict[str, str] = {}
    groups_seen: dict[str, int] = {}

    def record(engine: str, q: str, samples: list[float]) -> None:
        times.setdefault((engine, q), []).extend(samples)
        if samples:
            cold.setdefault((engine, q), []).append(samples[0])

    for cycle in range(args.cycles):
        order = (
            ["duckdb", "polars", "mojo"]
            if cycle % 2 == 0
            else ["mojo", "polars", "duckdb"]
        )
        for q in questions:
            print(f"\n--- cycle {cycle} {q} order={'>'.join(order)} ---")
            for engine in order:
                before = load_str()
                label = engine
                if engine == "polars":
                    samples, res = timed(polars_q(df, q), args.reps)
                    checks[("polars", q)] = checksum_frame(res, q)
                elif engine == "duckdb":
                    samples, res = timed(duckdb_q(con, q), args.reps)
                    checks[("duckdb", q)] = checksum_frame(res, q)
                else:
                    (
                        routed,
                        composed,
                        planned,
                        serialmrg,
                        cs,
                        route,
                        groups,
                        plan_line,
                    ) = run_mojo(args.binary, q, args.reps, args.workers)
                    record("algenta_routed", q, routed)
                    record("algenta_planned", q, planned)
                    if serialmrg:
                        record("algenta_serialmrg", q, serialmrg)
                    checks[("algenta_composed", q)] = cs
                    routes[q] = route
                    plans[q] = plan_line
                    groups_seen[q] = groups
                    samples = composed
                    label = "algenta_composed"
                record(label, q, samples)
                after = load_str()
                pretty = " ".join(f"{s:.3f}" for s in samples)
                print(
                    f"  {label:18s} reps_ms=[{pretty}] min={min(samples):.3f}"
                    f"  load_before=[{before}] load_after=[{after}]"
                )

    n = args.reps * args.cycles
    print(f"\n=== PLAN PER QUESTION (what the router actually chose) ===")
    for q in questions:
        print(f"  {plans.get(q, '(none)')}")

    print(f"\n=== MIN OF {n} (= {args.reps} reps x {args.cycles} cycles) ===")
    hdr = (
        f"{'q':<4}{'duckdb':>11}{'polars':>11}{'routed':>11}"
        f"{'serialmrg':>11}{'COMPOSED':>11}"
    )
    print(hdr)
    summary = {}
    for q in questions:
        row = {}
        for engine in (
            "duckdb",
            "polars",
            "algenta_routed",
            "algenta_serialmrg",
            "algenta_composed",
        ):
            xs = times.get((engine, q))
            row[engine] = min(xs) if xs else float("nan")
        summary[q] = row
        print(
            f"{q:<4}{row['duckdb']:>11.3f}{row['polars']:>11.3f}"
            f"{row['algenta_routed']:>11.3f}{row['algenta_serialmrg']:>11.3f}"
            f"{row['algenta_composed']:>11.3f}"
        )

    def stat(engine: str, q: str, which: str) -> float:
        xs = sorted(times.get((engine, q), []))
        if not xs:
            return float("nan")
        if which == "min":
            return xs[0]
        if which == "max":
            return xs[-1]
        return xs[len(xs) // 2]

    print("\n=== THE VERDICT: composed vs BOTH baselines, on min / median / max ===")
    print(
        f"{'q':<4}{'vs duck min':>13}{'vs duck med':>13}{'vs duck max':>13}"
        f"{'vs pol min':>12}{'vs pol med':>12}{'vs pol max':>12}{'win?':>7}"
    )
    outright = True
    verdict_rows = []
    for q in questions:
        r = {}
        for w in ("min", "median", "max"):
            r[("d", w)] = stat("duckdb", q, w) / stat("algenta_composed", q, w)
            r[("p", w)] = stat("polars", q, w) / stat("algenta_composed", q, w)
        won = r[("d", "min")] > 1.0 and r[("p", "min")] > 1.0
        outright = outright and won
        verdict_rows.append((q, r, won))
        print(
            f"{q:<4}{r[('d','min')]:>13.3f}{r[('d','median')]:>13.3f}"
            f"{r[('d','max')]:>13.3f}{r[('p','min')]:>12.3f}"
            f"{r[('p','median')]:>12.3f}{r[('p','max')]:>12.3f}"
            f"{('WIN' if won else 'LOSS'):>7}"
        )
    print(f"\nOUTRIGHT ON EVERY QUESTION (min-of-{n}): {outright}")

    print("\n=== RATIO TO CEILING (regime W) ===")
    print(
        f"{'q':<4}{'ceil_ms':>9}{'composed':>10}{'x':>7}{'duckdb':>10}{'x':>7}"
        f"{'polars':>10}{'x':>7}{'routed':>10}{'x':>7}"
    )
    for q in questions:
        r = summary[q]
        c = CEILING_MS[q]
        print(
            f"{q:<4}{c:>9.3f}{r['algenta_composed']:>10.3f}"
            f"{r['algenta_composed']/c:>7.1f}{r['duckdb']:>10.3f}"
            f"{r['duckdb']/c:>7.1f}{r['polars']:>10.3f}{r['polars']/c:>7.1f}"
            f"{r['algenta_routed']:>10.3f}{r['algenta_routed']/c:>7.1f}"
        )

    print("\n=== COMPOSITION'S OWN CONTRIBUTION (parallel merge, dense route) ===")
    for q in questions:
        xs = times.get(("algenta_serialmrg", q))
        if not xs:
            print(f"  {q} n/a (not the dense route)")
            continue
        s, c = min(xs), summary[q]["algenta_composed"]
        print(f"  {q} serial_merge={s:8.3f}  parallel_merge={c:8.3f}  {s/c:6.3f}x")

    print("\n=== COLD TIER (rep 0 of every block) / WARM+HOT ===")
    for q in questions:
        for engine in ("duckdb", "polars", "algenta_composed"):
            cs = cold.get((engine, q), [])
            allx = sorted(times.get((engine, q), []))
            warm = allx[1:] if len(allx) > 1 else allx
            print(
                f"  {q} {engine:18s} cold=" + " ".join(f"{x:.2f}" for x in cs)
                + f"  warm_hot_min={min(warm):.3f} med={sorted(warm)[len(warm)//2]:.3f}"
            )

    print("\n=== ALL SAMPLES ===")
    for q in questions:
        for engine in (
            "duckdb",
            "polars",
            "algenta_routed",
            "algenta_serialmrg",
            "algenta_composed",
        ):
            xs = sorted(times.get((engine, q), []))
            if not xs:
                continue
            print(
                f"  {q} {engine:18s} min={xs[0]:8.3f} "
                f"med={xs[len(xs)//2]:8.3f} max={xs[-1]:8.3f}  all="
                + " ".join(f"{x:.2f}" for x in xs)
            )

    print("\n=== CHECKSUM AGREEMENT ===")
    print(json.dumps({f"{k[0]}:{k[1]}": v for k, v in checks.items()}, indent=2))
    bad = 0
    for q in questions:
        ref = checks[("duckdb", q)]
        for engine in ("polars", "algenta_composed"):
            got = checks[(engine, q)]
            scale = max(1.0, abs(ref))
            rel = abs(got - ref) / scale
            if rel > 1e-12:
                bad += 1
            print(f"  {q} {engine:18s} rel={rel:.3e} {'OK ' if rel <= 1e-12 else 'MISMATCH'}")
    print(f"\ngroups per question: {groups_seen}")
    print(f"routes: {routes}")
    print(f"load at end: {load_str()}")
    if bad:
        raise SystemExit(f"BENCH_GATE composed_crossengine: {bad} mismatches")
    print("CROSS-ENGINE CHECKSUMS AGREE")
    print(f"OUTRIGHT={outright}")


if __name__ == "__main__":
    main()
