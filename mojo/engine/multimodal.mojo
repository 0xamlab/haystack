"""
multimodal.mojo — Image/audio/vision transformer and cross-modal fusion.
Zero Python imports.

Public API:
  image_patch_embed              — ViT patch embedding element
  image_patch_count              — number of patches from image
  spectrogram_mel_freq           — mel-scale frequency
  spectrogram_stft_magnitude     — STFT magnitude (simplified)
  audio_feature_norm             — audio feature normalisation
  vision_attention_scale         — ViT attention scaling
  cross_modal_similarity         — vision-language embedding similarity
  image_token_count              — tokens from image for LLM
  ocr_confidence_score           — OCR character confidence
  multimodal_fusion_weight       — modality fusion gate weight
"""
from std.math import sqrt, log, exp


fn image_patch_embed(
    pixel_value: Float64, weight: Float64, bias: Float64
) -> Float64:
    """Vision transformer patch embedding: one element of linear projection.

    embed = pixel × W + b

    Args:
        pixel_value: Flattened patch pixel value (0–1 normalised).
        weight: Patch embedding weight element.
        bias: Patch embedding bias element.

    Returns:
        Patch embedding element.
    """
    return pixel_value * weight + bias


fn image_patch_count(
    image_size: Float64, patch_size: Float64
) -> Float64:
    """Number of ViT patches from a square image.

    n_patches = (image_size / patch_size)²

    Args:
        image_size: Image height = width (pixels).
        patch_size: Patch size (16 for ViT-B/16).

    Returns:
        Total number of patches.
    """
    if patch_size <= 0.0:
        return 0.0
    var patches_per_side = image_size / patch_size
    return patches_per_side * patches_per_side


fn spectrogram_mel_freq(
    hz: Float64
) -> Float64:
    """Convert Hz to mel scale: mel = 2595 × log10(1 + hz/700).

    Args:
        hz: Frequency in Hertz.

    Returns:
        Mel-scale frequency.
    """
    return 2595.0 * log(1.0 + hz / 700.0) / 2.302585093  # log10 via log/ln(10)


fn spectrogram_stft_magnitude(
    real: Float64, imag: Float64
) -> Float64:
    """STFT magnitude from real and imaginary components.

    |X(f)| = sqrt(real² + imag²)

    Args:
        real: Real part of STFT bin.
        imag: Imaginary part of STFT bin.

    Returns:
        STFT magnitude.
    """
    return sqrt(real * real + imag * imag)


fn audio_feature_norm(
    feature: Float64, mean: Float64, std: Float64
) -> Float64:
    """Normalise audio feature (mel spectrogram, MFCC, etc.).

    x_norm = (x - μ) / σ

    Args:
        feature: Raw audio feature value.
        mean: Feature mean (computed over dataset).
        std: Feature standard deviation.

    Returns:
        Normalised feature.
    """
    if std <= 0.0:
        return 0.0
    return (feature - mean) / std


fn vision_attention_scale(head_dim: Float64) -> Float64:
    """Vision transformer attention scaling: 1/√d_head.

    Args:
        head_dim: Dimension per attention head.

    Returns:
        Attention scale factor.
    """
    if head_dim <= 0.0:
        return 1.0
    return 1.0 / sqrt(head_dim)


fn cross_modal_similarity(
    vision_embed: Float64, text_embed: Float64,
    vision_norm: Float64, text_norm: Float64,
    temperature: Float64
) -> Float64:
    """CLIP-style cross-modal cosine similarity.

    sim = cos(vision, text) / τ

    Args:
        vision_embed: Vision encoder embedding element.
        text_embed: Text encoder embedding element.
        vision_norm: L2 norm of vision embedding.
        text_norm: L2 norm of text embedding.
        temperature: CLIP temperature τ (learnable).

    Returns:
        Temperature-scaled similarity.
    """
    var denom = vision_norm * text_norm
    if denom <= 0.0 or temperature <= 0.0:
        return 0.0
    return (vision_embed * text_embed) / (denom * temperature)


fn image_token_count(
    image_size: Float64, patch_size: Float64, compression_factor: Float64
) -> Float64:
    """Number of tokens an image contributes to LLM context.

    Some models compress patches (LLaVA, Idefics): tokens = patches / compress.

    Args:
        image_size: Image resolution (square).
        patch_size: Patch size.
        compression_factor: Token compression ratio (1 = no compression).

    Returns:
        Image tokens in LLM context.
    """
    var n_patches = image_patch_count(image_size, patch_size)
    if compression_factor <= 0.0:
        return n_patches
    return Float64(Int64(n_patches / compression_factor + 0.5))


fn ocr_confidence_score(
    char_log_prob: Float64, seq_len: Float64
) -> Float64:
    """OCR character sequence confidence: exp(mean log prob).

    Args:
        char_log_prob: Sum of character log probabilities.
        seq_len: Number of characters in sequence.

    Returns:
        Sequence confidence (0–1).
    """
    if seq_len <= 0.0:
        return 0.0
    var mean_log_prob = char_log_prob / seq_len
    return exp(mean_log_prob)


fn multimodal_fusion_weight(
    modality_confidence: Float64, modality_relevance: Float64,
    n_modalities: Float64
) -> Float64:
    """Attention weight for modality fusion gate.

    weight = confidence × relevance / (sum across modalities)
    Returns unnormalised weight; caller normalises across modalities.

    Args:
        modality_confidence: Model confidence for this modality.
        modality_relevance: Task-specific relevance of modality.
        n_modalities: Number of modalities (for baseline uniform weight).

    Returns:
        Unnormalised fusion weight.
    """
    if n_modalities <= 0.0:
        return modality_confidence * modality_relevance
    return modality_confidence * modality_relevance
