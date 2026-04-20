"""bench_stats.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stats import compute_mean, compute_variance, pctile, count_below_zero, ins_sort, ilog2, part3, fast_sort
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

    var _acc_compute_mean: Float64 = 0.0
    var _t0_compute_mean = perf_counter_ns()
    for _ in range(N):
        _acc_compute_mean += compute_mean(_lf5, 5)
    var _t1_compute_mean = perf_counter_ns()
    var _ns_compute_mean = Float64(_t1_compute_mean - _t0_compute_mean) / Float64(N)
    print("MOJO_TIMING stats::compute_mean", _ns_compute_mean, _acc_compute_mean)
    var _acc_compute_variance: Float64 = 0.0
    var _t0_compute_variance = perf_counter_ns()
    for _ in range(N):
        _acc_compute_variance += compute_variance(_lf5, 5, 0.5)
    var _t1_compute_variance = perf_counter_ns()
    var _ns_compute_variance = Float64(_t1_compute_variance - _t0_compute_variance) / Float64(N)
    print("MOJO_TIMING stats::compute_variance", _ns_compute_variance, _acc_compute_variance)
    var _acc_pctile: Float64 = 0.0
    var _t0_pctile = perf_counter_ns()
    for _ in range(N):
        _acc_pctile += pctile(_lf5, 5, 5)
    var _t1_pctile = perf_counter_ns()
    var _ns_pctile = Float64(_t1_pctile - _t0_pctile) / Float64(N)
    print("MOJO_TIMING stats::pctile", _ns_pctile, _acc_pctile)
    var _acc_count_below_zero: Float64 = 0.0
    var _t0_count_below_zero = perf_counter_ns()
    for _ in range(N):
        _acc_count_below_zero += Float64(count_below_zero(_lf5, 5))
    var _t1_count_below_zero = perf_counter_ns()
    var _ns_count_below_zero = Float64(_t1_count_below_zero - _t0_count_below_zero) / Float64(N)
    print("MOJO_TIMING stats::count_below_zero", _ns_count_below_zero, _acc_count_below_zero)
    var _acc_ins_sort: Float64 = 0.0
    var _t0_ins_sort = perf_counter_ns()
    for _ in range(N):
        _ = ins_sort(_lf5, 5, 5)
    var _t1_ins_sort = perf_counter_ns()
    var _ns_ins_sort = Float64(_t1_ins_sort - _t0_ins_sort) / Float64(N)
    print("MOJO_TIMING stats::ins_sort", _ns_ins_sort, _acc_ins_sort)
    var _acc_ilog2: Float64 = 0.0
    var _t0_ilog2 = perf_counter_ns()
    for _ in range(N):
        _acc_ilog2 += Float64(ilog2(5))
    var _t1_ilog2 = perf_counter_ns()
    var _ns_ilog2 = Float64(_t1_ilog2 - _t0_ilog2) / Float64(N)
    print("MOJO_TIMING stats::ilog2", _ns_ilog2, _acc_ilog2)
    var _acc_part3: Float64 = 0.0
    var _t0_part3 = perf_counter_ns()
    for _ in range(N):
        _acc_part3 += Float64(part3(_lf5, 5, 5))
    var _t1_part3 = perf_counter_ns()
    var _ns_part3 = Float64(_t1_part3 - _t0_part3) / Float64(N)
    print("MOJO_TIMING stats::part3", _ns_part3, _acc_part3)
    var _acc_fast_sort: Float64 = 0.0
    var _t0_fast_sort = perf_counter_ns()
    for _ in range(N):
        _ = fast_sort(_lf5, 5)
    var _t1_fast_sort = perf_counter_ns()
    var _ns_fast_sort = Float64(_t1_fast_sort - _t0_fast_sort) / Float64(N)
    print("MOJO_TIMING stats::fast_sort", _ns_fast_sort, _acc_fast_sort)
