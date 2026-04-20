"""bench_graph_compiler.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from graph_compiler import fusion_benefit_score, dead_op_elimination_check, constant_folding_value, op_reorder_priority, common_subexpr_hash, graph_partition_cost, shape_inference_broadcast, type_promotion_bits, kernel_selection_score, memory_layout_transform_cost
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

    var _acc_fusion_benefit_score: Float64 = 0.0
    var _t0_fusion_benefit_score = perf_counter_ns()
    for _ in range(N):
        _acc_fusion_benefit_score += fusion_benefit_score(0.5, 0.5, 0.5, 0.5)
    var _t1_fusion_benefit_score = perf_counter_ns()
    var _ns_fusion_benefit_score = Float64(_t1_fusion_benefit_score - _t0_fusion_benefit_score) / Float64(N)
    print("MOJO_TIMING graph_compiler::fusion_benefit_score", _ns_fusion_benefit_score, _acc_fusion_benefit_score)
    var _acc_dead_op_elimination_check: Float64 = 0.0
    var _t0_dead_op_elimination_check = perf_counter_ns()
    for _ in range(N):
        _acc_dead_op_elimination_check += dead_op_elimination_check(0.5, 0.5)
    var _t1_dead_op_elimination_check = perf_counter_ns()
    var _ns_dead_op_elimination_check = Float64(_t1_dead_op_elimination_check - _t0_dead_op_elimination_check) / Float64(N)
    print("MOJO_TIMING graph_compiler::dead_op_elimination_check", _ns_dead_op_elimination_check, _acc_dead_op_elimination_check)
    var _acc_constant_folding_value: Float64 = 0.0
    var _t0_constant_folding_value = perf_counter_ns()
    for _ in range(N):
        _acc_constant_folding_value += constant_folding_value(0.5, 0.5)
    var _t1_constant_folding_value = perf_counter_ns()
    var _ns_constant_folding_value = Float64(_t1_constant_folding_value - _t0_constant_folding_value) / Float64(N)
    print("MOJO_TIMING graph_compiler::constant_folding_value", _ns_constant_folding_value, _acc_constant_folding_value)
    var _acc_op_reorder_priority: Float64 = 0.0
    var _t0_op_reorder_priority = perf_counter_ns()
    for _ in range(N):
        _acc_op_reorder_priority += op_reorder_priority(0.5, 0.5, 0.5)
    var _t1_op_reorder_priority = perf_counter_ns()
    var _ns_op_reorder_priority = Float64(_t1_op_reorder_priority - _t0_op_reorder_priority) / Float64(N)
    print("MOJO_TIMING graph_compiler::op_reorder_priority", _ns_op_reorder_priority, _acc_op_reorder_priority)
    var _acc_common_subexpr_hash: Float64 = 0.0
    var _t0_common_subexpr_hash = perf_counter_ns()
    for _ in range(N):
        _acc_common_subexpr_hash += common_subexpr_hash(0.5, 0.5, 0.5)
    var _t1_common_subexpr_hash = perf_counter_ns()
    var _ns_common_subexpr_hash = Float64(_t1_common_subexpr_hash - _t0_common_subexpr_hash) / Float64(N)
    print("MOJO_TIMING graph_compiler::common_subexpr_hash", _ns_common_subexpr_hash, _acc_common_subexpr_hash)
    var _acc_graph_partition_cost: Float64 = 0.0
    var _t0_graph_partition_cost = perf_counter_ns()
    for _ in range(N):
        _acc_graph_partition_cost += graph_partition_cost(0.5, 0.5, 0.5)
    var _t1_graph_partition_cost = perf_counter_ns()
    var _ns_graph_partition_cost = Float64(_t1_graph_partition_cost - _t0_graph_partition_cost) / Float64(N)
    print("MOJO_TIMING graph_compiler::graph_partition_cost", _ns_graph_partition_cost, _acc_graph_partition_cost)
    var _acc_shape_inference_broadcast: Float64 = 0.0
    var _t0_shape_inference_broadcast = perf_counter_ns()
    for _ in range(N):
        _acc_shape_inference_broadcast += shape_inference_broadcast(0.5, 0.5)
    var _t1_shape_inference_broadcast = perf_counter_ns()
    var _ns_shape_inference_broadcast = Float64(_t1_shape_inference_broadcast - _t0_shape_inference_broadcast) / Float64(N)
    print("MOJO_TIMING graph_compiler::shape_inference_broadcast", _ns_shape_inference_broadcast, _acc_shape_inference_broadcast)
    var _acc_type_promotion_bits: Float64 = 0.0
    var _t0_type_promotion_bits = perf_counter_ns()
    for _ in range(N):
        _acc_type_promotion_bits += type_promotion_bits(0.5, 0.5)
    var _t1_type_promotion_bits = perf_counter_ns()
    var _ns_type_promotion_bits = Float64(_t1_type_promotion_bits - _t0_type_promotion_bits) / Float64(N)
    print("MOJO_TIMING graph_compiler::type_promotion_bits", _ns_type_promotion_bits, _acc_type_promotion_bits)
    var _acc_kernel_selection_score: Float64 = 0.0
    var _t0_kernel_selection_score = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_selection_score += kernel_selection_score(0.5, 0.5, 0.5)
    var _t1_kernel_selection_score = perf_counter_ns()
    var _ns_kernel_selection_score = Float64(_t1_kernel_selection_score - _t0_kernel_selection_score) / Float64(N)
    print("MOJO_TIMING graph_compiler::kernel_selection_score", _ns_kernel_selection_score, _acc_kernel_selection_score)
    var _acc_memory_layout_transform_cost: Float64 = 0.0
    var _t0_memory_layout_transform_cost = perf_counter_ns()
    for _ in range(N):
        _acc_memory_layout_transform_cost += memory_layout_transform_cost(0.5, 0.5, 0.5, 0.5)
    var _t1_memory_layout_transform_cost = perf_counter_ns()
    var _ns_memory_layout_transform_cost = Float64(_t1_memory_layout_transform_cost - _t0_memory_layout_transform_cost) / Float64(N)
    print("MOJO_TIMING graph_compiler::memory_layout_transform_cost", _ns_memory_layout_transform_cost, _acc_memory_layout_transform_cost)
