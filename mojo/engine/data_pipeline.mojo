"""
data_pipeline.mojo — Training data pipeline: packing, dedup, curriculum, mixing.
Zero Python imports.

Public API:
  sequence_packing_efficiency    — packing efficiency for variable-length seqs
  deduplication_minhash_band     — MinHash band similarity
  curriculum_difficulty_score    — sample difficulty for curriculum learning
  dataset_mixing_weight          — domain mixing weight (doremi/chi-squared)
  token_accounting_cost          — compute token budget from dataset
  quality_filter_score           — heuristic quality score for sample
  shard_balance_score            — how balanced dataset shards are
  streaming_buffer_fullness      — streaming dataloader buffer ratio
  epoch_sample_index             — sample index with shuffling
  data_augmentation_weight       — augmented sample loss weight
"""
from std.math import sqrt, log, exp


def sequence_packing_efficiency(
    total_tokens: Float64, padded_tokens: Float64
) -> Float64:
    """Sequence packing efficiency: useful tokens / padded total.

    Args:
        total_tokens: Real tokens across all sequences.
        padded_tokens: Total tokens including padding.

    Returns:
        Packing efficiency (1.0 = no padding waste).
    """
    if padded_tokens <= 0.0:
        return 1.0
    return total_tokens / padded_tokens


def deduplication_minhash_band(
    signature_a: Float64, signature_b: Float64
) -> Float64:
    """MinHash LSH band similarity check.

    Returns 1.0 if signatures match in this band (candidate dup).

    Args:
        signature_a: MinHash signature element for doc A.
        signature_b: MinHash signature element for doc B.

    Returns:
        1.0 if match (candidate duplicate), 0.0 otherwise.
    """
    if signature_a == signature_b:
        return 1.0
    return 0.0


def curriculum_difficulty_score(
    perplexity: Float64, seq_len: Float64,
    vocab_diversity: Float64
) -> Float64:
    """Curriculum learning difficulty: harder samples have higher scores.

    score = perplexity × log(seq_len) / vocab_diversity

    Args:
        perplexity: Model perplexity on this sample.
        seq_len: Sequence length (longer = harder).
        vocab_diversity: Unique token ratio (lower = repetitive = easier).

    Returns:
        Difficulty score (higher = harder).
    """
    if vocab_diversity <= 0.0:
        return perplexity
    return perplexity * log(seq_len + 1.0) / vocab_diversity


def dataset_mixing_weight(
    domain_loss: Float64, reference_loss: Float64,
    temperature: Float64
) -> Float64:
    """DoRA/DoReMi domain mixing weight via exponential reweighting.

    w_i ∝ exp((L_i - L_ref_i) / T)

    Args:
        domain_loss: Current loss on this domain.
        reference_loss: Reference model loss on this domain.
        temperature: Mixing temperature.

    Returns:
        Unnormalised mixing weight (normalise across domains).
    """
    if temperature <= 0.0:
        return 1.0 if domain_loss > reference_loss else 0.0
    return exp((domain_loss - reference_loss) / temperature)


def token_accounting_cost(
    n_documents: Float64, avg_doc_tokens: Float64,
    epochs: Float64
) -> Float64:
    """Total training token count from dataset config.

    tokens = n_docs × avg_tokens × epochs

    Args:
        n_documents: Number of documents in dataset.
        avg_doc_tokens: Average tokens per document.
        epochs: Training epochs over dataset.

    Returns:
        Total training tokens.
    """
    return n_documents * avg_doc_tokens * epochs


def quality_filter_score(
    perplexity: Float64, perplexity_threshold: Float64,
    repetition_ratio: Float64, length_score: Float64
) -> Float64:
    """Heuristic quality score: high = keep, low = filter.

    Args:
        perplexity: Language model perplexity (lower = more natural).
        perplexity_threshold: Maximum acceptable perplexity.
        repetition_ratio: Fraction of repeated n-grams (lower = better).
        length_score: Length acceptability (0–1).

    Returns:
        Quality score (0–1; filter if < 0.5).
    """
    var ppl_score = 1.0 - perplexity / perplexity_threshold
    if ppl_score < 0.0:
        ppl_score = 0.0
    if ppl_score > 1.0:
        ppl_score = 1.0
    var rep_score = 1.0 - repetition_ratio
    return 0.4 * ppl_score + 0.3 * rep_score + 0.3 * length_score


def shard_balance_score(
    shard_tokens: Float64, target_tokens_per_shard: Float64
) -> Float64:
    """How balanced this shard is relative to the target.

    score = 1 - |shard - target| / target  (1 = perfectly balanced)

    Args:
        shard_tokens: Tokens in this shard.
        target_tokens_per_shard: Ideal tokens per shard.

    Returns:
        Balance score (0–1).
    """
    if target_tokens_per_shard <= 0.0:
        return 1.0
    var deviation = shard_tokens - target_tokens_per_shard
    if deviation < 0.0:
        deviation = -deviation
    var score = 1.0 - deviation / target_tokens_per_shard
    if score < 0.0:
        return 0.0
    return score


def streaming_buffer_fullness(
    buffered_tokens: Float64, buffer_capacity: Float64
) -> Float64:
    """Streaming dataloader buffer fullness ratio.

    Args:
        buffered_tokens: Tokens currently buffered.
        buffer_capacity: Maximum buffer capacity.

    Returns:
        Buffer fullness (0–1; < 0.2 = starvation risk).
    """
    if buffer_capacity <= 0.0:
        return 1.0
    var ratio = buffered_tokens / buffer_capacity
    if ratio > 1.0:
        return 1.0
    return ratio


def epoch_sample_index(
    sample_id: Float64, epoch: Float64, n_samples: Float64, seed: Float64
) -> Float64:
    """Deterministic shuffled sample index within epoch.

    index = (sample_id + epoch × seed) % n_samples

    Args:
        sample_id: Original sample index.
        epoch: Current epoch.
        n_samples: Total samples.
        seed: Random seed.

    Returns:
        Shuffled sample index for this epoch.
    """
    if n_samples <= 0.0:
        return 0.0
    return Float64(Int64(sample_id + epoch * seed) % Int64(n_samples))


def data_augmentation_weight(
    is_augmented: Float64, augmentation_factor: Float64
) -> Float64:
    """Loss weight for augmented samples (down-weight if augmented).

    Args:
        is_augmented: 1.0 if this sample was augmented.
        augmentation_factor: Weight multiplier for augmented samples (< 1).

    Returns:
        Loss weight for this sample.
    """
    if is_augmented > 0.5:
        return augmentation_factor
    return 1.0
