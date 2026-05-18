"""
sampling.mojo — Advanced quasi-random sampling. Zero Python imports.

Replaces scipy.stats.qmc with pure Mojo implementations for
Halton sequences, stratified sampling, Latin Hypercube Sampling,
low-discrepancy sequences, and discrepancy measures.

Public API:
  halton_sequence       — Halton (van der Corput) sequence in given base
  halton_2d             — 2D Halton points (bases 2, 3)
  stratified_sample_1d  — Stratified uniform sampling on [0,1]
  latin_hypercube_sample — Latin Hypercube Sampling in d dimensions
  sobol_like_2d         — Additive recurrence low-discrepancy 2D sequence
  discrepancy_l2_star   — L2-star discrepancy for 2D point sets
"""
from std.math import sqrt, abs as fabs
from std.random import random_float64


# ── halton_sequence ──────────────────────────────────────────────────────────


fn halton_sequence(n: Int, base: Int) -> List[Float64]:
    """Generate n values of the Halton (van der Corput) sequence in given base.

    Each value lies in (0, 1). The Halton sequence is a deterministic
    low-discrepancy sequence useful for quasi-Monte Carlo integration.

    Args:
        n:    Number of points to generate.
        base: Integer base (must be >= 2, typically a prime).

    Returns:
        List of n Float64 values in (0, 1).
    """
    var result = List[Float64]()
    for i in range(1, n + 1):
        var f: Float64 = 1.0
        var r: Float64 = 0.0
        var idx = i
        while idx > 0:
            f /= Float64(base)
            r += f * Float64(idx % base)
            idx //= base
        result.append(r)
    return result^


# ── halton_2d ────────────────────────────────────────────────────────────────


fn halton_2d(n: Int) -> List[List[Float64]]:
    """Generate n 2D Halton points using bases 2 and 3.

    Returns list of [x, y] pairs where each coordinate is in (0, 1).

    Args:
        n: Number of 2D points to generate.

    Returns:
        List of n [x, y] pairs.
    """
    var seq_x = halton_sequence(n, 2)
    var seq_y = halton_sequence(n, 3)
    var result = List[List[Float64]]()
    for i in range(n):
        var pt = List[Float64]()
        pt.append(seq_x[i])
        pt.append(seq_y[i])
        result.append(pt^)
    return result^


# ── stratified_sample_1d ─────────────────────────────────────────────────────


fn stratified_sample_1d(n_strata: Int) -> List[Float64]:
    """Divide [0,1] into n_strata equal bins, sample one uniform value from each.

    Ensures better coverage than pure random sampling by guaranteeing
    exactly one sample per stratum.

    Args:
        n_strata: Number of equal-width strata.

    Returns:
        List of n_strata Float64 values, one from each stratum.
    """
    var result = List[Float64]()
    var width = 1.0 / Float64(n_strata)
    for i in range(n_strata):
        var lo = Float64(i) * width
        var u = random_float64()
        result.append(lo + u * width)
    return result^


# ── latin_hypercube_sample ───────────────────────────────────────────────────


fn latin_hypercube_sample(n: Int, d: Int) -> List[List[Float64]]:
    """Generate n samples in d dimensions using Latin Hypercube Sampling.

    Each dimension is divided into n equal strata. In each dimension,
    exactly one sample falls in each stratum. This ensures good marginal
    coverage in all dimensions.

    Args:
        n: Number of samples.
        d: Number of dimensions.

    Returns:
        List of n points, each a List[Float64] of length d with values in [0,1].
    """
    # Build permutation per dimension using Fisher-Yates shuffle
    var result = List[List[Float64]]()
    for _ in range(n):
        var pt = List[Float64]()
        for _ in range(d):
            pt.append(0.0)
        result.append(pt^)

    var width = 1.0 / Float64(n)

    for dim in range(d):
        # Create identity permutation
        var perm = List[Int]()
        for i in range(n):
            perm.append(i)

        # Fisher-Yates shuffle
        for i in range(n - 1, 0, -1):
            var u = random_float64()
            var j = Int(u * Float64(i + 1))
            if j > i:
                j = i
            # Swap
            var tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp

        # Assign stratified samples using permutation
        for i in range(n):
            var stratum = perm[i]
            var lo = Float64(stratum) * width
            var u = random_float64()
            result[i][dim] = lo + u * width

    return result^


# ── sobol_like_2d ────────────────────────────────────────────────────────────


fn sobol_like_2d(n: Int) -> List[List[Float64]]:
    """Simple additive recurrence low-discrepancy sequence in 2D.

    Uses the golden ratio φ = (1+√5)/2 and its generalization for 2D:
      α₁ = 1/φ₂  where φ₂ is the plastic constant (≈ 1.3247)
      x_i = frac(0.5 + i * α₁)
      y_i = frac(0.5 + i * α₂)

    This produces a well-distributed point set in [0,1]².

    Args:
        n: Number of 2D points.

    Returns:
        List of n [x, y] pairs in [0, 1]².
    """
    # Use generalized golden ratio for d=2
    # φ₂ ≈ 1.32471795724... (plastic constant)
    var phi2: Float64 = 1.32471795724474602596
    var alpha1 = 1.0 / phi2
    var alpha2 = 1.0 / (phi2 * phi2)

    var result = List[List[Float64]]()
    for i in range(n):
        var x = 0.5 + Float64(i + 1) * alpha1
        var y = 0.5 + Float64(i + 1) * alpha2
        # frac: keep fractional part
        x = x - Float64(Int(x))
        y = y - Float64(Int(y))
        var pt = List[Float64]()
        pt.append(x)
        pt.append(y)
        result.append(pt^)
    return result^


# ── discrepancy_l2_star ──────────────────────────────────────────────────────


fn discrepancy_l2_star(points: List[List[Float64]]) -> Float64:
    """L2-star discrepancy for 2D point sets.

    Measures how uniformly distributed a set of 2D points is in [0,1]².
    Lower values indicate more uniform distributions.

    Uses the Warnock formula for 2D:
      D²_L2* = (1/3)^d - (2^(1-d)/n) Σ Π (1 - x²ᵢⱼ)
             + (1/n²) Σ Σ Π min(1-xᵢₖ, 1-xⱼₖ)

    For d=2:
      D² = 1/9 - (1/(2n)) Σᵢ (1-x²)(1-y²)
           + (1/n²) Σᵢ Σⱼ [min(1-xᵢ,1-xⱼ) * min(1-yᵢ,1-yⱼ)]

    But the standard L2-star uses a slightly different form. We implement
    the Hickernell (1998) closed-form for d=2.

    Args:
        points: List of [x, y] pairs in [0, 1]².

    Returns:
        L2-star discrepancy (non-negative Float64).
    """
    var n = len(points)
    if n == 0:
        return 0.0

    # Term 1: (1/3)^2 = 1/9
    var term1: Float64 = 1.0 / 9.0

    # Term 2: -(2/(2^2 * n)) * sum_i prod_k (1 - x_ik^2)
    #        = -(1/(2n)) * sum_i (1 - xi^2)(1 - yi^2)
    var sum2: Float64 = 0.0
    for i in range(n):
        var xi = points[i][0]
        var yi = points[i][1]
        sum2 += (1.0 - xi * xi) * (1.0 - yi * yi)
    var term2 = -sum2 / (2.0 * Float64(n))

    # Term 3: (1/n²) * sum_i sum_j prod_k (1 - max(x_ik, x_jk))
    var sum3: Float64 = 0.0
    for i in range(n):
        var xi = points[i][0]
        var yi = points[i][1]
        for j in range(n):
            var xj = points[j][0]
            var yj = points[j][1]
            var mx = xi if xi > xj else xj
            var my = yi if yi > yj else yj
            sum3 += (1.0 - mx) * (1.0 - my)
    var term3 = sum3 / (Float64(n) * Float64(n))

    var d2 = term1 + term2 + term3
    if d2 < 0.0:
        d2 = 0.0
    return sqrt(d2)
