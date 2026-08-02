"""crosscheck_stats.py — correctness crosscheck for q6/q8/q9 against DuckDB
1.5.5 and Polars 1.43.1, on the SAME seeded dataset `generate.py` wrote.

This is deliberately separate from `run_baselines.py`/`run_composed_interleaved.py`:
those two intentionally omit q6/q8/q9 (their own docstrings say so — the query
plane had no grouped order-statistic or grouped co-moment primitives). This
script is the correctness half of closing that gap: it reads the Mojo engine's
per-group dump (`bench_h2o_stats dump <q6|q8|q9>`) and asserts it against an
independent DuckDB/Polars computation of the identical question, by GROUP KEY
(never by row position — a permuted group order must not look like a mismatch).

q6: grouped MEDIAN(v3) and STDDEV_SAMP(v3) by id4, id5.
q8: the two LARGEST v3 per id6 (H2O's actual query: row_number() over
    (partition by id6 order by v3 desc) <= 2). Ties in row_number's order among
    EQUAL v3 values are unspecified by SQL and physical-order-dependent; v3 is
    a continuous round(uniform(0,100), 6), so an exact duplicate inside one
    ~100-row group is astronomically unlikely and this script does not lean on
    tie-breaking to pass.
q9: R^2 = corr(v1, v2)^2 by id2, id4 — H2O's actual q9 metric (squared), not
    plain r.

Usage:
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/crosscheck_stats.py q6
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/crosscheck_stats.py q8
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/crosscheck_stats.py q9
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/crosscheck_stats.py all
"""
from __future__ import annotations

import sys

import duckdb
import numpy as np
import polars as pl

DATA_DIR = "/tmp/h2o_groupby"
EXPECTED_POLARS = "1.43.1"
EXPECTED_DUCKDB = "1.5.5"


def assert_versions() -> None:
    if pl.__version__ != EXPECTED_POLARS:
        raise SystemExit(f"polars {pl.__version__} != required {EXPECTED_POLARS}")
    if duckdb.__version__ != EXPECTED_DUCKDB:
        raise SystemExit(f"duckdb {duckdb.__version__} != required {EXPECTED_DUCKDB}")
    print(f"versions OK: polars {pl.__version__}, duckdb {duckdb.__version__}")


def build_frame(names: list[str]) -> tuple["pl.DataFrame", "duckdb.DuckDBPyConnection"]:
    cols = {n: np.load(f"{DATA_DIR}/{n}.npy") for n in names}
    for name, arr in cols.items():
        if arr.shape != (10_000_000,):
            raise SystemExit(f"{name}.npy has shape {arr.shape}, expected (1e7,)")
    df = pl.DataFrame(cols)
    con = duckdb.connect()
    con.register("df_view", df.to_pandas())
    con.execute("CREATE TABLE tbl AS SELECT * FROM df_view")
    return df, con


def read_dump(path: str, prefix: str) -> list[list[str]]:
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith(prefix + " "):
                rows.append(line.split())
    return rows


def check_q6(mojo_path: str) -> int:
    """median(v3), sd(v3) by id4, id5."""
    df, con = build_frame(["id4", "id5", "v3"])
    duck = con.execute(
        "SELECT id4, id5, count(v3) AS n, median(v3) AS med, "
        "stddev_samp(v3) AS sd FROM tbl GROUP BY id4, id5"
    ).fetchdf()
    duck_idx = {
        (int(r.id4), int(r.id5)): (int(r.n), float(r.med), r.sd)
        for r in duck.itertuples()
    }
    pl_res = df.group_by(["id4", "id5"]).agg(
        pl.len().alias("n"), pl.median("v3").alias("med"), pl.std("v3").alias("sd")
    )
    pl_idx = {
        (row["id4"], row["id5"]): (row["n"], row["med"], row["sd"])
        for row in pl_res.iter_rows(named=True)
    }

    rows = read_dump(mojo_path, "ROW6")
    if not rows:
        raise SystemExit(f"no ROW6 lines in {mojo_path}")
    print(f"q6: {len(rows)} Mojo groups, {len(duck_idx)} DuckDB groups, {len(pl_idx)} Polars groups")
    bad = 0
    checked_median = 0
    checked_sd = 0
    for r in rows:
        id4, id5, n, med, sd, present_sd = (
            int(r[1]), int(r[2]), int(r[3]), float(r[4]), float(r[5]), int(r[6])
        )
        key = (id4, id5)
        if key not in duck_idx:
            print(f"  MISSING in duckdb: {key}")
            bad += 1
            continue
        dn, dmed, dsd = duck_idx[key]
        pn, pmed, psd = pl_idx[key]
        if n != dn or n != pn:
            print(f"  COUNT MISMATCH {key}: mojo={n} duckdb={dn} polars={pn}")
            bad += 1
            continue
        rel = abs(med - dmed) / max(1.0, abs(dmed))
        if rel > 1e-9:
            print(f"  MEDIAN MISMATCH {key}: mojo={med} duckdb={dmed} polars={pmed}")
            bad += 1
        checked_median += 1
        if present_sd:
            if dsd is None or (isinstance(dsd, float) and dsd != dsd):
                print(f"  SD PRESENT MISMATCH {key}: mojo has sd, duckdb NULL")
                bad += 1
                continue
            rel_sd = abs(sd - dsd) / max(1.0, abs(dsd))
            if rel_sd > 1e-6:
                print(f"  SD MISMATCH {key}: mojo={sd} duckdb={dsd} polars={psd}")
                bad += 1
            checked_sd += 1
    print(f"q6: checked median={checked_median} sd={checked_sd} mismatches={bad}")
    return bad


def check_q8(mojo_path: str) -> int:
    """largest two v3 per id6."""
    df, con = build_frame(["id6", "v3"])
    duck = con.execute(
        "SELECT id6, max(v3) AS top1, "
        "(arg_max(v3, v3, 2))[2] AS top2_or_null, count(*) AS n "
        "FROM tbl GROUP BY id6"
    ).fetchdf()
    # arg_max(x, y, n) returns the n largest y's x's; here x=y=v3 so it's the
    # n largest v3 values themselves, most-recent-tie-order aside (values are
    # continuous so ties are moot). list[-1] is the SECOND largest when n>=2.
    duck2 = con.execute(
        "SELECT id6, list_sort(arg_max(v3, v3, 2), 'DESC') AS top2list, "
        "count(*) AS n FROM tbl GROUP BY id6"
    ).fetchdf()
    duck_idx = {}
    for r in duck2.itertuples():
        lst = list(r.top2list)
        duck_idx[int(r.id6)] = (lst, int(r.n))

    rows = read_dump(mojo_path, "ROW8")
    if not rows:
        raise SystemExit(f"no ROW8 lines in {mojo_path}")
    print(f"q8: {len(rows)} Mojo groups, {len(duck_idx)} DuckDB groups")
    bad = 0
    checked = 0
    for r in rows:
        id6, top1, p1, top2, p2 = (
            int(r[1]), float(r[2]), int(r[3]), float(r[4]), int(r[5])
        )
        key = id6
        if key not in duck_idx:
            print(f"  MISSING in duckdb: {key}")
            bad += 1
            continue
        lst, dn = duck_idx[key]
        if p1 != (dn >= 1):
            print(f"  PRESENT1 MISMATCH {key}: mojo={p1} n={dn}")
            bad += 1
            continue
        if dn >= 1:
            d_top1 = lst[0]
            if abs(top1 - d_top1) > 1e-6:
                print(f"  TOP1 MISMATCH {key}: mojo={top1} duckdb={d_top1}")
                bad += 1
        if p2 != (dn >= 2):
            print(f"  PRESENT2 MISMATCH {key}: mojo={p2} n={dn}")
            bad += 1
            continue
        if dn >= 2:
            d_top2 = lst[1]
            if abs(top2 - d_top2) > 1e-6:
                print(f"  TOP2 MISMATCH {key}: mojo={top2} duckdb={d_top2}")
                bad += 1
        checked += 1
    print(f"q8: checked={checked} mismatches={bad}")
    return bad


def check_q9(mojo_path: str) -> int:
    """R^2 = corr(v1, v2)^2 by id2, id4."""
    df, con = build_frame(["id2", "id4", "v1", "v2"])
    duck = con.execute(
        "SELECT id2, id4, count(*) AS n, "
        "pow(corr(v1, v2), 2) AS r2 FROM tbl GROUP BY id2, id4"
    ).fetchdf()
    duck_idx = {(int(r.id2), int(r.id4)): (int(r.n), r.r2) for r in duck.itertuples()}
    pl_res = df.group_by(["id2", "id4"]).agg(
        pl.len().alias("n"), pl.corr("v1", "v2").pow(2).alias("r2")
    )
    pl_idx = {
        (row["id2"], row["id4"]): (row["n"], row["r2"]) for row in pl_res.iter_rows(named=True)
    }

    rows = read_dump(mojo_path, "ROW9")
    if not rows:
        raise SystemExit(f"no ROW9 lines in {mojo_path}")
    print(f"q9: {len(rows)} Mojo groups, {len(duck_idx)} DuckDB groups, {len(pl_idx)} Polars groups")
    bad = 0
    checked = 0
    for r in rows:
        id2, id4, n, r2, present = (
            int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5])
        )
        key = (id2, id4)
        if key not in duck_idx:
            print(f"  MISSING in duckdb: {key}")
            bad += 1
            continue
        dn, dr2 = duck_idx[key]
        pn, pr2 = pl_idx[key]
        if n != dn or n != pn:
            print(f"  COUNT MISMATCH {key}: mojo={n} duckdb={dn} polars={pn}")
            bad += 1
            continue
        d_present = dr2 is not None and not (isinstance(dr2, float) and dr2 != dr2)
        if present != d_present:
            print(f"  PRESENT MISMATCH {key}: mojo={present} duckdb_present={d_present} dr2={dr2}")
            bad += 1
            continue
        if present:
            rel = abs(r2 - dr2) / max(1e-9, abs(dr2))
            if rel > 1e-6:
                print(f"  R2 MISMATCH {key}: mojo={r2} duckdb={dr2} polars={pr2}")
                bad += 1
        checked += 1
    print(f"q9: checked={checked} mismatches={bad}")
    return bad


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: crosscheck_stats.py <q6|q8|q9|all>")
    assert_versions()
    which = sys.argv[1]
    total_bad = 0
    if which in ("q6", "all"):
        total_bad += check_q6(f"{DATA_DIR}/mojo_dump_q6.txt")
    if which in ("q8", "all"):
        total_bad += check_q8(f"{DATA_DIR}/mojo_dump_q8.txt")
    if which in ("q9", "all"):
        total_bad += check_q9(f"{DATA_DIR}/mojo_dump_q9.txt")
    if total_bad:
        raise SystemExit(f"CROSSCHECK FAILED: {total_bad} mismatches")
    print("CROSSCHECK ALL OK")


if __name__ == "__main__":
    main()
