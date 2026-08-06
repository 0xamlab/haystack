"""bench_matrix_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from matrix_ops import kronecker_product, hadamard_product, matrix_power, outer_product, matrix_exp_approx, vec, unvec, matrix_norm_1, matrix_norm_inf, commutator, is_orthogonal, gram_schmidt
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

    var _acc_kronecker_product: Float64 = 0.0
    var _t0_kronecker_product = perf_counter_ns()
    for _ in range(N):
        var _r_kronecker_product = kronecker_product([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_kronecker_product += Float64(len(_r_kronecker_product))
    var _t1_kronecker_product = perf_counter_ns()
    var _ns_kronecker_product = Float64(_t1_kronecker_product - _t0_kronecker_product) / Float64(N)
    print("MOJO_TIMING matrix_ops::kronecker_product", _ns_kronecker_product, _acc_kronecker_product)
    var _result_kronecker_product = kronecker_product([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_kronecker_product = _summary_list_list_float64(_result_kronecker_product)
    print("MOJO_RESULT matrix_ops::kronecker_product", _summary_kronecker_product)
    var _acc_hadamard_product: Float64 = 0.0
    var _t0_hadamard_product = perf_counter_ns()
    for _ in range(N):
        var _r_hadamard_product = hadamard_product([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_hadamard_product += Float64(len(_r_hadamard_product))
    var _t1_hadamard_product = perf_counter_ns()
    var _ns_hadamard_product = Float64(_t1_hadamard_product - _t0_hadamard_product) / Float64(N)
    print("MOJO_TIMING matrix_ops::hadamard_product", _ns_hadamard_product, _acc_hadamard_product)
    var _result_hadamard_product = hadamard_product([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_hadamard_product = _summary_list_list_float64(_result_hadamard_product)
    print("MOJO_RESULT matrix_ops::hadamard_product", _summary_hadamard_product)
    var _acc_matrix_power: Float64 = 0.0
    var _t0_matrix_power = perf_counter_ns()
    for _ in range(N):
        var _r_matrix_power = matrix_power([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_matrix_power += Float64(len(_r_matrix_power))
    var _t1_matrix_power = perf_counter_ns()
    var _ns_matrix_power = Float64(_t1_matrix_power - _t0_matrix_power) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_power", _ns_matrix_power, _acc_matrix_power)
    var _result_matrix_power = matrix_power([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
    var _summary_matrix_power = _summary_list_list_float64(_result_matrix_power)
    print("MOJO_RESULT matrix_ops::matrix_power", _summary_matrix_power)
    var _acc_outer_product: Float64 = 0.0
    var _t0_outer_product = perf_counter_ns()
    for _ in range(N):
        var _r_outer_product = outer_product(_lf5, _lf5)
        _acc_outer_product += Float64(len(_r_outer_product))
    var _t1_outer_product = perf_counter_ns()
    var _ns_outer_product = Float64(_t1_outer_product - _t0_outer_product) / Float64(N)
    print("MOJO_TIMING matrix_ops::outer_product", _ns_outer_product, _acc_outer_product)
    var _result_outer_product = outer_product(_lf5, _lf5)
    var _summary_outer_product = _summary_list_list_float64(_result_outer_product)
    print("MOJO_RESULT matrix_ops::outer_product", _summary_outer_product)
    var _acc_matrix_exp_approx: Float64 = 0.0
    var _t0_matrix_exp_approx = perf_counter_ns()
    for _ in range(N):
        var _r_matrix_exp_approx = matrix_exp_approx([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_matrix_exp_approx += Float64(len(_r_matrix_exp_approx))
    var _t1_matrix_exp_approx = perf_counter_ns()
    var _ns_matrix_exp_approx = Float64(_t1_matrix_exp_approx - _t0_matrix_exp_approx) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_exp_approx", _ns_matrix_exp_approx, _acc_matrix_exp_approx)
    var _result_matrix_exp_approx = matrix_exp_approx([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
    var _summary_matrix_exp_approx = _summary_list_list_float64(_result_matrix_exp_approx)
    print("MOJO_RESULT matrix_ops::matrix_exp_approx", _summary_matrix_exp_approx)
    var _acc_vec: Float64 = 0.0
    var _t0_vec = perf_counter_ns()
    for _ in range(N):
        var _r_vec = vec([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_vec += Float64(len(_r_vec))
    var _t1_vec = perf_counter_ns()
    var _ns_vec = Float64(_t1_vec - _t0_vec) / Float64(N)
    print("MOJO_TIMING matrix_ops::vec", _ns_vec, _acc_vec)
    var _result_vec = vec([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_vec = _summary_list_float64(_result_vec)
    print("MOJO_RESULT matrix_ops::vec", _summary_vec)
    var _acc_unvec: Float64 = 0.0
    var _t0_unvec = perf_counter_ns()
    for _ in range(N):
        var _r_unvec = unvec(_lf5, 5, 5)
        _acc_unvec += Float64(len(_r_unvec))
    var _t1_unvec = perf_counter_ns()
    var _ns_unvec = Float64(_t1_unvec - _t0_unvec) / Float64(N)
    print("MOJO_TIMING matrix_ops::unvec", _ns_unvec, _acc_unvec)
    var _result_unvec = unvec(_lf5, 5, 5)
    var _summary_unvec = _summary_list_list_float64(_result_unvec)
    print("MOJO_RESULT matrix_ops::unvec", _summary_unvec)
    var _acc_matrix_norm_1: Float64 = 0.0
    var _t0_matrix_norm_1 = perf_counter_ns()
    for _ in range(N):
        _acc_matrix_norm_1 += matrix_norm_1([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_matrix_norm_1 = perf_counter_ns()
    var _ns_matrix_norm_1 = Float64(_t1_matrix_norm_1 - _t0_matrix_norm_1) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_norm_1", _ns_matrix_norm_1, _acc_matrix_norm_1)
    var _result_matrix_norm_1 = matrix_norm_1([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_matrix_norm_1 = _summary_float64(_result_matrix_norm_1)
    print("MOJO_RESULT matrix_ops::matrix_norm_1", _summary_matrix_norm_1)
    var _acc_matrix_norm_inf: Float64 = 0.0
    var _t0_matrix_norm_inf = perf_counter_ns()
    for _ in range(N):
        _acc_matrix_norm_inf += matrix_norm_inf([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_matrix_norm_inf = perf_counter_ns()
    var _ns_matrix_norm_inf = Float64(_t1_matrix_norm_inf - _t0_matrix_norm_inf) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_norm_inf", _ns_matrix_norm_inf, _acc_matrix_norm_inf)
    var _result_matrix_norm_inf = matrix_norm_inf([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_matrix_norm_inf = _summary_float64(_result_matrix_norm_inf)
    print("MOJO_RESULT matrix_ops::matrix_norm_inf", _summary_matrix_norm_inf)
    var _acc_commutator: Float64 = 0.0
    var _t0_commutator = perf_counter_ns()
    for _ in range(N):
        var _r_commutator = commutator([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_commutator += Float64(len(_r_commutator))
    var _t1_commutator = perf_counter_ns()
    var _ns_commutator = Float64(_t1_commutator - _t0_commutator) / Float64(N)
    print("MOJO_TIMING matrix_ops::commutator", _ns_commutator, _acc_commutator)
    var _result_commutator = commutator([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_commutator = _summary_list_list_float64(_result_commutator)
    print("MOJO_RESULT matrix_ops::commutator", _summary_commutator)
    var _acc_is_orthogonal: Float64 = 0.0
    var _t0_is_orthogonal = perf_counter_ns()
    for _ in range(N):
        _acc_is_orthogonal += Float64(is_orthogonal([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _t1_is_orthogonal = perf_counter_ns()
    var _ns_is_orthogonal = Float64(_t1_is_orthogonal - _t0_is_orthogonal) / Float64(N)
    print("MOJO_TIMING matrix_ops::is_orthogonal", _ns_is_orthogonal, _acc_is_orthogonal)
    var _result_is_orthogonal = is_orthogonal([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_is_orthogonal = _summary_bool(_result_is_orthogonal)
    print("MOJO_RESULT matrix_ops::is_orthogonal", _summary_is_orthogonal)
    var _acc_gram_schmidt: Float64 = 0.0
    var _t0_gram_schmidt = perf_counter_ns()
    for _ in range(N):
        var _r_gram_schmidt = gram_schmidt([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_gram_schmidt += Float64(len(_r_gram_schmidt))
    var _t1_gram_schmidt = perf_counter_ns()
    var _ns_gram_schmidt = Float64(_t1_gram_schmidt - _t0_gram_schmidt) / Float64(N)
    print("MOJO_TIMING matrix_ops::gram_schmidt", _ns_gram_schmidt, _acc_gram_schmidt)
    var _result_gram_schmidt = gram_schmidt([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_gram_schmidt = _summary_list_list_float64(_result_gram_schmidt)
    print("MOJO_RESULT matrix_ops::gram_schmidt", _summary_gram_schmidt)
