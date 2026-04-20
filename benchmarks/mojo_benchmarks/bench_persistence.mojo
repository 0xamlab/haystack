"""bench_persistence.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from persistence import kv_create, restore, KVStore
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

    var _keeper_kv_create = List[KVStore]()
    _keeper_kv_create.append(kv_create())
    var _acc_kv_create: Float64 = 0.0
    var _t0_kv_create = perf_counter_ns()
    for _ in range(N):
        _keeper_kv_create[0] = kv_create()
        _acc_kv_create += Float64(len(_keeper_kv_create))
    var _t1_kv_create = perf_counter_ns()
    var _ns_kv_create = Float64(_t1_kv_create - _t0_kv_create) / Float64(N)
    print("MOJO_TIMING persistence::kv_create", _ns_kv_create, _acc_kv_create)
    var _keeper_restore = List[KVStore]()
    _keeper_restore.append(restore([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _acc_restore: Float64 = 0.0
    var _t0_restore = perf_counter_ns()
    for _ in range(N):
        _keeper_restore[0] = restore([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_restore += Float64(len(_keeper_restore))
    var _t1_restore = perf_counter_ns()
    var _ns_restore = Float64(_t1_restore - _t0_restore) / Float64(N)
    print("MOJO_TIMING persistence::restore", _ns_restore, _acc_restore)
