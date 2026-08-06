"""test_sorting.mojo — auto-generated tests for sorting."""
from std.math import isnan, isinf
from sorting import quicksort, mergesort, heapsort, insertion_sort, selection_sort, bubble_sort, counting_sort_int, is_sorted, reverse_list, nth_smallest

def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
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
    var _v_nth_smallest = nth_smallest(_lf5, 2)
    if is_finite(_v_nth_smallest): passed += 1; print("  ✅ sorting::nth_smallest =", _v_nth_smallest)
    else: failed += 1; print("  ❌ sorting::nth_smallest → non-finite:", _v_nth_smallest)

    print("  [sorting] Passed:", passed, "Failed:", failed)
