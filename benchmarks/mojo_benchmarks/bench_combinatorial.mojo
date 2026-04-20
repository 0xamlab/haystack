"""bench_combinatorial.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from combinatorial import knapsack_01, knapsack_01_value, tsp_greedy, tsp_tour_length, bin_packing_first_fit, bin_packing_first_fit_decreasing, assignment_greedy, max_subarray_sum, longest_increasing_subsequence, coin_change
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

    var _acc_knapsack_01: Float64 = 0.0
    var _t0_knapsack_01 = perf_counter_ns()
    for _ in range(N):
        var _r_knapsack_01 = knapsack_01(_li5, _li5, 5)
        _acc_knapsack_01 += Float64(len(_r_knapsack_01))
    var _t1_knapsack_01 = perf_counter_ns()
    var _ns_knapsack_01 = Float64(_t1_knapsack_01 - _t0_knapsack_01) / Float64(N)
    print("MOJO_TIMING combinatorial::knapsack_01", _ns_knapsack_01, _acc_knapsack_01)
    var _acc_knapsack_01_value: Float64 = 0.0
    var _t0_knapsack_01_value = perf_counter_ns()
    for _ in range(N):
        _acc_knapsack_01_value += Float64(knapsack_01_value(_li5, _li5, 5))
    var _t1_knapsack_01_value = perf_counter_ns()
    var _ns_knapsack_01_value = Float64(_t1_knapsack_01_value - _t0_knapsack_01_value) / Float64(N)
    print("MOJO_TIMING combinatorial::knapsack_01_value", _ns_knapsack_01_value, _acc_knapsack_01_value)
    var _acc_tsp_greedy: Float64 = 0.0
    var _t0_tsp_greedy = perf_counter_ns()
    for _ in range(N):
        var _r_tsp_greedy = tsp_greedy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_tsp_greedy += Float64(len(_r_tsp_greedy))
    var _t1_tsp_greedy = perf_counter_ns()
    var _ns_tsp_greedy = Float64(_t1_tsp_greedy - _t0_tsp_greedy) / Float64(N)
    print("MOJO_TIMING combinatorial::tsp_greedy", _ns_tsp_greedy, _acc_tsp_greedy)
    var _acc_tsp_tour_length: Float64 = 0.0
    var _t0_tsp_tour_length = perf_counter_ns()
    for _ in range(N):
        _acc_tsp_tour_length += tsp_tour_length([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5)
    var _t1_tsp_tour_length = perf_counter_ns()
    var _ns_tsp_tour_length = Float64(_t1_tsp_tour_length - _t0_tsp_tour_length) / Float64(N)
    print("MOJO_TIMING combinatorial::tsp_tour_length", _ns_tsp_tour_length, _acc_tsp_tour_length)
    var _acc_bin_packing_first_fit: Float64 = 0.0
    var _t0_bin_packing_first_fit = perf_counter_ns()
    for _ in range(N):
        _acc_bin_packing_first_fit += Float64(bin_packing_first_fit(_lf5, 0.5))
    var _t1_bin_packing_first_fit = perf_counter_ns()
    var _ns_bin_packing_first_fit = Float64(_t1_bin_packing_first_fit - _t0_bin_packing_first_fit) / Float64(N)
    print("MOJO_TIMING combinatorial::bin_packing_first_fit", _ns_bin_packing_first_fit, _acc_bin_packing_first_fit)
    var _acc_bin_packing_first_fit_decreasing: Float64 = 0.0
    var _t0_bin_packing_first_fit_decreasing = perf_counter_ns()
    for _ in range(N):
        _acc_bin_packing_first_fit_decreasing += Float64(bin_packing_first_fit_decreasing(_lf5, 0.5))
    var _t1_bin_packing_first_fit_decreasing = perf_counter_ns()
    var _ns_bin_packing_first_fit_decreasing = Float64(_t1_bin_packing_first_fit_decreasing - _t0_bin_packing_first_fit_decreasing) / Float64(N)
    print("MOJO_TIMING combinatorial::bin_packing_first_fit_decreasing", _ns_bin_packing_first_fit_decreasing, _acc_bin_packing_first_fit_decreasing)
    var _acc_assignment_greedy: Float64 = 0.0
    var _t0_assignment_greedy = perf_counter_ns()
    for _ in range(N):
        var _r_assignment_greedy = assignment_greedy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_assignment_greedy += Float64(len(_r_assignment_greedy))
    var _t1_assignment_greedy = perf_counter_ns()
    var _ns_assignment_greedy = Float64(_t1_assignment_greedy - _t0_assignment_greedy) / Float64(N)
    print("MOJO_TIMING combinatorial::assignment_greedy", _ns_assignment_greedy, _acc_assignment_greedy)
    var _acc_max_subarray_sum: Float64 = 0.0
    var _t0_max_subarray_sum = perf_counter_ns()
    for _ in range(N):
        _acc_max_subarray_sum += max_subarray_sum(_lf5)
    var _t1_max_subarray_sum = perf_counter_ns()
    var _ns_max_subarray_sum = Float64(_t1_max_subarray_sum - _t0_max_subarray_sum) / Float64(N)
    print("MOJO_TIMING combinatorial::max_subarray_sum", _ns_max_subarray_sum, _acc_max_subarray_sum)
    var _acc_longest_increasing_subsequence: Float64 = 0.0
    var _t0_longest_increasing_subsequence = perf_counter_ns()
    for _ in range(N):
        _acc_longest_increasing_subsequence += Float64(longest_increasing_subsequence(_lf5))
    var _t1_longest_increasing_subsequence = perf_counter_ns()
    var _ns_longest_increasing_subsequence = Float64(_t1_longest_increasing_subsequence - _t0_longest_increasing_subsequence) / Float64(N)
    print("MOJO_TIMING combinatorial::longest_increasing_subsequence", _ns_longest_increasing_subsequence, _acc_longest_increasing_subsequence)
    var _acc_coin_change: Float64 = 0.0
    var _t0_coin_change = perf_counter_ns()
    for _ in range(N):
        _acc_coin_change += Float64(coin_change(_li5, 5))
    var _t1_coin_change = perf_counter_ns()
    var _ns_coin_change = Float64(_t1_coin_change - _t0_coin_change) / Float64(N)
    print("MOJO_TIMING combinatorial::coin_change", _ns_coin_change, _acc_coin_change)
