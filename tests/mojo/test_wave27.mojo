"""Tests for Wave 27 — Reservoir Sampling, Probabilistic Sketches, Interval Arithmetic."""

from reservoir import (
    reservoir_sample,
    weighted_reservoir_sample,
    reservoir_sample_indices,
    bootstrap_sample,
    systematic_sample,
    sample_with_replacement,
    sample_without_replacement,
)
from sketch import (
    CountMinSketch,
    create_cms,
    cms_add,
    cms_query,
    cms_hash,
    HyperLogLog,
    create_hll,
    hll_add,
    hll_count,
    hll_hash,
    leading_zeros,
)
from interval import (
    Interval,
    interval,
    empty_interval,
    interval_add,
    interval_sub,
    interval_mul,
    interval_div,
    interval_contains,
    interval_overlaps,
    interval_intersection,
    interval_union_hull,
    interval_width,
    interval_midpoint,
    interval_radius,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Reservoir Tests ──────────────────────────────────────────────────────────


def test_reservoir() raises:
    print("== Reservoir Tests ==")
    var passed = 0

    # Build test data: [1.0, 2.0, ..., 20.0]
    var data = List[Float64]()
    for i in range(1, 21):
        data.append(Float64(i))

    # 1. reservoir_sample length == k
    var s1 = reservoir_sample(data, 5)
    _assert_eq(len(s1), 5, "reservoir_sample length == 5")
    passed += 1

    # 2. reservoir_sample: all values exist in original
    var all_in = True
    for i in range(len(s1)):
        var found = False
        for j in range(len(data)):
            if s1[i] == data[j]:
                found = True
                break
        if not found:
            all_in = False
            break
    _assert(all_in, "reservoir_sample values in original data")
    passed += 1

    # 3. reservoir_sample with k >= n returns all
    var s_all = reservoir_sample(data, 100)
    _assert_eq(len(s_all), 20, "reservoir_sample k>=n returns all")
    passed += 1

    # 4. reservoir_sample_indices: 10 unique indices in [0, 100)
    var idx = reservoir_sample_indices(100, 10)
    _assert_eq(len(idx), 10, "reservoir_sample_indices length == 10")
    passed += 1

    # 5. All indices in valid range
    var all_valid = True
    for i in range(len(idx)):
        if idx[i] < 0 or idx[i] >= 100:
            all_valid = False
            break
    _assert(all_valid, "reservoir_sample_indices all in [0,100)")
    passed += 1

    # 6. Indices are unique
    var unique = True
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            if idx[i] == idx[j]:
                unique = False
                break
        if not unique:
            break
    _assert(unique, "reservoir_sample_indices all unique")
    passed += 1

    # 7. bootstrap_sample: length == len(data)
    var bs = bootstrap_sample(data)
    _assert_eq(len(bs), len(data), "bootstrap_sample length == len(data)")
    passed += 1

    # 8. bootstrap values from original
    var bs_valid = True
    for i in range(len(bs)):
        var found = False
        for j in range(len(data)):
            if bs[i] == data[j]:
                found = True
                break
        if not found:
            bs_valid = False
            break
    _assert(bs_valid, "bootstrap_sample values from original")
    passed += 1

    # 9. systematic_sample: length == k
    var ss = systematic_sample(data, 5)
    _assert_eq(len(ss), 5, "systematic_sample length == 5")
    passed += 1

    # 10. systematic_sample values from original
    var ss_valid = True
    for i in range(len(ss)):
        var found = False
        for j in range(len(data)):
            if ss[i] == data[j]:
                found = True
                break
        if not found:
            ss_valid = False
            break
    _assert(ss_valid, "systematic_sample values from original")
    passed += 1

    # 11. sample_with_replacement: length == 20
    var swr = sample_with_replacement(data, 20)
    _assert_eq(len(swr), 20, "sample_with_replacement length == 20")
    passed += 1

    # 12. sample_with_replacement values from original
    var swr_valid = True
    for i in range(len(swr)):
        var found = False
        for j in range(len(data)):
            if swr[i] == data[j]:
                found = True
                break
        if not found:
            swr_valid = False
            break
    _assert(swr_valid, "sample_with_replacement values from original")
    passed += 1

    # 13. sample_without_replacement: length == 5
    var swor = sample_without_replacement(data, 5)
    _assert_eq(len(swor), 5, "sample_without_replacement length == 5")
    passed += 1

    # 14. sample_without_replacement: all unique
    var swor_unique = True
    for i in range(len(swor)):
        for j in range(i + 1, len(swor)):
            if swor[i] == swor[j]:
                swor_unique = False
                break
        if not swor_unique:
            break
    _assert(swor_unique, "sample_without_replacement all unique")
    passed += 1

    # 15. sample_without_replacement(data, len(data)): contains all elements
    var swor_full = sample_without_replacement(data, len(data))
    _assert_eq(len(swor_full), len(data), "sample_without_replacement full length")
    passed += 1

    # 16. Verify all original elements present in full sample
    var all_present = True
    for i in range(len(data)):
        var found = False
        for j in range(len(swor_full)):
            if data[i] == swor_full[j]:
                found = True
                break
        if not found:
            all_present = False
            break
    _assert(all_present, "sample_without_replacement full contains all elements")
    passed += 1

    # 17. weighted_reservoir_sample: length == k
    var weights = List[Float64]()
    for i in range(len(data)):
        weights.append(1.0)
    var ws = weighted_reservoir_sample(data, weights, 5)
    _assert_eq(len(ws), 5, "weighted_reservoir_sample length == 5")
    passed += 1

    # 18. weighted_reservoir_sample values from original
    var ws_valid = True
    for i in range(len(ws)):
        var found = False
        for j in range(len(data)):
            if ws[i] == data[j]:
                found = True
                break
        if not found:
            ws_valid = False
            break
    _assert(ws_valid, "weighted_reservoir_sample values from original")
    passed += 1

    print("  Reservoir: " + String(passed) + " passed")


# ── Sketch Tests ─────────────────────────────────────────────────────────────


def test_sketch() raises:
    print("== Sketch Tests ==")
    var passed = 0

    # 1. create_cms: width=100, depth=5
    var cms = create_cms(100, 5)
    _assert_eq(cms.width, 100, "cms width == 100")
    passed += 1

    # 2. cms depth
    _assert_eq(cms.depth, 5, "cms depth == 5")
    passed += 1

    # 3. cms_add then query — never underestimates
    cms_add(cms, 42, 7)
    var q1 = cms_query(cms, 42)
    _assert(q1 >= 7, "cms_query >= 7 for item 42")
    passed += 1

    # 4. Add same item 10 times → query >= 10
    var cms2 = create_cms(200, 5)
    for _ in range(10):
        cms_add(cms2, 99)
    var q2 = cms_query(cms2, 99)
    _assert(q2 >= 10, "cms_query >= 10 after 10 adds")
    passed += 1

    # 5. Query non-added item → 0 (or small false positive)
    var q3 = cms_query(cms2, 12345)
    _assert(q3 >= 0, "cms_query non-added >= 0")
    passed += 1

    # 6. Fresh CMS query is 0
    var cms3 = create_cms(100, 5)
    var q4 = cms_query(cms3, 1)
    _assert_eq(q4, 0, "fresh cms query == 0")
    passed += 1

    # 7. cms_hash returns valid range
    var h = cms_hash(42, 7, 100)
    _assert(h >= 0 and h < 100, "cms_hash in [0, 100)")
    passed += 1

    # 8. create_hll(10): m == 1024
    var hll = create_hll(10)
    _assert_eq(hll.m, 1024, "hll m == 1024")
    passed += 1

    # 9. hll precision
    _assert_eq(hll.p, 10, "hll p == 10")
    passed += 1

    # 10. hll_add many distinct items → count within 30% of true count
    for i in range(1000):
        hll_add(hll, i)
    var est = hll_count(hll)
    var ratio = est / 1000.0
    _assert(ratio > 0.7 and ratio < 1.3, "hll_count within 30% of 1000 | got " + String(est))
    passed += 1

    # 11. hll_add duplicates → count doesn't grow much
    var hll2 = create_hll(10)
    for _ in range(1000):
        hll_add(hll2, 42)  # Same item 1000 times
    var est2 = hll_count(hll2)
    _assert(est2 < 10.0, "hll duplicates count < 10 | got " + String(est2))
    passed += 1

    # 12. leading_zeros(0, 32) == 32
    _assert_eq(leading_zeros(0, 32), 32, "leading_zeros(0,32) == 32")
    passed += 1

    # 13. leading_zeros(1, 32) == 31
    _assert_eq(leading_zeros(1, 32), 31, "leading_zeros(1,32) == 31")
    passed += 1

    # 14. leading_zeros for power of 2
    _assert_eq(leading_zeros(8, 32), 28, "leading_zeros(8,32) == 28")
    passed += 1

    # 15. hll_hash produces non-negative values
    var hh = hll_hash(42)
    _assert(hh >= 0, "hll_hash(42) >= 0")
    passed += 1

    print("  Sketch: " + String(passed) + " passed")


# ── Interval Tests ───────────────────────────────────────────────────────────


def test_interval() raises:
    print("== Interval Tests ==")
    var passed = 0

    # 1. interval(1, 3) — lo=1, hi=3
    var iv1 = interval(1.0, 3.0)
    _assert_close(iv1.lo, 1.0, 1e-12, "interval(1,3) lo == 1")
    passed += 1

    # 2. hi == 3
    _assert_close(iv1.hi, 3.0, 1e-12, "interval(1,3) hi == 3")
    passed += 1

    # 3. not empty
    _assert(not iv1.empty, "interval(1,3) not empty")
    passed += 1

    # 4. interval(5, 2) — empty
    var iv_empty = interval(5.0, 2.0)
    _assert(iv_empty.empty, "interval(5,2) is empty")
    passed += 1

    # 5. interval_add([1,3], [2,4]) == [3,7]
    var a1 = interval(1.0, 3.0)
    var b1 = interval(2.0, 4.0)
    var sum1 = interval_add(a1, b1)
    _assert_close(sum1.lo, 3.0, 1e-12, "interval_add lo == 3")
    passed += 1

    # 6.
    _assert_close(sum1.hi, 7.0, 1e-12, "interval_add hi == 7")
    passed += 1

    # 7. interval_sub([1,3], [2,4]) == [-3,1]
    var sub1 = interval_sub(a1, b1)
    _assert_close(sub1.lo, -3.0, 1e-12, "interval_sub lo == -3")
    passed += 1

    # 8.
    _assert_close(sub1.hi, 1.0, 1e-12, "interval_sub hi == 1")
    passed += 1

    # 9. interval_mul([1,2], [3,4]) == [3,8]
    var a2 = interval(1.0, 2.0)
    var b2 = interval(3.0, 4.0)
    var mul1 = interval_mul(a2, b2)
    _assert_close(mul1.lo, 3.0, 1e-12, "interval_mul [1,2]*[3,4] lo == 3")
    passed += 1

    # 10.
    _assert_close(mul1.hi, 8.0, 1e-12, "interval_mul [1,2]*[3,4] hi == 8")
    passed += 1

    # 11. interval_mul([-1,1], [2,3]) — includes negative products
    var a3 = interval(-1.0, 1.0)
    var b3 = interval(2.0, 3.0)
    var mul2 = interval_mul(a3, b3)
    _assert_close(mul2.lo, -3.0, 1e-12, "interval_mul [-1,1]*[2,3] lo == -3")
    passed += 1

    # 12.
    _assert_close(mul2.hi, 3.0, 1e-12, "interval_mul [-1,1]*[2,3] hi == 3")
    passed += 1

    # 13. interval_contains([1,5], 3.0) == True
    var iv2 = interval(1.0, 5.0)
    _assert(interval_contains(iv2, 3.0), "interval_contains(3.0) == True")
    passed += 1

    # 14. interval_contains([1,5], 6.0) == False
    _assert(not interval_contains(iv2, 6.0), "interval_contains(6.0) == False")
    passed += 1

    # 15. interval_contains at boundaries
    _assert(interval_contains(iv2, 1.0), "interval_contains(1.0) == True (boundary)")
    passed += 1

    # 16. interval_contains at upper boundary
    _assert(interval_contains(iv2, 5.0), "interval_contains(5.0) == True (boundary)")
    passed += 1

    # 17. interval_overlaps([1,3], [2,5]) == True
    var ov_a = interval(1.0, 3.0)
    var ov_b = interval(2.0, 5.0)
    _assert(interval_overlaps(ov_a, ov_b), "overlaps([1,3],[2,5]) == True")
    passed += 1

    # 18. interval_overlaps([1,2], [3,4]) == False
    var no_ov_a = interval(1.0, 2.0)
    var no_ov_b = interval(3.0, 4.0)
    _assert(not interval_overlaps(no_ov_a, no_ov_b), "overlaps([1,2],[3,4]) == False")
    passed += 1

    # 19. interval_intersection([1,3], [2,5]) == [2,3]
    var isect = interval_intersection(ov_a, ov_b)
    _assert_close(isect.lo, 2.0, 1e-12, "intersection lo == 2")
    passed += 1

    # 20.
    _assert_close(isect.hi, 3.0, 1e-12, "intersection hi == 3")
    passed += 1

    # 21. Non-overlapping intersection is empty
    var isect2 = interval_intersection(no_ov_a, no_ov_b)
    _assert(isect2.empty, "intersection of non-overlapping is empty")
    passed += 1

    # 22. interval_union_hull([1,2], [4,5]) == [1,5]
    var hull_a = interval(1.0, 2.0)
    var hull_b = interval(4.0, 5.0)
    var hull = interval_union_hull(hull_a, hull_b)
    _assert_close(hull.lo, 1.0, 1e-12, "union_hull lo == 1")
    passed += 1

    # 23.
    _assert_close(hull.hi, 5.0, 1e-12, "union_hull hi == 5")
    passed += 1

    # 24. interval_width([1,5]) == 4.0
    _assert_close(interval_width(iv2), 4.0, 1e-12, "interval_width == 4")
    passed += 1

    # 25. interval_midpoint([1,5]) == 3.0
    _assert_close(interval_midpoint(iv2), 3.0, 1e-12, "interval_midpoint == 3")
    passed += 1

    # 26. interval_radius([1,5]) == 2.0
    _assert_close(interval_radius(iv2), 2.0, 1e-12, "interval_radius == 2")
    passed += 1

    # 27. empty_interval width == 0
    var ei = empty_interval()
    _assert_close(interval_width(ei), 0.0, 1e-12, "empty interval width == 0")
    passed += 1

    # 28. interval_div([2,6], [1,3]) == [2/3, 6]
    var div_a = interval(2.0, 6.0)
    var div_b = interval(1.0, 3.0)
    var dv = interval_div(div_a, div_b)
    _assert_close(dv.lo, 2.0 / 3.0, 1e-10, "interval_div lo == 2/3")
    passed += 1

    # 29.
    _assert_close(dv.hi, 6.0, 1e-12, "interval_div hi == 6")
    passed += 1

    print("  Interval: " + String(passed) + " passed")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 27 Tests ===")
    test_reservoir()
    test_sketch()
    test_interval()
    print("=== All Wave 27 tests passed! ===")
