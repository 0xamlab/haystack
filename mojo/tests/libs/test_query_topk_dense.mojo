"""test_query_topk_dense.mojo — `query.topk_dense` against a naive full-scan
reference and against itself across worker counts.

Blocks:
  1. RANDOM CROSSCHECK: for every code in a random dense-keyed dataset, the
     engine's (top1, top2, present1, present2) must equal `_top2_reference`'s
     answer over exactly that code's rows — a full independent scan, at
     several worker counts (1, 2, 3, 5, 8, 16).
  2. HAND-CHECKABLE EDGE CASES: group size 1 (present2 False), an all-duplicate
     group (top1 == top2, both present), negative and zero values, and a NaN
     value inside a group (ranks nothing, but the row still belongs to the
     group).
  3. NULLS: a null key excluded and tallied; a null value contributing no
     rank but not excluding the row's group membership.
  4. REFUSALS: cardinality 0 / negative / past DENSE_MAX_CARDINALITY, a
     fractional key, a negative key, a key at/past the bound, and the byte
     budget.
  5. WORKER-COUNT INVARIANCE: the fold performs no arithmetic (only
     compares), so the reported VALUES must be identical whatever worker
     count answers the same data — proven, not assumed.
"""
from std.memory import bitcast

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from query.coded_dense import DENSE_MAX_CARDINALITY
from query.aggregate import (
    GROUP_CODED_CARDINALITY_INVALID,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
)
from query.topk_dense import (
    GROUP_TOPK_STATE_TOO_LARGE,
    Top2GroupedResult,
    group_top2_dense_parallel,
    topk_route_status,
    topk_state_bytes,
    _fold_top2,
    _top2_reference,
)

struct Tally(Copyable, Movable):
    var checks: Int
    var failures: Int

    def __init__(out self):
        self.checks = 0
        self.failures = 0

    def ok(mut self, name: String, condition: Bool):
        self.checks += 1
        if not condition:
            self.failures += 1
            print("  FAIL " + name)


def _lcg(mut state: UInt64) -> UInt64:
    state = state * 6364136223846793005 + 1442695040888963407
    return state


def _rand01(mut state: UInt64) -> Float64:
    return Float64(Int(_lcg(state) >> 11)) / Float64(Int(UInt64(1) << 53))


def _batch1(keys: List[Float64], v: List[Float64]) -> RecordBatch:
    var names = List[String]()
    names.append("k")
    names.append("v")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(keys.copy()))
    cols.append(float64_from_list(v.copy()))
    return RecordBatch(schema_of(names^), cols^, len(keys))


def _bits(x: Float64) -> UInt64:
    return bitcast[DType.uint64](x)


def block1_random_crosscheck(mut t: Tally):
    var state: UInt64 = 0xC0FFEE
    var n = 4000
    var cardinality = 23
    var keys = List[Float64]()
    var vals = List[Float64]()
    for _ in range(n):
        var code = Int(_rand01(state) * Float64(cardinality))
        if code >= cardinality:
            code = cardinality - 1
        keys.append(Float64(code))
        vals.append((_rand01(state) - 0.5) * 200.0)
    var batch = _batch1(keys, vals)

    var worker_counts = List[Int]()
    worker_counts.append(1)
    worker_counts.append(2)
    worker_counts.append(3)
    worker_counts.append(5)
    worker_counts.append(8)
    worker_counts.append(16)

    for wi in range(len(worker_counts)):
        var workers = worker_counts[wi]
        var res = group_top2_dense_parallel(batch, 0, cardinality, 1, workers)
        t.ok("block1.ok.w" + String(workers), res.ok())
        if not res.ok():
            continue
        var seen_group = List[Bool](length=cardinality, fill=False)
        for g in range(res.result.n_groups()):
            var code = Int(res.result.key_tuples[g])
            seen_group[code] = True
            var group_vals = List[Float64]()
            for i in range(n):
                if Int(keys[i]) == code:
                    group_vals.append(vals[i])
            var ref_top1: Float64 = 0.0
            var ref_top2: Float64 = 0.0
            var ranked = _top2_reference(group_vals, ref_top1, ref_top2)
            t.ok(
                "block1.present1.w" + String(workers) + ".c" + String(code),
                res.result.present1[g] == (ranked >= 1),
            )
            t.ok(
                "block1.present2.w" + String(workers) + ".c" + String(code),
                res.result.present2[g] == (ranked >= 2),
            )
            if ranked >= 1:
                t.ok(
                    "block1.top1.w" + String(workers) + ".c" + String(code),
                    _bits(res.result.top1[g]) == _bits(ref_top1),
                )
            if ranked >= 2:
                t.ok(
                    "block1.top2.w" + String(workers) + ".c" + String(code),
                    _bits(res.result.top2[g]) == _bits(ref_top2),
                )
        # Every code that actually appears in the data must be a reported
        # group — a silently dropped group is a wrong answer no per-cell
        # comparison above would catch.
        var expected_groups = 0
        for c in range(cardinality):
            var present = False
            for i in range(n):
                if Int(keys[i]) == c:
                    present = True
                    break
            if present:
                expected_groups += 1
        t.ok(
            "block1.group_count.w" + String(workers),
            res.result.n_groups() == expected_groups,
        )


def block2_edge_cases(mut t: Tally):
    # group size 1
    var k1 = List[Float64]()
    var v1 = List[Float64]()
    k1.append(0.0)
    v1.append(42.0)
    var b1 = _batch1(k1, v1)
    var r1 = group_top2_dense_parallel(b1, 0, 1, 1, 1)
    t.ok("block2.size1.ok", r1.ok())
    t.ok("block2.size1.present1", r1.result.present1[0])
    t.ok("block2.size1.present2_false", not r1.result.present2[0])
    t.ok("block2.size1.top1", r1.result.top1[0] == 42.0)

    # all-duplicate group
    var k2 = List[Float64]()
    var v2 = List[Float64]()
    for _ in range(5):
        k2.append(0.0)
        v2.append(7.0)
    var b2 = _batch1(k2, v2)
    var r2 = group_top2_dense_parallel(b2, 0, 1, 1, 1)
    t.ok("block2.dup.top1", r2.result.top1[0] == 7.0)
    t.ok("block2.dup.top2", r2.result.top2[0] == 7.0)
    t.ok("block2.dup.present2", r2.result.present2[0])

    # negative and zero values
    var k3 = List[Float64]()
    var v3 = List[Float64]()
    var raw3 = List[Float64]()
    raw3.append(-5.0)
    raw3.append(0.0)
    raw3.append(-1.0)
    raw3.append(-10.0)
    for i in range(len(raw3)):
        k3.append(0.0)
        v3.append(raw3[i])
    var b3 = _batch1(k3, v3)
    var r3 = group_top2_dense_parallel(b3, 0, 1, 1, 1)
    t.ok("block2.neg.top1", r3.result.top1[0] == 0.0)
    t.ok("block2.neg.top2", r3.result.top2[0] == -1.0)

    # NaN inside a group: ranks nothing, row still belongs to the group
    var nan_val = Float64(0.0) / Float64(0.0)
    var k4 = List[Float64]()
    var v4 = List[Float64]()
    k4.append(0.0)
    v4.append(nan_val)
    k4.append(0.0)
    v4.append(3.0)
    var b4 = _batch1(k4, v4)
    var r4 = group_top2_dense_parallel(b4, 0, 1, 1, 1)
    t.ok("block2.nan.present1", r4.result.present1[0])
    t.ok("block2.nan.top1_is_the_real_value", r4.result.top1[0] == 3.0)
    t.ok("block2.nan.present2_false", not r4.result.present2[0])

    # an all-NaN group: the group exists (present1 False, not a crash)
    var k5 = List[Float64]()
    var v5 = List[Float64]()
    k5.append(0.0)
    v5.append(nan_val)
    k5.append(0.0)
    v5.append(nan_val)
    var b5 = _batch1(k5, v5)
    var r5 = group_top2_dense_parallel(b5, 0, 1, 1, 1)
    t.ok("block2.allnan.ok", r5.ok())
    t.ok("block2.allnan.n_groups", r5.result.n_groups() == 1)
    t.ok("block2.allnan.present1_false", not r5.result.present1[0])


def block3_nulls(mut t: Tally):
    var names = List[String]()
    names.append("k")
    names.append("v")
    var keys = List[Float64]()
    keys.append(0.0)
    keys.append(0.0)
    keys.append(1.0)
    var kmask = List[Bool]()
    kmask.append(True)
    kmask.append(False)  # null key: excluded, tallied
    kmask.append(True)
    var vals = List[Float64]()
    vals.append(5.0)
    vals.append(9.0)
    vals.append(3.0)
    var vmask = List[Bool]()
    vmask.append(False)  # null value: row belongs to group 0, ranks nothing
    vmask.append(True)
    vmask.append(True)
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(keys^, kmask))
    cols.append(float64_with_nulls(vals^, vmask))
    var batch = RecordBatch(schema_of(names^), cols^, 3)

    var res = group_top2_dense_parallel(batch, 0, 2, 1, 1)
    t.ok("block3.null_key_rows", res.result.null_key_rows == 1)
    t.ok("block3.groups", res.result.n_groups() == 2)
    # group 0: one row with a null value -> no ranked value
    t.ok("block3.group0.present1_false", not res.result.present1[0])
    # group 1: one row, value 3.0
    t.ok("block3.group1.present1", res.result.present1[1])
    t.ok("block3.group1.top1", res.result.top1[1] == 3.0)


def block4_refusals(mut t: Tally):
    var k = List[Float64]()
    var v = List[Float64]()
    k.append(0.0)
    v.append(1.0)
    var b = _batch1(k, v)

    t.ok(
        "block4.cardinality_zero",
        group_top2_dense_parallel(b, 0, 0, 1, 1).status == GROUP_CODED_CARDINALITY_INVALID,
    )
    t.ok(
        "block4.cardinality_negative",
        group_top2_dense_parallel(b, 0, -5, 1, 1).status == GROUP_CODED_CARDINALITY_INVALID,
    )
    t.ok(
        "block4.cardinality_too_large",
        group_top2_dense_parallel(b, 0, DENSE_MAX_CARDINALITY + 1, 1, 1).status
        == GROUP_CODED_CARDINALITY_INVALID,
    )

    # a fractional key refuses the whole call
    var k2 = List[Float64]()
    var v2 = List[Float64]()
    k2.append(0.5)
    v2.append(1.0)
    var b2 = _batch1(k2, v2)
    t.ok(
        "block4.fractional_key",
        group_top2_dense_parallel(b2, 0, 5, 1, 1).status == GROUP_CODED_KEY_NOT_A_CODE,
    )

    # a negative key refuses
    var k3 = List[Float64]()
    var v3 = List[Float64]()
    k3.append(-1.0)
    v3.append(1.0)
    var b3 = _batch1(k3, v3)
    t.ok(
        "block4.negative_key",
        group_top2_dense_parallel(b3, 0, 5, 1, 1).status == GROUP_CODED_KEY_NOT_A_CODE,
    )

    # a key at the bound (== cardinality) refuses
    var k4 = List[Float64]()
    var v4 = List[Float64]()
    k4.append(5.0)
    v4.append(1.0)
    var b4 = _batch1(k4, v4)
    t.ok(
        "block4.key_at_bound",
        group_top2_dense_parallel(b4, 0, 5, 1, 1).status == GROUP_CODED_KEY_NOT_A_CODE,
    )

    # the byte budget: a huge cardinality at a huge worker count refuses by
    # STATUS rather than allocating.
    t.ok(
        "block4.state_too_large",
        topk_route_status(1 << 20, 1 << 20) == GROUP_TOPK_STATE_TOO_LARGE,
    )
    t.ok(
        "block4.state_bytes_zero_on_bad_shape",
        topk_state_bytes(0, 4) == 0 and topk_state_bytes(4, 0) == 0,
    )


def block5_worker_invariance(mut t: Tally):
    """The fold performs no arithmetic (compares only), so two DIFFERENT
    worker counts over the SAME data must report the identical top1/top2 —
    not merely close, identical, because there is no floating-point
    association to differ by."""
    var state: UInt64 = 0xABCD1234
    var n = 2000
    var cardinality = 17
    var keys = List[Float64]()
    var vals = List[Float64]()
    for _ in range(n):
        var code = Int(_rand01(state) * Float64(cardinality))
        if code >= cardinality:
            code = cardinality - 1
        keys.append(Float64(code))
        vals.append((_rand01(state) - 0.5) * 1000.0)
    var batch = _batch1(keys, vals)

    var r1 = group_top2_dense_parallel(batch, 0, cardinality, 1, 1)
    var r16 = group_top2_dense_parallel(batch, 0, cardinality, 1, 16)
    t.ok("block5.same_group_count", r1.result.n_groups() == r16.result.n_groups())
    var mismatches = 0
    for g in range(r1.result.n_groups()):
        var code = Int(r1.result.key_tuples[g])
        for g2 in range(r16.result.n_groups()):
            if Int(r16.result.key_tuples[g2]) == code:
                if _bits(r1.result.top1[g]) != _bits(r16.result.top1[g2]):
                    mismatches += 1
                if _bits(r1.result.top2[g]) != _bits(r16.result.top2[g2]):
                    mismatches += 1
                if r1.result.present1[g] != r16.result.present1[g2]:
                    mismatches += 1
                if r1.result.present2[g] != r16.result.present2[g2]:
                    mismatches += 1
    t.ok("block5.worker_invariant", mismatches == 0)


def block6_fold_unit(mut t: Tally):
    """`_fold_top2` in isolation: the exact three-way tie the module header
    argues about, and the sequence a running fold sees one value at a time."""
    var t1: Float64 = Float64(0.0) / Float64(0.0)
    var t2: Float64 = Float64(0.0) / Float64(0.0)
    _fold_top2(t1, t2, 5.0)
    t.ok("block6.first", t1 == 5.0 and not (t2 == t2))
    _fold_top2(t1, t2, 5.0)
    t.ok("block6.tie_second", t1 == 5.0 and t2 == 5.0)
    _fold_top2(t1, t2, 5.0)
    t.ok("block6.tie_third_no_change", t1 == 5.0 and t2 == 5.0)
    _fold_top2(t1, t2, 9.0)
    t.ok("block6.new_max_shifts_down", t1 == 9.0 and t2 == 5.0)
    _fold_top2(t1, t2, Float64(0.0) / Float64(0.0))
    t.ok("block6.nan_no_effect", t1 == 9.0 and t2 == 5.0)


def main():
    print("=== test_query_topk_dense ===")
    var t = Tally()
    block1_random_crosscheck(t)
    block2_edge_cases(t)
    block3_nulls(t)
    block4_refusals(t)
    block5_worker_invariance(t)
    block6_fold_unit(t)
    print("")
    print("checks=" + String(t.checks) + " failures=" + String(t.failures))
    if t.failures != 0:
        print("FAILED")
    else:
        print("ALL PASS")
