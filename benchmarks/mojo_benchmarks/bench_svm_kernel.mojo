"""bench_svm_kernel.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from svm_kernel import kernel_linear, kernel_rbf, kernel_polynomial, kernel_sigmoid, kernel_matrix, kernel_center, frobenius_norm, kernel_alignment, is_positive_semidefinite
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

    var _acc_kernel_linear: Float64 = 0.0
    var _t0_kernel_linear = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_linear += kernel_linear(_lf5, _lf5)
    var _t1_kernel_linear = perf_counter_ns()
    var _ns_kernel_linear = Float64(_t1_kernel_linear - _t0_kernel_linear) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_linear", _ns_kernel_linear, _acc_kernel_linear)
    var _result_kernel_linear = kernel_linear(_lf5, _lf5)
    var _summary_kernel_linear = _summary_float64(_result_kernel_linear)
    print("MOJO_RESULT svm_kernel::kernel_linear", _summary_kernel_linear)
    var _acc_kernel_rbf: Float64 = 0.0
    var _t0_kernel_rbf = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_rbf += kernel_rbf(_lf5, _lf5, 0.5)
    var _t1_kernel_rbf = perf_counter_ns()
    var _ns_kernel_rbf = Float64(_t1_kernel_rbf - _t0_kernel_rbf) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_rbf", _ns_kernel_rbf, _acc_kernel_rbf)
    var _result_kernel_rbf = kernel_rbf(_lf5, _lf5, 0.5)
    var _summary_kernel_rbf = _summary_float64(_result_kernel_rbf)
    print("MOJO_RESULT svm_kernel::kernel_rbf", _summary_kernel_rbf)
    var _acc_kernel_polynomial: Float64 = 0.0
    var _t0_kernel_polynomial = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_polynomial += kernel_polynomial(_lf5, _lf5, 5, 0.5)
    var _t1_kernel_polynomial = perf_counter_ns()
    var _ns_kernel_polynomial = Float64(_t1_kernel_polynomial - _t0_kernel_polynomial) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_polynomial", _ns_kernel_polynomial, _acc_kernel_polynomial)
    var _result_kernel_polynomial = kernel_polynomial(_lf5, _lf5, 5, 0.5)
    var _summary_kernel_polynomial = _summary_float64(_result_kernel_polynomial)
    print("MOJO_RESULT svm_kernel::kernel_polynomial", _summary_kernel_polynomial)
    var _acc_kernel_sigmoid: Float64 = 0.0
    var _t0_kernel_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_sigmoid += kernel_sigmoid(_lf5, _lf5, 0.5, 0.5)
    var _t1_kernel_sigmoid = perf_counter_ns()
    var _ns_kernel_sigmoid = Float64(_t1_kernel_sigmoid - _t0_kernel_sigmoid) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_sigmoid", _ns_kernel_sigmoid, _acc_kernel_sigmoid)
    var _result_kernel_sigmoid = kernel_sigmoid(_lf5, _lf5, 0.5, 0.5)
    var _summary_kernel_sigmoid = _summary_float64(_result_kernel_sigmoid)
    print("MOJO_RESULT svm_kernel::kernel_sigmoid", _summary_kernel_sigmoid)
    var _acc_kernel_matrix: Float64 = 0.0
    var _t0_kernel_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_kernel_matrix = kernel_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 0.5, 5, 0.5)
        _acc_kernel_matrix += Float64(len(_r_kernel_matrix))
    var _t1_kernel_matrix = perf_counter_ns()
    var _ns_kernel_matrix = Float64(_t1_kernel_matrix - _t0_kernel_matrix) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_matrix", _ns_kernel_matrix, _acc_kernel_matrix)
    var _result_kernel_matrix = kernel_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 0.5, 5, 0.5)
    var _summary_kernel_matrix = _summary_list_list_float64(_result_kernel_matrix)
    print("MOJO_RESULT svm_kernel::kernel_matrix", _summary_kernel_matrix)
    var _acc_kernel_center: Float64 = 0.0
    var _t0_kernel_center = perf_counter_ns()
    for _ in range(N):
        var _r_kernel_center = kernel_center([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_kernel_center += Float64(len(_r_kernel_center))
    var _t1_kernel_center = perf_counter_ns()
    var _ns_kernel_center = Float64(_t1_kernel_center - _t0_kernel_center) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_center", _ns_kernel_center, _acc_kernel_center)
    var _result_kernel_center = kernel_center([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_kernel_center = _summary_list_list_float64(_result_kernel_center)
    print("MOJO_RESULT svm_kernel::kernel_center", _summary_kernel_center)
    var _acc_frobenius_norm: Float64 = 0.0
    var _t0_frobenius_norm = perf_counter_ns()
    for _ in range(N):
        _acc_frobenius_norm += frobenius_norm([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_frobenius_norm = perf_counter_ns()
    var _ns_frobenius_norm = Float64(_t1_frobenius_norm - _t0_frobenius_norm) / Float64(N)
    print("MOJO_TIMING svm_kernel::frobenius_norm", _ns_frobenius_norm, _acc_frobenius_norm)
    var _result_frobenius_norm = frobenius_norm([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_frobenius_norm = _summary_float64(_result_frobenius_norm)
    print("MOJO_RESULT svm_kernel::frobenius_norm", _summary_frobenius_norm)
    var _acc_kernel_alignment: Float64 = 0.0
    var _t0_kernel_alignment = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_alignment += kernel_alignment([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_kernel_alignment = perf_counter_ns()
    var _ns_kernel_alignment = Float64(_t1_kernel_alignment - _t0_kernel_alignment) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_alignment", _ns_kernel_alignment, _acc_kernel_alignment)
    var _result_kernel_alignment = kernel_alignment([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_kernel_alignment = _summary_float64(_result_kernel_alignment)
    print("MOJO_RESULT svm_kernel::kernel_alignment", _summary_kernel_alignment)
    var _acc_is_positive_semidefinite: Float64 = 0.0
    var _t0_is_positive_semidefinite = perf_counter_ns()
    for _ in range(N):
        _acc_is_positive_semidefinite += Float64(is_positive_semidefinite([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_is_positive_semidefinite = perf_counter_ns()
    var _ns_is_positive_semidefinite = Float64(_t1_is_positive_semidefinite - _t0_is_positive_semidefinite) / Float64(N)
    print("MOJO_TIMING svm_kernel::is_positive_semidefinite", _ns_is_positive_semidefinite, _acc_is_positive_semidefinite)
    var _result_is_positive_semidefinite = is_positive_semidefinite([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_is_positive_semidefinite = _summary_bool(_result_is_positive_semidefinite)
    print("MOJO_RESULT svm_kernel::is_positive_semidefinite", _summary_is_positive_semidefinite)
