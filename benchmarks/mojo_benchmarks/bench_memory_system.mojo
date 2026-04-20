"""bench_memory_system.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from memory_system import pool_fragmentation_ratio, slab_alloc_waste, cache_line_padding_bytes, strided_access_penalty, activation_memory_bytes, gradient_memory_bytes, optimizer_state_bytes, peak_memory_estimate, memory_bandwidth_utilization, numa_locality_score
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

    var _acc_pool_fragmentation_ratio: Float64 = 0.0
    var _t0_pool_fragmentation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_pool_fragmentation_ratio += pool_fragmentation_ratio(0.5, 0.5)
    var _t1_pool_fragmentation_ratio = perf_counter_ns()
    var _ns_pool_fragmentation_ratio = Float64(_t1_pool_fragmentation_ratio - _t0_pool_fragmentation_ratio) / Float64(N)
    print("MOJO_TIMING memory_system::pool_fragmentation_ratio", _ns_pool_fragmentation_ratio, _acc_pool_fragmentation_ratio)
    var _acc_slab_alloc_waste: Float64 = 0.0
    var _t0_slab_alloc_waste = perf_counter_ns()
    for _ in range(N):
        _acc_slab_alloc_waste += slab_alloc_waste(0.5, 0.5)
    var _t1_slab_alloc_waste = perf_counter_ns()
    var _ns_slab_alloc_waste = Float64(_t1_slab_alloc_waste - _t0_slab_alloc_waste) / Float64(N)
    print("MOJO_TIMING memory_system::slab_alloc_waste", _ns_slab_alloc_waste, _acc_slab_alloc_waste)
    var _acc_cache_line_padding_bytes: Float64 = 0.0
    var _t0_cache_line_padding_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_cache_line_padding_bytes += cache_line_padding_bytes(0.5, 0.5)
    var _t1_cache_line_padding_bytes = perf_counter_ns()
    var _ns_cache_line_padding_bytes = Float64(_t1_cache_line_padding_bytes - _t0_cache_line_padding_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::cache_line_padding_bytes", _ns_cache_line_padding_bytes, _acc_cache_line_padding_bytes)
    var _acc_strided_access_penalty: Float64 = 0.0
    var _t0_strided_access_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_strided_access_penalty += strided_access_penalty(0.5, 0.5)
    var _t1_strided_access_penalty = perf_counter_ns()
    var _ns_strided_access_penalty = Float64(_t1_strided_access_penalty - _t0_strided_access_penalty) / Float64(N)
    print("MOJO_TIMING memory_system::strided_access_penalty", _ns_strided_access_penalty, _acc_strided_access_penalty)
    var _acc_activation_memory_bytes: Float64 = 0.0
    var _t0_activation_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_activation_memory_bytes += activation_memory_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_activation_memory_bytes = perf_counter_ns()
    var _ns_activation_memory_bytes = Float64(_t1_activation_memory_bytes - _t0_activation_memory_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::activation_memory_bytes", _ns_activation_memory_bytes, _acc_activation_memory_bytes)
    var _acc_gradient_memory_bytes: Float64 = 0.0
    var _t0_gradient_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_memory_bytes += gradient_memory_bytes(0.5, 0.5)
    var _t1_gradient_memory_bytes = perf_counter_ns()
    var _ns_gradient_memory_bytes = Float64(_t1_gradient_memory_bytes - _t0_gradient_memory_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::gradient_memory_bytes", _ns_gradient_memory_bytes, _acc_gradient_memory_bytes)
    var _acc_optimizer_state_bytes: Float64 = 0.0
    var _t0_optimizer_state_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_optimizer_state_bytes += optimizer_state_bytes(0.5, 0.5)
    var _t1_optimizer_state_bytes = perf_counter_ns()
    var _ns_optimizer_state_bytes = Float64(_t1_optimizer_state_bytes - _t0_optimizer_state_bytes) / Float64(N)
    print("MOJO_TIMING memory_system::optimizer_state_bytes", _ns_optimizer_state_bytes, _acc_optimizer_state_bytes)
    var _acc_peak_memory_estimate: Float64 = 0.0
    var _t0_peak_memory_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_peak_memory_estimate += peak_memory_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_peak_memory_estimate = perf_counter_ns()
    var _ns_peak_memory_estimate = Float64(_t1_peak_memory_estimate - _t0_peak_memory_estimate) / Float64(N)
    print("MOJO_TIMING memory_system::peak_memory_estimate", _ns_peak_memory_estimate, _acc_peak_memory_estimate)
    var _acc_memory_bandwidth_utilization: Float64 = 0.0
    var _t0_memory_bandwidth_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_memory_bandwidth_utilization += memory_bandwidth_utilization(0.5, 0.5)
    var _t1_memory_bandwidth_utilization = perf_counter_ns()
    var _ns_memory_bandwidth_utilization = Float64(_t1_memory_bandwidth_utilization - _t0_memory_bandwidth_utilization) / Float64(N)
    print("MOJO_TIMING memory_system::memory_bandwidth_utilization", _ns_memory_bandwidth_utilization, _acc_memory_bandwidth_utilization)
    var _acc_numa_locality_score: Float64 = 0.0
    var _t0_numa_locality_score = perf_counter_ns()
    for _ in range(N):
        _acc_numa_locality_score += numa_locality_score(0.5, 0.5, 0.5)
    var _t1_numa_locality_score = perf_counter_ns()
    var _ns_numa_locality_score = Float64(_t1_numa_locality_score - _t0_numa_locality_score) / Float64(N)
    print("MOJO_TIMING memory_system::numa_locality_score", _ns_numa_locality_score, _acc_numa_locality_score)
