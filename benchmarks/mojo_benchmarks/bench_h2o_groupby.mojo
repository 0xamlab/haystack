"""bench_h2o_groupby.mojo — the H2O db-benchmark groupby questions our plane can answer.

Hand-written, not auto-generated. `benchmark_mojo_vs_python.py` only writes
`bench_<lib>.mojo` for libraries in the runtime inventory, and `query/` is in
`_SKIP_RUNTIME_DIRS`, so no generated file can collide with this name.

What this is, and what it is NOT
--------------------------------
This runs the 0.5 GB tier (N=1e7 rows, K=100) of the h2oai/db-benchmark groupby
suite — questions q1-q5 and q7 — through the public entry points every caller
gets, TWICE per question:

  * ROUND 1 (`r1`): the multi-pass shape PR #456 shipped — `group_by` /
    `group_by_multi`, one value column per pass, so q3/q4/q5/q7 cost 2, 3, 3
    and 2 full scans. Kept so the round-over-round change is measured in one
    process on one load, not stitched from two logs.
  * ROUND 2 (`r2`): the fused/coded/radix shape — `group_by_many` (one scan,
    N accumulators, radix-partitioned above `RADIX_MIN_GROUPS` probed groups)
    for q2/q3/q5/q7, and `group_by_coded` (dense array indexed by the
    dictionary code, K+1 = 101 because H2O codes are 1-based) for q1/q4.

It is NOT an H2O submission and does not claim one:

  * q6 (grouped median), q8 (top-2 per group) and q9 (grouped corr) are NOT
    run — grouped order statistics and grouped co-moments are missing from the
    plane, and skipping them silently would misrepresent the coverage.
  * id1..id3 are categorical in the original benchmark. The columnar plane
    stores dictionary codes as Float64, so the companion generator
    (`benchmarks/h2o_groupby/generate.py`) emits integer codes and hands the
    SAME integer codes to polars/duckdb.

Data comes from `benchmarks/h2o_groupby/generate.py` (seeded, deterministic),
which writes one raw little-endian float64 file per column into
/tmp/h2o_groupby. Run that first; this file refuses to invent data.

Per-question output: wall time per repetition for r1 and r2, group count, and a
checksum (sum over groups of every aggregated column) that `run_baselines.py`
compares against polars and duckdb for cross-engine agreement. r1 and r2
checksums are ASSERTED to agree in-process (exactly for sums/min/max on this
integer-coded data; 1e-9 relative for means, where the merge association
differs) — a faster wrong answer would fail here, not in a log diff.
"""
from std.io.file import FileHandle
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_AVG, AGG_MAX, AGG_MIN, AGG_SUM
from query.aggregate import (
    group_by,
    group_by_coded,
    group_by_many,
    group_by_multi,
)

comptime N_ROWS: Int = 10_000_000
comptime DATA_DIR: String = "/tmp/h2o_groupby"
comptime REPS: Int = 3
# H2O's categorical codes are 1..K, so the dense array needs K+1 slots (slot 0
# stays empty). K=100 for id1/id4 at this tier.
comptime H2O_CODE_CARDINALITY: Int = 101


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


fn _agree(a: Float64, b: Float64, rel_tol: Float64) -> Bool:
    """|a-b| within rel_tol of max(1, |a|) — the cross-round checksum gate."""
    var scale = a if a > 0.0 else -a
    if scale < 1.0:
        scale = 1.0
    var delta = a - b
    if delta < 0.0:
        delta = -delta
    return delta <= rel_tol * scale


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
    print("  (r1 = round 1 multi-pass; r2 = fused/coded/radix; times per repetition)")

    var mismatches = 0

    for rep in range(REPS):
        print("--- rep " + String(rep) + " ---")

        # ── q1: sum(v1) by id1 ── r1 one hashed pass; r2 code-indexed.
        var t0 = perf_counter_ns()
        var q1 = group_by(batch, 0, 5, AGG_SUM)
        var t1 = perf_counter_ns()
        var q1_sum = _checksum(q1.values, q1.present)
        _report("q1 r1 sum(v1) by id1          ", t1 - t0, q1.n_groups(), q1_sum)
        var vc_q1 = List[Int]()
        vc_q1.append(5)
        var ops_q1 = List[Int]()
        ops_q1.append(AGG_SUM)
        var t0b = perf_counter_ns()
        var q1b = group_by_coded(batch, 0, H2O_CODE_CARDINALITY, vc_q1, ops_q1)
        var t1b = perf_counter_ns()
        if not q1b.ok():
            raise Error("q1 r2: coded path refused real H2O codes")
        var q1b_sum = _checksum(q1b.result.values, q1b.result.present)
        _report("q1 r2 coded                   ", t1b - t0b, q1b.result.n_groups(), q1b_sum)
        if not _agree(q1_sum, q1b_sum, 0.0):  # integer sums: exact
            mismatches += 1
            print("  ❌ q1 r1/r2 checksum mismatch")

        # ── q2: sum(v1) by id1:id2 ── r1 composite pass; r2 fused (radix probes
        # ~10k groups, stays banded — measured at par, dispatch decides).
        var key12 = List[Int]()
        key12.append(0)
        key12.append(1)
        var t2 = perf_counter_ns()
        var q2 = group_by_multi(batch, key12, 5, AGG_SUM)
        var t3 = perf_counter_ns()
        var q2_sum = _checksum(q2.values, q2.present)
        _report("q2 r1 sum(v1) by id1:id2      ", t3 - t2, q2.n_groups(), q2_sum)
        var t2b = perf_counter_ns()
        var q2b = group_by_many(batch, key12, vc_q1, ops_q1)
        var t3b = perf_counter_ns()
        var q2b_sum = _checksum(q2b.values, q2b.present)
        _report("q2 r2 fused                   ", t3b - t2b, q2b.n_groups(), q2b_sum)
        if not _agree(q2_sum, q2b_sum, 0.0):
            mismatches += 1
            print("  ❌ q2 r1/r2 checksum mismatch")

        # ── q3: sum(v1), mean(v3) by id3 ── r1 two passes; r2 ONE fused pass
        # (id3 has ~100k groups: the probe sends this down the radix path).
        var kc3 = List[Int]()
        kc3.append(2)
        var t4 = perf_counter_ns()
        var q3a = group_by(batch, 2, 5, AGG_SUM)
        var q3b = group_by(batch, 2, 7, AGG_AVG)
        var t5 = perf_counter_ns()
        var q3_sum = _checksum(q3a.values, q3a.present) + _checksum(q3b.values, q3b.present)
        _report("q3 r1 sum(v1),mean(v3) by id3 ", t5 - t4, q3a.n_groups(), q3_sum)
        var vc_q3 = List[Int]()
        vc_q3.append(5)
        vc_q3.append(7)
        var ops_q3 = List[Int]()
        ops_q3.append(AGG_SUM)
        ops_q3.append(AGG_AVG)
        var t4b = perf_counter_ns()
        var q3f = group_by_many(batch, kc3, vc_q3, ops_q3)
        var t5b = perf_counter_ns()
        var q3f_sum = _checksum(q3f.values, q3f.present)
        _report("q3 r2 fused                   ", t5b - t4b, q3f.n_groups(), q3f_sum)
        if not _agree(q3_sum, q3f_sum, 1e-9):  # means: association differs
            mismatches += 1
            print("  ❌ q3 r1/r2 checksum mismatch")

        # ── q4: mean(v1:v3) by id4 ── r1 three passes; r2 ONE coded fused pass.
        var t6 = perf_counter_ns()
        var q4a = group_by(batch, 3, 5, AGG_AVG)
        var q4b = group_by(batch, 3, 6, AGG_AVG)
        var q4c = group_by(batch, 3, 7, AGG_AVG)
        var t7 = perf_counter_ns()
        var q4_sum = (
            _checksum(q4a.values, q4a.present)
            + _checksum(q4b.values, q4b.present)
            + _checksum(q4c.values, q4c.present)
        )
        _report("q4 r1 mean(v1:v3) by id4      ", t7 - t6, q4a.n_groups(), q4_sum)
        var vc_q4 = List[Int]()
        vc_q4.append(5)
        vc_q4.append(6)
        vc_q4.append(7)
        var ops_q4 = List[Int]()
        ops_q4.append(AGG_AVG)
        ops_q4.append(AGG_AVG)
        ops_q4.append(AGG_AVG)
        var t6b = perf_counter_ns()
        var q4f = group_by_coded(batch, 3, H2O_CODE_CARDINALITY, vc_q4, ops_q4)
        var t7b = perf_counter_ns()
        if not q4f.ok():
            raise Error("q4 r2: coded path refused real H2O codes")
        var q4f_sum = _checksum(q4f.result.values, q4f.result.present)
        _report("q4 r2 coded fused             ", t7b - t6b, q4f.result.n_groups(), q4f_sum)
        if not _agree(q4_sum, q4f_sum, 1e-9):
            mismatches += 1
            print("  ❌ q4 r1/r2 checksum mismatch")

        # ── q5: sum(v1:v3) by id6 ── r1 three passes; r2 ONE fused radix pass.
        var kc5 = List[Int]()
        kc5.append(4)
        var t8 = perf_counter_ns()
        var q5a = group_by(batch, 4, 5, AGG_SUM)
        var q5b = group_by(batch, 4, 6, AGG_SUM)
        var q5c = group_by(batch, 4, 7, AGG_SUM)
        var t9 = perf_counter_ns()
        var q5_sum = (
            _checksum(q5a.values, q5a.present)
            + _checksum(q5b.values, q5b.present)
            + _checksum(q5c.values, q5c.present)
        )
        _report("q5 r1 sum(v1:v3) by id6       ", t9 - t8, q5a.n_groups(), q5_sum)
        var ops_q5 = List[Int]()
        ops_q5.append(AGG_SUM)
        ops_q5.append(AGG_SUM)
        ops_q5.append(AGG_SUM)
        var t8b = perf_counter_ns()
        var q5f = group_by_many(batch, kc5, vc_q4, ops_q5)
        var t9b = perf_counter_ns()
        var q5f_sum = _checksum(q5f.values, q5f.present)
        _report("q5 r2 fused                   ", t9b - t8b, q5f.n_groups(), q5f_sum)
        # v3 is continuous, so its per-group sums fold in a different order on
        # the radix path than r1's band merge — 1e-9 relative, like the means.
        if not _agree(q5_sum, q5f_sum, 1e-9):
            mismatches += 1
            print("  ❌ q5 r1/r2 checksum mismatch")

        # ── q7: max(v1) - min(v2) by id3 ── r1 two passes + zip; r2 one fused
        # pass + zip. Both rely on the first-appearance order promise to align
        # the aggregate columns without a join.
        var t10 = perf_counter_ns()
        var q7a = group_by(batch, 2, 5, AGG_MAX)
        var q7b = group_by(batch, 2, 6, AGG_MIN)
        var range_sum: Float64 = 0.0
        for g in range(q7a.n_groups()):
            if q7a.present[g] and q7b.present[g]:
                range_sum += q7a.values[g] - q7b.values[g]
        var t11 = perf_counter_ns()
        _report("q7 r1 max(v1)-min(v2) by id3  ", t11 - t10, q7a.n_groups(), range_sum)
        var vc_q7 = List[Int]()
        vc_q7.append(5)
        vc_q7.append(6)
        var ops_q7 = List[Int]()
        ops_q7.append(AGG_MAX)
        ops_q7.append(AGG_MIN)
        var t10b = perf_counter_ns()
        var q7f = group_by_many(batch, kc3, vc_q7, ops_q7)
        var f_range_sum: Float64 = 0.0
        for g in range(q7f.n_groups()):
            if q7f.present_at(g, 0) and q7f.present_at(g, 1):
                f_range_sum += q7f.value_at(g, 0) - q7f.value_at(g, 1)
        var t11b = perf_counter_ns()
        _report("q7 r2 fused                   ", t11b - t10b, q7f.n_groups(), f_range_sum)
        if not _agree(range_sum, f_range_sum, 0.0):  # min/max: exact
            mismatches += 1
            print("  ❌ q7 r1/r2 checksum mismatch")

    print("")
    if mismatches > 0:
        raise Error(
            "bench_h2o_groupby: " + String(mismatches) + " r1/r2 checksum mismatch(es)"
        )
    print("done, all r1/r2 checksums agree. Compare against polars/duckdb via")
    print("benchmarks/h2o_groupby/run_baselines.py.")
