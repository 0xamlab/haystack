"""bench_linalg_ext.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from linalg_ext import mat_norm_frobenius, mat_norm_inf, mat_trace, mat_is_symmetric, mat_is_positive_definite, mat_power_iteration, mat_condition_number, PowerIterResult
from std.time import perf_counter_ns
from linalg import mat_from_list, Matrix

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
    var _acc_mat_norm_inf: Float64 = 0.0
    var _t0_mat_norm_inf = perf_counter_ns()
    for _ in range(N):
        _acc_mat_norm_inf += mat_norm_inf(_mat3)
    var _t1_mat_norm_inf = perf_counter_ns()
    var _ns_mat_norm_inf = Float64(_t1_mat_norm_inf - _t0_mat_norm_inf) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_norm_inf", _ns_mat_norm_inf, _acc_mat_norm_inf)
    var _acc_mat_trace: Float64 = 0.0
    var _t0_mat_trace = perf_counter_ns()
    for _ in range(N):
        _acc_mat_trace += mat_trace(_mat3)
    var _t1_mat_trace = perf_counter_ns()
    var _ns_mat_trace = Float64(_t1_mat_trace - _t0_mat_trace) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_trace", _ns_mat_trace, _acc_mat_trace)
    var _acc_mat_is_symmetric: Float64 = 0.0
    var _t0_mat_is_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_mat_is_symmetric += Float64(mat_is_symmetric(_mat3, 1e-10))
    var _t1_mat_is_symmetric = perf_counter_ns()
    var _ns_mat_is_symmetric = Float64(_t1_mat_is_symmetric - _t0_mat_is_symmetric) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_is_symmetric", _ns_mat_is_symmetric, _acc_mat_is_symmetric)
    var _acc_mat_is_positive_definite: Float64 = 0.0
    var _t0_mat_is_positive_definite = perf_counter_ns()
    for _ in range(N):
        _acc_mat_is_positive_definite += Float64(mat_is_positive_definite(_mat3))
    var _t1_mat_is_positive_definite = perf_counter_ns()
    var _ns_mat_is_positive_definite = Float64(_t1_mat_is_positive_definite - _t0_mat_is_positive_definite) / Float64(N)
    print("MOJO_TIMING linalg_ext::mat_is_positive_definite", _ns_mat_is_positive_definite, _acc_mat_is_positive_definite)
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
