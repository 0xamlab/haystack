"""bench_distributed_collectives.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from distributed_collectives import ring_allreduce_step, reduce_scatter_element, all_gather_offset, broadcast_scale, gradient_compression_ratio, expert_dispatch_volume, peer_bandwidth_utilization, collective_latency_alpha_beta, overlap_compute_comm_ratio, allreduce_tree_step_count
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

    var _acc_ring_allreduce_step: Float64 = 0.0
    var _t0_ring_allreduce_step = perf_counter_ns()
    for _ in range(N):
        _acc_ring_allreduce_step += ring_allreduce_step(0.5, 0.5, 0.5)
    var _t1_ring_allreduce_step = perf_counter_ns()
    var _ns_ring_allreduce_step = Float64(_t1_ring_allreduce_step - _t0_ring_allreduce_step) / Float64(N)
    print("MOJO_TIMING distributed_collectives::ring_allreduce_step", _ns_ring_allreduce_step, _acc_ring_allreduce_step)
    var _result_ring_allreduce_step = ring_allreduce_step(0.5, 0.5, 0.5)
    var _summary_ring_allreduce_step = _summary_float64(_result_ring_allreduce_step)
    print("MOJO_RESULT distributed_collectives::ring_allreduce_step", _summary_ring_allreduce_step)
    var _acc_reduce_scatter_element: Float64 = 0.0
    var _t0_reduce_scatter_element = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_scatter_element += reduce_scatter_element(0.5, 0.5)
    var _t1_reduce_scatter_element = perf_counter_ns()
    var _ns_reduce_scatter_element = Float64(_t1_reduce_scatter_element - _t0_reduce_scatter_element) / Float64(N)
    print("MOJO_TIMING distributed_collectives::reduce_scatter_element", _ns_reduce_scatter_element, _acc_reduce_scatter_element)
    var _result_reduce_scatter_element = reduce_scatter_element(0.5, 0.5)
    var _summary_reduce_scatter_element = _summary_float64(_result_reduce_scatter_element)
    print("MOJO_RESULT distributed_collectives::reduce_scatter_element", _summary_reduce_scatter_element)
    var _acc_all_gather_offset: Float64 = 0.0
    var _t0_all_gather_offset = perf_counter_ns()
    for _ in range(N):
        _acc_all_gather_offset += all_gather_offset(0.5, 0.5)
    var _t1_all_gather_offset = perf_counter_ns()
    var _ns_all_gather_offset = Float64(_t1_all_gather_offset - _t0_all_gather_offset) / Float64(N)
    print("MOJO_TIMING distributed_collectives::all_gather_offset", _ns_all_gather_offset, _acc_all_gather_offset)
    var _result_all_gather_offset = all_gather_offset(0.5, 0.5)
    var _summary_all_gather_offset = _summary_float64(_result_all_gather_offset)
    print("MOJO_RESULT distributed_collectives::all_gather_offset", _summary_all_gather_offset)
    var _acc_broadcast_scale: Float64 = 0.0
    var _t0_broadcast_scale = perf_counter_ns()
    for _ in range(N):
        _acc_broadcast_scale += broadcast_scale(0.5)
    var _t1_broadcast_scale = perf_counter_ns()
    var _ns_broadcast_scale = Float64(_t1_broadcast_scale - _t0_broadcast_scale) / Float64(N)
    print("MOJO_TIMING distributed_collectives::broadcast_scale", _ns_broadcast_scale, _acc_broadcast_scale)
    var _result_broadcast_scale = broadcast_scale(0.5)
    var _summary_broadcast_scale = _summary_float64(_result_broadcast_scale)
    print("MOJO_RESULT distributed_collectives::broadcast_scale", _summary_broadcast_scale)
    var _acc_gradient_compression_ratio: Float64 = 0.0
    var _t0_gradient_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_compression_ratio += gradient_compression_ratio(0.5, 0.5)
    var _t1_gradient_compression_ratio = perf_counter_ns()
    var _ns_gradient_compression_ratio = Float64(_t1_gradient_compression_ratio - _t0_gradient_compression_ratio) / Float64(N)
    print("MOJO_TIMING distributed_collectives::gradient_compression_ratio", _ns_gradient_compression_ratio, _acc_gradient_compression_ratio)
    var _result_gradient_compression_ratio = gradient_compression_ratio(0.5, 0.5)
    var _summary_gradient_compression_ratio = _summary_float64(_result_gradient_compression_ratio)
    print("MOJO_RESULT distributed_collectives::gradient_compression_ratio", _summary_gradient_compression_ratio)
    var _acc_expert_dispatch_volume: Float64 = 0.0
    var _t0_expert_dispatch_volume = perf_counter_ns()
    for _ in range(N):
        _acc_expert_dispatch_volume += expert_dispatch_volume(0.5, 0.5, 0.5)
    var _t1_expert_dispatch_volume = perf_counter_ns()
    var _ns_expert_dispatch_volume = Float64(_t1_expert_dispatch_volume - _t0_expert_dispatch_volume) / Float64(N)
    print("MOJO_TIMING distributed_collectives::expert_dispatch_volume", _ns_expert_dispatch_volume, _acc_expert_dispatch_volume)
    var _result_expert_dispatch_volume = expert_dispatch_volume(0.5, 0.5, 0.5)
    var _summary_expert_dispatch_volume = _summary_float64(_result_expert_dispatch_volume)
    print("MOJO_RESULT distributed_collectives::expert_dispatch_volume", _summary_expert_dispatch_volume)
    var _acc_peer_bandwidth_utilization: Float64 = 0.0
    var _t0_peer_bandwidth_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_peer_bandwidth_utilization += peer_bandwidth_utilization(0.5, 0.5, 0.5)
    var _t1_peer_bandwidth_utilization = perf_counter_ns()
    var _ns_peer_bandwidth_utilization = Float64(_t1_peer_bandwidth_utilization - _t0_peer_bandwidth_utilization) / Float64(N)
    print("MOJO_TIMING distributed_collectives::peer_bandwidth_utilization", _ns_peer_bandwidth_utilization, _acc_peer_bandwidth_utilization)
    var _result_peer_bandwidth_utilization = peer_bandwidth_utilization(0.5, 0.5, 0.5)
    var _summary_peer_bandwidth_utilization = _summary_float64(_result_peer_bandwidth_utilization)
    print("MOJO_RESULT distributed_collectives::peer_bandwidth_utilization", _summary_peer_bandwidth_utilization)
    var _acc_collective_latency_alpha_beta: Float64 = 0.0
    var _t0_collective_latency_alpha_beta = perf_counter_ns()
    for _ in range(N):
        _acc_collective_latency_alpha_beta += collective_latency_alpha_beta(0.5, 0.5, 0.5, 0.5)
    var _t1_collective_latency_alpha_beta = perf_counter_ns()
    var _ns_collective_latency_alpha_beta = Float64(_t1_collective_latency_alpha_beta - _t0_collective_latency_alpha_beta) / Float64(N)
    print("MOJO_TIMING distributed_collectives::collective_latency_alpha_beta", _ns_collective_latency_alpha_beta, _acc_collective_latency_alpha_beta)
    var _result_collective_latency_alpha_beta = collective_latency_alpha_beta(0.5, 0.5, 0.5, 0.5)
    var _summary_collective_latency_alpha_beta = _summary_float64(_result_collective_latency_alpha_beta)
    print("MOJO_RESULT distributed_collectives::collective_latency_alpha_beta", _summary_collective_latency_alpha_beta)
    var _acc_overlap_compute_comm_ratio: Float64 = 0.0
    var _t0_overlap_compute_comm_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_compute_comm_ratio += overlap_compute_comm_ratio(0.5, 0.5)
    var _t1_overlap_compute_comm_ratio = perf_counter_ns()
    var _ns_overlap_compute_comm_ratio = Float64(_t1_overlap_compute_comm_ratio - _t0_overlap_compute_comm_ratio) / Float64(N)
    print("MOJO_TIMING distributed_collectives::overlap_compute_comm_ratio", _ns_overlap_compute_comm_ratio, _acc_overlap_compute_comm_ratio)
    var _result_overlap_compute_comm_ratio = overlap_compute_comm_ratio(0.5, 0.5)
    var _summary_overlap_compute_comm_ratio = _summary_float64(_result_overlap_compute_comm_ratio)
    print("MOJO_RESULT distributed_collectives::overlap_compute_comm_ratio", _summary_overlap_compute_comm_ratio)
    var _acc_allreduce_tree_step_count: Float64 = 0.0
    var _t0_allreduce_tree_step_count = perf_counter_ns()
    for _ in range(N):
        _acc_allreduce_tree_step_count += allreduce_tree_step_count(0.5)
    var _t1_allreduce_tree_step_count = perf_counter_ns()
    var _ns_allreduce_tree_step_count = Float64(_t1_allreduce_tree_step_count - _t0_allreduce_tree_step_count) / Float64(N)
    print("MOJO_TIMING distributed_collectives::allreduce_tree_step_count", _ns_allreduce_tree_step_count, _acc_allreduce_tree_step_count)
    var _result_allreduce_tree_step_count = allreduce_tree_step_count(0.5)
    var _summary_allreduce_tree_step_count = _summary_float64(_result_allreduce_tree_step_count)
    print("MOJO_RESULT distributed_collectives::allreduce_tree_step_count", _summary_allreduce_tree_step_count)
