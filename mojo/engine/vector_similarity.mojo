"""
vector_similarity.mojo — Vector distance and similarity for embeddings/search. Zero Python imports.

Public API:
  cosine_similarity             — cos(θ) between two vectors
  dot_product                   — unnormalised inner product
  euclidean_distance            — L2 distance
  manhattan_distance            — L1 distance
  chebyshev_distance            — L∞ distance
  hamming_distance_bits         — bit-level Hamming
  jaccard_similarity            — set overlap measure
  pearson_correlation           — linear correlation
  minkowski_distance            — generalised Lp norm
  angular_distance              — 1 - cos(θ)
"""
from std.math import sqrt, log, exp


fn cosine_similarity(
    dot: Float64, norm_a: Float64, norm_b: Float64
) -> Float64:
    """Cosine similarity: cos(θ) = a·b / (||a|| × ||b||).

    Args:
        dot: Dot product a·b.
        norm_a: L2 norm of vector a.
        norm_b: L2 norm of vector b.

    Returns:
        Cosine similarity (-1 to 1).
    """
    var denom = norm_a * norm_b
    if denom <= 0.0:
        return 0.0
    return dot / denom


fn dot_product(sum_products: Float64) -> Float64:
    """Unnormalised dot product (pass sum of element products).

    Args:
        sum_products: Pre-computed sum of a_i × b_i.

    Returns:
        Dot product value.
    """
    return sum_products


fn euclidean_distance(sum_sq_diff: Float64) -> Float64:
    """L2 (Euclidean) distance: sqrt(Σ(a_i - b_i)²).

    Args:
        sum_sq_diff: Pre-computed sum of squared differences.

    Returns:
        Euclidean distance.
    """
    if sum_sq_diff < 0.0:
        return 0.0
    return sqrt(sum_sq_diff)


fn manhattan_distance(sum_abs_diff: Float64) -> Float64:
    """L1 (Manhattan) distance: Σ|a_i - b_i|.

    Args:
        sum_abs_diff: Pre-computed sum of absolute differences.

    Returns:
        Manhattan distance.
    """
    return sum_abs_diff


fn chebyshev_distance(max_abs_diff: Float64) -> Float64:
    """L∞ (Chebyshev) distance: max|a_i - b_i|.

    Args:
        max_abs_diff: Maximum absolute difference across dimensions.

    Returns:
        Chebyshev distance.
    """
    return max_abs_diff


fn hamming_distance_bits(
    xor_popcount: Float64, n_bits: Float64
) -> Float64:
    """Normalised Hamming distance for binary vectors.

    d = popcount(a XOR b) / n_bits

    Args:
        xor_popcount: Number of differing bits.
        n_bits: Total number of bits.

    Returns:
        Normalised Hamming distance (0–1).
    """
    if n_bits <= 0.0:
        return 0.0
    return xor_popcount / n_bits


fn jaccard_similarity(
    intersection: Float64, union_size: Float64
) -> Float64:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|.

    Args:
        intersection: Size of set intersection.
        union_size: Size of set union.

    Returns:
        Jaccard similarity (0–1).
    """
    if union_size <= 0.0:
        return 0.0
    return intersection / union_size


fn pearson_correlation(
    n: Float64, sum_xy: Float64,
    sum_x: Float64, sum_y: Float64,
    sum_x2: Float64, sum_y2: Float64
) -> Float64:
    """Pearson correlation coefficient.

    r = (n Σxy - Σx Σy) / sqrt((n Σx² - (Σx)²)(n Σy² - (Σy)²))

    Args:
        n: Number of elements.
        sum_xy: Σ(x_i × y_i).
        sum_x: Σx_i.
        sum_y: Σy_i.
        sum_x2: Σx_i².
        sum_y2: Σy_i².

    Returns:
        Pearson r (-1 to 1).
    """
    var num = n * sum_xy - sum_x * sum_y
    var denom_sq = (n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)
    if denom_sq <= 0.0:
        return 0.0
    return num / sqrt(denom_sq)


fn minkowski_distance(
    sum_abs_p: Float64, p: Float64
) -> Float64:
    """Minkowski distance: (Σ|a_i - b_i|^p)^(1/p).

    Args:
        sum_abs_p: Pre-computed Σ|a_i - b_i|^p.
        p: Norm order (1=Manhattan, 2=Euclidean).

    Returns:
        Minkowski distance.
    """
    if p <= 0.0:
        return 0.0
    return exp(log(sum_abs_p + 1e-300) / p)


fn angular_distance(
    dot: Float64, norm_a: Float64, norm_b: Float64
) -> Float64:
    """Angular distance: 1 - cos(θ) (in [0, 2]).

    Args:
        dot: Dot product a·b.
        norm_a: L2 norm of a.
        norm_b: L2 norm of b.

    Returns:
        Angular distance (0 = identical direction, 2 = opposite).
    """
    return 1.0 - cosine_similarity(dot, norm_a, norm_b)
