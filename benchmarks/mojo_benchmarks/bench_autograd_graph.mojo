"""bench_autograd_graph.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from autograd_graph import node_output_count, grad_accumulate, checkpointing_cost, topological_sort_key, grad_scale_loss, memory_efficient_backward_step, jacobian_vector_product, vector_jacobian_product, dead_node_prune_score, gradient_norm_clip_scale
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

    var _acc_node_output_count: Float64 = 0.0
    var _t0_node_output_count = perf_counter_ns()
    for _ in range(N):
        _acc_node_output_count += node_output_count(0.5)
    var _t1_node_output_count = perf_counter_ns()
    var _ns_node_output_count = Float64(_t1_node_output_count - _t0_node_output_count) / Float64(N)
    print("MOJO_TIMING autograd_graph::node_output_count", _ns_node_output_count, _acc_node_output_count)
    var _acc_grad_accumulate: Float64 = 0.0
    var _t0_grad_accumulate = perf_counter_ns()
    for _ in range(N):
        _acc_grad_accumulate += grad_accumulate(0.5, 0.5)
    var _t1_grad_accumulate = perf_counter_ns()
    var _ns_grad_accumulate = Float64(_t1_grad_accumulate - _t0_grad_accumulate) / Float64(N)
    print("MOJO_TIMING autograd_graph::grad_accumulate", _ns_grad_accumulate, _acc_grad_accumulate)
    var _acc_checkpointing_cost: Float64 = 0.0
    var _t0_checkpointing_cost = perf_counter_ns()
    for _ in range(N):
        _acc_checkpointing_cost += checkpointing_cost(0.5, 0.5, 0.5, 0.5)
    var _t1_checkpointing_cost = perf_counter_ns()
    var _ns_checkpointing_cost = Float64(_t1_checkpointing_cost - _t0_checkpointing_cost) / Float64(N)
    print("MOJO_TIMING autograd_graph::checkpointing_cost", _ns_checkpointing_cost, _acc_checkpointing_cost)
    var _acc_topological_sort_key: Float64 = 0.0
    var _t0_topological_sort_key = perf_counter_ns()
    for _ in range(N):
        _acc_topological_sort_key += topological_sort_key(0.5, 0.5, 0.5)
    var _t1_topological_sort_key = perf_counter_ns()
    var _ns_topological_sort_key = Float64(_t1_topological_sort_key - _t0_topological_sort_key) / Float64(N)
    print("MOJO_TIMING autograd_graph::topological_sort_key", _ns_topological_sort_key, _acc_topological_sort_key)
    var _acc_grad_scale_loss: Float64 = 0.0
    var _t0_grad_scale_loss = perf_counter_ns()
    for _ in range(N):
        _acc_grad_scale_loss += grad_scale_loss(0.5, 0.5)
    var _t1_grad_scale_loss = perf_counter_ns()
    var _ns_grad_scale_loss = Float64(_t1_grad_scale_loss - _t0_grad_scale_loss) / Float64(N)
    print("MOJO_TIMING autograd_graph::grad_scale_loss", _ns_grad_scale_loss, _acc_grad_scale_loss)
    var _acc_memory_efficient_backward_step: Float64 = 0.0
    var _t0_memory_efficient_backward_step = perf_counter_ns()
    for _ in range(N):
        _acc_memory_efficient_backward_step += memory_efficient_backward_step(0.5, 0.5, 0.5)
    var _t1_memory_efficient_backward_step = perf_counter_ns()
    var _ns_memory_efficient_backward_step = Float64(_t1_memory_efficient_backward_step - _t0_memory_efficient_backward_step) / Float64(N)
    print("MOJO_TIMING autograd_graph::memory_efficient_backward_step", _ns_memory_efficient_backward_step, _acc_memory_efficient_backward_step)
    var _acc_jacobian_vector_product: Float64 = 0.0
    var _t0_jacobian_vector_product = perf_counter_ns()
    for _ in range(N):
        _acc_jacobian_vector_product += jacobian_vector_product(0.5, 0.5)
    var _t1_jacobian_vector_product = perf_counter_ns()
    var _ns_jacobian_vector_product = Float64(_t1_jacobian_vector_product - _t0_jacobian_vector_product) / Float64(N)
    print("MOJO_TIMING autograd_graph::jacobian_vector_product", _ns_jacobian_vector_product, _acc_jacobian_vector_product)
    var _acc_vector_jacobian_product: Float64 = 0.0
    var _t0_vector_jacobian_product = perf_counter_ns()
    for _ in range(N):
        _acc_vector_jacobian_product += vector_jacobian_product(0.5, 0.5)
    var _t1_vector_jacobian_product = perf_counter_ns()
    var _ns_vector_jacobian_product = Float64(_t1_vector_jacobian_product - _t0_vector_jacobian_product) / Float64(N)
    print("MOJO_TIMING autograd_graph::vector_jacobian_product", _ns_vector_jacobian_product, _acc_vector_jacobian_product)
    var _acc_dead_node_prune_score: Float64 = 0.0
    var _t0_dead_node_prune_score = perf_counter_ns()
    for _ in range(N):
        _acc_dead_node_prune_score += dead_node_prune_score(0.5, 0.5)
    var _t1_dead_node_prune_score = perf_counter_ns()
    var _ns_dead_node_prune_score = Float64(_t1_dead_node_prune_score - _t0_dead_node_prune_score) / Float64(N)
    print("MOJO_TIMING autograd_graph::dead_node_prune_score", _ns_dead_node_prune_score, _acc_dead_node_prune_score)
    var _acc_gradient_norm_clip_scale: Float64 = 0.0
    var _t0_gradient_norm_clip_scale = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_norm_clip_scale += gradient_norm_clip_scale(0.5, 0.5)
    var _t1_gradient_norm_clip_scale = perf_counter_ns()
    var _ns_gradient_norm_clip_scale = Float64(_t1_gradient_norm_clip_scale - _t0_gradient_norm_clip_scale) / Float64(N)
    print("MOJO_TIMING autograd_graph::gradient_norm_clip_scale", _ns_gradient_norm_clip_scale, _acc_gradient_norm_clip_scale)
