"""
contrastive_learning.mojo — Contrastive / self-supervised learning losses.
Zero Python imports.

Public API:
  infonce_loss                   — InfoNCE / NT-Xent numerator
  simclr_positive_score          — SimCLR positive pair score
  simclr_temperature_scale       — temperature-scaled similarity
  triplet_margin_loss            — triplet margin loss value
  nt_xent_denominator_term       — one term in NT-Xent denominator
  moco_momentum_update           — MoCo momentum encoder EMA
  byol_ema_update                — BYOL / DINO online→target update
  vicreg_variance_loss           — VICReg variance regularisation
  vicreg_covariance_term         — VICReg covariance regularisation term
  barlow_twins_cross_corr        — Barlow Twins cross-correlation term
"""
from std.math import sqrt, log, exp


def infonce_loss(positive_score: Float64, sum_exp_scores: Float64) -> Float64:
    """InfoNCE loss numerator contribution (negative log-softmax).

    L = -log(exp(pos) / Σ exp(scores))

    Args:
        positive_score: Similarity score for positive pair.
        sum_exp_scores: Sum of exp(similarity) over all pairs.

    Returns:
        InfoNCE loss value.
    """
    if sum_exp_scores <= 0.0:
        return 0.0
    return -positive_score + log(sum_exp_scores)


def simclr_positive_score(
    dot: Float64, norm_a: Float64, norm_b: Float64, temperature: Float64
) -> Float64:
    """SimCLR positive pair cosine similarity scaled by temperature.

    score = cos(a, b) / τ

    Args:
        dot: Dot product of embeddings.
        norm_a: L2 norm of first embedding.
        norm_b: L2 norm of second embedding.
        temperature: Temperature τ (0.07 typical).

    Returns:
        Temperature-scaled similarity.
    """
    var denom = norm_a * norm_b
    if denom <= 0.0 or temperature <= 0.0:
        return 0.0
    return dot / denom / temperature


def simclr_temperature_scale(similarity: Float64, temperature: Float64) -> Float64:
    """Scale a pre-computed similarity by temperature.

    Args:
        similarity: Cosine similarity value.
        temperature: Temperature τ.

    Returns:
        Scaled similarity.
    """
    if temperature <= 0.0:
        return similarity
    return similarity / temperature


def triplet_margin_loss(
    anchor_pos_dist: Float64, anchor_neg_dist: Float64, margin: Float64
) -> Float64:
    """Triplet margin loss: max(0, d(a,p) - d(a,n) + margin).

    Args:
        anchor_pos_dist: Distance between anchor and positive.
        anchor_neg_dist: Distance between anchor and negative.
        margin: Margin α (1.0 typical).

    Returns:
        Triplet loss (≥ 0).
    """
    var loss = anchor_pos_dist - anchor_neg_dist + margin
    if loss < 0.0:
        return 0.0
    return loss


def nt_xent_denominator_term(
    similarity: Float64, temperature: Float64
) -> Float64:
    """One term in the NT-Xent denominator: exp(sim/τ).

    Args:
        similarity: Pairwise cosine similarity.
        temperature: Temperature τ.

    Returns:
        exp(similarity / temperature).
    """
    if temperature <= 0.0:
        return 1.0
    return exp(similarity / temperature)


def moco_momentum_update(
    target_param: Float64, online_param: Float64, momentum: Float64
) -> Float64:
    """MoCo momentum encoder EMA update.

    θ_k = m × θ_k + (1-m) × θ_q

    Args:
        target_param: Target/key encoder parameter.
        online_param: Online/query encoder parameter.
        momentum: EMA momentum (0.999 typical).

    Returns:
        Updated target parameter.
    """
    return momentum * target_param + (1.0 - momentum) * online_param


def byol_ema_update(
    target_param: Float64, online_param: Float64, tau: Float64
) -> Float64:
    """BYOL / DINO target network EMA update.

    θ_t = τ × θ_t + (1-τ) × θ_o

    Args:
        target_param: Target network parameter.
        online_param: Online network parameter.
        tau: EMA decay (0.996 typical).

    Returns:
        Updated target parameter.
    """
    return tau * target_param + (1.0 - tau) * online_param


def vicreg_variance_loss(variance: Float64, gamma: Float64) -> Float64:
    """VICReg variance regularisation: max(0, γ - std(z)).

    Args:
        variance: Batch variance of embedding dimension.
        gamma: Target variance threshold (1.0 typical).

    Returns:
        Variance loss term.
    """
    var std = sqrt(variance + 1e-4)
    var loss = gamma - std
    if loss < 0.0:
        return 0.0
    return loss


def vicreg_covariance_term(
    cov_ij: Float64, variance_i: Float64, variance_j: Float64
) -> Float64:
    """VICReg covariance regularisation: (cov[i,j]/(std_i×std_j))² for i≠j.

    Args:
        cov_ij: Off-diagonal covariance element.
        variance_i: Variance of dimension i.
        variance_j: Variance of dimension j.

    Returns:
        Squared normalised off-diagonal covariance.
    """
    var std_i = sqrt(variance_i + 1e-4)
    var std_j = sqrt(variance_j + 1e-4)
    var corr = cov_ij / (std_i * std_j)
    return corr * corr


def barlow_twins_cross_corr(
    z_a_i: Float64, z_b_i: Float64, n: Float64,
    mean_a: Float64, mean_b: Float64, std_a: Float64, std_b: Float64
) -> Float64:
    """Barlow Twins normalised cross-correlation matrix element.

    C_ij = Σ_b z^A_bi × z^B_bj / N

    Args:
        z_a_i: Embedding element from branch A.
        z_b_i: Embedding element from branch B.
        n: Batch size.
        mean_a: Mean of z_a across batch.
        mean_b: Mean of z_b across batch.
        std_a: Std of z_a across batch.
        std_b: Std of z_b across batch.

    Returns:
        Normalised cross-correlation term.
    """
    if n <= 0.0 or std_a <= 0.0 or std_b <= 0.0:
        return 0.0
    var za_norm = (z_a_i - mean_a) / std_a
    var zb_norm = (z_b_i - mean_b) / std_b
    return za_norm * zb_norm / n
