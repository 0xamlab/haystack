"""
evaluation_feedback.mojo — Model evaluation, drift detection, and feedback loop.
Zero Python imports.

Public API:
  accuracy_rolling_update        — rolling accuracy with decay
  model_drift_ks_stat            — Kolmogorov-Smirnov drift statistic
  population_stability_index     — PSI drift detection
  prediction_shift_score         — prediction distribution shift
  feedback_reward_signal         — RLHF reward from human feedback
  label_noise_rate_estimate      — label noise rate detection
  online_auc_update              — streaming AUC approximation update
  calibration_drift_score        — predicted vs actual calibration drift
  shadow_model_divergence        — shadow deployment divergence metric
  evaluation_sample_efficiency   — minimum eval set size for confidence
"""
from std.math import sqrt, log, exp


def accuracy_rolling_update(
    current_acc: Float64, new_correct: Float64,
    alpha: Float64
) -> Float64:
    """EMA-rolling accuracy update.

    acc_t = α × new_sample + (1-α) × acc_{t-1}

    Args:
        current_acc: Current rolling accuracy.
        new_correct: 1.0 if latest prediction correct, 0.0 if wrong.
        alpha: EMA smoothing (0.01–0.1 for slow tracking).

    Returns:
        Updated rolling accuracy.
    """
    return alpha * new_correct + (1.0 - alpha) * current_acc


def model_drift_ks_stat(
    cdf_reference: Float64, cdf_current: Float64
) -> Float64:
    """KS test statistic contribution: |F_ref(x) - F_cur(x)|.

    Take the max over all x for the full KS statistic.

    Args:
        cdf_reference: Reference distribution CDF value at x.
        cdf_current: Current distribution CDF value at x.

    Returns:
        Absolute difference (accumulate max for KS stat).
    """
    var diff = cdf_reference - cdf_current
    if diff < 0.0:
        return -diff
    return diff


def population_stability_index(
    p_current: Float64, p_reference: Float64
) -> Float64:
    """PSI term: (p_cur - p_ref) × log(p_cur / p_ref).

    Sum across bins for total PSI. PSI < 0.1 = stable, > 0.25 = drift.

    Args:
        p_current: Current bin proportion.
        p_reference: Reference bin proportion.

    Returns:
        PSI contribution for this bin.
    """
    if p_current <= 0.0 or p_reference <= 0.0:
        return 0.0
    return (p_current - p_reference) * log(p_current / p_reference)


def prediction_shift_score(
    mean_pred_new: Float64, mean_pred_ref: Float64,
    std_pred_ref: Float64
) -> Float64:
    """Prediction shift: normalised mean shift in model outputs.

    shift = |μ_new - μ_ref| / σ_ref (in standard deviations)

    Args:
        mean_pred_new: Current mean prediction.
        mean_pred_ref: Reference mean prediction.
        std_pred_ref: Reference standard deviation.

    Returns:
        Shift in standard deviations (> 2 = significant drift).
    """
    if std_pred_ref <= 0.0:
        return 0.0
    var diff = mean_pred_new - mean_pred_ref
    if diff < 0.0:
        diff = -diff
    return diff / std_pred_ref


def feedback_reward_signal(
    human_rating: Float64, baseline_rating: Float64,
    reward_scale: Float64
) -> Float64:
    """RLHF reward signal from human preference feedback.

    reward = (human - baseline) × scale

    Args:
        human_rating: Human preference score (0–1 or Likert).
        baseline_rating: Baseline/reference model score.
        reward_scale: Reward scaling factor.

    Returns:
        Reward signal for RL training.
    """
    return (human_rating - baseline_rating) * reward_scale


def label_noise_rate_estimate(
    agreement_rate: Float64, n_annotators: Float64
) -> Float64:
    """Label noise estimate from inter-annotator disagreement.

    noise ≈ 1 - agreement_rate / expected_max_agreement

    Args:
        agreement_rate: Observed fraction of label agreement.
        n_annotators: Number of annotators.

    Returns:
        Estimated label noise rate (0–1).
    """
    if n_annotators <= 1.0:
        return 0.0
    var expected_chance = 1.0 / n_annotators
    var noise = 1.0 - (agreement_rate - expected_chance) / (1.0 - expected_chance)
    if noise < 0.0:
        return 0.0
    if noise > 1.0:
        return 1.0
    return noise


def online_auc_update(
    current_auc: Float64, new_pos_rank: Float64,
    n_positive: Float64, n_negative: Float64
) -> Float64:
    """Streaming AUC approximation update (Wilcoxon-Mann-Whitney).

    AUC ≈ Σ(pos_rank) / (n_pos × n_neg) corrected.

    Args:
        current_auc: Running AUC estimate.
        new_pos_rank: Rank of new positive sample.
        n_positive: Count of positives seen so far.
        n_negative: Count of negatives seen so far.

    Returns:
        Updated AUC estimate.
    """
    if n_positive <= 0.0 or n_negative <= 0.0:
        return current_auc
    var new_contribution = (new_pos_rank - n_positive) / (n_positive * n_negative)
    return current_auc + new_contribution


def calibration_drift_score(
    current_ece: Float64, baseline_ece: Float64
) -> Float64:
    """Calibration drift: change in ECE from baseline.

    Args:
        current_ece: Current Expected Calibration Error.
        baseline_ece: Reference/baseline ECE.

    Returns:
        ECE delta (positive = model less calibrated than before).
    """
    return current_ece - baseline_ece


def shadow_model_divergence(
    prod_prediction: Float64, shadow_prediction: Float64
) -> Float64:
    """Divergence between production and shadow model predictions.

    Used to validate shadow deployments before promotion.

    Args:
        prod_prediction: Production model output.
        shadow_prediction: Shadow (candidate) model output.

    Returns:
        Absolute divergence.
    """
    var diff = prod_prediction - shadow_prediction
    if diff < 0.0:
        return -diff
    return diff


def evaluation_sample_efficiency(
    target_std_error: Float64, metric_std: Float64
) -> Float64:
    """Minimum evaluation samples for target standard error.

    n = (σ / SE)²

    Args:
        target_std_error: Desired standard error of metric.
        metric_std: Expected metric standard deviation.

    Returns:
        Minimum sample count.
    """
    if target_std_error <= 0.0:
        return 1e6
    var ratio = metric_std / target_std_error
    return ratio * ratio
