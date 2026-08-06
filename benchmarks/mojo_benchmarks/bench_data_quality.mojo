"""bench_data_quality.mojo — shape gate for the data_quality package.

Hand-written, not generated. `benchmark_mojo_vs_python.py` only writes `bench_<lib>.mojo`
for libraries in the runtime inventory, and no library is named `data_quality` (the modules
are `data_quality.contract`, `.profile`, `.expect`, `.duplicates`, `.leakage`), so nothing
can collide with this filename and that harness only writes — it never unlinks.

What is measured, and why each is the claim that matters
-------------------------------------------------------
Each measurement is a COST PER UNIT that must stay flat as the problem grows. Absolute
nanoseconds vary by machine and by JIT warm-up and are printed for tracking only; the gate
never reads them.

Every gated measurement is the MINIMUM of `SAMPLES` timed calls after `WARMUP` untimed ones,
and that choice is not decoration. Each call takes 0.1-2 ms, well inside OS scheduling noise,
and this tree is routinely built by several concurrent Mojo processes; measured on one machine
at load average 564, single-sample growth ratios on unchanged code ranged over 0.06x to 41x
and the gate failed 7 runs out of 8. Contention only ever ADDS time to a sample, so the floor
over a handful of samples reads the shape and the mean reads the machine's mood. A gate that
flakes trains the reader to re-run it, which is the same as not having it.

1. **A duplicate scan is O(n), not O(n^2).** The whole reason it goes through the frozen
   `columnar.hash_index.CompositeKeyIndex` instead of comparing pairs. Measured as ns per
   ROW across a 16x rise in n, against a pairwise reference implemented HERE (not in the
   kernel) so the two shapes are visible side by side rather than asserted. The reference
   also produces a group count, and the two counts must agree exactly — a faster scan that
   groups differently is not a faster scan.

2. **A profile is O(n), not O(n^2).** `engines/column_profiler._count_distinct_float`
   deduplicates with an insertion sort, which is quadratic; `data_quality.profile` uses the
   frozen hash index. The insertion-sort shape is reproduced here as the reference for the
   same reason as above. Measured as ns per row across a 16x rise.

3. **An expectation costs one pass per plan node per row.** Measured as ns per row at a
   fixed plan across a 16x rise in rows: flat means the per-row cost does not depend on how
   many rows there are.

4. **A suite of k expectations costs k * rows, not k^2 * rows.** Measured as ns per
   (expectation x row) across an 8x rise in k. This is the factor a work budget most often
   forgets to charge, and a budget that counts one factor of a product is not a budget.

4b. **The same claim once the budget starts TRUNCATING, which is where it was false.**
   Check 4 keeps every row inside the budget, so `rows_checked == n_rows` and a driver that
   extracts the full column per expectation is indistinguishable from one that extracts the
   prefix. The undercharge only shows when `rows` diverges from `n_rows`, so this varies k
   at a row count PAST the ceiling and watches the per-unit cost as the admitted prefix
   shrinks. Measured before the prefix extraction landed: a 256-expectation suite examining
   0.13% of a 4,194,304-row table spent 29x the wall time of a single expectation examining
   33% of it, at an identical declared cost. A shape gate that varies only k cannot see
   that; one that also varies n_rows past the budget can.

5. **The work budget is honest about what it did not check.** At a size over the budget the
   report's `n_rows_checked + n_rows_not_checked` must still equal `n_rows`, and
   `work_truncated` must be set. A partial pass that reported a clean table would be a wrong
   answer rather than a partial one.

Data is generated from the frozen keyed generator `determinism.counter_rng.rng_uniform`
with an explicit master seed, so every number below reproduces bit-for-bit on any machine
and in any order. Nothing here calls `random_float64`.

Gate
----
Fails on the properties, never on absolute nanoseconds:
  * duplicate-scan ns/row must not grow more than 3x across a 16x rise in n
  * the hash-index group count must EQUAL the pairwise reference's group count
  * profile ns/row must not grow more than 3x across a 16x rise in n
  * expectation ns/row must not grow more than 3x across a 16x rise in rows
  * suite ns/(expectation*row) must not grow more than 3x across an 8x rise in k
  * suite ns/(expectation*row) must not grow more than 3x across an 8x rise in k WHILE
    TRUNCATING, and both truncating cases must actually truncate or they measure nothing
  * a truncated report must account for every row and say it truncated
"""
from std.time import perf_counter_ns

from determinism.counter_rng import rng_uniform

from data_quality.contract import (
    DQ_MAX_WORK,
    DQ_OK,
    dq_mask_all_valid,
    dq_status_name,
    dq_values_equal,
)
from data_quality.duplicates import DQ_DUP_EXACT_BITS, duplicate_scan_flat
from data_quality.expect import (
    DQ_EXPECT_GT,
    expect_column_flat,
    expect_plan_flat,
    expect_suite_flat,
)
from data_quality.leakage import leakage_scan_flat
from data_quality.profile import profile_column

comptime WARMUP: Int = 2

# Timed samples per measurement, of which the gate reads the MINIMUM. Each individual call
# here takes 0.1-2 ms, which is well inside OS scheduling noise, and this tree is routinely
# built by several concurrent Mojo processes: measured on this machine at load average 564,
# single-sample growth ratios on unchanged code ranged over 0.06x to 41x and the gate failed
# 7 runs out of 8. The minimum is the right estimator for "how fast is this code" under
# contention, because contention can only ever ADD time to a sample — so the floor over a
# handful of samples is a far more stable read of the shape than the mean of them, and the
# gate is comparing shapes.
#
# EVERY TIMED SAMPLE'S RESULT IS CONSUMED into `acc` and cross-checked against an untimed
# call. A first attempt wrote `var _r = call()` inside the timed region — the spelling the
# WARMUP loops use, where it is harmless because they are untimed — and the numbers got
# WORSE, reporting ratios as absurd as 0.06x on code whose shape had not changed. An unused
# result makes the call dead and a partly eliminated timed region measures nothing. The
# `acc` check is load-bearing twice: it keeps the work alive, and it asserts every sample
# returned the same answer, which is the determinism claim this file makes about the keyed
# generator.
comptime SAMPLES: Int = 7
comptime MASTER_SEED: UInt64 = 0x5DA7A0DA11747900

# `query.ir` opcodes, as a caller sends them over the wire.
comptime IR_LITERAL: Int = 0
comptime IR_GT: Int = 102
comptime IR_COL_REF: Int = 130


def _ns_per(elapsed: UInt, work: Int, reps: Int) -> Float64:
    """`perf_counter_ns` yields UInt, so the delta stays unsigned until here."""
    if work <= 0 or reps <= 0:
        return 0.0
    return Float64(Int(elapsed)) / Float64(work * reps)


def _keyed_column(n: Int, n_distinct: Int, stream: UInt64) -> List[Float64]:
    """`n` values drawn from `n_distinct` levels through the frozen keyed generator.

    A deterministic function of `(MASTER_SEED, stream, i)` only, so the same column comes
    back on every machine and the duplicate structure is fixed rather than sampled.
    """
    var out = List[Float64]()
    var levels = n_distinct if n_distinct > 0 else 1
    for i in range(n):
        var u = rng_uniform(MASTER_SEED, 0, 0, 0, 0, stream, UInt64(i))
        out.append(Float64(Int(u * Float64(levels))))
    return out^


def _pairwise_group_count(values: List[Float64]) -> Int:
    """The O(n^2) reference: for each row, scan every earlier row for an equal key.

    Implemented in the BENCHMARK, never in the kernel. It uses the same equality the kernel
    states (`contract.dq_values_equal`, the frozen normalized bit pattern), so a difference
    in the group count can only come from the indexing and not from the comparison.
    """
    var groups = 0
    for i in range(len(values)):
        var seen = False
        for j in range(i):
            if dq_values_equal(values[i], values[j]):
                seen = True
                break
        if not seen:
            groups += 1
    return groups


def _insertion_sort_distinct(values: List[Float64]) -> Int:
    """The O(n^2) dedup shape that `engines/column_profiler` uses, as the reference.

    Reproduced here rather than called: `_count_distinct_float` is private to that frozen
    module, and this is about the SHAPE of the algorithm, not about that function.
    """
    var n = len(values)
    if n == 0:
        return 0
    var sorted = values.copy()
    for i in range(1, n):
        var key = sorted[i]
        var j = i - 1
        while j >= 0 and sorted[j] > key:
            sorted[j + 1] = sorted[j]
            j -= 1
        sorted[j + 1] = key
    var distinct = 1
    for i in range(1, n):
        if sorted[i] != sorted[i - 1]:
            distinct += 1
    return distinct


def main() raises:
    var failures = 0
    print("=== data_quality: shape gate ===")
    print("keyed generator: determinism.counter_rng.rng_uniform, master seed fixed")
    print("")

    # 1. duplicate scan: O(n) hash index vs an O(n^2) pairwise reference
    print("=== 1. duplicate scan: cost per row across a 16x rise in n ===")
    var dup_sizes = List[Int]()
    dup_sizes.append(1000)
    dup_sizes.append(4000)
    dup_sizes.append(16000)
    var dup_first: Float64 = 0.0
    var dup_last: Float64 = 0.0
    var key_cols = List[Int]()
    key_cols.append(0)
    for s in range(len(dup_sizes)):
        var n = dup_sizes[s]
        var col = _keyed_column(n, n // 4, 11)
        var mask = dq_mask_all_valid(n)
        for _ in range(WARMUP):
            var _w = duplicate_scan_flat(col, n, 1, mask, key_cols, DQ_DUP_EXACT_BITS, 0)
        var report = duplicate_scan_flat(col, n, 1, mask, key_cols, DQ_DUP_EXACT_BITS, 0)
        var acc = 0
        var per_row: Float64 = 0.0
        for _ in range(SAMPLES):
            var t0 = perf_counter_ns()
            var r = duplicate_scan_flat(col, n, 1, mask, key_cols, DQ_DUP_EXACT_BITS, 0)
            var t1 = perf_counter_ns()
            acc += r.n_groups
            var sample = _ns_per(t1 - t0, n, 1)
            if per_row <= 0.0 or sample < per_row:
                per_row = sample
        if acc != SAMPLES * report.n_groups:
            failures += 1
            print("    FAIL samples disagreed:", acc, "vs", SAMPLES * report.n_groups)
        if s == 0:
            dup_first = per_row
        dup_last = per_row
        print(
            "  n=" + String(n),
            "groups=" + String(report.n_groups),
            "duplicate_rows=" + String(report.n_duplicate_rows),
            "ns/row=" + String(per_row),
        )
        if report.status != DQ_OK:
            failures += 1
            print("    FAIL scan refused:", dq_status_name(report.status))

    var dup_growth = dup_last / dup_first if dup_first > 0.0 else 999.0
    if dup_growth <= 3.0:
        print(
            "  ✅ ns/row grew only "
            + String(dup_growth)
            + "x across a 16x rise in n — O(n), not O(n^2)"
        )
    else:
        failures += 1
        print("  ❌ ns/row grew " + String(dup_growth) + "x; the scan is not linear")

    var ref_n = 4000
    var ref_col = _keyed_column(ref_n, ref_n // 4, 11)
    var ref_mask = dq_mask_all_valid(ref_n)
    var t2 = perf_counter_ns()
    var fast = duplicate_scan_flat(ref_col, ref_n, 1, ref_mask, key_cols, DQ_DUP_EXACT_BITS, 0)
    var t3 = perf_counter_ns()
    var t4 = perf_counter_ns()
    var reference_groups = _pairwise_group_count(ref_col)
    var t5 = perf_counter_ns()
    var fast_ms = Float64(Int(t3 - t2)) / 1.0e6
    var pairwise_ms = Float64(Int(t5 - t4)) / 1.0e6
    print("")
    print("  n=" + String(ref_n) + " hash index      " + String(fast_ms) + " ms")
    print("  n=" + String(ref_n) + " pairwise O(n^2) " + String(pairwise_ms) + " ms")
    if fast_ms > 0.0:
        print("  speedup=" + String(pairwise_ms / fast_ms) + "x")
    if fast.n_groups == reference_groups:
        print(
            "  ✅ both report "
            + String(reference_groups)
            + " groups — the speed is over the same answer"
        )
    else:
        failures += 1
        print(
            "  ❌ group counts differ: index "
            + String(fast.n_groups)
            + " vs pairwise "
            + String(reference_groups)
        )

    # 2. profile: O(n) distinct count vs an insertion-sort dedup
    print("")
    print("=== 2. profile: cost per row across a 16x rise in n ===")
    var prof_sizes = List[Int]()
    prof_sizes.append(1000)
    prof_sizes.append(4000)
    prof_sizes.append(16000)
    var prof_first: Float64 = 0.0
    var prof_last: Float64 = 0.0
    for s in range(len(prof_sizes)):
        var n = prof_sizes[s]
        var col = _keyed_column(n, n // 2, 23)
        var mask = dq_mask_all_valid(n)
        for _ in range(WARMUP):
            var _w = profile_column(col, mask, n)
        var p = profile_column(col, mask, n)
        var acc = 0
        var per_row: Float64 = 0.0
        for _ in range(SAMPLES):
            var t6 = perf_counter_ns()
            var q = profile_column(col, mask, n)
            var t7 = perf_counter_ns()
            acc += q.n_distinct_finite
            var sample = _ns_per(t7 - t6, n, 1)
            if per_row <= 0.0 or sample < per_row:
                per_row = sample
        if acc != SAMPLES * p.n_distinct_finite:
            failures += 1
            print("    FAIL samples disagreed:", acc, "vs", SAMPLES * p.n_distinct_finite)
        if s == 0:
            prof_first = per_row
        prof_last = per_row
        print(
            "  n=" + String(n),
            "distinct=" + String(p.n_distinct_finite),
            "mean_present=" + String(p.has_mean),
            "ns/row=" + String(per_row),
        )

    var prof_growth = prof_last / prof_first if prof_first > 0.0 else 999.0
    if prof_growth <= 3.0:
        print(
            "  ✅ ns/row grew only "
            + String(prof_growth)
            + "x across a 16x rise in n — census, dedup and sort all stay near-linear"
        )
    else:
        failures += 1
        print("  ❌ ns/row grew " + String(prof_growth) + "x; the profile is superlinear")

    var pref_col = _keyed_column(ref_n, ref_n // 2, 23)
    var t8 = perf_counter_ns()
    var pfast = profile_column(pref_col, dq_mask_all_valid(ref_n), ref_n)
    var t9 = perf_counter_ns()
    var t10 = perf_counter_ns()
    var insertion_distinct = _insertion_sort_distinct(pref_col)
    var t11 = perf_counter_ns()
    var pfast_ms = Float64(Int(t9 - t8)) / 1.0e6
    var insertion_ms = Float64(Int(t11 - t10)) / 1.0e6
    print("")
    print("  n=" + String(ref_n) + " full profile (hash dedup)  " + String(pfast_ms) + " ms")
    print("  n=" + String(ref_n) + " insertion-sort dedup ALONE " + String(insertion_ms) + " ms")
    if pfast_ms > 0.0:
        print("  speedup=" + String(insertion_ms / pfast_ms) + "x")
    if pfast.n_distinct_finite == insertion_distinct:
        print(
            "  ✅ both report "
            + String(insertion_distinct)
            + " distinct values — same answer, different shape"
        )
    else:
        failures += 1
        print(
            "  ❌ distinct counts differ: hash "
            + String(pfast.n_distinct_finite)
            + " vs insertion sort "
            + String(insertion_distinct)
        )

    # 3. one expectation: cost per row flat as rows rise
    print("")
    print("=== 3. one expectation: cost per row across a 16x rise in rows ===")
    var exp_sizes = List[Int]()
    exp_sizes.append(1000)
    exp_sizes.append(4000)
    exp_sizes.append(16000)
    var exp_first: Float64 = 0.0
    var exp_last: Float64 = 0.0
    for s in range(len(exp_sizes)):
        var n = exp_sizes[s]
        var col = _keyed_column(n, 1000, 31)
        var mask = dq_mask_all_valid(n)
        for _ in range(WARMUP):
            var _w = expect_column_flat(col, n, 1, mask, 0, DQ_EXPECT_GT, 100.0, 0.0, 0)
        var r = expect_column_flat(col, n, 1, mask, 0, DQ_EXPECT_GT, 100.0, 0.0, 0)
        var acc = 0
        var per_row: Float64 = 0.0
        for _ in range(SAMPLES):
            var t12 = perf_counter_ns()
            var q = expect_column_flat(col, n, 1, mask, 0, DQ_EXPECT_GT, 100.0, 0.0, 0)
            var t13 = perf_counter_ns()
            acc += q.n_violations
            var sample = _ns_per(t13 - t12, n, 1)
            if per_row <= 0.0 or sample < per_row:
                per_row = sample
        if acc != SAMPLES * r.n_violations:
            failures += 1
            print("    FAIL samples disagreed:", acc, "vs", SAMPLES * r.n_violations)
        if s == 0:
            exp_first = per_row
        exp_last = per_row
        print(
            "  rows=" + String(n),
            "violations=" + String(r.n_violations),
            "checked=" + String(r.n_rows_checked),
            "ns/row=" + String(per_row),
        )
        if r.status != DQ_OK:
            failures += 1
            print("    FAIL expectation refused:", dq_status_name(r.status))

    var exp_growth = exp_last / exp_first if exp_first > 0.0 else 999.0
    if exp_growth <= 3.0:
        print(
            "  ✅ ns/row grew only "
            + String(exp_growth)
            + "x across a 16x rise in rows — one pass per node per row"
        )
    else:
        failures += 1
        print("  ❌ ns/row grew " + String(exp_growth) + "x; the evaluation is superlinear")

    # 4. a suite: cost per (expectation x row) flat as k rises
    print("")
    print("=== 4. suite: cost per (expectation x row) across an 8x rise in k ===")
    var suite_rows = 2000
    var suite_col = _keyed_column(suite_rows, 1000, 37)
    var suite_mask = dq_mask_all_valid(suite_rows)
    var k_values = List[Int]()
    k_values.append(4)
    k_values.append(16)
    k_values.append(32)
    var suite_first: Float64 = 0.0
    var suite_last: Float64 = 0.0
    for s in range(len(k_values)):
        var k = k_values[s]
        var cols = List[Int]()
        var ops = List[Int]()
        var lows = List[Float64]()
        var highs = List[Float64]()
        for _ in range(k):
            cols.append(0)
            ops.append(DQ_EXPECT_GT)
            lows.append(100.0)
            highs.append(0.0)
        for _ in range(WARMUP):
            var _w = expect_suite_flat(
                suite_col, suite_rows, 1, suite_mask, cols, ops, lows, highs, 0
            )
        var r = expect_suite_flat(
            suite_col, suite_rows, 1, suite_mask, cols, ops, lows, highs, 0
        )
        var acc = 0
        var per_unit: Float64 = 0.0
        for _ in range(SAMPLES):
            var t14 = perf_counter_ns()
            var q = expect_suite_flat(
                suite_col, suite_rows, 1, suite_mask, cols, ops, lows, highs, 0
            )
            var t15 = perf_counter_ns()
            acc += q.n_violations
            var sample = _ns_per(t15 - t14, k * r.n_rows_checked, 1)
            if per_unit <= 0.0 or sample < per_unit:
                per_unit = sample
        if acc != SAMPLES * r.n_violations:
            failures += 1
            print("    FAIL samples disagreed:", acc, "vs", SAMPLES * r.n_violations)
        if s == 0:
            suite_first = per_unit
        suite_last = per_unit
        print(
            "  k=" + String(k),
            "rows_checked=" + String(r.n_rows_checked),
            "violations=" + String(r.n_violations),
            "ns/(k*row)=" + String(per_unit),
        )
        if r.status != DQ_OK:
            failures += 1
            print("    FAIL suite refused:", dq_status_name(r.status))

    var suite_growth = suite_last / suite_first if suite_first > 0.0 else 999.0
    if suite_growth <= 3.0:
        print(
            "  ✅ ns/(k*row) grew only "
            + String(suite_growth)
            + "x across an 8x rise in k — linear in the suite, not quadratic"
        )
    else:
        failures += 1
        print("  ❌ ns/(k*row) grew " + String(suite_growth) + "x; k is not charged linearly")

    # 4b. THE SAME MEASUREMENT, PAST THE BUDGET. Check 4 cannot see the defect that lived
    # here, and the reason is worth stating: it pins `suite_rows` at 2000, which is small
    # enough that `rows_checked == n_rows` for every k it tries. While those two are equal,
    # a driver that extracts the FULL column per expectation and one that extracts the
    # PREFIX do identical work, so the per-unit cost looks flat either way. The undercharge
    # only appears once `rows` diverges from `n_rows` — so this check drives n_rows PAST the
    # ceiling and lets the admitted prefix shrink as k rises.
    #
    # 2^19 rows over 1 column at 3 nodes per GT expectation: k=4 costs 12 per row and the
    # budget admits 4194304 // 12 = 349525; k=256 costs 768 and admits 5461. Both truncate.
    # Charged cost is k * rows_checked: 1398100 against 1398016, flat to within 0.01%, so
    # ns/(k*row) must be flat. Extracting the full column instead makes the real work
    # k * n_rows — 4 * 524288 against 256 * 524288, a SIXTY-FOUR-fold rise at a flat
    # declared cost.
    #
    # The 64x spread is deliberate and it is the second version of this check. An 8x spread
    # (k=8 vs k=64) discriminated only intermittently: the un-truncated driver's own
    # allocation churn inflates the SMALL-k baseline as well, which compresses the ratio, and
    # measured across three runs it came out 2.1x / 2.6x / 2.7x — under a 3.0x gate three
    # times out of three while the defect was present. A shape gate whose effect size is
    # near its noise floor is not a gate. WARMUP applies here as it does everywhere else,
    # for the same reason.
    print("")
    print("=== 4b. suite PAST the budget: per-unit cost as the admitted prefix shrinks ===")
    var trunc_rows = 1 << 19
    var trunc_col = _keyed_column(trunc_rows, 1000, 43)
    var trunc_mask = dq_mask_all_valid(trunc_rows)
    var trunc_ks = List[Int]()
    trunc_ks.append(4)
    trunc_ks.append(256)
    var trunc_first: Float64 = 0.0
    var trunc_last: Float64 = 0.0
    for s in range(len(trunc_ks)):
        var k = trunc_ks[s]
        var cols = List[Int]()
        var ops = List[Int]()
        var lows = List[Float64]()
        var highs = List[Float64]()
        for _ in range(k):
            cols.append(0)
            ops.append(DQ_EXPECT_GT)
            lows.append(100.0)
            highs.append(0.0)
        for _ in range(WARMUP):
            var _w = expect_suite_flat(
                trunc_col, trunc_rows, 1, trunc_mask, cols, ops, lows, highs, 0
            )
        var r = expect_suite_flat(
            trunc_col, trunc_rows, 1, trunc_mask, cols, ops, lows, highs, 0
        )
        var acc = 0
        var per_unit: Float64 = 0.0
        for _ in range(SAMPLES):
            var t20 = perf_counter_ns()
            var q = expect_suite_flat(
                trunc_col, trunc_rows, 1, trunc_mask, cols, ops, lows, highs, 0
            )
            var t21 = perf_counter_ns()
            acc += q.n_violations
            var sample = _ns_per(t21 - t20, k * r.n_rows_checked, 1)
            if per_unit <= 0.0 or sample < per_unit:
                per_unit = sample
        if acc != SAMPLES * r.n_violations:
            failures += 1
            print("    FAIL samples disagreed:", acc, "vs", SAMPLES * r.n_violations)
        if s == 0:
            trunc_first = per_unit
        trunc_last = per_unit
        print(
            "  k=" + String(k),
            "n_rows=" + String(trunc_rows),
            "rows_checked=" + String(r.n_rows_checked),
            "not_checked=" + String(r.n_rows_not_checked),
            "charged=" + String(k * r.n_rows_checked),
            "ns/(k*row)=" + String(per_unit),
        )
        if r.status != DQ_OK:
            failures += 1
            print("    FAIL suite refused:", dq_status_name(r.status))
        if not r.work_truncated or r.n_rows_checked >= trunc_rows:
            failures += 1
            print("    FAIL this case must TRUNCATE or it measures nothing")

    var trunc_growth = trunc_last / trunc_first if trunc_first > 0.0 else 999.0
    if trunc_growth <= 3.0:
        print(
            "  ✅ ns/(k*row) grew only "
            + String(trunc_growth)
            + "x while the admitted prefix shrank 64x — the loop costs what the budget charged"
        )
    else:
        failures += 1
        print(
            "  ❌ ns/(k*row) grew " + String(trunc_growth)
            + "x; a truncated suite is paying for rows it declared unchecked"
        )

    # 5. the budget says what it did not check
    print("")
    print("=== 5. over the budget: the report accounts for every row ===")
    # `expect_plan_flat` charges `n_cols + n_nodes` per row. With a 1024-node plan over one
    # column that is 1025, so the 2^22 budget admits 4194304 // 1025 = 4092 rows.
    var n_nodes = 1024
    var budget_rows = 4093
    var budget_col = _keyed_column(budget_rows, 1000, 41)
    var budget_mask = dq_mask_all_valid(budget_rows)
    var pad_ints = List[Int]()
    var pad_fvals = List[Float64]()
    pad_ints.append(IR_COL_REF)
    pad_ints.append(0)
    pad_ints.append(-1)
    pad_ints.append(-1)
    pad_ints.append(-1)
    pad_fvals.append(0.0)
    pad_ints.append(IR_LITERAL)
    pad_ints.append(-1)
    pad_ints.append(-1)
    pad_ints.append(-1)
    pad_ints.append(-1)
    pad_fvals.append(100.0)
    for _ in range(n_nodes - 3):
        pad_ints.append(IR_LITERAL)
        pad_ints.append(-1)
        pad_ints.append(-1)
        pad_ints.append(-1)
        pad_ints.append(-1)
        pad_fvals.append(0.0)
    pad_ints.append(IR_GT)
    pad_ints.append(-1)
    pad_ints.append(0)
    pad_ints.append(1)
    pad_ints.append(-1)
    pad_fvals.append(0.0)

    var t16 = perf_counter_ns()
    var truncated = expect_plan_flat(
        budget_col, budget_rows, 1, budget_mask, pad_ints, pad_fvals, n_nodes - 1, 0, 0
    )
    var t17 = perf_counter_ns()
    print(
        "  nodes=" + String(n_nodes),
        "rows=" + String(budget_rows),
        "checked=" + String(truncated.n_rows_checked),
        "not_checked=" + String(truncated.n_rows_not_checked),
        "ms=" + String(Float64(Int(t17 - t16)) / 1.0e6),
    )
    print(
        "  budget=" + String(DQ_MAX_WORK)
        + " work units, charged as (n_cols + n_nodes) per row"
    )
    if (
        truncated.status == DQ_OK
        and truncated.work_truncated
        and truncated.n_rows_checked + truncated.n_rows_not_checked == truncated.n_rows
        and truncated.n_rows_not_checked > 0
    ):
        print("  ✅ every row is accounted for, and work_truncated says the pass was partial")
    else:
        failures += 1
        print("  ❌ a truncated pass did not account for its rows")

    # 6. leakage scan cost per row, for tracking
    print("")
    print("=== 6. leakage scan: cost per row (tracking), and the proof at scale ===")
    var leak_n = 8000
    var leak_target = _keyed_column(leak_n, leak_n, 53)
    var leak_feature = List[Float64]()
    for i in range(leak_n):
        leak_feature.append(3.0 * leak_target[i] + 5.0)
    var leak_mask = dq_mask_all_valid(leak_n)
    for _ in range(WARMUP):
        var _w = leakage_scan_flat(
            leak_feature, leak_mask, leak_target, leak_mask, leak_n, 0.95, 0.95
        )
    var t18 = perf_counter_ns()
    var leak = leakage_scan_flat(
        leak_feature, leak_mask, leak_target, leak_mask, leak_n, 0.95, 0.95
    )
    var t19 = perf_counter_ns()
    print(
        "  n=" + String(leak_n),
        "proven_affine=" + String(leak.proven_affine),
        "slope=" + String(leak.affine_slope),
        "intercept=" + String(leak.affine_intercept),
        "ns/row=" + String(_ns_per(t19 - t18, leak_n, 1)),
    )
    if leak.proven_affine and leak.affine_slope == 3.0 and leak.affine_intercept == 5.0:
        print("  ✅ 8000 keyed rows of 3y+5 are still proven exactly affine")
    else:
        failures += 1
        print("  ❌ the affine proof did not hold at scale:", leak.affine_slope)

    print("")
    if failures == 0:
        print("BENCH_GATE data_quality PASS")
    else:
        print("BENCH_GATE data_quality FAIL " + String(failures))
        raise Error("bench_data_quality: " + String(failures) + " gate failure(s)")
