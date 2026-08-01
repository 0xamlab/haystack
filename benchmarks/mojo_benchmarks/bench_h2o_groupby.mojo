"""bench_h2o_groupby.mojo — the H2O db-benchmark groupby questions our plane can answer.

Hand-written, not auto-generated. `benchmark_mojo_vs_python.py` only writes
`bench_<lib>.mojo` for libraries in the runtime inventory, and `query/` is in
`_SKIP_RUNTIME_DIRS`, so no generated file can collide with this name.

What this is, and what it is NOT
--------------------------------
This runs the 0.5 GB tier (N=1e7 rows, K=100) of the h2oai/db-benchmark groupby
suite — questions q1-q5 and q7 — through `query.aggregate.group_by` and
`group_by_multi`, the same public entry points every caller gets. It is NOT an
H2O submission and does not claim one:

  * q6 (grouped median), q8 (top-2 per group) and q9 (grouped corr) are NOT run —
    grouped order statistics and grouped co-moments are missing from the plane,
    and skipping them silently would misrepresent the coverage.
  * q3/q4/q5/q7 ask for several aggregates per grouping. The plane's public
    surface aggregates ONE value column per pass, so those questions cost one
    pass per aggregate here (2, 3, 3 and 2 passes respectively) where
    polars/duckdb fuse them into one. The per-question time reported is the SUM
    of those passes — the honest cost of answering the question today.
  * id1..id3 are categorical in the original benchmark. The columnar plane
    stores dictionary codes as Float64, so the companion generator
    (`benchmarks/h2o_groupby/generate.py`) emits integer codes and hands the
    SAME integer codes to polars/duckdb.

Data comes from `benchmarks/h2o_groupby/generate.py` (seeded, deterministic),
which writes one raw little-endian float64 file per column into
/tmp/h2o_groupby. Run that first; this file refuses to invent data.

Per-question output: wall time per repetition, group count, and a checksum
(sum over groups of the aggregated value) that `run_baselines.py` compares
against polars and duckdb for cross-engine agreement.
"""
from std.io.file import FileHandle
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_AVG, AGG_MAX, AGG_MIN, AGG_SUM
from query.aggregate import group_by, group_by_multi

comptime N_ROWS: Int = 10_000_000
comptime DATA_DIR: String = "/tmp/h2o_groupby"
comptime REPS: Int = 3


fn _load_column(name: String) raises -> Float64Array:
    """One raw float64 column written by generate.py, as a no-null column."""
    var f = open(DATA_DIR + "/" + name + ".f64.bin", "r")
    var raw = f.read_bytes()
    f.close()
    if len(raw) != N_ROWS * 8:
        raise Error(
            name + ".f64.bin is " + String(len(raw)) + " bytes, expected "
            + String(N_ROWS * 8) + " — run benchmarks/h2o_groupby/generate.py first"
        )
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    var values = List[Float64](capacity=N_ROWS)
    for i in range(N_ROWS):
        values.append(fp[i])
    return float64_from_list(values^)


fn _checksum(values: List[Float64], present: List[Bool]) -> Float64:
    var total: Float64 = 0.0
    for i in range(len(values)):
        if present[i]:
            total += values[i]
    return total


fn _report(name: String, ns: UInt, groups: Int, checksum: Float64):
    print(
        "  " + name
        + "  s=" + String(Float64(Int(ns)) / 1e9)
        + "  groups=" + String(groups)
        + "  checksum=" + String(checksum)
    )


fn main() raises:
    print("=== H2O groupby 0.5 GB tier (N=1e7, K=100) via query.aggregate ===")
    print("  loading columns from " + DATA_DIR + " ...")
    var id1 = _load_column("id1")
    var id2 = _load_column("id2")
    var id3 = _load_column("id3")
    var id4 = _load_column("id4")
    var id6 = _load_column("id6")
    var v1 = _load_column("v1")
    var v2 = _load_column("v2")
    var v3 = _load_column("v3")

    var names = List[String]()
    names.append("id1")  # 0
    names.append("id2")  # 1
    names.append("id3")  # 2
    names.append("id4")  # 3
    names.append("id6")  # 4
    names.append("v1")   # 5
    names.append("v2")   # 6
    names.append("v3")   # 7
    var cols = List[Float64Array]()
    cols.append(id1^)
    cols.append(id2^)
    cols.append(id3^)
    cols.append(id4^)
    cols.append(id6^)
    cols.append(v1^)
    cols.append(v2^)
    cols.append(v3^)
    var batch = RecordBatch(schema_of(names^), cols^, N_ROWS)
    print("  loaded: " + batch.describe())
    print("")
    print("  (times are per repetition; q3/q4/q5/q7 are multi-pass — see header)")

    for rep in range(REPS):
        print("--- rep " + String(rep) + " ---")

        # q1: sum(v1) by id1 — one pass.
        var t0 = perf_counter_ns()
        var q1 = group_by(batch, 0, 5, AGG_SUM)
        var t1 = perf_counter_ns()
        _report("q1 sum(v1) by id1          ", t1 - t0, q1.n_groups(), _checksum(q1.values, q1.present))

        # q2: sum(v1) by id1:id2 — one pass, composite key.
        var key12 = List[Int]()
        key12.append(0)
        key12.append(1)
        var t2 = perf_counter_ns()
        var q2 = group_by_multi(batch, key12, 5, AGG_SUM)
        var t3 = perf_counter_ns()
        _report("q2 sum(v1) by id1:id2      ", t3 - t2, q2.n_groups(), _checksum(q2.values, q2.present))

        # q3: sum(v1), mean(v3) by id3 — two passes.
        var t4 = perf_counter_ns()
        var q3a = group_by(batch, 2, 5, AGG_SUM)
        var q3b = group_by(batch, 2, 7, AGG_AVG)
        var t5 = perf_counter_ns()
        _report(
            "q3 sum(v1),mean(v3) by id3 ",
            t5 - t4,
            q3a.n_groups(),
            _checksum(q3a.values, q3a.present) + _checksum(q3b.values, q3b.present),
        )

        # q4: mean(v1..v3) by id4 — three passes.
        var t6 = perf_counter_ns()
        var q4a = group_by(batch, 3, 5, AGG_AVG)
        var q4b = group_by(batch, 3, 6, AGG_AVG)
        var q4c = group_by(batch, 3, 7, AGG_AVG)
        var t7 = perf_counter_ns()
        _report(
            "q4 mean(v1:v3) by id4      ",
            t7 - t6,
            q4a.n_groups(),
            _checksum(q4a.values, q4a.present)
            + _checksum(q4b.values, q4b.present)
            + _checksum(q4c.values, q4c.present),
        )

        # q5: sum(v1..v3) by id6 — three passes.
        var t8 = perf_counter_ns()
        var q5a = group_by(batch, 4, 5, AGG_SUM)
        var q5b = group_by(batch, 4, 6, AGG_SUM)
        var q5c = group_by(batch, 4, 7, AGG_SUM)
        var t9 = perf_counter_ns()
        _report(
            "q5 sum(v1:v3) by id6       ",
            t9 - t8,
            q5a.n_groups(),
            _checksum(q5a.values, q5a.present)
            + _checksum(q5b.values, q5b.present)
            + _checksum(q5c.values, q5c.present),
        )

        # q7: max(v1) - min(v2) by id3 — two passes plus a per-group zip.
        var t10 = perf_counter_ns()
        var q7a = group_by(batch, 2, 5, AGG_MAX)
        var q7b = group_by(batch, 2, 6, AGG_MIN)
        var range_sum: Float64 = 0.0
        # Both passes group the same key column, so group order is identical —
        # first-appearance order is a documented promise of group_by.
        for g in range(q7a.n_groups()):
            if q7a.present[g] and q7b.present[g]:
                range_sum += q7a.values[g] - q7b.values[g]
        var t11 = perf_counter_ns()
        _report("q7 max(v1)-min(v2) by id3  ", t11 - t10, q7a.n_groups(), range_sum)

    print("")
    print("done. Compare checksums via benchmarks/h2o_groupby/run_baselines.py.")
