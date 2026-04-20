"""bench_svm_kernel.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from svm_kernel import kernel_linear, kernel_rbf, kernel_polynomial, kernel_sigmoid, kernel_matrix, kernel_center, frobenius_norm, kernel_alignment, is_positive_semidefinite
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

    var _acc_kernel_linear: Float64 = 0.0
    var _t0_kernel_linear = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_linear += kernel_linear(_lf5, _lf5)
    var _t1_kernel_linear = perf_counter_ns()
    var _ns_kernel_linear = Float64(_t1_kernel_linear - _t0_kernel_linear) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_linear", _ns_kernel_linear, _acc_kernel_linear)
    var _acc_kernel_rbf: Float64 = 0.0
    var _t0_kernel_rbf = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_rbf += kernel_rbf(_lf5, _lf5, 0.5)
    var _t1_kernel_rbf = perf_counter_ns()
    var _ns_kernel_rbf = Float64(_t1_kernel_rbf - _t0_kernel_rbf) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_rbf", _ns_kernel_rbf, _acc_kernel_rbf)
    var _acc_kernel_polynomial: Float64 = 0.0
    var _t0_kernel_polynomial = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_polynomial += kernel_polynomial(_lf5, _lf5, 5, 0.5)
    var _t1_kernel_polynomial = perf_counter_ns()
    var _ns_kernel_polynomial = Float64(_t1_kernel_polynomial - _t0_kernel_polynomial) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_polynomial", _ns_kernel_polynomial, _acc_kernel_polynomial)
    var _acc_kernel_sigmoid: Float64 = 0.0
    var _t0_kernel_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_sigmoid += kernel_sigmoid(_lf5, _lf5, 0.5, 0.5)
    var _t1_kernel_sigmoid = perf_counter_ns()
    var _ns_kernel_sigmoid = Float64(_t1_kernel_sigmoid - _t0_kernel_sigmoid) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_sigmoid", _ns_kernel_sigmoid, _acc_kernel_sigmoid)
    var _acc_kernel_matrix: Float64 = 0.0
    var _t0_kernel_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_kernel_matrix = kernel_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 0.5, 5, 0.5)
        _acc_kernel_matrix += Float64(len(_r_kernel_matrix))
    var _t1_kernel_matrix = perf_counter_ns()
    var _ns_kernel_matrix = Float64(_t1_kernel_matrix - _t0_kernel_matrix) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_matrix", _ns_kernel_matrix, _acc_kernel_matrix)
    var _acc_kernel_center: Float64 = 0.0
    var _t0_kernel_center = perf_counter_ns()
    for _ in range(N):
        var _r_kernel_center = kernel_center([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_kernel_center += Float64(len(_r_kernel_center))
    var _t1_kernel_center = perf_counter_ns()
    var _ns_kernel_center = Float64(_t1_kernel_center - _t0_kernel_center) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_center", _ns_kernel_center, _acc_kernel_center)
    var _acc_frobenius_norm: Float64 = 0.0
    var _t0_frobenius_norm = perf_counter_ns()
    for _ in range(N):
        _acc_frobenius_norm += frobenius_norm([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_frobenius_norm = perf_counter_ns()
    var _ns_frobenius_norm = Float64(_t1_frobenius_norm - _t0_frobenius_norm) / Float64(N)
    print("MOJO_TIMING svm_kernel::frobenius_norm", _ns_frobenius_norm, _acc_frobenius_norm)
    var _acc_kernel_alignment: Float64 = 0.0
    var _t0_kernel_alignment = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_alignment += kernel_alignment([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_kernel_alignment = perf_counter_ns()
    var _ns_kernel_alignment = Float64(_t1_kernel_alignment - _t0_kernel_alignment) / Float64(N)
    print("MOJO_TIMING svm_kernel::kernel_alignment", _ns_kernel_alignment, _acc_kernel_alignment)
    var _acc_is_positive_semidefinite: Float64 = 0.0
    var _t0_is_positive_semidefinite = perf_counter_ns()
    for _ in range(N):
        _acc_is_positive_semidefinite += Float64(is_positive_semidefinite([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_is_positive_semidefinite = perf_counter_ns()
    var _ns_is_positive_semidefinite = Float64(_t1_is_positive_semidefinite - _t0_is_positive_semidefinite) / Float64(N)
    print("MOJO_TIMING svm_kernel::is_positive_semidefinite", _ns_is_positive_semidefinite, _acc_is_positive_semidefinite)
