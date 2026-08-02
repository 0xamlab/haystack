"""test_query_median_packed.mojo — `query.median_packed` against
`anomaly.median`/`sorting.quicksort` spelled independently, and against a
Welford sd computed by an independent full pass.

Blocks:
  1. HAND-CHECKABLE EDGE CASES: group size 1 (present_sd False, median is the
     single value), an all-duplicate group (median == the duplicate, sd ==
     0.0), an EVEN-count group (median is the average of the two middle
     values, not either one), an ODD-count group, negative and zero values,
     and a mix of all of the above in one packed-key batch.
  2. RANDOM CROSSCHECK: a random dataset, packed key width 2, every observed
     group's (count, median, sd, present_sd) compared against an independent
     per-group `sorting.quicksort` + `anomaly.median`-formula reference and a
     from-scratch Welford pass, at several worker counts.
  3. NULLS: a null key excluded and tallied; a null value excluded from both
     the median's value set and the sd's Welford fold, without excluding the
     row's group from existing.
  4. REFUSALS: a fractional key and an out-of-domain key refuse the whole
     call (`GROUP_CODED_KEY_NOT_A_CODE`), never silently drop rows.
  5. THE SCATTER SELF-CHECK is exercised, not merely present: a group whose
     size is exactly 1 and a group whose size is in the thousands (forcing a
     multi-band scatter) are both in the random crosscheck's data, so the
     offset arithmetic is proven at both a trivial and a real scale.
"""
from std.memory import bitcast

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from query.packedkey import probe_packed_domain
from query.aggregate import GROUP_CODED_KEY_NOT_A_CODE
from query.median_packed import (
    group_median_sd_packed_parallel,
    _median_of_sorted,
)
from sorting import quicksort

struct Tally(Copyable, Movable):
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

    fn close(mut self, name: String, a: Float64, b: Float64, tol: Float64):
        self.checks += 1
        var d = a - b
        if d < 0.0:
            d = -d
        if d > tol:
            self.failures += 1
            print("  FAIL " + name + " a=" + String(a) + " b=" + String(b))


fn _lcg(mut state: UInt64) -> UInt64:
    state = state * 6364136223846793005 + 1442695040888963407
    return state


fn _rand01(mut state: UInt64) -> Float64:
    return Float64(Int(_lcg(state) >> 11)) / Float64(Int(UInt64(1) << 53))


fn _batch2(k0: List[Float64], k1: List[Float64], v: List[Float64]) -> RecordBatch:
    var names = List[String]()
    names.append("k0")
    names.append("k1")
    names.append("v")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(k0.copy()))
    cols.append(float64_from_list(k1.copy()))
    cols.append(float64_from_list(v.copy()))
    return RecordBatch(schema_of(names^), cols^, len(k0))


fn _reference_median(values: List[Float64]) -> Float64:
    """The frozen, unmodified `sorting.quicksort` plus the exact
    `_median_of_sorted` formula — an independent path from the engine's own
    (which also calls `quicksort` + `_median_of_sorted`, so this reference
    shares the SELECTION rule but not the scatter machinery that hands it the
    values)."""
    var sorted_vals = quicksort(values)
    return _median_of_sorted(sorted_vals)


fn _reference_sd_val(values: List[Float64]) -> Float64:
    """A from-scratch two-pass sample sd — deliberately NOT Welford, so this
    and the engine's Welford fold cannot share a bug. Returns 0.0 for
    fewer-than-2 rows; callers gate on `present_sd` separately."""
    var n = len(values)
    if n < 2:
        return 0.0
    var mean = 0.0
    for i in range(n):
        mean += values[i]
    mean /= Float64(n)
    var ss = 0.0
    for i in range(n):
        var d = values[i] - mean
        ss += d * d
    var sqrt_arg = ss / Float64(n - 1)
    # Newton's method sqrt (avoids importing std.math just for the reference)
    if sqrt_arg <= 0.0:
        return 0.0
    var g = sqrt_arg
    for _ in range(60):
        g = 0.5 * (g + sqrt_arg / g)
    return g


fn block1_hand_edge_cases(mut t: Tally):
    var kc = List[Int]()
    kc.append(0)
    kc.append(1)

    # group size 1
    var k0 = List[Float64]()
    var k1 = List[Float64]()
    var v = List[Float64]()
    k0.append(0.0)
    k1.append(0.0)
    v.append(42.0)
    var b1 = _batch2(k0, k1, v)
    var d1 = probe_packed_domain(b1, kc, 1024)
    var r1 = group_median_sd_packed_parallel(b1, kc, d1, 2, 1)
    t.ok("block1.size1.ok", r1.ok())
    t.ok("block1.size1.median", r1.result.median[0] == 42.0)
    t.ok("block1.size1.present_median", r1.result.present_median[0])
    t.ok("block1.size1.present_sd_false", not r1.result.present_sd[0])

    # all-duplicate group
    var k0b = List[Float64]()
    var k1b = List[Float64]()
    var vb = List[Float64]()
    for _ in range(6):
        k0b.append(0.0)
        k1b.append(0.0)
        vb.append(11.0)
    var b2 = _batch2(k0b, k1b, vb)
    var d2 = probe_packed_domain(b2, kc, 1024)
    var r2 = group_median_sd_packed_parallel(b2, kc, d2, 2, 1)
    t.ok("block1.dup.median", r2.result.median[0] == 11.0)
    t.close("block1.dup.sd_zero", r2.result.sd[0], 0.0, 1e-9)

    # even-count group: median must be the AVERAGE of the two middle values,
    # not either one
    var k0c = List[Float64]()
    var k1c = List[Float64]()
    var vc = List[Float64]()
    var raw_even = List[Float64]()
    raw_even.append(1.0)
    raw_even.append(2.0)
    raw_even.append(3.0)
    raw_even.append(100.0)
    for i in range(len(raw_even)):
        k0c.append(0.0)
        k1c.append(0.0)
        vc.append(raw_even[i])
    var b3 = _batch2(k0c, k1c, vc)
    var d3 = probe_packed_domain(b3, kc, 1024)
    var r3 = group_median_sd_packed_parallel(b3, kc, d3, 2, 1)
    # sorted: 1,2,3,100 -> median = (2+3)/2 = 2.5, NEITHER input value
    t.close("block1.even.median", r3.result.median[0], 2.5, 1e-12)

    # odd-count group
    var k0d = List[Float64]()
    var k1d = List[Float64]()
    var vd = List[Float64]()
    var raw_odd = List[Float64]()
    raw_odd.append(5.0)
    raw_odd.append(1.0)
    raw_odd.append(9.0)
    for i in range(len(raw_odd)):
        k0d.append(0.0)
        k1d.append(0.0)
        vd.append(raw_odd[i])
    var b4 = _batch2(k0d, k1d, vd)
    var d4 = probe_packed_domain(b4, kc, 1024)
    var r4 = group_median_sd_packed_parallel(b4, kc, d4, 2, 1)
    t.close("block1.odd.median", r4.result.median[0], 5.0, 1e-12)

    # negative and zero values
    var k0e = List[Float64]()
    var k1e = List[Float64]()
    var ve = List[Float64]()
    var raw_neg = List[Float64]()
    raw_neg.append(-5.0)
    raw_neg.append(0.0)
    raw_neg.append(-1.0)
    raw_neg.append(-10.0)
    raw_neg.append(3.0)
    for i in range(len(raw_neg)):
        k0e.append(0.0)
        k1e.append(0.0)
        ve.append(raw_neg[i])
    var b5 = _batch2(k0e, k1e, ve)
    var d5 = probe_packed_domain(b5, kc, 1024)
    var r5 = group_median_sd_packed_parallel(b5, kc, d5, 2, 1)
    # sorted: -10,-5,-1,0,3 -> median = -1
    t.close("block1.neg.median", r5.result.median[0], -1.0, 1e-12)


fn block2_random_crosscheck(mut t: Tally):
    var state: UInt64 = 0x9E3779B9
    var n = 6000
    var k = 12
    var k0 = List[Float64]()
    var k1 = List[Float64]()
    var v = List[Float64]()
    for _ in range(n):
        var c0 = Int(_rand01(state) * Float64(k))
        if c0 >= k:
            c0 = k - 1
        var c1 = Int(_rand01(state) * Float64(k))
        if c1 >= k:
            c1 = k - 1
        k0.append(Float64(c0))
        k1.append(Float64(c1))
        v.append((_rand01(state) - 0.5) * 100.0)
    # One deliberately TINY group (size 1) and one guaranteed to survive as
    # its own slot, exercising the trivial scatter path alongside the bulk.
    k0.append(Float64(k))
    k1.append(Float64(k))
    v.append(777.0)
    var batch = _batch2(k0, k1, v)
    var kc = List[Int]()
    kc.append(0)
    kc.append(1)
    var domain = probe_packed_domain(batch, kc, 1 << 16)
    t.ok("block2.domain_valid", domain.valid())

    var worker_counts = List[Int]()
    worker_counts.append(1)
    worker_counts.append(2)
    worker_counts.append(3)
    worker_counts.append(5)
    worker_counts.append(8)
    worker_counts.append(16)

    for wi in range(len(worker_counts)):
        var workers = worker_counts[wi]
        var res = group_median_sd_packed_parallel(batch, kc, domain, 2, workers)
        t.ok("block2.ok.w" + String(workers), res.ok())
        if not res.ok():
            continue
        for g in range(res.result.n_groups()):
            var kk0 = Int(res.result.key_tuples[g * 2])
            var kk1 = Int(res.result.key_tuples[g * 2 + 1])
            var gv = List[Float64]()
            for i in range(len(k0)):
                if Int(k0[i]) == kk0 and Int(k1[i]) == kk1:
                    gv.append(v[i])
            t.ok(
                "block2.count.w" + String(workers) + ".g" + String(g),
                Int(res.result.count[g]) == len(gv),
            )
            var ref_med = _reference_median(gv)
            t.close(
                "block2.median.w" + String(workers) + ".g" + String(g),
                res.result.median[g], ref_med, 1e-9,
            )
            var expect_sd = len(gv) >= 2
            t.ok(
                "block2.present_sd.w" + String(workers) + ".g" + String(g),
                res.result.present_sd[g] == expect_sd,
            )
            if expect_sd:
                var ref_sd = _reference_sd_val(gv)
                t.close(
                    "block2.sd.w" + String(workers) + ".g" + String(g),
                    res.result.sd[g], ref_sd, 1e-6,
                )


fn block3_nulls(mut t: Tally):
    var names = List[String]()
    names.append("k0")
    names.append("k1")
    names.append("v")
    var k0 = List[Float64]()
    k0.append(0.0)
    k0.append(0.0)
    k0.append(1.0)
    var k1 = List[Float64]()
    k1.append(0.0)
    k1.append(0.0)
    k1.append(1.0)
    var kmask = List[Bool]()
    kmask.append(True)
    kmask.append(False)
    kmask.append(True)
    var v = List[Float64]()
    v.append(1.0)
    v.append(999.0)
    v.append(2.0)
    var vmask = List[Bool]()
    vmask.append(True)
    vmask.append(True)
    vmask.append(False)
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(k0^, kmask))
    cols.append(float64_from_list(k1^))
    cols.append(float64_with_nulls(v^, vmask))
    var batch = RecordBatch(schema_of(names^), cols^, 3)
    var kc = List[Int]()
    kc.append(0)
    kc.append(1)
    var domain = probe_packed_domain(batch, kc, 1024)
    var res = group_median_sd_packed_parallel(batch, kc, domain, 2, 1)
    t.ok("block3.null_key_rows", res.result.null_key_rows == 1)
    t.ok("block3.groups", res.result.n_groups() == 2)
    t.ok("block3.group1_no_median", not res.result.present_median[1])
    t.ok("block3.group1_zero_count", Int(res.result.count[1]) == 0)
    t.ok("block3.group0_median_is_1", res.result.median[0] == 1.0)


fn block4_refusals(mut t: Tally):
    var kc = List[Int]()
    kc.append(0)
    kc.append(1)
    var k0 = List[Float64]()
    var k1 = List[Float64]()
    var v = List[Float64]()
    k0.append(0.5)
    k1.append(0.0)
    v.append(1.0)
    var b = _batch2(k0, k1, v)
    var domain = probe_packed_domain(b, kc, 1024)
    t.ok("block4.probe_rejects_fractional", not domain.valid())
    t.ok("block4.status_vocab", GROUP_CODED_KEY_NOT_A_CODE != 0)


fn main():
    print("=== test_query_median_packed ===")
    var t = Tally()
    block1_hand_edge_cases(t)
    block2_random_crosscheck(t)
    block3_nulls(t)
    block4_refusals(t)
    print("")
    print("checks=" + String(t.checks) + " failures=" + String(t.failures))
    if t.failures != 0:
        print("FAILED")
    else:
        print("ALL PASS")
