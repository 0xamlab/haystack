"""
transformer_blocks.mojo — Full transformer block primitives (MHA, FFN, residual).
Zero Python imports.

Public API:
  multi_head_split_head          — per-head dimension slice
  feedforward_layer1             — FFN first linear + activation
  feedforward_layer2             — FFN second linear projection
  residual_connection            — x + sublayer(x)
  pre_norm                       — pre-norm residual pattern
  post_norm                      — post-norm residual pattern
  causal_mask_logit              — apply causal mask to attention logit
  attention_head_output          — weighted value sum for one head
  gated_feedforward              — gated FFN (SwiGLU variant)
  dropout_scale                  — inverted dropout at training time
"""
from std.math import sqrt, log, exp


fn multi_head_split_head(
    embedding_val: Float64, head: Float64,
    head_dim: Float64, d_model: Float64
) -> Float64:
    """Extract head-specific element from a projected embedding.

    Conceptually: head_output = W_q × x sliced to [head × head_dim : (head+1) × head_dim].
    Returns the scale factor 1/√head_dim (applied during attention).

    Args:
        embedding_val: Projected embedding element (Q, K, or V).
        head: Head index.
        head_dim: Dimension per head.
        d_model: Full model dimension.

    Returns:
        Scaled element for this head.
    """
    if head_dim <= 0.0 or d_model <= 0.0:
        return 0.0
    return embedding_val / sqrt(head_dim)


fn feedforward_layer1(
    x: Float64, weight: Float64, bias: Float64
) -> Float64:
    """FFN first linear layer: y = x × W + b.

    Apply activation (GELU/SiLU) outside this function.

    Args:
        x: Input activation.
        weight: Weight element W[i,j].
        bias: Bias b[j].

    Returns:
        Pre-activation linear output element.
    """
    return x * weight + bias


fn feedforward_layer2(
    x: Float64, weight: Float64, bias: Float64
) -> Float64:
    """FFN second linear projection: y = activated × W2 + b2.

    Args:
        x: Activated intermediate (after GELU/SiLU from layer1).
        weight: Output weight element.
        bias: Output bias element.

    Returns:
        FFN output element.
    """
    return x * weight + bias


fn residual_connection(x: Float64, sublayer_out: Float64) -> Float64:
    """Residual connection: y = x + sublayer(x).

    Args:
        x: Input to the sublayer.
        sublayer_out: Output of the sublayer (attention or FFN).

    Returns:
        Residual output.
    """
    return x + sublayer_out


fn pre_norm(
    x: Float64, norm_out: Float64, sublayer_out: Float64
) -> Float64:
    """Pre-norm residual: y = x + sublayer(LayerNorm(x)).

    Args:
        x: Original input (bypass).
        norm_out: Layer-normed x (passed to sublayer).
        sublayer_out: sublayer(LayerNorm(x)) output element.

    Returns:
        Pre-norm residual output.
    """
    return x + sublayer_out


fn post_norm(
    x: Float64, sublayer_out: Float64, norm_scale: Float64, norm_bias: Float64
) -> Float64:
    """Post-norm residual: y = LayerNorm(x + sublayer(x)).

    Simplified: applies residual then a single scale/shift.

    Args:
        x: Input.
        sublayer_out: Sublayer output.
        norm_scale: LayerNorm γ scale.
        norm_bias: LayerNorm β shift.

    Returns:
        Post-norm residual (partial — caller handles full norm).
    """
    return (x + sublayer_out) * norm_scale + norm_bias


fn causal_mask_logit(
    logit: Float64, query_pos: Float64, key_pos: Float64
) -> Float64:
    """Apply causal (autoregressive) mask: -inf if key > query position.

    Args:
        logit: Raw attention logit.
        query_pos: Position of query token.
        key_pos: Position of key token.

    Returns:
        Masked logit (-1e9 if key is future, else unchanged).
    """
    if key_pos > query_pos:
        return -1e9
    return logit


fn attention_head_output(
    value: Float64, attention_weight: Float64
) -> Float64:
    """Weighted value sum for one attention head: Σ α_i × v_i.

    This is one term; caller accumulates across sequence positions.

    Args:
        value: Value vector element V[k, d].
        attention_weight: Softmax attention weight α_k.

    Returns:
        Weighted contribution.
    """
    return attention_weight * value


fn gated_feedforward(
    x: Float64, gate: Float64
) -> Float64:
    """Gated FFN (SwiGLU): output = SiLU(gate) × x.

    SiLU(x) = x / (1 + exp(-x))

    Args:
        x: Value branch input.
        gate: Gate branch input.

    Returns:
        Gated FFN output element.
    """
    var silu_gate = gate / (1.0 + exp(-gate))
    return silu_gate * x


fn dropout_scale(x: Float64, keep_prob: Float64) -> Float64:
    """Inverted dropout scaling (training): x / keep_prob.

    At inference: return x unchanged (keep_prob = 1.0).

    Args:
        x: Activation value (assuming neuron is kept).
        keep_prob: Keep probability (1 - dropout_rate).

    Returns:
        Scaled activation.
    """
    if keep_prob <= 0.0:
        return 0.0
    return x / keep_prob
