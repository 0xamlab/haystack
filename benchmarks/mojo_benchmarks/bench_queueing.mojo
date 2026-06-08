"""bench_queueing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from queueing import factorial, mm1_utilization, mm1_avg_queue_length, mm1_avg_system_size, mm1_avg_wait_time, mm1_avg_system_time, mmc_erlang_c, mmc_avg_wait_time, erlang_b, littles_law_L, littles_law_W
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_factorial = factorial(5)
    var _summary_factorial = _summary_float64(_result_factorial)
    print("MOJO_RESULT queueing::factorial", _summary_factorial)
    var _acc_mm1_utilization: Float64 = 0.0
    var _t0_mm1_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_utilization += mm1_utilization(0.5, 0.5)
    var _t1_mm1_utilization = perf_counter_ns()
    var _ns_mm1_utilization = Float64(_t1_mm1_utilization - _t0_mm1_utilization) / Float64(N)
    print("MOJO_TIMING queueing::mm1_utilization", _ns_mm1_utilization, _acc_mm1_utilization)
    var _result_mm1_utilization = mm1_utilization(0.5, 0.5)
    var _summary_mm1_utilization = _summary_float64(_result_mm1_utilization)
    print("MOJO_RESULT queueing::mm1_utilization", _summary_mm1_utilization)
    var _acc_mm1_avg_queue_length: Float64 = 0.0
    var _t0_mm1_avg_queue_length = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_queue_length += mm1_avg_queue_length(0.5, 0.5)
    var _t1_mm1_avg_queue_length = perf_counter_ns()
    var _ns_mm1_avg_queue_length = Float64(_t1_mm1_avg_queue_length - _t0_mm1_avg_queue_length) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_queue_length", _ns_mm1_avg_queue_length, _acc_mm1_avg_queue_length)
    var _result_mm1_avg_queue_length = mm1_avg_queue_length(0.5, 0.5)
    var _summary_mm1_avg_queue_length = _summary_float64(_result_mm1_avg_queue_length)
    print("MOJO_RESULT queueing::mm1_avg_queue_length", _summary_mm1_avg_queue_length)
    var _acc_mm1_avg_system_size: Float64 = 0.0
    var _t0_mm1_avg_system_size = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_system_size += mm1_avg_system_size(0.5, 0.5)
    var _t1_mm1_avg_system_size = perf_counter_ns()
    var _ns_mm1_avg_system_size = Float64(_t1_mm1_avg_system_size - _t0_mm1_avg_system_size) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_system_size", _ns_mm1_avg_system_size, _acc_mm1_avg_system_size)
    var _result_mm1_avg_system_size = mm1_avg_system_size(0.5, 0.5)
    var _summary_mm1_avg_system_size = _summary_float64(_result_mm1_avg_system_size)
    print("MOJO_RESULT queueing::mm1_avg_system_size", _summary_mm1_avg_system_size)
    var _acc_mm1_avg_wait_time: Float64 = 0.0
    var _t0_mm1_avg_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_wait_time += mm1_avg_wait_time(0.5, 0.5)
    var _t1_mm1_avg_wait_time = perf_counter_ns()
    var _ns_mm1_avg_wait_time = Float64(_t1_mm1_avg_wait_time - _t0_mm1_avg_wait_time) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_wait_time", _ns_mm1_avg_wait_time, _acc_mm1_avg_wait_time)
    var _result_mm1_avg_wait_time = mm1_avg_wait_time(0.5, 0.5)
    var _summary_mm1_avg_wait_time = _summary_float64(_result_mm1_avg_wait_time)
    print("MOJO_RESULT queueing::mm1_avg_wait_time", _summary_mm1_avg_wait_time)
    var _acc_mm1_avg_system_time: Float64 = 0.0
    var _t0_mm1_avg_system_time = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_avg_system_time += mm1_avg_system_time(0.5, 0.5)
    var _t1_mm1_avg_system_time = perf_counter_ns()
    var _ns_mm1_avg_system_time = Float64(_t1_mm1_avg_system_time - _t0_mm1_avg_system_time) / Float64(N)
    print("MOJO_TIMING queueing::mm1_avg_system_time", _ns_mm1_avg_system_time, _acc_mm1_avg_system_time)
    var _result_mm1_avg_system_time = mm1_avg_system_time(0.5, 0.5)
    var _summary_mm1_avg_system_time = _summary_float64(_result_mm1_avg_system_time)
    print("MOJO_RESULT queueing::mm1_avg_system_time", _summary_mm1_avg_system_time)
    var _acc_mmc_erlang_c: Float64 = 0.0
    var _t0_mmc_erlang_c = perf_counter_ns()
    for _ in range(N):
        _acc_mmc_erlang_c += mmc_erlang_c(0.5, 0.5, 5)
    var _t1_mmc_erlang_c = perf_counter_ns()
    var _ns_mmc_erlang_c = Float64(_t1_mmc_erlang_c - _t0_mmc_erlang_c) / Float64(N)
    print("MOJO_TIMING queueing::mmc_erlang_c", _ns_mmc_erlang_c, _acc_mmc_erlang_c)
    var _result_mmc_erlang_c = mmc_erlang_c(0.5, 0.5, 5)
    var _summary_mmc_erlang_c = _summary_float64(_result_mmc_erlang_c)
    print("MOJO_RESULT queueing::mmc_erlang_c", _summary_mmc_erlang_c)
    var _acc_mmc_avg_wait_time: Float64 = 0.0
    var _t0_mmc_avg_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_mmc_avg_wait_time += mmc_avg_wait_time(0.5, 0.5, 5)
    var _t1_mmc_avg_wait_time = perf_counter_ns()
    var _ns_mmc_avg_wait_time = Float64(_t1_mmc_avg_wait_time - _t0_mmc_avg_wait_time) / Float64(N)
    print("MOJO_TIMING queueing::mmc_avg_wait_time", _ns_mmc_avg_wait_time, _acc_mmc_avg_wait_time)
    var _result_mmc_avg_wait_time = mmc_avg_wait_time(0.5, 0.5, 5)
    var _summary_mmc_avg_wait_time = _summary_float64(_result_mmc_avg_wait_time)
    print("MOJO_RESULT queueing::mmc_avg_wait_time", _summary_mmc_avg_wait_time)
    var _acc_erlang_b: Float64 = 0.0
    var _t0_erlang_b = perf_counter_ns()
    for _ in range(N):
        _acc_erlang_b += erlang_b(0.5, 5)
    var _t1_erlang_b = perf_counter_ns()
    var _ns_erlang_b = Float64(_t1_erlang_b - _t0_erlang_b) / Float64(N)
    print("MOJO_TIMING queueing::erlang_b", _ns_erlang_b, _acc_erlang_b)
    var _result_erlang_b = erlang_b(0.5, 5)
    var _summary_erlang_b = _summary_float64(_result_erlang_b)
    print("MOJO_RESULT queueing::erlang_b", _summary_erlang_b)
    var _acc_littles_law_L: Float64 = 0.0
    var _t0_littles_law_L = perf_counter_ns()
    for _ in range(N):
        _acc_littles_law_L += littles_law_L(0.5, 0.5)
    var _t1_littles_law_L = perf_counter_ns()
    var _ns_littles_law_L = Float64(_t1_littles_law_L - _t0_littles_law_L) / Float64(N)
    print("MOJO_TIMING queueing::littles_law_L", _ns_littles_law_L, _acc_littles_law_L)
    var _result_littles_law_L = littles_law_L(0.5, 0.5)
    var _summary_littles_law_L = _summary_float64(_result_littles_law_L)
    print("MOJO_RESULT queueing::littles_law_L", _summary_littles_law_L)
    var _acc_littles_law_W: Float64 = 0.0
    var _t0_littles_law_W = perf_counter_ns()
    for _ in range(N):
        _acc_littles_law_W += littles_law_W(0.5, 0.5)
    var _t1_littles_law_W = perf_counter_ns()
    var _ns_littles_law_W = Float64(_t1_littles_law_W - _t0_littles_law_W) / Float64(N)
    print("MOJO_TIMING queueing::littles_law_W", _ns_littles_law_W, _acc_littles_law_W)
    var _result_littles_law_W = littles_law_W(0.5, 0.5)
    var _summary_littles_law_W = _summary_float64(_result_littles_law_W)
    print("MOJO_RESULT queueing::littles_law_W", _summary_littles_law_W)
