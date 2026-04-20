"""bench_anomaly.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from anomaly import percentile, median, mad, zscore_detect, iqr_detect, modified_zscore_detect, isolation_score, exp_approx, grubbs_test_statistic, count_anomalies
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

    var _acc_percentile: Float64 = 0.0
    var _t0_percentile = perf_counter_ns()
    for _ in range(N):
        _acc_percentile += percentile(_lf5, 0.5)
    var _t1_percentile = perf_counter_ns()
    var _ns_percentile = Float64(_t1_percentile - _t0_percentile) / Float64(N)
    print("MOJO_TIMING anomaly::percentile", _ns_percentile, _acc_percentile)
    var _acc_median: Float64 = 0.0
    var _t0_median = perf_counter_ns()
    for _ in range(N):
        _acc_median += median(_lf5)
    var _t1_median = perf_counter_ns()
    var _ns_median = Float64(_t1_median - _t0_median) / Float64(N)
    print("MOJO_TIMING anomaly::median", _ns_median, _acc_median)
    var _acc_mad: Float64 = 0.0
    var _t0_mad = perf_counter_ns()
    for _ in range(N):
        _acc_mad += mad(_lf5)
    var _t1_mad = perf_counter_ns()
    var _ns_mad = Float64(_t1_mad - _t0_mad) / Float64(N)
    print("MOJO_TIMING anomaly::mad", _ns_mad, _acc_mad)
    var _acc_zscore_detect: Float64 = 0.0
    var _t0_zscore_detect = perf_counter_ns()
    for _ in range(N):
        var _r_zscore_detect = zscore_detect(_lf5, 0.5)
        _acc_zscore_detect += Float64(len(_r_zscore_detect))
    var _t1_zscore_detect = perf_counter_ns()
    var _ns_zscore_detect = Float64(_t1_zscore_detect - _t0_zscore_detect) / Float64(N)
    print("MOJO_TIMING anomaly::zscore_detect", _ns_zscore_detect, _acc_zscore_detect)
    var _acc_iqr_detect: Float64 = 0.0
    var _t0_iqr_detect = perf_counter_ns()
    for _ in range(N):
        var _r_iqr_detect = iqr_detect(_lf5, 0.5)
        _acc_iqr_detect += Float64(len(_r_iqr_detect))
    var _t1_iqr_detect = perf_counter_ns()
    var _ns_iqr_detect = Float64(_t1_iqr_detect - _t0_iqr_detect) / Float64(N)
    print("MOJO_TIMING anomaly::iqr_detect", _ns_iqr_detect, _acc_iqr_detect)
    var _acc_modified_zscore_detect: Float64 = 0.0
    var _t0_modified_zscore_detect = perf_counter_ns()
    for _ in range(N):
        var _r_modified_zscore_detect = modified_zscore_detect(_lf5, 0.5)
        _acc_modified_zscore_detect += Float64(len(_r_modified_zscore_detect))
    var _t1_modified_zscore_detect = perf_counter_ns()
    var _ns_modified_zscore_detect = Float64(_t1_modified_zscore_detect - _t0_modified_zscore_detect) / Float64(N)
    print("MOJO_TIMING anomaly::modified_zscore_detect", _ns_modified_zscore_detect, _acc_modified_zscore_detect)
    var _acc_isolation_score: Float64 = 0.0
    var _t0_isolation_score = perf_counter_ns()
    for _ in range(N):
        _acc_isolation_score += isolation_score(_lf5, 0.5, 5, 5)
    var _t1_isolation_score = perf_counter_ns()
    var _ns_isolation_score = Float64(_t1_isolation_score - _t0_isolation_score) / Float64(N)
    print("MOJO_TIMING anomaly::isolation_score", _ns_isolation_score, _acc_isolation_score)
    var _acc_exp_approx: Float64 = 0.0
    var _t0_exp_approx = perf_counter_ns()
    for _ in range(N):
        _acc_exp_approx += exp_approx(0.5)
    var _t1_exp_approx = perf_counter_ns()
    var _ns_exp_approx = Float64(_t1_exp_approx - _t0_exp_approx) / Float64(N)
    print("MOJO_TIMING anomaly::exp_approx", _ns_exp_approx, _acc_exp_approx)
    var _acc_grubbs_test_statistic: Float64 = 0.0
    var _t0_grubbs_test_statistic = perf_counter_ns()
    for _ in range(N):
        _acc_grubbs_test_statistic += grubbs_test_statistic(_lf5)
    var _t1_grubbs_test_statistic = perf_counter_ns()
    var _ns_grubbs_test_statistic = Float64(_t1_grubbs_test_statistic - _t0_grubbs_test_statistic) / Float64(N)
    print("MOJO_TIMING anomaly::grubbs_test_statistic", _ns_grubbs_test_statistic, _acc_grubbs_test_statistic)
    var _acc_count_anomalies: Float64 = 0.0
    var _t0_count_anomalies = perf_counter_ns()
    for _ in range(N):
        _acc_count_anomalies += Float64(count_anomalies(_lb5))
    var _t1_count_anomalies = perf_counter_ns()
    var _ns_count_anomalies = Float64(_t1_count_anomalies - _t0_count_anomalies) / Float64(N)
    print("MOJO_TIMING anomaly::count_anomalies", _ns_count_anomalies, _acc_count_anomalies)
