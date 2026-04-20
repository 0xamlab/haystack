"""bench_matrix_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from matrix_ops import kronecker_product, hadamard_product, matrix_power, outer_product, matrix_exp_approx, vec, unvec, matrix_norm_1, matrix_norm_inf, commutator, is_orthogonal, gram_schmidt
from std.time import perf_counter_ns

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
    var _acc_hadamard_product: Float64 = 0.0
    var _t0_hadamard_product = perf_counter_ns()
    for _ in range(N):
        var _r_hadamard_product = hadamard_product([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_hadamard_product += Float64(len(_r_hadamard_product))
    var _t1_hadamard_product = perf_counter_ns()
    var _ns_hadamard_product = Float64(_t1_hadamard_product - _t0_hadamard_product) / Float64(N)
    print("MOJO_TIMING matrix_ops::hadamard_product", _ns_hadamard_product, _acc_hadamard_product)
    var _acc_matrix_power: Float64 = 0.0
    var _t0_matrix_power = perf_counter_ns()
    for _ in range(N):
        var _r_matrix_power = matrix_power([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_matrix_power += Float64(len(_r_matrix_power))
    var _t1_matrix_power = perf_counter_ns()
    var _ns_matrix_power = Float64(_t1_matrix_power - _t0_matrix_power) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_power", _ns_matrix_power, _acc_matrix_power)
    var _acc_outer_product: Float64 = 0.0
    var _t0_outer_product = perf_counter_ns()
    for _ in range(N):
        var _r_outer_product = outer_product(_lf5, _lf5)
        _acc_outer_product += Float64(len(_r_outer_product))
    var _t1_outer_product = perf_counter_ns()
    var _ns_outer_product = Float64(_t1_outer_product - _t0_outer_product) / Float64(N)
    print("MOJO_TIMING matrix_ops::outer_product", _ns_outer_product, _acc_outer_product)
    var _acc_matrix_exp_approx: Float64 = 0.0
    var _t0_matrix_exp_approx = perf_counter_ns()
    for _ in range(N):
        var _r_matrix_exp_approx = matrix_exp_approx([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_matrix_exp_approx += Float64(len(_r_matrix_exp_approx))
    var _t1_matrix_exp_approx = perf_counter_ns()
    var _ns_matrix_exp_approx = Float64(_t1_matrix_exp_approx - _t0_matrix_exp_approx) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_exp_approx", _ns_matrix_exp_approx, _acc_matrix_exp_approx)
    var _acc_vec: Float64 = 0.0
    var _t0_vec = perf_counter_ns()
    for _ in range(N):
        var _r_vec = vec([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_vec += Float64(len(_r_vec))
    var _t1_vec = perf_counter_ns()
    var _ns_vec = Float64(_t1_vec - _t0_vec) / Float64(N)
    print("MOJO_TIMING matrix_ops::vec", _ns_vec, _acc_vec)
    var _acc_unvec: Float64 = 0.0
    var _t0_unvec = perf_counter_ns()
    for _ in range(N):
        var _r_unvec = unvec(_lf5, 5, 5)
        _acc_unvec += Float64(len(_r_unvec))
    var _t1_unvec = perf_counter_ns()
    var _ns_unvec = Float64(_t1_unvec - _t0_unvec) / Float64(N)
    print("MOJO_TIMING matrix_ops::unvec", _ns_unvec, _acc_unvec)
    var _acc_matrix_norm_1: Float64 = 0.0
    var _t0_matrix_norm_1 = perf_counter_ns()
    for _ in range(N):
        _acc_matrix_norm_1 += matrix_norm_1([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_matrix_norm_1 = perf_counter_ns()
    var _ns_matrix_norm_1 = Float64(_t1_matrix_norm_1 - _t0_matrix_norm_1) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_norm_1", _ns_matrix_norm_1, _acc_matrix_norm_1)
    var _acc_matrix_norm_inf: Float64 = 0.0
    var _t0_matrix_norm_inf = perf_counter_ns()
    for _ in range(N):
        _acc_matrix_norm_inf += matrix_norm_inf([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_matrix_norm_inf = perf_counter_ns()
    var _ns_matrix_norm_inf = Float64(_t1_matrix_norm_inf - _t0_matrix_norm_inf) / Float64(N)
    print("MOJO_TIMING matrix_ops::matrix_norm_inf", _ns_matrix_norm_inf, _acc_matrix_norm_inf)
    var _acc_commutator: Float64 = 0.0
    var _t0_commutator = perf_counter_ns()
    for _ in range(N):
        var _r_commutator = commutator([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_commutator += Float64(len(_r_commutator))
    var _t1_commutator = perf_counter_ns()
    var _ns_commutator = Float64(_t1_commutator - _t0_commutator) / Float64(N)
    print("MOJO_TIMING matrix_ops::commutator", _ns_commutator, _acc_commutator)
    var _acc_is_orthogonal: Float64 = 0.0
    var _t0_is_orthogonal = perf_counter_ns()
    for _ in range(N):
        _acc_is_orthogonal += Float64(is_orthogonal([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _t1_is_orthogonal = perf_counter_ns()
    var _ns_is_orthogonal = Float64(_t1_is_orthogonal - _t0_is_orthogonal) / Float64(N)
    print("MOJO_TIMING matrix_ops::is_orthogonal", _ns_is_orthogonal, _acc_is_orthogonal)
    var _acc_gram_schmidt: Float64 = 0.0
    var _t0_gram_schmidt = perf_counter_ns()
    for _ in range(N):
        var _r_gram_schmidt = gram_schmidt([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_gram_schmidt += Float64(len(_r_gram_schmidt))
    var _t1_gram_schmidt = perf_counter_ns()
    var _ns_gram_schmidt = Float64(_t1_gram_schmidt - _t0_gram_schmidt) / Float64(N)
    print("MOJO_TIMING matrix_ops::gram_schmidt", _ns_gram_schmidt, _acc_gram_schmidt)
