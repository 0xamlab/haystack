"""bench_queueing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from queueing import factorial, mm1_utilization, mm1_avg_queue_length, mm1_avg_system_size, mm1_avg_wait_time, mm1_avg_system_time, mmc_erlang_c, mmc_avg_wait_time, erlang_b, littles_law_L, littles_law_W
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

    var _acc_factorial: Float64 = 0.0
    var _t0_factorial = perf_counter_ns()
    for _ in range(N):
        _acc_factorial += factorial(5)
    var _t1_factorial = perf_counter_ns()
    var _ns_factorial = Float64(_t1_factorial - _t0_factorial) / Float64(N)
    print("MOJO_TIMING queueing::factorial", _ns_factorial, _acc_factorial)
    var _acc_mm1_utilization: Float64 = 0.0
    var _t0_mm1_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_utilization += mm1_utilization(0.5, 0.5)
    var _t1_mm1_utilization = perf_counter_ns()
    var _ns_mm1_utilization = Float64(_t1_mm1_utilization - _t0_mm1_utilization) / Float64(N)
    print("MOJO_TIMING queueing::mm1_utilization", _ns_mm1_utilization, _acc_mm1_utilization)
    var _acc_mm1_avg_queue_length: Float64 = 0.0
    var _t0_mm1_avg_queue_length = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_queue_length += mm1_avg_queue_length(0.5, 0.5)
    var _t1_mm1_avg_queue_length = perf_counter_ns()
    var _ns_mm1_avg_queue_length = Float64(_t1_mm1_avg_queue_length - _t0_mm1_avg_queue_length) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_queue_length", _ns_mm1_avg_queue_length, _acc_mm1_avg_queue_length)
    var _acc_mm1_avg_system_size: Float64 = 0.0
    var _t0_mm1_avg_system_size = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_system_size += mm1_avg_system_size(0.5, 0.5)
    var _t1_mm1_avg_system_size = perf_counter_ns()
    var _ns_mm1_avg_system_size = Float64(_t1_mm1_avg_system_size - _t0_mm1_avg_system_size) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_system_size", _ns_mm1_avg_system_size, _acc_mm1_avg_system_size)
    var _acc_mm1_avg_wait_time: Float64 = 0.0
    var _t0_mm1_avg_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_wait_time += mm1_avg_wait_time(0.5, 0.5)
    var _t1_mm1_avg_wait_time = perf_counter_ns()
    var _ns_mm1_avg_wait_time = Float64(_t1_mm1_avg_wait_time - _t0_mm1_avg_wait_time) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_wait_time", _ns_mm1_avg_wait_time, _acc_mm1_avg_wait_time)
    var _acc_mm1_avg_system_time: Float64 = 0.0
    var _t0_mm1_avg_system_time = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_system_time += mm1_avg_system_time(0.5, 0.5)
    var _t1_mm1_avg_system_time = perf_counter_ns()
    var _ns_mm1_avg_system_time = Float64(_t1_mm1_avg_system_time - _t0_mm1_avg_system_time) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_system_time", _ns_mm1_avg_system_time, _acc_mm1_avg_system_time)
    var _acc_mmc_erlang_c: Float64 = 0.0
    var _t0_mmc_erlang_c = perf_counter_ns()
    for _ in range(N):
        _acc_mmc_erlang_c += mmc_erlang_c(0.5, 0.5, 5)
    var _t1_mmc_erlang_c = perf_counter_ns()
    var _ns_mmc_erlang_c = Float64(_t1_mmc_erlang_c - _t0_mmc_erlang_c) / Float64(N)
    print("MOJO_TIMING queueing::mmc_erlang_c", _ns_mmc_erlang_c, _acc_mmc_erlang_c)
    var _acc_mmc_avg_wait_time: Float64 = 0.0
    var _t0_mmc_avg_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_mmc_avg_wait_time += mmc_avg_wait_time(0.5, 0.5, 5)
    var _t1_mmc_avg_wait_time = perf_counter_ns()
    var _ns_mmc_avg_wait_time = Float64(_t1_mmc_avg_wait_time - _t0_mmc_avg_wait_time) / Float64(N)
    print("MOJO_TIMING queueing::mmc_avg_wait_time", _ns_mmc_avg_wait_time, _acc_mmc_avg_wait_time)
    var _acc_erlang_b: Float64 = 0.0
    var _t0_erlang_b = perf_counter_ns()
    for _ in range(N):
        _acc_erlang_b += erlang_b(0.5, 5)
    var _t1_erlang_b = perf_counter_ns()
    var _ns_erlang_b = Float64(_t1_erlang_b - _t0_erlang_b) / Float64(N)
    print("MOJO_TIMING queueing::erlang_b", _ns_erlang_b, _acc_erlang_b)
    var _acc_littles_law_L: Float64 = 0.0
    var _t0_littles_law_L = perf_counter_ns()
    for _ in range(N):
        _acc_littles_law_L += littles_law_L(0.5, 0.5)
    var _t1_littles_law_L = perf_counter_ns()
    var _ns_littles_law_L = Float64(_t1_littles_law_L - _t0_littles_law_L) / Float64(N)
    print("MOJO_TIMING queueing::littles_law_L", _ns_littles_law_L, _acc_littles_law_L)
    var _acc_littles_law_W: Float64 = 0.0
    var _t0_littles_law_W = perf_counter_ns()
    for _ in range(N):
        _acc_littles_law_W += littles_law_W(0.5, 0.5)
    var _t1_littles_law_W = perf_counter_ns()
    var _ns_littles_law_W = Float64(_t1_littles_law_W - _t0_littles_law_W) / Float64(N)
    print("MOJO_TIMING queueing::littles_law_W", _ns_littles_law_W, _acc_littles_law_W)
