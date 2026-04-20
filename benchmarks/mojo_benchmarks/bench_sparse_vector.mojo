"""bench_sparse_vector.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sparse_vector import sv_dot, sv_add, sv_scale, sv_norm, sv_cosine, sv_to_dense, dense_to_sparse, sv_nnz, sv_sparsity, sv_max
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

    var _acc_sv_dot: Float64 = 0.0
    var _t0_sv_dot = perf_counter_ns()
    for _ in range(N):
        _acc_sv_dot += sv_dot(_li5, _lf5, _li5, _lf5)
    var _t1_sv_dot = perf_counter_ns()
    var _ns_sv_dot = Float64(_t1_sv_dot - _t0_sv_dot) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_dot", _ns_sv_dot, _acc_sv_dot)
    var _acc_sv_add: Float64 = 0.0
    var _t0_sv_add = perf_counter_ns()
    for _ in range(N):
        var _r_sv_add = sv_add(_li5, _lf5, _li5, _lf5)
        _acc_sv_add += Float64(len(_r_sv_add))
    var _t1_sv_add = perf_counter_ns()
    var _ns_sv_add = Float64(_t1_sv_add - _t0_sv_add) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_add", _ns_sv_add, _acc_sv_add)
    var _acc_sv_scale: Float64 = 0.0
    var _t0_sv_scale = perf_counter_ns()
    for _ in range(N):
        var _r_sv_scale = sv_scale(_lf5, 0.5)
        _acc_sv_scale += Float64(len(_r_sv_scale))
    var _t1_sv_scale = perf_counter_ns()
    var _ns_sv_scale = Float64(_t1_sv_scale - _t0_sv_scale) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_scale", _ns_sv_scale, _acc_sv_scale)
    var _acc_sv_norm: Float64 = 0.0
    var _t0_sv_norm = perf_counter_ns()
    for _ in range(N):
        _acc_sv_norm += sv_norm(_lf5)
    var _t1_sv_norm = perf_counter_ns()
    var _ns_sv_norm = Float64(_t1_sv_norm - _t0_sv_norm) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_norm", _ns_sv_norm, _acc_sv_norm)
    var _acc_sv_cosine: Float64 = 0.0
    var _t0_sv_cosine = perf_counter_ns()
    for _ in range(N):
        _acc_sv_cosine += sv_cosine(_li5, _lf5, _li5, _lf5)
    var _t1_sv_cosine = perf_counter_ns()
    var _ns_sv_cosine = Float64(_t1_sv_cosine - _t0_sv_cosine) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_cosine", _ns_sv_cosine, _acc_sv_cosine)
    var _acc_sv_to_dense: Float64 = 0.0
    var _t0_sv_to_dense = perf_counter_ns()
    for _ in range(N):
        var _r_sv_to_dense = sv_to_dense(_li5, _lf5, 5)
        _acc_sv_to_dense += Float64(len(_r_sv_to_dense))
    var _t1_sv_to_dense = perf_counter_ns()
    var _ns_sv_to_dense = Float64(_t1_sv_to_dense - _t0_sv_to_dense) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_to_dense", _ns_sv_to_dense, _acc_sv_to_dense)
    var _acc_dense_to_sparse: Float64 = 0.0
    var _t0_dense_to_sparse = perf_counter_ns()
    for _ in range(N):
        var _r_dense_to_sparse = dense_to_sparse(_lf5, 0.5)
        _acc_dense_to_sparse += Float64(len(_r_dense_to_sparse))
    var _t1_dense_to_sparse = perf_counter_ns()
    var _ns_dense_to_sparse = Float64(_t1_dense_to_sparse - _t0_dense_to_sparse) / Float64(N)
    print("MOJO_TIMING sparse_vector::dense_to_sparse", _ns_dense_to_sparse, _acc_dense_to_sparse)
    var _acc_sv_nnz: Float64 = 0.0
    var _t0_sv_nnz = perf_counter_ns()
    for _ in range(N):
        _acc_sv_nnz += Float64(sv_nnz(_lf5))
    var _t1_sv_nnz = perf_counter_ns()
    var _ns_sv_nnz = Float64(_t1_sv_nnz - _t0_sv_nnz) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_nnz", _ns_sv_nnz, _acc_sv_nnz)
    var _acc_sv_sparsity: Float64 = 0.0
    var _t0_sv_sparsity = perf_counter_ns()
    for _ in range(N):
        _acc_sv_sparsity += sv_sparsity(5, 5)
    var _t1_sv_sparsity = perf_counter_ns()
    var _ns_sv_sparsity = Float64(_t1_sv_sparsity - _t0_sv_sparsity) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_sparsity", _ns_sv_sparsity, _acc_sv_sparsity)
    var _acc_sv_max: Float64 = 0.0
    var _t0_sv_max = perf_counter_ns()
    for _ in range(N):
        _acc_sv_max += sv_max(_lf5)
    var _t1_sv_max = perf_counter_ns()
    var _ns_sv_max = Float64(_t1_sv_max - _t0_sv_max) / Float64(N)
    print("MOJO_TIMING sparse_vector::sv_max", _ns_sv_max, _acc_sv_max)
