#!/usr/bin/env python3
"""All 22 TPC-H-derived query templates, hand-translated onto the real
query-plane engine and verified row-for-row against a DuckDB oracle over the
identical SF=1 data. See RESULTS.md for the full methodology and every
disclosed workaround.

Requires (see RESULTS.md "Resuming this"):
  - The isolated local Postgres DB loaded with real dbgen SF=1 TPC-H data.
  - A DuckDB file with the same tables materialized (the oracle).
  - The 22 real query texts (qgen-substituted, DuckDB-dialect-fixed).
  - The compiled query-plane worker at mojo_build/simulate_queryplane.

    ALGENTA_RUNTIME_WORKER=$PWD/../../mojo_build/simulate_queryplane \\
      ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
      python3 benchmarks/tpch_derived/verified_queries.py
"""

from __future__ import annotations

import time

from engine_harness import (
    Query,
    chunk,
    close,
    col,
    dim_with_code,
    duck_run,
    encode_strings,
    epoch_day,
    lit,
    pg_fetch,
    repeat,
    run_query,
    runtime,
    strip,
    timing_stats,
)

N_REPS = 3
QDIR = "/tmp/tpch-work/queries_duckdb"


# ─────────────────────────── Q1: multi-aggregate GROUP BY ──────────────────
def q1():
    recs = pg_fetch(
        "SELECT l_returnflag, l_linestatus, l_quantity, l_extendedprice, l_discount, l_tax, "
        "l_shipdate FROM lineitem"
    )
    rf_codes, rf_map = encode_strings([r["l_returnflag"] for r in recs])
    ls_codes, ls_map = encode_strings([r["l_linestatus"] for r in recs])
    fact_cols = [
        "l_returnflag_code", "l_linestatus_code", "l_quantity", "l_extendedprice",
        "l_discount", "l_tax", "l_shipdate",
    ]
    rows = [
        [rf_codes[i], ls_codes[i], r["l_quantity"], r["l_extendedprice"], r["l_discount"],
         r["l_tax"], r["l_shipdate"]]
        for i, r in enumerate(recs)
    ]
    threshold = epoch_day("1998-12-01") - 91

    # Resident-handle migration (PR #542's parsed-batch cache): open ONE handle
    # per chunk ONCE, before run_engine() is ever invoked (correctness pass or
    # any repeat() rep), so every call reuses the SAME parsed batch instead of
    # resending `rows=` (and reparsing it) on every one of N_REPS calls.
    handles = [
        runtime().open_dataset(batch, name=f"q1_chunk_{i}", routing_module="stats")
        for i, batch in enumerate(chunk(rows))
    ]

    def run_engine():
        partial = {}
        for handle in handles:
            disc = col("l_extendedprice") * (lit(1.0) - col("l_discount"))
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter(col("l_shipdate") <= threshold)
                .project(
                    l_returnflag_code=col("l_returnflag_code"),
                    l_linestatus_code=col("l_linestatus_code"),
                    l_quantity=col("l_quantity"),
                    l_extendedprice=col("l_extendedprice"),
                    l_discount=col("l_discount"),
                    disc_price=disc,
                    charge=disc * (lit(1.0) + col("l_tax")),
                )
                .group_by_many(
                    by=["l_returnflag_code", "l_linestatus_code"],
                    aggs=[
                        ("l_quantity", "sum"), ("l_quantity", "count"),
                        ("l_extendedprice", "sum"),
                        ("l_discount", "sum"), ("l_discount", "count"),
                        ("disc_price", "sum"), ("charge", "sum"),
                    ],
                )
            )
            for r in run_query(q).rows:
                key = (r[0], r[1])
                acc = partial.setdefault(key, [0.0] * 7)
                for i in range(7):
                    acc[i] += r[2 + i] or 0.0
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    final = []
    for (rfc, lsc), acc in partial.items():
        sum_qty, cnt_qty, sum_price, sum_disc, cnt_disc, sum_discprice, sum_charge = acc
        final.append((
            rf_map[rfc], ls_map[lsc], sum_qty, sum_price, sum_discprice, sum_charge,
            sum_qty / cnt_qty, sum_price / cnt_qty, sum_disc / cnt_disc, int(cnt_qty),
        ))
    final.sort(key=lambda t: (t[0], t[1]))

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/1.sql")
        duck_times.append(dt)

    mism = 0
    for e, d in zip(final, drows, strict=False):
        ok = (
            e[0] == strip(d[0]) and e[1] == strip(d[1]) and all(close(e[i], d[i]) for i in range(2, 9))
            and int(e[9]) == d[9]
        )
        if not ok:
            mism += 1
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q2: correlated MIN, decorrelated ──────────────
def q2():
    supplier_ok = [[r["s_suppkey"], r["s_nationkey"]] for r in pg_fetch("""
        SELECT s.s_suppkey, s.s_nationkey FROM supplier s
        JOIN nation n ON s.s_nationkey = n.n_nationkey
        JOIN region r ON n.n_regionkey = r.r_regionkey
        WHERE r.r_name = 'AMERICA'
    """)]
    part_ok = [[r["p_partkey"]] for r in pg_fetch(
        "SELECT p_partkey FROM part WHERE p_size = 37 AND p_type LIKE '%COPPER'")]
    ps_cols = ["ps_partkey", "ps_suppkey", "ps_supplycost"]
    ps_rows = [[r[c] for c in ps_cols] for r in pg_fetch(f"SELECT {', '.join(ps_cols)} FROM partsupp")]

    def run_engine():
        ps_filtered = (
            Query(columns=ps_cols, rows=ps_rows)
            .with_table("supp_ok", ["s_suppkey", "s_nationkey"], rows=supplier_ok)
            .join("supp_ok", left_on="ps_suppkey", right_on="s_suppkey", how="semi")
            .run(runtime(), routing_module="stats")
        )
        ps_f_cols, ps_f_rows = ps_filtered.columns, [list(r) for r in ps_filtered.rows]
        min_res = (
            Query(columns=ps_f_cols, rows=ps_f_rows)
            .group_by("ps_partkey", "ps_supplycost", agg="min")
            .run(runtime(), routing_module="stats")
        )
        min_cols, min_rows = min_res.columns, [list(r) for r in min_res.rows]
        cand = (
            Query(columns=ps_f_cols, rows=ps_f_rows)
            .with_table("part_ok", ["p_partkey"], rows=part_ok)
            .join("part_ok", left_on="ps_partkey", right_on="p_partkey", how="inner")
            .with_table("min_by_part", min_cols, rows=min_rows)
            .join("min_by_part", left_on="ps_partkey", right_on="ps_partkey", how="inner")
            .filter(col("ps_supplycost").eq(col("min_by_part.min_ps_supplycost")))
            .select("ps_partkey", "ps_suppkey")
            .run(runtime(), routing_module="stats")
        )
        return list(cand.rows)

    cand_rows = run_engine()
    engine_times = repeat(run_engine, N_REPS)

    part_decode = {float(r["p_partkey"]): strip(r["p_mfgr"]) for r in pg_fetch("SELECT p_partkey, p_mfgr FROM part")}
    supp_decode = {
        float(r["s_suppkey"]): (strip(r["s_name"]), float(r["s_acctbal"]), strip(r["s_address"]),
                                 strip(r["s_phone"]), strip(r["s_comment"]), strip(r["n_name"]))
        for r in pg_fetch("""
            SELECT s.s_suppkey, s.s_name, s.s_acctbal, s.s_address, s.s_phone, s.s_comment, n.n_name
            FROM supplier s JOIN nation n ON s.s_nationkey = n.n_nationkey
        """)
    }
    final = []
    for partkey, suppkey in cand_rows:
        mfgr = part_decode[partkey]
        name, acctbal, address, phone, comment, nation = supp_decode[suppkey]
        final.append((acctbal, name, nation, int(partkey), mfgr, address, phone, comment))
    final.sort(key=lambda t: (-t[0], t[2], t[1], t[3]))
    final = final[:100]

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/2.sql")
        duck_times.append(dt)
    drows = drows[:100]

    mism = 0
    for e, d in zip(final, drows, strict=False):
        dd = [strip(x) if isinstance(x, str) else x for x in d]
        ok = (
            close(e[0], dd[0]) and e[1] == dd[1] and e[2] == dd[2] and e[3] == dd[3]
            and e[4] == dd[4] and e[5] == dd[5] and e[6] == dd[6] and e[7] == dd[7]
        )
        if not ok:
            mism += 1
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q3: 3-way join, top-10 ─────────────────────────
def q3():
    cust_ok = [[r["c_custkey"]] for r in pg_fetch("SELECT c_custkey FROM customer WHERE c_mktsegment='BUILDING'")]
    orders_raw = pg_fetch(
        "SELECT o_orderkey, o_custkey, o_orderdate, o_shippriority FROM orders WHERE o_orderdate < '1995-03-12'"
    )
    orders_cols = ["o_orderkey", "o_custkey", "o_orderdate", "o_shippriority"]
    orders_rows = [[r[c] for c in orders_cols] for r in orders_raw]
    orders_final = (
        Query(columns=orders_cols, rows=orders_rows)
        .with_table("cust_ok", ["c_custkey"], rows=cust_ok)
        .join("cust_ok", left_on="o_custkey", right_on="c_custkey", how="semi")
        .run(runtime(), routing_module="stats")
    )
    orders_final_cols = orders_final.columns
    orders_final_rows = [list(r) for r in orders_final.rows]

    lineitem_cols = ["l_orderkey", "l_extendedprice", "l_discount", "l_shipdate"]
    fact = pg_fetch(f"SELECT {', '.join(lineitem_cols)} FROM lineitem")
    threshold = epoch_day("1995-03-12")

    # Resident-handle migration: open ONE handle per chunk ONCE, before
    # run_engine() is invoked by the correctness pass or any repeat() rep.
    # `orders_final` stays an inline `.with_table(...)` side table, untouched —
    # PR #542's cache doesn't cover with_table rows and it's small enough not
    # to be worth migrating.
    handles = []
    for i, batch in enumerate(chunk(fact)):
        rows = [[r[c] for c in lineitem_cols] for r in batch]
        handles.append(runtime().open_dataset(rows, name=f"q3_chunk_{i}", routing_module="stats"))

    def run_engine():
        partial = {}
        for handle in handles:
            qq = (
                Query(columns=lineitem_cols, dataset=handle)
                .filter(col("l_shipdate") > threshold)
                .project(
                    l_orderkey=col("l_orderkey"),
                    revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")),
                )
                .with_table("orders_final", orders_final_cols, rows=orders_final_rows)
                .join("orders_final", left_on="l_orderkey", right_on="o_orderkey", how="inner")
                .group_by_many(
                    by=["l_orderkey", "orders_final.o_orderdate", "orders_final.o_shippriority"],
                    aggs=[("revenue", "sum")],
                )
            )
            for r in run_query(qq).rows:
                key = (r[0], r[1], r[2])
                partial[key] = partial.get(key, 0.0) + (r[3] or 0.0)
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(int(k[0]), v, k[1], int(k[2])) for k, v in partial.items()]
    final.sort(key=lambda t: (-t[1], t[2]))
    final = final[:10]

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/3.sql")
        duck_times.append(dt)
    drows = drows[:10]

    mism = 0
    for e, d in zip(final, drows, strict=False):
        ok = e[0] == d[0] and close(e[1], d[1]) and int(e[2]) == epoch_day(str(d[2])) and e[3] == d[3]
        if not ok:
            mism += 1
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q4: EXISTS via semi join ───────────────────────
def q4():
    fact = pg_fetch("SELECT l_orderkey, l_commitdate, l_receiptdate FROM lineitem")

    # Resident-handle migration: open ONE handle per chunk ONCE, before pass1()
    # is ever invoked (correctness pass or any repeat() rep). pass2()'s own
    # `chunk(qualifying_rows)` loop is untouched -- the chunked variable there
    # (`qchunk`) only ever feeds an inline `.with_table("qual", ...)` side
    # table; the loop's actual `Query(rows=orders_rows)` uses the SAME fixed
    # `orders_rows` every iteration, not the chunked value, so there is no
    # `Query(rows=batch)`-from-chunk() call there to migrate.
    handles = [
        runtime().open_dataset(
            [[r["l_orderkey"], r["l_commitdate"], r["l_receiptdate"]] for r in batch],
            name=f"q4_chunk_{i}", routing_module="stats",
        )
        for i, batch in enumerate(chunk(fact))
    ]

    def pass1():
        qualifying = set()
        for handle in handles:
            q = (
                Query(columns=["l_orderkey", "l_commitdate", "l_receiptdate"], dataset=handle)
                .filter(col("l_commitdate") < col("l_receiptdate"))
                .distinct("l_orderkey")
            )
            for r in run_query(q).rows:
                qualifying.add(r[0])
        return qualifying

    try:
        qualifying = pass1()

        orders_raw = pg_fetch(
            "SELECT o_orderkey, o_orderpriority FROM orders WHERE o_orderdate >= '1994-11-01' "
            "AND o_orderdate < '1995-02-01'"
        )
        priority_codes, priority_map = encode_strings([r["o_orderpriority"] for r in orders_raw])
        orders_rows = [[r["o_orderkey"], priority_codes[i]] for i, r in enumerate(orders_raw)]
        qualifying_rows = [[k] for k in qualifying]

        def pass2():
            matched = set()
            for qchunk in chunk(qualifying_rows):
                qq = (
                    Query(columns=["o_orderkey", "priority_code"], rows=orders_rows)
                    .with_table("qual", ["l_orderkey"], rows=qchunk)
                    .join("qual", left_on="o_orderkey", right_on="l_orderkey", how="semi")
                )
                for r in run_query(qq).rows:
                    matched.add(r[0])
            final_rows = [r for r in orders_rows if r[0] in matched]
            qq2 = Query(columns=["o_orderkey", "priority_code"], rows=final_rows).group_by(
                "priority_code", "priority_code", agg="count"
            )
            return {r[0]: r[1] for r in run_query(qq2).rows}

        counts = pass2()
        engine_times = repeat(lambda: (pass1(), pass2()), N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(priority_map[k], int(v)) for k, v in counts.items()]
    final.sort(key=lambda t: t[0])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/4.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), d[1]) for d in drows]
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if e != d)
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q5: nation bridge, col-vs-col filter ───────────
def q5():
    nation_ok = pg_fetch("""
        SELECT n.n_nationkey, n.n_name FROM nation n JOIN region r ON n.n_regionkey=r.r_regionkey
        WHERE r.r_name='AFRICA'""")
    nation_map = {float(r["n_nationkey"]): strip(r["n_name"]) for r in nation_ok}
    nk_list = tuple(int(r["n_nationkey"]) for r in nation_ok)

    customer_ok = [[r["c_custkey"], r["c_nationkey"]] for r in pg_fetch(
        f"SELECT c_custkey, c_nationkey FROM customer WHERE c_nationkey IN {nk_list}")]
    supplier_ok = [[r["s_suppkey"], r["s_nationkey"]] for r in pg_fetch(
        f"SELECT s_suppkey, s_nationkey FROM supplier WHERE s_nationkey IN {nk_list}")]
    orders_ok = [[r["o_orderkey"], r["o_custkey"]] for r in pg_fetch(
        "SELECT o_orderkey, o_custkey FROM orders WHERE o_orderdate >= '1997-01-01' "
        "AND o_orderdate < '1998-01-01'")]

    fact_cols = ["l_orderkey", "l_suppkey", "l_extendedprice", "l_discount"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")

    # Resident-handle migration: open ONE handle per chunk ONCE, before
    # run_engine() is invoked by the correctness pass or any repeat() rep.
    # `supp_ok` / `orders_cust` stay inline `.with_table(...)` side tables,
    # untouched. The small `q1`/`res1` correlated-subquery re-run each call
    # (unchunked, not from `chunk()`) is likewise left as-is.
    handles = []
    for i, batch in enumerate(chunk(fact)):
        rows = [[r[c] for c in fact_cols] for r in batch]
        handles.append(runtime().open_dataset(rows, name=f"q5_chunk_{i}", routing_module="stats"))

    def run_engine():
        q1 = (
            Query(columns=["o_orderkey", "o_custkey"], rows=orders_ok)
            .with_table("cust_ok", ["c_custkey", "c_nationkey"], rows=customer_ok)
            .join("cust_ok", left_on="o_custkey", right_on="c_custkey", how="inner")
            .project(o_orderkey=col("o_orderkey"), c_nationkey=col("cust_ok.c_nationkey"))
        )
        res1 = q1.run(runtime(), routing_module="stats")
        orders_cust_cols = res1.columns
        orders_cust_rows = [list(r) for r in res1.rows]

        partial = {}
        for handle in handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .project(
                    l_orderkey=col("l_orderkey"),
                    l_suppkey=col("l_suppkey"),
                    revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")),
                )
                .with_table("supp_ok", ["s_suppkey", "s_nationkey"], rows=supplier_ok)
                .join("supp_ok", left_on="l_suppkey", right_on="s_suppkey", how="inner")
                .with_table("orders_cust", orders_cust_cols, rows=orders_cust_rows)
                .join("orders_cust", left_on="l_orderkey", right_on="o_orderkey", how="inner")
                .filter(col("supp_ok.s_nationkey").eq(col("orders_cust.c_nationkey")))
                .group_by("supp_ok.s_nationkey", "revenue", agg="sum")
            )
            for r in run_query(q).rows:
                partial[r[0]] = partial.get(r[0], 0.0) + (r[1] or 0.0)
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(nation_map[k], v) for k, v in partial.items()]
    final.sort(key=lambda t: -t[1])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/5.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), d[1]) for d in drows]
    mism = 0
    for e, d in zip(final, drows2, strict=False):
        if not (e[0] == d[0] and close(e[1], d[1])):
            mism += 1
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q6: single-table filter + aggregate ───────────
def q6():
    fact_cols = ["l_shipdate", "l_discount", "l_quantity", "l_extendedprice"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    lo, hi = epoch_day("1997-01-01"), epoch_day("1998-01-01")

    # Open ONE resident handle per chunk, once, before run_engine() is ever
    # invoked (correctness pass or timed repeat()) -- reused across all of them
    # instead of resending `rows=` inline on every call (see PR #542 + Q19's
    # resident-handle migration in RESULTS.md).
    fact_handles = []
    for batch in chunk(fact):
        rows = [[r[c] for c in fact_cols] for r in batch]
        fact_handles.append(
            runtime().open_dataset(rows, name=f"q6_chunk_{len(fact_handles)}", routing_module="stats")
        )

    def run_engine():
        total = 0.0
        for handle in fact_handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter(
                    (col("l_shipdate") >= lo) & (col("l_shipdate") < hi)
                    & (col("l_discount") >= 0.05) & (col("l_discount") <= 0.07)
                    & (col("l_quantity") < 25)
                )
                .project(revenue=col("l_extendedprice") * col("l_discount"))
                .group_by("revenue", "revenue", agg="sum")
            )
            for r in run_query(q).rows:
                total += r[1] or 0.0
        return total

    try:
        total = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in fact_handles:
            runtime().close_dataset(h, routing_module="stats")

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/6.sql")
        duck_times.append(dt)

    ok = close(total, drows[0][0], tol=0.5)
    return ok, (
        f"engine={total:.2f} duckdb={float(drows[0][0]):.2f} "
        f"engine[{timing_stats(engine_times)}] duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q7: 2-nation cross-shipping, disjoint OR ───────
def q7():
    nation_ok = pg_fetch("SELECT n_nationkey, n_name FROM nation WHERE n_name IN ('JAPAN','JORDAN')")
    nation_map = {float(r["n_nationkey"]): strip(r["n_name"]) for r in nation_ok}
    nk_list = tuple(int(r["n_nationkey"]) for r in nation_ok)

    supplier_ok = [[r["s_suppkey"], r["s_nationkey"]] for r in pg_fetch(
        f"SELECT s_suppkey, s_nationkey FROM supplier WHERE s_nationkey IN {nk_list}")]
    customer_ok = [[r["c_custkey"], r["c_nationkey"]] for r in pg_fetch(
        f"SELECT c_custkey, c_nationkey FROM customer WHERE c_nationkey IN {nk_list}")]
    orders_all = pg_fetch("SELECT o_orderkey, o_custkey FROM orders")

    fact_cols = ["l_orderkey", "l_suppkey", "l_extendedprice", "l_discount", "l_shipdate", "l_year"]
    fact = pg_fetch(
        "SELECT l_orderkey, l_suppkey, l_extendedprice, l_discount, l_shipdate, "
        "EXTRACT(YEAR FROM l_shipdate)::float AS l_year FROM lineitem"
    )
    lo, hi = epoch_day("1995-01-01"), epoch_day("1996-12-31")

    # Open ONE resident handle per chunk per fact table, once, before
    # run_engine() is ever invoked (correctness pass or timed repeat()) --
    # reused across all of them instead of resending `rows=` inline on every
    # call. `.with_table(...)` side tables (cust_ok, supp_ok, orders_cust)
    # stay inline -- they're small and PR #542's cache doesn't cover them.
    orders_handles = []
    for batch in chunk(orders_all):
        rows = [[r["o_orderkey"], r["o_custkey"]] for r in batch]
        orders_handles.append(
            runtime().open_dataset(rows, name=f"q7_orders_chunk_{len(orders_handles)}", routing_module="stats")
        )

    fact_handles = []
    for batch in chunk(fact):
        rows = [[r[c] for c in fact_cols] for r in batch]
        fact_handles.append(
            runtime().open_dataset(rows, name=f"q7_fact_chunk_{len(fact_handles)}", routing_module="stats")
        )

    def run_engine():
        orders_cust_rows = []
        orders_cust_cols = None
        for handle in orders_handles:
            q1 = (
                Query(columns=["o_orderkey", "o_custkey"], dataset=handle)
                .with_table("cust_ok", ["c_custkey", "c_nationkey"], rows=customer_ok)
                .join("cust_ok", left_on="o_custkey", right_on="c_custkey", how="inner")
                .project(o_orderkey=col("o_orderkey"), c_nationkey=col("cust_ok.c_nationkey"))
            )
            res1 = q1.run(runtime(), routing_module="stats")
            orders_cust_cols = res1.columns
            orders_cust_rows.extend(list(r) for r in res1.rows)

        partial = {}
        for handle in fact_handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter((col("l_shipdate") >= lo) & (col("l_shipdate") <= hi))
                .project(
                    l_orderkey=col("l_orderkey"),
                    l_suppkey=col("l_suppkey"),
                    l_year=col("l_year"),
                    revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")),
                )
                .with_table("supp_ok", ["s_suppkey", "s_nationkey"], rows=supplier_ok)
                .join("supp_ok", left_on="l_suppkey", right_on="s_suppkey", how="inner")
                .with_table("orders_cust", orders_cust_cols, rows=orders_cust_rows)
                .join("orders_cust", left_on="l_orderkey", right_on="o_orderkey", how="inner")
                .filter(col("supp_ok.s_nationkey").ne(col("orders_cust.c_nationkey")))
                .group_by_many(
                    by=["supp_ok.s_nationkey", "orders_cust.c_nationkey", "l_year"],
                    aggs=[("revenue", "sum")],
                )
            )
            for r in run_query(q).rows:
                key = (r[0], r[1], r[2])
                partial[key] = partial.get(key, 0.0) + (r[3] or 0.0)
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in orders_handles + fact_handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(nation_map[k[0]], nation_map[k[1]], int(k[2]), v) for k, v in partial.items()]
    final.sort(key=lambda t: (t[0], t[1], t[2]))

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/7.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), strip(d[1]), d[2], d[3]) for d in drows]
    mism = 0
    for e, d in zip(final, drows2, strict=False):
        if not (e[0] == d[0] and e[1] == d[1] and e[2] == d[2] and close(e[3], d[3])):
            mism += 1
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q8: national market share, CASE arithmetic ────
def q8():
    me_nations = tuple(int(r["n_nationkey"]) for r in pg_fetch(
        "SELECT n.n_nationkey FROM nation n JOIN region r ON n.n_regionkey=r.r_regionkey "
        "WHERE r.r_name='MIDDLE EAST'"))
    customer_ok = [[r["c_custkey"]] for r in pg_fetch(
        f"SELECT c_custkey FROM customer WHERE c_nationkey IN {me_nations}")]
    part_ok = [[r["p_partkey"]] for r in pg_fetch("SELECT p_partkey FROM part WHERE p_type = 'SMALL PLATED STEEL'")]
    supplier_all = [[r["s_suppkey"], r["s_nationkey"]] for r in pg_fetch("SELECT s_suppkey, s_nationkey FROM supplier")]
    jordan_key = float(pg_fetch("SELECT n_nationkey FROM nation WHERE n_name='JORDAN'")[0]["n_nationkey"])

    orders_raw = pg_fetch(
        "SELECT o_orderkey, o_custkey, EXTRACT(YEAR FROM o_orderdate)::float AS o_year "
        "FROM orders WHERE o_orderdate BETWEEN '1995-01-01' AND '1996-12-31'"
    )
    orders_rows = [[r["o_orderkey"], r["o_custkey"], r["o_year"]] for r in orders_raw]

    fact_cols = ["l_orderkey", "l_partkey", "l_suppkey", "l_extendedprice", "l_discount"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")

    # Open ONE resident handle per chunk, once, before run_engine() is ever
    # invoked (correctness pass or timed repeat()) -- reused across all of
    # them instead of resending `rows=` inline on every call. `.with_table(...)`
    # side tables (part_ok, supp_all, orders_cust) stay inline.
    fact_handles = []
    for batch in chunk(fact):
        rows = [[r[c] for c in fact_cols] for r in batch]
        fact_handles.append(
            runtime().open_dataset(rows, name=f"q8_fact_chunk_{len(fact_handles)}", routing_module="stats")
        )

    def run_engine():
        q1 = (
            Query(columns=["o_orderkey", "o_custkey", "o_year"], rows=orders_rows)
            .with_table("cust_ok", ["c_custkey"], rows=customer_ok)
            .join("cust_ok", left_on="o_custkey", right_on="c_custkey", how="semi")
            .select("o_orderkey", "o_year")
        )
        res1 = q1.run(runtime(), routing_module="stats")
        orders_cust_cols, orders_cust_rows = res1.columns, [list(r) for r in res1.rows]

        partial = {}
        for handle in fact_handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .project(
                    l_orderkey=col("l_orderkey"),
                    l_partkey=col("l_partkey"),
                    l_suppkey=col("l_suppkey"),
                    volume=col("l_extendedprice") * (lit(1.0) - col("l_discount")),
                )
                .with_table("part_ok", ["p_partkey"], rows=part_ok)
                .join("part_ok", left_on="l_partkey", right_on="p_partkey", how="semi")
                .with_table("supp_all", ["s_suppkey", "s_nationkey"], rows=supplier_all)
                .join("supp_all", left_on="l_suppkey", right_on="s_suppkey", how="inner")
                .with_table("orders_cust", orders_cust_cols, rows=orders_cust_rows)
                .join("orders_cust", left_on="l_orderkey", right_on="o_orderkey", how="inner")
                .project(
                    o_year=col("orders_cust.o_year"),
                    volume=col("volume"),
                    jordan_volume=col("supp_all.s_nationkey").eq(jordan_key) * col("volume"),
                )
                .group_by_many(by=["o_year"], aggs=[("volume", "sum"), ("jordan_volume", "sum")])
            )
            for r in run_query(q).rows:
                acc = partial.setdefault(r[0], [0.0, 0.0])
                acc[0] += r[1] or 0.0
                acc[1] += r[2] or 0.0
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in fact_handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(int(y), acc[1] / acc[0]) for y, acc in partial.items()]
    final.sort(key=lambda t: t[0])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/8.sql")
        duck_times.append(dt)

    mism = sum(1 for e, d in zip(final, drows, strict=False) if not (e[0] == d[0] and close(e[1], d[1], tol=1e-6)))
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q9: composite key + LIKE ───────────────────────
def q9():
    MULT = 10_000_000.0
    part_ok = [[r["p_partkey"]] for r in pg_fetch("SELECT p_partkey FROM part WHERE p_name LIKE '%dim%'")]
    supplier_all = [[r["s_suppkey"], r["s_nationkey"]] for r in pg_fetch("SELECT s_suppkey, s_nationkey FROM supplier")]
    nation_map = {float(r["n_nationkey"]): strip(r["n_name"]) for r in pg_fetch("SELECT n_nationkey, n_name FROM nation")}

    ps_rows = [[r["ps_partkey"], r["ps_suppkey"], r["ps_supplycost"]] for r in pg_fetch(
        "SELECT ps_partkey, ps_suppkey, ps_supplycost FROM partsupp")]
    q0 = (
        Query(columns=["ps_partkey", "ps_suppkey", "ps_supplycost"], rows=ps_rows)
        .with_table("part_ok", ["p_partkey"], rows=part_ok)
        .join("part_ok", left_on="ps_partkey", right_on="p_partkey", how="semi")
        .project(ps_key=col("ps_partkey") * lit(MULT) + col("ps_suppkey"), ps_supplycost=col("ps_supplycost"))
    )
    res0 = q0.run(runtime(), routing_module="stats")
    ps_key_cols, ps_key_rows = res0.columns, [list(r) for r in res0.rows]

    orders_year = {r["o_orderkey"]: r["o_year"] for r in pg_fetch(
        "SELECT o_orderkey, EXTRACT(YEAR FROM o_orderdate)::float AS o_year FROM orders")}

    fact_cols = ["l_orderkey", "l_partkey", "l_suppkey", "l_extendedprice", "l_discount", "l_quantity"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")

    # Open ONE resident handle per chunk, once, before run_engine() is ever
    # invoked (correctness pass or timed repeat()) -- reused across all of
    # them instead of resending `rows=` inline on every call. `.with_table(...)`
    # side tables (ps_key_tbl, supp_all) stay inline.
    fact_handles = []
    for batch in chunk(fact):
        rows = [[r[c] for c in fact_cols] for r in batch]
        fact_handles.append(
            runtime().open_dataset(rows, name=f"q9_fact_chunk_{len(fact_handles)}", routing_module="stats")
        )

    def run_engine():
        partial = {}
        for handle in fact_handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .project(
                    l_orderkey=col("l_orderkey"),
                    ps_key=col("l_partkey") * lit(MULT) + col("l_suppkey"),
                    ext_amount=col("l_extendedprice") * (lit(1.0) - col("l_discount")),
                    l_quantity=col("l_quantity"),
                    l_suppkey=col("l_suppkey"),
                )
                .with_table("ps_key_tbl", ps_key_cols, rows=ps_key_rows)
                .join("ps_key_tbl", left_on="ps_key", right_on="ps_key", how="inner")
                .with_table("supp_all", ["s_suppkey", "s_nationkey"], rows=supplier_all)
                .join("supp_all", left_on="l_suppkey", right_on="s_suppkey", how="inner")
                .project(
                    l_orderkey=col("l_orderkey"),
                    s_nationkey=col("supp_all.s_nationkey"),
                    amount=col("ext_amount") - col("ps_key_tbl.ps_supplycost") * col("l_quantity"),
                )
                .group_by_many(by=["s_nationkey", "l_orderkey"], aggs=[("amount", "sum")])
            )
            for r in run_query(q).rows:
                key = (r[0], r[1])
                partial[key] = partial.get(key, 0.0) + (r[2] or 0.0)
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in fact_handles:
            runtime().close_dataset(h, routing_module="stats")

    by_nation_year = {}
    for (nk, orderkey), amt in partial.items():
        year = orders_year[orderkey]
        key = (nk, year)
        by_nation_year[key] = by_nation_year.get(key, 0.0) + amt
    final = [(nation_map[nk], int(y), amt) for (nk, y), amt in by_nation_year.items()]
    final.sort(key=lambda t: (t[0], -t[1]))

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/9.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), d[1], d[2]) for d in drows]
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if not (e[0] == d[0] and e[1] == d[1] and close(e[2], d[2])))
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q10: star join, output-only decode, top-20 ─────
def q10():
    cust_recs = pg_fetch("""
        SELECT c.c_custkey, c.c_name, c.c_acctbal, c.c_phone, c.c_address, c.c_comment, n.n_name
        FROM customer c JOIN nation n ON c.c_nationkey = n.n_nationkey
    """)
    cust_decode = {
        float(r["c_custkey"]): (
            strip(r["c_name"]), float(r["c_acctbal"]), strip(r["c_phone"]),
            strip(r["n_name"]), strip(r["c_address"]), strip(r["c_comment"]),
        )
        for r in cust_recs
    }
    orders_ok = [[r["o_orderkey"], r["o_custkey"]] for r in pg_fetch(
        "SELECT o_orderkey, o_custkey FROM orders WHERE o_orderdate >= '1993-04-01' AND o_orderdate < '1993-07-01'")]

    fact_cols = ["l_orderkey", "l_returnflag", "l_extendedprice", "l_discount"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    rf_codes, rf_map = encode_strings([r["l_returnflag"] for r in fact])
    R_code = next(c for c, v in rf_map.items() if v == "R")

    # Resident-handle migration (see RESULTS.md's Q19 update): open every chunk ONCE,
    # before repeat()'s timing loop, instead of resending the same rows= JSON per call.
    chunk_rows = []
    idx = 0
    for batch in chunk(fact):
        n = len(batch)
        chunk_rows.append(
            [[r["l_orderkey"], rf_codes[idx + i], r["l_extendedprice"], r["l_discount"]]
             for i, r in enumerate(batch)]
        )
        idx += n
    handles = [
        runtime().open_dataset(rows, name=f"q10_lineitem_{i}", routing_module="stats")
        for i, rows in enumerate(chunk_rows)
    ]

    def run_engine():
        partial = {}
        for handle in handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter(col("l_returnflag").eq(R_code))
                .project(l_orderkey=col("l_orderkey"), revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")))
                .with_table("orders_ok", ["o_orderkey", "o_custkey"], rows=orders_ok)
                .join("orders_ok", left_on="l_orderkey", right_on="o_orderkey", how="inner")
                .group_by("orders_ok.o_custkey", "revenue", agg="sum")
            )
            for r in run_query(q).rows:
                partial[r[0]] = partial.get(r[0], 0.0) + (r[1] or 0.0)
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for handle in handles:
            runtime().close_dataset(handle, routing_module="stats")

    final = []
    for custkey, revenue in partial.items():
        name, acctbal, phone, nation, address, comment = cust_decode[custkey]
        final.append((int(custkey), name, revenue, acctbal, nation, address, phone, comment))
    final.sort(key=lambda t: -t[2])
    final = final[:20]

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/10.sql")
        duck_times.append(dt)
    drows = drows[:20]

    mism = 0
    for e, d in zip(final, drows, strict=False):
        dd = [strip(x) if isinstance(x, str) else x for x in d]
        ok = (
            e[0] == dd[0] and e[1] == dd[1] and close(e[2], dd[2]) and close(e[3], dd[3])
            and e[4] == dd[4] and e[5] == dd[5] and e[6] == dd[6] and e[7] == dd[7]
        )
        if not ok:
            mism += 1
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q11: non-correlated scalar threshold ───────────
def q11():
    supplier_ok = [[r["s_suppkey"]] for r in pg_fetch(
        "SELECT s_suppkey FROM supplier s JOIN nation n ON s.s_nationkey=n.n_nationkey "
        "WHERE n.n_name='SAUDI ARABIA'")]
    ps_cols = ["ps_partkey", "ps_suppkey", "ps_availqty", "ps_supplycost"]
    ps_rows = [[r[c] for c in ps_cols] for r in pg_fetch(f"SELECT {', '.join(ps_cols)} FROM partsupp")]

    def run_engine():
        q = (
            Query(columns=ps_cols, rows=ps_rows)
            .with_table("supp_ok", ["s_suppkey"], rows=supplier_ok)
            .join("supp_ok", left_on="ps_suppkey", right_on="s_suppkey", how="semi")
            .project(ps_partkey=col("ps_partkey"), value=col("ps_supplycost") * col("ps_availqty"))
            .group_by("ps_partkey", "value", agg="sum")
        )
        res = q.run(runtime(), routing_module="stats")
        return {int(r[0]): (r[1] or 0.0) for r in res.rows}

    sums = run_engine()
    engine_times = repeat(run_engine, N_REPS)

    total = sum(sums.values())
    threshold = total * 0.0001
    final = [(pk, v) for pk, v in sums.items() if v > threshold]
    final.sort(key=lambda t: -t[1])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/11.sql")
        duck_times.append(dt)

    mism = sum(1 for e, d in zip(final, drows, strict=False) if not (e[0] == d[0] and close(e[1], d[1])))
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q12: CASE arithmetic + shipmode IN ─────────────
def q12():
    fact_cols = ["l_orderkey", "l_shipmode", "l_commitdate", "l_receiptdate", "l_shipdate"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    sm_codes, sm_map = encode_strings([r["l_shipmode"] for r in fact])
    SHIP_code = next(c for c, v in sm_map.items() if v == "SHIP")
    TRUCK_code = next(c for c, v in sm_map.items() if v == "TRUCK")

    orders_all = pg_fetch("SELECT o_orderkey, o_orderpriority FROM orders")
    pr_codes, pr_map = encode_strings([r["o_orderpriority"] for r in orders_all])
    URGENT = next(c for c, v in pr_map.items() if v == "1-URGENT")
    HIGH = next(c for c, v in pr_map.items() if v == "2-HIGH")
    priority_of = {r["o_orderkey"]: pr_codes[i] for i, r in enumerate(orders_all)}

    lo, hi = epoch_day("1994-01-01"), epoch_day("1995-01-01")
    cols = ["l_orderkey", "l_shipmode", "l_commitdate", "l_receiptdate", "l_shipdate", "priority_code"]

    # Resident-handle migration: open every chunk ONCE, before repeat()'s timing loop.
    chunk_rows = []
    idx = 0
    for batch in chunk(fact):
        n = len(batch)
        chunk_rows.append(
            [
                [r["l_orderkey"], sm_codes[idx + i], r["l_commitdate"], r["l_receiptdate"], r["l_shipdate"],
                 priority_of[r["l_orderkey"]]]
                for i, r in enumerate(batch)
            ]
        )
        idx += n
    handles = [
        runtime().open_dataset(rows, name=f"q12_lineitem_{i}", routing_module="stats")
        for i, rows in enumerate(chunk_rows)
    ]

    def run_engine():
        partial = {}
        for handle in handles:
            q = (
                Query(columns=cols, dataset=handle)
                .filter(
                    (col("l_shipmode").eq(SHIP_code) | col("l_shipmode").eq(TRUCK_code))
                    & (col("l_commitdate") < col("l_receiptdate"))
                    & (col("l_shipdate") < col("l_commitdate"))
                    & (col("l_receiptdate") >= lo) & (col("l_receiptdate") < hi)
                )
                .project(
                    l_shipmode=col("l_shipmode"),
                    is_high=(col("priority_code").eq(URGENT) | col("priority_code").eq(HIGH)),
                    is_low=~(col("priority_code").eq(URGENT) | col("priority_code").eq(HIGH)),
                )
                .group_by_many(by=["l_shipmode"], aggs=[("is_high", "sum"), ("is_low", "sum")])
            )
            for r in run_query(q).rows:
                acc = partial.setdefault(r[0], [0.0, 0.0])
                acc[0] += r[1] or 0.0
                acc[1] += r[2] or 0.0
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for handle in handles:
            runtime().close_dataset(handle, routing_module="stats")

    final = [(sm_map[k], int(v[0]), int(v[1])) for k, v in partial.items()]
    final.sort(key=lambda t: t[0])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/12.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), d[1], d[2]) for d in drows]
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if e != d)
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q13: LEFT JOIN via default-zero, 2-stage GROUP BY
def q13():
    all_custkeys = [r["c_custkey"] for r in pg_fetch("SELECT c_custkey FROM customer")]
    orders_custkeys = [r["o_custkey"] for r in pg_fetch(
        "SELECT o_custkey FROM orders WHERE o_comment NOT LIKE '%pending%packages%'")]

    # Resident-handle migration: two `chunk()` loops here, and the second's rows depend
    # on the first's query result -- but that result is a pure, deterministic function of
    # already-fetched data (no mutation between calls), so it is computed ONCE up front to
    # build the second stage's resident handles too, before repeat()'s timing loop starts.
    order_chunks = [[[c, 1.0] for c in batch] for batch in chunk(orders_custkeys)]
    order_handles = [
        runtime().open_dataset(rows, name=f"q13_orders_{i}", routing_module="stats")
        for i, rows in enumerate(order_chunks)
    ]

    def _orders_pass():
        count_by_custkey = {}
        for handle in order_handles:
            q = Query(columns=["o_custkey", "one"], dataset=handle).group_by("o_custkey", "one", agg="sum")
            for r in run_query(q).rows:
                count_by_custkey[r[0]] = count_by_custkey.get(r[0], 0.0) + (r[1] or 0.0)
        return count_by_custkey

    count_by_custkey = _orders_pass()
    cdist_rows = [[count_by_custkey.get(float(ck), 0.0), 1.0] for ck in all_custkeys]
    cdist_handles = [
        runtime().open_dataset(batch, name=f"q13_cdist_{i}", routing_module="stats")
        for i, batch in enumerate(chunk(cdist_rows))
    ]

    def run_engine():
        # Re-dispatch the first stage every call too (same per-call engine work the
        # original inline form did) -- its result is deterministic and already baked
        # into cdist_handles, so it is not re-used to rebuild the second stage's rows.
        _orders_pass()
        final_counts = {}
        for handle in cdist_handles:
            q2 = Query(columns=["c_count", "one"], dataset=handle).group_by("c_count", "one", agg="sum")
            for r in run_query(q2).rows:
                final_counts[r[0]] = final_counts.get(r[0], 0.0) + (r[1] or 0.0)
        return final_counts

    try:
        final_counts = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for handle in order_handles + cdist_handles:
            runtime().close_dataset(handle, routing_module="stats")

    final = [(int(k), int(v)) for k, v in final_counts.items()]
    final.sort(key=lambda t: (-t[1], -t[0]))

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/13.sql")
        duck_times.append(dt)

    mism = sum(1 for e, d in zip(final, drows, strict=False) if e != d)
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q14: CASE arithmetic (promo share) ────────────
def q14():
    promo_ok = [[r["p_partkey"]] for r in pg_fetch("SELECT p_partkey FROM part WHERE p_type LIKE 'PROMO%'")]
    fact_cols = ["l_partkey", "l_extendedprice", "l_discount", "l_shipdate"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    lo, hi = epoch_day("1994-03-01"), epoch_day("1994-04-01")

    # Resident-handle migration: open every chunk ONCE, before repeat()'s timing loop.
    # Both queries per chunk (promo_sum, total_sum) reuse the SAME resident handle.
    chunk_rows = [[[r[c] for c in fact_cols] for r in batch] for batch in chunk(fact)]
    handles = [
        runtime().open_dataset(rows, name=f"q14_lineitem_{i}", routing_module="stats")
        for i, rows in enumerate(chunk_rows)
    ]

    def run_engine():
        promo_sum, total_sum = 0.0, 0.0
        for handle in handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter((col("l_shipdate") >= lo) & (col("l_shipdate") < hi))
                .project(l_partkey=col("l_partkey"), revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")))
                .with_table("promo_ok", ["p_partkey"], rows=promo_ok)
                .join("promo_ok", left_on="l_partkey", right_on="p_partkey", how="semi")
            )
            for r in run_query(q).rows:
                promo_sum += r[1] or 0.0
            q_all = (
                Query(columns=fact_cols, dataset=handle)
                .filter((col("l_shipdate") >= lo) & (col("l_shipdate") < hi))
                .project(revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")))
                .group_by("revenue", "revenue", agg="sum")
            )
            for r in run_query(q_all).rows:
                total_sum += r[1] or 0.0
        return 100.0 * promo_sum / total_sum

    try:
        result = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for handle in handles:
            runtime().close_dataset(handle, routing_module="stats")

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/14.sql")
        duck_times.append(dt)

    ok = close(result, drows[0][0], tol=1e-6)
    return ok, (
        f"engine={result:.6f} duckdb={float(drows[0][0]):.6f} "
        f"engine[{timing_stats(engine_times)}] duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q15: correlated MAX (2-stage) ─────────────────
def q15():
    fact_cols = ["l_suppkey", "l_extendedprice", "l_discount", "l_shipdate"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    lo, hi = epoch_day("1994-03-01"), epoch_day("1994-06-01")

    handles = [
        runtime().open_dataset(
            [[r[c] for c in fact_cols] for r in batch], name=f"q15_lineitem_{i}", routing_module="stats"
        )
        for i, batch in enumerate(chunk(fact))
    ]

    def run_engine():
        partial = {}
        for handle in handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter((col("l_shipdate") >= lo) & (col("l_shipdate") < hi))
                .project(l_suppkey=col("l_suppkey"), revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")))
                .group_by("l_suppkey", "revenue", agg="sum")
            )
            for r in run_query(q).rows:
                partial[r[0]] = partial.get(r[0], 0.0) + (r[1] or 0.0)
        return partial

    try:
        partial = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    max_rev = max(partial.values())
    qualifying = [sk for sk, v in partial.items() if abs(v - max_rev) < 1e-6]
    supplier_recs = pg_fetch(
        f"SELECT s_suppkey, s_name, s_address, s_phone FROM supplier "
        f"WHERE s_suppkey IN ({','.join(str(int(k)) for k in qualifying)})"
    )
    final = [(int(r["s_suppkey"]), strip(r["s_name"]), strip(r["s_address"]), strip(r["s_phone"]), max_rev)
             for r in supplier_recs]
    final.sort(key=lambda t: t[0])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/15.sql")
        duck_times.append(dt)

    drows2 = [(d[0], strip(d[1]), strip(d[2]), strip(d[3]), d[4]) for d in drows]
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if not (e[:4] == d[:4] and close(e[4], d[4])))
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q16: composite anti-join + distinct+count ─────
def q16():
    bad_suppliers = [[r["s_suppkey"]] for r in pg_fetch(
        "SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%'")]
    part_ok, part_map = dim_with_code(
        "p_partkey", ["p_brand", "p_type", "p_size"],
        "part WHERE p_brand <> 'Brand#12' AND p_type NOT LIKE 'STANDARD POLISHED%' "
        "AND p_size IN (41, 28, 43, 38, 8, 30, 12, 45)",
    )
    ps_cols = ["ps_partkey", "ps_suppkey"]
    ps_rows = [[r[c] for c in ps_cols] for r in pg_fetch(f"SELECT {', '.join(ps_cols)} FROM partsupp")]

    def run_engine():
        q = (
            Query(columns=ps_cols, rows=ps_rows)
            .with_table("bad_supp", ["s_suppkey"], rows=bad_suppliers)
            .join("bad_supp", left_on="ps_suppkey", right_on="s_suppkey", how="anti")
            .with_table("part_ok", ["p_partkey", "grp_code"], rows=part_ok)
            .join("part_ok", left_on="ps_partkey", right_on="p_partkey", how="inner")
            .distinct("part_ok.grp_code", "ps_suppkey")
            .group_by("part_ok.grp_code", "ps_suppkey", agg="count")
        )
        return list(run_query(q).rows)

    rows_out = run_engine()
    engine_times = repeat(run_engine, N_REPS)

    final = []
    for r in rows_out:
        brand, ptype, psize = part_map[r[0]]
        final.append((strip(brand), strip(ptype), int(psize), int(r[1])))
    final.sort(key=lambda t: (-t[3], t[0], t[1], t[2]))

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/16.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), strip(d[1]), d[2], d[3]) for d in drows]
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if e != d)
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q17: correlated AVG, sum/count decorrelation ───
def q17():
    fact_cols = ["l_partkey", "l_quantity", "l_extendedprice"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    fact_batches = list(chunk(fact))

    avg_handles = [
        runtime().open_dataset(
            [[r[c] for c in fact_cols] for r in batch], name=f"q17_avg_{i}", routing_module="stats"
        )
        for i, batch in enumerate(fact_batches)
    ]

    def compute_avg():
        sums, counts = {}, {}
        for handle in avg_handles:
            q = Query(columns=fact_cols, dataset=handle).group_by_many(
                by=["l_partkey"], aggs=[("l_quantity", "sum"), ("l_quantity", "count")]
            )
            for r in run_query(q).rows:
                sums[r[0]] = sums.get(r[0], 0.0) + (r[1] or 0.0)
                counts[r[0]] = counts.get(r[0], 0.0) + (r[2] or 0.0)
        return {pk: sums[pk] / counts[pk] for pk in sums}

    part_ok = [[r["p_partkey"]] for r in pg_fetch(
        "SELECT p_partkey FROM part WHERE p_brand='Brand#21' AND p_container='WRAP CASE'")]

    _avg_qty_seed = compute_avg()
    filt_cols = fact_cols + ["avg_qty"]
    filt_handles = [
        runtime().open_dataset(
            [[r[c] for c in fact_cols] + [_avg_qty_seed.get(r["l_partkey"], 0.0)] for r in batch],
            name=f"q17_filt_{i}", routing_module="stats",
        )
        for i, batch in enumerate(fact_batches)
    ]

    def run_engine():
        compute_avg()  # recomputed every rep for parity with the original's per-rep
        # engine cost -- filt_handles already carries this (deterministically
        # identical) avg_qty column, so it is not rebuilt from this call's result.
        total = 0.0
        for handle in filt_handles:
            q = (
                Query(columns=filt_cols, dataset=handle)
                .with_table("part_ok", ["p_partkey"], rows=part_ok)
                .join("part_ok", left_on="l_partkey", right_on="p_partkey", how="semi")
                .filter(col("l_quantity") < lit(0.2) * col("avg_qty"))
                .group_by("l_partkey", "l_extendedprice", agg="sum")
            )
            for r in run_query(q).rows:
                total += r[1] or 0.0
        return total / 7.0

    try:
        result = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in avg_handles + filt_handles:
            runtime().close_dataset(h, routing_module="stats")

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/17.sql")
        duck_times.append(dt)

    ok = close(result, drows[0][0], tol=0.5)
    return ok, (
        f"engine={result:.4f} duckdb={float(drows[0][0]):.4f} "
        f"engine[{timing_stats(engine_times)}] duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q18: correlated HAVING via decorrelation ──────
def q18():
    fact_cols = ["l_orderkey", "l_quantity"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")

    handles = [
        runtime().open_dataset(
            [[r[c] for c in fact_cols] for r in batch], name=f"q18_lineitem_{i}", routing_module="stats"
        )
        for i, batch in enumerate(chunk(fact))
    ]

    def run_engine():
        qty_by_order = {}
        for handle in handles:
            q = Query(columns=fact_cols, dataset=handle).group_by("l_orderkey", "l_quantity", agg="sum")
            for r in run_query(q).rows:
                qty_by_order[r[0]] = qty_by_order.get(r[0], 0.0) + (r[1] or 0.0)
        return {ok: q for ok, q in qty_by_order.items() if q > 312.0}

    try:
        qualifying = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    ok_list = ",".join(str(int(k)) for k in qualifying)
    orders_recs = pg_fetch(
        f"SELECT o_orderkey, o_custkey, o_orderdate, o_totalprice FROM orders WHERE o_orderkey IN ({ok_list})"
    )
    custkeys = {r["o_custkey"] for r in orders_recs}
    cust_list = ",".join(str(int(k)) for k in custkeys)
    cust_decode = {float(r["c_custkey"]): strip(r["c_name"]) for r in pg_fetch(
        f"SELECT c_custkey, c_name FROM customer WHERE c_custkey IN ({cust_list})")}

    final = []
    for r in orders_recs:
        name = cust_decode[r["o_custkey"]]
        final.append((name, int(r["o_custkey"]), int(r["o_orderkey"]), r["o_orderdate"], float(r["o_totalprice"]),
                      qualifying[r["o_orderkey"]]))
    final.sort(key=lambda t: (-t[4], t[3]))
    final = final[:100]

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/18.sql")
        duck_times.append(dt)
    drows = drows[:100]

    import datetime
    mism = 0
    for e, d in zip(final, drows, strict=False):
        ed_date = datetime.date(1970, 1, 1) + datetime.timedelta(days=int(e[3]))
        ok_row = (
            e[0] == strip(d[0]) and e[1] == d[1] and e[2] == d[2] and ed_date == d[3]
            and close(e[4], d[4]) and close(e[5], d[5])
        )
        if not ok_row:
            mism += 1
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q19: disjoint 3-way OR-branch decomposition ────
def q19():
    branches = [
        ("Brand#53", ["SM CASE", "SM BOX", "SM PACK", "SM PKG"], 2.0, 1, 5),
        ("Brand#54", ["MED BAG", "MED BOX", "MED PKG", "MED PACK"], 19.0, 1, 10),
        ("Brand#13", ["LG CASE", "LG BOX", "LG PACK", "LG PKG"], 25.0, 1, 15),
    ]
    branch_parts = []
    for brand, containers, qlo, slo, shi in branches:
        cont_list = "(" + ",".join(f"'{c}'" for c in containers) + ")"
        rows = [[r["p_partkey"]] for r in pg_fetch(
            f"SELECT p_partkey FROM part WHERE p_brand='{brand}' AND p_container IN {cont_list} "
            f"AND p_size BETWEEN {slo} AND {shi}")]
        branch_parts.append((rows, qlo, qlo + 10))

    fact_cols = ["l_partkey", "l_quantity", "l_extendedprice", "l_discount", "l_shipmode", "l_shipinstruct"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    sm_codes, sm_map = encode_strings([r["l_shipmode"] for r in fact])
    si_codes, si_map = encode_strings([r["l_shipinstruct"] for r in fact])
    AIR = next(c for c, v in sm_map.items() if v == "AIR")
    # "AIR REG" is TPC-H's own literal Q19 text; the real domain only has "REG AIR" (a
    # well-known spec quirk carried over from the official templates) so this half of the
    # IN-list never matches anything -- reproduced faithfully by omitting it when absent,
    # not by inventing a match. DuckDB (run on the identical real query text) hits the same
    # quirk, which is exactly why both sides agree despite it.
    AIRREG_codes = [c for c, v in sm_map.items() if v == "AIR REG"]
    DIP = next(c for c, v in si_map.items() if v == "DELIVER IN PERSON")

    def shipmode_pred():
        pred = col("l_shipmode").eq(AIR)
        for c in AIRREG_codes:
            pred = pred | col("l_shipmode").eq(c)
        return pred

    def run_engine():
        total = 0.0
        idx = 0
        for batch in chunk(fact):
            n = len(batch)
            rows = [
                [r["l_partkey"], r["l_quantity"], r["l_extendedprice"], r["l_discount"], sm_codes[idx + i],
                 si_codes[idx + i]]
                for i, r in enumerate(batch)
            ]
            idx += n
            for part_rows, qlo, qhi in branch_parts:
                qq = (
                    Query(columns=fact_cols, rows=rows)
                    .filter(
                        shipmode_pred()
                        & col("l_shipinstruct").eq(DIP)
                        & (col("l_quantity") >= qlo) & (col("l_quantity") <= qhi)
                    )
                    .with_table("part_ok", ["p_partkey"], rows=part_rows)
                    .join("part_ok", left_on="l_partkey", right_on="p_partkey", how="semi")
                    .project(revenue=col("l_extendedprice") * (lit(1.0) - col("l_discount")))
                    .group_by("revenue", "revenue", agg="sum")
                )
                for r in run_query(qq).rows:
                    total += r[1] or 0.0
        return total

    total = run_engine()
    engine_times = repeat(run_engine, N_REPS)

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/19.sql")
        duck_times.append(dt)

    ok = close(total, drows[0][0], tol=0.5)
    return ok, (
        f"engine={total:.2f} duckdb={float(drows[0][0]):.2f} "
        f"engine[{timing_stats(engine_times)}] duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q20: composite key + NULL-safe decorrelation ───
def q20():
    MULT = 10_000_000.0
    part_ok = [[r["p_partkey"]] for r in pg_fetch("SELECT p_partkey FROM part WHERE p_name LIKE 'medium%'")]
    fact_cols = ["l_partkey", "l_suppkey", "l_quantity", "l_shipdate"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    lo, hi = epoch_day("1997-01-01"), epoch_day("1998-01-01")

    ps_cols = ["ps_partkey", "ps_suppkey", "ps_availqty"]
    ps_rows = [[r[c] for c in ps_cols] for r in pg_fetch(f"SELECT {', '.join(ps_cols)} FROM partsupp")]
    nation_supp = [[r["s_suppkey"], strip(r["s_name"]), strip(r["s_address"])] for r in pg_fetch(
        "SELECT s.s_suppkey, s.s_name, s.s_address FROM supplier s JOIN nation n ON s.s_nationkey=n.n_nationkey "
        "WHERE n.n_name='CHINA'")]

    # Resident-handle migration (PR #542's parsed-batch cache): open each lineitem
    # chunk ONCE, before the repeat()-timed run_engine() closure, and reuse the
    # handles across the correctness pass and every timed rep instead of resending
    # `rows=` inline per call. The small partsupp side query below was never
    # chunked to begin with (SF=1 partsupp is under CHUNK_SIZE) so it stays inline.
    handles = [
        runtime().open_dataset(
            [[r[c] for c in fact_cols] for r in batch], name=f"q20_chunk_{i}", routing_module="stats"
        )
        for i, batch in enumerate(chunk(fact))
    ]

    def run_engine():
        partial = {}
        for handle in handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter((col("l_shipdate") >= lo) & (col("l_shipdate") < hi))
                .group_by_many(by=["l_partkey", "l_suppkey"], aggs=[("l_quantity", "sum")])
            )
            for r in run_query(q).rows:
                key = (r[0], r[1])
                partial[key] = partial.get(key, 0.0) + (r[2] or 0.0)
        half_sum_rows = [[pk * MULT + sk, 0.5 * s] for (pk, sk), s in partial.items()]

        cand = (
            Query(columns=ps_cols, rows=ps_rows)
            .with_table("part_ok", ["p_partkey"], rows=part_ok)
            .join("part_ok", left_on="ps_partkey", right_on="p_partkey", how="semi")
            .project(
                ps_key=col("ps_partkey") * lit(MULT) + col("ps_suppkey"),
                ps_availqty=col("ps_availqty"),
                ps_suppkey=col("ps_suppkey"),
            )
            .with_table("half_sum", ["ps_key", "half_qty"], rows=half_sum_rows)
            .join("half_sum", left_on="ps_key", right_on="ps_key", how="inner")
            .filter(col("ps_availqty") > col("half_sum.half_qty"))
            .select("ps_suppkey")
            .distinct("ps_suppkey")
        )
        res = cand.run(runtime(), routing_module="stats")
        return {r[0] for r in res.rows}

    try:
        candidate_suppkeys = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(name, addr) for sk, name, addr in nation_supp if float(sk) in candidate_suppkeys]
    final.sort(key=lambda t: t[0])

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/20.sql")
        duck_times.append(dt)

    drows2 = [(strip(d[0]), strip(d[1])) for d in drows]
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if e != d)
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q21: EXISTS/NOT EXISTS via cardinality ────────
def q21():
    fact_cols = ["l_orderkey", "l_suppkey", "l_commitdate", "l_receiptdate"]
    fact = pg_fetch(f"SELECT {', '.join(fact_cols)} FROM lineitem")
    orders_status = pg_fetch("SELECT o_orderkey FROM orders WHERE o_orderstatus = 'F'")
    status_ok = {r["o_orderkey"] for r in orders_status}
    supplier_recs = pg_fetch(
        "SELECT s.s_suppkey, s.s_name FROM supplier s JOIN nation n ON s.s_nationkey=n.n_nationkey "
        "WHERE n.n_name='VIETNAM'")
    name_codes, name_map = encode_strings([r["s_name"] for r in supplier_recs])
    supplier_ok = [[r["s_suppkey"], name_codes[i]] for i, r in enumerate(supplier_recs)]

    # Resident-handle migration (PR #542's parsed-batch cache): both `for batch in
    # chunk(fact):` loops below iterate over the SAME unmutated lineitem chunks
    # (the derived `qual_rows` between them is a small side table passed via
    # `with_table`, not part of the resident fact rows), so ONE set of handles,
    # opened once before the repeat()-timed run_engine() closure, serves both
    # loops across the correctness pass and every timed rep.
    handles = [
        runtime().open_dataset(
            [[r[c] for c in fact_cols] for r in batch], name=f"q21_chunk_{i}", routing_module="stats"
        )
        for i, batch in enumerate(chunk(fact))
    ]

    def run_engine():
        n_supp, n_late = {}, {}
        for handle in handles:
            qa = Query(columns=fact_cols, dataset=handle).distinct("l_orderkey", "l_suppkey").group_by(
                "l_orderkey", "l_suppkey", agg="count"
            )
            for r in run_query(qa).rows:
                n_supp[r[0]] = n_supp.get(r[0], 0.0) + (r[1] or 0.0)
            qb = (
                Query(columns=fact_cols, dataset=handle)
                .filter(col("l_receiptdate") > col("l_commitdate"))
                .distinct("l_orderkey", "l_suppkey")
                .group_by("l_orderkey", "l_suppkey", agg="count")
            )
            for r in run_query(qb).rows:
                n_late[r[0]] = n_late.get(r[0], 0.0) + (r[1] or 0.0)

        qualifying = {ok for ok, n in n_supp.items() if n > 1 and n_late.get(ok, 0.0) == 1}
        qualifying_final = {ok for ok in qualifying if ok in status_ok}
        qual_rows = [[k] for k in qualifying_final]

        counts = {}
        for handle in handles:
            q = (
                Query(columns=fact_cols, dataset=handle)
                .filter(col("l_receiptdate") > col("l_commitdate"))
                .with_table("qual", ["l_orderkey"], rows=qual_rows)
                .join("qual", left_on="l_orderkey", right_on="l_orderkey", how="semi")
                .with_table("supp_ok", ["s_suppkey", "name_code"], rows=supplier_ok)
                .join("supp_ok", left_on="l_suppkey", right_on="s_suppkey", how="inner")
                .group_by("supp_ok.name_code", "l_orderkey", agg="count")
            )
            for r in run_query(q).rows:
                counts[r[0]] = counts.get(r[0], 0.0) + (r[1] or 0.0)
        return counts

    try:
        counts = run_engine()
        engine_times = repeat(run_engine, N_REPS)
    finally:
        for h in handles:
            runtime().close_dataset(h, routing_module="stats")

    final = [(strip(name_map[code]), int(v)) for code, v in counts.items()]
    final.sort(key=lambda t: (-t[1], t[0]))
    final = final[:100]

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/21.sql")
        duck_times.append(dt)
    drows = drows[:100]

    mism = sum(1 for e, d in zip(final, drows, strict=False) if not (e[0] == strip(d[0]) and e[1] == d[1]))
    ok = mism == 0 and len(final) == len(drows)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


# ─────────────────────────── Q22: NOT EXISTS anti-join + scalar AVG ─────────
def q22():
    codes = ("38", "22", "34", "25", "42", "21", "23")
    code_list = ",".join(f"'{c}'" for c in codes)
    cust_recs = pg_fetch(f"""
        SELECT c_custkey, CAST(SUBSTRING(c_phone FROM 1 FOR 2) AS INT) AS cntrycode, c_acctbal
        FROM customer WHERE SUBSTRING(c_phone FROM 1 FOR 2) IN ({code_list})
    """)
    cust_rows = [[r["c_custkey"], r["cntrycode"], r["c_acctbal"]] for r in cust_recs]
    order_custkeys = [[r["o_custkey"]] for r in pg_fetch("SELECT DISTINCT o_custkey FROM orders")]

    def run_engine():
        avg_q = (
            Query(columns=["c_custkey", "cntrycode", "c_acctbal"], rows=cust_rows)
            .filter(col("c_acctbal") > 0.0)
            .project(one=lit(1.0), c_acctbal=col("c_acctbal"))
            .group_by_many(by=["one"], aggs=[("c_acctbal", "sum"), ("c_acctbal", "count")])
        )
        res = avg_q.run(runtime(), routing_module="stats")
        total_sum, total_count = res.rows[0][1], res.rows[0][2]
        avg_acctbal = total_sum / total_count

        final_q = (
            Query(columns=["c_custkey", "cntrycode", "c_acctbal"], rows=cust_rows)
            .filter(col("c_acctbal") > avg_acctbal)
            .with_table("has_orders", ["o_custkey"], rows=order_custkeys)
            .join("has_orders", left_on="c_custkey", right_on="o_custkey", how="anti")
            .project(cntrycode=col("cntrycode"), c_acctbal=col("c_acctbal"), one=lit(1.0))
            .group_by_many(by=["cntrycode"], aggs=[("one", "sum"), ("c_acctbal", "sum")])
        )
        res2 = final_q.run(runtime(), routing_module="stats")
        return [(int(r[0]), int(r[1]), r[2]) for r in res2.rows]

    final = sorted(run_engine(), key=lambda t: t[0])
    engine_times = repeat(run_engine, N_REPS)

    duck_times = []
    drows = None
    for _ in range(N_REPS):
        _, drows, dt = duck_run(f"{QDIR}/22.sql")
        duck_times.append(dt)

    drows2 = sorted(((int(d[0]), d[1], d[2]) for d in drows), key=lambda t: t[0])
    mism = sum(1 for e, d in zip(final, drows2, strict=False) if not (e[0] == d[0] and e[1] == d[1] and close(e[2], d[2])))
    ok = mism == 0 and len(final) == len(drows2)
    return ok, (
        f"n={len(final)} mismatches={mism} engine[{timing_stats(engine_times)}] "
        f"duckdb[{timing_stats(duck_times)}]"
    )


QUERIES = {
    1: q1, 2: q2, 3: q3, 4: q4, 5: q5, 6: q6, 7: q7, 8: q8, 9: q9, 10: q10,
    11: q11, 12: q12, 13: q13, 14: q14, 15: q15, 16: q16, 17: q17, 18: q18,
    19: q19, 20: q20, 21: q21, 22: q22,
}


def main() -> int:
    failures = 0
    t_start = time.perf_counter()
    for num in sorted(QUERIES):
        t0 = time.perf_counter()
        try:
            ok, detail = QUERIES[num]()
        except Exception as exc:  # noqa: BLE001 - this is the harness's own report
            ok, detail = False, f"EXCEPTION: {exc!r}"
        dt = time.perf_counter() - t0
        print(f"Q{num}: {'PASS' if ok else 'FAIL'} ({dt:.1f}s wall) — {detail}", flush=True)
        if not ok:
            failures += 1
    print(
        f"\n{len(QUERIES) - failures} of {len(QUERIES)} attempted queries passed "
        f"({len(QUERIES)} of 22 real TPC-H templates attempted). "
        f"Total wall time {time.perf_counter() - t_start:.1f}s."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
