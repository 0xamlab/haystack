"""
bpe_tokenizer.mojo — BPE / SentencePiece tokenization math primitives.
Zero Python imports.

Public API:
  bpe_merge_score                — BPE merge candidate score (frequency)
  bpe_pair_frequency             — bigram frequency estimate
  subword_log_probability        — subword unigram log-probability
  sentencepiece_vocab_size_est   — estimated vocab coverage at size V
  byte_fallback_encode           — byte fallback token count
  tokenization_compression_ratio — text → token compression ratio
  vocab_fertility                — tokens per word (fertility metric)
  oov_rate                       — out-of-vocabulary rate estimate
  bpe_merge_rank_score           — priority queue score for merge
  streaming_token_boundary       — streaming tokenizer boundary detection
"""
from std.math import sqrt, log, exp


def bpe_merge_score(
    pair_frequency: Float64, vocab_frequency_a: Float64, vocab_frequency_b: Float64
) -> Float64:
    """BPE merge candidate score: pair_freq / (freq_a × freq_b).

    Higher score → merge pair (a, b) earlier.

    Args:
        pair_frequency: Frequency of adjacent pair (a, b) in corpus.
        vocab_frequency_a: Total frequency of token a.
        vocab_frequency_b: Total frequency of token b.

    Returns:
        BPE merge score.
    """
    var denom = vocab_frequency_a * vocab_frequency_b
    if denom <= 0.0:
        return 0.0
    return pair_frequency / denom


def bpe_pair_frequency(
    joint_count: Float64, total_pairs: Float64
) -> Float64:
    """Normalised bigram frequency for BPE pair selection.

    Args:
        joint_count: Number of co-occurrences of pair (a, b).
        total_pairs: Total adjacent token pairs in corpus.

    Returns:
        Normalised bigram frequency.
    """
    if total_pairs <= 0.0:
        return 0.0
    return joint_count / total_pairs


def subword_log_probability(
    token_count: Float64, total_tokens: Float64
) -> Float64:
    """Unigram language model log-probability for a subword.

    log P(token) = log(count / total)

    Args:
        token_count: Frequency of this subword in training corpus.
        total_tokens: Total subword token count.

    Returns:
        Log probability (≤ 0).
    """
    if token_count <= 0.0 or total_tokens <= 0.0:
        return -1e300
    return log(token_count / total_tokens)


def sentencepiece_vocab_size_est(
    char_coverage: Float64, corpus_chars: Float64, target_coverage: Float64
) -> Float64:
    """Estimated vocab size to achieve target character coverage.

    Approximation: V ≈ corpus_chars × (1 - coverage) / (1 - target)

    Args:
        char_coverage: Current character coverage at base vocab.
        corpus_chars: Unique characters in corpus.
        target_coverage: Target coverage (0.9999 typical).

    Returns:
        Estimated required vocab size.
    """
    if char_coverage >= target_coverage:
        return corpus_chars
    var ratio = (1.0 - target_coverage) / (1.0 - char_coverage + 1e-10)
    return corpus_chars / ratio


def byte_fallback_encode(
    text_bytes: Float64
) -> Float64:
    """Number of byte-fallback tokens for raw bytes (3 per byte in some SPM).

    Args:
        text_bytes: Number of bytes in the text span.

    Returns:
        Token count using byte-fallback encoding.
    """
    return text_bytes


def tokenization_compression_ratio(
    n_chars: Float64, n_tokens: Float64
) -> Float64:
    """Text compression ratio: characters per token.

    Higher ratio → more compression (better tokenizer efficiency).

    Args:
        n_chars: Number of characters in text.
        n_tokens: Number of tokens produced.

    Returns:
        Characters per token (GPT-4 ≈ 4).
    """
    if n_tokens <= 0.0:
        return 0.0
    return n_chars / n_tokens


def vocab_fertility(n_tokens: Float64, n_words: Float64) -> Float64:
    """Tokenizer fertility: average tokens per word.

    Args:
        n_tokens: Total tokens in corpus.
        n_words: Total words (whitespace-split) in corpus.

    Returns:
        Fertility (1.0 = words == tokens, higher = more subword splits).
    """
    if n_words <= 0.0:
        return 1.0
    return n_tokens / n_words


def oov_rate(oov_tokens: Float64, total_tokens: Float64) -> Float64:
    """Out-of-vocabulary rate (fraction of UNK tokens).

    Args:
        oov_tokens: Tokens mapped to UNK.
        total_tokens: Total tokens.

    Returns:
        OOV rate (0–1; lower = better vocabulary coverage).
    """
    if total_tokens <= 0.0:
        return 0.0
    return oov_tokens / total_tokens


def bpe_merge_rank_score(
    frequency: Float64, rank: Float64
) -> Float64:
    """Priority score for BPE merge queue: frequency / (rank + 1).

    Args:
        frequency: Pair frequency in current iteration.
        rank: Current merge rank (lower = earlier merge).

    Returns:
        Priority score (higher = merge first).
    """
    return frequency / (rank + 1.0)


def streaming_token_boundary(
    char_code: Float64, prev_char_code: Float64
) -> Float64:
    """Detect likely token boundary in streaming context.

    Simplified: boundary at whitespace (ASCII 32) or punctuation.

    Args:
        char_code: Unicode code point of current character.
        prev_char_code: Previous character code.

    Returns:
        1.0 if likely boundary, 0.0 otherwise.
    """
    # Whitespace: ASCII 9 (tab), 10 (newline), 32 (space)
    if char_code == 32.0 or char_code == 10.0 or char_code == 9.0:
        return 1.0
    # Punctuation range (simplified: 33-47, 58-64, 91-96, 123-126)
    if char_code >= 33.0 and char_code <= 47.0:
        return 1.0
    return 0.0
