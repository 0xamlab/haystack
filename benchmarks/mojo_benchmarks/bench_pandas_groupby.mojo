"""bench_pandas_groupby.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pandas_groupby import group_mean_update, group_variance_update, group_min_update, group_max_update, group_sum_update, group_count_update, group_std_from_variance, weighted_group_mean, group_median_approx, group_skewness_term
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

    var _acc_group_mean_update: Float64 = 0.0
    var _t0_group_mean_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_mean_update += group_mean_update(0.5, 0.5, 0.5)
    var _t1_group_mean_update = perf_counter_ns()
    var _ns_group_mean_update = Float64(_t1_group_mean_update - _t0_group_mean_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_mean_update", _ns_group_mean_update, _acc_group_mean_update)
    var _acc_group_variance_update: Float64 = 0.0
    var _t0_group_variance_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_variance_update += group_variance_update(0.5, 0.5, 0.5, 0.5)
    var _t1_group_variance_update = perf_counter_ns()
    var _ns_group_variance_update = Float64(_t1_group_variance_update - _t0_group_variance_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_variance_update", _ns_group_variance_update, _acc_group_variance_update)
    var _acc_group_min_update: Float64 = 0.0
    var _t0_group_min_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_min_update += group_min_update(0.5, 0.5)
    var _t1_group_min_update = perf_counter_ns()
    var _ns_group_min_update = Float64(_t1_group_min_update - _t0_group_min_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_min_update", _ns_group_min_update, _acc_group_min_update)
    var _acc_group_max_update: Float64 = 0.0
    var _t0_group_max_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_max_update += group_max_update(0.5, 0.5)
    var _t1_group_max_update = perf_counter_ns()
    var _ns_group_max_update = Float64(_t1_group_max_update - _t0_group_max_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_max_update", _ns_group_max_update, _acc_group_max_update)
    var _acc_group_sum_update: Float64 = 0.0
    var _t0_group_sum_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_sum_update += group_sum_update(0.5, 0.5)
    var _t1_group_sum_update = perf_counter_ns()
    var _ns_group_sum_update = Float64(_t1_group_sum_update - _t0_group_sum_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_sum_update", _ns_group_sum_update, _acc_group_sum_update)
    var _acc_group_count_update: Float64 = 0.0
    var _t0_group_count_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_count_update += group_count_update(0.5)
    var _t1_group_count_update = perf_counter_ns()
    var _ns_group_count_update = Float64(_t1_group_count_update - _t0_group_count_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_count_update", _ns_group_count_update, _acc_group_count_update)
    var _acc_group_std_from_variance: Float64 = 0.0
    var _t0_group_std_from_variance = perf_counter_ns()
    for _ in range(N):
        _acc_group_std_from_variance += group_std_from_variance(0.5, 0.5, 0.5)
    var _t1_group_std_from_variance = perf_counter_ns()
    var _ns_group_std_from_variance = Float64(_t1_group_std_from_variance - _t0_group_std_from_variance) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_std_from_variance", _ns_group_std_from_variance, _acc_group_std_from_variance)
    var _acc_weighted_group_mean: Float64 = 0.0
    var _t0_weighted_group_mean = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_group_mean += weighted_group_mean(0.5, 0.5)
    var _t1_weighted_group_mean = perf_counter_ns()
    var _ns_weighted_group_mean = Float64(_t1_weighted_group_mean - _t0_weighted_group_mean) / Float64(N)
    print("MOJO_TIMING pandas_groupby::weighted_group_mean", _ns_weighted_group_mean, _acc_weighted_group_mean)
    var _acc_group_median_approx: Float64 = 0.0
    var _t0_group_median_approx = perf_counter_ns()
    for _ in range(N):
        _acc_group_median_approx += group_median_approx(0.5, 0.5, 0.5)
    var _t1_group_median_approx = perf_counter_ns()
    var _ns_group_median_approx = Float64(_t1_group_median_approx - _t0_group_median_approx) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_median_approx", _ns_group_median_approx, _acc_group_median_approx)
    var _acc_group_skewness_term: Float64 = 0.0
    var _t0_group_skewness_term = perf_counter_ns()
    for _ in range(N):
        _acc_group_skewness_term += group_skewness_term(0.5, 0.5, 0.5)
    var _t1_group_skewness_term = perf_counter_ns()
    var _ns_group_skewness_term = Float64(_t1_group_skewness_term - _t0_group_skewness_term) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_skewness_term", _ns_group_skewness_term, _acc_group_skewness_term)
