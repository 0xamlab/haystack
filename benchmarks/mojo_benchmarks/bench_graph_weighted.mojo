"""bench_graph_weighted.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from graph.weighted import union_find_create, union_find_find, union_find_union
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

    var _acc_union_find_create: Float64 = 0.0
    var _t0_union_find_create = perf_counter_ns()
    for _ in range(N):
        var _r_union_find_create = union_find_create(5)
        _acc_union_find_create += Float64(len(_r_union_find_create))
    var _t1_union_find_create = perf_counter_ns()
    var _ns_union_find_create = Float64(_t1_union_find_create - _t0_union_find_create) / Float64(N)
    print("MOJO_TIMING graph_weighted::union_find_create", _ns_union_find_create, _acc_union_find_create)
    var _acc_union_find_find: Float64 = 0.0
    var _t0_union_find_find = perf_counter_ns()
    for _ in range(N):
        _acc_union_find_find += Float64(union_find_find(_li5, 5))
    var _t1_union_find_find = perf_counter_ns()
    var _ns_union_find_find = Float64(_t1_union_find_find - _t0_union_find_find) / Float64(N)
    print("MOJO_TIMING graph_weighted::union_find_find", _ns_union_find_find, _acc_union_find_find)
    var _acc_union_find_union: Float64 = 0.0
    var _t0_union_find_union = perf_counter_ns()
    for _ in range(N):
        _acc_union_find_union += Float64(union_find_union(_li5, 5, 5))
    var _t1_union_find_union = perf_counter_ns()
    var _ns_union_find_union = Float64(_t1_union_find_union - _t0_union_find_union) / Float64(N)
    print("MOJO_TIMING graph_weighted::union_find_union", _ns_union_find_union, _acc_union_find_union)
