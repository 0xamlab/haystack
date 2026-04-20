"""bench_kalman.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from kalman import mat_identity, mat_mul, mat_transpose, mat_add, mat_sub, mat_scale, mat_inv_2x2, matvec, kalman_smooth_1d
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

    var _acc_mat_identity: Float64 = 0.0
    var _t0_mat_identity = perf_counter_ns()
    for _ in range(N):
        var _r_mat_identity = mat_identity(5)
        _acc_mat_identity += Float64(len(_r_mat_identity))
    var _t1_mat_identity = perf_counter_ns()
    var _ns_mat_identity = Float64(_t1_mat_identity - _t0_mat_identity) / Float64(N)
    print("MOJO_TIMING kalman::mat_identity", _ns_mat_identity, _acc_mat_identity)
    var _acc_mat_mul: Float64 = 0.0
    var _t0_mat_mul = perf_counter_ns()
    for _ in range(N):
        var _r_mat_mul = mat_mul([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_mul += Float64(len(_r_mat_mul))
    var _t1_mat_mul = perf_counter_ns()
    var _ns_mat_mul = Float64(_t1_mat_mul - _t0_mat_mul) / Float64(N)
    print("MOJO_TIMING kalman::mat_mul", _ns_mat_mul, _acc_mat_mul)
    var _acc_mat_transpose: Float64 = 0.0
    var _t0_mat_transpose = perf_counter_ns()
    for _ in range(N):
        var _r_mat_transpose = mat_transpose([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_transpose += Float64(len(_r_mat_transpose))
    var _t1_mat_transpose = perf_counter_ns()
    var _ns_mat_transpose = Float64(_t1_mat_transpose - _t0_mat_transpose) / Float64(N)
    print("MOJO_TIMING kalman::mat_transpose", _ns_mat_transpose, _acc_mat_transpose)
    var _acc_mat_add: Float64 = 0.0
    var _t0_mat_add = perf_counter_ns()
    for _ in range(N):
        var _r_mat_add = mat_add([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_add += Float64(len(_r_mat_add))
    var _t1_mat_add = perf_counter_ns()
    var _ns_mat_add = Float64(_t1_mat_add - _t0_mat_add) / Float64(N)
    print("MOJO_TIMING kalman::mat_add", _ns_mat_add, _acc_mat_add)
    var _acc_mat_sub: Float64 = 0.0
    var _t0_mat_sub = perf_counter_ns()
    for _ in range(N):
        var _r_mat_sub = mat_sub([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_sub += Float64(len(_r_mat_sub))
    var _t1_mat_sub = perf_counter_ns()
    var _ns_mat_sub = Float64(_t1_mat_sub - _t0_mat_sub) / Float64(N)
    print("MOJO_TIMING kalman::mat_sub", _ns_mat_sub, _acc_mat_sub)
    var _acc_mat_scale: Float64 = 0.0
    var _t0_mat_scale = perf_counter_ns()
    for _ in range(N):
        var _r_mat_scale = mat_scale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_mat_scale += Float64(len(_r_mat_scale))
    var _t1_mat_scale = perf_counter_ns()
    var _ns_mat_scale = Float64(_t1_mat_scale - _t0_mat_scale) / Float64(N)
    print("MOJO_TIMING kalman::mat_scale", _ns_mat_scale, _acc_mat_scale)
    var _acc_mat_inv_2x2: Float64 = 0.0
    var _t0_mat_inv_2x2 = perf_counter_ns()
    for _ in range(N):
        var _r_mat_inv_2x2 = mat_inv_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_mat_inv_2x2 += Float64(len(_r_mat_inv_2x2))
    var _t1_mat_inv_2x2 = perf_counter_ns()
    var _ns_mat_inv_2x2 = Float64(_t1_mat_inv_2x2 - _t0_mat_inv_2x2) / Float64(N)
    print("MOJO_TIMING kalman::mat_inv_2x2", _ns_mat_inv_2x2, _acc_mat_inv_2x2)
    var _acc_matvec: Float64 = 0.0
    var _t0_matvec = perf_counter_ns()
    for _ in range(N):
        var _r_matvec = matvec([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_matvec += Float64(len(_r_matvec))
    var _t1_matvec = perf_counter_ns()
    var _ns_matvec = Float64(_t1_matvec - _t0_matvec) / Float64(N)
    print("MOJO_TIMING kalman::matvec", _ns_matvec, _acc_matvec)
    var _acc_kalman_smooth_1d: Float64 = 0.0
    var _t0_kalman_smooth_1d = perf_counter_ns()
    for _ in range(N):
        var _r_kalman_smooth_1d = kalman_smooth_1d(_lf5, 0.5, 0.5)
        _acc_kalman_smooth_1d += Float64(len(_r_kalman_smooth_1d))
    var _t1_kalman_smooth_1d = perf_counter_ns()
    var _ns_kalman_smooth_1d = Float64(_t1_kalman_smooth_1d - _t0_kalman_smooth_1d) / Float64(N)
    print("MOJO_TIMING kalman::kalman_smooth_1d", _ns_kalman_smooth_1d, _acc_kalman_smooth_1d)
