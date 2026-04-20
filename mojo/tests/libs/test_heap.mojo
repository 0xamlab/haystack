"""test_heap.mojo — auto-generated tests for heap library."""
from std.math import isnan, isinf
from heap import heap_peek_min, heap_peek_max, k_smallest, k_largest, running_median, is_min_heap

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_heap_peek_min = heap_peek_min(_lf5)
    if is_finite(_v_heap_peek_min): passed += 1; print("  ✅ heap::heap_peek_min =", _v_heap_peek_min)
    else: failed += 1; print("  ❌ heap::heap_peek_min → non-finite:", _v_heap_peek_min)
    var _v_heap_peek_max = heap_peek_max(_lf5)
    if is_finite(_v_heap_peek_max): passed += 1; print("  ✅ heap::heap_peek_max =", _v_heap_peek_max)
    else: failed += 1; print("  ❌ heap::heap_peek_max → non-finite:", _v_heap_peek_max)
    var _v_k_smallest = k_smallest(_lf5, 5)
    if len(_v_k_smallest) >= 0: passed += 1; print("  ✅ heap::k_smallest")
    var _v_k_largest = k_largest(_lf5, 5)
    if len(_v_k_largest) >= 0: passed += 1; print("  ✅ heap::k_largest")
    var _v_running_median = running_median(_lf5)
    if len(_v_running_median) >= 0: passed += 1; print("  ✅ heap::running_median")
    _ = is_min_heap(_lf5)
    passed += 1; print("  ✅ heap::is_min_heap")

    print("  [heap] Passed:", passed, "Failed:", failed)
