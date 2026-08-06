"""
data_feedback_loop.mojo — Data-centric AI loop: collect, label, retrain, deploy, evaluate.
Zero Python imports.

Public API:
  sample_informativeness          — active learning: how informative is a sample
  auto_label_confidence           — confidence of auto-labeling prediction
  data_drift_detection_score      — magnitude of data distribution shift
  retraining_trigger_score        — when to trigger model retraining
  dataset_freshness_score         — recency of training data
  annotation_effort_estimate      — labeling effort for a sample batch
  deployment_readiness_score      — model readiness for deployment
  online_evaluation_stat          — online AB test statistic
  feedback_signal_quality         — quality of collected feedback signal
  continuous_learning_rate        — adaptive learning rate for continual learning
"""
from std.math import sqrt, log, exp


def sample_informativeness(
    prediction_entropy: Float64, model_uncertainty: Float64,
    diversity_from_existing: Float64
) -> Float64:
    """Active learning: how informative is a sample for retraining.

    info = entropy × uncertainty × diversity

    Args:
        prediction_entropy: Entropy of model's prediction distribution.
        model_uncertainty: Epistemic uncertainty on this sample.
        diversity_from_existing: Distance from existing training data.

    Returns:
        Informativeness score (higher = more valuable to label).
    """
    return prediction_entropy * model_uncertainty * diversity_from_existing


def auto_label_confidence(
    teacher_model_logprob: Float64, label_agreement_rate: Float64,
    sample_difficulty: Float64
) -> Float64:
    """Confidence of auto-labeling (pseudo-labeling) a sample.

    confidence = exp(logprob) × agreement / difficulty

    Args:
        teacher_model_logprob: Log probability of teacher's label.
        label_agreement_rate: Agreement across multiple teacher signals.
        sample_difficulty: Estimated sample difficulty (higher = harder).

    Returns:
        Auto-label confidence (0–1).
    """
    if sample_difficulty <= 0.0:
        return exp(teacher_model_logprob)
    return exp(teacher_model_logprob) * label_agreement_rate / sample_difficulty


def data_drift_detection_score(
    current_feature_mean: Float64, baseline_feature_mean: Float64,
    baseline_feature_std: Float64
) -> Float64:
    """Magnitude of data distribution shift (z-score style).

    drift = |current_mean - baseline_mean| / baseline_std

    Args:
        current_feature_mean: Current distribution mean.
        baseline_feature_mean: Training distribution mean.
        baseline_feature_std: Training distribution standard deviation.

    Returns:
        Drift z-score (0 = no drift, >2 = significant drift).
    """
    if baseline_feature_std <= 0.0:
        return 0.0
    var diff = current_feature_mean - baseline_feature_mean
    if diff < 0.0:
        diff = -diff
    return diff / baseline_feature_std


def retraining_trigger_score(
    performance_degradation: Float64, drift_score: Float64,
    data_volume_new: Float64, retrain_cost: Float64
) -> Float64:
    """When to trigger model retraining.

    Positive = retrain now; negative = wait.

    Args:
        performance_degradation: Drop in key metric since last training.
        drift_score: Data drift magnitude.
        data_volume_new: New labeled samples available.
        retrain_cost: Compute cost of retraining.

    Returns:
        Retraining trigger score.
    """
    var benefit = performance_degradation * 10.0 + drift_score + log(data_volume_new + 1.0)
    return benefit - retrain_cost


def dataset_freshness_score(
    newest_sample_age_days: Float64, half_life_days: Float64
) -> Float64:
    """Recency of training data (exponential decay by age).

    Args:
        newest_sample_age_days: Age of most recent sample.
        half_life_days: Half-life of data freshness.

    Returns:
        Freshness score (1 = current, 0 = stale).
    """
    if half_life_days <= 0.0:
        return 1.0
    return exp(-newest_sample_age_days * 0.693 / half_life_days)


def annotation_effort_estimate(
    n_samples: Float64, avg_annotation_time_s: Float64,
    review_fraction: Float64
) -> Float64:
    """Total annotation effort estimate for a batch.

    effort = n × time × (1 + review_fraction)

    Args:
        n_samples: Number of samples to annotate.
        avg_annotation_time_s: Average time per sample.
        review_fraction: Fraction requiring human review.

    Returns:
        Total annotation time (seconds).
    """
    return n_samples * avg_annotation_time_s * (1.0 + review_fraction)


def deployment_readiness_score(
    validation_accuracy: Float64, accuracy_threshold: Float64,
    bias_score: Float64, bias_threshold: Float64,
    safety_score: Float64
) -> Float64:
    """Model readiness for deployment (all gates must pass).

    Args:
        validation_accuracy: Holdout set accuracy.
        accuracy_threshold: Minimum acceptable accuracy.
        bias_score: Detected bias metric (lower = better).
        bias_threshold: Maximum acceptable bias.
        safety_score: Safety evaluation score (0–1).

    Returns:
        Readiness score (1 = ready, 0 = not ready).
    """
    var acc_ok = 1.0 if validation_accuracy >= accuracy_threshold else 0.0
    var bias_ok = 1.0 if bias_score <= bias_threshold else 0.0
    return acc_ok * bias_ok * safety_score


def online_evaluation_stat(
    treatment_metric: Float64, control_metric: Float64,
    pooled_std: Float64, n_samples: Float64
) -> Float64:
    """Online AB test z-statistic for model comparison.

    z = (treatment - control) / (std / sqrt(n))

    Args:
        treatment_metric: Metric for new model.
        control_metric: Metric for baseline model.
        pooled_std: Pooled standard deviation.
        n_samples: Total samples per arm.

    Returns:
        Z-statistic (positive = treatment better).
    """
    if pooled_std <= 0.0 or n_samples <= 0.0:
        return 0.0
    return (treatment_metric - control_metric) / (pooled_std / sqrt(n_samples))


def feedback_signal_quality(
    explicit_feedback_rate: Float64, implicit_signal_rate: Float64,
    label_noise_estimate: Float64
) -> Float64:
    """Quality of collected user feedback signal.

    quality = (explicit × 0.7 + implicit × 0.3) × (1 - noise)

    Args:
        explicit_feedback_rate: Rate of explicit user feedback (0–1).
        implicit_signal_rate: Rate of implicit signal collection (0–1).
        label_noise_estimate: Estimated label noise (0–1).

    Returns:
        Overall feedback quality score (0–1).
    """
    var signal = explicit_feedback_rate * 0.7 + implicit_signal_rate * 0.3
    return signal * (1.0 - label_noise_estimate)


def continuous_learning_rate(
    base_lr: Float64, drift_magnitude: Float64,
    catastrophic_forgetting_risk: Float64
) -> Float64:
    """Adaptive learning rate for continual learning.

    Higher drift → higher LR; high forgetting risk → lower LR.

    Args:
        base_lr: Base learning rate.
        drift_magnitude: Detected drift magnitude.
        catastrophic_forgetting_risk: Risk of forgetting old knowledge (0–1).

    Returns:
        Adjusted learning rate.
    """
    var drift_boost = 1.0 + drift_magnitude
    var forgetting_penalty = 1.0 - catastrophic_forgetting_risk * 0.9
    return base_lr * drift_boost * forgetting_penalty
