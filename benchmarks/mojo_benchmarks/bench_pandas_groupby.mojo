"""bench_pandas_groupby.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pandas_groupby import group_mean_update, group_variance_update, group_min_update, group_max_update, group_sum_update, group_count_update, group_std_from_variance, weighted_group_mean, group_median_approx, group_skewness_term
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

    var _acc_group_mean_update: Float64 = 0.0
    var _t0_group_mean_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_mean_update += group_mean_update(0.5, 0.5, 0.5)
    var _t1_group_mean_update = perf_counter_ns()
    var _ns_group_mean_update = Float64(_t1_group_mean_update - _t0_group_mean_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_mean_update", _ns_group_mean_update, _acc_group_mean_update)
    var _result_group_mean_update = group_mean_update(0.5, 0.5, 0.5)
    var _summary_group_mean_update = _summary_float64(_result_group_mean_update)
    print("MOJO_RESULT pandas_groupby::group_mean_update", _summary_group_mean_update)
    var _acc_group_variance_update: Float64 = 0.0
    var _t0_group_variance_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_variance_update += group_variance_update(0.5, 0.5, 0.5, 0.5)
    var _t1_group_variance_update = perf_counter_ns()
    var _ns_group_variance_update = Float64(_t1_group_variance_update - _t0_group_variance_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_variance_update", _ns_group_variance_update, _acc_group_variance_update)
    var _result_group_variance_update = group_variance_update(0.5, 0.5, 0.5, 0.5)
    var _summary_group_variance_update = _summary_float64(_result_group_variance_update)
    print("MOJO_RESULT pandas_groupby::group_variance_update", _summary_group_variance_update)
    var _acc_group_min_update: Float64 = 0.0
    var _t0_group_min_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_min_update += group_min_update(0.5, 0.5)
    var _t1_group_min_update = perf_counter_ns()
    var _ns_group_min_update = Float64(_t1_group_min_update - _t0_group_min_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_min_update", _ns_group_min_update, _acc_group_min_update)
    var _result_group_min_update = group_min_update(0.5, 0.5)
    var _summary_group_min_update = _summary_float64(_result_group_min_update)
    print("MOJO_RESULT pandas_groupby::group_min_update", _summary_group_min_update)
    var _acc_group_max_update: Float64 = 0.0
    var _t0_group_max_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_max_update += group_max_update(0.5, 0.5)
    var _t1_group_max_update = perf_counter_ns()
    var _ns_group_max_update = Float64(_t1_group_max_update - _t0_group_max_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_max_update", _ns_group_max_update, _acc_group_max_update)
    var _result_group_max_update = group_max_update(0.5, 0.5)
    var _summary_group_max_update = _summary_float64(_result_group_max_update)
    print("MOJO_RESULT pandas_groupby::group_max_update", _summary_group_max_update)
    var _acc_group_sum_update: Float64 = 0.0
    var _t0_group_sum_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_sum_update += group_sum_update(0.5, 0.5)
    var _t1_group_sum_update = perf_counter_ns()
    var _ns_group_sum_update = Float64(_t1_group_sum_update - _t0_group_sum_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_sum_update", _ns_group_sum_update, _acc_group_sum_update)
    var _result_group_sum_update = group_sum_update(0.5, 0.5)
    var _summary_group_sum_update = _summary_float64(_result_group_sum_update)
    print("MOJO_RESULT pandas_groupby::group_sum_update", _summary_group_sum_update)
    var _acc_group_count_update: Float64 = 0.0
    var _t0_group_count_update = perf_counter_ns()
    for _ in range(N):
        _acc_group_count_update += group_count_update(0.5)
    var _t1_group_count_update = perf_counter_ns()
    var _ns_group_count_update = Float64(_t1_group_count_update - _t0_group_count_update) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_count_update", _ns_group_count_update, _acc_group_count_update)
    var _result_group_count_update = group_count_update(0.5)
    var _summary_group_count_update = _summary_float64(_result_group_count_update)
    print("MOJO_RESULT pandas_groupby::group_count_update", _summary_group_count_update)
    var _acc_group_std_from_variance: Float64 = 0.0
    var _t0_group_std_from_variance = perf_counter_ns()
    for _ in range(N):
        _acc_group_std_from_variance += group_std_from_variance(0.5, 0.5, 0.5)
    var _t1_group_std_from_variance = perf_counter_ns()
    var _ns_group_std_from_variance = Float64(_t1_group_std_from_variance - _t0_group_std_from_variance) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_std_from_variance", _ns_group_std_from_variance, _acc_group_std_from_variance)
    var _result_group_std_from_variance = group_std_from_variance(0.5, 0.5, 0.5)
    var _summary_group_std_from_variance = _summary_float64(_result_group_std_from_variance)
    print("MOJO_RESULT pandas_groupby::group_std_from_variance", _summary_group_std_from_variance)
    var _acc_weighted_group_mean: Float64 = 0.0
    var _t0_weighted_group_mean = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_group_mean += weighted_group_mean(0.5, 0.5)
    var _t1_weighted_group_mean = perf_counter_ns()
    var _ns_weighted_group_mean = Float64(_t1_weighted_group_mean - _t0_weighted_group_mean) / Float64(N)
    print("MOJO_TIMING pandas_groupby::weighted_group_mean", _ns_weighted_group_mean, _acc_weighted_group_mean)
    var _result_weighted_group_mean = weighted_group_mean(0.5, 0.5)
    var _summary_weighted_group_mean = _summary_float64(_result_weighted_group_mean)
    print("MOJO_RESULT pandas_groupby::weighted_group_mean", _summary_weighted_group_mean)
    var _acc_group_median_approx: Float64 = 0.0
    var _t0_group_median_approx = perf_counter_ns()
    for _ in range(N):
        _acc_group_median_approx += group_median_approx(0.5, 0.5, 0.5)
    var _t1_group_median_approx = perf_counter_ns()
    var _ns_group_median_approx = Float64(_t1_group_median_approx - _t0_group_median_approx) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_median_approx", _ns_group_median_approx, _acc_group_median_approx)
    var _result_group_median_approx = group_median_approx(0.5, 0.5, 0.5)
    var _summary_group_median_approx = _summary_float64(_result_group_median_approx)
    print("MOJO_RESULT pandas_groupby::group_median_approx", _summary_group_median_approx)
    var _acc_group_skewness_term: Float64 = 0.0
    var _t0_group_skewness_term = perf_counter_ns()
    for _ in range(N):
        _acc_group_skewness_term += group_skewness_term(0.5, 0.5, 0.5)
    var _t1_group_skewness_term = perf_counter_ns()
    var _ns_group_skewness_term = Float64(_t1_group_skewness_term - _t0_group_skewness_term) / Float64(N)
    print("MOJO_TIMING pandas_groupby::group_skewness_term", _ns_group_skewness_term, _acc_group_skewness_term)
    var _result_group_skewness_term = group_skewness_term(0.5, 0.5, 0.5)
    var _summary_group_skewness_term = _summary_float64(_result_group_skewness_term)
    print("MOJO_RESULT pandas_groupby::group_skewness_term", _summary_group_skewness_term)
