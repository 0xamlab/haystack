"""test_query_coded_dense.mojo — `query.coded_dense` against the engine it
replaces, bit for bit.

Hand-written. The claim this suite exists to make unfalsifiable: at equal
worker count `group_by_coded_dense_parallel` returns EXACTLY what
`group_by_coded_parallel` returns — not "within tolerance", exactly, down to
the bit pattern of every Float64 — on every supported opcode, every layout,
and every edge the packed encoding could plausibly move.

Every comparison here is BITWISE (`_bits`), not `==`. Two reasons, both of
which a tolerance comparison would hide:

  * a mean folded by a different association is off by an ulp, and an ulp is
    exactly what a "faster wrong answer" looks like when the fast route
    quietly changed the fold order;
  * NaN != NaN, so `==` cannot check the all-NaN extremum case at all, which
    is the case the #459 defect lived in twice.

Blocks, in order:

  1. IDENTITY, per opcode, per worker count (1/2/3/5/8/16 — 1 is the serial
     path, 3 and 5 are odd so the band arithmetic cannot be even-only, 16 is
     more workers than some of the batches have rows). SUM / AVG / MIN / MAX /
     COUNT alone, uniform 3-aggregate, and MIXED, on random data.
  2. THE NaN POLICY, which is a policy and not a detail: NaN values scattered,
     a group whose values are ALL NaN (must report the canonical quiet NaN with
     `present` true, from both engines, same bits), NaN in the FIRST row of a
     group (the order-dependence #459 introduced), and NaN under min AND max
     in the same call.
  3. NULLS, both layouts: null values in some value columns and not others
     (the divergent-count layout), a group whose every value is null (count 0,
     group still present), null KEYS (excluded and tallied), and ALL keys null.
  4. ADVERSARIAL VALUES: +0.0 against -0.0 (a tie must keep FIRST appearance,
     which is what makes the sum's `-0.0` case and the extremum's tie case
     observable), +/-inf, and values that make a Welford mean and a
     sum-then-divide mean differ.
  5. REFUSALS, and that a refusal is a STATUS and not an abort: a key past the
     cardinality, a negative key, a fractional key, a NaN key, cardinality 0 /
     negative / past `DENSE_MAX_CARDINALITY`, VAR and STD (routing signal), a
     malformed (columns, opcodes) pairing, and a state size past the byte
     budget. The out-of-range-key cases are the load-bearing ones: an
     unguarded dense write there is an UNCATCHABLE abort, so this block
     reaching its own end is the proof.
  6. `_dense_min_fold` / `_dense_max_fold` == `_dense_min_reference` /
     `_dense_max_reference` (which are spelled with the frozen
     `group_min_update` / `group_max_update` and an explicit `seen`) over the
     full cross product of an adversarial value set with itself.
  7. `dense_state_bytes` arithmetic and the `dense_route_status` table.

Data comes from a fixed-seed LCG in this file, so a failure reproduces.
"""
from std.memory import bitcast

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from columnar.hash_index import CANONICAL_NAN_BITS
from pandas_groupby import (
    group_count_update,
    group_max_update,
    group_mean_update,
    group_min_update,
    group_sum_update,
)
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
    ManyGroupedResult,
    group_by_coded_parallel,
)
from query.coded_dense import (
    DENSE_MAX_CARDINALITY,
    DENSE_MAX_STATE_BYTES,
    GROUP_DENSE_OPCODE_UNSUPPORTED,
    GROUP_DENSE_STATE_TOO_LARGE,
    _apply_dyn,
    _dense_max_fold,
    _dense_max_reference,
    _dense_min_fold,
    _dense_min_reference,
    dense_record_stride,
    dense_route_status,
    dense_state_bytes,
    dense_supports_opcode,
    group_by_coded_dense,
    group_by_coded_dense_parallel,
)

struct Tally(Copyable, Movable):
    """Check counter threaded through every block, so a block that silently
    ran ZERO comparisons is visible as a low count rather than as a pass."""

    var checks: Int
    var failures: Int
    var nan_exempt: Int
    """Cells where BOTH engines returned a NaN with DIFFERENT payloads.

    Counted, never ignored. The payload a poisoned `fadd` propagates is a
    compiler choice (see the `nan_payload` block), so it is not part of any
    engine's contract — but an exemption that fired where no NaN exists would
    be a mismatch wearing a NaN's clothes, so every block below asserts the
    exact number it is allowed to consume, and that number is 0 everywhere
    except the block that exists to exercise it."""

    def __init__(out self):
        self.checks = 0
        self.failures = 0
        self.nan_exempt = 0

    def ok(mut self, name: String, condition: Bool):
        self.checks += 1
        if not condition:
            self.failures += 1
            print("  FAIL " + name)


def _bits(x: Float64) -> UInt64:
    """The bit pattern, so NaN compares equal to NaN and -0.0 does not compare
    equal to +0.0 — the two distinctions a `==` identity check cannot make."""
    return bitcast[DType.uint64](x)


def _lcg(mut state: UInt64) -> UInt64:
    state = state * 6364136223846793005 + 1442695040888963407
    return state


def _rand01(mut state: UInt64) -> Float64:
    return Float64(Int(_lcg(state) >> 11)) / Float64(Int(UInt64(1) << 53))


def _same(mut t: Tally, name: String, a: ManyGroupedResult, b: ManyGroupedResult):
    """Every field of two results, bitwise. One helper so no call site can
    accidentally check fewer fields than another."""
    t.ok(name + ".n_groups", a.n_groups() == b.n_groups())
    t.ok(name + ".key_width", a.key_width == b.key_width)
    t.ok(name + ".n_aggs", a.n_aggs == b.n_aggs)
    t.ok(name + ".null_key_rows", a.null_key_rows == b.null_key_rows)
    t.ok(name + ".len_keys", len(a.key_tuples) == len(b.key_tuples))
    t.ok(name + ".len_values", len(a.values) == len(b.values))
    t.ok(name + ".len_present", len(a.present) == len(b.present))
    t.ok(name + ".len_counts", len(a.counts) == len(b.counts))
    if len(a.key_tuples) != len(b.key_tuples):
        return
    var key_bad = 0
    for i in range(len(a.key_tuples)):
        if _bits(a.key_tuples[i]) != _bits(b.key_tuples[i]):
            key_bad += 1
    t.ok(name + ".keys_bitwise_and_in_order", key_bad == 0)
    if len(a.values) != len(b.values):
        return
    var val_bad = 0
    var pres_bad = 0
    var cnt_bad = 0
    for i in range(len(a.values)):
        if _bits(a.values[i]) != _bits(b.values[i]):
            if a.values[i] != a.values[i] and b.values[i] != b.values[i]:
                # Both NaN, different payload. Recorded, not waved through.
                t.nan_exempt += 1
            else:
                val_bad += 1
        if a.present[i] != b.present[i]:
            pres_bad += 1
        if _bits(a.counts[i]) != _bits(b.counts[i]):
            cnt_bad += 1
    t.ok(name + ".values_bitwise", val_bad == 0)
    t.ok(name + ".present", pres_bad == 0)
    t.ok(name + ".counts_bitwise", cnt_bad == 0)


def _batch1(keys: List[Float64], v: List[Float64]) -> RecordBatch:
    var names = List[String]()
    names.append("k")
    names.append("v0")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(keys.copy()))
    cols.append(float64_from_list(v.copy()))
    return RecordBatch(schema_of(names^), cols^, len(keys))


def _batch3(
    key_col: Float64Array,
    a: Float64Array,
    b: Float64Array,
    c: Float64Array,
    n_rows: Int,
) -> RecordBatch:
    var names = List[String]()
    names.append("k")
    names.append("v0")
    names.append("v1")
    names.append("v2")
    var cols = List[Float64Array]()
    cols.append(key_col.copy())
    cols.append(a.copy())
    cols.append(b.copy())
    cols.append(c.copy())
    return RecordBatch(schema_of(names^), cols^, n_rows)


def _ints(a: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    return out^


def _ints3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _pad8(n: Int) -> Int:
    """The suite's own copy of the cache-line rounding, so `dense_state_bytes`
    is checked against arithmetic written here rather than against itself."""
    return ((n + 7) // 8) * 8


def _worker_counts() -> List[Int]:
    var w = List[Int]()
    w.append(1)
    w.append(2)
    w.append(3)
    w.append(5)
    w.append(8)
    w.append(16)
    return w^


def _compare_all_workers(
    mut t: Tally,
    label: String,
    batch: RecordBatch,
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
):
    """The whole point, in one call: same request, both engines, every worker
    count, bitwise. Also asserts both engines AGREE ON THE STATUS — a route
    that refused where the reference succeeded would otherwise pass a
    comparison of two empty results."""
    var ws = _worker_counts()
    for i in range(len(ws)):
        var w = ws[i]
        var ref_r = group_by_coded_parallel(
            batch, 0, cardinality, value_columns, opcodes, w
        )
        var dense = group_by_coded_dense_parallel(
            batch, 0, cardinality, value_columns, opcodes, w
        )
        var tag = label + "@w" + String(w)
        t.ok(tag + ".status", ref_r.status == dense.status)
        if ref_r.status != dense.status:
            continue
        t.ok(tag + ".status_ok", ref_r.status == GROUP_CODED_OK)
        _same(t, tag, ref_r.result, dense.result)


def block1_identity_random(mut t: Tally):
    print("block 1: identity vs group_by_coded_parallel, random data")
    var state = UInt64(0x2026_0801_C0DE)
    var n = 5000
    var K = 37
    var keys = List[Float64]()
    var v0 = List[Float64]()
    var v1 = List[Float64]()
    var v2 = List[Float64]()
    for _ in range(n):
        keys.append(Float64(Int(_lcg(state) % UInt64(K))))
        v0.append(_rand01(state) * 200.0 - 100.0)
        v1.append(_rand01(state) * 1e6)
        v2.append(_rand01(state) * 1e-6)
    var kc = float64_from_list(keys.copy())
    var batch = _batch3(
        kc,
        float64_from_list(v0^),
        float64_from_list(v1^),
        float64_from_list(v2^),
        n,
    )
    _compare_all_workers(t, "sum1", batch, K, _ints(1), _ints(AGG_SUM))
    _compare_all_workers(t, "avg1", batch, K, _ints(1), _ints(AGG_AVG))
    _compare_all_workers(t, "min1", batch, K, _ints(1), _ints(AGG_MIN))
    _compare_all_workers(t, "max1", batch, K, _ints(1), _ints(AGG_MAX))
    _compare_all_workers(t, "cnt1", batch, K, _ints(1), _ints(AGG_COUNT))
    _compare_all_workers(
        t,
        "avg3", batch, K, _ints3(1, 2, 3), _ints3(AGG_AVG, AGG_AVG, AGG_AVG)
    )
    _compare_all_workers(
        t,
        "sum3", batch, K, _ints3(1, 2, 3), _ints3(AGG_SUM, AGG_SUM, AGG_SUM)
    )
    _compare_all_workers(
        t,
        "mixed", batch, K, _ints3(1, 2, 3), _ints3(AGG_SUM, AGG_AVG, AGG_MIN)
    )
    _compare_all_workers(
        t,
        "minmax", batch, K, _ints3(1, 1, 2), _ints3(AGG_MIN, AGG_MAX, AGG_COUNT)
    )
    # A batch with FEWER rows than the widest worker count, and a single row.
    var tiny_k = List[Float64]()
    var tiny_v = List[Float64]()
    for i in range(5):
        tiny_k.append(Float64(i % 3))
        tiny_v.append(Float64(i) - 2.0)
    _compare_all_workers(t, "tiny_sum", _batch1(tiny_k, tiny_v), 3, _ints(1), _ints(AGG_SUM))
    var one_k = List[Float64]()
    one_k.append(2.0)
    var one_v = List[Float64]()
    one_v.append(-0.0)
    _compare_all_workers(t, "onerow_sum", _batch1(one_k, one_v), 3, _ints(1), _ints(AGG_SUM))
    _compare_all_workers(t, "onerow_min", _batch1(one_k, one_v), 3, _ints(1), _ints(AGG_MIN))


def block2_nan_policy(mut t: Tally):
    print("block 2: the NaN policy, ONE payload, strict bit identity")
    var nan = bitcast[DType.float64](CANONICAL_NAN_BITS)
    var keys = List[Float64]()
    var vals = List[Float64]()
    # group 0: NaN in the FIRST row, then live values  (the #459 shape: a
    # first-value-seeded extremum made the serial fold order-dependent)
    keys.append(0.0)
    vals.append(nan)
    keys.append(0.0)
    vals.append(3.0)
    keys.append(0.0)
    vals.append(-7.5)
    # group 1: live, NaN, live
    keys.append(1.0)
    vals.append(2.0)
    keys.append(1.0)
    vals.append(nan)
    keys.append(1.0)
    vals.append(9.0)
    # group 4: ALL NaN, and NOTHING below adds to it -> the all-NaN extremum
    keys.append(4.0)
    vals.append(nan)
    keys.append(4.0)
    vals.append(nan)
    # group 5: exactly one live value
    keys.append(5.0)
    vals.append(4.25)
    # pad groups 0..3 only, so group 4 stays all-NaN and NaNs land on band
    # boundaries at several worker counts
    for i in range(200):
        keys.append(Float64(i % 4))
        vals.append(nan if (i % 7 == 0) else (Float64(i) * 0.5 - 25.0))
    var batch = _batch1(keys, vals)
    var before = t.nan_exempt
    _compare_all_workers(t, "nan_min", batch, 6, _ints(1), _ints(AGG_MIN))
    _compare_all_workers(t, "nan_max", batch, 6, _ints(1), _ints(AGG_MAX))
    _compare_all_workers(t, "nan_sum", batch, 6, _ints(1), _ints(AGG_SUM))
    _compare_all_workers(t, "nan_avg", batch, 6, _ints(1), _ints(AGG_AVG))
    _compare_all_workers(t, "nan_cnt", batch, 6, _ints(1), _ints(AGG_COUNT))
    _compare_all_workers(
        t, "nan_minmax", batch, 6, _ints3(1, 1, 1), _ints3(AGG_MIN, AGG_MAX, AGG_SUM)
    )
    # ONE payload in play, so nothing may be exempted: this whole block is
    # strict bit identity, the all-NaN extremum included.
    t.ok("nan.no_exemptions_needed", t.nan_exempt == before)
    # The all-NaN group's extremum: canonical quiet NaN, present, count kept.
    var d = group_by_coded_dense_parallel(batch, 0, 6, _ints(1), _ints(AGG_MIN), 4)
    var r = group_by_coded_parallel(batch, 0, 6, _ints(1), _ints(AGG_MIN), 4)
    t.ok("nan.dense_ok", d.ok() and r.ok())
    var found = 0
    for g in range(d.result.n_groups()):
        if d.result.key_tuples[g] == 4.0:
            found += 1
            t.ok("nan.allnan_present", d.result.present[g])
            t.ok("nan.allnan_canonical", _bits(d.result.values[g]) == CANONICAL_NAN_BITS)
            t.ok("nan.allnan_count_2", d.result.counts[g] == 2.0)
            t.ok(
                "nan.allnan_matches_reference",
                _bits(d.result.values[g]) == _bits(r.result.values[g]),
            )
    t.ok("nan.allnan_group_exists_once", found == 1)


def block2b_nan_payload(mut t: Tally):
    print("block 2b: several NaN PAYLOADS in one group — where identity stops")
    # A fact about this machine, not about either engine: the payload an `fadd`
    # propagates when BOTH operands are NaN depends on operand order, and
    # operand order of a commutative `fadd` is the compiler's choice. Measured:
    # the shipped engine's 1e0-worker fold of [canonical, 0xDEADBEEF] returns
    # 0xDEADBEEF while a constant-folded `canonical + 0xDEADBEEF` returns
    # canonical. So the PAYLOAD of a poisoned sum is not a property any engine
    # here promises, and an identity claim must say so out loud instead of
    # quietly comparing it.
    #
    # What IS promised, and asserted below: the poisoned cell is a NaN in both
    # engines; and min/max — which `value_for` CANONICALIZES — stay strictly
    # bit-identical even here.
    var nan = bitcast[DType.float64](CANONICAL_NAN_BITS)
    var n1 = bitcast[DType.float64](UInt64(0x7FF8_0000_DEAD_BEEF))
    var n2 = bitcast[DType.float64](UInt64(0x7FF8_0000_0BAD_F00D))
    var keys = List[Float64]()
    var vals = List[Float64]()
    for i in range(256):
        keys.append(Float64(i % 3))
        var m = i % 4
        if m == 0:
            vals.append(nan)
        elif m == 1:
            vals.append(n1)
        elif m == 2:
            vals.append(n2)
        else:
            vals.append(Float64(i) - 100.0)
    var batch = _batch1(keys, vals)
    # min/max/count: strict, no exemption allowed.
    var before = t.nan_exempt
    _compare_all_workers(t, "payload_min", batch, 3, _ints(1), _ints(AGG_MIN))
    _compare_all_workers(t, "payload_max", batch, 3, _ints(1), _ints(AGG_MAX))
    _compare_all_workers(t, "payload_cnt", batch, 3, _ints(1), _ints(AGG_COUNT))
    t.ok("payload.extrema_are_strict", t.nan_exempt == before)
    # sum/avg through the SAME comparator every other block uses, so the
    # exemption path itself is exercised rather than described — and it must
    # actually fire, or the whole mechanism is vacuous.
    _compare_all_workers(t, "payload_sum", batch, 3, _ints(1), _ints(AGG_SUM))
    _compare_all_workers(t, "payload_avg", batch, 3, _ints(1), _ints(AGG_AVG))
    t.ok("payload.exemption_actually_fired", t.nan_exempt > before)
    # sum/avg: NaN-ness compared, payload not.
    var ws = _worker_counts()
    var all_nan = True
    var both_nan_cells = 0
    for i in range(len(ws)):
        var r = group_by_coded_parallel(batch, 0, 3, _ints(1), _ints(AGG_SUM), ws[i])
        var d = group_by_coded_dense_parallel(batch, 0, 3, _ints(1), _ints(AGG_SUM), ws[i])
        t.ok("payload.sum_status@w" + String(ws[i]), r.status == d.status and d.ok())
        t.ok("payload.sum_groups@w" + String(ws[i]), r.result.n_groups() == d.result.n_groups())
        for g in range(d.result.n_groups()):
            t.ok(
                "payload.sum_key@w" + String(ws[i]),
                _bits(r.result.key_tuples[g]) == _bits(d.result.key_tuples[g]),
            )
            t.ok(
                "payload.sum_count@w" + String(ws[i]),
                _bits(r.result.counts[g]) == _bits(d.result.counts[g]),
            )
            if not (r.result.values[g] != r.result.values[g]):
                all_nan = False
            if not (d.result.values[g] != d.result.values[g]):
                all_nan = False
            both_nan_cells += 1
    t.ok("payload.every_poisoned_sum_is_nan_in_both", all_nan)
    t.ok("payload.cells_examined", both_nan_cells >= 18)


def block3_nulls(mut t: Tally):
    print("block 3: nulls, both layouts")
    var n = 600
    var K = 11
    var keys = List[Float64]()
    var v0 = List[Float64]()
    var v1 = List[Float64]()
    var v2 = List[Float64]()
    var v0_valid = List[Bool]()
    var v1_valid = List[Bool]()
    var key_valid = List[Bool]()
    for i in range(n):
        keys.append(Float64(i % K))
        v0.append(Float64(i) * 0.125 - 3.0)
        v1.append(Float64(n - i) * 2.0)
        v2.append(Float64(i % 17) - 8.0)
        # every value of group 4 in column 0 is null -> count 0, group present
        v0_valid.append(not ((i % K) == 4 or i % 5 == 0))
        v1_valid.append(i % 3 != 0)
        key_valid.append(i % 23 != 7)
    var kc_full = float64_from_list(keys.copy())
    var kc_nulls = float64_with_nulls(keys.copy(), key_valid.copy())
    var a_null = float64_with_nulls(v0.copy(), v0_valid^)
    var b_null = float64_with_nulls(v1.copy(), v1_valid^)
    var c_full = float64_from_list(v2.copy())

    # divergent counts: column 0 and 1 have nulls, column 2 does not
    var mixed_nulls = _batch3(kc_full, a_null, b_null, c_full, n)
    _compare_all_workers(t, "vnull_sum3", mixed_nulls, K, _ints3(1, 2, 3), _ints3(AGG_SUM, AGG_SUM, AGG_SUM))
    _compare_all_workers(t, "vnull_avg3", mixed_nulls, K, _ints3(1, 2, 3), _ints3(AGG_AVG, AGG_AVG, AGG_AVG))
    _compare_all_workers(t, "vnull_mix", mixed_nulls, K, _ints3(1, 2, 3), _ints3(AGG_MIN, AGG_MAX, AGG_COUNT))
    _compare_all_workers(t, "vnull_one", mixed_nulls, K, _ints(1), _ints(AGG_SUM))

    # null keys, no value nulls -> the SHARED-count layout with key exclusion
    var keynull = _batch3(
        kc_nulls,
        float64_from_list(v0.copy()),
        float64_from_list(v1.copy()),
        float64_from_list(v2.copy()),
        n,
    )
    _compare_all_workers(t, "knull_sum", keynull, K, _ints(1), _ints(AGG_SUM))
    _compare_all_workers(t, "knull_avg3", keynull, K, _ints3(1, 2, 3), _ints3(AGG_AVG, AGG_AVG, AGG_AVG))

    # null keys AND null values together
    var both = _batch3(kc_nulls, a_null, b_null, c_full, n)
    _compare_all_workers(t, "both_null", both, K, _ints3(1, 2, 3), _ints3(AGG_SUM, AGG_AVG, AGG_MIN))

    # ALL keys null: zero groups, every row tallied
    var all_null_valid = List[Bool]()
    for _ in range(n):
        all_null_valid.append(False)
    var kc_all_null = float64_with_nulls(keys.copy(), all_null_valid^)
    var none = _batch3(
        kc_all_null,
        float64_from_list(v0.copy()),
        float64_from_list(v1.copy()),
        float64_from_list(v2.copy()),
        n,
    )
    _compare_all_workers(t, "allkeysnull", none, K, _ints(1), _ints(AGG_SUM))
    var d = group_by_coded_dense_parallel(none, 0, K, _ints(1), _ints(AGG_SUM), 4)
    t.ok("allkeysnull.zero_groups", d.ok() and d.result.n_groups() == 0)
    t.ok("allkeysnull.tallied", d.result.null_key_rows == n)


def block4_adversarial_values(mut t: Tally):
    print("block 4: signed zero, infinities, ulp-sensitive means")
    var keys = List[Float64]()
    var vals = List[Float64]()
    # group 0: +0.0 first then -0.0  -> a tie must keep FIRST appearance
    keys.append(0.0)
    vals.append(0.0)
    keys.append(0.0)
    vals.append(-0.0)
    # group 1: -0.0 first then +0.0
    keys.append(1.0)
    vals.append(-0.0)
    keys.append(1.0)
    vals.append(0.0)
    # group 2: a lone -0.0 (its SUM must stay -0.0, which a fold from +0.0
    # would silently turn into +0.0)
    keys.append(2.0)
    vals.append(-0.0)
    # group 3: infinities both ways plus a finite
    keys.append(3.0)
    vals.append(Float64(1.0) / Float64(0.0))
    keys.append(3.0)
    vals.append(Float64(-1.0) / Float64(0.0))
    keys.append(3.0)
    vals.append(1.0)
    # group 4: magnitudes that make Welford and sum/n disagree in the last bits
    keys.append(4.0)
    vals.append(1e16)
    keys.append(4.0)
    vals.append(1.0)
    keys.append(4.0)
    vals.append(-1e16)
    keys.append(4.0)
    vals.append(1.0)
    # spread over more bands
    var state = UInt64(0xFEED_FACE)
    for _ in range(300):
        keys.append(Float64(Int(_lcg(state) % 5)))
        var pick = Int(_lcg(state) % 4)
        if pick == 0:
            vals.append(-0.0)
        elif pick == 1:
            vals.append(0.0)
        elif pick == 2:
            vals.append(_rand01(state) * 1e17)
        else:
            vals.append(-_rand01(state) * 1e-17)
    var batch = _batch1(keys, vals)
    _compare_all_workers(t, "zero_sum", batch, 5, _ints(1), _ints(AGG_SUM))
    _compare_all_workers(t, "zero_min", batch, 5, _ints(1), _ints(AGG_MIN))
    _compare_all_workers(t, "zero_max", batch, 5, _ints(1), _ints(AGG_MAX))
    _compare_all_workers(t, "ulp_avg", batch, 5, _ints(1), _ints(AGG_AVG))
    _compare_all_workers(
        t,
        "zero_all", batch, 5, _ints3(1, 1, 1), _ints3(AGG_SUM, AGG_MIN, AGG_AVG)
    )
    # -0.0 must survive the merge as -0.0 on the lone-row group.
    var d = group_by_coded_dense_parallel(batch, 0, 5, _ints(1), _ints(AGG_SUM), 8)
    var r = group_by_coded_parallel(batch, 0, 5, _ints(1), _ints(AGG_SUM), 8)
    t.ok("zero.status", d.ok() and r.ok())
    _same(t, "zero.w8", r.result, d.result)


def block5_refusals(mut t: Tally):
    print("block 5: refusals are statuses, not aborts")
    # A key PAST the cardinality. An unguarded dense store here is an
    # uncatchable abort, so this block finishing at all is the proof.
    var keys = List[Float64]()
    var vals = List[Float64]()
    for i in range(400):
        keys.append(Float64(i % 4))
        vals.append(Float64(i))
    keys[399] = 4.0  # == cardinality, one past the last legal code
    var batch = _batch1(keys, vals)
    var ws = _worker_counts()
    for i in range(len(ws)):
        var d = group_by_coded_dense_parallel(batch, 0, 4, _ints(1), _ints(AGG_SUM), ws[i])
        t.ok("refuse.past_bound@w" + String(ws[i]), d.status == GROUP_CODED_KEY_NOT_A_CODE)
        t.ok("refuse.past_bound_empty@w" + String(ws[i]), d.result.n_groups() == 0)
    # far past the bound, in the FIRST row (so the very first store would abort)
    keys[399] = 3.0
    keys[0] = 1e9
    var far = _batch1(keys, vals)
    t.ok(
        "refuse.far_past_bound",
        group_by_coded_dense_parallel(far, 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == GROUP_CODED_KEY_NOT_A_CODE,
    )
    keys[0] = -1.0
    t.ok(
        "refuse.negative",
        group_by_coded_dense_parallel(_batch1(keys, vals), 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == GROUP_CODED_KEY_NOT_A_CODE,
    )
    keys[0] = -0.5
    t.ok(
        "refuse.negative_fraction",
        group_by_coded_dense_parallel(_batch1(keys, vals), 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == GROUP_CODED_KEY_NOT_A_CODE,
    )
    keys[0] = 2.5
    t.ok(
        "refuse.fractional",
        group_by_coded_dense_parallel(_batch1(keys, vals), 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == GROUP_CODED_KEY_NOT_A_CODE,
    )
    keys[0] = bitcast[DType.float64](CANONICAL_NAN_BITS)
    t.ok(
        "refuse.nan_key",
        group_by_coded_dense_parallel(_batch1(keys, vals), 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == GROUP_CODED_KEY_NOT_A_CODE,
    )
    keys[0] = Float64(1.0) / Float64(0.0)
    t.ok(
        "refuse.inf_key",
        group_by_coded_dense_parallel(_batch1(keys, vals), 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == GROUP_CODED_KEY_NOT_A_CODE,
    )
    # The reference engine refuses the same shapes, so the ROUTE is not
    # trading a refusal for an answer or the other way round.
    keys[0] = 4.0
    var same_shape = _batch1(keys, vals)
    t.ok(
        "refuse.reference_agrees",
        group_by_coded_parallel(same_shape, 0, 4, _ints(1), _ints(AGG_SUM), 8).status
        == group_by_coded_dense_parallel(same_shape, 0, 4, _ints(1), _ints(AGG_SUM), 8).status,
    )

    keys[0] = 0.0
    var clean = _batch1(keys, vals)
    # cardinality
    t.ok(
        "refuse.card_zero",
        group_by_coded_dense_parallel(clean, 0, 0, _ints(1), _ints(AGG_SUM), 4).status
        == GROUP_CODED_CARDINALITY_INVALID,
    )
    t.ok(
        "refuse.card_negative",
        group_by_coded_dense_parallel(clean, 0, -3, _ints(1), _ints(AGG_SUM), 4).status
        == GROUP_CODED_CARDINALITY_INVALID,
    )
    t.ok(
        "refuse.card_past_ceiling",
        group_by_coded_dense_parallel(
            clean, 0, DENSE_MAX_CARDINALITY + 1, _ints(1), _ints(AGG_SUM), 4
        ).status
        == GROUP_CODED_CARDINALITY_INVALID,
    )
    # opcodes this packing cannot hold -> a ROUTING signal, not a failure
    t.ok(
        "refuse.var",
        group_by_coded_dense_parallel(clean, 0, 4, _ints(1), _ints(AGG_VAR), 4).status
        == GROUP_DENSE_OPCODE_UNSUPPORTED,
    )
    t.ok(
        "refuse.std",
        group_by_coded_dense_parallel(clean, 0, 4, _ints(1), _ints(AGG_STD), 4).status
        == GROUP_DENSE_OPCODE_UNSUPPORTED,
    )
    t.ok(
        "refuse.unknown_opcode",
        group_by_coded_dense_parallel(clean, 0, 4, _ints(1), _ints(9999), 4).status
        == GROUP_DENSE_OPCODE_UNSUPPORTED,
    )
    t.ok("supports.sum", dense_supports_opcode(AGG_SUM))
    t.ok("supports.avg", dense_supports_opcode(AGG_AVG))
    t.ok("supports.min", dense_supports_opcode(AGG_MIN))
    t.ok("supports.max", dense_supports_opcode(AGG_MAX))
    t.ok("supports.count", dense_supports_opcode(AGG_COUNT))
    t.ok("supports.not_var", not dense_supports_opcode(AGG_VAR))
    t.ok("supports.not_std", not dense_supports_opcode(AGG_STD))
    t.ok("supports.not_unknown", not dense_supports_opcode(-1))
    # malformed pairing
    var two_cols = List[Int]()
    two_cols.append(1)
    two_cols.append(1)
    t.ok(
        "refuse.pair_mismatch",
        group_by_coded_dense_parallel(clean, 0, 4, two_cols, _ints(AGG_SUM), 4).status
        == GROUP_CODED_BAD_REQUEST,
    )
    t.ok(
        "refuse.no_aggs",
        group_by_coded_dense_parallel(clean, 0, 4, List[Int](), List[Int](), 4).status
        == GROUP_CODED_BAD_REQUEST,
    )
    # state budget: a legal cardinality whose TOTAL state is not
    t.ok(
        "refuse.state_too_large",
        group_by_coded_dense_parallel(
            clean, 0, DENSE_MAX_CARDINALITY, _ints3(1, 1, 1), _ints3(AGG_SUM, AGG_SUM, AGG_SUM), 16
        ).status
        == GROUP_DENSE_STATE_TOO_LARGE,
    )
    # and the unsuffixed entry point takes the same decisions
    t.ok(
        "entry.group_by_coded_dense_refuses",
        group_by_coded_dense(clean, 0, 0, _ints(1), _ints(AGG_SUM)).status
        == GROUP_CODED_CARDINALITY_INVALID,
    )
    t.ok("entry.group_by_coded_dense_ok", group_by_coded_dense(clean, 0, 4, _ints(1), _ints(AGG_SUM)).ok())


def block6b_apply_arms(mut t: Tally):
    print("block 6b: every _apply arm == the frozen primitive it claims to be")
    # Pinned DIRECTLY, not only through a scan, because which scan reaches which
    # arm is a routing decision: `AGG_AVG` is reached from the vector scan on a
    # uniform request and from `_apply_dyn` on a mixed one, and an earlier draft
    # had an arm no scan reached at all — a mutation there passed every test.
    var nan = bitcast[DType.float64](CANONICAL_NAN_BITS)
    var vs = List[Float64]()
    vs.append(0.0)
    vs.append(-0.0)
    vs.append(1.0)
    vs.append(-7.25)
    vs.append(1e16)
    vs.append(-1e16)
    vs.append(1e-300)
    vs.append(Float64(1.0) / Float64(0.0))
    vs.append(nan)
    var cs = List[Float64]()
    cs.append(1.0)
    cs.append(2.0)
    cs.append(3.0)
    cs.append(1e7)
    var sum_bad = 0
    var avg_bad = 0
    var min_bad = 0
    var max_bad = 0
    var cnt_bad = 0
    var cases = 0
    for i in range(len(vs)):
        for j in range(len(vs)):
            for k in range(len(cs)):
                cases += 1
                var cur = vs[i]
                var v = vs[j]
                var c = cs[k]
                if _bits(_apply_dyn(AGG_SUM, cur, v, c)) != _bits(
                    group_sum_update(cur, v)
                ):
                    sum_bad += 1
                if _bits(_apply_dyn(AGG_AVG, cur, v, c)) != _bits(
                    group_mean_update(cur, v, c)
                ):
                    avg_bad += 1
                if _bits(_apply_dyn(AGG_MIN, cur, v, c)) != _bits(
                    _dense_min_fold(cur, v)
                ):
                    min_bad += 1
                if _bits(_apply_dyn(AGG_MAX, cur, v, c)) != _bits(
                    _dense_max_fold(cur, v)
                ):
                    max_bad += 1
                # COUNT keeps the payload untouched: its answer is the count slot
                if _bits(_apply_dyn(AGG_COUNT, cur, v, c)) != _bits(cur):
                    cnt_bad += 1
    t.ok("apply.sum_is_group_sum_update", sum_bad == 0)
    t.ok("apply.avg_is_group_mean_update", avg_bad == 0)
    t.ok("apply.min_is_the_sentinel_fold", min_bad == 0)
    t.ok("apply.max_is_the_sentinel_fold", max_bad == 0)
    t.ok("apply.count_leaves_the_payload", cnt_bad == 0)
    t.ok("apply.unknown_opcode_leaves_the_payload", _bits(_apply_dyn(-1, 5.0, 9.0, 2.0)) == _bits(Float64(5.0)))
    t.ok("apply.cases_ran", cases >= 300)


def block6_fold_equivalence(mut t: Tally):
    print("block 6: _dense_min_fold / _dense_max_fold == the frozen-primitive reference")
    var nan = bitcast[DType.float64](CANONICAL_NAN_BITS)
    var other_nan = bitcast[DType.float64](UInt64(0x7FF8_0000_0000_0001))
    var inf = Float64(1.0) / Float64(0.0)
    var vs = List[Float64]()
    vs.append(0.0)
    vs.append(-0.0)
    vs.append(1.0)
    vs.append(-1.0)
    vs.append(1e308)
    vs.append(-1e308)
    vs.append(5e-324)
    vs.append(inf)
    vs.append(-inf)
    vs.append(nan)
    vs.append(other_nan)
    var min_bad = 0
    var max_bad = 0
    var seeded_cases = 0
    for i in range(len(vs)):
        # SEEDED: `current` is a real extremum, so `seen` is True.
        var current = vs[i]
        if current != current:
            continue  # a real extremum is never NaN under this policy
        for j in range(len(vs)):
            seeded_cases += 1
            if _bits(_dense_min_fold(current, vs[j])) != _bits(
                _dense_min_reference(current, True, vs[j])
            ):
                min_bad += 1
            if _bits(_dense_max_fold(current, vs[j])) != _bits(
                _dense_max_reference(current, True, vs[j])
            ):
                max_bad += 1
        # UNSEEDED: `current` is the canonical-NaN sentinel, `seen` is False.
        seeded_cases += 1
        if _bits(_dense_min_fold(nan, current)) != _bits(
            _dense_min_reference(0.0, False, current)
        ):
            min_bad += 1
        if _bits(_dense_max_fold(nan, current)) != _bits(
            _dense_max_reference(0.0, False, current)
        ):
            max_bad += 1
    t.ok("fold.min_equals_reference", min_bad == 0)
    t.ok("fold.max_equals_reference", max_bad == 0)
    t.ok("fold.cases_ran", seeded_cases > 100)
    # The sentinel absorbs NaN in both directions: a NaN never seeds.
    t.ok("fold.nan_never_seeds_min", _bits(_dense_min_fold(nan, other_nan)) == CANONICAL_NAN_BITS)
    t.ok("fold.nan_never_seeds_max", _bits(_dense_max_fold(nan, other_nan)) == CANONICAL_NAN_BITS)
    # A tie keeps `current` -> first appearance survives for signed zero.
    t.ok("fold.min_tie_keeps_first", _bits(_dense_min_fold(0.0, -0.0)) == _bits(Float64(0.0)))
    t.ok("fold.max_tie_keeps_first", _bits(_dense_max_fold(-0.0, 0.0)) == _bits(Float64(-0.0)))


def block7_budget_table(mut t: Tally):
    print("block 7: state-byte arithmetic and the route table")
    # The record stride is what the scan, the merge and the byte budget all
    # index with, so it is pinned rather than inferred from any one of them.
    t.ok("stride.shared_1agg_is_a_16B_vector", dense_record_stride(1, True) == 2)
    t.ok("stride.shared_2aggs_pads_to_a_32B_vector", dense_record_stride(2, True) == 4)
    t.ok("stride.shared_3aggs_is_a_32B_vector", dense_record_stride(3, True) == 4)
    t.ok("stride.shared_4aggs_stops_padding", dense_record_stride(4, True) == 5)
    t.ok("stride.shared_8aggs_stops_padding", dense_record_stride(8, True) == 9)
    t.ok("stride.percol_is_count_plus_payload", dense_record_stride(3, False) == 6)
    t.ok("stride.percol_1agg", dense_record_stride(1, False) == 2)
    t.ok(
        "stride.bytes_use_the_same_stride",
        dense_state_bytes(101, 2, 4, True) == 4 * _pad8(101 * dense_record_stride(2, True)) * 8
        + 4 * 101 * 8,
    )
    # shared-count layout: stride 1 + n_aggs, padded to 8 slots
    t.ok("bytes.q1_shape", dense_state_bytes(101, 1, 16, True) == 16 * 208 * 8 + 16 * 101 * 8)
    t.ok("bytes.q4_shape", dense_state_bytes(101, 3, 16, True) == 16 * 408 * 8 + 16 * 101 * 8)
    # divergent-count layout: stride 2 * n_aggs, and a `seen` byte per code
    t.ok(
        "bytes.nulls_layout",
        dense_state_bytes(101, 3, 16, False) == 16 * 608 * 8 + 16 * 101 * 8 + 16 * 101,
    )
    t.ok("bytes.grows_with_workers", dense_state_bytes(101, 1, 32, True) > dense_state_bytes(101, 1, 16, True))
    t.ok("bytes.counts_seen_only_when_present", dense_state_bytes(64, 2, 4, False) > dense_state_bytes(64, 2, 4, True))
    t.ok("route.q1_ok", dense_route_status(101, _ints(1), _ints(AGG_SUM), 16, True) == GROUP_CODED_OK)
    t.ok(
        "route.q4_ok",
        dense_route_status(101, _ints3(1, 2, 3), _ints3(AGG_AVG, AGG_AVG, AGG_AVG), 16, True)
        == GROUP_CODED_OK,
    )
    # 1e5 codes -- the id3/id6 shape query.aggregate's 4096 ceiling locks out
    t.ok("route.1e5_codes_ok", dense_route_status(100001, _ints(1), _ints(AGG_SUM), 16, True) == GROUP_CODED_OK)
    t.ok(
        "route.1e5_codes_3aggs_ok",
        dense_route_status(100001, _ints3(1, 2, 3), _ints3(AGG_AVG, AGG_AVG, AGG_AVG), 16, True)
        == GROUP_CODED_OK,
    )
    t.ok(
        "route.budget_refuses",
        dense_route_status(DENSE_MAX_CARDINALITY, _ints(1), _ints(AGG_SUM), 16, True)
        == GROUP_DENSE_STATE_TOO_LARGE,
    )
    t.ok(
        "route.budget_is_the_binding_bound",
        dense_state_bytes(DENSE_MAX_CARDINALITY, 1, 16, True) > DENSE_MAX_STATE_BYTES,
    )
    t.ok("route.card_invalid", dense_route_status(0, _ints(1), _ints(AGG_SUM), 16, True) == GROUP_CODED_CARDINALITY_INVALID)
    t.ok("route.opcode", dense_route_status(101, _ints(1), _ints(AGG_VAR), 16, True) == GROUP_DENSE_OPCODE_UNSUPPORTED)
    t.ok(
        "route.bad_request",
        dense_route_status(101, List[Int](), List[Int](), 16, True) == GROUP_CODED_BAD_REQUEST,
    )


def main():
    print("=== test_query_coded_dense ===")
    var t = Tally()
    block1_identity_random(t)
    var after1 = t.nan_exempt
    t.ok("block1.strict_no_nan_exemptions", after1 == 0)
    block2_nan_policy(t)
    block2b_nan_payload(t)
    # Everything from here on is strict again: 2b is the ONLY block permitted
    # to consume a payload exemption, and this pins that.
    var budget = t.nan_exempt
    t.ok("block2b.consumed_exemptions", budget > 0)
    block3_nulls(t)
    t.ok("block3.strict_no_nan_exemptions", t.nan_exempt == budget)
    block4_adversarial_values(t)
    t.ok(
        "block4.inf_minus_inf_is_the_DEFAULT_nan_so_still_strict",
        t.nan_exempt == budget,
    )
    block5_refusals(t)
    block6_fold_equivalence(t)
    block6b_apply_arms(t)
    block7_budget_table(t)
    print("")
    print(
        "checks=" + String(t.checks)
        + " failures=" + String(t.failures)
        + " nan_payload_exemptions=" + String(t.nan_exempt)
    )
    if t.failures != 0:
        print("FAILED")
    else:
        print("ALL PASS")
