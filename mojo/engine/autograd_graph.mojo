"""
autograd_graph.mojo — Computation graph and reverse-mode autodiff primitives.
Zero Python imports.

Public API:
  node_output_count              — fan-out for gradient accumulation
  grad_accumulate                — add incoming gradient to accumulator
  checkpointing_cost             — recompute vs memory tradeoff
  topological_sort_key           — depth-first ordering key
  grad_scale_loss                — gradient scaling for mixed precision
  memory_efficient_backward_step — gradient checkpointing memory
  jacobian_vector_product        — Jvp forward-mode component
  vector_jacobian_product        — vJp reverse-mode component
  dead_node_prune_score          — score zero-grad nodes for pruning
  gradient_norm_clip_scale       — global gradient norm clipping scale
"""
from std.math import sqrt, log, exp


def node_output_count(
    current_count: Float64
) -> Float64:
    """Increment fan-out count for a computation graph node.

    Tracks how many downstream nodes receive this node's output,
    used to know when gradient accumulation is complete.

    Args:
        current_count: Current output edge count.

    Returns:
        Incremented count.
    """
    return current_count + 1.0


def grad_accumulate(
    current_grad: Float64, incoming_grad: Float64
) -> Float64:
    """Accumulate incoming gradient into node gradient buffer.

    For nodes with multiple outputs, gradients from all consumers
    are summed before propagating backward.

    Args:
        current_grad: Accumulated gradient so far.
        incoming_grad: New gradient arriving from a consumer node.

    Returns:
        Updated accumulated gradient.
    """
    return current_grad + incoming_grad


def checkpointing_cost(
    memory_saved_bytes: Float64, recompute_flops: Float64,
    flops_per_second: Float64, memory_bandwidth: Float64
) -> Float64:
    """Cost-benefit ratio of activation checkpointing.

    ratio = recompute_time / memory_save_time
    < 1 → checkpointing saves more than it costs.

    Args:
        memory_saved_bytes: Bytes freed by not storing activations.
        recompute_flops: FLOPs needed to recompute the saved activations.
        flops_per_second: Hardware compute throughput.
        memory_bandwidth: Hardware memory bandwidth (bytes/sec).

    Returns:
        Cost ratio (< 1 = beneficial checkpointing).
    """
    if flops_per_second <= 0.0 or memory_bandwidth <= 0.0:
        return 1.0
    var recompute_time = recompute_flops / flops_per_second
    var memory_time = memory_saved_bytes / memory_bandwidth
    if memory_time <= 0.0:
        return 1.0
    return recompute_time / memory_time


def topological_sort_key(
    node_depth: Float64, node_id: Float64, n_nodes: Float64
) -> Float64:
    """Unique sort key for topological ordering of computation graph.

    key = depth × n_nodes + node_id

    Args:
        node_depth: Depth of node from input (0 = input nodes).
        node_id: Unique node identifier.
        n_nodes: Total nodes in graph.

    Returns:
        Sort key (lower = processed earlier in backward pass).
    """
    return node_depth * n_nodes + node_id


def grad_scale_loss(
    loss: Float64, scale_factor: Float64
) -> Float64:
    """Loss scaling for mixed-precision training.

    Multiply loss by scale before backward to avoid FP16 underflow.

    Args:
        loss: Original loss value.
        scale_factor: Gradient scale (2^16 typical).

    Returns:
        Scaled loss.
    """
    return loss * scale_factor


def memory_efficient_backward_step(
    segment_memory_bytes: Float64,
    n_segments: Float64,
    total_activation_bytes: Float64
) -> Float64:
    """Memory savings from gradient checkpointing segmentation.

    Stores only segment boundaries; recomputes internals.

    Args:
        segment_memory_bytes: Memory of one checkpoint segment.
        n_segments: Number of checkpoint segments.
        total_activation_bytes: Full activation memory without checkpointing.

    Returns:
        Memory reduction ratio (< 1 = savings).
    """
    if total_activation_bytes <= 0.0:
        return 1.0
    var stored = segment_memory_bytes * n_segments
    return stored / total_activation_bytes


def jacobian_vector_product(
    jvp_tangent: Float64, local_jacobian: Float64
) -> Float64:
    """Forward-mode JVP: one element of J × v.

    Args:
        jvp_tangent: Incoming tangent (forward-mode seed).
        local_jacobian: Local Jacobian element ∂y_i/∂x_j.

    Returns:
        Forward tangent propagated through this node.
    """
    return local_jacobian * jvp_tangent


def vector_jacobian_product(
    upstream_grad: Float64, local_jacobian: Float64
) -> Float64:
    """Reverse-mode VJP: one element of vᵀ × J.

    Args:
        upstream_grad: Upstream gradient (cotangent).
        local_jacobian: Local Jacobian element ∂y_i/∂x_j.

    Returns:
        Gradient propagated backward through this node.
    """
    return upstream_grad * local_jacobian


def dead_node_prune_score(
    grad_magnitude: Float64, threshold: Float64
) -> Float64:
    """Score for pruning zero-gradient nodes from computation graph.

    Returns 1.0 if node should be pruned, 0.0 if kept.

    Args:
        grad_magnitude: L∞ norm of gradients through this node.
        threshold: Minimum gradient magnitude to keep node.

    Returns:
        Prune decision (1.0 = prune, 0.0 = keep).
    """
    if grad_magnitude < threshold:
        return 1.0
    return 0.0


def gradient_norm_clip_scale(
    global_grad_norm: Float64, max_norm: Float64
) -> Float64:
    """Global gradient norm clipping scale factor.

    scale = min(1, max_norm / grad_norm)

    Args:
        global_grad_norm: L2 norm of all gradients concatenated.
        max_norm: Maximum allowed gradient norm.

    Returns:
        Multiplicative scale to apply to all gradients.
    """
    if global_grad_norm <= max_norm or global_grad_norm <= 0.0:
        return 1.0
    return max_norm / global_grad_norm
