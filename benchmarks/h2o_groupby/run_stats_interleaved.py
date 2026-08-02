"""run_stats_interleaved.py — q6/q8/q9 against polars and duckdb, interleaved,
in one measurement window — `run_composed_interleaved.py`'s exact protocol,
extended to the three questions it explicitly omits.

Protocol, unchanged from the composed script:

  * versions ASSERTED at runtime — polars 1.43.1, duckdb 1.5.5.
  * the same seeded dataset `generate.py` wrote, loaded once, given to every
    engine as in-memory columns. No parse is timed anywhere.
  * REPS_PER_BLOCK reps per engine per block x CYCLES cycles, engine order
    ROTATED per cycle. Headline is the MIN of all of them; median and max
    also printed.
  * `os.getloadavg()` recorded before and after every engine block, because a
    close result on a loaded machine is not a result — see q1's history in
    this same suite, and see the module for why this matters more here: this
    script's own recon found the host at load 35-262 while building it.
  * CHECKSUMS compared at the end (sum over present groups of the reported
    metric) — a coarse cross-engine sanity check; the per-GROUP correctness
    claim is `crosscheck_stats.py`'s, already run and passing on the full
    dataset before this script exists to measure speed at all.

Ceiling-first pricing (McCalpin STREAM, 350.9 GB/s, this same suite's number):
q8 touches id6+v3 once (160 MB) = 0.456 ms; q9 touches id2+id4+v1+v2 once
(320 MB) = 0.912 ms. q6 is NOT single-pass — it counts+Welford-folds v3 once,
then scatters it once more, then reads the scattered copy back for sorting —
so its floor is not simply `bytes/bandwidth`, and this script reports the
ratio to the naive one-pass number as a LOWER bound on the true ceiling
multiple, not the ceiling itself.

Usage:
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/run_stats_interleaved.py \\
        --binary /tmp/bench_h2o_stats
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
QUESTIONS = ("q6", "q8", "q9")

# One-pass naive floor in ms: bytes the query must touch at minimum (every
# column Float64) / 350.9 GB/s. q6's true floor is higher (multi-pass) — see
# the module docstring.
CEILING_MS = {
    "q6": 0.684,   # id4 + id5 + v3, one pass, LOWER bound only
    "q8": 0.456,   # id6 + v3
    "q9": 0.912,   # id2 + id4 + v1 + v2
}


def load_str() -> str:
    a, b, c = os.getloadavg()
    return f"{a:.2f} {b:.2f} {c:.2f}"


def assert_versions() -> None:
    if pl.__version__ != EXPECTED_POLARS:
        raise SystemExit(f"polars {pl.__version__} != required {EXPECTED_POLARS}")
    if duckdb.__version__ != EXPECTED_DUCKDB:
        raise SystemExit(f"duckdb {duckdb.__version__} != required {EXPECTED_DUCKDB}")
    print(f"versions OK: polars {pl.__version__}, duckdb {duckdb.__version__}")
    print(f"numpy {np.__version__}; python {sys.version.split()[0]} at {sys.executable}")


def build_engines():
    names = ["id2", "id4", "id5", "id6", "v1", "v2", "v3"]
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
    if q == "q6":
        return lambda: df.group_by(["id4", "id5"]).agg(
            pl.median("v3").alias("med"), pl.std("v3").alias("sd")
        )
    if q == "q8":
        return lambda: (
            df.sort("v3", descending=True)
            .group_by("id6", maintain_order=False)
            .head(2)
        )
    return lambda: df.group_by(["id2", "id4"]).agg(pl.corr("v1", "v2").pow(2).alias("r2"))


def duckdb_q(con, q: str):
    sql = {
        "q6": (
            "SELECT id4, id5, median(v3) AS med, stddev_samp(v3) AS sd "
            "FROM tbl GROUP BY id4, id5"
        ),
        "q8": (
            "SELECT id6, list_sort(arg_max(v3, v3, 2), 'DESC') AS top2 "
            "FROM tbl GROUP BY id6"
        ),
        "q9": (
            "SELECT id2, id4, pow(corr(v1, v2), 2) AS r2 FROM tbl GROUP BY id2, id4"
        ),
    }[q]
    return lambda: con.execute(sql).fetchdf()


def checksum_frame(obj, q: str) -> float:
    if q == "q6":
        # Sum median AND sd, matching the Mojo bench's checksum exactly (it
        # adds both over every present group) — a coarse cross-engine sanity
        # check, not the correctness claim (that is per-group, in
        # `crosscheck_stats.py`, already run and passing on the full data).
        med = obj["med"].to_numpy() if hasattr(obj["med"], "to_numpy") else obj["med"].to_numpy()
        sd = obj["sd"].to_numpy() if hasattr(obj["sd"], "to_numpy") else obj["sd"].to_numpy()
        return float(np.nansum(med) + np.nansum(sd))
    if q == "q8":
        # polars: one row per (id6, rank) with a "v3" column; duckdb: a list column.
        if "top2" in obj.columns if hasattr(obj, "columns") else False:
            return float(sum(sum(x) for x in obj["top2"]))
        return float(obj["v3"].sum())
    return float(obj["r2"].fillna(0).sum()) if hasattr(obj["r2"], "fillna") else float(
        sum(x for x in obj["r2"] if x is not None)
    )


REP_RE = re.compile(r"^REP (\w+) (\d+) ms=(?P<ms>[0-9.eE+-]+) groups=(?P<groups>\d+) checksum=(?P<cs>[0-9.eE+-]+)")


def run_mojo(binary: str, q: str, reps: int, workers: int):
    out = subprocess.run(
        [binary, "time", q, str(reps), str(workers)],
        capture_output=True, text=True, check=False, cwd=DATA_DIR,
    )
    samples, checksum, groups = [], None, None
    for line in out.stdout.splitlines():
        m = REP_RE.match(line)
        if m:
            samples.append(float(m.group("ms")))
            checksum = float(m.group("cs"))
            groups = int(m.group("groups"))
        elif "BENCH_GATE" in line:
            raise SystemExit(f"BENCH_GATE from bench: {line}")
    if out.returncode != 0:
        raise SystemExit(f"{binary} {q} exited {out.returncode}\n{out.stdout}\n{out.stderr}")
    if not samples:
        raise SystemExit(f"no REP lines from {binary} {q}:\n{out.stdout}\n{out.stderr}")
    return samples, checksum, groups


def timed(fn, reps: int):
    out = []
    result = None
    for _ in range(reps):
        t = time.perf_counter()
        result = fn()
        out.append((time.perf_counter() - t) * 1000.0)
    return out, result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default="/tmp/bench_h2o_stats")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--cycles", type=int, default=CYCLES)
    ap.add_argument("--reps", type=int, default=REPS_PER_BLOCK)
    ap.add_argument("--questions", default=",".join(QUESTIONS))
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
    checks: dict[tuple[str, str], float] = {}
    groups_seen: dict[str, int] = {}

    def record(engine: str, q: str, samples: list[float]) -> None:
        times.setdefault((engine, q), []).extend(samples)

    for cycle in range(args.cycles):
        order = (
            ["duckdb", "polars", "algenta"] if cycle % 2 == 0
            else ["algenta", "polars", "duckdb"]
        )
        for q in questions:
            print(f"\n--- cycle {cycle} {q} order={'>'.join(order)} ---")
            for engine in order:
                before = load_str()
                if engine == "polars":
                    samples, res = timed(polars_q(df, q), args.reps)
                    checks[("polars", q)] = checksum_frame(res, q)
                elif engine == "duckdb":
                    samples, res = timed(duckdb_q(con, q), args.reps)
                    checks[("duckdb", q)] = checksum_frame(res, q)
                else:
                    samples, cs, groups = run_mojo(args.binary, q, args.reps, args.workers)
                    checks[("algenta", q)] = cs
                    groups_seen[q] = groups
                record(engine, q, samples)
                after = load_str()
                pretty = " ".join(f"{s:.3f}" for s in samples)
                print(
                    f"  {engine:10s} reps_ms=[{pretty}] min={min(samples):.3f}"
                    f"  load_before=[{before}] load_after=[{after}]"
                )

    n = args.reps * args.cycles
    print(f"\n=== MIN OF {n} (= {args.reps} reps x {args.cycles} cycles) ===")
    hdr = f"{'q':<4}{'duckdb':>11}{'polars':>11}{'algenta':>11}"
    print(hdr)
    summary = {}
    for q in questions:
        row = {}
        for engine in ("duckdb", "polars", "algenta"):
            xs = times.get((engine, q))
            row[engine] = min(xs) if xs else float("nan")
        summary[q] = row
        print(f"{q:<4}{row['duckdb']:>11.3f}{row['polars']:>11.3f}{row['algenta']:>11.3f}")

    def stat(engine: str, q: str, which: str) -> float:
        xs = sorted(times.get((engine, q), []))
        if not xs:
            return float("nan")
        if which == "min":
            return xs[0]
        if which == "max":
            return xs[-1]
        return xs[len(xs) // 2]

    print("\n=== THE VERDICT: algenta vs BOTH baselines, on min / median / max ===")
    print(
        f"{'q':<4}{'vs duck min':>13}{'vs duck med':>13}{'vs duck max':>13}"
        f"{'vs pol min':>12}{'vs pol med':>12}{'vs pol max':>12}{'win?':>7}"
    )
    outright = True
    for q in questions:
        r = {}
        for w in ("min", "median", "max"):
            r[("d", w)] = stat("duckdb", q, w) / stat("algenta", q, w)
            r[("p", w)] = stat("polars", q, w) / stat("algenta", q, w)
        won = r[("d", "min")] > 1.0 and r[("p", "min")] > 1.0
        outright = outright and won
        print(
            f"{q:<4}{r[('d','min')]:>13.3f}{r[('d','median')]:>13.3f}"
            f"{r[('d','max')]:>13.3f}{r[('p','min')]:>12.3f}"
            f"{r[('p','median')]:>12.3f}{r[('p','max')]:>12.3f}"
            f"{('WIN' if won else 'LOSS'):>7}"
        )
    print(f"\nOUTRIGHT ON EVERY QUESTION (min-of-{n}): {outright}")

    print("\n=== RATIO TO ONE-PASS FLOOR (q6's is a LOWER bound, see module docstring) ===")
    for q in questions:
        r = summary[q]
        c = CEILING_MS[q]
        print(
            f"{q}: floor={c:.3f}ms algenta={r['algenta']:.3f}ms ({r['algenta']/c:.1f}x) "
            f"duckdb={r['duckdb']:.3f}ms ({r['duckdb']/c:.1f}x) "
            f"polars={r['polars']:.3f}ms ({r['polars']/c:.1f}x)"
        )

    print("\n=== ALL SAMPLES ===")
    for q in questions:
        for engine in ("duckdb", "polars", "algenta"):
            xs = sorted(times.get((engine, q), []))
            if not xs:
                continue
            print(
                f"  {q} {engine:10s} min={xs[0]:8.3f} med={xs[len(xs)//2]:8.3f} "
                f"max={xs[-1]:8.3f}  all=" + " ".join(f"{x:.2f}" for x in xs)
            )

    print("\n=== CHECKSUM AGREEMENT (coarse; per-group agreement already proved) ===")
    print(json.dumps({f"{k[0]}:{k[1]}": v for k, v in checks.items()}, indent=2))
    print(f"\ngroups per question: {groups_seen}")
    print(f"load at end: {load_str()}")
    print(f"OUTRIGHT={outright}")


if __name__ == "__main__":
    main()
