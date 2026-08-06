"""
memory_system.mojo — Memory pooling, tensor layout, and activation checkpointing math.
Zero Python imports.

Public API:
  pool_fragmentation_ratio       — memory pool fragmentation estimate
  slab_alloc_waste               — slab allocator waste per object
  cache_line_padding_bytes       — padding to align to cache line
  strided_access_penalty         — memory access penalty for strided tensors
  activation_memory_bytes        — activation memory for a layer
  gradient_memory_bytes          — gradient memory estimate
  optimizer_state_bytes          — Adam optimizer state memory
  peak_memory_estimate           — peak memory during forward+backward
  memory_bandwidth_utilization   — effective memory bandwidth fraction
  numa_locality_score            — NUMA access locality metric
"""
from std.math import sqrt, log, exp


def pool_fragmentation_ratio(
    allocated_bytes: Float64, used_bytes: Float64
) -> Float64:
    """Memory pool fragmentation: (allocated - used) / allocated.

    Args:
        allocated_bytes: Total bytes reserved in pool.
        used_bytes: Bytes actively in use.

    Returns:
        Fragmentation ratio (0 = no waste, 1 = fully wasted).
    """
    if allocated_bytes <= 0.0:
        return 0.0
    var frag = (allocated_bytes - used_bytes) / allocated_bytes
    if frag < 0.0:
        return 0.0
    return frag


def slab_alloc_waste(
    object_size: Float64, slab_size: Float64
) -> Float64:
    """Waste per slab from non-integer number of objects.

    waste = slab_size mod object_size

    Args:
        object_size: Size of each allocated object (bytes).
        slab_size: Total slab size (bytes).

    Returns:
        Bytes wasted per slab.
    """
    if object_size <= 0.0:
        return 0.0
    var n_objects = Float64(Int64(slab_size / object_size))
    return slab_size - n_objects * object_size


def cache_line_padding_bytes(
    struct_size: Float64, cache_line: Float64
) -> Float64:
    """Bytes of padding needed to align struct to cache line boundary.

    Args:
        struct_size: Current struct size (bytes).
        cache_line: Cache line size (64 bytes CPU, 128 GPU).

    Returns:
        Padding bytes required.
    """
    if cache_line <= 0.0:
        return 0.0
    var remainder = struct_size - Float64(Int64(struct_size / cache_line)) * cache_line
    if remainder == 0.0:
        return 0.0
    return cache_line - remainder


def strided_access_penalty(
    stride_bytes: Float64, cache_line: Float64
) -> Float64:
    """Cache miss rate multiplier for strided memory access.

    penalty = stride / cache_line (1.0 = no penalty for contiguous).

    Args:
        stride_bytes: Bytes between successive accessed elements.
        cache_line: Cache line size.

    Returns:
        Penalty factor (≥ 1.0; higher = worse).
    """
    if cache_line <= 0.0:
        return 1.0
    var penalty = stride_bytes / cache_line
    if penalty < 1.0:
        return 1.0
    return penalty


def activation_memory_bytes(
    batch_size: Float64, seq_len: Float64,
    d_model: Float64, n_layers: Float64, dtype_bytes: Float64
) -> Float64:
    """Activation memory for transformer forward pass.

    Per layer: batch × seq × d_model × dtype_bytes
    Total: × n_layers × 2 (input + output)

    Args:
        batch_size: Batch size B.
        seq_len: Sequence length N.
        d_model: Hidden dimension.
        n_layers: Number of transformer layers.
        dtype_bytes: Bytes per element.

    Returns:
        Total activation memory in bytes.
    """
    return batch_size * seq_len * d_model * n_layers * 2.0 * dtype_bytes


def gradient_memory_bytes(
    n_parameters: Float64, dtype_bytes: Float64
) -> Float64:
    """Gradient memory: same shape as parameters.

    Args:
        n_parameters: Total trainable parameters.
        dtype_bytes: Gradient dtype bytes (4 for FP32).

    Returns:
        Gradient memory in bytes.
    """
    return n_parameters * dtype_bytes


def optimizer_state_bytes(
    n_parameters: Float64, optimizer_type: Float64
) -> Float64:
    """Optimizer state memory.

    optimizer_type: 1=SGD (0x extra), 2=SGD+momentum (1x), 3=Adam (2x).

    Args:
        n_parameters: Total parameters.
        optimizer_type: 1=SGD, 2=momentum, 3=Adam/AdamW.

    Returns:
        Optimizer state memory in FP32 bytes.
    """
    var multiplier = 0.0
    if optimizer_type >= 3.0:
        multiplier = 2.0  # m and v for Adam
    elif optimizer_type >= 2.0:
        multiplier = 1.0  # velocity for momentum
    return n_parameters * multiplier * 4.0


def peak_memory_estimate(
    model_weights_bytes: Float64, activation_bytes: Float64,
    gradient_bytes: Float64, optimizer_bytes: Float64
) -> Float64:
    """Peak GPU memory during training (forward + backward).

    peak = weights + activations + gradients + optimizer_states

    Args:
        model_weights_bytes: Model parameter memory.
        activation_bytes: Forward-pass activation memory.
        gradient_bytes: Gradient memory.
        optimizer_bytes: Optimizer state memory.

    Returns:
        Peak memory estimate in bytes.
    """
    return model_weights_bytes + activation_bytes + gradient_bytes + optimizer_bytes


def memory_bandwidth_utilization(
    actual_throughput_gbs: Float64, peak_bandwidth_gbs: Float64
) -> Float64:
    """Memory bandwidth utilization ratio.

    Args:
        actual_throughput_gbs: Measured bandwidth (GB/s).
        peak_bandwidth_gbs: Theoretical peak (GB/s).

    Returns:
        Utilization (0–1).
    """
    if peak_bandwidth_gbs <= 0.0:
        return 0.0
    var util = actual_throughput_gbs / peak_bandwidth_gbs
    if util > 1.0:
        return 1.0
    return util


def numa_locality_score(
    local_accesses: Float64, remote_accesses: Float64,
    remote_penalty: Float64
) -> Float64:
    """NUMA locality score: weighted effective access rate.

    score = local / (local + remote × penalty)

    Args:
        local_accesses: Accesses to local NUMA node.
        remote_accesses: Accesses to remote NUMA node.
        remote_penalty: Remote access latency multiplier (2–4×).

    Returns:
        Locality score (1.0 = fully local).
    """
    var total = local_accesses + remote_accesses * remote_penalty
    if total <= 0.0:
        return 1.0
    return local_accesses / total
