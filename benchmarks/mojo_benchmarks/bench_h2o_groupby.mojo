"""bench_h2o_groupby.mojo — the H2O db-benchmark groupby questions our plane can answer.

Hand-written, not auto-generated. `benchmark_mojo_vs_python.py` only writes
`bench_<lib>.mojo` for libraries in the runtime inventory, and `query/` is in
`_SKIP_RUNTIME_DIRS`, so no generated file can collide with this name.

What this is, and what it is NOT
--------------------------------
This runs the 0.5 GB tier (N=1e7 rows, K=100) of the h2oai/db-benchmark groupby
suite — questions q1-q5 and q7 — through the query plane THREE ways per
question, in one process on one load:

  * ROUND 1 (`r1`): the multi-pass shape PR #456 shipped — `group_by` /
    `group_by_multi`, one value column per pass, so q3/q4/q5/q7 cost 2, 3, 3
    and 2 full scans.
  * ROUND 2 (`r2`): the fused engines PR #458 shipped, PINNED to the route
    round 2 chose per question — `group_by_coded` for q1/q4 (dense array by
    dictionary code, K+1 = 101 because H2O codes are 1-based),
    `group_by_many_banded` for q2, `group_by_many_radix` for q3/q5/q7. Round
    3 made these engines faster (specialized updates, counted scatter,
    batched hashing), so these lines measure "the best explicit engine",
    not round 2's historical wall time.
  * ROUND 3 (`r3`): `group_by_many` — the SHAPE-DISPATCHED entry point
    (`plan_many_route`: coded / banded / radix by probe). What a caller who
    names no engine gets.

The routing regression gate
---------------------------
Per question, per repetition: ratio(rep) = r3 / min(r1, r2) of THAT rep —
the three rounds of one rep run back-to-back, so a load spike hits them
together and cancels out of the ratio, where cross-rep best-vs-best pairing
does not (a mid-run spike to load ~19 flipped exactly that comparison during
development). The gate fails a question only when min over reps of
ratio(rep) > 1.05: a real routing mistake makes r3 slower in EVERY rep (the
measured mistakes are 2-8x, q1 routed radix-instead-of-coded is 8x), while
noise has to lose every adjacent-in-time pairing to slip through. Violations
fail the run loudly (`BENCH_GATE h2o_round3_routing`).

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

Per-question output: wall time per repetition for r1/r2/r3, group count, and a
checksum (sum over groups of every aggregated column) that `run_baselines.py`
compares against polars and duckdb for cross-engine agreement. r2 and r3
checksums are ASSERTED against r1 in-process (exactly for sums/min/max on this
integer-coded data; 1e-9 relative where the fold association differs) — a
faster wrong answer fails here, not in a log diff.
"""
from std.io.file import FileHandle
from std.sys import info
from std.time import perf_counter_ns

from columnar.array import Float64Array, float64_from_list
from columnar.batch import RecordBatch, schema_of
from numeric.contract import AGG_AVG, AGG_MAX, AGG_MIN, AGG_SUM
from query.aggregate import (
    group_by,
    group_by_coded,
    group_by_many,
    group_by_many_banded,
    group_by_many_radix,
    group_by_multi,
)

comptime N_ROWS: Int = 10_000_000
comptime DATA_DIR: String = "/tmp/h2o_groupby"
comptime REPS: Int = 3
# H2O's categorical codes are 1..K, so the dense array needs K+1 slots (slot 0
# stays empty). K=100 for id1/id4 at this tier.
comptime H2O_CODE_CARDINALITY: Int = 101
comptime N_QUESTIONS: Int = 6
comptime GATE_MARGIN: Float64 = 1.05


def _load_column(name: String) raises -> Float64Array:
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


def _checksum(values: List[Float64], present: List[Bool]) -> Float64:
    var total: Float64 = 0.0
    for i in range(len(values)):
        if present[i]:
            total += values[i]
    return total


def _report(name: String, ns: UInt, groups: Int, checksum: Float64):
    print(
        "  " + name
        + "  s=" + String(Float64(Int(ns)) / 1e9)
        + "  groups=" + String(groups)
        + "  checksum=" + String(checksum)
    )


def _agree(a: Float64, b: Float64, rel_tol: Float64) -> Bool:
    """|a-b| within rel_tol of max(1, |a|) — the cross-round checksum gate."""
    var scale = a if a > 0.0 else -a
    if scale < 1.0:
        scale = 1.0
    var delta = a - b
    if delta < 0.0:
        delta = -delta
    return delta <= rel_tol * scale


def _record(mut times: List[Float64], q: Int, rep: Int, ns: UInt):
    times[q * REPS + rep] = Float64(Int(ns)) / 1e9


def _best_of(times: List[Float64], q: Int) -> Float64:
    var best = 1e30
    for rep in range(REPS):
        if times[q * REPS + rep] < best:
            best = times[q * REPS + rep]
    return best


def main() raises:
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
    var cores = info.num_physical_cores()
    print("  loaded: " + batch.describe() + "  (" + String(cores) + " workers)")
    print("")
    print("  (r1 = round 1 multi-pass; r2 = best explicit engine, round-2 route;")
    print("   r3 = group_by_many auto dispatch; times per repetition)")

    var mismatches = 0
    var times_r1 = List[Float64](length=N_QUESTIONS * REPS, fill=1e30)
    var times_r2 = List[Float64](length=N_QUESTIONS * REPS, fill=1e30)
    var times_r3 = List[Float64](length=N_QUESTIONS * REPS, fill=1e30)

    for rep in range(REPS):
        print("--- rep " + String(rep) + " ---")

        # ── q1: sum(v1) by id1 ── r1 hashed pass; r2 coded explicit; r3 routed.
        var kc1 = List[Int]()
        kc1.append(0)
        var t0 = perf_counter_ns()
        var q1 = group_by(batch, 0, 5, AGG_SUM)
        var t1 = perf_counter_ns()
        _record(times_r1, 0, rep, t1 - t0)
        var q1_sum = _checksum(q1.values, q1.present)
        _report("q1 r1 sum(v1) by id1          ", t1 - t0, q1.n_groups(), q1_sum)
        var vc_q1 = List[Int]()
        vc_q1.append(5)
        var ops_q1 = List[Int]()
        ops_q1.append(AGG_SUM)
        var t0b = perf_counter_ns()
        var q1b = group_by_coded(batch, 0, H2O_CODE_CARDINALITY, vc_q1, ops_q1)
        var t1b = perf_counter_ns()
        _record(times_r2, 0, rep, t1b - t0b)
        if not q1b.ok():
            raise Error("q1 r2: coded path refused real H2O codes")
        var q1b_sum = _checksum(q1b.result.values, q1b.result.present)
        _report("q1 r2 coded                   ", t1b - t0b, q1b.result.n_groups(), q1b_sum)
        var t0c = perf_counter_ns()
        var q1c = group_by_many(batch, kc1, vc_q1, ops_q1)
        var t1c = perf_counter_ns()
        _record(times_r3, 0, rep, t1c - t0c)
        var q1c_sum = _checksum(q1c.values, q1c.present)
        _report("q1 r3 routed                  ", t1c - t0c, q1c.n_groups(), q1c_sum)
        if not _agree(q1_sum, q1b_sum, 0.0):  # integer sums: exact
            mismatches += 1
            print("  ❌ q1 r1/r2 checksum mismatch")
        if not _agree(q1_sum, q1c_sum, 0.0):
            mismatches += 1
            print("  ❌ q1 r1/r3 checksum mismatch")

        # ── q2: sum(v1) by id1:id2 ── r1 composite pass; r2 banded explicit
        # (round 2's route); r3 routed. The ~10k probed groups sit in the
        # measured banded/radix coin-flip zone, so the dispatcher stays
        # banded — RADIX_MIN_GROUPS documents the measurement.
        var key12 = List[Int]()
        key12.append(0)
        key12.append(1)
        var t2 = perf_counter_ns()
        var q2 = group_by_multi(batch, key12, 5, AGG_SUM)
        var t3 = perf_counter_ns()
        _record(times_r1, 1, rep, t3 - t2)
        var q2_sum = _checksum(q2.values, q2.present)
        _report("q2 r1 sum(v1) by id1:id2      ", t3 - t2, q2.n_groups(), q2_sum)
        var t2b = perf_counter_ns()
        var q2b = group_by_many_banded(batch, key12, vc_q1, ops_q1, cores)
        var t3b = perf_counter_ns()
        _record(times_r2, 1, rep, t3b - t2b)
        var q2b_sum = _checksum(q2b.values, q2b.present)
        _report("q2 r2 banded                  ", t3b - t2b, q2b.n_groups(), q2b_sum)
        var t2c = perf_counter_ns()
        var q2c = group_by_many(batch, key12, vc_q1, ops_q1)
        var t3c = perf_counter_ns()
        _record(times_r3, 1, rep, t3c - t2c)
        var q2c_sum = _checksum(q2c.values, q2c.present)
        _report("q2 r3 routed                  ", t3c - t2c, q2c.n_groups(), q2c_sum)
        if not _agree(q2_sum, q2b_sum, 0.0):
            mismatches += 1
            print("  ❌ q2 r1/r2 checksum mismatch")
        if not _agree(q2_sum, q2c_sum, 0.0):
            mismatches += 1
            print("  ❌ q2 r1/r3 checksum mismatch")

        # ── q3: sum(v1), mean(v3) by id3 ── r1 two passes; r2 ONE radix pass
        # (round 2's route: ~100k groups); r3 routed.
        var kc3 = List[Int]()
        kc3.append(2)
        var t4 = perf_counter_ns()
        var q3a = group_by(batch, 2, 5, AGG_SUM)
        var q3b = group_by(batch, 2, 7, AGG_AVG)
        var t5 = perf_counter_ns()
        _record(times_r1, 2, rep, t5 - t4)
        var q3_sum = _checksum(q3a.values, q3a.present) + _checksum(q3b.values, q3b.present)
        _report("q3 r1 sum(v1),mean(v3) by id3 ", t5 - t4, q3a.n_groups(), q3_sum)
        var vc_q3 = List[Int]()
        vc_q3.append(5)
        vc_q3.append(7)
        var ops_q3 = List[Int]()
        ops_q3.append(AGG_SUM)
        ops_q3.append(AGG_AVG)
        var t4b = perf_counter_ns()
        var q3f = group_by_many_radix(batch, kc3, vc_q3, ops_q3, cores)
        var t5b = perf_counter_ns()
        _record(times_r2, 2, rep, t5b - t4b)
        var q3f_sum = _checksum(q3f.values, q3f.present)
        _report("q3 r2 radix                   ", t5b - t4b, q3f.n_groups(), q3f_sum)
        var t4c = perf_counter_ns()
        var q3c = group_by_many(batch, kc3, vc_q3, ops_q3)
        var t5c = perf_counter_ns()
        _record(times_r3, 2, rep, t5c - t4c)
        var q3c_sum = _checksum(q3c.values, q3c.present)
        _report("q3 r3 routed                  ", t5c - t4c, q3c.n_groups(), q3c_sum)
        if not _agree(q3_sum, q3f_sum, 1e-9):  # means: association differs
            mismatches += 1
            print("  ❌ q3 r1/r2 checksum mismatch")
        if not _agree(q3_sum, q3c_sum, 1e-9):
            mismatches += 1
            print("  ❌ q3 r1/r3 checksum mismatch")

        # ── q4: mean(v1:v3) by id4 ── r1 three passes; r2 ONE coded fused pass;
        # r3 routed.
        var kc4 = List[Int]()
        kc4.append(3)
        var t6 = perf_counter_ns()
        var q4a = group_by(batch, 3, 5, AGG_AVG)
        var q4b = group_by(batch, 3, 6, AGG_AVG)
        var q4c = group_by(batch, 3, 7, AGG_AVG)
        var t7 = perf_counter_ns()
        _record(times_r1, 3, rep, t7 - t6)
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
        _record(times_r2, 3, rep, t7b - t6b)
        if not q4f.ok():
            raise Error("q4 r2: coded path refused real H2O codes")
        var q4f_sum = _checksum(q4f.result.values, q4f.result.present)
        _report("q4 r2 coded fused             ", t7b - t6b, q4f.result.n_groups(), q4f_sum)
        var t6c = perf_counter_ns()
        var q4r = group_by_many(batch, kc4, vc_q4, ops_q4)
        var t7c = perf_counter_ns()
        _record(times_r3, 3, rep, t7c - t6c)
        var q4r_sum = _checksum(q4r.values, q4r.present)
        _report("q4 r3 routed                  ", t7c - t6c, q4r.n_groups(), q4r_sum)
        if not _agree(q4_sum, q4f_sum, 1e-9):
            mismatches += 1
            print("  ❌ q4 r1/r2 checksum mismatch")
        if not _agree(q4_sum, q4r_sum, 1e-9):
            mismatches += 1
            print("  ❌ q4 r1/r3 checksum mismatch")

        # ── q5: sum(v1:v3) by id6 ── r1 three passes; r2 ONE radix pass; r3
        # routed.
        var kc5 = List[Int]()
        kc5.append(4)
        var t8 = perf_counter_ns()
        var q5a = group_by(batch, 4, 5, AGG_SUM)
        var q5b = group_by(batch, 4, 6, AGG_SUM)
        var q5c = group_by(batch, 4, 7, AGG_SUM)
        var t9 = perf_counter_ns()
        _record(times_r1, 4, rep, t9 - t8)
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
        var q5f = group_by_many_radix(batch, kc5, vc_q4, ops_q5, cores)
        var t9b = perf_counter_ns()
        _record(times_r2, 4, rep, t9b - t8b)
        var q5f_sum = _checksum(q5f.values, q5f.present)
        _report("q5 r2 radix                   ", t9b - t8b, q5f.n_groups(), q5f_sum)
        var t8c = perf_counter_ns()
        var q5r = group_by_many(batch, kc5, vc_q4, ops_q5)
        var t9c = perf_counter_ns()
        _record(times_r3, 4, rep, t9c - t8c)
        var q5r_sum = _checksum(q5r.values, q5r.present)
        _report("q5 r3 routed                  ", t9c - t8c, q5r.n_groups(), q5r_sum)
        # v3 is continuous, so its per-group sums fold in a different order on
        # the radix path than r1's band merge — 1e-9 relative, like the means.
        if not _agree(q5_sum, q5f_sum, 1e-9):
            mismatches += 1
            print("  ❌ q5 r1/r2 checksum mismatch")
        if not _agree(q5_sum, q5r_sum, 1e-9):
            mismatches += 1
            print("  ❌ q5 r1/r3 checksum mismatch")

        # ── q7: max(v1) - min(v2) by id3 ── r1 two passes + zip; r2 one radix
        # pass + zip; r3 routed + zip. All rely on the first-appearance order
        # promise to align the aggregate columns without a join.
        var t10 = perf_counter_ns()
        var q7a = group_by(batch, 2, 5, AGG_MAX)
        var q7b = group_by(batch, 2, 6, AGG_MIN)
        var range_sum: Float64 = 0.0
        for g in range(q7a.n_groups()):
            if q7a.present[g] and q7b.present[g]:
                range_sum += q7a.values[g] - q7b.values[g]
        var t11 = perf_counter_ns()
        _record(times_r1, 5, rep, t11 - t10)
        _report("q7 r1 max(v1)-min(v2) by id3  ", t11 - t10, q7a.n_groups(), range_sum)
        var vc_q7 = List[Int]()
        vc_q7.append(5)
        vc_q7.append(6)
        var ops_q7 = List[Int]()
        ops_q7.append(AGG_MAX)
        ops_q7.append(AGG_MIN)
        var t10b = perf_counter_ns()
        var q7f = group_by_many_radix(batch, kc3, vc_q7, ops_q7, cores)
        var f_range_sum: Float64 = 0.0
        for g in range(q7f.n_groups()):
            if q7f.present_at(g, 0) and q7f.present_at(g, 1):
                f_range_sum += q7f.value_at(g, 0) - q7f.value_at(g, 1)
        var t11b = perf_counter_ns()
        _record(times_r2, 5, rep, t11b - t10b)
        _report("q7 r2 radix                   ", t11b - t10b, q7f.n_groups(), f_range_sum)
        var t10c = perf_counter_ns()
        var q7r = group_by_many(batch, kc3, vc_q7, ops_q7)
        var r_range_sum: Float64 = 0.0
        for g in range(q7r.n_groups()):
            if q7r.present_at(g, 0) and q7r.present_at(g, 1):
                r_range_sum += q7r.value_at(g, 0) - q7r.value_at(g, 1)
        var t11c = perf_counter_ns()
        _record(times_r3, 5, rep, t11c - t10c)
        _report("q7 r3 routed                  ", t11c - t10c, q7r.n_groups(), r_range_sum)
        if not _agree(range_sum, f_range_sum, 0.0):  # min/max: exact
            mismatches += 1
            print("  ❌ q7 r1/r2 checksum mismatch")
        if not _agree(range_sum, r_range_sum, 0.0):
            mismatches += 1
            print("  ❌ q7 r1/r3 checksum mismatch")

    print("")
    # ── the routing regression gate: r3 must match the best explicit engine ──
    var q_names = List[String]()
    q_names.append("q1")
    q_names.append("q2")
    q_names.append("q3")
    q_names.append("q4")
    q_names.append("q5")
    q_names.append("q7")
    var gate_failures = 0
    for q in range(N_QUESTIONS):
        # Per-rep pairing: the rounds of one rep share the rep's load, so the
        # ratio is honest under a spike. A routing mistake loses every rep.
        var min_ratio = 1e30
        for rep in range(REPS):
            var floor = times_r1[q * REPS + rep]
            if times_r2[q * REPS + rep] < floor:
                floor = times_r2[q * REPS + rep]
            var ratio = times_r3[q * REPS + rep] / floor
            if ratio < min_ratio:
                min_ratio = ratio
        var ok = min_ratio <= GATE_MARGIN
        if not ok:
            gate_failures += 1
        print(
            "  " + q_names[q]
            + "  best r1=" + String(_best_of(times_r1, q))
            + "  r2=" + String(_best_of(times_r2, q))
            + "  r3=" + String(_best_of(times_r3, q))
            + "  min_ratio=" + String(min_ratio)
            + ("  ✅ within 1.05 x best" if ok else "  ❌ r3 REGRESSED past 1.05 x best in EVERY rep")
        )
    if gate_failures == 0:
        print("BENCH_GATE h2o_round3_routing PASS")
    else:
        print("BENCH_GATE h2o_round3_routing FAIL " + String(gate_failures))

    if mismatches > 0:
        raise Error(
            "bench_h2o_groupby: " + String(mismatches) + " cross-round checksum mismatch(es)"
        )
    if gate_failures > 0:
        raise Error(
            "bench_h2o_groupby: the dispatcher regressed " + String(gate_failures)
            + " question(s) past 1.05 x the best explicit engine"
        )
    print("done: all checksums agree across rounds, and the routed engine matches")
    print("the best explicit engine per question. Compare against polars/duckdb via")
    print("benchmarks/h2o_groupby/run_baselines.py.")
