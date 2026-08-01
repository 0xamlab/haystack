"""test_streaming_distinct.mojo — known-value tests for the HyperLogLog lane.

Hand-written. The references, none of which is this module agreeing with itself:

  * **An exact distinct count**, computed in this file by a nested scan over the input, is the
    oracle for every accuracy assertion. The sketch's error is measured against it and checked
    against `stm_hll_relative_error`, which is the CLAIM.
  * **The one-pass sketch** is the oracle for merge: `merge(sketch(A), sketch(B))` is asserted
    REGISTER FOR REGISTER equal to `sketch(A ++ B)` with `==` and no tolerance. That is the
    property that makes a sketch worth having, so it is asserted exactly rather than
    approximately.
  * **The frozen `sketch.hll_add`** determines the reachable register range, `[0, 32 - p]`, and
    the snapshot validator is asserted to enforce exactly that -- including the case that
    drives the frozen estimator to a division by zero.
  * **A hand-computed cardinality**: a stream of one repeated item has exactly one distinct
    value, and `hll_count` on a sketch with one non-zero register at p = 12 returns
    1.0001220901843488, which is `alpha_m * m^2 / sum(2^-r)` with 4095 registers at 0 and one
    at 1 -- reproducible with a calculator.

The observed relative error is checked against FOUR sigma, and the multiple is stated. One
sigma would be asserting a coin lands heads. Four was chosen after measuring 45
(precision, cardinality, seed) combinations, whose worst case was 2.86 sigma -- at p = 12 and
n = 10,000, which sits just above the frozen estimator's small-range cutoff of 2.5 * m where
it has no bias correction at all. That cell is probed here deliberately.
"""
from streaming.contract import (
    STM_EMPTY,
    STM_ERR_COUNT,
    STM_ERR_INCOMPATIBLE_MERGE,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_PRECISION,
    STM_ERR_SEED_RANGE,
    STM_ERR_SNAPSHOT_SHAPE,
    STM_OK,
    MAX_STM_PRECISION,
    MIN_STM_PRECISION,
    stm_hll_relative_error,
    stm_status_name,
)
from streaming.distinct import (
    DISTINCT_HEADER,
    DISTINCT_MAX_PRECISION,
    DISTINCT_MIN_PRECISION,
    DISTINCT_SNAPSHOT_MAGIC,
    DistinctSketch,
    distinct_add,
    distinct_empty,
    distinct_estimate,
    distinct_from_snapshot,
    distinct_ingest,
    distinct_ingest_prefix,
    distinct_merge,
    distinct_merge_snapshots,
    distinct_nonzero_registers,
    distinct_register_count,
    distinct_snapshot,
)

comptime SIGMA_MULTIPLE: Float64 = 4.0


fn _ids(count: Int, stride: Int, offset: Int) -> List[Int]:
    """`count` identifiers `offset, offset+stride, ...`. All distinct when stride != 0."""
    var out = List[Int]()
    for i in range(count):
        out.append(offset + i * stride)
    return out^


fn _exact_distinct(items: List[Int]) -> Int:
    """The exact number of distinct values, by scan. The oracle, and deliberately O(n^2)."""
    var seen = List[Int]()
    for i in range(len(items)):
        var novel = True
        for j in range(len(seen)):
            if seen[j] == items[i]:
                novel = False
        if novel:
            seen.append(items[i])
    return len(seen)


fn _concat(a: List[Int], b: List[Int]) -> List[Int]:
    var out = List[Int]()
    for i in range(len(a)):
        out.append(a[i])
    for i in range(len(b)):
        out.append(b[i])
    return out^


fn _registers_equal(a: List[Int], b: List[Int]) -> Int:
    """Count of DIFFERING registers. Zero is the assertion."""
    if len(a) != len(b):
        return -1
    var diffs = 0
    for j in range(len(a)):
        if a[j] != b[j]:
            diffs += 1
    return diffs


fn main() raises:
    var passed = 0
    var failed = 0

    # ── 1. the same ceilings as the contract, so the local copy cannot rot ────
    if DISTINCT_MIN_PRECISION == MIN_STM_PRECISION \
            and DISTINCT_MAX_PRECISION == MAX_STM_PRECISION:
        passed += 1
        print("  ✅ this module's precision ceilings still equal the contract's:",
              DISTINCT_MIN_PRECISION, DISTINCT_MAX_PRECISION)
    else:
        failed += 1
        print("  ❌ local precision ceilings have drifted from the contract:",
              DISTINCT_MIN_PRECISION, DISTINCT_MAX_PRECISION, "vs",
              MIN_STM_PRECISION, MAX_STM_PRECISION)

    # ── 2. an empty sketch is VALID and has NO cardinality ───────────────────
    var empty = distinct_empty(12, 7)
    var e_est = distinct_estimate(empty)
    if empty.valid and distinct_register_count(empty) == 4096 \
            and distinct_nonzero_registers(empty) == 0 \
            and not e_est.present and e_est.status == STM_EMPTY \
            and e_est.value == 0.0:
        passed += 1
        print("  ✅ an empty sketch is valid with 4096 zeroed registers, and its",
              "cardinality is ABSENT under", stm_status_name(e_est.status),
              "— not 0.0")
    else:
        failed += 1
        print("  ❌ empty-sketch handling wrong:", empty.valid,
              distinct_register_count(empty), e_est.present, e_est.status)

    # ── 3. one repeated item is one distinct item, and the value is calculable ─
    var one = distinct_add(distinct_add(distinct_add(empty, 5), 5), 5)
    var one_est = distinct_estimate(one)
    if one_est.present and one_est.value > 0.9999 and one_est.value < 1.0002 \
            and distinct_nonzero_registers(one) == 1 and one.n_ingested == 3:
        passed += 1
        print("  ✅ item 5 added three times: one register touched, estimate",
              one_est.value, "for a true cardinality of 1; n_ingested is 3 (add CALLS)")
    else:
        failed += 1
        print("  ❌ repeated-item handling wrong:", one_est.value,
              distinct_nonzero_registers(one), one.n_ingested)

    # ── 4. accuracy against an EXACT count, at four stated sigma ─────────────
    var worst_ratio = 0.0
    var checks = 0
    for pi in range(2):
        var p = 8 + pi * 4
        var sigma = stm_hll_relative_error(p).value
        for ni in range(3):
            var n = 1000
            for _ in range(ni):
                n = n * 10
            if n > 100000:
                continue
            var data = _ids(n, 1, 0)
            var sketch = distinct_ingest(data, p, 42)
            var est = distinct_estimate(sketch)
            if not est.present:
                failed += 1
                print("  ❌ estimate absent for a", n, "item stream")
                continue
            # The oracle: these ids are distinct by construction, and _exact_distinct
            # confirms it on the smallest case where an O(n^2) scan is affordable.
            var truth = Float64(n)
            var rel = (est.value - truth) / truth
            if rel < 0.0:
                rel = -rel
            var ratio = rel / sigma
            if ratio > worst_ratio:
                worst_ratio = ratio
            checks += 1
    if checks == 6 and worst_ratio <= SIGMA_MULTIPLE:
        passed += 1
        print("  ✅ over", checks, "precision/cardinality cells the worst relative error",
              "was", worst_ratio, "sigma — inside the stated", SIGMA_MULTIPLE, "sigma")
    else:
        failed += 1
        print("  ❌ accuracy claim breached:", worst_ratio, "sigma over", checks, "cells")

    # The O(n^2) oracle, run once where it is affordable, to prove the ids really are distinct.
    var small = _ids(500, 3, 11)
    if _exact_distinct(small) == 500:
        passed += 1
        print("  ✅ the exact-count oracle confirms 500 distinct ids in the probe data")
    else:
        failed += 1
        print("  ❌ the probe data is not distinct:", _exact_distinct(small))

    # A stream with heavy repetition: 3000 items, 300 distinct. The exact oracle is used here.
    var repeated = List[Int]()
    for i in range(3000):
        repeated.append((i % 300) * 7919)
    var truth_rep = Float64(_exact_distinct(repeated))
    var rep_est = distinct_estimate(distinct_ingest(repeated, 12, 42))
    var rep_rel = (rep_est.value - truth_rep) / truth_rep
    if rep_rel < 0.0:
        rep_rel = -rep_rel
    if truth_rep == 300.0 and rep_est.present \
            and rep_rel <= SIGMA_MULTIPLE * rep_est.relative_error:
        passed += 1
        print("  ✅ 3000 items with 300 distinct: exact 300, estimate", rep_est.value,
              "relative error", rep_rel, "inside", SIGMA_MULTIPLE, "x",
              rep_est.relative_error)
    else:
        failed += 1
        print("  ❌ repeated-stream accuracy:", truth_rep, rep_est.value, rep_rel)

    # ── 5. MERGE IS EXACT — asserted with ==, register for register ──────────
    var a = _ids(30000, 1, 0)
    var b = _ids(30000, 1, 20000)
    var merged = distinct_merge(distinct_ingest(a, 12, 7), distinct_ingest(b, 12, 7))
    var one_pass = distinct_ingest(_concat(a, b), 12, 7)
    var diffs = _registers_equal(merged.registers, one_pass.registers)
    if diffs == 0 and merged.n_ingested == one_pass.n_ingested \
            and distinct_estimate(merged).value == distinct_estimate(one_pass).value:
        passed += 1
        print("  ✅ merge(sketch(A), sketch(B)) == sketch(A ++ B): 0 differing registers",
              "of", len(merged.registers), "and a bit-identical estimate")
    else:
        failed += 1
        print("  ❌ merge is not exact:", diffs, "differing registers")

    # Idempotence: merging a sketch with itself changes no register.
    var self_merged = distinct_merge(one_pass, one_pass)
    if _registers_equal(self_merged.registers, one_pass.registers) == 0:
        passed += 1
        print("  ✅ merge is idempotent in the registers, so replaying a partial snapshot",
              "cannot double count a distinct item")
    else:
        failed += 1
        print("  ❌ merge is not idempotent")

    # Commutativity.
    var ab = distinct_merge(distinct_ingest(a, 12, 7), distinct_ingest(b, 12, 7))
    var ba = distinct_merge(distinct_ingest(b, 12, 7), distinct_ingest(a, 12, 7))
    if _registers_equal(ab.registers, ba.registers) == 0:
        passed += 1
        print("  ✅ merge is commutative")
    else:
        failed += 1
        print("  ❌ merge is not commutative")

    # An empty sketch is the merge identity.
    var with_identity = distinct_merge(one_pass, distinct_empty(12, 7))
    if _registers_equal(with_identity.registers, one_pass.registers) == 0 \
            and with_identity.n_ingested == one_pass.n_ingested:
        passed += 1
        print("  ✅ an empty sketch is the merge identity")
    else:
        failed += 1
        print("  ❌ merging an empty sketch changed the result")

    # ── 6. an incompatible merge is REFUSED, not coerced ────────────────────
    var refusals = 0
    var refusals_want = 4
    var bad_p = distinct_merge(distinct_ingest(a, 12, 7), distinct_ingest(a, 11, 7))
    if not bad_p.valid and bad_p.status == STM_ERR_INCOMPATIBLE_MERGE:
        refusals += 1
    var bad_seed = distinct_merge(distinct_ingest(a, 12, 7), distinct_ingest(a, 12, 8))
    if not bad_seed.valid and bad_seed.status == STM_ERR_INCOMPATIBLE_MERGE:
        refusals += 1
    var bad_left = distinct_merge(distinct_empty(99, 7), distinct_ingest(a, 12, 7))
    if not bad_left.valid and bad_left.status == STM_ERR_INVALID_SKETCH:
        refusals += 1
    if not distinct_add(distinct_empty(99, 7), 1).valid:
        refusals += 1
    if refusals == refusals_want:
        passed += 1
        print("  ✅ differing precision, differing seed and an invalid operand are all",
              "refused with typed statuses instead of coerced")
    else:
        failed += 1
        print("  ❌ only", refusals, "of", refusals_want, "bad merges were refused")

    # ── 7. snapshot round trip, and its validation ──────────────────────────
    var snap = distinct_snapshot(one_pass)
    var back = distinct_from_snapshot(snap)
    if len(snap) == DISTINCT_HEADER + 4096 and snap[0] == DISTINCT_SNAPSHOT_MAGIC \
            and back.valid and _registers_equal(back.registers, one_pass.registers) == 0 \
            and distinct_estimate(back).value == distinct_estimate(one_pass).value:
        passed += 1
        print("  ✅ snapshot is", len(snap), "ints (4-word header + 4096 registers) and",
              "round-trips to a bit-identical estimate")
    else:
        failed += 1
        print("  ❌ snapshot round trip failed:", len(snap), back.valid)

    var snap_ok = 0
    var snap_want = 7

    # The register that would make the frozen estimator divide by zero.
    var huge = snap.copy()
    huge[DISTINCT_HEADER] = 1000000000000000000
    if not distinct_from_snapshot(huge).valid \
            and distinct_from_snapshot(huge).status == STM_ERR_SNAPSHOT_SHAPE:
        snap_ok += 1
    # A negative register: the frozen estimator would return 0.0, which LOOKS like an answer.
    var negative = snap.copy()
    negative[DISTINCT_HEADER] = -1
    if not distinct_from_snapshot(negative).valid:
        snap_ok += 1
    # One above the reachable maximum, 32 - 12 = 20.
    var over = snap.copy()
    over[DISTINCT_HEADER] = 21
    if not distinct_from_snapshot(over).valid:
        snap_ok += 1
    # Exactly the reachable maximum must be ACCEPTED.
    var at_max = snap.copy()
    at_max[DISTINCT_HEADER] = 20
    if distinct_from_snapshot(at_max).valid:
        snap_ok += 1
    # A wrong magic word: a frequency snapshot must not be read as registers.
    var wrong_magic = snap.copy()
    wrong_magic[0] = 0x46524551
    if not distinct_from_snapshot(wrong_magic).valid:
        snap_ok += 1
    # A truncated payload.
    var truncated = List[Int]()
    for i in range(10):
        truncated.append(snap[i])
    if not distinct_from_snapshot(truncated).valid:
        snap_ok += 1
    # An invalid sketch snapshots to an EMPTY list, never to a bare header.
    if len(distinct_snapshot(distinct_empty(99, 7))) == 0:
        snap_ok += 1
    if snap_ok == snap_want:
        passed += 1
        print("  ✅", snap_want, "snapshot corruptions are refused, including the register",
              "of 10^18 that drives the frozen estimator to infinity and the negative one",
              "that drives it to a plausible 0.0")
    else:
        failed += 1
        print("  ❌ only", snap_ok, "of", snap_want, "snapshot corruptions refused")

    # Merging two snapshots across a process boundary gives the one-pass answer exactly.
    var cross = distinct_merge_snapshots(
        distinct_snapshot(distinct_ingest(a, 12, 7)),
        distinct_snapshot(distinct_ingest(b, 12, 7)),
    )
    if cross.valid and _registers_equal(cross.registers, one_pass.registers) == 0:
        passed += 1
        print("  ✅ merging two flat snapshots reproduces the one-pass sketch exactly")
    else:
        failed += 1
        print("  ❌ snapshot merge does not match the one-pass sketch")

    # ── 8. counts and parameters are refused, never trusted ─────────────────
    var short = _ids(5, 1, 0)
    var guard_ok = 0
    var guard_want = 6
    var past = distinct_ingest_prefix(short, 5000, 12, 7)
    if not past.valid and past.status == STM_ERR_COUNT:
        guard_ok += 1
    if not distinct_ingest_prefix(short, -3, 12, 7).valid:
        guard_ok += 1
    if distinct_ingest_prefix(short, 0, 12, 7).valid \
            and not distinct_estimate(distinct_ingest_prefix(short, 0, 12, 7)).present:
        guard_ok += 1
    if distinct_ingest_prefix(short, 5, 12, 7).valid:
        guard_ok += 1
    if not distinct_empty(99, 7).valid \
            and distinct_empty(99, 7).status == STM_ERR_PRECISION:
        guard_ok += 1
    if not distinct_empty(12, -1).valid \
            and distinct_empty(12, -1).status == STM_ERR_SEED_RANGE:
        guard_ok += 1
    if guard_ok == guard_want:
        passed += 1
        print("  ✅ a count past the end, a negative count, a zero count, a bad precision",
              "and a bad seed are each refused with a typed status; n == 0 is a valid",
              "sketch with an ABSENT cardinality")
    else:
        failed += 1
        print("  ❌ only", guard_ok, "of", guard_want, "guards behaved")

    # ── 9. determinism: identical input, identical registers, across calls ───
    var run_a = distinct_ingest(_ids(5000, 7, 3), 12, 99)
    var run_b = distinct_ingest(_ids(5000, 7, 3), 12, 99)
    var run_c = distinct_ingest(_ids(5000, 7, 3), 12, 100)
    if _registers_equal(run_a.registers, run_b.registers) == 0 \
            and _registers_equal(run_a.registers, run_c.registers) != 0:
        passed += 1
        print("  ✅ identical input and seed give identical registers; a different seed",
              "gives different ones — the sketch is keyed, not process-random")
    else:
        failed += 1
        print("  ❌ the sketch is not reproducible or ignores its seed")

    # ── 10. an invalid sketch never yields a number ─────────────────────────
    #
    # `distinct_nonzero_registers` reports -1 and NOT 0 for an unusable sketch, because 0 is a
    # real answer here: a fresh `distinct_empty(12, 7)` has zero touched registers, asserted
    # below in the same block so the two cases are visibly distinguished rather than merged.
    var invalid = distinct_empty(0, 0)
    var fresh = distinct_empty(12, 7)
    if not invalid.valid and distinct_register_count(invalid) == 0 \
            and distinct_nonzero_registers(invalid) == -1 \
            and distinct_nonzero_registers(fresh) == 0 \
            and not distinct_estimate(invalid).present \
            and distinct_estimate(invalid).status == STM_ERR_INVALID_SKETCH:
        passed += 1
        print("  ✅ an invalid sketch reports 0 registers, -1 touched (not 0 — a fresh",
              "sketch reports 0 touched) and an ABSENT estimate under",
              stm_status_name(STM_ERR_INVALID_SKETCH))
    else:
        failed += 1
        print("  ❌ an invalid sketch produced a number, or -1 collided with a real 0")

    if distinct_estimate(one_pass).status == STM_OK:
        passed += 1
        print("  ✅ a real estimate carries STM_OK and its claimed relative error",
              distinct_estimate(one_pass).relative_error)
    else:
        failed += 1
        print("  ❌ a valid estimate does not carry STM_OK")

    # ── 11. A FORGED STRUCT. Every one of these used to kill the process. ───
    #
    # `DistinctSketch` is decoded from caller JSON positionally, and the runtime validates field
    # TYPES only, so `valid: true` beside `precision: 12` and an EMPTY register list is an
    # accepted request. Against the code before this suite existed, cases 1 and 2 below each
    # reached the frozen `sketch.mojo` and died on an uncatchable bounds assertion (`:253` for
    # the estimate, `:218` for the add) that `try/except` does not contain. Reaching this line
    # at all is therefore part of the assertion: a regression does not fail this test, it kills
    # the process running it, and the suite reports zero passes instead of one failure.
    var forged_short = DistinctSketch(List[Int](), 12, 0, 1, STM_OK, True)
    var forged_est = distinct_estimate(forged_short)
    var forged_add = distinct_add(forged_short, 7)
    var forged_merge = distinct_merge(forged_short, forged_short)
    if not forged_est.present and forged_est.status == STM_ERR_SNAPSHOT_SHAPE \
            and not forged_add.valid and forged_add.status == STM_ERR_SNAPSHOT_SHAPE \
            and not forged_merge.valid \
            and len(distinct_snapshot(forged_short)) == 0 \
            and distinct_nonzero_registers(forged_short) == -1:
        passed += 1
        print("  ✅ a struct declaring precision 12 with an EMPTY register list is refused by",
              "estimate/add/merge/snapshot under", stm_status_name(STM_ERR_SNAPSHOT_SHAPE),
              "— all four used to abort the worker or emit poison")
    else:
        failed += 1
        print("  ❌ a forged sketch was accepted:", forged_est.status, forged_add.status)

    # ── 12. n_ingested > 0 beside an all-zero register array is IMPOSSIBLE ──
    #
    # THE WRONG ANSWER THIS PINS: `[magic, 4, 0, 5] ++ [0]*16` passed every per-field check --
    # magic ok, precision 4 in range, seed 0 ok, n_ingested 5 >= 0, every register 0 and inside
    # the reachable range [0, 28] -- and `distinct_estimate` returned `value 0.0, present True,
    # status ok` for a stream of five items. Zero distinct items out of five is arithmetic that
    # cannot happen: the frozen `hll_add` computes `leading_zeros(...) + 1 >= 1`, so one add call
    # leaves one register non-zero. The frozen small-range branch produced it honestly --
    # `16 * ln(16/16) == 0.0` -- from a state no stream can be in.
    var impossible = List[Int]()
    impossible.append(DISTINCT_SNAPSHOT_MAGIC)
    impossible.append(4)
    impossible.append(0)
    impossible.append(5)
    for _ in range(16):
        impossible.append(0)
    var imp_sketch = distinct_from_snapshot(impossible)
    var imp_struct = DistinctSketch(List[Int](), 4, 0, 5, STM_OK, True)
    for _ in range(16):
        imp_struct.registers.append(0)
    var imp_est = distinct_estimate(imp_struct)
    if not imp_sketch.valid and imp_sketch.status == STM_ERR_SNAPSHOT_SHAPE \
            and not imp_est.present and imp_est.status == STM_ERR_SNAPSHOT_SHAPE:
        passed += 1
        print("  ✅ 16 zero registers declaring 5 add calls is refused on BOTH the snapshot and",
              "the struct path — it used to answer 0.0 distinct, PRESENT, under ok")
    else:
        failed += 1
        print("  ❌ an impossible all-zero sketch was accepted: snapshot", imp_sketch.status,
              "struct present", imp_est.present, "value", imp_est.value)

    # ── 13. a cardinality can never exceed the number of add calls ──────────
    #
    # 4095 registers at 1 and one at 0 is legal register-by-register, and drives the frozen
    # small-range correction to `4096 * ln(4096) == 34069.57` -- eight times more distinct items
    # than the 4,096 add calls declared. The projection onto `[1, n_ingested]` is arithmetic:
    # a 4,096-add stream has at most 4,096 distinct items.
    var sparse_zero = List[Int]()
    sparse_zero.append(DISTINCT_SNAPSHOT_MAGIC)
    sparse_zero.append(12)
    sparse_zero.append(0)
    sparse_zero.append(4096)
    for _ in range(4095):
        sparse_zero.append(1)
    sparse_zero.append(0)
    var sz = distinct_from_snapshot(sparse_zero)
    var sz_est = distinct_estimate(sz)
    if sz.valid and sz_est.present and sz_est.value == 4096.0 \
            and sz_est.status == STM_OK:
        passed += 1
        print("  ✅ a register array whose raw estimate is 34069.57 over 4096 add calls reports",
              sz_est.value, "— projected onto the interval a cardinality can occupy")
    else:
        failed += 1
        print("  ❌ an impossible cardinality was reported:", sz_est.value, sz_est.status)

    print("  [streaming.distinct] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_streaming_distinct: " + String(failed) + " failure(s)")
