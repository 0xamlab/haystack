"""
weight_loader.mojo — Weight loading: sharded checkpoints, safetensors, lazy loading.
Zero Python imports.

Public API:
  shard_offset_bytes             — byte offset for weight shard
  safetensors_header_size        — safetensors header size estimate
  lazy_load_priority             — which weights to load first
  gguf_quantized_block_size      — GGUF quantized block byte size
  checkpoint_resume_step         — training resume step from checkpoint
  weight_diff_norm               — difference norm between checkpoints
  partial_load_coverage          — fraction of model weights loaded
  adapter_merge_ratio            — LoRA merge interpolation factor
  hf_model_index_shards          — HuggingFace index shard count
  weight_hash_verify             — rolling checksum verification
"""
from std.math import sqrt, log, exp


fn shard_offset_bytes(
    shard_id: Float64, params_per_shard: Float64, dtype_bytes: Float64
) -> Float64:
    """Byte offset for weight shard in sharded checkpoint.

    offset = shard_id × params_per_shard × dtype_bytes

    Args:
        shard_id: Shard index (0-indexed).
        params_per_shard: Parameters per shard.
        dtype_bytes: Bytes per parameter.

    Returns:
        Byte offset in checkpoint file.
    """
    return shard_id * params_per_shard * dtype_bytes


fn safetensors_header_size(
    n_tensors: Float64, avg_tensor_name_bytes: Float64
) -> Float64:
    """Safetensors JSON header size estimate.

    header ≈ n_tensors × (name + metadata) bytes

    Args:
        n_tensors: Number of tensors in the file.
        avg_tensor_name_bytes: Average tensor name length + JSON overhead.

    Returns:
        Estimated header size in bytes.
    """
    return n_tensors * (avg_tensor_name_bytes + 64.0)  # 64 bytes metadata per tensor


fn lazy_load_priority(
    layer_id: Float64, total_layers: Float64,
    current_inference_layer: Float64
) -> Float64:
    """Priority for lazy weight loading: load layers ahead of inference.

    Args:
        layer_id: Layer to potentially load.
        total_layers: Total model layers.
        current_inference_layer: Layer currently executing.

    Returns:
        Load priority (higher = load sooner).
    """
    var ahead = layer_id - current_inference_layer
    if ahead < 0.0:
        ahead = -ahead  # Already passed; low priority
        return 1.0 / (ahead + 1.0)
    return total_layers / (ahead + 1.0)


fn gguf_quantized_block_size(
    n_bits: Float64, block_size: Float64
) -> Float64:
    """GGUF quantized block size in bytes.

    Q4_0: 18 bytes per 32 elements; Q8_0: 34 bytes per 32.
    Approximation: ceil(n_bits × block_size / 8) + scale_bytes.

    Args:
        n_bits: Bits per weight.
        block_size: Elements per quantization block.

    Returns:
        Block size in bytes.
    """
    var data_bytes = Float64(Int64(n_bits * block_size / 8.0 + 0.5))
    var scale_bytes = 2.0  # FP16 scale per block
    return data_bytes + scale_bytes


fn checkpoint_resume_step(
    checkpoint_path_hash: Float64, step_encoded: Float64
) -> Float64:
    """Extract training step from checkpoint metadata (encoded).

    Args:
        checkpoint_path_hash: Hash of checkpoint path.
        step_encoded: Step number encoded in checkpoint metadata.

    Returns:
        Training step to resume from.
    """
    return step_encoded


fn weight_diff_norm(
    weight_new: Float64, weight_old: Float64
) -> Float64:
    """Squared difference contribution for weight change norm.

    Sum across all params then sqrt for L2 norm of weight change.

    Args:
        weight_new: Weight after training.
        weight_old: Weight before training.

    Returns:
        Squared difference.
    """
    var diff = weight_new - weight_old
    return diff * diff


fn partial_load_coverage(
    loaded_params: Float64, total_params: Float64
) -> Float64:
    """Fraction of model weights currently loaded in memory.

    Args:
        loaded_params: Parameters currently in GPU/CPU memory.
        total_params: Total model parameters.

    Returns:
        Load coverage (0–1).
    """
    if total_params <= 0.0:
        return 0.0
    return loaded_params / total_params


fn adapter_merge_ratio(
    base_weight: Float64, adapter_weight: Float64, alpha: Float64
) -> Float64:
    """Interpolate between base and adapter weights for deployment.

    w_merged = (1 - α) × base + α × adapter

    Args:
        base_weight: Original pre-trained weight.
        adapter_weight: Fine-tuned adapter weight.
        alpha: Merge ratio (0 = pure base, 1 = pure adapter).

    Returns:
        Merged weight element.
    """
    return (1.0 - alpha) * base_weight + alpha * adapter_weight


fn hf_model_index_shards(
    total_params: Float64, max_shard_bytes: Float64, dtype_bytes: Float64
) -> Float64:
    """Number of shards for HuggingFace model index (model.safetensors.index.json).

    Args:
        total_params: Total model parameters.
        max_shard_bytes: Maximum bytes per shard (5GB typical).
        dtype_bytes: Bytes per parameter.

    Returns:
        Number of shards.
    """
    var total_bytes = total_params * dtype_bytes
    if max_shard_bytes <= 0.0:
        return 1.0
    return Float64(Int64((total_bytes + max_shard_bytes - 1.0) / max_shard_bytes))


fn weight_hash_verify(
    accumulated_hash: Float64, weight: Float64, prime: Float64
) -> Float64:
    """Rolling polynomial hash for weight checkpoint verification.

    hash = hash × prime + weight_quantized

    Args:
        accumulated_hash: Running hash value.
        weight: Weight element.
        prime: Hash prime multiplier.

    Returns:
        Updated hash.
    """
    var quantized = Float64(Int64(weight * 10000.0 + 0.5))
    return accumulated_hash * prime + quantized
