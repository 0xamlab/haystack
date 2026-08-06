"""
flash_attention.mojo — Flash Attention / blockwise attention memory-efficient math.
Zero Python imports.

Public API:
  flash_block_max                — online softmax block max update
  flash_block_sum_exp            — online normalizer update
  flash_block_output             — block output accumulation
  flash_rescale_output           — rescale output after max update
  flash_final_normalize          — divide accumulated output by normalizer
  paged_attention_block_score    — paged KV block attention score
  sliding_window_attention       — local attention window mask
  sparse_attention_block_density — sparse attention block density
  grouped_query_attention_scale  — GQA key-value head reuse scale
  ring_attention_chunk_size      — ring attention chunk partition
"""
from std.math import sqrt, log, exp


def flash_block_max(
    current_max: Float64, new_score: Float64
) -> Float64:
    """Online softmax: update running row maximum with new block scores.

    m_new = max(m_old, max(new_block_scores))

    Args:
        current_max: Running maximum from previous blocks.
        new_score: New attention score from current block.

    Returns:
        Updated maximum.
    """
    if new_score > current_max:
        return new_score
    return current_max


def flash_block_sum_exp(
    current_sum: Float64, old_max: Float64,
    new_max: Float64, new_score: Float64
) -> Float64:
    """Online softmax: update running normalizer after max update.

    l_new = exp(m_old - m_new) × l_old + exp(score - m_new)

    Args:
        current_sum: Running sum l_old.
        old_max: Previous running maximum m_old.
        new_max: Updated maximum m_new.
        new_score: New attention score from current block.

    Returns:
        Updated normalizer l_new.
    """
    var rescale = exp(old_max - new_max)
    return current_sum * rescale + exp(new_score - new_max)


def flash_block_output(
    current_output: Float64, old_max: Float64, new_max: Float64,
    attention_weight: Float64, value: Float64
) -> Float64:
    """Block output accumulation with running max correction.

    o_new = exp(m_old - m_new) × o_old + exp(score - m_new) × v

    Args:
        current_output: Running output accumulator o_old.
        old_max: Previous maximum m_old.
        new_max: Updated maximum m_new.
        attention_weight: exp(score - m_new) for this KV pair.
        value: Value element v.

    Returns:
        Updated output accumulator.
    """
    var rescale = exp(old_max - new_max)
    return current_output * rescale + attention_weight * value


def flash_rescale_output(
    output: Float64, old_sum: Float64,
    old_max: Float64, new_max: Float64
) -> Float64:
    """Rescale accumulated output when running max updates.

    o = o × exp(m_old - m_new) / l_ratio

    Args:
        output: Current accumulated output.
        old_sum: Previous normalizer.
        old_max: Previous maximum.
        new_max: New maximum.

    Returns:
        Rescaled output.
    """
    if old_sum <= 0.0:
        return output
    return output * exp(old_max - new_max)


def flash_final_normalize(
    output: Float64, normalizer: Float64
) -> Float64:
    """Final normalisation: o_final = o_accumulated / l_total.

    Args:
        output: Fully accumulated output.
        normalizer: Final normalizer l (sum of all exp weights).

    Returns:
        Normalised attention output.
    """
    if normalizer <= 0.0:
        return 0.0
    return output / normalizer


def paged_attention_block_score(
    query_elem: Float64, key_elem: Float64,
    block_max_key: Float64, head_dim: Float64
) -> Float64:
    """Paged attention score for one KV block element.

    Uses block-max for per-block softmax stability.

    Args:
        query_elem: Query element.
        key_elem: Key element from paged block.
        block_max_key: Maximum key element in this block.
        head_dim: Head dimension for scaling.

    Returns:
        Scaled attention logit.
    """
    if head_dim <= 0.0:
        return 0.0
    return (query_elem * key_elem) / sqrt(head_dim)


def sliding_window_attention(
    query_pos: Float64, key_pos: Float64, window_size: Float64
) -> Float64:
    """Local sliding-window attention mask.

    Returns 0.0 (attend) or -1e9 (mask) based on window.

    Args:
        query_pos: Query token position.
        key_pos: Key token position.
        window_size: Maximum relative distance to attend to.

    Returns:
        0.0 if within window, -1e9 if outside.
    """
    var dist = query_pos - key_pos
    if dist < 0.0:
        dist = -dist
    if dist <= window_size and key_pos <= query_pos:
        return 0.0
    return -1e9


def sparse_attention_block_density(
    n_attended: Float64, block_size: Float64
) -> Float64:
    """Fraction of non-zero blocks in sparse attention pattern.

    density = n_attended / block_size²

    Args:
        n_attended: Number of attended positions in block.
        block_size: Block size (rows × cols).

    Returns:
        Block density (0 = fully sparse, 1 = dense).
    """
    var max_attended = block_size * block_size
    if max_attended <= 0.0:
        return 1.0
    return n_attended / max_attended


def grouped_query_attention_scale(
    n_query_heads: Float64, n_kv_heads: Float64
) -> Float64:
    """GQA key-value head reuse factor.

    Each KV head serves n_q/n_kv query heads.

    Args:
        n_query_heads: Total query heads.
        n_kv_heads: Total KV heads (< n_q for GQA; 1 for MQA).

    Returns:
        Query heads per KV head.
    """
    if n_kv_heads <= 0.0:
        return n_query_heads
    return n_query_heads / n_kv_heads


def ring_attention_chunk_size(
    seq_len: Float64, n_devices: Float64
) -> Float64:
    """Ring attention sequence chunk per device.

    chunk = seq_len / n_devices

    Args:
        seq_len: Total sequence length.
        n_devices: Number of devices in ring.

    Returns:
        Tokens processed per device per ring step.
    """
    if n_devices <= 0.0:
        return seq_len
    return seq_len / n_devices
