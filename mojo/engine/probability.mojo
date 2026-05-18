"""
probability.mojo — Probability theory utilities. Zero Python imports.
Bayesian inference, conditional probability, combinatorics, distributions, information theory.

Public API:
  bayes              — P(A|B) via Bayes' theorem
  joint_probability  — P(A∩B) = P(B|A)*P(A)
  total_probability  — law of total probability
  factorial          — n!
  combinations       — n choose k
  permutations       — n perm k
  binomial_pmf       — P(X=k) for Binomial(n,p)
  poisson_pmf        — P(X=k) for Poisson(λ)
  entropy            — Shannon entropy (bits)
  kl_divergence      — KL divergence (bits)
  mutual_information — mutual information from joint distribution (bits)
"""
from std.math import abs as fabs, log, exp, pow


# ── Constants ─────────────────────────────────────────────────────────────────

comptime LN2: Float64 = 0.6931471805599453  # ln(2) for log2 conversion


# ── Bayes' Theorem ────────────────────────────────────────────────────────────


fn bayes(prior: Float64, likelihood: Float64, evidence: Float64) -> Float64:
    """Bayes' theorem: P(A|B) = P(B|A) * P(A) / P(B).

    Args:
        prior:      P(A) — prior probability.
        likelihood: P(B|A) — likelihood of evidence given hypothesis.
        evidence:   P(B) — total probability of evidence.

    Returns:
        P(A|B) — posterior probability. Returns 0.0 if evidence is zero.
    """
    if fabs(evidence) < 1e-15:
        return 0.0
    return likelihood * prior / evidence


# ── Joint Probability ─────────────────────────────────────────────────────────


fn joint_probability(p_a: Float64, p_b_given_a: Float64) -> Float64:
    """Joint probability: P(A∩B) = P(B|A) * P(A).

    Args:
        p_a:         P(A).
        p_b_given_a: P(B|A) — conditional probability.

    Returns:
        P(A∩B).
    """
    return p_a * p_b_given_a


# ── Law of Total Probability ─────────────────────────────────────────────────


fn total_probability(
    priors: List[Float64], likelihoods: List[Float64]
) -> Float64:
    """Law of total probability: P(B) = Σ P(B|Aᵢ) * P(Aᵢ).

    Args:
        priors:      List of P(Aᵢ) for each partition.
        likelihoods: List of P(B|Aᵢ) for each partition.

    Returns:
        P(B). Uses min(len(priors), len(likelihoods)) terms.
    """
    var n = len(priors)
    var m = len(likelihoods)
    var count = n if n < m else m
    var total: Float64 = 0.0
    for i in range(count):
        total += priors[i] * likelihoods[i]
    return total


# ── Factorial ─────────────────────────────────────────────────────────────────


fn factorial(n: Int) -> Float64:
    """Compute n! as Float64.

    Returns 1.0 for n <= 1. Uses iterative multiplication.
    """
    if n <= 1:
        return 1.0
    var result: Float64 = 1.0
    for i in range(2, n + 1):
        result *= Float64(i)
    return result


# ── Combinations ──────────────────────────────────────────────────────────────


fn combinations(n: Int, k: Int) -> Float64:
    """Binomial coefficient: C(n, k) = n! / (k! * (n-k)!).

    Uses multiplicative formula to avoid overflow for moderate n.
    Returns 0.0 if k < 0 or k > n.
    """
    if k < 0 or k > n:
        return 0.0
    if k == 0 or k == n:
        return 1.0
    # Use smaller k for efficiency: C(n,k) = C(n, n-k)
    var kk = k
    if kk > n - kk:
        kk = n - kk
    var result: Float64 = 1.0
    for i in range(kk):
        result = result * Float64(n - i) / Float64(i + 1)
    return result


# ── Permutations ──────────────────────────────────────────────────────────────


fn permutations(n: Int, k: Int) -> Float64:
    """Permutations: P(n, k) = n! / (n-k)!.

    Returns 0.0 if k < 0 or k > n.
    """
    if k < 0 or k > n:
        return 0.0
    if k == 0:
        return 1.0
    var result: Float64 = 1.0
    for i in range(k):
        result *= Float64(n - i)
    return result


# ── Binomial PMF ──────────────────────────────────────────────────────────────


fn binomial_pmf(k: Int, n: Int, p: Float64) -> Float64:
    """Binomial PMF: P(X=k) = C(n,k) * p^k * (1-p)^(n-k).

    Args:
        k: Number of successes.
        n: Number of trials.
        p: Probability of success per trial.

    Returns:
        P(X=k). Returns 0.0 if k < 0 or k > n.
    """
    if k < 0 or k > n:
        return 0.0
    var coeff = combinations(n, k)
    return coeff * pow(p, Float64(k)) * pow(1.0 - p, Float64(n - k))


# ── Poisson PMF ───────────────────────────────────────────────────────────────


fn poisson_pmf(k: Int, lam: Float64) -> Float64:
    """Poisson PMF: P(X=k) = λ^k * e^(-λ) / k!.

    Args:
        k:   Number of events.
        lam: λ — expected number of events.

    Returns:
        P(X=k). Returns 0.0 if k < 0.
    """
    if k < 0:
        return 0.0
    return pow(lam, Float64(k)) * exp(-lam) / factorial(k)


# ── Shannon Entropy ───────────────────────────────────────────────────────────


fn entropy(probs: List[Float64]) -> Float64:
    """Shannon entropy in bits: H = -Σ p * log2(p).

    Uses natural log internally, then divides by ln(2) for bits.
    Skips zero probabilities (convention: 0 log 0 = 0).

    Args:
        probs: List of probabilities (should sum to 1).

    Returns:
        Entropy in bits.
    """
    var h: Float64 = 0.0
    for i in range(len(probs)):
        var p = probs[i]
        if p > 1e-15:
            h -= p * log(p)
    return h / LN2


# ── KL Divergence ─────────────────────────────────────────────────────────────


fn kl_divergence(p: List[Float64], q: List[Float64]) -> Float64:
    """Kullback-Leibler divergence in bits: D_KL(P||Q) = Σ p * log2(p/q).

    Uses natural log internally, then divides by ln(2) for bits.
    Skips entries where p is zero. Returns inf-like large value if q is zero
    where p is nonzero (undefined KL).

    Args:
        p: True distribution.
        q: Approximate distribution.

    Returns:
        KL divergence in bits.
    """
    var n = len(p)
    var m = len(q)
    var count = n if n < m else m
    var kl: Float64 = 0.0
    for i in range(count):
        var pi = p[i]
        var qi = q[i]
        if pi > 1e-15:
            if qi < 1e-15:
                # KL is undefined/infinite when q=0 and p>0
                kl += 1e10
            else:
                kl += pi * log(pi / qi)
    return kl / LN2


# ── Mutual Information ────────────────────────────────────────────────────────


fn mutual_information(joint: List[List[Float64]]) -> Float64:
    """Mutual information from joint distribution in bits.

    I(X;Y) = Σᵢ Σⱼ p(x,y) * log2(p(x,y) / (p(x)*p(y)))

    Computes marginals from the joint distribution, then calculates MI.
    Skips entries where joint probability is zero.

    Args:
        joint: 2D joint probability table. joint[i][j] = P(X=i, Y=j).

    Returns:
        Mutual information in bits.
    """
    var rows = len(joint)
    if rows == 0:
        return 0.0
    var cols = len(joint[0])
    if cols == 0:
        return 0.0

    # Compute marginal P(X=i) = Σⱼ joint[i][j]
    var margin_x = List[Float64]()
    for i in range(rows):
        var s: Float64 = 0.0
        for j in range(len(joint[i])):
            s += joint[i][j]
        margin_x.append(s)

    # Compute marginal P(Y=j) = Σᵢ joint[i][j]
    var margin_y = List[Float64]()
    for j in range(cols):
        var s: Float64 = 0.0
        for i in range(rows):
            if j < len(joint[i]):
                s += joint[i][j]
        margin_y.append(s)

    # MI = Σ p(x,y) * log(p(x,y) / (p(x)*p(y)))
    var mi: Float64 = 0.0
    for i in range(rows):
        for j in range(len(joint[i])):
            var pxy = joint[i][j]
            if pxy > 1e-15:
                var px = margin_x[i]
                var py = margin_y[j]
                if px > 1e-15 and py > 1e-15:
                    mi += pxy * log(pxy / (px * py))

    return mi / LN2
