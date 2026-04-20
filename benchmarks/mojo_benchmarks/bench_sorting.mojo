"""bench_sorting.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sorting import quicksort, mergesort, heapsort, insertion_sort, selection_sort, bubble_sort, counting_sort_int, is_sorted, reverse_list, nth_smallest
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_quicksort: Float64 = 0.0
    var _t0_quicksort = perf_counter_ns()
    for _ in range(N):
        var _r_quicksort = quicksort(_lf5)
        _acc_quicksort += Float64(len(_r_quicksort))
    var _t1_quicksort = perf_counter_ns()
    var _ns_quicksort = Float64(_t1_quicksort - _t0_quicksort) / Float64(N)
    print("MOJO_TIMING sorting::quicksort", _ns_quicksort, _acc_quicksort)
    var _acc_mergesort: Float64 = 0.0
    var _t0_mergesort = perf_counter_ns()
    for _ in range(N):
        var _r_mergesort = mergesort(_lf5)
        _acc_mergesort += Float64(len(_r_mergesort))
    var _t1_mergesort = perf_counter_ns()
    var _ns_mergesort = Float64(_t1_mergesort - _t0_mergesort) / Float64(N)
    print("MOJO_TIMING sorting::mergesort", _ns_mergesort, _acc_mergesort)
    var _acc_heapsort: Float64 = 0.0
    var _t0_heapsort = perf_counter_ns()
    for _ in range(N):
        var _r_heapsort = heapsort(_lf5)
        _acc_heapsort += Float64(len(_r_heapsort))
    var _t1_heapsort = perf_counter_ns()
    var _ns_heapsort = Float64(_t1_heapsort - _t0_heapsort) / Float64(N)
    print("MOJO_TIMING sorting::heapsort", _ns_heapsort, _acc_heapsort)
    var _acc_insertion_sort: Float64 = 0.0
    var _t0_insertion_sort = perf_counter_ns()
    for _ in range(N):
        var _r_insertion_sort = insertion_sort(_lf5)
        _acc_insertion_sort += Float64(len(_r_insertion_sort))
    var _t1_insertion_sort = perf_counter_ns()
    var _ns_insertion_sort = Float64(_t1_insertion_sort - _t0_insertion_sort) / Float64(N)
    print("MOJO_TIMING sorting::insertion_sort", _ns_insertion_sort, _acc_insertion_sort)
    var _acc_selection_sort: Float64 = 0.0
    var _t0_selection_sort = perf_counter_ns()
    for _ in range(N):
        var _r_selection_sort = selection_sort(_lf5)
        _acc_selection_sort += Float64(len(_r_selection_sort))
    var _t1_selection_sort = perf_counter_ns()
    var _ns_selection_sort = Float64(_t1_selection_sort - _t0_selection_sort) / Float64(N)
    print("MOJO_TIMING sorting::selection_sort", _ns_selection_sort, _acc_selection_sort)
    var _acc_bubble_sort: Float64 = 0.0
    var _t0_bubble_sort = perf_counter_ns()
    for _ in range(N):
        var _r_bubble_sort = bubble_sort(_lf5)
        _acc_bubble_sort += Float64(len(_r_bubble_sort))
    var _t1_bubble_sort = perf_counter_ns()
    var _ns_bubble_sort = Float64(_t1_bubble_sort - _t0_bubble_sort) / Float64(N)
    print("MOJO_TIMING sorting::bubble_sort", _ns_bubble_sort, _acc_bubble_sort)
    var _acc_counting_sort_int: Float64 = 0.0
    var _t0_counting_sort_int = perf_counter_ns()
    for _ in range(N):
        var _r_counting_sort_int = counting_sort_int(_li5)
        _acc_counting_sort_int += Float64(len(_r_counting_sort_int))
    var _t1_counting_sort_int = perf_counter_ns()
    var _ns_counting_sort_int = Float64(_t1_counting_sort_int - _t0_counting_sort_int) / Float64(N)
    print("MOJO_TIMING sorting::counting_sort_int", _ns_counting_sort_int, _acc_counting_sort_int)
    var _acc_is_sorted: Float64 = 0.0
    var _t0_is_sorted = perf_counter_ns()
    for _ in range(N):
        _acc_is_sorted += Float64(is_sorted(_lf5))
    var _t1_is_sorted = perf_counter_ns()
    var _ns_is_sorted = Float64(_t1_is_sorted - _t0_is_sorted) / Float64(N)
    print("MOJO_TIMING sorting::is_sorted", _ns_is_sorted, _acc_is_sorted)
    var _acc_reverse_list: Float64 = 0.0
    var _t0_reverse_list = perf_counter_ns()
    for _ in range(N):
        var _r_reverse_list = reverse_list(_lf5)
        _acc_reverse_list += Float64(len(_r_reverse_list))
    var _t1_reverse_list = perf_counter_ns()
    var _ns_reverse_list = Float64(_t1_reverse_list - _t0_reverse_list) / Float64(N)
    print("MOJO_TIMING sorting::reverse_list", _ns_reverse_list, _acc_reverse_list)
    var _acc_nth_smallest: Float64 = 0.0
    var _t0_nth_smallest = perf_counter_ns()
    for _ in range(N):
        _acc_nth_smallest += nth_smallest(_lf5, 5)
    var _t1_nth_smallest = perf_counter_ns()
    var _ns_nth_smallest = Float64(_t1_nth_smallest - _t0_nth_smallest) / Float64(N)
    print("MOJO_TIMING sorting::nth_smallest", _ns_nth_smallest, _acc_nth_smallest)
