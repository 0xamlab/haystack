"""
graph_compiler.mojo — Op fusion, dead op elimination, graph lowering math.
Zero Python imports.

Public API:
  fusion_benefit_score           — benefit of fusing two ops
  dead_op_elimination_check      — detect zero-output ops
  constant_folding_value         — fold compile-time constants
  op_reorder_priority            — op reordering for memory locality
  common_subexpr_hash            — CSE hash component
  graph_partition_cost           — cut cost for graph partitioning
  shape_inference_broadcast      — static shape inference for broadcast
  type_promotion_bits            — dtype promotion rules
  kernel_selection_score         — select best kernel for op+shape
  memory_layout_transform_cost   — cost of tensor layout conversion
"""
from std.math import sqrt, log, exp


def fusion_benefit_score(
    op_a_memory_bytes: Float64, op_b_memory_bytes: Float64,
    shared_intermediate_bytes: Float64, fusion_overhead: Float64
) -> Float64:
    """Estimate benefit of fusing op_a followed by op_b.

    benefit = shared_intermediate_bytes - fusion_overhead
    (positive = beneficial to fuse)

    Args:
        op_a_memory_bytes: Memory traffic of op_a alone.
        op_b_memory_bytes: Memory traffic of op_b alone.
        shared_intermediate_bytes: Bytes of intermediate tensor eliminated by fusion.
        fusion_overhead: Additional complexity cost from fusion.

    Returns:
        Fusion benefit (positive = fuse, negative = keep separate).
    """
    return shared_intermediate_bytes - fusion_overhead


def dead_op_elimination_check(
    output_consumer_count: Float64, grad_flow: Float64
) -> Float64:
    """Check if an op is dead (no consumers, no gradient flow).

    Returns 1.0 if op should be eliminated.

    Args:
        output_consumer_count: Number of ops consuming this output.
        grad_flow: Gradient magnitude flowing through this op.

    Returns:
        1.0 if dead (can eliminate), 0.0 if live.
    """
    if output_consumer_count <= 0.0 and grad_flow <= 0.0:
        return 1.0
    return 0.0


def constant_folding_value(
    is_constant: Float64, computed_value: Float64
) -> Float64:
    """Constant folding: replace constant-only subgraph with its value.

    Args:
        is_constant: 1.0 if all inputs to this op are compile-time constants.
        computed_value: Pre-computed result of the op.

    Returns:
        Folded value if constant, else 0 (caller handles non-constant case).
    """
    if is_constant > 0.5:
        return computed_value
    return 0.0


def op_reorder_priority(
    cache_miss_cost: Float64, compute_intensity: Float64,
    dependency_depth: Float64
) -> Float64:
    """Op reordering priority for memory-locality optimisation.

    Higher priority = schedule earlier to maximise cache reuse.
    priority = compute_intensity / (cache_miss_cost × depth)

    Args:
        cache_miss_cost: Expected cache misses if scheduled now.
        compute_intensity: Arithmetic intensity of this op.
        dependency_depth: Critical path depth (prevents reordering past deps).

    Returns:
        Scheduling priority score.
    """
    var denom = (cache_miss_cost + 1.0) * (dependency_depth + 1.0)
    if denom <= 0.0:
        return compute_intensity
    return compute_intensity / denom


def common_subexpr_hash(
    op_type: Float64, input_hash_a: Float64, input_hash_b: Float64
) -> Float64:
    """Common subexpression elimination hash component.

    hash = op_type × prime + input_hash_a × prime² + input_hash_b

    Args:
        op_type: Numeric op code.
        input_hash_a: Hash of first input.
        input_hash_b: Hash of second input.

    Returns:
        Combined hash for CSE lookup.
    """
    var prime = 31.0
    return op_type * prime * prime + input_hash_a * prime + input_hash_b


def graph_partition_cost(
    n_cross_edges: Float64, edge_bandwidth_bytes: Float64,
    n_devices: Float64
) -> Float64:
    """Cost of a graph partition cut (communication overhead).

    cost = n_cross_edges × edge_bandwidth_bytes / n_devices

    Args:
        n_cross_edges: Edges crossing partition boundary.
        edge_bandwidth_bytes: Data bytes per cut edge.
        n_devices: Target device count.

    Returns:
        Communication cost for this partition.
    """
    if n_devices <= 0.0:
        return n_cross_edges * edge_bandwidth_bytes
    return n_cross_edges * edge_bandwidth_bytes / n_devices


def shape_inference_broadcast(
    dim_a: Float64, dim_b: Float64
) -> Float64:
    """Static shape inference for broadcast dimensions.

    NumPy broadcast: max(a, b) if one is 1, else must match.

    Args:
        dim_a: Dimension size from tensor A.
        dim_b: Dimension size from tensor B.

    Returns:
        Output dimension size (-1 if incompatible).
    """
    if dim_a == dim_b:
        return dim_a
    if dim_a == 1.0:
        return dim_b
    if dim_b == 1.0:
        return dim_a
    return -1.0  # Incompatible shapes


def type_promotion_bits(
    dtype_a_bits: Float64, dtype_b_bits: Float64
) -> Float64:
    """Dtype promotion: result type for mixed-dtype ops.

    Rules: FP > INT, wider > narrower.

    Args:
        dtype_a_bits: Bits of first operand (8/16/32/64).
        dtype_b_bits: Bits of second operand.

    Returns:
        Result dtype bits.
    """
    if dtype_a_bits > dtype_b_bits:
        return dtype_a_bits
    return dtype_b_bits


def kernel_selection_score(
    kernel_flops_per_ns: Float64, shape_match_score: Float64,
    memory_efficiency: Float64
) -> Float64:
    """Score for selecting the best kernel implementation for an op.

    score = flops × shape_match × memory_efficiency

    Args:
        kernel_flops_per_ns: Kernel throughput for this shape.
        shape_match_score: How well kernel is tuned for this tensor shape.
        memory_efficiency: Memory access efficiency of this kernel.

    Returns:
        Kernel selection score (higher = better).
    """
    return kernel_flops_per_ns * shape_match_score * memory_efficiency


def memory_layout_transform_cost(
    n_elements: Float64, src_stride: Float64,
    dst_stride: Float64, dtype_bytes: Float64
) -> Float64:
    """Cost of tensor layout transformation (e.g. NCHW → NHWC).

    Cost ∝ n_elements × max(src_stride, dst_stride) × dtype_bytes

    Args:
        n_elements: Total tensor elements.
        src_stride: Stride of source layout.
        dst_stride: Stride of destination layout.
        dtype_bytes: Bytes per element.

    Returns:
        Estimated bytes accessed for layout transform.
    """
    var max_stride = src_stride if src_stride > dst_stride else dst_stride
    return n_elements * max_stride * dtype_bytes
