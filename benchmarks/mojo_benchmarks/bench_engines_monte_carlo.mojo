"""bench_engines_monte_carlo.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from engines.monte_carlo import xorshift64, xr_f64, thread_seed
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

    var _acc_xorshift64: Float64 = 0.0
    var _t0_xorshift64 = perf_counter_ns()
    for _ in range(N):
        _acc_xorshift64 += Float64(xorshift64(UInt64(1)))
    var _t1_xorshift64 = perf_counter_ns()
    var _ns_xorshift64 = Float64(_t1_xorshift64 - _t0_xorshift64) / Float64(N)
    print("MOJO_TIMING engines_monte_carlo::xorshift64", _ns_xorshift64, _acc_xorshift64)
    var _acc_xr_f64: Float64 = 0.0
    var _t0_xr_f64 = perf_counter_ns()
    for _ in range(N):
        _acc_xr_f64 += xr_f64(UInt64(1))
    var _t1_xr_f64 = perf_counter_ns()
    var _ns_xr_f64 = Float64(_t1_xr_f64 - _t0_xr_f64) / Float64(N)
    print("MOJO_TIMING engines_monte_carlo::xr_f64", _ns_xr_f64, _acc_xr_f64)
    var _acc_thread_seed: Float64 = 0.0
    var _t0_thread_seed = perf_counter_ns()
    for _ in range(N):
        _acc_thread_seed += Float64(thread_seed(5, UInt64(1)))
    var _t1_thread_seed = perf_counter_ns()
    var _ns_thread_seed = Float64(_t1_thread_seed - _t0_thread_seed) / Float64(N)
    print("MOJO_TIMING engines_monte_carlo::thread_seed", _ns_thread_seed, _acc_thread_seed)
