"""
ml_metrics_extended.mojo — Extended ML evaluation metrics.
Zero Python imports.

Public API:
  auc_trapezoid                  — trapezoidal AUC for one ROC segment
  average_precision_term         — one term in AP / PR curve
  ndcg_gain                      — DCG gain at rank k
  ndcg_discount                  — DCG discount at rank k
  map_term                       — one term in Mean Average Precision
  f_beta_score                   — Fβ score
  matthews_corr_coeff            — Matthews correlation coefficient
  cohen_kappa                    — Cohen's kappa agreement
  calibration_ece_term           — Expected Calibration Error term
  brier_score_term               — Brier score term
"""
from std.math import sqrt, log, exp


def auc_trapezoid(
    fpr1: Float64, fpr2: Float64, tpr1: Float64, tpr2: Float64
) -> Float64:
    """Trapezoidal rule AUC for one ROC segment.

    Area = (fpr2 - fpr1) × (tpr1 + tpr2) / 2

    Args:
        fpr1: False positive rate at left point.
        fpr2: False positive rate at right point.
        tpr1: True positive rate at left point.
        tpr2: True positive rate at right point.

    Returns:
        Partial AUC for this segment.
    """
    return (fpr2 - fpr1) * (tpr1 + tpr2) / 2.0


def average_precision_term(
    precision: Float64, recall_delta: Float64
) -> Float64:
    """One term in Average Precision sum: P(r) × ΔR.

    Args:
        precision: Precision at this recall level.
        recall_delta: Change in recall (Δrecall).

    Returns:
        AP contribution.
    """
    return precision * recall_delta


def ndcg_gain(relevance: Float64) -> Float64:
    """DCG gain: 2^rel - 1.

    Args:
        relevance: Relevance label (0–4 typical).

    Returns:
        Gain value.
    """
    return exp(relevance * 0.6931471805599453) - 1.0


def ndcg_discount(rank: Float64) -> Float64:
    """DCG discount: 1 / log2(rank + 1).

    Args:
        rank: Rank position (1-indexed).

    Returns:
        Discount factor.
    """
    if rank <= 0.0:
        return 1.0
    return 1.0 / (log(rank + 1.0) / 0.6931471805599453)


def map_term(precision_at_k: Float64, is_relevant: Float64) -> Float64:
    """One term in Mean Average Precision: P@k × rel(k).

    Args:
        precision_at_k: Precision at rank k.
        is_relevant: 1.0 if item at rank k is relevant, else 0.0.

    Returns:
        AP contribution at this rank.
    """
    return precision_at_k * is_relevant


def f_beta_score(
    precision: Float64, recall: Float64, beta: Float64
) -> Float64:
    """Fβ score: (1+β²) × P × R / (β²P + R).

    Args:
        precision: Precision value.
        recall: Recall value.
        beta: β parameter (1 = F1, 2 = F2).

    Returns:
        Fβ score (0–1).
    """
    var b2 = beta * beta
    var denom = b2 * precision + recall
    if denom <= 0.0:
        return 0.0
    return (1.0 + b2) * precision * recall / denom


def matthews_corr_coeff(
    tp: Float64, tn: Float64, fp: Float64, fn_val: Float64
) -> Float64:
    """Matthews Correlation Coefficient.

    MCC = (TP×TN - FP×FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))

    Args:
        tp: True positives.
        tn: True negatives.
        fp: False positives.
        fn_val: False negatives.

    Returns:
        MCC (-1 to 1).
    """
    var num = tp * tn - fp * fn_val
    var denom_sq = (tp + fp) * (tp + fn_val) * (tn + fp) * (tn + fn_val)
    if denom_sq <= 0.0:
        return 0.0
    return num / sqrt(denom_sq)


def cohen_kappa(
    observed_agreement: Float64, expected_agreement: Float64
) -> Float64:
    """Cohen's kappa: (p_o - p_e) / (1 - p_e).

    Args:
        observed_agreement: Proportion of observed agreement p_o.
        expected_agreement: Proportion of expected agreement p_e.

    Returns:
        Kappa coefficient.
    """
    var denom = 1.0 - expected_agreement
    if denom <= 0.0:
        return 1.0
    return (observed_agreement - expected_agreement) / denom


def calibration_ece_term(
    bin_confidence: Float64, bin_accuracy: Float64,
    bin_count: Float64, total_count: Float64
) -> Float64:
    """Expected Calibration Error contribution for one confidence bin.

    ECE = Σ |acc(B_m) - conf(B_m)| × |B_m| / n

    Args:
        bin_confidence: Mean confidence in this bin.
        bin_accuracy: Fraction correct in this bin.
        bin_count: Number of samples in bin.
        total_count: Total samples.

    Returns:
        ECE contribution from this bin.
    """
    if total_count <= 0.0:
        return 0.0
    var diff = bin_accuracy - bin_confidence
    if diff < 0.0:
        diff = -diff
    return diff * bin_count / total_count


def brier_score_term(prob: Float64, outcome: Float64) -> Float64:
    """Brier score term: (p - y)² for one sample.

    Args:
        prob: Predicted probability.
        outcome: Actual outcome (0 or 1).

    Returns:
        Squared error term.
    """
    var diff = prob - outcome
    return diff * diff
