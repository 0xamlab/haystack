"""test_columnar_sort_radix.mojo — known-value tests for the Float64 LSD radix sort.

Hand-written. A sort is easy to test badly: a sortedness scan passes for an implementation that
drops half the input and duplicates the rest, so every case here checks the MULTISET as well as
the order, and the cases are chosen to be the ones a radix over IEEE-754 keys actually gets wrong.

  * signed zero, which has two bit patterns that compare equal
  * denormals and +/-DBL_MAX, the extremes of the exponent field
  * negatives, whose magnitude order is reversed under a naive unsigned radix
  * an all-identical input, which makes every pass skippable and takes the early-exit path
  * a parallel run whose worker count does not divide n, which is where band arithmetic goes wrong
  * the parallel arm at a size past `RADIX_PARALLEL_MIN_N` with several ACTIVE passes, because the
    per-worker histogram is only valid for the first pass and reusing it for the rest was a real
    bug caught by exactly this shape
"""
from columnar.sort_radix import (
    RADIX_PARALLEL_MIN_N,
    radix_sort_f64,
    radix_sort_f64_auto,
    radix_sort_f64_parallel,
    radix_sort_f64_report,
    radix_sort_f64_roundtrip_ok,
)


def _sorted_ok(data: List[Float64]) -> Bool:
    for i in range(1, len(data)):
        if data[i] < data[i - 1]:
            return False
    return True


@fieldwise_init
struct Fingerprint(Copyable, Movable):
    """Two permutation invariants over a buffer's raw bit patterns."""

    var xor: UInt64
    var wrapping_sum: UInt64


def _fingerprint(data: List[Float64]) -> Fingerprint:
    """xor and wrapping sum of the raw bits: two permutation invariants."""
    var x: UInt64 = 0
    var s: UInt64 = 0
    for i in range(len(data)):
        var b = data[i].to_bits[DType.uint64]()
        x ^= b
        s = s + b
    return Fingerprint(x, s)


def _same_multiset(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return False
    var fa = _fingerprint(a)
    var fb = _fingerprint(b)
    return fa.xor == fb.xor and fa.wrapping_sum == fb.wrapping_sum


def _xorshift(mut s: UInt64) -> UInt64:
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


def _random_doubles(n: Int, seed: UInt64) -> List[Float64]:
    var out = List[Float64](unsafe_uninit_length=n)
    var s = seed
    for i in range(n):
        var r = _xorshift(s)
        var mag = Float64(r >> 11) * (1.0 / 9007199254740992.0)
        out[i] = -mag if (r & 1) == 1 else mag
    return out^


def main():
    var passed = 0
    var failed = 0

    # ── the key transform is a bijection ─────────────────────────────────────
    var edge = List[Float64]()
    edge.append(0.0)
    edge.append(-0.0)
    edge.append(1.0)
    edge.append(-1.0)
    edge.append(4.9406564584124654e-324)
    edge.append(-4.9406564584124654e-324)
    edge.append(2.2250738585072014e-308)
    edge.append(1.7976931348623157e308)
    edge.append(-1.7976931348623157e308)
    var bijection = True
    for i in range(len(edge)):
        if not radix_sort_f64_roundtrip_ok(edge[i]):
            bijection = False
    if bijection:
        passed += 1
        print("  ✅ unkey(key(x)) is bit-identical on 0, -0, denormals and +/-DBL_MAX")
    else:
        failed += 1
        print("  ❌ the key transform is not a bijection on the edge values")

    # ── the edge values themselves sort into total order ─────────────────────
    var sorted_edge = radix_sort_f64(edge)
    var edge_ok = (
        _sorted_ok(sorted_edge)
        and _same_multiset(sorted_edge, edge)
        and sorted_edge[0] == -1.7976931348623157e308
        and sorted_edge[len(sorted_edge) - 1] == 1.7976931348623157e308
    )
    # -0.0 must precede +0.0: IEEE total order, and the property a comparison sort cannot give.
    var minus_zero_first = False
    for i in range(len(sorted_edge) - 1):
        if (
            sorted_edge[i].to_bits[DType.uint64]() == 0x8000000000000000
            and sorted_edge[i + 1].to_bits[DType.uint64]() == 0
        ):
            minus_zero_first = True
    if edge_ok and minus_zero_first:
        print("  ✅ 9 edge values sort into IEEE total order, -0.0 immediately before +0.0")
        passed += 1
    else:
        failed += 1
        print("  ❌ edge ordering wrong: sorted =", _sorted_ok(sorted_edge),
              " multiset =", _same_multiset(sorted_edge, edge),
              " -0 before +0 =", minus_zero_first)

    # ── empty and single ─────────────────────────────────────────────────────
    var nothing = List[Float64]()
    var one = List[Float64]()
    one.append(7.5)
    if len(radix_sort_f64(nothing)) == 0 and radix_sort_f64(one)[0] == 7.5:
        passed += 1
        print("  ✅ sorting nothing gives nothing; sorting one value gives that value")
    else:
        failed += 1
        print("  ❌ the empty or single-element case is wrong")

    # ── every element identical: all eight passes skip ───────────────────────
    var same = List[Float64](length=1000, fill=3.25)
    var same_out = radix_sort_f64(same)
    var same_report = radix_sort_f64_report(same)
    var same_ok = _sorted_ok(same_out) and _same_multiset(same_out, same)
    for i in range(len(same_out)):
        if same_out[i] != 3.25:
            same_ok = False
    if same_ok and same_report.passes_run == 0:
        passed += 1
        print("  ✅ 1000 copies of one value: 0 of 8 passes run, output is the same multiset")
    else:
        failed += 1
        print("  ❌ identical input mishandled; passes_run =", same_report.passes_run)

    # ── random, sequential ───────────────────────────────────────────────────
    var rnd = _random_doubles(5000, 12345)
    var rnd_out = radix_sort_f64(rnd)
    if _sorted_ok(rnd_out) and _same_multiset(rnd_out, rnd):
        passed += 1
        print("  ✅ 5000 random doubles sort, and the output is a permutation of the input")
    else:
        failed += 1
        print("  ❌ the sequential random case is wrong")

    # ── parallel agrees with sequential BIT FOR BIT, several worker counts ───
    # 3, 5 and 7 do not divide 5000, which is where band arithmetic goes wrong if it is going to.
    var parallel_identical = True
    var counts = List[Int]()
    counts.append(2)
    counts.append(3)
    counts.append(5)
    counts.append(7)
    counts.append(16)
    for ci in range(len(counts)):
        var par = radix_sort_f64_parallel(rnd, counts[ci])
        if len(par) != len(rnd_out):
            parallel_identical = False
        else:
            for i in range(len(par)):
                if par[i].to_bits[DType.uint64]() != rnd_out[i].to_bits[DType.uint64]():
                    parallel_identical = False
    if parallel_identical:
        passed += 1
        print("  ✅ 2, 3, 5, 7 and 16 workers all give bit-identical output to the sequential arm")
    else:
        failed += 1
        print("  ❌ the parallel arm's output depends on the worker count")

    # ── the parallel arm past its threshold, with many active passes ─────────
    # The per-worker histogram built during keying is valid for the FIRST scatter only; every
    # scatter permutes which elements sit in a worker's band. Reusing it left 28% of a 1e6 array
    # out of order. This case is large enough to take the real parallel path and random enough
    # that all eight passes are active, which is the only shape that catches it.
    var big = _random_doubles(RADIX_PARALLEL_MIN_N + 1234, 987654321)
    var big_seq = radix_sort_f64(big)
    var big_par = radix_sort_f64_parallel(big, 16)
    var big_auto = radix_sort_f64_auto(big)
    var big_report = radix_sort_f64_report(big)
    var big_ok = (
        _sorted_ok(big_par)
        and _same_multiset(big_par, big)
        and _sorted_ok(big_auto)
        and _same_multiset(big_auto, big)
        and len(big_par) == len(big_seq)
    )
    if big_ok:
        for i in range(len(big_par)):
            if big_par[i].to_bits[DType.uint64]() != big_seq[i].to_bits[DType.uint64]():
                big_ok = False
            if big_auto[i].to_bits[DType.uint64]() != big_seq[i].to_bits[DType.uint64]():
                big_ok = False
    if big_ok and big_report.passes_run >= 4:
        passed += 1
        print(
            "  ✅ past the parallel threshold with",
            big_report.passes_run,
            "of 8 passes active, 16 workers match the sequential arm bit for bit",
        )
    else:
        failed += 1
        print("  ❌ the multi-pass parallel path disagrees; passes =", big_report.passes_run)

    # ── already-sorted and reverse-sorted are the same work ──────────────────
    # A radix makes no comparisons, so input order must not change the answer. This is the
    # property the insertion sort in `query.executor` does not have.
    var ascending = radix_sort_f64(rnd)
    var descending = List[Float64](unsafe_uninit_length=len(ascending))
    for i in range(len(ascending)):
        descending[i] = ascending[len(ascending) - 1 - i]
    var from_sorted = radix_sort_f64(ascending)
    var from_reverse = radix_sort_f64(descending)
    var order_free = len(from_sorted) == len(from_reverse)
    if order_free:
        for i in range(len(from_sorted)):
            if from_sorted[i] != from_reverse[i] or from_sorted[i] != rnd_out[i]:
                order_free = False
    if order_free:
        passed += 1
        print("  ✅ sorted and reverse-sorted input give the identical result, element for element")
    else:
        failed += 1
        print("  ❌ the result depends on the input order")

    print("  [columnar.sort_radix] Passed:", passed, "Failed:", failed)
