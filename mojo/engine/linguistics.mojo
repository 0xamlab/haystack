"""
linguistics.mojo — Computational Linguistics Library. Zero Python imports.

Pure Mojo implementations of text statistics, readability indices, and
lexical diversity measures used in corpus linguistics and NLP.

Public API:
  type_token_ratio            — TTR = types / tokens
  hapax_legomena_ratio        — hapax / N
  yules_k                     — Yule's K vocabulary richness
  heaps_law                   — V = K * N^β (vocabulary growth)
  zipfs_frequency             — f(r) = f_max / r^s
  flesch_reading_ease         — Flesch reading ease score
  flesch_kincaid_grade        — Flesch-Kincaid grade level
  gunning_fog_index           — Gunning fog index
  automated_readability_index — ARI
  coleman_liau_index          — Coleman-Liau index
  lexical_density             — LD = content_words / total_words
  mean_word_length            — MWL = chars / words
"""
from std.math import sqrt, abs as fabs, exp, log, pow


# ── type_token_ratio ──────────────────────────────────────────────────────────


fn type_token_ratio(n_types: Float64, n_tokens: Float64) -> Float64:
    """TTR = types / tokens."""
    return n_types / n_tokens


# ── hapax_legomena_ratio ──────────────────────────────────────────────────────


fn hapax_legomena_ratio(hapax_count: Float64, n_tokens: Float64) -> Float64:
    """Hapax legomena ratio = hapax / N."""
    return hapax_count / n_tokens


# ── yules_k ───────────────────────────────────────────────────────────────────


fn yules_k(n_tokens: Float64, freq_spectrum_sum: Float64) -> Float64:
    """Yule's K = 10000 * (M2 - N) / N².

    freq_spectrum_sum = Σ(i² * f_i), i.e. sum of (frequency² × count).
    """
    return 10000.0 * (freq_spectrum_sum - n_tokens) / (n_tokens * n_tokens)


# ── heaps_law ─────────────────────────────────────────────────────────────────


fn heaps_law(k: Float64, beta: Float64, n_tokens: Float64) -> Float64:
    """Heaps' law: V = K * N^β (expected vocabulary size)."""
    return k * exp(beta * log(n_tokens))


# ── zipfs_frequency ───────────────────────────────────────────────────────────


fn zipfs_frequency(
    rank: Float64, max_freq: Float64, s: Float64
) -> Float64:
    """Zipf's frequency: f(r) = f_max / r^s."""
    return max_freq / exp(s * log(rank))


# ── flesch_reading_ease ───────────────────────────────────────────────────────


fn flesch_reading_ease(
    total_words: Float64,
    total_sentences: Float64,
    total_syllables: Float64,
) -> Float64:
    """Flesch reading ease = 206.835 - 1.015*(w/s) - 84.6*(syl/w)."""
    var asl = total_words / total_sentences
    var asw = total_syllables / total_words
    return 206.835 - 1.015 * asl - 84.6 * asw


# ── flesch_kincaid_grade ──────────────────────────────────────────────────────


fn flesch_kincaid_grade(
    total_words: Float64,
    total_sentences: Float64,
    total_syllables: Float64,
) -> Float64:
    """Flesch-Kincaid grade = 0.39*(w/s) + 11.8*(syl/w) - 15.59."""
    var asl = total_words / total_sentences
    var asw = total_syllables / total_words
    return 0.39 * asl + 11.8 * asw - 15.59


# ── gunning_fog_index ─────────────────────────────────────────────────────────


fn gunning_fog_index(
    total_words: Float64,
    total_sentences: Float64,
    complex_words: Float64,
) -> Float64:
    """Gunning fog = 0.4 * ((w/s) + 100*(cw/w))."""
    var asl = total_words / total_sentences
    var pct_complex = 100.0 * complex_words / total_words
    return 0.4 * (asl + pct_complex)


# ── automated_readability_index ───────────────────────────────────────────────


fn automated_readability_index(
    total_chars: Float64,
    total_words: Float64,
    total_sentences: Float64,
) -> Float64:
    """ARI = 4.71*(c/w) + 0.5*(w/s) - 21.43."""
    return 4.71 * (total_chars / total_words) + 0.5 * (total_words / total_sentences) - 21.43


# ── coleman_liau_index ────────────────────────────────────────────────────────


fn coleman_liau_index(
    avg_letters_per_100w: Float64, avg_sentences_per_100w: Float64
) -> Float64:
    """Coleman-Liau = 0.0588*L - 0.296*S - 15.8."""
    return 0.0588 * avg_letters_per_100w - 0.296 * avg_sentences_per_100w - 15.8


# ── lexical_density ───────────────────────────────────────────────────────────


fn lexical_density(content_words: Float64, total_words: Float64) -> Float64:
    """LD = content_words / total_words."""
    return content_words / total_words


# ── mean_word_length ──────────────────────────────────────────────────────────


fn mean_word_length(total_chars: Float64, total_words: Float64) -> Float64:
    """MWL = total_chars / total_words."""
    return total_chars / total_words
