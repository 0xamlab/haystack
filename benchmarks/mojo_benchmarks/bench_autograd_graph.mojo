"""bench_autograd_graph.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from autograd_graph import node_output_count, grad_accumulate, checkpointing_cost, topological_sort_key, grad_scale_loss, memory_efficient_backward_step, jacobian_vector_product, vector_jacobian_product, dead_node_prune_score, gradient_norm_clip_scale
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

    var _acc_node_output_count: Float64 = 0.0
    var _t0_node_output_count = perf_counter_ns()
    for _ in range(N):
        _acc_node_output_count += node_output_count(0.5)
    var _t1_node_output_count = perf_counter_ns()
    var _ns_node_output_count = Float64(_t1_node_output_count - _t0_node_output_count) / Float64(N)
    print("MOJO_TIMING autograd_graph::node_output_count", _ns_node_output_count, _acc_node_output_count)
    var _result_node_output_count = node_output_count(0.5)
    var _summary_node_output_count = _summary_float64(_result_node_output_count)
    print("MOJO_RESULT autograd_graph::node_output_count", _summary_node_output_count)
    var _acc_grad_accumulate: Float64 = 0.0
    var _t0_grad_accumulate = perf_counter_ns()
    for _ in range(N):
        _acc_grad_accumulate += grad_accumulate(0.5, 0.5)
    var _t1_grad_accumulate = perf_counter_ns()
    var _ns_grad_accumulate = Float64(_t1_grad_accumulate - _t0_grad_accumulate) / Float64(N)
    print("MOJO_TIMING autograd_graph::grad_accumulate", _ns_grad_accumulate, _acc_grad_accumulate)
    var _result_grad_accumulate = grad_accumulate(0.5, 0.5)
    var _summary_grad_accumulate = _summary_float64(_result_grad_accumulate)
    print("MOJO_RESULT autograd_graph::grad_accumulate", _summary_grad_accumulate)
    var _acc_checkpointing_cost: Float64 = 0.0
    var _t0_checkpointing_cost = perf_counter_ns()
    for _ in range(N):
        _acc_checkpointing_cost += checkpointing_cost(0.5, 0.5, 0.5, 0.5)
    var _t1_checkpointing_cost = perf_counter_ns()
    var _ns_checkpointing_cost = Float64(_t1_checkpointing_cost - _t0_checkpointing_cost) / Float64(N)
    print("MOJO_TIMING autograd_graph::checkpointing_cost", _ns_checkpointing_cost, _acc_checkpointing_cost)
    var _result_checkpointing_cost = checkpointing_cost(0.5, 0.5, 0.5, 0.5)
    var _summary_checkpointing_cost = _summary_float64(_result_checkpointing_cost)
    print("MOJO_RESULT autograd_graph::checkpointing_cost", _summary_checkpointing_cost)
    var _acc_topological_sort_key: Float64 = 0.0
    var _t0_topological_sort_key = perf_counter_ns()
    for _ in range(N):
        _acc_topological_sort_key += topological_sort_key(0.5, 0.5, 0.5)
    var _t1_topological_sort_key = perf_counter_ns()
    var _ns_topological_sort_key = Float64(_t1_topological_sort_key - _t0_topological_sort_key) / Float64(N)
    print("MOJO_TIMING autograd_graph::topological_sort_key", _ns_topological_sort_key, _acc_topological_sort_key)
    var _result_topological_sort_key = topological_sort_key(0.5, 0.5, 0.5)
    var _summary_topological_sort_key = _summary_float64(_result_topological_sort_key)
    print("MOJO_RESULT autograd_graph::topological_sort_key", _summary_topological_sort_key)
    var _acc_grad_scale_loss: Float64 = 0.0
    var _t0_grad_scale_loss = perf_counter_ns()
    for _ in range(N):
        _acc_grad_scale_loss += grad_scale_loss(0.5, 0.5)
    var _t1_grad_scale_loss = perf_counter_ns()
    var _ns_grad_scale_loss = Float64(_t1_grad_scale_loss - _t0_grad_scale_loss) / Float64(N)
    print("MOJO_TIMING autograd_graph::grad_scale_loss", _ns_grad_scale_loss, _acc_grad_scale_loss)
    var _result_grad_scale_loss = grad_scale_loss(0.5, 0.5)
    var _summary_grad_scale_loss = _summary_float64(_result_grad_scale_loss)
    print("MOJO_RESULT autograd_graph::grad_scale_loss", _summary_grad_scale_loss)
    var _acc_memory_efficient_backward_step: Float64 = 0.0
    var _t0_memory_efficient_backward_step = perf_counter_ns()
    for _ in range(N):
        _acc_memory_efficient_backward_step += memory_efficient_backward_step(0.5, 0.5, 0.5)
    var _t1_memory_efficient_backward_step = perf_counter_ns()
    var _ns_memory_efficient_backward_step = Float64(_t1_memory_efficient_backward_step - _t0_memory_efficient_backward_step) / Float64(N)
    print("MOJO_TIMING autograd_graph::memory_efficient_backward_step", _ns_memory_efficient_backward_step, _acc_memory_efficient_backward_step)
    var _result_memory_efficient_backward_step = memory_efficient_backward_step(0.5, 0.5, 0.5)
    var _summary_memory_efficient_backward_step = _summary_float64(_result_memory_efficient_backward_step)
    print("MOJO_RESULT autograd_graph::memory_efficient_backward_step", _summary_memory_efficient_backward_step)
    var _acc_jacobian_vector_product: Float64 = 0.0
    var _t0_jacobian_vector_product = perf_counter_ns()
    for _ in range(N):
        _acc_jacobian_vector_product += jacobian_vector_product(0.5, 0.5)
    var _t1_jacobian_vector_product = perf_counter_ns()
    var _ns_jacobian_vector_product = Float64(_t1_jacobian_vector_product - _t0_jacobian_vector_product) / Float64(N)
    print("MOJO_TIMING autograd_graph::jacobian_vector_product", _ns_jacobian_vector_product, _acc_jacobian_vector_product)
    var _result_jacobian_vector_product = jacobian_vector_product(0.5, 0.5)
    var _summary_jacobian_vector_product = _summary_float64(_result_jacobian_vector_product)
    print("MOJO_RESULT autograd_graph::jacobian_vector_product", _summary_jacobian_vector_product)
    var _acc_vector_jacobian_product: Float64 = 0.0
    var _t0_vector_jacobian_product = perf_counter_ns()
    for _ in range(N):
        _acc_vector_jacobian_product += vector_jacobian_product(0.5, 0.5)
    var _t1_vector_jacobian_product = perf_counter_ns()
    var _ns_vector_jacobian_product = Float64(_t1_vector_jacobian_product - _t0_vector_jacobian_product) / Float64(N)
    print("MOJO_TIMING autograd_graph::vector_jacobian_product", _ns_vector_jacobian_product, _acc_vector_jacobian_product)
    var _result_vector_jacobian_product = vector_jacobian_product(0.5, 0.5)
    var _summary_vector_jacobian_product = _summary_float64(_result_vector_jacobian_product)
    print("MOJO_RESULT autograd_graph::vector_jacobian_product", _summary_vector_jacobian_product)
    var _acc_dead_node_prune_score: Float64 = 0.0
    var _t0_dead_node_prune_score = perf_counter_ns()
    for _ in range(N):
        _acc_dead_node_prune_score += dead_node_prune_score(0.5, 0.5)
    var _t1_dead_node_prune_score = perf_counter_ns()
    var _ns_dead_node_prune_score = Float64(_t1_dead_node_prune_score - _t0_dead_node_prune_score) / Float64(N)
    print("MOJO_TIMING autograd_graph::dead_node_prune_score", _ns_dead_node_prune_score, _acc_dead_node_prune_score)
    var _result_dead_node_prune_score = dead_node_prune_score(0.5, 0.5)
    var _summary_dead_node_prune_score = _summary_float64(_result_dead_node_prune_score)
    print("MOJO_RESULT autograd_graph::dead_node_prune_score", _summary_dead_node_prune_score)
    var _acc_gradient_norm_clip_scale: Float64 = 0.0
    var _t0_gradient_norm_clip_scale = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_norm_clip_scale += gradient_norm_clip_scale(0.5, 0.5)
    var _t1_gradient_norm_clip_scale = perf_counter_ns()
    var _ns_gradient_norm_clip_scale = Float64(_t1_gradient_norm_clip_scale - _t0_gradient_norm_clip_scale) / Float64(N)
    print("MOJO_TIMING autograd_graph::gradient_norm_clip_scale", _ns_gradient_norm_clip_scale, _acc_gradient_norm_clip_scale)
    var _result_gradient_norm_clip_scale = gradient_norm_clip_scale(0.5, 0.5)
    var _summary_gradient_norm_clip_scale = _summary_float64(_result_gradient_norm_clip_scale)
    print("MOJO_RESULT autograd_graph::gradient_norm_clip_scale", _summary_gradient_norm_clip_scale)
