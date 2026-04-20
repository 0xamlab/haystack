"""bench_stats_bootstrap.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stats_bootstrap import bootstrap_replicate, bootstrap_mean_ci, bootstrap_std_ci, bootstrap_median_ci, bootstrap_bias, bootstrap_se, bootstrap_test, jackknife_mean, jackknife_se, bca_correction
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

    var _acc_bootstrap_replicate: Float64 = 0.0
    var _t0_bootstrap_replicate = perf_counter_ns()
    for _ in range(N):
        var _r_bootstrap_replicate = bootstrap_replicate(_lf5)
        _acc_bootstrap_replicate += Float64(len(_r_bootstrap_replicate))
    var _t1_bootstrap_replicate = perf_counter_ns()
    var _ns_bootstrap_replicate = Float64(_t1_bootstrap_replicate - _t0_bootstrap_replicate) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_replicate", _ns_bootstrap_replicate, _acc_bootstrap_replicate)
    var _acc_bootstrap_mean_ci: Float64 = 0.0
    var _t0_bootstrap_mean_ci = perf_counter_ns()
    for _ in range(N):
        var _r_bootstrap_mean_ci = bootstrap_mean_ci(_lf5, 5, 0.5)
        _acc_bootstrap_mean_ci += Float64(len(_r_bootstrap_mean_ci))
    var _t1_bootstrap_mean_ci = perf_counter_ns()
    var _ns_bootstrap_mean_ci = Float64(_t1_bootstrap_mean_ci - _t0_bootstrap_mean_ci) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_mean_ci", _ns_bootstrap_mean_ci, _acc_bootstrap_mean_ci)
    var _acc_bootstrap_std_ci: Float64 = 0.0
    var _t0_bootstrap_std_ci = perf_counter_ns()
    for _ in range(N):
        var _r_bootstrap_std_ci = bootstrap_std_ci(_lf5, 5, 0.5)
        _acc_bootstrap_std_ci += Float64(len(_r_bootstrap_std_ci))
    var _t1_bootstrap_std_ci = perf_counter_ns()
    var _ns_bootstrap_std_ci = Float64(_t1_bootstrap_std_ci - _t0_bootstrap_std_ci) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_std_ci", _ns_bootstrap_std_ci, _acc_bootstrap_std_ci)
    var _acc_bootstrap_median_ci: Float64 = 0.0
    var _t0_bootstrap_median_ci = perf_counter_ns()
    for _ in range(N):
        var _r_bootstrap_median_ci = bootstrap_median_ci(_lf5, 5, 0.5)
        _acc_bootstrap_median_ci += Float64(len(_r_bootstrap_median_ci))
    var _t1_bootstrap_median_ci = perf_counter_ns()
    var _ns_bootstrap_median_ci = Float64(_t1_bootstrap_median_ci - _t0_bootstrap_median_ci) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_median_ci", _ns_bootstrap_median_ci, _acc_bootstrap_median_ci)
    var _acc_bootstrap_bias: Float64 = 0.0
    var _t0_bootstrap_bias = perf_counter_ns()
    for _ in range(N):
        _acc_bootstrap_bias += bootstrap_bias(_lf5, 5, 5)
    var _t1_bootstrap_bias = perf_counter_ns()
    var _ns_bootstrap_bias = Float64(_t1_bootstrap_bias - _t0_bootstrap_bias) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_bias", _ns_bootstrap_bias, _acc_bootstrap_bias)
    var _acc_bootstrap_se: Float64 = 0.0
    var _t0_bootstrap_se = perf_counter_ns()
    for _ in range(N):
        _acc_bootstrap_se += bootstrap_se(_lf5, 5, 5)
    var _t1_bootstrap_se = perf_counter_ns()
    var _ns_bootstrap_se = Float64(_t1_bootstrap_se - _t0_bootstrap_se) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_se", _ns_bootstrap_se, _acc_bootstrap_se)
    var _acc_bootstrap_test: Float64 = 0.0
    var _t0_bootstrap_test = perf_counter_ns()
    for _ in range(N):
        _acc_bootstrap_test += bootstrap_test(_lf5, _lf5, 5)
    var _t1_bootstrap_test = perf_counter_ns()
    var _ns_bootstrap_test = Float64(_t1_bootstrap_test - _t0_bootstrap_test) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bootstrap_test", _ns_bootstrap_test, _acc_bootstrap_test)
    var _acc_jackknife_mean: Float64 = 0.0
    var _t0_jackknife_mean = perf_counter_ns()
    for _ in range(N):
        var _r_jackknife_mean = jackknife_mean(_lf5)
        _acc_jackknife_mean += Float64(len(_r_jackknife_mean))
    var _t1_jackknife_mean = perf_counter_ns()
    var _ns_jackknife_mean = Float64(_t1_jackknife_mean - _t0_jackknife_mean) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::jackknife_mean", _ns_jackknife_mean, _acc_jackknife_mean)
    var _acc_jackknife_se: Float64 = 0.0
    var _t0_jackknife_se = perf_counter_ns()
    for _ in range(N):
        _acc_jackknife_se += jackknife_se(_lf5)
    var _t1_jackknife_se = perf_counter_ns()
    var _ns_jackknife_se = Float64(_t1_jackknife_se - _t0_jackknife_se) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::jackknife_se", _ns_jackknife_se, _acc_jackknife_se)
    var _acc_bca_correction: Float64 = 0.0
    var _t0_bca_correction = perf_counter_ns()
    for _ in range(N):
        var _r_bca_correction = bca_correction(_lf5, 5, 0.5)
        _acc_bca_correction += Float64(len(_r_bca_correction))
    var _t1_bca_correction = perf_counter_ns()
    var _ns_bca_correction = Float64(_t1_bca_correction - _t0_bca_correction) / Float64(N)
    print("MOJO_TIMING stats_bootstrap::bca_correction", _ns_bca_correction, _acc_bca_correction)
