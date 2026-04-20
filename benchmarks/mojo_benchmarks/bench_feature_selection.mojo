"""bench_feature_selection.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from feature_selection import column_mean, column_variance, variance_threshold, correlation_filter, f_test_scores, select_k_best, forward_selection_greedy, information_gain, feature_importance_permutation
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

    var _acc_column_mean: Float64 = 0.0
    var _t0_column_mean = perf_counter_ns()
    for _ in range(N):
        var _r_column_mean = column_mean([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_column_mean += Float64(len(_r_column_mean))
    var _t1_column_mean = perf_counter_ns()
    var _ns_column_mean = Float64(_t1_column_mean - _t0_column_mean) / Float64(N)
    print("MOJO_TIMING feature_selection::column_mean", _ns_column_mean, _acc_column_mean)
    var _acc_column_variance: Float64 = 0.0
    var _t0_column_variance = perf_counter_ns()
    for _ in range(N):
        var _r_column_variance = column_variance([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_column_variance += Float64(len(_r_column_variance))
    var _t1_column_variance = perf_counter_ns()
    var _ns_column_variance = Float64(_t1_column_variance - _t0_column_variance) / Float64(N)
    print("MOJO_TIMING feature_selection::column_variance", _ns_column_variance, _acc_column_variance)
    var _acc_variance_threshold: Float64 = 0.0
    var _t0_variance_threshold = perf_counter_ns()
    for _ in range(N):
        var _r_variance_threshold = variance_threshold([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_variance_threshold += Float64(len(_r_variance_threshold))
    var _t1_variance_threshold = perf_counter_ns()
    var _ns_variance_threshold = Float64(_t1_variance_threshold - _t0_variance_threshold) / Float64(N)
    print("MOJO_TIMING feature_selection::variance_threshold", _ns_variance_threshold, _acc_variance_threshold)
    var _acc_correlation_filter: Float64 = 0.0
    var _t0_correlation_filter = perf_counter_ns()
    for _ in range(N):
        var _r_correlation_filter = correlation_filter([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_correlation_filter += Float64(len(_r_correlation_filter))
    var _t1_correlation_filter = perf_counter_ns()
    var _ns_correlation_filter = Float64(_t1_correlation_filter - _t0_correlation_filter) / Float64(N)
    print("MOJO_TIMING feature_selection::correlation_filter", _ns_correlation_filter, _acc_correlation_filter)
    var _acc_f_test_scores: Float64 = 0.0
    var _t0_f_test_scores = perf_counter_ns()
    for _ in range(N):
        var _r_f_test_scores = f_test_scores([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_f_test_scores += Float64(len(_r_f_test_scores))
    var _t1_f_test_scores = perf_counter_ns()
    var _ns_f_test_scores = Float64(_t1_f_test_scores - _t0_f_test_scores) / Float64(N)
    print("MOJO_TIMING feature_selection::f_test_scores", _ns_f_test_scores, _acc_f_test_scores)
    var _acc_select_k_best: Float64 = 0.0
    var _t0_select_k_best = perf_counter_ns()
    for _ in range(N):
        var _r_select_k_best = select_k_best(_lf5, 5)
        _acc_select_k_best += Float64(len(_r_select_k_best))
    var _t1_select_k_best = perf_counter_ns()
    var _ns_select_k_best = Float64(_t1_select_k_best - _t0_select_k_best) / Float64(N)
    print("MOJO_TIMING feature_selection::select_k_best", _ns_select_k_best, _acc_select_k_best)
    var _acc_forward_selection_greedy: Float64 = 0.0
    var _t0_forward_selection_greedy = perf_counter_ns()
    for _ in range(N):
        var _r_forward_selection_greedy = forward_selection_greedy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5)
        _acc_forward_selection_greedy += Float64(len(_r_forward_selection_greedy))
    var _t1_forward_selection_greedy = perf_counter_ns()
    var _ns_forward_selection_greedy = Float64(_t1_forward_selection_greedy - _t0_forward_selection_greedy) / Float64(N)
    print("MOJO_TIMING feature_selection::forward_selection_greedy", _ns_forward_selection_greedy, _acc_forward_selection_greedy)
    var _acc_information_gain: Float64 = 0.0
    var _t0_information_gain = perf_counter_ns()
    for _ in range(N):
        _acc_information_gain += information_gain(_lf5, _lf5, 5)
    var _t1_information_gain = perf_counter_ns()
    var _ns_information_gain = Float64(_t1_information_gain - _t0_information_gain) / Float64(N)
    print("MOJO_TIMING feature_selection::information_gain", _ns_information_gain, _acc_information_gain)
    var _acc_feature_importance_permutation: Float64 = 0.0
    var _t0_feature_importance_permutation = perf_counter_ns()
    for _ in range(N):
        var _r_feature_importance_permutation = feature_importance_permutation([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5)
        _acc_feature_importance_permutation += Float64(len(_r_feature_importance_permutation))
    var _t1_feature_importance_permutation = perf_counter_ns()
    var _ns_feature_importance_permutation = Float64(_t1_feature_importance_permutation - _t0_feature_importance_permutation) / Float64(N)
    print("MOJO_TIMING feature_selection::feature_importance_permutation", _ns_feature_importance_permutation, _acc_feature_importance_permutation)
