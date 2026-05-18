"""
cryptanalysis.mojo — Cryptanalysis Utilities Library. Zero Python imports.

Provides functions for classical cryptanalysis including frequency analysis,
index of coincidence, Friedman key-length estimation, Kasiski examination,
Hamming distance, Shannon entropy, and brute-force time estimation.

Public API:
  frequency_score_2       — Chi-squared for 2-bin distribution
  index_of_coincidence_2  — IC for 2-letter counts
  expected_ic_random      — Expected IC for random text = 1/alphabet_size
  expected_ic_english     — Expected IC for English ≈ 0.0667
  friedman_key_length     — Estimate key length from IC
  kasiski_distance_gcd    — GCD of two distances (Kasiski examination)
  caesar_decrypt_score    — Score a Caesar shift
  hamming_distance_bytes  — Bit-level Hamming distance between two bytes
  entropy_bits_2          — Shannon entropy for 2-symbol distribution
  entropy_bits_4          — Shannon entropy for 4-symbol distribution
  brute_force_time_estimate — Estimated seconds to brute-force
  avalanche_effect        — Ratio of changed bits
"""

from std.math import log as _log


# ── helpers ──────────────────────────────────────────────────────────────────


fn _log2(x: Float64) -> Float64:
    """Log base 2."""
    return _log(x) / _log(2.0)


fn _gcd(a_in: Int, b_in: Int) -> Int:
    """Euclidean GCD."""
    var a = a_in
    var b = b_in
    if a < 0:
        a = -a
    if b < 0:
        b = -b
    while b != 0:
        var t = b
        b = a % b
        a = t
    return a


fn _entropy_term(p: Float64) -> Float64:
    """Single term of Shannon entropy: -p*log2(p) if p>0, else 0."""
    if p > 0.0:
        return -p * _log2(p)
    return 0.0


# ── frequency_score_2 ────────────────────────────────────────────────────────


fn frequency_score_2(
    c0: Int, c1: Int, ef0: Float64, ef1: Float64
) -> Float64:
    """Chi-squared score for 2-bin letter frequency analysis.

    chi2 = sum( (observed - expected)^2 / expected )
    where expected_i = ef_i * total.
    """
    var total = Float64(c0 + c1)
    var e0 = ef0 * total
    var e1 = ef1 * total
    var score: Float64 = 0.0
    if e0 > 0.0:
        var d0 = Float64(c0) - e0
        score += (d0 * d0) / e0
    if e1 > 0.0:
        var d1 = Float64(c1) - e1
        score += (d1 * d1) / e1
    return score


# ── index_of_coincidence_2 ───────────────────────────────────────────────────


fn index_of_coincidence_2(c0: Int, c1: Int, total: Int) -> Float64:
    """IC = sum(ni*(ni-1)) / (N*(N-1)) for 2 letter counts."""
    if total <= 1:
        return 0.0
    var numerator = c0 * (c0 - 1) + c1 * (c1 - 1)
    return Float64(numerator) / Float64(total * (total - 1))


# ── expected_ic_random ───────────────────────────────────────────────────────


fn expected_ic_random(alphabet_size: Int) -> Float64:
    """Expected IC for random text = 1/alphabet_size."""
    if alphabet_size <= 0:
        return 0.0
    return 1.0 / Float64(alphabet_size)


# ── expected_ic_english ──────────────────────────────────────────────────────


fn expected_ic_english() -> Float64:
    """Expected IC for English ≈ 0.0667."""
    return 0.0667


# ── friedman_key_length ──────────────────────────────────────────────────────


fn friedman_key_length(ic: Float64, alphabet_size: Int) -> Float64:
    """Estimate key length from observed IC using Friedman's formula.

    k ≈ (kp - kr) / (ic - kr)
    where kp = expected IC for English ≈ 0.0667
          kr = 1/c (random IC)
    """
    var kp: Float64 = 0.0667
    var kr: Float64 = 1.0 / Float64(alphabet_size)
    var denom = ic - kr
    if denom <= 0.0:
        return 1.0
    return (kp - kr) / denom


# ── kasiski_distance_gcd ─────────────────────────────────────────────────────


fn kasiski_distance_gcd(d1: Int, d2: Int) -> Int:
    """GCD of two distances (for Kasiski examination)."""
    return _gcd(d1, d2)


# ── caesar_decrypt_score ─────────────────────────────────────────────────────


fn caesar_decrypt_score(
    shift: Int, expected_e_freq: Float64, actual_freq_at_e: Float64
) -> Float64:
    """Score a Caesar shift by how well the frequency matches expected 'e'.

    Returns the absolute difference (lower = better).
    """
    var diff = actual_freq_at_e - expected_e_freq
    if diff < 0.0:
        diff = -diff
    return diff


# ── hamming_distance_bytes ───────────────────────────────────────────────────


fn hamming_distance_bytes(a: Int, b: Int) -> Int:
    """Bit-level Hamming distance between two byte values (0-255)."""
    var xor_val = a ^ b
    var count: Int = 0
    var v = xor_val
    while v != 0:
        count += v & 1
        v = v >> 1
    return count


# ── entropy_bits_2 ───────────────────────────────────────────────────────────


fn entropy_bits_2(p0: Float64, p1: Float64) -> Float64:
    """Shannon entropy in bits for 2-symbol distribution."""
    return _entropy_term(p0) + _entropy_term(p1)


# ── entropy_bits_4 ───────────────────────────────────────────────────────────


fn entropy_bits_4(p0: Float64, p1: Float64, p2: Float64, p3: Float64) -> Float64:
    """Shannon entropy in bits for 4-symbol distribution."""
    return _entropy_term(p0) + _entropy_term(p1) + _entropy_term(p2) + _entropy_term(p3)


# ── brute_force_time_estimate ────────────────────────────────────────────────


fn brute_force_time_estimate(key_bits: Int, ops_per_second: Float64) -> Float64:
    """Estimated seconds to brute-force = 2^key_bits / ops_per_second.

    Uses loop-based power of 2 for Float64 precision.
    """
    if ops_per_second <= 0.0:
        return 0.0
    var keyspace: Float64 = 1.0
    for _ in range(key_bits):
        keyspace *= 2.0
    return keyspace / ops_per_second


# ── avalanche_effect ─────────────────────────────────────────────────────────


fn avalanche_effect(changed_bits: Int, total_bits: Int) -> Float64:
    """Ratio of changed bits (ideal ≈ 0.5 for good cipher)."""
    if total_bits <= 0:
        return 0.0
    return Float64(changed_bits) / Float64(total_bits)
