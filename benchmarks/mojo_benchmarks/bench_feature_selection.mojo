"""bench_feature_selection.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from feature_selection import column_mean, column_variance, variance_threshold, correlation_filter, f_test_scores, select_k_best, forward_selection_greedy, information_gain, feature_importance_permutation
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_column_mean = column_mean([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_column_mean = _summary_list_float64(_result_column_mean)
    print("MOJO_RESULT feature_selection::column_mean", _summary_column_mean)
    var _acc_column_variance: Float64 = 0.0
    var _t0_column_variance = perf_counter_ns()
    for _ in range(N):
        var _r_column_variance = column_variance([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_column_variance += Float64(len(_r_column_variance))
    var _t1_column_variance = perf_counter_ns()
    var _ns_column_variance = Float64(_t1_column_variance - _t0_column_variance) / Float64(N)
    print("MOJO_TIMING feature_selection::column_variance", _ns_column_variance, _acc_column_variance)
    var _result_column_variance = column_variance([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_column_variance = _summary_list_float64(_result_column_variance)
    print("MOJO_RESULT feature_selection::column_variance", _summary_column_variance)
    var _acc_variance_threshold: Float64 = 0.0
    var _t0_variance_threshold = perf_counter_ns()
    for _ in range(N):
        var _r_variance_threshold = variance_threshold([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_variance_threshold += Float64(len(_r_variance_threshold))
    var _t1_variance_threshold = perf_counter_ns()
    var _ns_variance_threshold = Float64(_t1_variance_threshold - _t0_variance_threshold) / Float64(N)
    print("MOJO_TIMING feature_selection::variance_threshold", _ns_variance_threshold, _acc_variance_threshold)
    var _result_variance_threshold = variance_threshold([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_variance_threshold = _summary_list_int(_result_variance_threshold)
    print("MOJO_RESULT feature_selection::variance_threshold", _summary_variance_threshold)
    var _acc_correlation_filter: Float64 = 0.0
    var _t0_correlation_filter = perf_counter_ns()
    for _ in range(N):
        var _r_correlation_filter = correlation_filter([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_correlation_filter += Float64(len(_r_correlation_filter))
    var _t1_correlation_filter = perf_counter_ns()
    var _ns_correlation_filter = Float64(_t1_correlation_filter - _t0_correlation_filter) / Float64(N)
    print("MOJO_TIMING feature_selection::correlation_filter", _ns_correlation_filter, _acc_correlation_filter)
    var _result_correlation_filter = correlation_filter([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_correlation_filter = _summary_list_int(_result_correlation_filter)
    print("MOJO_RESULT feature_selection::correlation_filter", _summary_correlation_filter)
    var _acc_f_test_scores: Float64 = 0.0
    var _t0_f_test_scores = perf_counter_ns()
    for _ in range(N):
        var _r_f_test_scores = f_test_scores([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_f_test_scores += Float64(len(_r_f_test_scores))
    var _t1_f_test_scores = perf_counter_ns()
    var _ns_f_test_scores = Float64(_t1_f_test_scores - _t0_f_test_scores) / Float64(N)
    print("MOJO_TIMING feature_selection::f_test_scores", _ns_f_test_scores, _acc_f_test_scores)
    var _result_f_test_scores = f_test_scores([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_f_test_scores = _summary_list_float64(_result_f_test_scores)
    print("MOJO_RESULT feature_selection::f_test_scores", _summary_f_test_scores)
    var _acc_select_k_best: Float64 = 0.0
    var _t0_select_k_best = perf_counter_ns()
    for _ in range(N):
        var _r_select_k_best = select_k_best(_lf5, 5)
        _acc_select_k_best += Float64(len(_r_select_k_best))
    var _t1_select_k_best = perf_counter_ns()
    var _ns_select_k_best = Float64(_t1_select_k_best - _t0_select_k_best) / Float64(N)
    print("MOJO_TIMING feature_selection::select_k_best", _ns_select_k_best, _acc_select_k_best)
    var _result_select_k_best = select_k_best(_lf5, 5)
    var _summary_select_k_best = _summary_list_int(_result_select_k_best)
    print("MOJO_RESULT feature_selection::select_k_best", _summary_select_k_best)
    var _acc_forward_selection_greedy: Float64 = 0.0
    var _t0_forward_selection_greedy = perf_counter_ns()
    for _ in range(N):
        var _r_forward_selection_greedy = forward_selection_greedy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5)
        _acc_forward_selection_greedy += Float64(len(_r_forward_selection_greedy))
    var _t1_forward_selection_greedy = perf_counter_ns()
    var _ns_forward_selection_greedy = Float64(_t1_forward_selection_greedy - _t0_forward_selection_greedy) / Float64(N)
    print("MOJO_TIMING feature_selection::forward_selection_greedy", _ns_forward_selection_greedy, _acc_forward_selection_greedy)
    var _result_forward_selection_greedy = forward_selection_greedy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5)
    var _summary_forward_selection_greedy = _summary_list_int(_result_forward_selection_greedy)
    print("MOJO_RESULT feature_selection::forward_selection_greedy", _summary_forward_selection_greedy)
    var _acc_information_gain: Float64 = 0.0
    var _t0_information_gain = perf_counter_ns()
    for _ in range(N):
        _acc_information_gain += information_gain(_lf5, _lf5, 5)
    var _t1_information_gain = perf_counter_ns()
    var _ns_information_gain = Float64(_t1_information_gain - _t0_information_gain) / Float64(N)
    print("MOJO_TIMING feature_selection::information_gain", _ns_information_gain, _acc_information_gain)
    var _result_information_gain = information_gain(_lf5, _lf5, 5)
    var _summary_information_gain = _summary_float64(_result_information_gain)
    print("MOJO_RESULT feature_selection::information_gain", _summary_information_gain)
    var _acc_feature_importance_permutation: Float64 = 0.0
    var _t0_feature_importance_permutation = perf_counter_ns()
    for _ in range(N):
        var _r_feature_importance_permutation = feature_importance_permutation([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5)
        _acc_feature_importance_permutation += Float64(len(_r_feature_importance_permutation))
    var _t1_feature_importance_permutation = perf_counter_ns()
    var _ns_feature_importance_permutation = Float64(_t1_feature_importance_permutation - _t0_feature_importance_permutation) / Float64(N)
    print("MOJO_TIMING feature_selection::feature_importance_permutation", _ns_feature_importance_permutation, _acc_feature_importance_permutation)
    var _result_feature_importance_permutation = feature_importance_permutation([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5)
    var _summary_feature_importance_permutation = _summary_list_float64(_result_feature_importance_permutation)
    print("MOJO_RESULT feature_selection::feature_importance_permutation", _summary_feature_importance_permutation)
