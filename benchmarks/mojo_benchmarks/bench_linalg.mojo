"""bench_linalg.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from linalg import mat_zeros, mat_identity, mat_from_list, mat_add, mat_sub, mat_scale, mat_transpose, mat_mul, mat_det, mat_inv, vec_dot, vec_norm, vec_cross, Matrix
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
    var _mat3_data = List[Float64]()
    _mat3_data.append(1.0); _mat3_data.append(0.0); _mat3_data.append(0.0)
    _mat3_data.append(0.0); _mat3_data.append(2.0); _mat3_data.append(0.0)
    _mat3_data.append(0.0); _mat3_data.append(0.0); _mat3_data.append(3.0)
    var _mat3 = mat_from_list(_mat3_data, 3, 3)
    var N: Int = 10000

    var _keeper_mat_zeros = List[Matrix]()
    _keeper_mat_zeros.append(mat_zeros(5, 5))
    var _acc_mat_zeros: Float64 = 0.0
    var _t0_mat_zeros = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_zeros[0] = mat_zeros(5, 5)
        _acc_mat_zeros += Float64(len(_keeper_mat_zeros))
    var _t1_mat_zeros = perf_counter_ns()
    var _ns_mat_zeros = Float64(_t1_mat_zeros - _t0_mat_zeros) / Float64(N)
    print("MOJO_TIMING linalg::mat_zeros", _ns_mat_zeros, _acc_mat_zeros)
    var _keeper_mat_identity = List[Matrix]()
    _keeper_mat_identity.append(mat_identity(5))
    var _acc_mat_identity: Float64 = 0.0
    var _t0_mat_identity = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_identity[0] = mat_identity(5)
        _acc_mat_identity += Float64(len(_keeper_mat_identity))
    var _t1_mat_identity = perf_counter_ns()
    var _ns_mat_identity = Float64(_t1_mat_identity - _t0_mat_identity) / Float64(N)
    print("MOJO_TIMING linalg::mat_identity", _ns_mat_identity, _acc_mat_identity)
    var _keeper_mat_from_list = List[Matrix]()
    _keeper_mat_from_list.append(mat_from_list(_lf5, 5, 5))
    var _acc_mat_from_list: Float64 = 0.0
    var _t0_mat_from_list = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_from_list[0] = mat_from_list(_lf5, 5, 5)
        _acc_mat_from_list += Float64(len(_keeper_mat_from_list))
    var _t1_mat_from_list = perf_counter_ns()
    var _ns_mat_from_list = Float64(_t1_mat_from_list - _t0_mat_from_list) / Float64(N)
    print("MOJO_TIMING linalg::mat_from_list", _ns_mat_from_list, _acc_mat_from_list)
    var _keeper_mat_add = List[Matrix]()
    _keeper_mat_add.append(mat_add(_mat3, _mat3))
    var _acc_mat_add: Float64 = 0.0
    var _t0_mat_add = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_add[0] = mat_add(_mat3, _mat3)
        _acc_mat_add += Float64(len(_keeper_mat_add))
    var _t1_mat_add = perf_counter_ns()
    var _ns_mat_add = Float64(_t1_mat_add - _t0_mat_add) / Float64(N)
    print("MOJO_TIMING linalg::mat_add", _ns_mat_add, _acc_mat_add)
    var _keeper_mat_sub = List[Matrix]()
    _keeper_mat_sub.append(mat_sub(_mat3, _mat3))
    var _acc_mat_sub: Float64 = 0.0
    var _t0_mat_sub = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_sub[0] = mat_sub(_mat3, _mat3)
        _acc_mat_sub += Float64(len(_keeper_mat_sub))
    var _t1_mat_sub = perf_counter_ns()
    var _ns_mat_sub = Float64(_t1_mat_sub - _t0_mat_sub) / Float64(N)
    print("MOJO_TIMING linalg::mat_sub", _ns_mat_sub, _acc_mat_sub)
    var _keeper_mat_scale = List[Matrix]()
    _keeper_mat_scale.append(mat_scale(_mat3, 2.0))
    var _acc_mat_scale: Float64 = 0.0
    var _t0_mat_scale = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_scale[0] = mat_scale(_mat3, 2.0)
        _acc_mat_scale += Float64(len(_keeper_mat_scale))
    var _t1_mat_scale = perf_counter_ns()
    var _ns_mat_scale = Float64(_t1_mat_scale - _t0_mat_scale) / Float64(N)
    print("MOJO_TIMING linalg::mat_scale", _ns_mat_scale, _acc_mat_scale)
    var _keeper_mat_transpose = List[Matrix]()
    _keeper_mat_transpose.append(mat_transpose(_mat3))
    var _acc_mat_transpose: Float64 = 0.0
    var _t0_mat_transpose = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_transpose[0] = mat_transpose(_mat3)
        _acc_mat_transpose += Float64(len(_keeper_mat_transpose))
    var _t1_mat_transpose = perf_counter_ns()
    var _ns_mat_transpose = Float64(_t1_mat_transpose - _t0_mat_transpose) / Float64(N)
    print("MOJO_TIMING linalg::mat_transpose", _ns_mat_transpose, _acc_mat_transpose)
    var _keeper_mat_mul = List[Matrix]()
    _keeper_mat_mul.append(mat_mul(_mat3, _mat3))
    var _acc_mat_mul: Float64 = 0.0
    var _t0_mat_mul = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_mul[0] = mat_mul(_mat3, _mat3)
        _acc_mat_mul += Float64(len(_keeper_mat_mul))
    var _t1_mat_mul = perf_counter_ns()
    var _ns_mat_mul = Float64(_t1_mat_mul - _t0_mat_mul) / Float64(N)
    print("MOJO_TIMING linalg::mat_mul", _ns_mat_mul, _acc_mat_mul)
    var _acc_mat_det: Float64 = 0.0
    var _t0_mat_det = perf_counter_ns()
    for _ in range(N):
        _acc_mat_det += mat_det(_mat3)
    var _t1_mat_det = perf_counter_ns()
    var _ns_mat_det = Float64(_t1_mat_det - _t0_mat_det) / Float64(N)
    print("MOJO_TIMING linalg::mat_det", _ns_mat_det, _acc_mat_det)
    var _keeper_mat_inv = List[Matrix]()
    _keeper_mat_inv.append(mat_inv(_mat3))
    var _acc_mat_inv: Float64 = 0.0
    var _t0_mat_inv = perf_counter_ns()
    for _ in range(N):
        _keeper_mat_inv[0] = mat_inv(_mat3)
        _acc_mat_inv += Float64(len(_keeper_mat_inv))
    var _t1_mat_inv = perf_counter_ns()
    var _ns_mat_inv = Float64(_t1_mat_inv - _t0_mat_inv) / Float64(N)
    print("MOJO_TIMING linalg::mat_inv", _ns_mat_inv, _acc_mat_inv)
    var _acc_vec_dot: Float64 = 0.0
    var _t0_vec_dot = perf_counter_ns()
    for _ in range(N):
        _acc_vec_dot += vec_dot(_lf5, _lf5)
    var _t1_vec_dot = perf_counter_ns()
    var _ns_vec_dot = Float64(_t1_vec_dot - _t0_vec_dot) / Float64(N)
    print("MOJO_TIMING linalg::vec_dot", _ns_vec_dot, _acc_vec_dot)
    var _acc_vec_norm: Float64 = 0.0
    var _t0_vec_norm = perf_counter_ns()
    for _ in range(N):
        _acc_vec_norm += vec_norm(_lf5)
    var _t1_vec_norm = perf_counter_ns()
    var _ns_vec_norm = Float64(_t1_vec_norm - _t0_vec_norm) / Float64(N)
    print("MOJO_TIMING linalg::vec_norm", _ns_vec_norm, _acc_vec_norm)
    var _acc_vec_cross: Float64 = 0.0
    var _t0_vec_cross = perf_counter_ns()
    for _ in range(N):
        var _r_vec_cross = vec_cross(_lf5, _lf5)
        _acc_vec_cross += Float64(len(_r_vec_cross))
    var _t1_vec_cross = perf_counter_ns()
    var _ns_vec_cross = Float64(_t1_vec_cross - _t0_vec_cross) / Float64(N)
    print("MOJO_TIMING linalg::vec_cross", _ns_vec_cross, _acc_vec_cross)
