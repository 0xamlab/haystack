"""bench_dimensionality.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dimensionality import column_means, center_data, covariance_matrix, power_iteration, eigenvalue_from_vector, deflate_matrix, pca, PCAResult
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

    var _acc_column_means: Float64 = 0.0
    var _t0_column_means = perf_counter_ns()
    for _ in range(N):
        var _r_column_means = column_means([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_column_means += Float64(len(_r_column_means))
    var _t1_column_means = perf_counter_ns()
    var _ns_column_means = Float64(_t1_column_means - _t0_column_means) / Float64(N)
    print("MOJO_TIMING dimensionality::column_means", _ns_column_means, _acc_column_means)
    var _result_column_means = column_means([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_column_means = _summary_list_float64(_result_column_means)
    print("MOJO_RESULT dimensionality::column_means", _summary_column_means)
    var _acc_center_data: Float64 = 0.0
    var _t0_center_data = perf_counter_ns()
    for _ in range(N):
        var _r_center_data = center_data([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_center_data += Float64(len(_r_center_data))
    var _t1_center_data = perf_counter_ns()
    var _ns_center_data = Float64(_t1_center_data - _t0_center_data) / Float64(N)
    print("MOJO_TIMING dimensionality::center_data", _ns_center_data, _acc_center_data)
    var _result_center_data = center_data([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_center_data = _summary_list_list_float64(_result_center_data)
    print("MOJO_RESULT dimensionality::center_data", _summary_center_data)
    var _acc_covariance_matrix: Float64 = 0.0
    var _t0_covariance_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_covariance_matrix = covariance_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_covariance_matrix += Float64(len(_r_covariance_matrix))
    var _t1_covariance_matrix = perf_counter_ns()
    var _ns_covariance_matrix = Float64(_t1_covariance_matrix - _t0_covariance_matrix) / Float64(N)
    print("MOJO_TIMING dimensionality::covariance_matrix", _ns_covariance_matrix, _acc_covariance_matrix)
    var _result_covariance_matrix = covariance_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_covariance_matrix = _summary_list_list_float64(_result_covariance_matrix)
    print("MOJO_RESULT dimensionality::covariance_matrix", _summary_covariance_matrix)
    var _acc_power_iteration: Float64 = 0.0
    var _t0_power_iteration = perf_counter_ns()
    for _ in range(N):
        var _r_power_iteration = power_iteration([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_power_iteration += Float64(len(_r_power_iteration))
    var _t1_power_iteration = perf_counter_ns()
    var _ns_power_iteration = Float64(_t1_power_iteration - _t0_power_iteration) / Float64(N)
    print("MOJO_TIMING dimensionality::power_iteration", _ns_power_iteration, _acc_power_iteration)
    var _result_power_iteration = power_iteration([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
    var _summary_power_iteration = _summary_list_float64(_result_power_iteration)
    print("MOJO_RESULT dimensionality::power_iteration", _summary_power_iteration)
    var _acc_eigenvalue_from_vector: Float64 = 0.0
    var _t0_eigenvalue_from_vector = perf_counter_ns()
    for _ in range(N):
        _acc_eigenvalue_from_vector += eigenvalue_from_vector([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _t1_eigenvalue_from_vector = perf_counter_ns()
    var _ns_eigenvalue_from_vector = Float64(_t1_eigenvalue_from_vector - _t0_eigenvalue_from_vector) / Float64(N)
    print("MOJO_TIMING dimensionality::eigenvalue_from_vector", _ns_eigenvalue_from_vector, _acc_eigenvalue_from_vector)
    var _result_eigenvalue_from_vector = eigenvalue_from_vector([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_eigenvalue_from_vector = _summary_float64(_result_eigenvalue_from_vector)
    print("MOJO_RESULT dimensionality::eigenvalue_from_vector", _summary_eigenvalue_from_vector)
    var _acc_deflate_matrix: Float64 = 0.0
    var _t0_deflate_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_deflate_matrix = deflate_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5, _lf5)
        _acc_deflate_matrix += Float64(len(_r_deflate_matrix))
    var _t1_deflate_matrix = perf_counter_ns()
    var _ns_deflate_matrix = Float64(_t1_deflate_matrix - _t0_deflate_matrix) / Float64(N)
    print("MOJO_TIMING dimensionality::deflate_matrix", _ns_deflate_matrix, _acc_deflate_matrix)
    var _result_deflate_matrix = deflate_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5, _lf5)
    var _summary_deflate_matrix = _summary_list_list_float64(_result_deflate_matrix)
    print("MOJO_RESULT dimensionality::deflate_matrix", _summary_deflate_matrix)
    var _keeper_pca = List[PCAResult]()
    _keeper_pca.append(pca([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 2))
    var _acc_pca: Float64 = 0.0
    var _t0_pca = perf_counter_ns()
    for _ in range(N):
        _keeper_pca[0] = pca([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 2)
        _acc_pca += Float64(len(_keeper_pca))
    var _t1_pca = perf_counter_ns()
    var _ns_pca = Float64(_t1_pca - _t0_pca) / Float64(N)
    print("MOJO_TIMING dimensionality::pca", _ns_pca, _acc_pca)
