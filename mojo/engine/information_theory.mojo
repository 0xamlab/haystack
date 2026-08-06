"""
information_theory.mojo — Information theory measures. Zero Python imports.

Replaces scipy.stats entropy and ad-hoc information theory Python code with
pure Mojo implementations for Shannon entropy, joint/conditional entropy,
mutual information, KL divergence, cross entropy, binary entropy,
channel capacity, redundancy, and normalized entropy.

Public API:
  entropy              — Shannon entropy H(X)
  joint_entropy        — Joint entropy H(X,Y)
  conditional_entropy  — Conditional entropy H(Y|X)
  mutual_information   — Mutual information I(X;Y)
  kl_divergence        — Kullback-Leibler divergence
  cross_entropy        — Cross entropy H(p,q)
  binary_entropy       — Binary entropy H(p)
  channel_capacity_bsc — Binary symmetric channel capacity
  redundancy           — Redundancy R = log2(n) - H
  normalized_entropy   — Normalized entropy H/log2(n)
"""
from std.math import log2, log, abs as fabs


# ── entropy ───────────────────────────────────────────────────────────────────


def entropy(probs: List[Float64]) -> Float64:
    """Shannon entropy: -Σ p*log2(p). Skip p=0."""
    var h: Float64 = 0.0
    for i in range(len(probs)):
        var p = probs[i]
        if p > 0.0:
            h -= p * log2(p)
    return h


# ── joint_entropy ─────────────────────────────────────────────────────────────


def joint_entropy(joint_probs: List[List[Float64]]) -> Float64:
    """Joint entropy: -Σᵢⱼ p(i,j)*log2(p(i,j))."""
    var h: Float64 = 0.0
    for i in range(len(joint_probs)):
        for j in range(len(joint_probs[i])):
            var p = joint_probs[i][j]
            if p > 0.0:
                h -= p * log2(p)
    return h


# ── conditional_entropy ───────────────────────────────────────────────────────


def conditional_entropy(joint_probs: List[List[Float64]]) -> Float64:
    """Conditional entropy H(Y|X) = H(X,Y) - H(X).

    X marginal is obtained by summing rows of the joint distribution.
    """
    var hxy = joint_entropy(joint_probs)
    # Compute marginal of X (row sums)
    var marginal_x = List[Float64]()
    for i in range(len(joint_probs)):
        var s: Float64 = 0.0
        for j in range(len(joint_probs[i])):
            s += joint_probs[i][j]
        marginal_x.append(s)
    var hx = entropy(marginal_x)
    return hxy - hx


# ── mutual_information ────────────────────────────────────────────────────────


def mutual_information(joint_probs: List[List[Float64]]) -> Float64:
    """Mutual information I(X;Y) = H(X) + H(Y) - H(X,Y)."""
    var hxy = joint_entropy(joint_probs)
    # Marginal X (row sums)
    var marginal_x = List[Float64]()
    for i in range(len(joint_probs)):
        var s: Float64 = 0.0
        for j in range(len(joint_probs[i])):
            s += joint_probs[i][j]
        marginal_x.append(s)
    # Marginal Y (column sums)
    var n_cols = 0
    if len(joint_probs) > 0:
        n_cols = len(joint_probs[0])
    # A row shorter than the first would be read past its end in the
    # column sums below (uncatchable abort).
    for i in range(len(joint_probs)):
        if len(joint_probs[i]) < n_cols:
            return 0.0
    var marginal_y = List[Float64]()
    for j in range(n_cols):
        var s: Float64 = 0.0
        for i in range(len(joint_probs)):
            s += joint_probs[i][j]
        marginal_y.append(s)
    var hx = entropy(marginal_x)
    var hy = entropy(marginal_y)
    return hx + hy - hxy


# ── kl_divergence ─────────────────────────────────────────────────────────────


def kl_divergence(p: List[Float64], q: List[Float64]) -> Float64:
    """KL divergence: Σ p*log2(p/q). Requires q[i]>0 where p[i]>0."""
    # A short q would be read past its end below (uncatchable abort).
    if len(q) < len(p):
        return 0.0
    var kl: Float64 = 0.0
    for i in range(len(p)):
        if p[i] > 0.0 and q[i] > 0.0:
            kl += p[i] * log2(p[i] / q[i])
    return kl


# ── cross_entropy ─────────────────────────────────────────────────────────────


def cross_entropy(p: List[Float64], q: List[Float64]) -> Float64:
    """Cross entropy: -Σ p*log2(q)."""
    # A short q would be read past its end below (uncatchable abort).
    if len(q) < len(p):
        return 0.0
    var ce: Float64 = 0.0
    for i in range(len(p)):
        if p[i] > 0.0 and q[i] > 0.0:
            ce -= p[i] * log2(q[i])
    return ce


# ── binary_entropy ────────────────────────────────────────────────────────────


def binary_entropy(p: Float64) -> Float64:
    """Binary entropy: H(p) = -p*log2(p) - (1-p)*log2(1-p)."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * log2(p) - (1.0 - p) * log2(1.0 - p)


# ── channel_capacity_bsc ─────────────────────────────────────────────────────


def channel_capacity_bsc(error_prob: Float64) -> Float64:
    """Binary symmetric channel capacity: C = 1 - H(p)."""
    return 1.0 - binary_entropy(error_prob)


# ── redundancy ────────────────────────────────────────────────────────────────


def redundancy(probs: List[Float64]) -> Float64:
    """Redundancy: R = log2(n) - H(probs). Max possible entropy minus actual."""
    var n = len(probs)
    if n <= 1:
        return 0.0
    return log2(Float64(n)) - entropy(probs)


# ── normalized_entropy ────────────────────────────────────────────────────────


def normalized_entropy(probs: List[Float64]) -> Float64:
    """Normalized entropy: H(probs) / log2(n). Range [0,1]."""
    var n = len(probs)
    if n <= 1:
        return 0.0
    var max_h = log2(Float64(n))
    if max_h <= 0.0:
        return 0.0
    return entropy(probs) / max_h
