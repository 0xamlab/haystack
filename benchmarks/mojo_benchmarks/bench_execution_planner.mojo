"""bench_execution_planner.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from execution_planner import fusion_opportunity_score, device_placement_score, kv_policy_eviction_priority, batching_strategy_score, scheduling_priority_score, prefetch_benefit_estimate, graph_rewrite_gain, memory_placement_affinity, pipeline_depth_optimal, adaptive_batch_size
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

    var _acc_fusion_opportunity_score: Float64 = 0.0
    var _t0_fusion_opportunity_score = perf_counter_ns()
    for _ in range(N):
        _acc_fusion_opportunity_score += fusion_opportunity_score(0.5, 0.5, 0.5)
    var _t1_fusion_opportunity_score = perf_counter_ns()
    var _ns_fusion_opportunity_score = Float64(_t1_fusion_opportunity_score - _t0_fusion_opportunity_score) / Float64(N)
    print("MOJO_TIMING execution_planner::fusion_opportunity_score", _ns_fusion_opportunity_score, _acc_fusion_opportunity_score)
    var _acc_device_placement_score: Float64 = 0.0
    var _t0_device_placement_score = perf_counter_ns()
    for _ in range(N):
        _acc_device_placement_score += device_placement_score(0.5, 0.5, 0.5)
    var _t1_device_placement_score = perf_counter_ns()
    var _ns_device_placement_score = Float64(_t1_device_placement_score - _t0_device_placement_score) / Float64(N)
    print("MOJO_TIMING execution_planner::device_placement_score", _ns_device_placement_score, _acc_device_placement_score)
    var _acc_kv_policy_eviction_priority: Float64 = 0.0
    var _t0_kv_policy_eviction_priority = perf_counter_ns()
    for _ in range(N):
        _acc_kv_policy_eviction_priority += kv_policy_eviction_priority(0.5, 0.5, 0.5, 0.5)
    var _t1_kv_policy_eviction_priority = perf_counter_ns()
    var _ns_kv_policy_eviction_priority = Float64(_t1_kv_policy_eviction_priority - _t0_kv_policy_eviction_priority) / Float64(N)
    print("MOJO_TIMING execution_planner::kv_policy_eviction_priority", _ns_kv_policy_eviction_priority, _acc_kv_policy_eviction_priority)
    var _acc_batching_strategy_score: Float64 = 0.0
    var _t0_batching_strategy_score = perf_counter_ns()
    for _ in range(N):
        _acc_batching_strategy_score += batching_strategy_score(0.5, 0.5, 0.5, 0.5)
    var _t1_batching_strategy_score = perf_counter_ns()
    var _ns_batching_strategy_score = Float64(_t1_batching_strategy_score - _t0_batching_strategy_score) / Float64(N)
    print("MOJO_TIMING execution_planner::batching_strategy_score", _ns_batching_strategy_score, _acc_batching_strategy_score)
    var _acc_scheduling_priority_score: Float64 = 0.0
    var _t0_scheduling_priority_score = perf_counter_ns()
    for _ in range(N):
        _acc_scheduling_priority_score += scheduling_priority_score(0.5, 0.5, 0.5, 0.5)
    var _t1_scheduling_priority_score = perf_counter_ns()
    var _ns_scheduling_priority_score = Float64(_t1_scheduling_priority_score - _t0_scheduling_priority_score) / Float64(N)
    print("MOJO_TIMING execution_planner::scheduling_priority_score", _ns_scheduling_priority_score, _acc_scheduling_priority_score)
    var _acc_prefetch_benefit_estimate: Float64 = 0.0
    var _t0_prefetch_benefit_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prefetch_benefit_estimate += prefetch_benefit_estimate(0.5, 0.5, 0.5)
    var _t1_prefetch_benefit_estimate = perf_counter_ns()
    var _ns_prefetch_benefit_estimate = Float64(_t1_prefetch_benefit_estimate - _t0_prefetch_benefit_estimate) / Float64(N)
    print("MOJO_TIMING execution_planner::prefetch_benefit_estimate", _ns_prefetch_benefit_estimate, _acc_prefetch_benefit_estimate)
    var _acc_graph_rewrite_gain: Float64 = 0.0
    var _t0_graph_rewrite_gain = perf_counter_ns()
    for _ in range(N):
        _acc_graph_rewrite_gain += graph_rewrite_gain(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_graph_rewrite_gain = perf_counter_ns()
    var _ns_graph_rewrite_gain = Float64(_t1_graph_rewrite_gain - _t0_graph_rewrite_gain) / Float64(N)
    print("MOJO_TIMING execution_planner::graph_rewrite_gain", _ns_graph_rewrite_gain, _acc_graph_rewrite_gain)
    var _acc_memory_placement_affinity: Float64 = 0.0
    var _t0_memory_placement_affinity = perf_counter_ns()
    for _ in range(N):
        _acc_memory_placement_affinity += memory_placement_affinity(0.5, 0.5, 0.5, 0.5)
    var _t1_memory_placement_affinity = perf_counter_ns()
    var _ns_memory_placement_affinity = Float64(_t1_memory_placement_affinity - _t0_memory_placement_affinity) / Float64(N)
    print("MOJO_TIMING execution_planner::memory_placement_affinity", _ns_memory_placement_affinity, _acc_memory_placement_affinity)
    var _acc_pipeline_depth_optimal: Float64 = 0.0
    var _t0_pipeline_depth_optimal = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_depth_optimal += pipeline_depth_optimal(0.5, 0.5, 0.5)
    var _t1_pipeline_depth_optimal = perf_counter_ns()
    var _ns_pipeline_depth_optimal = Float64(_t1_pipeline_depth_optimal - _t0_pipeline_depth_optimal) / Float64(N)
    print("MOJO_TIMING execution_planner::pipeline_depth_optimal", _ns_pipeline_depth_optimal, _acc_pipeline_depth_optimal)
    var _acc_adaptive_batch_size: Float64 = 0.0
    var _t0_adaptive_batch_size = perf_counter_ns()
    for _ in range(N):
        _acc_adaptive_batch_size += adaptive_batch_size(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adaptive_batch_size = perf_counter_ns()
    var _ns_adaptive_batch_size = Float64(_t1_adaptive_batch_size - _t0_adaptive_batch_size) / Float64(N)
    print("MOJO_TIMING execution_planner::adaptive_batch_size", _ns_adaptive_batch_size, _acc_adaptive_batch_size)
