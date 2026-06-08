"""bench_graph_compiler.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from graph_compiler import fusion_benefit_score, dead_op_elimination_check, constant_folding_value, op_reorder_priority, common_subexpr_hash, graph_partition_cost, shape_inference_broadcast, type_promotion_bits, kernel_selection_score, memory_layout_transform_cost
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

    var _acc_fusion_benefit_score: Float64 = 0.0
    var _t0_fusion_benefit_score = perf_counter_ns()
    for _ in range(N):
        _acc_fusion_benefit_score += fusion_benefit_score(0.5, 0.5, 0.5, 0.5)
    var _t1_fusion_benefit_score = perf_counter_ns()
    var _ns_fusion_benefit_score = Float64(_t1_fusion_benefit_score - _t0_fusion_benefit_score) / Float64(N)
    print("MOJO_TIMING graph_compiler::fusion_benefit_score", _ns_fusion_benefit_score, _acc_fusion_benefit_score)
    var _result_fusion_benefit_score = fusion_benefit_score(0.5, 0.5, 0.5, 0.5)
    var _summary_fusion_benefit_score = _summary_float64(_result_fusion_benefit_score)
    print("MOJO_RESULT graph_compiler::fusion_benefit_score", _summary_fusion_benefit_score)
    var _acc_dead_op_elimination_check: Float64 = 0.0
    var _t0_dead_op_elimination_check = perf_counter_ns()
    for _ in range(N):
        _acc_dead_op_elimination_check += dead_op_elimination_check(0.5, 0.5)
    var _t1_dead_op_elimination_check = perf_counter_ns()
    var _ns_dead_op_elimination_check = Float64(_t1_dead_op_elimination_check - _t0_dead_op_elimination_check) / Float64(N)
    print("MOJO_TIMING graph_compiler::dead_op_elimination_check", _ns_dead_op_elimination_check, _acc_dead_op_elimination_check)
    var _result_dead_op_elimination_check = dead_op_elimination_check(0.5, 0.5)
    var _summary_dead_op_elimination_check = _summary_float64(_result_dead_op_elimination_check)
    print("MOJO_RESULT graph_compiler::dead_op_elimination_check", _summary_dead_op_elimination_check)
    var _acc_constant_folding_value: Float64 = 0.0
    var _t0_constant_folding_value = perf_counter_ns()
    for _ in range(N):
        _acc_constant_folding_value += constant_folding_value(0.5, 0.5)
    var _t1_constant_folding_value = perf_counter_ns()
    var _ns_constant_folding_value = Float64(_t1_constant_folding_value - _t0_constant_folding_value) / Float64(N)
    print("MOJO_TIMING graph_compiler::constant_folding_value", _ns_constant_folding_value, _acc_constant_folding_value)
    var _result_constant_folding_value = constant_folding_value(0.5, 0.5)
    var _summary_constant_folding_value = _summary_float64(_result_constant_folding_value)
    print("MOJO_RESULT graph_compiler::constant_folding_value", _summary_constant_folding_value)
    var _acc_op_reorder_priority: Float64 = 0.0
    var _t0_op_reorder_priority = perf_counter_ns()
    for _ in range(N):
        _acc_op_reorder_priority += op_reorder_priority(0.5, 0.5, 0.5)
    var _t1_op_reorder_priority = perf_counter_ns()
    var _ns_op_reorder_priority = Float64(_t1_op_reorder_priority - _t0_op_reorder_priority) / Float64(N)
    print("MOJO_TIMING graph_compiler::op_reorder_priority", _ns_op_reorder_priority, _acc_op_reorder_priority)
    var _result_op_reorder_priority = op_reorder_priority(0.5, 0.5, 0.5)
    var _summary_op_reorder_priority = _summary_float64(_result_op_reorder_priority)
    print("MOJO_RESULT graph_compiler::op_reorder_priority", _summary_op_reorder_priority)
    var _acc_common_subexpr_hash: Float64 = 0.0
    var _t0_common_subexpr_hash = perf_counter_ns()
    for _ in range(N):
        _acc_common_subexpr_hash += common_subexpr_hash(0.5, 0.5, 0.5)
    var _t1_common_subexpr_hash = perf_counter_ns()
    var _ns_common_subexpr_hash = Float64(_t1_common_subexpr_hash - _t0_common_subexpr_hash) / Float64(N)
    print("MOJO_TIMING graph_compiler::common_subexpr_hash", _ns_common_subexpr_hash, _acc_common_subexpr_hash)
    var _result_common_subexpr_hash = common_subexpr_hash(0.5, 0.5, 0.5)
    var _summary_common_subexpr_hash = _summary_float64(_result_common_subexpr_hash)
    print("MOJO_RESULT graph_compiler::common_subexpr_hash", _summary_common_subexpr_hash)
    var _acc_graph_partition_cost: Float64 = 0.0
    var _t0_graph_partition_cost = perf_counter_ns()
    for _ in range(N):
        _acc_graph_partition_cost += graph_partition_cost(0.5, 0.5, 0.5)
    var _t1_graph_partition_cost = perf_counter_ns()
    var _ns_graph_partition_cost = Float64(_t1_graph_partition_cost - _t0_graph_partition_cost) / Float64(N)
    print("MOJO_TIMING graph_compiler::graph_partition_cost", _ns_graph_partition_cost, _acc_graph_partition_cost)
    var _result_graph_partition_cost = graph_partition_cost(0.5, 0.5, 0.5)
    var _summary_graph_partition_cost = _summary_float64(_result_graph_partition_cost)
    print("MOJO_RESULT graph_compiler::graph_partition_cost", _summary_graph_partition_cost)
    var _acc_shape_inference_broadcast: Float64 = 0.0
    var _t0_shape_inference_broadcast = perf_counter_ns()
    for _ in range(N):
        _acc_shape_inference_broadcast += shape_inference_broadcast(0.5, 0.5)
    var _t1_shape_inference_broadcast = perf_counter_ns()
    var _ns_shape_inference_broadcast = Float64(_t1_shape_inference_broadcast - _t0_shape_inference_broadcast) / Float64(N)
    print("MOJO_TIMING graph_compiler::shape_inference_broadcast", _ns_shape_inference_broadcast, _acc_shape_inference_broadcast)
    var _result_shape_inference_broadcast = shape_inference_broadcast(0.5, 0.5)
    var _summary_shape_inference_broadcast = _summary_float64(_result_shape_inference_broadcast)
    print("MOJO_RESULT graph_compiler::shape_inference_broadcast", _summary_shape_inference_broadcast)
    var _acc_type_promotion_bits: Float64 = 0.0
    var _t0_type_promotion_bits = perf_counter_ns()
    for _ in range(N):
        _acc_type_promotion_bits += type_promotion_bits(0.5, 0.5)
    var _t1_type_promotion_bits = perf_counter_ns()
    var _ns_type_promotion_bits = Float64(_t1_type_promotion_bits - _t0_type_promotion_bits) / Float64(N)
    print("MOJO_TIMING graph_compiler::type_promotion_bits", _ns_type_promotion_bits, _acc_type_promotion_bits)
    var _result_type_promotion_bits = type_promotion_bits(0.5, 0.5)
    var _summary_type_promotion_bits = _summary_float64(_result_type_promotion_bits)
    print("MOJO_RESULT graph_compiler::type_promotion_bits", _summary_type_promotion_bits)
    var _acc_kernel_selection_score: Float64 = 0.0
    var _t0_kernel_selection_score = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_selection_score += kernel_selection_score(0.5, 0.5, 0.5)
    var _t1_kernel_selection_score = perf_counter_ns()
    var _ns_kernel_selection_score = Float64(_t1_kernel_selection_score - _t0_kernel_selection_score) / Float64(N)
    print("MOJO_TIMING graph_compiler::kernel_selection_score", _ns_kernel_selection_score, _acc_kernel_selection_score)
    var _result_kernel_selection_score = kernel_selection_score(0.5, 0.5, 0.5)
    var _summary_kernel_selection_score = _summary_float64(_result_kernel_selection_score)
    print("MOJO_RESULT graph_compiler::kernel_selection_score", _summary_kernel_selection_score)
    var _acc_memory_layout_transform_cost: Float64 = 0.0
    var _t0_memory_layout_transform_cost = perf_counter_ns()
    for _ in range(N):
        _acc_memory_layout_transform_cost += memory_layout_transform_cost(0.5, 0.5, 0.5, 0.5)
    var _t1_memory_layout_transform_cost = perf_counter_ns()
    var _ns_memory_layout_transform_cost = Float64(_t1_memory_layout_transform_cost - _t0_memory_layout_transform_cost) / Float64(N)
    print("MOJO_TIMING graph_compiler::memory_layout_transform_cost", _ns_memory_layout_transform_cost, _acc_memory_layout_transform_cost)
    var _result_memory_layout_transform_cost = memory_layout_transform_cost(0.5, 0.5, 0.5, 0.5)
    var _summary_memory_layout_transform_cost = _summary_float64(_result_memory_layout_transform_cost)
    print("MOJO_RESULT graph_compiler::memory_layout_transform_cost", _summary_memory_layout_transform_cost)
