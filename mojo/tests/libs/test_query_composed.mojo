"""test_query_composed.mojo — `query.composed`, the one route, against the
engines it composes.

Hand-written. The sibling suites (`test_query_coded_dense`,
`test_query_packedkey`, `test_query_aggregate_late`) already pin each engine
against its own reference. This suite exists for the claims that only appear
once they are composed, because a composition can lose what the pieces won and
none of those suites can see it:

  1. THE PARALLEL MERGE MOVES NO BIT. The composition's largest speedup comes
     from fanning the O(groups x aggregates x bands) merge out over group
     ranges. That is only legal if it is a decomposition of the loop rather than
     a re-association of the arithmetic, and the only way to know is to run both
     settings and compare BIT PATTERNS. Every opcode, both layouts, worker
     counts 1/2/3/5/8/16, and the NaN/signed-zero cases where an ulp would show.
  2. THE COMPOSED ROUTE == A SHIPPED ENGINE. `group_by_many_banded` holds
     private tables per contiguous row band and merges in band order — the
     identical fold association a band-local dense array uses — and unlike
     `group_by_coded_parallel` it is not capped at `MAX_CODED_CARDINALITY`, so
     it is the reference that reaches the 1e5-code shapes at all.
  3. THE SEED MOVED INTO THE BAND. min/max seed every private payload to the
     canonical NaN; the composition does it inside the worker that owns the
     memory. The NaN policy is the thing that must survive that move, and it
     was the defect found twice here, so it is re-proven and not assumed.
  4. THE WORKER CAP IS PART OF THE ROUTE. The dense state budget refuses 1e5
     codes at 32 bands and admits them at 16. `compose_dense_workers` is that
     arithmetic and it is checked against `dense_state_bytes` directly.
  5. THE EXACT DOMAIN SCAN AGREES WITH THE GUARD. `compose_exact_domain` and
     `_dense_code` must have the SAME notion of "is a code", or the route
     admits a call the scan then refuses (slow) or refuses one the scan would
     have taken (a lost route). Pinned over the adversarial float set.
  6. REFUSAL IS TOTAL. A key past a probe-derived bound refuses the dense route
     and the composed entry point returns the SHIPPED answer, bitwise. This
     block reaching its own end is itself an assertion: an unguarded dense write
     out of range is an UNCATCHABLE abort that `try` does not contain, so a
     missing guard shows up as a dead process, not a failed check.
  7. THE STATUS BLOCK HAS NO DUPLICATE. Composing turned up `coded_dense` and
     `packedkey` both numbering a different refusal 334. `compose_status_name`
     walks 330..339 and every assigned name must be distinct, so the next
     module that claims a taken number fails here instead of shipping an
     ambiguity to a caller that switches on the status.

Every comparison is BITWISE. `==` calls +0.0 and -0.0 equal and calls every
NaN unequal, and those are exactly the two distinctions an identity claim
needs. Data comes from a fixed-seed LCG in this file, so a failure reproduces.
"""
from std.memory import bitcast

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from columnar.hash_index import CANONICAL_NAN_BITS
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MIN,
    AGG_STD,
    AGG_SUM,
    AGG_VAR,
)
from query.aggregate import (
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_CARDINALITY_INVALID,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    MAX_CODED_CARDINALITY,
    ManyGroupedResult,
    group_by_coded_parallel,
    group_by_many_banded,
    group_by_many_parallel,
)
from query.coded_dense import (
    DENSE_MAX_CARDINALITY,
    DENSE_MAX_STATE_BYTES,
    GROUP_DENSE_OPCODE_UNSUPPORTED,
    GROUP_DENSE_STATE_TOO_LARGE,
    dense_state_bytes,
    group_by_coded_dense_parallel,
)
from query.composed import (
    COMPOSE_EXACT_DOMAIN_MIN_SPAN,
    COMPOSE_PARALLEL_MERGE_MIN_FOLDS,
    COMPOSE_ROUTE_DENSE,
    COMPOSE_ROUTE_LATE,
    COMPOSE_ROUTE_PACKED,
    COMPOSE_ROUTE_SHIPPED,
    compose_dense_workers,
    compose_exact_domain,
    compose_merge_folds,
    compose_plan,
    compose_route_name,
    compose_status_name,
    group_by_composed_dense_parallel,
    group_by_composed_parallel,
)
from query.packedkey import GROUP_PACKED_DOMAIN_TOO_LARGE


struct Tally(Copyable, Movable):
    """Check counter threaded through every block, so a block that silently ran
    ZERO comparisons is visible as a low count rather than as a pass."""

    var checks: Int
    var failures: Int

    fn __init__(out self):
        self.checks = 0
        self.failures = 0

    fn ok(mut self, name: String, condition: Bool):
        self.checks += 1
        if not condition:
            self.failures += 1
            print("  FAIL " + name)


fn _bits(x: Float64) -> UInt64:
    """The bit pattern, so NaN compares equal to NaN and -0.0 does not compare
    equal to +0.0 — the two distinctions `==` cannot make."""
    return bitcast[DType.uint64](x)


fn _lcg(mut state: UInt64) -> UInt64:
    state = state * 6364136223846793005 + 1442695040888963407
    return state


fn _rand01(mut state: UInt64) -> Float64:
    return Float64(Int(_lcg(state) >> 11)) / Float64(Int(UInt64(1) << 53))


fn _canonical() -> Float64:
    return bitcast[DType.float64](CANONICAL_NAN_BITS)


fn _diff_cells(a: ManyGroupedResult, b: ManyGroupedResult) -> Int:
    """Cells where two results differ BITWISE. 0 is identity; keys are compared
    IN ORDER so a permutation is not identity."""
    if a.n_groups() != b.n_groups():
        return 1_000_000_000
    if a.n_aggs != b.n_aggs or a.key_width != b.key_width:
        return 1_000_000_001
    if a.null_key_rows != b.null_key_rows:
        return 1_000_000_002
    if len(a.values) != len(b.values) or len(a.key_tuples) != len(b.key_tuples):
        return 1_000_000_003
    var bad = 0
    for i in range(len(a.key_tuples)):
        if _bits(a.key_tuples[i]) != _bits(b.key_tuples[i]):
            bad += 1
    for i in range(len(a.values)):
        if _bits(a.values[i]) != _bits(b.values[i]):
            bad += 1
        if a.present[i] != b.present[i]:
            bad += 1
        if _bits(a.counts[i]) != _bits(b.counts[i]):
            bad += 1
    return bad


fn _one_key_batch(
    var keys: List[Float64], var values: List[List[Float64]]
) -> RecordBatch:
    var n = len(keys)
    var names = List[String]()
    names.append("k")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(keys^))
    for j in range(len(values)):
        names.append("v" + String(j))
        cols.append(float64_from_list(values[j].copy()))
    return RecordBatch(schema_of(names^), cols^, n)


fn _ints(n: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(n):
        out.append(i)
    return out^


fn _value_cols(n_aggs: Int) -> List[Int]:
    var out = List[Int]()
    for j in range(n_aggs):
        out.append(1 + j)
    return out^


fn _ops(var codes: List[Int]) -> List[Int]:
    return codes^


# ══ block 1 ══ the parallel merge moves no bit ════════════════════════════════
fn block1_merge_decomposition(mut t: Tally):
    """PARALLEL merge == SERIAL merge, bitwise, over every opcode and layout.

    This is the composition's single largest speedup and its single largest
    correctness risk. `merge_one_range` is the only definition of the merge and
    both settings call it, so what is actually being proven here is that the
    PARTITION of the group range is what it claims to be: groups independent,
    each group's fold over workers still ascending. A re-association would show
    on the Welford mean's last ulp, which is why the values below are
    continuous and of mixed magnitude rather than small integers.
    """
    var seed: UInt64 = 0x5EED_C0DE_1234
    var n = 4001
    var K = 37
    var keys = List[Float64](capacity=n)
    var v0 = List[Float64](capacity=n)
    var v1 = List[Float64](capacity=n)
    var v2 = List[Float64](capacity=n)
    for i in range(n):
        keys.append(Float64(Int(_lcg(seed) % UInt64(K))))
        # Mixed magnitudes: a mean folded in a different order differs in the
        # last ulp only when the summands are not all the same size.
        v0.append(_rand01(seed) * 1e6 - 5e5)
        v1.append(_rand01(seed) * 1e-8)
        v2.append(_rand01(seed) * 1e12)
    var vals = List[List[Float64]]()
    vals.append(v0.copy())
    vals.append(v1.copy())
    vals.append(v2.copy())
    var batch = _one_key_batch(keys^, vals^)

    var opsets = List[List[Int]]()
    var labels = List[String]()
    var sets = List[Int]()
    var one_sum = List[Int]()
    one_sum.append(AGG_SUM)
    opsets.append(one_sum^)
    labels.append("sum1")
    sets.append(1)
    var one_avg = List[Int]()
    one_avg.append(AGG_AVG)
    opsets.append(one_avg^)
    labels.append("avg1")
    sets.append(1)
    var one_min = List[Int]()
    one_min.append(AGG_MIN)
    opsets.append(one_min^)
    labels.append("min1")
    sets.append(1)
    var one_max = List[Int]()
    one_max.append(AGG_MAX)
    opsets.append(one_max^)
    labels.append("max1")
    sets.append(1)
    var one_cnt = List[Int]()
    one_cnt.append(AGG_COUNT)
    opsets.append(one_cnt^)
    labels.append("count1")
    sets.append(1)
    var three_avg = List[Int]()
    three_avg.append(AGG_AVG)
    three_avg.append(AGG_AVG)
    three_avg.append(AGG_AVG)
    opsets.append(three_avg^)
    labels.append("avg3")
    sets.append(3)
    var mixed = List[Int]()
    mixed.append(AGG_SUM)
    mixed.append(AGG_MIN)
    mixed.append(AGG_MAX)
    opsets.append(mixed^)
    labels.append("mixed3")
    sets.append(3)
    var mixed2 = List[Int]()
    mixed2.append(AGG_AVG)
    mixed2.append(AGG_COUNT)
    opsets.append(mixed2^)
    labels.append("mixed2")
    sets.append(2)

    var wcounts = List[Int]()
    wcounts.append(1)
    wcounts.append(2)
    wcounts.append(3)
    wcounts.append(5)
    wcounts.append(8)
    wcounts.append(16)

    for s in range(len(opsets)):
        var vc = _value_cols(sets[s])
        for wi in range(len(wcounts)):
            var w = wcounts[wi]
            var par = group_by_composed_dense_parallel(
                batch, 0, K, vc, opsets[s], w, True
            )
            var ser = group_by_composed_dense_parallel(
                batch, 0, K, vc, opsets[s], w, False
            )
            var tag = labels[s] + ".w" + String(w)
            t.ok("block1." + tag + ".par_ok", par.status == GROUP_CODED_OK)
            t.ok("block1." + tag + ".ser_ok", ser.status == GROUP_CODED_OK)
            if par.ok() and ser.ok():
                t.ok(
                    "block1." + tag + ".par_eq_ser",
                    _diff_cells(par.result, ser.result) == 0,
                )
                # And both against the SHIPPED banded engine at the same band
                # count: same private-table-per-band association, so bit
                # equality is owed, not hoped for.
                var banded = group_by_many_banded(
                    batch, _ints(1), vc, opsets[s], w
                )
                t.ok(
                    "block1." + tag + ".par_eq_shipped_banded",
                    _diff_cells(banded, par.result) == 0,
                )
                if K <= MAX_CODED_CARDINALITY:
                    var coded = group_by_coded_parallel(
                        batch, 0, K, vc, opsets[s], w
                    )
                    t.ok("block1." + tag + ".coded_ok", coded.ok())
                    if coded.ok():
                        t.ok(
                            "block1." + tag + ".par_eq_shipped_coded",
                            _diff_cells(coded.result, par.result) == 0,
                        )


# ══ block 2 ══ NaN policy across the in-band seed ═════════════════════════════
fn block2_nan_policy(mut t: Tally):
    """A NaN counts, poisons sum/mean, and contributes to NO extremum; an
    all-NaN group reports the canonical quiet NaN with `present` true.

    Re-proven and not inherited, because the composition MOVED the extremum
    seed from a serial prologue into the band. If the move dropped a seed, an
    all-NaN group's min would read 0.0 — a wrong answer that no timing would
    reveal. NaN in the FIRST row of a group is included on purpose: that
    position is where the #459 order-dependence lived.
    """
    var nan = _canonical()
    var keys = List[Float64]()
    var v0 = List[Float64]()
    var v1 = List[Float64]()
    # group 0: NaN FIRST, then ordered values
    keys.append(0.0)
    v0.append(nan)
    v1.append(nan)
    keys.append(0.0)
    v0.append(3.0)
    v1.append(-2.0)
    keys.append(0.0)
    v0.append(-1.0)
    v1.append(9.0)
    # group 1: every value NaN
    for _ in range(5):
        keys.append(1.0)
        v0.append(nan)
        v1.append(nan)
    # group 2: NaN LAST
    keys.append(2.0)
    v0.append(7.0)
    v1.append(7.0)
    keys.append(2.0)
    v0.append(nan)
    v1.append(nan)
    # group 3: ordered only, so a live extremum must survive next to the others
    keys.append(3.0)
    v0.append(-1e308)
    v1.append(1e308)
    keys.append(3.0)
    v0.append(5e-324)
    v1.append(-5e-324)
    var vals = List[List[Float64]]()
    vals.append(v0.copy())
    vals.append(v1.copy())
    var batch = _one_key_batch(keys^, vals^)

    var ops = List[Int]()
    ops.append(AGG_MAX)
    ops.append(AGG_MIN)
    var vc = _value_cols(2)
    var wcounts = List[Int]()
    wcounts.append(1)
    wcounts.append(2)
    wcounts.append(4)
    wcounts.append(9)
    for wi in range(len(wcounts)):
        var w = wcounts[wi]
        var par = group_by_composed_dense_parallel(batch, 0, 4, vc, ops, w, True)
        var ser = group_by_composed_dense_parallel(batch, 0, 4, vc, ops, w, False)
        var coded = group_by_coded_parallel(batch, 0, 4, vc, ops, w)
        var tag = "w" + String(w)
        t.ok("block2." + tag + ".ok", par.ok() and ser.ok() and coded.ok())
        if not (par.ok() and ser.ok() and coded.ok()):
            continue
        t.ok("block2." + tag + ".par_eq_ser", _diff_cells(par.result, ser.result) == 0)
        t.ok(
            "block2." + tag + ".eq_shipped",
            _diff_cells(coded.result, par.result) == 0,
        )
        ref r = par.result
        # group 0 (key 0.0) is first in first-appearance order.
        t.ok("block2." + tag + ".g0.max_is_3", _bits(r.value_at(0, 0)) == _bits(3.0))
        t.ok("block2." + tag + ".g0.min_is_-2", _bits(r.value_at(0, 1)) == _bits(-2.0))
        t.ok("block2." + tag + ".g0.count_3", r.count_at(0, 0) == 3.0)
        # group 1: every value NaN -> present, count 5, both extrema canonical NaN.
        t.ok("block2." + tag + ".g1.present_max", r.present_at(1, 0))
        t.ok("block2." + tag + ".g1.present_min", r.present_at(1, 1))
        t.ok(
            "block2." + tag + ".g1.max_canonical_nan",
            _bits(r.value_at(1, 0)) == CANONICAL_NAN_BITS,
        )
        t.ok(
            "block2." + tag + ".g1.min_canonical_nan",
            _bits(r.value_at(1, 1)) == CANONICAL_NAN_BITS,
        )
        t.ok("block2." + tag + ".g1.count_5", r.count_at(1, 0) == 5.0)
        # group 2: NaN last, live extremum survives and NaN still counts.
        t.ok("block2." + tag + ".g2.max_is_7", _bits(r.value_at(2, 0)) == _bits(7.0))
        t.ok("block2." + tag + ".g2.count_2", r.count_at(2, 0) == 2.0)
        # group 3: extreme magnitudes, no NaN.
        t.ok(
            "block2." + tag + ".g3.max_is_denormal",
            _bits(r.value_at(3, 0)) == _bits(5e-324),
        )
        # min is over the SECOND value column, whose group-3 values are
        # 1e308 and -5e-324 — so -5e-324, not -1e308. (My first expectation
        # here read the wrong column; the engines agreed with each other and
        # only the hand-computed answer was wrong, which is the argument for
        # having both the cross-engine check and the read-out.)
        t.ok(
            "block2." + tag + ".g3.min_is_-5e-324",
            _bits(r.value_at(3, 1)) == _bits(-5e-324),
        )


fn block2b_signed_zero_and_inf(mut t: Tally):
    """+0.0 against -0.0, and +/-inf, through the composed merge.

    A sum whose every summand is -0.0 must stay -0.0: folding from a 0.0 seed
    would silently make it +0.0, which is the `merge_from` copy-on-empty branch
    doing real work. A +0.0/-0.0 tie under min/max must keep FIRST appearance.
    """
    var inf = Float64(1.0) / Float64(0.0)
    var keys = List[Float64]()
    var v0 = List[Float64]()
    # group 0: -0.0 only
    for _ in range(3):
        keys.append(0.0)
        v0.append(-0.0)
    # group 1: +0.0 then -0.0
    keys.append(1.0)
    v0.append(0.0)
    keys.append(1.0)
    v0.append(-0.0)
    # group 2: -0.0 then +0.0
    keys.append(2.0)
    v0.append(-0.0)
    keys.append(2.0)
    v0.append(0.0)
    # group 3: +inf and -inf
    keys.append(3.0)
    v0.append(inf)
    keys.append(3.0)
    v0.append(-inf)
    var vals = List[List[Float64]]()
    vals.append(v0.copy())
    var batch = _one_key_batch(keys^, vals^)
    var vc = _value_cols(1)
    var opsets = List[Int]()
    opsets.append(AGG_SUM)
    opsets.append(AGG_MIN)
    opsets.append(AGG_MAX)
    for oi in range(len(opsets)):
        var ops = List[Int]()
        ops.append(opsets[oi])
        for w in range(1, 6):
            var par = group_by_composed_dense_parallel(batch, 0, 4, vc, ops, w, True)
            var ser = group_by_composed_dense_parallel(batch, 0, 4, vc, ops, w, False)
            var coded = group_by_coded_parallel(batch, 0, 4, vc, ops, w)
            var tag = "op" + String(opsets[oi]) + ".w" + String(w)
            t.ok("block2b." + tag + ".ok", par.ok() and ser.ok() and coded.ok())
            if not (par.ok() and ser.ok() and coded.ok()):
                continue
            t.ok(
                "block2b." + tag + ".par_eq_ser",
                _diff_cells(par.result, ser.result) == 0,
            )
            t.ok(
                "block2b." + tag + ".eq_shipped",
                _diff_cells(coded.result, par.result) == 0,
            )
            if opsets[oi] == AGG_SUM:
                # A sum of nothing but -0.0 is +0.0, in BOTH engines, because
                # the frozen `group_sum_update` is `current + new` from a 0.0
                # seed and `0.0 + -0.0` is `+0.0`. Pinned as the fact it is
                # rather than as the -0.0 a reader might expect: what the
                # composed route owes is the SHIPPED answer, and the shipped
                # answer here is +0.0. `merge_from`'s copy-on-empty branch is
                # still load-bearing — it is what stops an empty band from
                # being folded in as a zero — but it cannot manufacture a -0.0
                # that no band total ever held.
                t.ok(
                    "block2b." + tag + ".neg_zero_sum_is_plus_zero_like_shipped",
                    _bits(par.result.value_at(0, 0)) == _bits(0.0)
                    and _bits(par.result.value_at(0, 0))
                    == _bits(coded.result.value_at(0, 0)),
                )
            if opsets[oi] == AGG_MIN:
                # The extremum DOES carry the sign: min over {-0.0} is -0.0,
                # which is the distinction `==` cannot see and the reason every
                # comparison in this file is on bits.
                t.ok(
                    "block2b." + tag + ".min_of_neg_zero_is_neg_zero",
                    _bits(par.result.value_at(0, 0)) == _bits(-0.0),
                )


# ══ block 3 ══ nulls, both layouts ════════════════════════════════════════════
fn block3_nulls(mut t: Tally):
    """Null VALUES in one column and not another (the divergent-count layout),
    a group whose every value is null, and null KEYS (excluded and tallied)."""
    var n = 600
    var K = 11
    var seed: UInt64 = 0xA11_1234
    var keys = List[Float64](capacity=n)
    var kvalid = List[Bool](capacity=n)
    var c0 = List[Float64](capacity=n)
    var c0valid = List[Bool](capacity=n)
    var c1 = List[Float64](capacity=n)
    for i in range(n):
        keys.append(Float64(i % K))
        # every 47th row has a null KEY
        kvalid.append(i % 47 != 0)
        c0.append(_rand01(seed) * 100.0)
        # group 3 has EVERY value null in column 0: count 0, group still present
        c0valid.append(not (i % K == 3) and i % 5 != 0)
        c1.append(_rand01(seed) * 1e9)
    var names = List[String]()
    names.append("k")
    names.append("v0")
    names.append("v1")
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(keys.copy(), kvalid.copy()))
    cols.append(float64_with_nulls(c0.copy(), c0valid.copy()))
    cols.append(float64_from_list(c1.copy()))
    var batch = RecordBatch(schema_of(names^), cols^, n)

    var vc = _value_cols(2)
    var opsets = List[List[Int]]()
    var a = List[Int]()
    a.append(AGG_SUM)
    a.append(AGG_AVG)
    opsets.append(a^)
    var b = List[Int]()
    b.append(AGG_MIN)
    b.append(AGG_MAX)
    opsets.append(b^)
    var c = List[Int]()
    c.append(AGG_COUNT)
    c.append(AGG_SUM)
    opsets.append(c^)
    for s in range(len(opsets)):
        for w in range(1, 7):
            var par = group_by_composed_dense_parallel(
                batch, 0, K, vc, opsets[s], w, True
            )
            var ser = group_by_composed_dense_parallel(
                batch, 0, K, vc, opsets[s], w, False
            )
            var coded = group_by_coded_parallel(batch, 0, K, vc, opsets[s], w)
            var tag = "s" + String(s) + ".w" + String(w)
            t.ok("block3." + tag + ".ok", par.ok() and ser.ok() and coded.ok())
            if not (par.ok() and ser.ok() and coded.ok()):
                continue
            t.ok(
                "block3." + tag + ".par_eq_ser",
                _diff_cells(par.result, ser.result) == 0,
            )
            t.ok(
                "block3." + tag + ".eq_shipped",
                _diff_cells(coded.result, par.result) == 0,
            )
            t.ok(
                "block3." + tag + ".null_keys_tallied",
                par.result.null_key_rows == coded.result.null_key_rows
                and par.result.null_key_rows > 0,
            )


# ══ block 4 ══ the worker cap ════════════════════════════════════════════════
fn block4_worker_cap(mut t: Tally):
    """`compose_dense_workers` is the third composition finding, as arithmetic.

    Checked against `dense_state_bytes` directly rather than against remembered
    numbers: whatever it returns must FIT, and one more doubling must NOT — the
    two halves of "largest admissible".
    """
    var cards = List[Int]()
    cards.append(101)
    cards.append(4096)
    cards.append(100001)
    cards.append(1 << 20)
    for ci in range(len(cards)):
        var K = cards[ci]
        for n_aggs in range(1, 5):
            var w = compose_dense_workers(K, n_aggs, True, 32)
            var tag = "K" + String(K) + ".a" + String(n_aggs)
            if w == 0:
                t.ok(
                    "block4." + tag + ".zero_means_even_one_worker_overflows",
                    dense_state_bytes(K, n_aggs, 1, True) > DENSE_MAX_STATE_BYTES,
                )
                continue
            t.ok("block4." + tag + ".at_most_requested", w <= 32 and w >= 1)
            t.ok(
                "block4." + tag + ".fits",
                dense_state_bytes(K, n_aggs, w, True) <= DENSE_MAX_STATE_BYTES,
            )
            if w < 32:
                t.ok(
                    "block4." + tag + ".doubling_does_not_fit",
                    dense_state_bytes(K, n_aggs, w * 2, True)
                    > DENSE_MAX_STATE_BYTES,
                )
    # The specific finding, named: 1e5 codes are REFUSED at 32 bands and
    # ADMITTED at 16, which is why the composed router caps and why an
    # uncapped router would fall back on exactly q3/q5/q7.
    t.ok(
        "block4.1e5_refused_at_32",
        dense_state_bytes(100001, 2, 32, True) > DENSE_MAX_STATE_BYTES,
    )
    t.ok(
        "block4.1e5_admitted_at_16",
        dense_state_bytes(100001, 2, 16, True) <= DENSE_MAX_STATE_BYTES,
    )
    t.ok("block4.1e5_cap_is_16", compose_dense_workers(100001, 2, True, 32) == 16)
    t.ok("block4.1e5_3aggs_cap_is_16", compose_dense_workers(100001, 3, True, 32) == 16)
    t.ok("block4.small_uncapped", compose_dense_workers(101, 1, True, 32) == 32)
    t.ok("block4.zero_cardinality", compose_dense_workers(0, 1, True, 16) == 0)
    t.ok("block4.zero_aggs", compose_dense_workers(101, 0, True, 16) == 0)
    # Monotone in the request: asking for fewer can never admit more.
    var prev = 0
    for req in range(1, 33):
        var got = compose_dense_workers(100001, 3, True, req)
        t.ok("block4.monotone." + String(req), got >= prev or got == 0)
        if got > 0:
            prev = got
    # The fold estimate saturates instead of wrapping.
    t.ok("block4.folds_small", compose_merge_folds(100, 1, 16) == 1600)
    t.ok(
        "block4.folds_below_line",
        compose_merge_folds(100, 1, 16) < COMPOSE_PARALLEL_MERGE_MIN_FOLDS,
    )
    t.ok(
        "block4.folds_above_line",
        compose_merge_folds(100000, 2, 16) >= COMPOSE_PARALLEL_MERGE_MIN_FOLDS,
    )
    t.ok(
        "block4.folds_saturate",
        compose_merge_folds(1 << 40, 1 << 20, 1 << 20) > 0,
    )
    t.ok("block4.folds_zero", compose_merge_folds(0, 3, 16) == 0)


# ══ block 5 ══ the exact domain scan agrees with the guard ═══════════════════
fn block5_exact_domain(mut t: Tally):
    """`compose_exact_domain` and `_dense_code` must agree on "is a code".

    Not tested through the guard directly — the guard is private to
    `coded_dense` — but through the OBSERVABLE consequence, which is stronger:
    whenever the domain scan says dense, the composed dense engine at that bound
    must ANSWER (never `GROUP_CODED_KEY_NOT_A_CODE`), and whenever it says not
    dense, the engine at any bound must refuse. A disagreement either way is a
    route that lies.
    """
    var inf = Float64(1.0) / Float64(0.0)
    var nan = _canonical()
    var bad_values = List[Float64]()
    var bad_labels = List[String]()
    bad_values.append(-1.0)
    bad_labels.append("negative")
    bad_values.append(-0.5)
    bad_labels.append("negative_fraction")
    bad_values.append(2.5)
    bad_labels.append("fraction")
    bad_values.append(nan)
    bad_labels.append("nan")
    bad_values.append(inf)
    bad_labels.append("pos_inf")
    bad_values.append(-inf)
    bad_labels.append("neg_inf")
    bad_values.append(Float64(DENSE_MAX_CARDINALITY))
    bad_labels.append("at_ceiling")
    bad_values.append(1e300)
    bad_labels.append("huge")
    bad_values.append(-0.0)
    bad_labels.append("negative_zero_IS_a_code")

    for bi in range(len(bad_values)):
        var keys = List[Float64]()
        var v0 = List[Float64]()
        for i in range(200):
            keys.append(Float64(i % 7))
            v0.append(Float64(i))
        keys[137] = bad_values[bi]
        var vals = List[List[Float64]]()
        vals.append(v0.copy())
        var batch = _one_key_batch(keys^, vals^)
        var dom = compose_exact_domain(batch, 0, 4)
        var tag = bad_labels[bi]
        # -0.0 IS a code (0), so it is the one entry that must be ACCEPTED — a
        # test set of only rejections cannot tell a working guard from one that
        # rejects everything.
        var want_dense = bad_labels[bi] == "negative_zero_IS_a_code"
        t.ok("block5." + tag + ".domain_dense_" + String(want_dense),
             dom.dense == want_dense)
        var vc = _value_cols(1)
        var ops = List[Int]()
        ops.append(AGG_SUM)
        if want_dense:
            t.ok("block5." + tag + ".bound_is_7", dom.bound == 7)
            var eng = group_by_composed_dense_parallel(
                batch, 0, dom.bound, vc, ops, 4, True
            )
            t.ok("block5." + tag + ".engine_answers", eng.ok())
        else:
            # Whatever bound a caller picks, an unguarded write here is an
            # UNCATCHABLE abort. Refusal by STATUS is the contract.
            var eng = group_by_composed_dense_parallel(batch, 0, 7, vc, ops, 4, True)
            t.ok(
                "block5." + tag + ".engine_refuses",
                eng.status == GROUP_CODED_KEY_NOT_A_CODE,
            )
            # And the composed entry point still answers, via the shipped
            # engine, bit for bit.
            var composed = group_by_composed_parallel(batch, _ints(1), vc, ops, 4)
            var shipped = group_by_many_parallel(batch, _ints(1), vc, ops, 4)
            t.ok(
                "block5." + tag + ".fallback_is_shipped_bitwise",
                _diff_cells(shipped, composed) == 0,
            )

    # A clean column: the exact bound is max+1, and every worker count agrees
    # (the scan is parallel, so a band-boundary bug would show as a wrong max).
    var keys2 = List[Float64]()
    var v2 = List[Float64]()
    for i in range(5000):
        keys2.append(Float64((i * 7919) % 4099))
        v2.append(Float64(i))
    var vals2 = List[List[Float64]]()
    vals2.append(v2.copy())
    var batch2 = _one_key_batch(keys2^, vals2^)
    for w in range(1, 12):
        var d = compose_exact_domain(batch2, 0, w)
        t.ok("block5.clean.w" + String(w) + ".dense", d.dense)
        t.ok("block5.clean.w" + String(w) + ".bound_4099", d.bound == 4099)
    # A NULL key is not a code and is not a rejection either — it is skipped.
    var keys3 = List[Float64]()
    var kv3 = List[Bool]()
    var v3 = List[Float64]()
    for i in range(300):
        keys3.append(Float64(i % 5) if i % 13 != 0 else -7.0)
        kv3.append(i % 13 != 0)
        v3.append(Float64(i))
    var names3 = List[String]()
    names3.append("k")
    names3.append("v0")
    var cols3 = List[Float64Array]()
    cols3.append(float64_with_nulls(keys3.copy(), kv3.copy()))
    cols3.append(float64_from_list(v3.copy()))
    var batch3 = RecordBatch(schema_of(names3^), cols3^, 300)
    for w in range(1, 6):
        var d3 = compose_exact_domain(batch3, 0, w)
        t.ok(
            "block5.null_keys_skipped.w" + String(w),
            d3.dense and d3.bound == 5,
        )


# ══ block 6 ══ routing, and refusal totality past the probe window ═══════════
fn block6_routing(mut t: Tally):
    """`compose_plan` picks the route the shape deserves, and the entry point is
    TOTAL — every refusal falls through to the shipped engine.

    The last case is the load-bearing one: a batch LARGER than the probe window
    with a key hidden past it, so the probe-derived bound genuinely lies. The
    dense scan must refuse by flag and the composed answer must still be the
    shipped answer, bit for bit.
    """
    var seed: UInt64 = 0xB0_1234
    # width 1, small domain -> DENSE
    var keys = List[Float64]()
    var v0 = List[Float64]()
    for i in range(3000):
        keys.append(Float64(i % 53))
        v0.append(_rand01(seed))
    var vals = List[List[Float64]]()
    vals.append(v0.copy())
    var b1 = _one_key_batch(keys^, vals^)
    var vc1 = _value_cols(1)
    var sum1 = List[Int]()
    sum1.append(AGG_SUM)
    var p1 = compose_plan(b1, _ints(1), vc1, sum1, 8)
    t.ok("block6.width1_small_is_dense", p1.route == COMPOSE_ROUTE_DENSE)
    t.ok("block6.width1_bound_is_53", p1.cardinality == 53)
    t.ok("block6.width1_no_exact_scan", not p1.exact_domain)
    t.ok("block6.width1_serial_merge", not p1.parallel_merge)
    t.ok("block6.plan_status_ok", p1.status == GROUP_CODED_OK)
    t.ok("block6.route_name", compose_route_name(p1.route) == "dense")

    # VAR / STD cannot be packed -> must NOT take the dense route.
    var varops = List[Int]()
    varops.append(AGG_VAR)
    var pv = compose_plan(b1, _ints(1), vc1, varops, 8)
    t.ok("block6.var_not_dense", pv.route != COMPOSE_ROUTE_DENSE)
    var stdops = List[Int]()
    stdops.append(AGG_STD)
    var ps = compose_plan(b1, _ints(1), vc1, stdops, 8)
    t.ok("block6.std_not_dense", ps.route != COMPOSE_ROUTE_DENSE)
    # ...and the answer is still right, from whichever engine took it.
    var cv = group_by_composed_parallel(b1, _ints(1), vc1, varops, 8)
    var sv = group_by_many_parallel(b1, _ints(1), vc1, varops, 8)
    t.ok("block6.var_answer_is_shipped", _diff_cells(sv, cv) == 0)

    # width 2 -> PACKED
    var k1 = List[Float64]()
    var k2 = List[Float64]()
    var w0 = List[Float64]()
    for i in range(4000):
        k1.append(Float64(i % 40))
        k2.append(Float64((i // 40) % 25))
        w0.append(_rand01(seed))
    var names2 = List[String]()
    names2.append("k1")
    names2.append("k2")
    names2.append("v0")
    var cols2 = List[Float64Array]()
    cols2.append(float64_from_list(k1^))
    cols2.append(float64_from_list(k2^))
    cols2.append(float64_from_list(w0^))
    var b2 = RecordBatch(schema_of(names2^), cols2^, 4000)
    var vc2 = List[Int]()
    vc2.append(2)
    var p2 = compose_plan(b2, _ints(2), vc2, sum1, 8)
    t.ok("block6.width2_is_packed", p2.route == COMPOSE_ROUTE_PACKED)
    t.ok("block6.width2_slots_1000", p2.domain.slots == 1000)
    var c2 = group_by_composed_parallel(b2, _ints(2), vc2, sum1, 8)
    var s2 = group_by_many_parallel(b2, _ints(2), vc2, sum1, 8)
    t.ok("block6.width2_answer_matches_shipped", _diff_cells(s2, c2) == 0)

    # width 0 -> SHIPPED, and still correct.
    var p0 = compose_plan(b1, List[Int](), vc1, sum1, 8)
    t.ok("block6.width0_is_shipped", p0.route == COMPOSE_ROUTE_SHIPPED)
    var c0 = group_by_composed_parallel(b1, List[Int](), vc1, sum1, 8)
    var s0 = group_by_many_parallel(b1, List[Int](), vc1, sum1, 8)
    t.ok("block6.width0_answer_matches_shipped", _diff_cells(s0, c0) == 0)

    # Malformed (columns, opcodes) -> SHIPPED, and the shipped refusal shape.
    var two_ops = List[Int]()
    two_ops.append(AGG_SUM)
    two_ops.append(AGG_SUM)
    var pm = compose_plan(b1, _ints(1), vc1, two_ops, 8)
    t.ok("block6.malformed_is_shipped", pm.route == COMPOSE_ROUTE_SHIPPED)
    t.ok("block6.malformed_status", pm.status == GROUP_CODED_BAD_REQUEST)
    var cm = group_by_composed_parallel(b1, _ints(1), vc1, two_ops, 8)
    var sm = group_by_many_parallel(b1, _ints(1), vc1, two_ops, 8)
    t.ok("block6.malformed_answer_matches_shipped", _diff_cells(sm, cm) == 0)

    # ── the probe lies: a key hidden PAST the probe window ──────────────────
    # 70000 rows > COMPOSE_PROBE_ROWS, span in the window is 9 (< the exact-scan
    # line, so the bound comes from the window), and row 69999 carries 500.
    var big_k = List[Float64]()
    var big_v = List[Float64]()
    for i in range(70000):
        big_k.append(Float64(i % 9))
        big_v.append(_rand01(seed) * 1000.0)
    big_k[69999] = 500.0
    var bigvals = List[List[Float64]]()
    bigvals.append(big_v.copy())
    var b3 = _one_key_batch(big_k^, bigvals^)
    var p3 = compose_plan(b3, _ints(1), vc1, sum1, 8)
    t.ok("block6.tail_key.plan_is_dense", p3.route == COMPOSE_ROUTE_DENSE)
    t.ok("block6.tail_key.bound_from_window", p3.cardinality == 9)
    t.ok("block6.tail_key.no_exact_scan", not p3.exact_domain)
    var eng3 = group_by_composed_dense_parallel(
        b3, 0, p3.cardinality, vc1, sum1, p3.workers, p3.parallel_merge
    )
    t.ok(
        "block6.tail_key.engine_refuses",
        eng3.status == GROUP_CODED_KEY_NOT_A_CODE,
    )
    var c3 = group_by_composed_parallel(b3, _ints(1), vc1, sum1, 8)
    var s3 = group_by_many_parallel(b3, _ints(1), vc1, sum1, 8)
    t.ok("block6.tail_key.fallback_is_shipped", _diff_cells(s3, c3) == 0)
    t.ok("block6.tail_key.group_500_present", c3.n_groups() == 10)

    # Same batch, but the span in the window is WIDE enough to buy the exact
    # scan, so the tail key is FOUND and the dense route succeeds instead of
    # refusing — which is the whole point of COMPOSE_EXACT_DOMAIN_MIN_SPAN.
    var wide_k = List[Float64]()
    var wide_v = List[Float64]()
    for i in range(70000):
        wide_k.append(Float64((i * 7919) % COMPOSE_EXACT_DOMAIN_MIN_SPAN))
        wide_v.append(_rand01(seed) * 1000.0)
    wide_k[69999] = Float64(COMPOSE_EXACT_DOMAIN_MIN_SPAN + 991)
    var widevals = List[List[Float64]]()
    widevals.append(wide_v.copy())
    var b4 = _one_key_batch(wide_k^, widevals^)
    var p4 = compose_plan(b4, _ints(1), vc1, sum1, 8)
    t.ok("block6.wide.plan_is_dense", p4.route == COMPOSE_ROUTE_DENSE)
    t.ok("block6.wide.exact_scan_ran", p4.exact_domain)
    t.ok(
        "block6.wide.bound_includes_tail_key",
        p4.cardinality == COMPOSE_EXACT_DOMAIN_MIN_SPAN + 992,
    )
    var eng4 = group_by_composed_dense_parallel(
        b4, 0, p4.cardinality, vc1, sum1, p4.workers, p4.parallel_merge
    )
    t.ok("block6.wide.engine_answers", eng4.ok())
    var c4 = group_by_composed_parallel(b4, _ints(1), vc1, sum1, 8)
    var banded4 = group_by_many_banded(b4, _ints(1), vc1, sum1, p4.workers)
    t.ok("block6.wide.eq_shipped_banded", _diff_cells(banded4, c4) == 0)

    # A non-integral key hidden past the window on a WIDE span: the exact scan
    # sees it, declines dense, and another engine answers.
    var bad_k = List[Float64]()
    var bad_v = List[Float64]()
    for i in range(70000):
        bad_k.append(Float64((i * 7919) % COMPOSE_EXACT_DOMAIN_MIN_SPAN))
        bad_v.append(_rand01(seed) * 1000.0)
    bad_k[69999] = 12.5
    var badvals = List[List[Float64]]()
    badvals.append(bad_v.copy())
    var b5 = _one_key_batch(bad_k^, badvals^)
    var p5 = compose_plan(b5, _ints(1), vc1, sum1, 8)
    t.ok("block6.wide_bad.not_dense", p5.route != COMPOSE_ROUTE_DENSE)
    var c5 = group_by_composed_parallel(b5, _ints(1), vc1, sum1, 8)
    var s5 = group_by_many_parallel(b5, _ints(1), vc1, sum1, 8)
    t.ok("block6.wide_bad.answer_matches_shipped", _diff_cells(s5, c5) == 0)


# ══ block 7 ══ the status block has no duplicate ═════════════════════════════
fn block7_status_registry(mut t: Tally):
    """330..339 must map to DISTINCT names.

    This is the block that exists because composition found a real collision:
    `coded_dense` and `packedkey` both numbered a different refusal 334, and
    neither module's own status-name function could see it. A caller switching
    on the status would have read one number as two meanings.
    """
    var names = List[String]()
    for s in range(330, 340):
        names.append(compose_status_name(s))
    for i in range(len(names)):
        if names[i] == "unassigned":
            continue
        for j in range(i + 1, len(names)):
            t.ok(
                "block7.distinct." + String(330 + i) + "_vs_" + String(330 + j),
                names[i] != names[j],
            )
    # Every constant the query plane exports must be IN the block and named.
    t.ok("block7.ok_named", compose_status_name(GROUP_CODED_OK) == "ok")
    t.ok(
        "block7.dense_opcode_named",
        compose_status_name(GROUP_DENSE_OPCODE_UNSUPPORTED)
        == "dense_opcode_unsupported",
    )
    t.ok(
        "block7.dense_state_named",
        compose_status_name(GROUP_DENSE_STATE_TOO_LARGE) == "dense_state_too_large",
    )
    t.ok(
        "block7.packed_named",
        compose_status_name(GROUP_PACKED_DOMAIN_TOO_LARGE)
        == "packed_domain_too_large",
    )
    t.ok(
        "block7.packed_is_not_334",
        GROUP_PACKED_DOMAIN_TOO_LARGE != GROUP_DENSE_OPCODE_UNSUPPORTED,
    )
    t.ok("block7.in_block", GROUP_PACKED_DOMAIN_TOO_LARGE < 340)
    t.ok("block7.unassigned_tail", compose_status_name(339) == "unassigned")
    t.ok("block7.outside_block", compose_status_name(400) == "unassigned")


# ══ block 8 ══ the composed engine's refusals are statuses ═══════════════════
fn block8_engine_refusals(mut t: Tally):
    """The engine's own refusal table, so a refusal cannot be mistaken for an
    empty answer — and so the byte budget is a real gate rather than a comment."""
    var keys = List[Float64]()
    var v0 = List[Float64]()
    for i in range(500):
        keys.append(Float64(i % 5))
        v0.append(Float64(i))
    var vals = List[List[Float64]]()
    vals.append(v0.copy())
    var batch = _one_key_batch(keys^, vals^)
    var vc = _value_cols(1)
    var sum1 = List[Int]()
    sum1.append(AGG_SUM)

    var r0 = group_by_composed_dense_parallel(batch, 0, 0, vc, sum1, 4, True)
    t.ok("block8.cardinality_0", r0.status == GROUP_CODED_CARDINALITY_INVALID)
    var rn = group_by_composed_dense_parallel(batch, 0, -3, vc, sum1, 4, True)
    t.ok("block8.cardinality_negative", rn.status == GROUP_CODED_CARDINALITY_INVALID)
    var rb = group_by_composed_dense_parallel(
        batch, 0, DENSE_MAX_CARDINALITY + 1, vc, sum1, 4, True
    )
    t.ok("block8.cardinality_past_ceiling", rb.status == GROUP_CODED_CARDINALITY_INVALID)
    var varops = List[Int]()
    varops.append(AGG_VAR)
    var rv = group_by_composed_dense_parallel(batch, 0, 5, vc, varops, 4, True)
    t.ok("block8.var_unsupported", rv.status == GROUP_DENSE_OPCODE_UNSUPPORTED)
    var stdops = List[Int]()
    stdops.append(AGG_STD)
    var rs = group_by_composed_dense_parallel(batch, 0, 5, vc, stdops, 4, True)
    t.ok("block8.std_unsupported", rs.status == GROUP_DENSE_OPCODE_UNSUPPORTED)
    var two = List[Int]()
    two.append(AGG_SUM)
    two.append(AGG_SUM)
    var rm = group_by_composed_dense_parallel(batch, 0, 5, vc, two, 4, True)
    t.ok("block8.bad_request", rm.status == GROUP_CODED_BAD_REQUEST)
    # A cardinality inside DENSE_MAX_CARDINALITY whose STATE is not: the byte
    # budget, exercised rather than described.
    var rt = group_by_composed_dense_parallel(
        batch, 0, 1 << 20, vc, sum1, 4, True
    )
    t.ok("block8.state_too_large", rt.status == GROUP_DENSE_STATE_TOO_LARGE)
    # A one-row batch and a worker count past the row count both answer.
    var kk = List[Float64]()
    kk.append(3.0)
    var vv = List[Float64]()
    vv.append(-0.0)
    var one = List[List[Float64]]()
    one.append(vv.copy())
    var b1 = _one_key_batch(kk^, one^)
    var r1 = group_by_composed_dense_parallel(b1, 0, 4, vc, sum1, 16, True)
    t.ok("block8.one_row_ok", r1.ok() and r1.result.n_groups() == 1)
    # One row whose value is -0.0, summed: +0.0, and the SHIPPED engine agrees.
    # The claim is agreement, not a remembered sign — see block2b.
    var s1 = group_by_coded_parallel(b1, 0, 4, vc, sum1, 16)
    t.ok(
        "block8.one_row_matches_shipped_bitwise",
        s1.ok() and _diff_cells(s1.result, r1.result) == 0,
    )
    var minops = List[Int]()
    minops.append(AGG_MIN)
    var r1m = group_by_composed_dense_parallel(b1, 0, 4, vc, minops, 16, True)
    t.ok(
        "block8.one_row_min_keeps_negative_zero",
        r1m.ok() and _bits(r1m.result.value_at(0, 0)) == _bits(-0.0),
    )


fn main():
    print("test_query_composed")
    var t = Tally()
    block1_merge_decomposition(t)
    block2_nan_policy(t)
    block2b_signed_zero_and_inf(t)
    block3_nulls(t)
    block4_worker_cap(t)
    block5_exact_domain(t)
    block6_routing(t)
    block7_status_registry(t)
    block8_engine_refusals(t)
    print("")
    print("checks=" + String(t.checks) + " failures=" + String(t.failures))
    if t.failures != 0:
        print("FAILED")
    else:
        print("ALL PASS")
