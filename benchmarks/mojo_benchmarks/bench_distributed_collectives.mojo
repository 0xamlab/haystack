"""bench_distributed_collectives.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from distributed_collectives import ring_allreduce_step, reduce_scatter_element, all_gather_offset, broadcast_scale, gradient_compression_ratio, expert_dispatch_volume, peer_bandwidth_utilization, collective_latency_alpha_beta, overlap_compute_comm_ratio, allreduce_tree_step_count
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

    var _acc_ring_allreduce_step: Float64 = 0.0
    var _t0_ring_allreduce_step = perf_counter_ns()
    for _ in range(N):
        _acc_ring_allreduce_step += ring_allreduce_step(0.5, 0.5, 0.5)
    var _t1_ring_allreduce_step = perf_counter_ns()
    var _ns_ring_allreduce_step = Float64(_t1_ring_allreduce_step - _t0_ring_allreduce_step) / Float64(N)
    print("MOJO_TIMING distributed_collectives::ring_allreduce_step", _ns_ring_allreduce_step, _acc_ring_allreduce_step)
    var _acc_reduce_scatter_element: Float64 = 0.0
    var _t0_reduce_scatter_element = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_scatter_element += reduce_scatter_element(0.5, 0.5)
    var _t1_reduce_scatter_element = perf_counter_ns()
    var _ns_reduce_scatter_element = Float64(_t1_reduce_scatter_element - _t0_reduce_scatter_element) / Float64(N)
    print("MOJO_TIMING distributed_collectives::reduce_scatter_element", _ns_reduce_scatter_element, _acc_reduce_scatter_element)
    var _acc_all_gather_offset: Float64 = 0.0
    var _t0_all_gather_offset = perf_counter_ns()
    for _ in range(N):
        _acc_all_gather_offset += all_gather_offset(0.5, 0.5)
    var _t1_all_gather_offset = perf_counter_ns()
    var _ns_all_gather_offset = Float64(_t1_all_gather_offset - _t0_all_gather_offset) / Float64(N)
    print("MOJO_TIMING distributed_collectives::all_gather_offset", _ns_all_gather_offset, _acc_all_gather_offset)
    var _acc_broadcast_scale: Float64 = 0.0
    var _t0_broadcast_scale = perf_counter_ns()
    for _ in range(N):
        _acc_broadcast_scale += broadcast_scale(0.5)
    var _t1_broadcast_scale = perf_counter_ns()
    var _ns_broadcast_scale = Float64(_t1_broadcast_scale - _t0_broadcast_scale) / Float64(N)
    print("MOJO_TIMING distributed_collectives::broadcast_scale", _ns_broadcast_scale, _acc_broadcast_scale)
    var _acc_gradient_compression_ratio: Float64 = 0.0
    var _t0_gradient_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_compression_ratio += gradient_compression_ratio(0.5, 0.5)
    var _t1_gradient_compression_ratio = perf_counter_ns()
    var _ns_gradient_compression_ratio = Float64(_t1_gradient_compression_ratio - _t0_gradient_compression_ratio) / Float64(N)
    print("MOJO_TIMING distributed_collectives::gradient_compression_ratio", _ns_gradient_compression_ratio, _acc_gradient_compression_ratio)
    var _acc_expert_dispatch_volume: Float64 = 0.0
    var _t0_expert_dispatch_volume = perf_counter_ns()
    for _ in range(N):
        _acc_expert_dispatch_volume += expert_dispatch_volume(0.5, 0.5, 0.5)
    var _t1_expert_dispatch_volume = perf_counter_ns()
    var _ns_expert_dispatch_volume = Float64(_t1_expert_dispatch_volume - _t0_expert_dispatch_volume) / Float64(N)
    print("MOJO_TIMING distributed_collectives::expert_dispatch_volume", _ns_expert_dispatch_volume, _acc_expert_dispatch_volume)
    var _acc_peer_bandwidth_utilization: Float64 = 0.0
    var _t0_peer_bandwidth_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_peer_bandwidth_utilization += peer_bandwidth_utilization(0.5, 0.5, 0.5)
    var _t1_peer_bandwidth_utilization = perf_counter_ns()
    var _ns_peer_bandwidth_utilization = Float64(_t1_peer_bandwidth_utilization - _t0_peer_bandwidth_utilization) / Float64(N)
    print("MOJO_TIMING distributed_collectives::peer_bandwidth_utilization", _ns_peer_bandwidth_utilization, _acc_peer_bandwidth_utilization)
    var _acc_collective_latency_alpha_beta: Float64 = 0.0
    var _t0_collective_latency_alpha_beta = perf_counter_ns()
    for _ in range(N):
        _acc_collective_latency_alpha_beta += collective_latency_alpha_beta(0.5, 0.5, 0.5, 0.5)
    var _t1_collective_latency_alpha_beta = perf_counter_ns()
    var _ns_collective_latency_alpha_beta = Float64(_t1_collective_latency_alpha_beta - _t0_collective_latency_alpha_beta) / Float64(N)
    print("MOJO_TIMING distributed_collectives::collective_latency_alpha_beta", _ns_collective_latency_alpha_beta, _acc_collective_latency_alpha_beta)
    var _acc_overlap_compute_comm_ratio: Float64 = 0.0
    var _t0_overlap_compute_comm_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_compute_comm_ratio += overlap_compute_comm_ratio(0.5, 0.5)
    var _t1_overlap_compute_comm_ratio = perf_counter_ns()
    var _ns_overlap_compute_comm_ratio = Float64(_t1_overlap_compute_comm_ratio - _t0_overlap_compute_comm_ratio) / Float64(N)
    print("MOJO_TIMING distributed_collectives::overlap_compute_comm_ratio", _ns_overlap_compute_comm_ratio, _acc_overlap_compute_comm_ratio)
    var _acc_allreduce_tree_step_count: Float64 = 0.0
    var _t0_allreduce_tree_step_count = perf_counter_ns()
    for _ in range(N):
        _acc_allreduce_tree_step_count += allreduce_tree_step_count(0.5)
    var _t1_allreduce_tree_step_count = perf_counter_ns()
    var _ns_allreduce_tree_step_count = Float64(_t1_allreduce_tree_step_count - _t0_allreduce_tree_step_count) / Float64(N)
    print("MOJO_TIMING distributed_collectives::allreduce_tree_step_count", _ns_allreduce_tree_step_count, _acc_allreduce_tree_step_count)
