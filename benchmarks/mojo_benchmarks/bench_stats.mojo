"""bench_stats.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stats import compute_mean, compute_variance, pctile, count_below_zero, ins_sort, ilog2, part3, fast_sort
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

    var _acc_compute_mean: Float64 = 0.0
    var _t0_compute_mean = perf_counter_ns()
    for _ in range(N):
        _acc_compute_mean += compute_mean(_lf5, 5)
    var _t1_compute_mean = perf_counter_ns()
    var _ns_compute_mean = Float64(_t1_compute_mean - _t0_compute_mean) / Float64(N)
    print("MOJO_TIMING stats::compute_mean", _ns_compute_mean, _acc_compute_mean)
    var _result_compute_mean = compute_mean(_lf5, 5)
    var _summary_compute_mean = _summary_float64(_result_compute_mean)
    print("MOJO_RESULT stats::compute_mean", _summary_compute_mean)
    var _acc_compute_variance: Float64 = 0.0
    var _t0_compute_variance = perf_counter_ns()
    for _ in range(N):
        _acc_compute_variance += compute_variance(_lf5, 5, 0.5)
    var _t1_compute_variance = perf_counter_ns()
    var _ns_compute_variance = Float64(_t1_compute_variance - _t0_compute_variance) / Float64(N)
    print("MOJO_TIMING stats::compute_variance", _ns_compute_variance, _acc_compute_variance)
    var _result_compute_variance = compute_variance(_lf5, 5, 0.5)
    var _summary_compute_variance = _summary_float64(_result_compute_variance)
    print("MOJO_RESULT stats::compute_variance", _summary_compute_variance)
    var _acc_pctile: Float64 = 0.0
    var _t0_pctile = perf_counter_ns()
    for _ in range(N):
        _acc_pctile += pctile(_lf5, 5, 5)
    var _t1_pctile = perf_counter_ns()
    var _ns_pctile = Float64(_t1_pctile - _t0_pctile) / Float64(N)
    print("MOJO_TIMING stats::pctile", _ns_pctile, _acc_pctile)
    var _result_pctile = pctile(_lf5, 5, 5)
    var _summary_pctile = _summary_float64(_result_pctile)
    print("MOJO_RESULT stats::pctile", _summary_pctile)
    var _acc_count_below_zero: Float64 = 0.0
    var _t0_count_below_zero = perf_counter_ns()
    for _ in range(N):
        _acc_count_below_zero += Float64(count_below_zero(_lf5, 5))
    var _t1_count_below_zero = perf_counter_ns()
    var _ns_count_below_zero = Float64(_t1_count_below_zero - _t0_count_below_zero) / Float64(N)
    print("MOJO_TIMING stats::count_below_zero", _ns_count_below_zero, _acc_count_below_zero)
    var _result_count_below_zero = count_below_zero(_lf5, 5)
    var _summary_count_below_zero = _summary_int(_result_count_below_zero)
    print("MOJO_RESULT stats::count_below_zero", _summary_count_below_zero)
    var _acc_ins_sort: Float64 = 0.0
    var _t0_ins_sort = perf_counter_ns()
    for _ in range(N):
        _ = ins_sort(_lf5, 5, 5)
    var _t1_ins_sort = perf_counter_ns()
    var _ns_ins_sort = Float64(_t1_ins_sort - _t0_ins_sort) / Float64(N)
    print("MOJO_TIMING stats::ins_sort", _ns_ins_sort, _acc_ins_sort)
    var _result_ins_sort = ins_sort(_lf5, 5, 5)
    var _summary_ins_sort = "none"
    print("MOJO_RESULT stats::ins_sort", _summary_ins_sort)
    var _acc_ilog2: Float64 = 0.0
    var _t0_ilog2 = perf_counter_ns()
    for _ in range(N):
        _acc_ilog2 += Float64(ilog2(5))
    var _t1_ilog2 = perf_counter_ns()
    var _ns_ilog2 = Float64(_t1_ilog2 - _t0_ilog2) / Float64(N)
    print("MOJO_TIMING stats::ilog2", _ns_ilog2, _acc_ilog2)
    var _result_ilog2 = ilog2(5)
    var _summary_ilog2 = _summary_int(_result_ilog2)
    print("MOJO_RESULT stats::ilog2", _summary_ilog2)
    var _acc_part3: Float64 = 0.0
    var _t0_part3 = perf_counter_ns()
    for _ in range(N):
        _acc_part3 += Float64(part3(_lf5, 5, 5))
    var _t1_part3 = perf_counter_ns()
    var _ns_part3 = Float64(_t1_part3 - _t0_part3) / Float64(N)
    print("MOJO_TIMING stats::part3", _ns_part3, _acc_part3)
    var _result_part3 = part3(_lf5, 5, 5)
    var _summary_part3 = _summary_int(_result_part3)
    print("MOJO_RESULT stats::part3", _summary_part3)
    var _acc_fast_sort: Float64 = 0.0
    var _t0_fast_sort = perf_counter_ns()
    for _ in range(N):
        _ = fast_sort(_lf5, 5)
    var _t1_fast_sort = perf_counter_ns()
    var _ns_fast_sort = Float64(_t1_fast_sort - _t0_fast_sort) / Float64(N)
    print("MOJO_TIMING stats::fast_sort", _ns_fast_sort, _acc_fast_sort)
    var _result_fast_sort = fast_sort(_lf5, 5)
    var _summary_fast_sort = "none"
    print("MOJO_RESULT stats::fast_sort", _summary_fast_sort)
