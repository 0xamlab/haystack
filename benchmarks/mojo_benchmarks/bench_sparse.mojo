"""bench_sparse.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sparse import sparse_from_dense, SparseMatrixCOO
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

    var _keeper_sparse_from_dense = List[SparseMatrixCOO]()
    _keeper_sparse_from_dense.append(sparse_from_dense([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _acc_sparse_from_dense: Float64 = 0.0
    var _t0_sparse_from_dense = perf_counter_ns()
    for _ in range(N):
        _keeper_sparse_from_dense[0] = sparse_from_dense([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_sparse_from_dense += Float64(len(_keeper_sparse_from_dense))
    var _t1_sparse_from_dense = perf_counter_ns()
    var _ns_sparse_from_dense = Float64(_t1_sparse_from_dense - _t0_sparse_from_dense) / Float64(N)
    print("MOJO_TIMING sparse::sparse_from_dense", _ns_sparse_from_dense, _acc_sparse_from_dense)
