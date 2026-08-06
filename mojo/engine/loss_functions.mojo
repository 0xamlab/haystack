"""
loss_functions.mojo — ML loss functions. Zero Python imports.

Public API:
  binary_cross_entropy          — BCE for binary classification
  categorical_cross_entropy     — CE for multi-class
  focal_loss                    — focal loss for class imbalance
  huber_loss                    — smooth L1 / Huber loss
  kl_divergence                 — KL(P||Q) for distributions
  contrastive_loss              — Siamese network loss
  triplet_loss                  — anchor-positive-negative loss
  mse_loss                      — mean squared error
  mae_loss                      — mean absolute error
  label_smoothing_loss          — cross-entropy with label smoothing
"""
from std.math import log, exp, sqrt


def binary_cross_entropy(
    y_true: Float64, y_pred: Float64
) -> Float64:
    """Binary cross-entropy loss.

    BCE = -(y log(p) + (1-y) log(1-p))

    Args:
        y_true: Ground truth label (0 or 1).
        y_pred: Predicted probability (0–1).

    Returns:
        BCE loss for this sample.
    """
    var eps = 1e-7
    var p = y_pred
    if p < eps:
        p = eps
    if p > 1.0 - eps:
        p = 1.0 - eps
    return -(y_true * log(p) + (1.0 - y_true) * log(1.0 - p))


def categorical_cross_entropy(
    y_true: Float64, y_pred: Float64
) -> Float64:
    """Categorical cross-entropy for one class: -y log(p).

    Args:
        y_true: One-hot ground truth for this class.
        y_pred: Predicted probability for this class.

    Returns:
        CE contribution from this class.
    """
    var eps = 1e-7
    var p = y_pred if y_pred > eps else eps
    return -y_true * log(p)


def focal_loss(
    y_true: Float64, y_pred: Float64, gamma: Float64, alpha: Float64
) -> Float64:
    """Focal loss (Lin et al. 2017) for class imbalance.

    FL = -alpha × (1-p)^gamma × log(p)

    Args:
        y_true: Ground truth (0 or 1).
        y_pred: Predicted probability (0–1).
        gamma: Focusing parameter (0 = CE, 2 = standard focal).
        alpha: Class weighting factor (0–1).

    Returns:
        Focal loss for this sample.
    """
    var eps = 1e-7
    var p = y_pred if y_pred > eps else eps
    if p > 1.0 - eps:
        p = 1.0 - eps
    var p_t = p if y_true > 0.5 else (1.0 - p)
    var alpha_t = alpha if y_true > 0.5 else (1.0 - alpha)
    return -alpha_t * pow_approx(1.0 - p_t, gamma) * log(p_t)


def pow_approx(base: Float64, exponent: Float64) -> Float64:
    if base <= 0.0:
        return 0.0
    return exp(exponent * log(base))


def huber_loss(
    y_true: Float64, y_pred: Float64, delta: Float64
) -> Float64:
    """Huber (smooth L1) loss.

    L = 0.5(y-p)²           if |y-p| ≤ δ
    L = δ|y-p| - 0.5δ²     otherwise

    Args:
        y_true: True value.
        y_pred: Predicted value.
        delta: Threshold between quadratic and linear regions.

    Returns:
        Huber loss.
    """
    var diff = y_true - y_pred
    if diff < 0.0:
        diff = -diff
    if diff <= delta:
        return 0.5 * diff * diff
    return delta * diff - 0.5 * delta * delta


def kl_divergence(p: Float64, q: Float64) -> Float64:
    """KL divergence contribution: p × log(p/q).

    Args:
        p: True distribution probability.
        q: Approximate distribution probability.

    Returns:
        KL contribution (sum over all classes for full KL).
    """
    var eps = 1e-7
    if p <= eps:
        return 0.0
    var q_safe = q if q > eps else eps
    return p * log(p / q_safe)


def contrastive_loss(
    distance: Float64, label: Float64, margin: Float64
) -> Float64:
    """Contrastive loss (Hadsell et al. 2006).

    L = (1-y) × d² + y × max(0, margin - d)²

    Args:
        distance: Euclidean distance between pair embeddings.
        label: 0 = similar pair, 1 = dissimilar pair.
        margin: Margin for dissimilar pairs.

    Returns:
        Contrastive loss for this pair.
    """
    if label < 0.5:
        return distance * distance
    var diff = margin - distance
    if diff < 0.0:
        return 0.0
    return diff * diff


def triplet_loss(
    dist_pos: Float64, dist_neg: Float64, margin: Float64
) -> Float64:
    """Triplet loss: max(0, d_pos - d_neg + margin).

    Args:
        dist_pos: Distance between anchor and positive.
        dist_neg: Distance between anchor and negative.
        margin: Triplet margin.

    Returns:
        Triplet loss.
    """
    var loss = dist_pos - dist_neg + margin
    if loss < 0.0:
        return 0.0
    return loss


def mse_loss(y_true: Float64, y_pred: Float64) -> Float64:
    """Mean squared error (per sample): (y - p)².

    Args:
        y_true: True value.
        y_pred: Predicted value.

    Returns:
        Squared error.
    """
    var diff = y_true - y_pred
    return diff * diff


def mae_loss(y_true: Float64, y_pred: Float64) -> Float64:
    """Mean absolute error (per sample): |y - p|.

    Args:
        y_true: True value.
        y_pred: Predicted value.

    Returns:
        Absolute error.
    """
    var diff = y_true - y_pred
    if diff < 0.0:
        diff = -diff
    return diff


def label_smoothing_loss(
    y_true: Float64, y_pred: Float64,
    epsilon: Float64, n_classes: Float64
) -> Float64:
    """Cross-entropy with label smoothing.

    y_smooth = (1-ε) × y_true + ε/K

    Args:
        y_true: Hard one-hot label (0 or 1).
        y_pred: Predicted probability.
        epsilon: Smoothing factor (0.1 is common).
        n_classes: Total number of classes K.

    Returns:
        Smoothed cross-entropy contribution.
    """
    var eps_inner = 1e-7
    var p = y_pred if y_pred > eps_inner else eps_inner
    var y_smooth = (1.0 - epsilon) * y_true + epsilon / n_classes
    return -y_smooth * log(p)
