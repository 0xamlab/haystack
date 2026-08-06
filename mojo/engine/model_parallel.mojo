"""
model_parallel.mojo — Data, model, and pipeline parallelism math.
Zero Python imports.

Public API:
  data_parallel_gradient_scale   — gradient scaling for data parallelism
  tensor_parallel_split_dim      — tensor parallel shard dimension
  pipeline_bubble_fraction       — pipeline parallel bubble overhead
  gradient_all_reduce_bytes      — all-reduce communication volume
  activation_checkpointing_ratio — memory savings from checkpointing
  pipeline_stage_assignment      — layer to pipeline stage mapping
  microbatch_throughput          — pipeline microbatch efficiency
  zero_stage3_param_bytes        — ZeRO-3 parameter shard size
  communication_computation_ratio — overlap feasibility metric
  ddp_sync_overhead              — DDP gradient sync overhead estimate
"""
from std.math import sqrt, log, exp


def data_parallel_gradient_scale(
    world_size: Float64
) -> Float64:
    """Gradient scale factor for data parallelism: 1/world_size.

    Gradients must be averaged across all replicas.

    Args:
        world_size: Number of data-parallel processes.

    Returns:
        Gradient averaging factor.
    """
    if world_size <= 0.0:
        return 1.0
    return 1.0 / world_size


def tensor_parallel_split_dim(
    total_dim: Float64, tp_degree: Float64
) -> Float64:
    """Shard size for tensor parallelism.

    Each device holds total_dim / tp_degree elements.

    Args:
        total_dim: Full dimension size (e.g., d_model or FFN hidden).
        tp_degree: Tensor parallelism degree.

    Returns:
        Per-device shard size.
    """
    if tp_degree <= 0.0:
        return total_dim
    return total_dim / tp_degree


def pipeline_bubble_fraction(
    n_stages: Float64, n_microbatches: Float64
) -> Float64:
    """Pipeline parallel bubble fraction: (p-1)/(m+p-1).

    Args:
        n_stages: Number of pipeline stages p.
        n_microbatches: Number of microbatches m.

    Returns:
        Pipeline bubble fraction (lower = more efficient).
    """
    var total = n_microbatches + n_stages - 1.0
    if total <= 0.0:
        return 1.0
    return (n_stages - 1.0) / total


def gradient_all_reduce_bytes(
    n_parameters: Float64, dtype_bytes: Float64, world_size: Float64
) -> Float64:
    """All-reduce communication volume for gradient synchronisation.

    Ring all-reduce: 2 × (world_size-1)/world_size × n_params × bytes.

    Args:
        n_parameters: Total gradient parameters.
        dtype_bytes: Bytes per gradient element.
        world_size: Number of workers.

    Returns:
        Total bytes communicated per all-reduce.
    """
    if world_size <= 1.0:
        return 0.0
    return 2.0 * (world_size - 1.0) / world_size * n_parameters * dtype_bytes


def activation_checkpointing_ratio(
    n_checkpointed_layers: Float64, total_layers: Float64
) -> Float64:
    """Memory saved fraction by activation checkpointing select layers.

    Args:
        n_checkpointed_layers: Layers where activations are recomputed.
        total_layers: Total transformer layers.

    Returns:
        Fraction of activation memory freed.
    """
    if total_layers <= 0.0:
        return 0.0
    return n_checkpointed_layers / total_layers


def pipeline_stage_assignment(
    layer_id: Float64, total_layers: Float64, n_stages: Float64
) -> Float64:
    """Assign a transformer layer to a pipeline stage.

    stage = floor(layer_id × n_stages / total_layers)

    Args:
        layer_id: Layer index (0-indexed).
        total_layers: Total layers.
        n_stages: Pipeline stages.

    Returns:
        Stage index for this layer.
    """
    if total_layers <= 0.0 or n_stages <= 0.0:
        return 0.0
    var stage = Float64(Int64(layer_id * n_stages / total_layers))
    if stage >= n_stages:
        return n_stages - 1.0
    return stage


def microbatch_throughput(
    microbatch_size: Float64, n_microbatches: Float64,
    pipeline_time: Float64
) -> Float64:
    """Effective throughput samples/sec for pipeline parallelism.

    Args:
        microbatch_size: Samples per microbatch.
        n_microbatches: Number of microbatches per global batch.
        pipeline_time: Total pipeline execution time (ms).

    Returns:
        Samples per second.
    """
    if pipeline_time <= 0.0:
        return 0.0
    return microbatch_size * n_microbatches / (pipeline_time / 1000.0)


def zero_stage3_param_bytes(
    total_param_bytes: Float64, world_size: Float64
) -> Float64:
    """ZeRO Stage 3: parameter shard per device.

    Each device holds 1/world_size of parameters.

    Args:
        total_param_bytes: Total model parameter bytes.
        world_size: Number of data-parallel devices.

    Returns:
        Parameter bytes per device under ZeRO-3.
    """
    if world_size <= 0.0:
        return total_param_bytes
    return total_param_bytes / world_size


def communication_computation_ratio(
    comm_bytes: Float64, bandwidth_gbs: Float64,
    compute_time_ms: Float64
) -> Float64:
    """Ratio of communication to computation time.

    < 1 → communication hidden by computation (overlap possible).

    Args:
        comm_bytes: Bytes to communicate.
        bandwidth_gbs: Network bandwidth (GB/s).
        compute_time_ms: Compute time to overlap with.

    Returns:
        Comm/compute ratio (< 1 = overlap feasible).
    """
    if bandwidth_gbs <= 0.0 or compute_time_ms <= 0.0:
        return 1.0
    var comm_time_ms = comm_bytes / (bandwidth_gbs * 1e9) * 1000.0
    return comm_time_ms / compute_time_ms


def ddp_sync_overhead(
    grad_sync_time_ms: Float64, step_time_ms: Float64
) -> Float64:
    """DDP gradient synchronisation overhead fraction.

    Args:
        grad_sync_time_ms: Time for gradient all-reduce.
        step_time_ms: Total training step time.

    Returns:
        Synchronisation overhead fraction (0–1).
    """
    if step_time_ms <= 0.0:
        return 0.0
    var overhead = grad_sync_time_ms / step_time_ms
    if overhead > 1.0:
        return 1.0
    return overhead
