"""bench_env.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from env import env_get, env_get_int, env_get_float, env_get_bool, env_is_set
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

    var _acc_env_get: Float64 = 0.0
    var _t0_env_get = perf_counter_ns()
    for _ in range(N):
        _ = env_get("test", "test")
    var _t1_env_get = perf_counter_ns()
    var _ns_env_get = Float64(_t1_env_get - _t0_env_get) / Float64(N)
    print("MOJO_TIMING env::env_get", _ns_env_get, _acc_env_get)
    var _acc_env_get_int: Float64 = 0.0
    var _t0_env_get_int = perf_counter_ns()
    for _ in range(N):
        _acc_env_get_int += Float64(env_get_int("test", 5))
    var _t1_env_get_int = perf_counter_ns()
    var _ns_env_get_int = Float64(_t1_env_get_int - _t0_env_get_int) / Float64(N)
    print("MOJO_TIMING env::env_get_int", _ns_env_get_int, _acc_env_get_int)
    var _acc_env_get_float: Float64 = 0.0
    var _t0_env_get_float = perf_counter_ns()
    for _ in range(N):
        _acc_env_get_float += env_get_float("test", 0.5)
    var _t1_env_get_float = perf_counter_ns()
    var _ns_env_get_float = Float64(_t1_env_get_float - _t0_env_get_float) / Float64(N)
    print("MOJO_TIMING env::env_get_float", _ns_env_get_float, _acc_env_get_float)
    var _acc_env_get_bool: Float64 = 0.0
    var _t0_env_get_bool = perf_counter_ns()
    for _ in range(N):
        _acc_env_get_bool += Float64(env_get_bool("test", True))
    var _t1_env_get_bool = perf_counter_ns()
    var _ns_env_get_bool = Float64(_t1_env_get_bool - _t0_env_get_bool) / Float64(N)
    print("MOJO_TIMING env::env_get_bool", _ns_env_get_bool, _acc_env_get_bool)
    var _acc_env_is_set: Float64 = 0.0
    var _t0_env_is_set = perf_counter_ns()
    for _ in range(N):
        _acc_env_is_set += Float64(env_is_set("test"))
    var _t1_env_is_set = perf_counter_ns()
    var _ns_env_is_set = Float64(_t1_env_is_set - _t0_env_is_set) / Float64(N)
    print("MOJO_TIMING env::env_is_set", _ns_env_is_set, _acc_env_is_set)
