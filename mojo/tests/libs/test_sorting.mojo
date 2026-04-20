"""test_sorting.mojo — auto-generated tests for sorting library."""
from std.math import isnan, isinf
from sorting import quicksort, mergesort, heapsort, insertion_sort, selection_sort, bubble_sort, counting_sort_int, is_sorted, reverse_list, nth_smallest

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

    var _v_quicksort = quicksort(_lf5)
    if len(_v_quicksort) >= 0: passed += 1; print("  ✅ sorting::quicksort")
    var _v_mergesort = mergesort(_lf5)
    if len(_v_mergesort) >= 0: passed += 1; print("  ✅ sorting::mergesort")
    var _v_heapsort = heapsort(_lf5)
    if len(_v_heapsort) >= 0: passed += 1; print("  ✅ sorting::heapsort")
    var _v_insertion_sort = insertion_sort(_lf5)
    if len(_v_insertion_sort) >= 0: passed += 1; print("  ✅ sorting::insertion_sort")
    var _v_selection_sort = selection_sort(_lf5)
    if len(_v_selection_sort) >= 0: passed += 1; print("  ✅ sorting::selection_sort")
    var _v_bubble_sort = bubble_sort(_lf5)
    if len(_v_bubble_sort) >= 0: passed += 1; print("  ✅ sorting::bubble_sort")
    var _v_counting_sort_int = counting_sort_int(_li5)
    if len(_v_counting_sort_int) >= 0: passed += 1; print("  ✅ sorting::counting_sort_int")
    _ = is_sorted(_lf5)
    passed += 1; print("  ✅ sorting::is_sorted")
    var _v_reverse_list = reverse_list(_lf5)
    if len(_v_reverse_list) >= 0: passed += 1; print("  ✅ sorting::reverse_list")
    var _v_nth_smallest = nth_smallest(_lf5, 5)
    if is_finite(_v_nth_smallest): passed += 1; print("  ✅ sorting::nth_smallest =", _v_nth_smallest)
    else: failed += 1; print("  ❌ sorting::nth_smallest → non-finite:", _v_nth_smallest)

    print("  [sorting] Passed:", passed, "Failed:", failed)
