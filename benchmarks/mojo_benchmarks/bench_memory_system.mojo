"""bench_memory_system.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from memory_system import pool_fragmentation_ratio, slab_alloc_waste, cache_line_padding_bytes, strided_access_penalty, activation_memory_bytes, gradient_memory_bytes, optimizer_state_bytes, peak_memory_estimate, memory_bandwidth_utilization, numa_locality_score
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

    var _acc_pool_fragmentation_ratio: Float64 = 0.0
    var _t0_pool_fragmentation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_pool_fragmentation_ratio += pool_fragmentation_ratio(0.5, 0.5)
    var _t1_pool_fragmentation_ratio = perf_counter_ns()
    var _ns_pool_fragmentation_ratio = Float64(_t1_pool_fragmentation_ratio - _t0_pool_fragmentation_ratio) / Float64(N)
    print("MOJO_TIMING memory_system::pool_fragmentation_ratio", _ns_pool_fragmentation_ratio, _acc_pool_fragmentation_ratio)
    var _result_pool_fragmentation_ratio = pool_fragmentation_ratio(0.5, 0.5)
    var _summary_pool_fragmentation_ratio = _summary_float64(_result_pool_fragmentation_ratio)
    print("MOJO_RESULT memory_system::pool_fragmentation_ratio", _summary_pool_fragmentation_ratio)
    var _acc_slab_alloc_waste: Float64 = 0.0
    var _t0_slab_alloc_waste = perf_counter_ns()
    for _ in range(N):
        _acc_slab_alloc_waste += slab_alloc_waste(0.5, 0.5)
    var _t1_slab_alloc_waste = perf_counter_ns()
    var _ns_slab_alloc_waste = Float64(_t1_slab_alloc_waste - _t0_slab_alloc_waste) / Float64(N)
    print("MOJO_TIMING memory_system::slab_alloc_waste", _ns_slab_alloc_waste, _acc_slab_alloc_waste)
    var _result_slab_alloc_waste = slab_alloc_waste(0.5, 0.5)
    var _summary_slab_alloc_waste = _summary_float64(_result_slab_alloc_waste)
    print("MOJO_RESULT memory_system::slab_alloc_waste", _summary_slab_alloc_waste)
    var _acc_cache_line_padding_bytes: Float64 = 0.0
    var _t0_cache_line_padding_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_cache_line_padding_bytes += cache_line_padding_bytes(0.5, 0.5)
    var _t1_cache_line_padding_bytes = perf_counter_ns()
    var _ns_cache_line_padding_bytes = Float64(_t1_cache_line_padding_bytes - _t0_cache_line_padding_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::cache_line_padding_bytes", _ns_cache_line_padding_bytes, _acc_cache_line_padding_bytes)
    var _result_cache_line_padding_bytes = cache_line_padding_bytes(0.5, 0.5)
    var _summary_cache_line_padding_bytes = _summary_float64(_result_cache_line_padding_bytes)
    print("MOJO_RESULT memory_system::cache_line_padding_bytes", _summary_cache_line_padding_bytes)
    var _acc_strided_access_penalty: Float64 = 0.0
    var _t0_strided_access_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_strided_access_penalty += strided_access_penalty(0.5, 0.5)
    var _t1_strided_access_penalty = perf_counter_ns()
    var _ns_strided_access_penalty = Float64(_t1_strided_access_penalty - _t0_strided_access_penalty) / Float64(N)
    print("MOJO_TIMING memory_system::strided_access_penalty", _ns_strided_access_penalty, _acc_strided_access_penalty)
    var _result_strided_access_penalty = strided_access_penalty(0.5, 0.5)
    var _summary_strided_access_penalty = _summary_float64(_result_strided_access_penalty)
    print("MOJO_RESULT memory_system::strided_access_penalty", _summary_strided_access_penalty)
    var _acc_activation_memory_bytes: Float64 = 0.0
    var _t0_activation_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_activation_memory_bytes += activation_memory_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_activation_memory_bytes = perf_counter_ns()
    var _ns_activation_memory_bytes = Float64(_t1_activation_memory_bytes - _t0_activation_memory_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::activation_memory_bytes", _ns_activation_memory_bytes, _acc_activation_memory_bytes)
    var _result_activation_memory_bytes = activation_memory_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_activation_memory_bytes = _summary_float64(_result_activation_memory_bytes)
    print("MOJO_RESULT memory_system::activation_memory_bytes", _summary_activation_memory_bytes)
    var _acc_gradient_memory_bytes: Float64 = 0.0
    var _t0_gradient_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_memory_bytes += gradient_memory_bytes(0.5, 0.5)
    var _t1_gradient_memory_bytes = perf_counter_ns()
    var _ns_gradient_memory_bytes = Float64(_t1_gradient_memory_bytes - _t0_gradient_memory_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::gradient_memory_bytes", _ns_gradient_memory_bytes, _acc_gradient_memory_bytes)
    var _result_gradient_memory_bytes = gradient_memory_bytes(0.5, 0.5)
    var _summary_gradient_memory_bytes = _summary_float64(_result_gradient_memory_bytes)
    print("MOJO_RESULT memory_system::gradient_memory_bytes", _summary_gradient_memory_bytes)
    var _acc_optimizer_state_bytes: Float64 = 0.0
    var _t0_optimizer_state_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_optimizer_state_bytes += optimizer_state_bytes(0.5, 0.5)
    var _t1_optimizer_state_bytes = perf_counter_ns()
    var _ns_optimizer_state_bytes = Float64(_t1_optimizer_state_bytes - _t0_optimizer_state_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::optimizer_state_bytes", _ns_optimizer_state_bytes, _acc_optimizer_state_bytes)
    var _result_optimizer_state_bytes = optimizer_state_bytes(0.5, 0.5)
    var _summary_optimizer_state_bytes = _summary_float64(_result_optimizer_state_bytes)
    print("MOJO_RESULT memory_system::optimizer_state_bytes", _summary_optimizer_state_bytes)
    var _acc_peak_memory_estimate: Float64 = 0.0
    var _t0_peak_memory_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_peak_memory_estimate += peak_memory_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_peak_memory_estimate = perf_counter_ns()
    var _ns_peak_memory_estimate = Float64(_t1_peak_memory_estimate - _t0_peak_memory_estimate) / Float64(N)
    print("MOJO_TIMING memory_system::peak_memory_estimate", _ns_peak_memory_estimate, _acc_peak_memory_estimate)
    var _result_peak_memory_estimate = peak_memory_estimate(0.5, 0.5, 0.5, 0.5)
    var _summary_peak_memory_estimate = _summary_float64(_result_peak_memory_estimate)
    print("MOJO_RESULT memory_system::peak_memory_estimate", _summary_peak_memory_estimate)
    var _acc_memory_bandwidth_utilization: Float64 = 0.0
    var _t0_memory_bandwidth_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_memory_bandwidth_utilization += memory_bandwidth_utilization(0.5, 0.5)
    var _t1_memory_bandwidth_utilization = perf_counter_ns()
    var _ns_memory_bandwidth_utilization = Float64(_t1_memory_bandwidth_utilization - _t0_memory_bandwidth_utilization) / Float64(N)
    print("MOJO_TIMING memory_system::memory_bandwidth_utilization", _ns_memory_bandwidth_utilization, _acc_memory_bandwidth_utilization)
    var _result_memory_bandwidth_utilization = memory_bandwidth_utilization(0.5, 0.5)
    var _summary_memory_bandwidth_utilization = _summary_float64(_result_memory_bandwidth_utilization)
    print("MOJO_RESULT memory_system::memory_bandwidth_utilization", _summary_memory_bandwidth_utilization)
    var _acc_numa_locality_score: Float64 = 0.0
    var _t0_numa_locality_score = perf_counter_ns()
    for _ in range(N):
        _acc_numa_locality_score += numa_locality_score(0.5, 0.5, 0.5)
    var _t1_numa_locality_score = perf_counter_ns()
    var _ns_numa_locality_score = Float64(_t1_numa_locality_score - _t0_numa_locality_score) / Float64(N)
    print("MOJO_TIMING memory_system::numa_locality_score", _ns_numa_locality_score, _acc_numa_locality_score)
    var _result_numa_locality_score = numa_locality_score(0.5, 0.5, 0.5)
    var _summary_numa_locality_score = _summary_float64(_result_numa_locality_score)
    print("MOJO_RESULT memory_system::numa_locality_score", _summary_numa_locality_score)
