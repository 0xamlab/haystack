"""Polars and DuckDB baselines for the H2O groupby questions the Mojo bench runs.

Times q1-q5 and q7 of the h2oai/db-benchmark groupby suite (0.5 GB tier: N=1e7,
K=100) on the SAME integer-coded data `generate.py` wrote, on the same machine.
Both engines get in-memory columns (no CSV parse timed) and their default
parallelism. Prints the load average before and after so a loaded machine is
visible in the record rather than hidden in the variance.

The checksum per question matches what bench_h2o_groupby.mojo prints (sum over
groups of every aggregated column), so cross-engine agreement is checked, not
assumed.

q6 (grouped median), q8 (top-2 per group) and q9 (grouped corr) are omitted on
purpose: the Mojo query plane does not support grouped order statistics or
grouped co-moments yet, and timing the baselines on questions we cannot answer
would not be a comparison.

Run with an interpreter that has polars + duckdb + pandas + numpy, e.g.:
    /tmp/bb/bin/python -P benchmarks/h2o_groupby/run_baselines.py
"""

import json
import os
import time

import duckdb
import numpy as np
import polars as pl

DATA_DIR = "/tmp/h2o_groupby"
REPS = 3


def loadavg() -> str:
    return "%.2f %.2f %.2f" % os.getloadavg()


def main() -> None:
    print(f"load before: {loadavg()}")
    cols = {
        name: np.load(os.path.join(DATA_DIR, f"{name}.npy"))
        for name in ["id1", "id2", "id3", "id4", "id6", "v1", "v2", "v3"]
    }
    df = pl.DataFrame(cols)
    con = duckdb.connect()
    con.register("df_view", df.to_pandas())
    con.execute("CREATE TABLE tbl AS SELECT * FROM df_view")

    polars_queries = {
        "q1": lambda: df.group_by("id1").agg(pl.sum("v1")),
        "q2": lambda: df.group_by("id1", "id2").agg(pl.sum("v1")),
        "q3": lambda: df.group_by("id3").agg(pl.sum("v1"), pl.mean("v3")),
        "q4": lambda: df.group_by("id4").agg(
            pl.mean("v1"), pl.mean("v2"), pl.mean("v3")
        ),
        "q5": lambda: df.group_by("id6").agg(
            pl.sum("v1"), pl.sum("v2"), pl.sum("v3")
        ),
        "q7": lambda: df.group_by("id3").agg(
            (pl.max("v1") - pl.min("v2")).alias("range_v1_v2")
        ),
    }
    duckdb_queries = {
        "q1": "SELECT id1, SUM(v1) AS s FROM tbl GROUP BY id1",
        "q2": "SELECT id1, id2, SUM(v1) AS s FROM tbl GROUP BY id1, id2",
        "q3": "SELECT id3, SUM(v1) AS s, AVG(v3) AS m FROM tbl GROUP BY id3",
        "q4": (
            "SELECT id4, AVG(v1) AS m1, AVG(v2) AS m2, AVG(v3) AS m3"
            " FROM tbl GROUP BY id4"
        ),
        "q5": (
            "SELECT id6, SUM(v1) AS s1, SUM(v2) AS s2, SUM(v3) AS s3"
            " FROM tbl GROUP BY id6"
        ),
        "q7": (
            "SELECT id3, MAX(v1) - MIN(v2) AS r FROM tbl GROUP BY id3"
        ),
    }

    results: dict[str, dict[str, list[float]]] = {}
    checksums: dict[str, dict[str, float]] = {"polars": {}, "duckdb": {}}
    for rep in range(REPS):
        print(f"--- rep {rep} (load {loadavg()}) ---")
        for q in polars_queries:
            t0 = time.perf_counter()
            out = polars_queries[q]()
            t_pl = time.perf_counter() - t0
            agg_cols = [c for c in out.columns if not c.startswith("id")]
            checksums["polars"][q] = float(
                sum(out[c].sum() for c in agg_cols)
            )
            t0 = time.perf_counter()
            rel = con.execute(duckdb_queries[q])
            arr = rel.fetchnumpy()
            t_db = time.perf_counter() - t0
            agg_keys = [k for k in arr if not k.startswith("id")]
            checksums["duckdb"][q] = float(sum(arr[k].sum() for k in agg_keys))
            results.setdefault(q, {"polars": [], "duckdb": []})
            results[q]["polars"].append(t_pl)
            results[q]["duckdb"].append(t_db)
            print(
                f"  {q}: polars {t_pl:.4f}s (groups={out.height})"
                f"  duckdb {t_db:.4f}s"
            )

    print(f"load after: {loadavg()}")
    print(json.dumps({"times": results, "checksums": checksums}, indent=2))


if __name__ == "__main__":
    main()
