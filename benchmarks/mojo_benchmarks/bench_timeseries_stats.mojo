"""bench_timeseries_stats.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from timeseries_stats import autocorrelation, autocorrelation_function, partial_autocorrelation, rolling_mean, rolling_std, exponential_smoothing, difference, adf_test_statistic, holt_linear
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_autocorrelation: Float64 = 0.0
    var _t0_autocorrelation = perf_counter_ns()
    for _ in range(N):
        _acc_autocorrelation += autocorrelation(_lf5, 5)
    var _t1_autocorrelation = perf_counter_ns()
    var _ns_autocorrelation = Float64(_t1_autocorrelation - _t0_autocorrelation) / Float64(N)
    print("MOJO_TIMING timeseries_stats::autocorrelation", _ns_autocorrelation, _acc_autocorrelation)
    var _result_autocorrelation = autocorrelation(_lf5, 5)
    var _summary_autocorrelation = _summary_float64(_result_autocorrelation)
    print("MOJO_RESULT timeseries_stats::autocorrelation", _summary_autocorrelation)
    var _acc_autocorrelation_function: Float64 = 0.0
    var _t0_autocorrelation_function = perf_counter_ns()
    for _ in range(N):
        var _r_autocorrelation_function = autocorrelation_function(_lf5, 5)
        _acc_autocorrelation_function += Float64(len(_r_autocorrelation_function))
    var _t1_autocorrelation_function = perf_counter_ns()
    var _ns_autocorrelation_function = Float64(_t1_autocorrelation_function - _t0_autocorrelation_function) / Float64(N)
    print("MOJO_TIMING timeseries_stats::autocorrelation_function", _ns_autocorrelation_function, _acc_autocorrelation_function)
    var _result_autocorrelation_function = autocorrelation_function(_lf5, 5)
    var _summary_autocorrelation_function = _summary_list_float64(_result_autocorrelation_function)
    print("MOJO_RESULT timeseries_stats::autocorrelation_function", _summary_autocorrelation_function)
    var _acc_partial_autocorrelation: Float64 = 0.0
    var _t0_partial_autocorrelation = perf_counter_ns()
    for _ in range(N):
        var _r_partial_autocorrelation = partial_autocorrelation(_lf5, 5)
        _acc_partial_autocorrelation += Float64(len(_r_partial_autocorrelation))
    var _t1_partial_autocorrelation = perf_counter_ns()
    var _ns_partial_autocorrelation = Float64(_t1_partial_autocorrelation - _t0_partial_autocorrelation) / Float64(N)
    print("MOJO_TIMING timeseries_stats::partial_autocorrelation", _ns_partial_autocorrelation, _acc_partial_autocorrelation)
    var _result_partial_autocorrelation = partial_autocorrelation(_lf5, 5)
    var _summary_partial_autocorrelation = _summary_list_float64(_result_partial_autocorrelation)
    print("MOJO_RESULT timeseries_stats::partial_autocorrelation", _summary_partial_autocorrelation)
    var _acc_rolling_mean: Float64 = 0.0
    var _t0_rolling_mean = perf_counter_ns()
    for _ in range(N):
        var _r_rolling_mean = rolling_mean(_lf5, 5)
        _acc_rolling_mean += Float64(len(_r_rolling_mean))
    var _t1_rolling_mean = perf_counter_ns()
    var _ns_rolling_mean = Float64(_t1_rolling_mean - _t0_rolling_mean) / Float64(N)
    print("MOJO_TIMING timeseries_stats::rolling_mean", _ns_rolling_mean, _acc_rolling_mean)
    var _result_rolling_mean = rolling_mean(_lf5, 5)
    var _summary_rolling_mean = _summary_list_float64(_result_rolling_mean)
    print("MOJO_RESULT timeseries_stats::rolling_mean", _summary_rolling_mean)
    var _acc_rolling_std: Float64 = 0.0
    var _t0_rolling_std = perf_counter_ns()
    for _ in range(N):
        var _r_rolling_std = rolling_std(_lf5, 5)
        _acc_rolling_std += Float64(len(_r_rolling_std))
    var _t1_rolling_std = perf_counter_ns()
    var _ns_rolling_std = Float64(_t1_rolling_std - _t0_rolling_std) / Float64(N)
    print("MOJO_TIMING timeseries_stats::rolling_std", _ns_rolling_std, _acc_rolling_std)
    var _result_rolling_std = rolling_std(_lf5, 5)
    var _summary_rolling_std = _summary_list_float64(_result_rolling_std)
    print("MOJO_RESULT timeseries_stats::rolling_std", _summary_rolling_std)
    var _acc_exponential_smoothing: Float64 = 0.0
    var _t0_exponential_smoothing = perf_counter_ns()
    for _ in range(N):
        var _r_exponential_smoothing = exponential_smoothing(_lf5, 0.5)
        _acc_exponential_smoothing += Float64(len(_r_exponential_smoothing))
    var _t1_exponential_smoothing = perf_counter_ns()
    var _ns_exponential_smoothing = Float64(_t1_exponential_smoothing - _t0_exponential_smoothing) / Float64(N)
    print("MOJO_TIMING timeseries_stats::exponential_smoothing", _ns_exponential_smoothing, _acc_exponential_smoothing)
    var _result_exponential_smoothing = exponential_smoothing(_lf5, 0.5)
    var _summary_exponential_smoothing = _summary_list_float64(_result_exponential_smoothing)
    print("MOJO_RESULT timeseries_stats::exponential_smoothing", _summary_exponential_smoothing)
    var _acc_difference: Float64 = 0.0
    var _t0_difference = perf_counter_ns()
    for _ in range(N):
        var _r_difference = difference(_lf5, 5)
        _acc_difference += Float64(len(_r_difference))
    var _t1_difference = perf_counter_ns()
    var _ns_difference = Float64(_t1_difference - _t0_difference) / Float64(N)
    print("MOJO_TIMING timeseries_stats::difference", _ns_difference, _acc_difference)
    var _result_difference = difference(_lf5, 5)
    var _summary_difference = _summary_list_float64(_result_difference)
    print("MOJO_RESULT timeseries_stats::difference", _summary_difference)
    var _acc_adf_test_statistic: Float64 = 0.0
    var _t0_adf_test_statistic = perf_counter_ns()
    for _ in range(N):
        _acc_adf_test_statistic += adf_test_statistic(_lf5)
    var _t1_adf_test_statistic = perf_counter_ns()
    var _ns_adf_test_statistic = Float64(_t1_adf_test_statistic - _t0_adf_test_statistic) / Float64(N)
    print("MOJO_TIMING timeseries_stats::adf_test_statistic", _ns_adf_test_statistic, _acc_adf_test_statistic)
    var _result_adf_test_statistic = adf_test_statistic(_lf5)
    var _summary_adf_test_statistic = _summary_float64(_result_adf_test_statistic)
    print("MOJO_RESULT timeseries_stats::adf_test_statistic", _summary_adf_test_statistic)
    var _acc_holt_linear: Float64 = 0.0
    var _t0_holt_linear = perf_counter_ns()
    for _ in range(N):
        var _r_holt_linear = holt_linear(_lf5, 0.5, 0.5)
        _acc_holt_linear += Float64(len(_r_holt_linear))
    var _t1_holt_linear = perf_counter_ns()
    var _ns_holt_linear = Float64(_t1_holt_linear - _t0_holt_linear) / Float64(N)
    print("MOJO_TIMING timeseries_stats::holt_linear", _ns_holt_linear, _acc_holt_linear)
    var _result_holt_linear = holt_linear(_lf5, 0.5, 0.5)
    var _summary_holt_linear = _summary_list_float64(_result_holt_linear)
    print("MOJO_RESULT timeseries_stats::holt_linear", _summary_holt_linear)
