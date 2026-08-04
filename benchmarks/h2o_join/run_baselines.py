"""Polars and DuckDB baselines for the H2O join questions the Mojo bench runs.

Times q1-q5 of the h2oai/db-benchmark join suite (0.5 GB tier: N=1e7 fact rows) on
the SAME integer-coded data `generate.py` wrote, on the same machine. Both engines get
in-memory columns (no CSV parse timed) and their default parallelism.

q4 in the official suite joins on id5, the STRING form of id2. This project's own H2O
groupby page already established the convention of feeding every engine the SAME
integer dictionary codes rather than strings (see its Method section); this file
follows that same convention for q4, so q4 here is the identical operation to q2 for
every engine, not an independent measurement of string-vs-int join cost. See
`benchmarks/mojo_benchmarks/bench_h2o_join.mojo`'s docstring for the full rationale.

The checksum per question (sum(v1) + sum(v2) over the joined result) matches what
`bench_h2o_join.mojo` prints, so cross-engine agreement is checked, not assumed.

Run with an interpreter that has polars + duckdb + numpy, e.g.:
    /tmp/bb/bin/python benchmarks/h2o_join/run_baselines.py
"""

import json
import os
import time

import duckdb
import numpy as np
import polars as pl

DATA_DIR = "/tmp/h2o_join"
REPS = 3
EXPECT_DUCKDB = "1.5.5"
EXPECT_POLARS = "1.43.1"


def loadavg() -> str:
    return "%.2f %.2f %.2f" % os.getloadavg()


def _load(table: str, col: str) -> np.ndarray:
    return np.load(os.path.join(DATA_DIR, f"{table}_{col}.npy"))


def main() -> None:
    assert duckdb.__version__ == EXPECT_DUCKDB, (
        f"expected duckdb {EXPECT_DUCKDB}, got {duckdb.__version__}"
    )
    assert pl.__version__ == EXPECT_POLARS, (
        f"expected polars {EXPECT_POLARS}, got {pl.__version__}"
    )
    print(f"duckdb {duckdb.__version__}  polars {pl.__version__}")
    print(f"load before: {loadavg()}")

    x = pl.DataFrame(
        {
            "id1": _load("x", "id1"),
            "id2": _load("x", "id2"),
            "id3": _load("x", "id3"),
            "v1": _load("x", "v1"),
        }
    )
    small = pl.DataFrame({"id1": _load("small", "id1"), "v2": _load("small", "v2")})
    medium = pl.DataFrame(
        {
            "id1": _load("medium", "id1"),
            "id2": _load("medium", "id2"),
            "v2": _load("medium", "v2"),
        }
    )
    big = pl.DataFrame(
        {
            "id1": _load("big", "id1"),
            "id2": _load("big", "id2"),
            "id3": _load("big", "id3"),
            "v2": _load("big", "v2"),
        }
    )

    con = duckdb.connect()
    con.register("x_view", x.to_arrow())
    con.register("small_view", small.to_arrow())
    con.register("medium_view", medium.to_arrow())
    con.register("big_view", big.to_arrow())
    con.execute("CREATE TABLE x AS SELECT * FROM x_view")
    con.execute("CREATE TABLE small AS SELECT * FROM small_view")
    con.execute("CREATE TABLE medium AS SELECT * FROM medium_view")
    con.execute("CREATE TABLE big AS SELECT * FROM big_view")
    con.execute(f"PRAGMA THREADS={os.cpu_count()}")

    polars_queries = {
        "q1": lambda: x.join(small, on="id1", how="inner"),
        "q2": lambda: x.join(medium, on="id2", how="inner"),
        "q3": lambda: x.join(medium, on="id2", how="left"),
        "q4": lambda: x.join(medium, on="id2", how="inner"),  # id2 stands in for id5
        "q5": lambda: x.join(big, on="id3", how="inner"),
    }
    duckdb_queries = {
        "q1": "SELECT x.*, small.v2 AS v2 FROM x JOIN small USING (id1)",
        "q2": "SELECT x.*, medium.id1 AS medium_id1, medium.v2 AS v2 FROM x JOIN medium USING (id2)",
        "q3": "SELECT x.*, medium.id1 AS medium_id1, medium.v2 AS v2 FROM x LEFT JOIN medium USING (id2)",
        "q4": "SELECT x.*, medium.id1 AS medium_id1, medium.v2 AS v2 FROM x JOIN medium USING (id2)",
        "q5": (
            "SELECT x.*, big.id1 AS big_id1, big.id2 AS big_id2, big.v2 AS v2"
            " FROM x JOIN big USING (id3)"
        ),
    }

    results: dict[str, dict[str, list[float]]] = {}
    checksums: dict[str, dict[str, float]] = {"polars": {}, "duckdb": {}}
    row_counts: dict[str, dict[str, int]] = {"polars": {}, "duckdb": {}}
    for rep in range(REPS):
        print(f"--- rep {rep} (load {loadavg()}) ---")
        for q in polars_queries:
            t0 = time.perf_counter()
            out = polars_queries[q]()
            t_pl = time.perf_counter() - t0
            checksums["polars"][q] = float(out["v1"].sum()) + float(out["v2"].sum())
            row_counts["polars"][q] = out.height

            t0 = time.perf_counter()
            rel = con.execute(duckdb_queries[q])
            arr = rel.fetchnumpy()
            t_db = time.perf_counter() - t0
            checksums["duckdb"][q] = float(np.nansum(arr["v1"])) + float(
                np.nansum(arr["v2"])
            )
            row_counts["duckdb"][q] = len(arr["v1"])

            results.setdefault(q, {"polars": [], "duckdb": []})
            results[q]["polars"].append(t_pl)
            results[q]["duckdb"].append(t_db)
            print(
                f"  {q}: polars {t_pl:.4f}s (rows={out.height})"
                f"  duckdb {t_db:.4f}s (rows={row_counts['duckdb'][q]})"
            )

    print(f"load after: {loadavg()}")
    print(
        json.dumps(
            {"times": results, "checksums": checksums, "row_counts": row_counts},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
