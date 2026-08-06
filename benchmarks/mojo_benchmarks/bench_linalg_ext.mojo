"""bench_linalg_ext.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from linalg_ext import mat_norm_frobenius, mat_norm_inf, mat_trace, mat_is_symmetric, mat_is_positive_definite, mat_power_iteration, mat_condition_number, PowerIterResult
from std.time import perf_counter_ns
from linalg import mat_from_list, Matrix
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
    var _mat3_data = List[Float64]()
    _mat3_data.append(1.0); _mat3_data.append(0.0); _mat3_data.append(0.0)
    _mat3_data.append(0.0); _mat3_data.append(2.0); _mat3_data.append(0.0)
    _mat3_data.append(0.0); _mat3_data.append(0.0); _mat3_data.append(3.0)
    var _mat3 = mat_from_list(_mat3_data, 3, 3)
    var N: Int = 10000

    var _acc_mat_norm_frobenius: Float64 = 0.0
    var _t0_mat_norm_frobenius = perf_counter_ns()
    for _ in range(N):
        _acc_mat_norm_frobenius += mat_norm_frobenius(_mat3)
    var _t1_mat_norm_frobenius = perf_counter_ns()
    var _ns_mat_norm_frobenius = Float64(_t1_mat_norm_frobenius - _t0_mat_norm_frobenius) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_norm_frobenius", _ns_mat_norm_frobenius, _acc_mat_norm_frobenius)
    var _result_mat_norm_frobenius = mat_norm_frobenius(_mat3)
    var _summary_mat_norm_frobenius = _summary_float64(_result_mat_norm_frobenius)
    print("MOJO_RESULT linalg_ext::mat_norm_frobenius", _summary_mat_norm_frobenius)
    var _acc_mat_norm_inf: Float64 = 0.0
    var _t0_mat_norm_inf = perf_counter_ns()
    for _ in range(N):
        _acc_mat_norm_inf += mat_norm_inf(_mat3)
    var _t1_mat_norm_inf = perf_counter_ns()
    var _ns_mat_norm_inf = Float64(_t1_mat_norm_inf - _t0_mat_norm_inf) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_norm_inf", _ns_mat_norm_inf, _acc_mat_norm_inf)
    var _result_mat_norm_inf = mat_norm_inf(_mat3)
    var _summary_mat_norm_inf = _summary_float64(_result_mat_norm_inf)
    print("MOJO_RESULT linalg_ext::mat_norm_inf", _summary_mat_norm_inf)
    var _acc_mat_trace: Float64 = 0.0
    var _t0_mat_trace = perf_counter_ns()
    for _ in range(N):
        _acc_mat_trace += mat_trace(_mat3)
    var _t1_mat_trace = perf_counter_ns()
    var _ns_mat_trace = Float64(_t1_mat_trace - _t0_mat_trace) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_trace", _ns_mat_trace, _acc_mat_trace)
    var _result_mat_trace = mat_trace(_mat3)
    var _summary_mat_trace = _summary_float64(_result_mat_trace)
    print("MOJO_RESULT linalg_ext::mat_trace", _summary_mat_trace)
    var _acc_mat_is_symmetric: Float64 = 0.0
    var _t0_mat_is_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_mat_is_symmetric += Float64(mat_is_symmetric(_mat3, 1e-10))
    var _t1_mat_is_symmetric = perf_counter_ns()
    var _ns_mat_is_symmetric = Float64(_t1_mat_is_symmetric - _t0_mat_is_symmetric) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_is_symmetric", _ns_mat_is_symmetric, _acc_mat_is_symmetric)
    var _result_mat_is_symmetric = mat_is_symmetric(_mat3, 1e-10)
    var _summary_mat_is_symmetric = _summary_bool(_result_mat_is_symmetric)
    print("MOJO_RESULT linalg_ext::mat_is_symmetric", _summary_mat_is_symmetric)
    var _acc_mat_is_positive_definite: Float64 = 0.0
    var _t0_mat_is_positive_definite = perf_counter_ns()
    for _ in range(N):
        _acc_mat_is_positive_definite += Float64(mat_is_positive_definite(_mat3))
    var _t1_mat_is_positive_definite = perf_counter_ns()
    var _ns_mat_is_positive_definite = Float64(_t1_mat_is_positive_definite - _t0_mat_is_positive_definite) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_is_positive_definite", _ns_mat_is_positive_definite, _acc_mat_is_positive_definite)
    var _result_mat_is_positive_definite = mat_is_positive_definite(_mat3)
    var _summary_mat_is_positive_definite = _summary_bool(_result_mat_is_positive_definite)
    print("MOJO_RESULT linalg_ext::mat_is_positive_definite", _summary_mat_is_positive_definite)
    var _keeper_mat_power_iteration = List[PowerIterResult]()
    _keeper_mat_power_iteration.append(mat_power_iteration(_mat3, 100))
    var _acc_mat_power_iteration: Float64 = 0.0
    var _t0_mat_power_iteration = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_power_iteration[0] = mat_power_iteration(_mat3, 100)
        _acc_mat_power_iteration += Float64(len(_keeper_mat_power_iteration))
    var _t1_mat_power_iteration = perf_counter_ns()
    var _ns_mat_power_iteration = Float64(_t1_mat_power_iteration - _t0_mat_power_iteration) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_power_iteration", _ns_mat_power_iteration, _acc_mat_power_iteration)
    var _acc_mat_condition_number: Float64 = 0.0
    var _t0_mat_condition_number = perf_counter_ns()
    for _ in range(N):
        _acc_mat_condition_number += mat_condition_number(_mat3)
    var _t1_mat_condition_number = perf_counter_ns()
    var _ns_mat_condition_number = Float64(_t1_mat_condition_number - _t0_mat_condition_number) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_condition_number", _ns_mat_condition_number, _acc_mat_condition_number)
    var _result_mat_condition_number = mat_condition_number(_mat3)
    var _summary_mat_condition_number = _summary_float64(_result_mat_condition_number)
    print("MOJO_RESULT linalg_ext::mat_condition_number", _summary_mat_condition_number)
