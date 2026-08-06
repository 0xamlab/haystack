"""
model_serialization.mojo — Model format, loading, checkpointing math.
Zero Python imports.

Public API:
  weight_quantization_bits       — bits needed for given precision
  checkpoint_size_estimate       — model checkpoint byte estimate
  delta_compression_ratio        — gradient delta compression
  weight_sparsity_ratio          — fraction of near-zero weights
  model_flops_estimate           — FLOPs for forward pass
  onnx_op_count_estimate         — ONNX graph op estimate
  lora_parameter_count           — LoRA adapter parameter count
  pruning_sparsity_speedup       — pruning-induced speedup estimate
  weight_sharing_ratio           — parameter sharing compression
  version_hash_component         — model version checksum component
"""
from std.math import sqrt, log, exp


def weight_quantization_bits(
    precision: Float64
) -> Float64:
    """Bits required for given weight precision.

    1=binary, 2=INT2, 4=INT4, 8=INT8, 16=FP16, 32=FP32.

    Args:
        precision: Precision identifier (bits).

    Returns:
        Bits per weight.
    """
    if precision <= 1.0:
        return 1.0
    if precision <= 2.0:
        return 2.0
    if precision <= 4.0:
        return 4.0
    if precision <= 8.0:
        return 8.0
    if precision <= 16.0:
        return 16.0
    return 32.0


def checkpoint_size_estimate(
    n_parameters: Float64, dtype_bits: Float64,
    include_optimizer: Float64
) -> Float64:
    """Model checkpoint size in bytes.

    size = n_params × bits/8 × (1 + optimizer_multiplier)

    Args:
        n_parameters: Total model parameters.
        dtype_bits: Bits per weight (16 or 32).
        include_optimizer: 1.0 to include Adam states (3× model).

    Returns:
        Checkpoint size in bytes.
    """
    var base = n_parameters * dtype_bits / 8.0
    if include_optimizer > 0.5:
        return base * 3.0  # weights + m + v in FP32
    return base


def delta_compression_ratio(
    delta_norm: Float64, weight_norm: Float64
) -> Float64:
    """Gradient delta compression ratio: how sparse are weight updates.

    ratio = ||Δw|| / ||w||  (small → weights barely changed → compress well)

    Args:
        delta_norm: L2 norm of weight update.
        weight_norm: L2 norm of weights.

    Returns:
        Delta ratio (lower = more compressible).
    """
    if weight_norm <= 0.0:
        return 1.0
    return delta_norm / weight_norm


def weight_sparsity_ratio(
    near_zero_count: Float64, total_weights: Float64,
    threshold: Float64
) -> Float64:
    """Fraction of weights below sparsity threshold.

    Args:
        near_zero_count: Weights with |w| < threshold.
        total_weights: Total weight count.
        threshold: Sparsity threshold (unused here — count provided).

    Returns:
        Sparsity ratio (0–1).
    """
    if total_weights <= 0.0:
        return 0.0
    return near_zero_count / total_weights


def model_flops_estimate(
    n_params: Float64, seq_len: Float64, batch_size: Float64
) -> Float64:
    """FLOPs for one forward pass (Chinchilla approximation).

    FLOPs ≈ 2 × N × L × B  where N=params, L=seq_len, B=batch

    Args:
        n_params: Model parameters.
        seq_len: Sequence length.
        batch_size: Batch size.

    Returns:
        FLOPs estimate for one forward pass.
    """
    return 2.0 * n_params * seq_len * batch_size


def onnx_op_count_estimate(
    n_layers: Float64, ops_per_layer: Float64, n_heads: Float64
) -> Float64:
    """Estimate ONNX graph operator count for a transformer.

    Each layer: linear, attention, norm, activation ops.

    Args:
        n_layers: Transformer layers.
        ops_per_layer: Base ops per layer (Matmul, Add, etc.).
        n_heads: Attention heads (adds ops for head split/merge).

    Returns:
        Estimated ONNX op count.
    """
    return n_layers * (ops_per_layer + 4.0 * n_heads)


def lora_parameter_count(
    d_model: Float64, rank: Float64, n_target_modules: Float64
) -> Float64:
    """LoRA adapter parameter count.

    params = 2 × d_model × rank × n_modules  (A and B matrices)

    Args:
        d_model: Model hidden dimension.
        rank: LoRA rank r (4–64 typical).
        n_target_modules: Number of weight matrices adapted.

    Returns:
        Total LoRA parameter count.
    """
    return 2.0 * d_model * rank * n_target_modules


def pruning_sparsity_speedup(
    sparsity: Float64, memory_bound_fraction: Float64
) -> Float64:
    """Theoretical speedup from unstructured pruning.

    Speedup ≈ 1 / (1 - sparsity) for memory-bound ops.

    Args:
        sparsity: Fraction of pruned weights (0–1).
        memory_bound_fraction: Fraction of ops that are memory-bound.

    Returns:
        Effective speedup estimate.
    """
    var compute_speedup = 1.0 / (1.0 - sparsity + 1e-6)
    # Memory-bound ops benefit from sparsity; compute-bound less so
    return 1.0 + memory_bound_fraction * (compute_speedup - 1.0)


def weight_sharing_ratio(
    unique_weights: Float64, total_weights: Float64
) -> Float64:
    """Parameter sharing compression ratio.

    ratio = unique / total  (lower = more sharing = smaller model)

    Args:
        unique_weights: Number of unique weight values.
        total_weights: Total weight count.

    Returns:
        Sharing ratio (compression factor = 1/ratio).
    """
    if total_weights <= 0.0:
        return 1.0
    return unique_weights / total_weights


def version_hash_component(
    param_value: Float64, index: Float64, prime: Float64
) -> Float64:
    """Lightweight rolling hash component for model version checksums.

    hash = (hash × prime + param_quantised) mod large_prime

    Args:
        param_value: Weight value (will be rounded).
        index: Parameter index.
        prime: Hash prime multiplier.

    Returns:
        Hash accumulation step.
    """
    var quantised = Float64(Int64(param_value * 1000.0))
    return (index * prime + quantised)
