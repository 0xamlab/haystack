"""bench_kalman.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from kalman import mat_identity, mat_mul, mat_transpose, mat_add, mat_sub, mat_scale, mat_inv_2x2, matvec, kalman_smooth_1d
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

    var _acc_mat_identity: Float64 = 0.0
    var _t0_mat_identity = perf_counter_ns()
    for _ in range(N):
        var _r_mat_identity = mat_identity(5)
        _acc_mat_identity += Float64(len(_r_mat_identity))
    var _t1_mat_identity = perf_counter_ns()
    var _ns_mat_identity = Float64(_t1_mat_identity - _t0_mat_identity) / Float64(N)
    print("MOJO_TIMING kalman::mat_identity", _ns_mat_identity, _acc_mat_identity)
    var _result_mat_identity = mat_identity(5)
    var _summary_mat_identity = _summary_list_list_float64(_result_mat_identity)
    print("MOJO_RESULT kalman::mat_identity", _summary_mat_identity)
    var _acc_mat_mul: Float64 = 0.0
    var _t0_mat_mul = perf_counter_ns()
    for _ in range(N):
        var _r_mat_mul = mat_mul([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_mul += Float64(len(_r_mat_mul))
    var _t1_mat_mul = perf_counter_ns()
    var _ns_mat_mul = Float64(_t1_mat_mul - _t0_mat_mul) / Float64(N)
    print("MOJO_TIMING kalman::mat_mul", _ns_mat_mul, _acc_mat_mul)
    var _result_mat_mul = mat_mul([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mat_mul = _summary_list_list_float64(_result_mat_mul)
    print("MOJO_RESULT kalman::mat_mul", _summary_mat_mul)
    var _acc_mat_transpose: Float64 = 0.0
    var _t0_mat_transpose = perf_counter_ns()
    for _ in range(N):
        var _r_mat_transpose = mat_transpose([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_transpose += Float64(len(_r_mat_transpose))
    var _t1_mat_transpose = perf_counter_ns()
    var _ns_mat_transpose = Float64(_t1_mat_transpose - _t0_mat_transpose) / Float64(N)
    print("MOJO_TIMING kalman::mat_transpose", _ns_mat_transpose, _acc_mat_transpose)
    var _result_mat_transpose = mat_transpose([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mat_transpose = _summary_list_list_float64(_result_mat_transpose)
    print("MOJO_RESULT kalman::mat_transpose", _summary_mat_transpose)
    var _acc_mat_add: Float64 = 0.0
    var _t0_mat_add = perf_counter_ns()
    for _ in range(N):
        var _r_mat_add = mat_add([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_add += Float64(len(_r_mat_add))
    var _t1_mat_add = perf_counter_ns()
    var _ns_mat_add = Float64(_t1_mat_add - _t0_mat_add) / Float64(N)
    print("MOJO_TIMING kalman::mat_add", _ns_mat_add, _acc_mat_add)
    var _result_mat_add = mat_add([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mat_add = _summary_list_list_float64(_result_mat_add)
    print("MOJO_RESULT kalman::mat_add", _summary_mat_add)
    var _acc_mat_sub: Float64 = 0.0
    var _t0_mat_sub = perf_counter_ns()
    for _ in range(N):
        var _r_mat_sub = mat_sub([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_sub += Float64(len(_r_mat_sub))
    var _t1_mat_sub = perf_counter_ns()
    var _ns_mat_sub = Float64(_t1_mat_sub - _t0_mat_sub) / Float64(N)
    print("MOJO_TIMING kalman::mat_sub", _ns_mat_sub, _acc_mat_sub)
    var _result_mat_sub = mat_sub([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mat_sub = _summary_list_list_float64(_result_mat_sub)
    print("MOJO_RESULT kalman::mat_sub", _summary_mat_sub)
    var _acc_mat_scale: Float64 = 0.0
    var _t0_mat_scale = perf_counter_ns()
    for _ in range(N):
        var _r_mat_scale = mat_scale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_mat_scale += Float64(len(_r_mat_scale))
    var _t1_mat_scale = perf_counter_ns()
    var _ns_mat_scale = Float64(_t1_mat_scale - _t0_mat_scale) / Float64(N)
    print("MOJO_TIMING kalman::mat_scale", _ns_mat_scale, _acc_mat_scale)
    var _result_mat_scale = mat_scale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_mat_scale = _summary_list_list_float64(_result_mat_scale)
    print("MOJO_RESULT kalman::mat_scale", _summary_mat_scale)
    var _acc_mat_inv_2x2: Float64 = 0.0
    var _t0_mat_inv_2x2 = perf_counter_ns()
    for _ in range(N):
        var _r_mat_inv_2x2 = mat_inv_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_inv_2x2 += Float64(len(_r_mat_inv_2x2))
    var _t1_mat_inv_2x2 = perf_counter_ns()
    var _ns_mat_inv_2x2 = Float64(_t1_mat_inv_2x2 - _t0_mat_inv_2x2) / Float64(N)
    print("MOJO_TIMING kalman::mat_inv_2x2", _ns_mat_inv_2x2, _acc_mat_inv_2x2)
    var _result_mat_inv_2x2 = mat_inv_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mat_inv_2x2 = _summary_list_list_float64(_result_mat_inv_2x2)
    print("MOJO_RESULT kalman::mat_inv_2x2", _summary_mat_inv_2x2)
    var _acc_matvec: Float64 = 0.0
    var _t0_matvec = perf_counter_ns()
    for _ in range(N):
        var _r_matvec = matvec([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_matvec += Float64(len(_r_matvec))
    var _t1_matvec = perf_counter_ns()
    var _ns_matvec = Float64(_t1_matvec - _t0_matvec) / Float64(N)
    print("MOJO_TIMING kalman::matvec", _ns_matvec, _acc_matvec)
    var _result_matvec = matvec([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_matvec = _summary_list_float64(_result_matvec)
    print("MOJO_RESULT kalman::matvec", _summary_matvec)
    var _acc_kalman_smooth_1d: Float64 = 0.0
    var _t0_kalman_smooth_1d = perf_counter_ns()
    for _ in range(N):
        var _r_kalman_smooth_1d = kalman_smooth_1d(_lf5, 0.5, 0.5)
        _acc_kalman_smooth_1d += Float64(len(_r_kalman_smooth_1d))
    var _t1_kalman_smooth_1d = perf_counter_ns()
    var _ns_kalman_smooth_1d = Float64(_t1_kalman_smooth_1d - _t0_kalman_smooth_1d) / Float64(N)
    print("MOJO_TIMING kalman::kalman_smooth_1d", _ns_kalman_smooth_1d, _acc_kalman_smooth_1d)
    var _result_kalman_smooth_1d = kalman_smooth_1d(_lf5, 0.5, 0.5)
    var _summary_kalman_smooth_1d = _summary_list_float64(_result_kalman_smooth_1d)
    print("MOJO_RESULT kalman::kalman_smooth_1d", _summary_kalman_smooth_1d)
