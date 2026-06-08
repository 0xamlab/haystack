"""bench_execution_planner.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from execution_planner import fusion_opportunity_score, device_placement_score, kv_policy_eviction_priority, batching_strategy_score, scheduling_priority_score, prefetch_benefit_estimate, graph_rewrite_gain, memory_placement_affinity, pipeline_depth_optimal, adaptive_batch_size
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

    var _acc_fusion_opportunity_score: Float64 = 0.0
    var _t0_fusion_opportunity_score = perf_counter_ns()
    for _ in range(N):
        _acc_fusion_opportunity_score += fusion_opportunity_score(0.5, 0.5, 0.5)
    var _t1_fusion_opportunity_score = perf_counter_ns()
    var _ns_fusion_opportunity_score = Float64(_t1_fusion_opportunity_score - _t0_fusion_opportunity_score) / Float64(N)
    print("MOJO_TIMING execution_planner::fusion_opportunity_score", _ns_fusion_opportunity_score, _acc_fusion_opportunity_score)
    var _result_fusion_opportunity_score = fusion_opportunity_score(0.5, 0.5, 0.5)
    var _summary_fusion_opportunity_score = _summary_float64(_result_fusion_opportunity_score)
    print("MOJO_RESULT execution_planner::fusion_opportunity_score", _summary_fusion_opportunity_score)
    var _acc_device_placement_score: Float64 = 0.0
    var _t0_device_placement_score = perf_counter_ns()
    for _ in range(N):
        _acc_device_placement_score += device_placement_score(0.5, 0.5, 0.5)
    var _t1_device_placement_score = perf_counter_ns()
    var _ns_device_placement_score = Float64(_t1_device_placement_score - _t0_device_placement_score) / Float64(N)
    print("MOJO_TIMING execution_planner::device_placement_score", _ns_device_placement_score, _acc_device_placement_score)
    var _result_device_placement_score = device_placement_score(0.5, 0.5, 0.5)
    var _summary_device_placement_score = _summary_float64(_result_device_placement_score)
    print("MOJO_RESULT execution_planner::device_placement_score", _summary_device_placement_score)
    var _acc_kv_policy_eviction_priority: Float64 = 0.0
    var _t0_kv_policy_eviction_priority = perf_counter_ns()
    for _ in range(N):
        _acc_kv_policy_eviction_priority += kv_policy_eviction_priority(0.5, 0.5, 0.5, 0.5)
    var _t1_kv_policy_eviction_priority = perf_counter_ns()
    var _ns_kv_policy_eviction_priority = Float64(_t1_kv_policy_eviction_priority - _t0_kv_policy_eviction_priority) / Float64(N)
    print("MOJO_TIMING execution_planner::kv_policy_eviction_priority", _ns_kv_policy_eviction_priority, _acc_kv_policy_eviction_priority)
    var _result_kv_policy_eviction_priority = kv_policy_eviction_priority(0.5, 0.5, 0.5, 0.5)
    var _summary_kv_policy_eviction_priority = _summary_float64(_result_kv_policy_eviction_priority)
    print("MOJO_RESULT execution_planner::kv_policy_eviction_priority", _summary_kv_policy_eviction_priority)
    var _acc_batching_strategy_score: Float64 = 0.0
    var _t0_batching_strategy_score = perf_counter_ns()
    for _ in range(N):
        _acc_batching_strategy_score += batching_strategy_score(0.5, 0.5, 0.5, 0.5)
    var _t1_batching_strategy_score = perf_counter_ns()
    var _ns_batching_strategy_score = Float64(_t1_batching_strategy_score - _t0_batching_strategy_score) / Float64(N)
    print("MOJO_TIMING execution_planner::batching_strategy_score", _ns_batching_strategy_score, _acc_batching_strategy_score)
    var _result_batching_strategy_score = batching_strategy_score(0.5, 0.5, 0.5, 0.5)
    var _summary_batching_strategy_score = _summary_float64(_result_batching_strategy_score)
    print("MOJO_RESULT execution_planner::batching_strategy_score", _summary_batching_strategy_score)
    var _acc_scheduling_priority_score: Float64 = 0.0
    var _t0_scheduling_priority_score = perf_counter_ns()
    for _ in range(N):
        _acc_scheduling_priority_score += scheduling_priority_score(0.5, 0.5, 0.5, 0.5)
    var _t1_scheduling_priority_score = perf_counter_ns()
    var _ns_scheduling_priority_score = Float64(_t1_scheduling_priority_score - _t0_scheduling_priority_score) / Float64(N)
    print("MOJO_TIMING execution_planner::scheduling_priority_score", _ns_scheduling_priority_score, _acc_scheduling_priority_score)
    var _result_scheduling_priority_score = scheduling_priority_score(0.5, 0.5, 0.5, 0.5)
    var _summary_scheduling_priority_score = _summary_float64(_result_scheduling_priority_score)
    print("MOJO_RESULT execution_planner::scheduling_priority_score", _summary_scheduling_priority_score)
    var _acc_prefetch_benefit_estimate: Float64 = 0.0
    var _t0_prefetch_benefit_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prefetch_benefit_estimate += prefetch_benefit_estimate(0.5, 0.5, 0.5)
    var _t1_prefetch_benefit_estimate = perf_counter_ns()
    var _ns_prefetch_benefit_estimate = Float64(_t1_prefetch_benefit_estimate - _t0_prefetch_benefit_estimate) / Float64(N)
    print("MOJO_TIMING execution_planner::prefetch_benefit_estimate", _ns_prefetch_benefit_estimate, _acc_prefetch_benefit_estimate)
    var _result_prefetch_benefit_estimate = prefetch_benefit_estimate(0.5, 0.5, 0.5)
    var _summary_prefetch_benefit_estimate = _summary_float64(_result_prefetch_benefit_estimate)
    print("MOJO_RESULT execution_planner::prefetch_benefit_estimate", _summary_prefetch_benefit_estimate)
    var _acc_graph_rewrite_gain: Float64 = 0.0
    var _t0_graph_rewrite_gain = perf_counter_ns()
    for _ in range(N):
        _acc_graph_rewrite_gain += graph_rewrite_gain(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_graph_rewrite_gain = perf_counter_ns()
    var _ns_graph_rewrite_gain = Float64(_t1_graph_rewrite_gain - _t0_graph_rewrite_gain) / Float64(N)
    print("MOJO_TIMING execution_planner::graph_rewrite_gain", _ns_graph_rewrite_gain, _acc_graph_rewrite_gain)
    var _result_graph_rewrite_gain = graph_rewrite_gain(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_graph_rewrite_gain = _summary_float64(_result_graph_rewrite_gain)
    print("MOJO_RESULT execution_planner::graph_rewrite_gain", _summary_graph_rewrite_gain)
    var _acc_memory_placement_affinity: Float64 = 0.0
    var _t0_memory_placement_affinity = perf_counter_ns()
    for _ in range(N):
        _acc_memory_placement_affinity += memory_placement_affinity(0.5, 0.5, 0.5, 0.5)
    var _t1_memory_placement_affinity = perf_counter_ns()
    var _ns_memory_placement_affinity = Float64(_t1_memory_placement_affinity - _t0_memory_placement_affinity) / Float64(N)
    print("MOJO_TIMING execution_planner::memory_placement_affinity", _ns_memory_placement_affinity, _acc_memory_placement_affinity)
    var _result_memory_placement_affinity = memory_placement_affinity(0.5, 0.5, 0.5, 0.5)
    var _summary_memory_placement_affinity = _summary_float64(_result_memory_placement_affinity)
    print("MOJO_RESULT execution_planner::memory_placement_affinity", _summary_memory_placement_affinity)
    var _acc_pipeline_depth_optimal: Float64 = 0.0
    var _t0_pipeline_depth_optimal = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_depth_optimal += pipeline_depth_optimal(0.5, 0.5, 0.5)
    var _t1_pipeline_depth_optimal = perf_counter_ns()
    var _ns_pipeline_depth_optimal = Float64(_t1_pipeline_depth_optimal - _t0_pipeline_depth_optimal) / Float64(N)
    print("MOJO_TIMING execution_planner::pipeline_depth_optimal", _ns_pipeline_depth_optimal, _acc_pipeline_depth_optimal)
    var _result_pipeline_depth_optimal = pipeline_depth_optimal(0.5, 0.5, 0.5)
    var _summary_pipeline_depth_optimal = _summary_float64(_result_pipeline_depth_optimal)
    print("MOJO_RESULT execution_planner::pipeline_depth_optimal", _summary_pipeline_depth_optimal)
    var _acc_adaptive_batch_size: Float64 = 0.0
    var _t0_adaptive_batch_size = perf_counter_ns()
    for _ in range(N):
        _acc_adaptive_batch_size += adaptive_batch_size(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adaptive_batch_size = perf_counter_ns()
    var _ns_adaptive_batch_size = Float64(_t1_adaptive_batch_size - _t0_adaptive_batch_size) / Float64(N)
    print("MOJO_TIMING execution_planner::adaptive_batch_size", _ns_adaptive_batch_size, _acc_adaptive_batch_size)
    var _result_adaptive_batch_size = adaptive_batch_size(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_adaptive_batch_size = _summary_float64(_result_adaptive_batch_size)
    print("MOJO_RESULT execution_planner::adaptive_batch_size", _summary_adaptive_batch_size)
