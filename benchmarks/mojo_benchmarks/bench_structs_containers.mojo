"""bench_structs_containers.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from structs.containers import counter, unique
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

    var _acc_counter: Float64 = 0.0
    var _t0_counter = perf_counter_ns()
    for _ in range(N):
        var _r_counter = counter(_lf5, 5)
        _acc_counter += Float64(len(_r_counter))
    var _t1_counter = perf_counter_ns()
    var _ns_counter = Float64(_t1_counter - _t0_counter) / Float64(N)
    print("MOJO_TIMING structs_containers::counter", _ns_counter, _acc_counter)
    var _acc_unique: Float64 = 0.0
    var _t0_unique = perf_counter_ns()
    for _ in range(N):
        var _r_unique = unique(_lf5)
        _acc_unique += Float64(len(_r_unique))
    var _t1_unique = perf_counter_ns()
    var _ns_unique = Float64(_t1_unique - _t0_unique) / Float64(N)
    print("MOJO_TIMING structs_containers::unique", _ns_unique, _acc_unique)
