"""bench_matrix_decomp.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from matrix_decomp import det_2x2, det_3x3, trace, is_symmetric, cholesky, is_positive_definite, lu_decompose, eigen_2x2, forward_substitution, back_substitution, solve_lu
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

    var _acc_det_2x2: Float64 = 0.0
    var _t0_det_2x2 = perf_counter_ns()
    for _ in range(N):
        _acc_det_2x2 += det_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_det_2x2 = perf_counter_ns()
    var _ns_det_2x2 = Float64(_t1_det_2x2 - _t0_det_2x2) / Float64(N)
    print("MOJO_TIMING matrix_decomp::det_2x2", _ns_det_2x2, _acc_det_2x2)
    var _result_det_2x2 = det_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_det_2x2 = _summary_float64(_result_det_2x2)
    print("MOJO_RESULT matrix_decomp::det_2x2", _summary_det_2x2)
    var _acc_det_3x3: Float64 = 0.0
    var _t0_det_3x3 = perf_counter_ns()
    for _ in range(N):
        _acc_det_3x3 += det_3x3([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_det_3x3 = perf_counter_ns()
    var _ns_det_3x3 = Float64(_t1_det_3x3 - _t0_det_3x3) / Float64(N)
    print("MOJO_TIMING matrix_decomp::det_3x3", _ns_det_3x3, _acc_det_3x3)
    var _result_det_3x3 = det_3x3([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_det_3x3 = _summary_float64(_result_det_3x3)
    print("MOJO_RESULT matrix_decomp::det_3x3", _summary_det_3x3)
    var _acc_trace: Float64 = 0.0
    var _t0_trace = perf_counter_ns()
    for _ in range(N):
        _acc_trace += trace([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_trace = perf_counter_ns()
    var _ns_trace = Float64(_t1_trace - _t0_trace) / Float64(N)
    print("MOJO_TIMING matrix_decomp::trace", _ns_trace, _acc_trace)
    var _result_trace = trace([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_trace = _summary_float64(_result_trace)
    print("MOJO_RESULT matrix_decomp::trace", _summary_trace)
    var _acc_is_symmetric: Float64 = 0.0
    var _t0_is_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_is_symmetric += Float64(is_symmetric([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _t1_is_symmetric = perf_counter_ns()
    var _ns_is_symmetric = Float64(_t1_is_symmetric - _t0_is_symmetric) / Float64(N)
    print("MOJO_TIMING matrix_decomp::is_symmetric", _ns_is_symmetric, _acc_is_symmetric)
    var _result_is_symmetric = is_symmetric([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_is_symmetric = _summary_bool(_result_is_symmetric)
    print("MOJO_RESULT matrix_decomp::is_symmetric", _summary_is_symmetric)
    var _acc_cholesky: Float64 = 0.0
    var _t0_cholesky = perf_counter_ns()
    for _ in range(N):
        var _r_cholesky = cholesky([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_cholesky += Float64(len(_r_cholesky))
    var _t1_cholesky = perf_counter_ns()
    var _ns_cholesky = Float64(_t1_cholesky - _t0_cholesky) / Float64(N)
    print("MOJO_TIMING matrix_decomp::cholesky", _ns_cholesky, _acc_cholesky)
    var _result_cholesky = cholesky([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_cholesky = _summary_list_list_float64(_result_cholesky)
    print("MOJO_RESULT matrix_decomp::cholesky", _summary_cholesky)
    var _acc_is_positive_definite: Float64 = 0.0
    var _t0_is_positive_definite = perf_counter_ns()
    for _ in range(N):
        _acc_is_positive_definite += Float64(is_positive_definite([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_is_positive_definite = perf_counter_ns()
    var _ns_is_positive_definite = Float64(_t1_is_positive_definite - _t0_is_positive_definite) / Float64(N)
    print("MOJO_TIMING matrix_decomp::is_positive_definite", _ns_is_positive_definite, _acc_is_positive_definite)
    var _result_is_positive_definite = is_positive_definite([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_is_positive_definite = _summary_bool(_result_is_positive_definite)
    print("MOJO_RESULT matrix_decomp::is_positive_definite", _summary_is_positive_definite)
    var _acc_lu_decompose: Float64 = 0.0
    var _t0_lu_decompose = perf_counter_ns()
    for _ in range(N):
        var _r_lu_decompose = lu_decompose([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_lu_decompose += Float64(len(_r_lu_decompose))
    var _t1_lu_decompose = perf_counter_ns()
    var _ns_lu_decompose = Float64(_t1_lu_decompose - _t0_lu_decompose) / Float64(N)
    print("MOJO_TIMING matrix_decomp::lu_decompose", _ns_lu_decompose, _acc_lu_decompose)
    var _acc_eigen_2x2: Float64 = 0.0
    var _t0_eigen_2x2 = perf_counter_ns()
    for _ in range(N):
        var _r_eigen_2x2 = eigen_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_eigen_2x2 += Float64(len(_r_eigen_2x2))
    var _t1_eigen_2x2 = perf_counter_ns()
    var _ns_eigen_2x2 = Float64(_t1_eigen_2x2 - _t0_eigen_2x2) / Float64(N)
    print("MOJO_TIMING matrix_decomp::eigen_2x2", _ns_eigen_2x2, _acc_eigen_2x2)
    var _result_eigen_2x2 = eigen_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_eigen_2x2 = _summary_list_list_float64(_result_eigen_2x2)
    print("MOJO_RESULT matrix_decomp::eigen_2x2", _summary_eigen_2x2)
    var _acc_forward_substitution: Float64 = 0.0
    var _t0_forward_substitution = perf_counter_ns()
    for _ in range(N):
        var _r_forward_substitution = forward_substitution([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_forward_substitution += Float64(len(_r_forward_substitution))
    var _t1_forward_substitution = perf_counter_ns()
    var _ns_forward_substitution = Float64(_t1_forward_substitution - _t0_forward_substitution) / Float64(N)
    print("MOJO_TIMING matrix_decomp::forward_substitution", _ns_forward_substitution, _acc_forward_substitution)
    var _result_forward_substitution = forward_substitution([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_forward_substitution = _summary_list_float64(_result_forward_substitution)
    print("MOJO_RESULT matrix_decomp::forward_substitution", _summary_forward_substitution)
    var _acc_back_substitution: Float64 = 0.0
    var _t0_back_substitution = perf_counter_ns()
    for _ in range(N):
        var _r_back_substitution = back_substitution([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_back_substitution += Float64(len(_r_back_substitution))
    var _t1_back_substitution = perf_counter_ns()
    var _ns_back_substitution = Float64(_t1_back_substitution - _t0_back_substitution) / Float64(N)
    print("MOJO_TIMING matrix_decomp::back_substitution", _ns_back_substitution, _acc_back_substitution)
    var _result_back_substitution = back_substitution([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_back_substitution = _summary_list_float64(_result_back_substitution)
    print("MOJO_RESULT matrix_decomp::back_substitution", _summary_back_substitution)
    var _acc_solve_lu: Float64 = 0.0
    var _t0_solve_lu = perf_counter_ns()
    for _ in range(N):
        var _r_solve_lu = solve_lu([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_solve_lu += Float64(len(_r_solve_lu))
    var _t1_solve_lu = perf_counter_ns()
    var _ns_solve_lu = Float64(_t1_solve_lu - _t0_solve_lu) / Float64(N)
    print("MOJO_TIMING matrix_decomp::solve_lu", _ns_solve_lu, _acc_solve_lu)
    var _result_solve_lu = solve_lu([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_solve_lu = _summary_list_float64(_result_solve_lu)
    print("MOJO_RESULT matrix_decomp::solve_lu", _summary_solve_lu)
