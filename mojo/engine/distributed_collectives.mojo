"""
distributed_collectives.mojo — Multi-GPU/node communication: all-reduce, scatter, gather.
Zero Python imports.

Public API:
  ring_allreduce_step            — ring all-reduce chunk contribution
  reduce_scatter_element         — reduce-scatter shard element
  all_gather_offset              — all-gather element offset
  broadcast_scale                — broadcast normalisation factor
  gradient_compression_ratio     — gradient compression savings
  expert_dispatch_volume         — MoE expert-to-expert data volume
  peer_bandwidth_utilization     — point-to-point bandwidth usage
  collective_latency_alpha_beta  — alpha-beta model latency
  overlap_compute_comm_ratio     — compute/comm overlap efficiency
  allreduce_tree_step_count      — tree all-reduce step count
"""
from std.math import sqrt, log, exp


def ring_allreduce_step(
    local_chunk: Float64, recv_chunk: Float64,
    is_reduce_phase: Float64
) -> Float64:
    """Ring all-reduce: one step in reduce or broadcast phase.

    Reduce phase: chunk += recv_chunk
    Broadcast phase: chunk = recv_chunk (copy)

    Args:
        local_chunk: Local gradient chunk value.
        recv_chunk: Received chunk from left neighbour.
        is_reduce_phase: 1.0 = reduce, 0.0 = broadcast.

    Returns:
        Updated chunk value.
    """
    if is_reduce_phase > 0.5:
        return local_chunk + recv_chunk
    return recv_chunk


def reduce_scatter_element(
    grad_element: Float64, world_size: Float64
) -> Float64:
    """Reduce-scatter: divide element by world_size after reduction.

    Args:
        grad_element: Accumulated gradient element (sum across ranks).
        world_size: Number of workers.

    Returns:
        Averaged gradient element.
    """
    if world_size <= 0.0:
        return grad_element
    return grad_element / world_size


def all_gather_offset(
    rank: Float64, shard_size: Float64
) -> Float64:
    """All-gather byte offset for rank's shard.

    offset = rank × shard_size

    Args:
        rank: Worker rank.
        shard_size: Elements per shard.

    Returns:
        Starting element index for this rank's shard.
    """
    return rank * shard_size


def broadcast_scale(world_size: Float64) -> Float64:
    """Normalisation factor after reduce-broadcast (1/N).

    Args:
        world_size: Number of workers.

    Returns:
        Scale factor for averaging.
    """
    if world_size <= 0.0:
        return 1.0
    return 1.0 / world_size


def gradient_compression_ratio(
    original_bytes: Float64, compressed_bytes: Float64
) -> Float64:
    """Gradient compression savings ratio.

    ratio = 1 - compressed / original

    Args:
        original_bytes: Uncompressed gradient bytes.
        compressed_bytes: After compression (top-k, quantisation, etc.).

    Returns:
        Compression ratio (0 = no saving, 1 = perfect compression).
    """
    if original_bytes <= 0.0:
        return 0.0
    var ratio = 1.0 - compressed_bytes / original_bytes
    if ratio < 0.0:
        return 0.0
    return ratio


def expert_dispatch_volume(
    tokens_per_expert: Float64, hidden_dim: Float64,
    dtype_bytes: Float64
) -> Float64:
    """MoE expert dispatch data volume (bytes sent to expert device).

    volume = tokens × hidden_dim × dtype_bytes × 2 (send + recv)

    Args:
        tokens_per_expert: Tokens dispatched to this expert.
        hidden_dim: Hidden dimension size.
        dtype_bytes: Bytes per element.

    Returns:
        Bytes transferred for this expert dispatch.
    """
    return tokens_per_expert * hidden_dim * dtype_bytes * 2.0


def peer_bandwidth_utilization(
    bytes_transferred: Float64, link_bandwidth_gbs: Float64,
    elapsed_ms: Float64
) -> Float64:
    """Point-to-point link bandwidth utilization.

    Args:
        bytes_transferred: Bytes sent/received.
        link_bandwidth_gbs: Peak link bandwidth (GB/s).
        elapsed_ms: Transfer duration (ms).

    Returns:
        Utilization fraction (0–1).
    """
    if link_bandwidth_gbs <= 0.0 or elapsed_ms <= 0.0:
        return 0.0
    var peak_bytes = link_bandwidth_gbs * 1e9 * elapsed_ms / 1000.0
    var util = bytes_transferred / peak_bytes
    if util > 1.0:
        return 1.0
    return util


def collective_latency_alpha_beta(
    n_bytes: Float64, n_steps: Float64,
    alpha_us: Float64, beta_gbs: Float64
) -> Float64:
    """Alpha-beta model collective latency estimate.

    latency = n_steps × (alpha + n_bytes / beta)

    Args:
        n_bytes: Message size in bytes.
        n_steps: Number of communication rounds.
        alpha_us: Per-message latency (µs).
        beta_gbs: Bandwidth (GB/s).

    Returns:
        Total collective latency (µs).
    """
    if beta_gbs <= 0.0:
        return n_steps * alpha_us
    var bw_us_per_byte = 1.0 / (beta_gbs * 1000.0)  # µs/byte
    return n_steps * (alpha_us + n_bytes * bw_us_per_byte)


def overlap_compute_comm_ratio(
    compute_ms: Float64, comm_ms: Float64
) -> Float64:
    """Communication hidden by computation overlap efficiency.

    If comm_ms < compute_ms: full overlap possible.
    efficiency = min(1, compute / comm)

    Args:
        compute_ms: Compute kernel duration.
        comm_ms: Communication duration.

    Returns:
        Overlap efficiency (1.0 = fully hidden).
    """
    if comm_ms <= 0.0:
        return 1.0
    var ratio = compute_ms / comm_ms
    if ratio > 1.0:
        return 1.0
    return ratio


def allreduce_tree_step_count(world_size: Float64) -> Float64:
    """Tree all-reduce step count: log2(world_size) × 2.

    Args:
        world_size: Number of workers.

    Returns:
        Number of communication rounds.
    """
    if world_size <= 1.0:
        return 0.0
    return Float64(Int64(log(world_size) / 0.6931471805599453 + 0.5)) * 2.0
