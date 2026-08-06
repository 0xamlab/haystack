"""
rlhf_dpo.mojo — RLHF, DPO, IPO, ORPO and preference optimisation math.
Zero Python imports.

Public API:
  dpo_loss                       — Direct Preference Optimisation loss
  ipo_loss                       — Identity Preference Optimisation loss
  orpo_ratio                     — ORPO odds ratio objective
  ppo_clip_objective             — PPO clipped surrogate objective
  reward_model_score             — Bradley-Terry reward model score
  kl_penalty_term                — KL divergence penalty from reference
  advantage_gae                  — Generalised Advantage Estimation
  grpo_group_advantage           — GRPO group-relative advantage
  sft_loss_token                 — supervised fine-tuning cross-entropy
  preference_margin_loss         — margin-based preference loss
"""
from std.math import sqrt, log, exp


def dpo_loss(
    log_ratio_chosen: Float64, log_ratio_rejected: Float64, beta: Float64
) -> Float64:
    """Direct Preference Optimisation loss (Rafailov et al. 2023).

    L_DPO = -log σ(β × (log π/π_ref(chosen) - log π/π_ref(rejected)))

    Args:
        log_ratio_chosen: log(π(y_w|x)/π_ref(y_w|x)) for preferred response.
        log_ratio_rejected: log(π(y_l|x)/π_ref(y_l|x)) for rejected response.
        beta: KL regularisation strength.

    Returns:
        DPO loss term.
    """
    var logit = beta * (log_ratio_chosen - log_ratio_rejected)
    return -log(1.0 / (1.0 + exp(-logit)))  # -log sigmoid


def ipo_loss(
    log_ratio_chosen: Float64, log_ratio_rejected: Float64, tau: Float64
) -> Float64:
    """Identity Preference Optimisation loss (Azar et al. 2024).

    L_IPO = (log π(chosen)/π_ref - log π(rejected)/π_ref - 1/(2τ))²

    Args:
        log_ratio_chosen: Log ratio for chosen response.
        log_ratio_rejected: Log ratio for rejected response.
        tau: Regularisation parameter.

    Returns:
        IPO loss term.
    """
    var diff = log_ratio_chosen - log_ratio_rejected - 1.0 / (2.0 * tau)
    return diff * diff


def orpo_ratio(
    chosen_log_prob: Float64, rejected_log_prob: Float64,
    chosen_seq_len: Float64, rejected_seq_len: Float64,
    lambda_orpo: Float64
) -> Float64:
    """ORPO odds ratio preference objective (Hong et al. 2024).

    odds = p/(1-p); loss = -log(odds_chosen / odds_rejected)

    Args:
        chosen_log_prob: Avg log prob of chosen response.
        rejected_log_prob: Avg log prob of rejected response.
        chosen_seq_len: Chosen sequence length.
        rejected_seq_len: Rejected sequence length.
        lambda_orpo: ORPO lambda coefficient.

    Returns:
        ORPO loss contribution.
    """
    # A log-prob > 0 (or nan) makes log(1-p) below nan/inf, which cannot
    # cross the JSON result wire; refuse with the degenerate loss.
    if not (chosen_log_prob <= 0.0) or not (rejected_log_prob <= 0.0):
        return 0.0
    var log_odds_chosen = chosen_log_prob - log(1.0 - exp(chosen_log_prob) + 1e-10)
    var log_odds_rejected = rejected_log_prob - log(1.0 - exp(rejected_log_prob) + 1e-10)
    var log_ratio = log_odds_chosen - log_odds_rejected
    var p = 1.0 / (1.0 + exp(-log_ratio))
    if not (p > 0.0):  # log(0)/log(nan) below would yield inf/nan
        return 0.0
    return -lambda_orpo * log(p)


def ppo_clip_objective(
    ratio: Float64, advantage: Float64, clip_eps: Float64
) -> Float64:
    """PPO clipped surrogate objective.

    L_clip = min(r × A, clip(r, 1-ε, 1+ε) × A)

    Args:
        ratio: π(a|s) / π_old(a|s) importance sampling ratio.
        advantage: Advantage estimate A(s,a).
        clip_eps: PPO clip epsilon (0.2 typical).

    Returns:
        Clipped objective (negate for loss).
    """
    var clipped_ratio = ratio
    if clipped_ratio > 1.0 + clip_eps:
        clipped_ratio = 1.0 + clip_eps
    if clipped_ratio < 1.0 - clip_eps:
        clipped_ratio = 1.0 - clip_eps
    var obj1 = ratio * advantage
    var obj2 = clipped_ratio * advantage
    if obj1 < obj2:
        return obj1
    return obj2


def reward_model_score(
    chosen_logit: Float64, rejected_logit: Float64
) -> Float64:
    """Bradley-Terry reward model pairwise loss.

    L = -log σ(r(chosen) - r(rejected))

    Args:
        chosen_logit: Reward model score for preferred response.
        rejected_logit: Reward model score for rejected response.

    Returns:
        Pairwise reward loss.
    """
    var diff = chosen_logit - rejected_logit
    return -log(1.0 / (1.0 + exp(-diff)))


def kl_penalty_term(
    log_prob_policy: Float64, log_prob_reference: Float64, beta: Float64
) -> Float64:
    """KL divergence penalty from reference model.

    penalty = β × (log π(y) - log π_ref(y))

    Args:
        log_prob_policy: Policy log probability for token.
        log_prob_reference: Reference model log probability.
        beta: KL coefficient.

    Returns:
        KL penalty term.
    """
    return beta * (log_prob_policy - log_prob_reference)


def advantage_gae(
    reward: Float64, value_current: Float64, value_next: Float64,
    gamma: Float64, lam: Float64, prev_gae: Float64
) -> Float64:
    """Generalised Advantage Estimation (GAE-λ).

    δ = r + γV(s') - V(s)
    GAE = δ + γλ × prev_GAE

    Args:
        reward: Reward at this step.
        value_current: Value estimate V(s).
        value_next: Value estimate V(s').
        gamma: Discount factor.
        lam: GAE lambda (0.95 typical).
        prev_gae: Previous GAE value (for recurrence).

    Returns:
        GAE advantage estimate.
    """
    var delta = reward + gamma * value_next - value_current
    return delta + gamma * lam * prev_gae


def grpo_group_advantage(
    reward: Float64, group_mean: Float64, group_std: Float64
) -> Float64:
    """GRPO group-relative advantage (DeepSeek-R1 style).

    A = (r - mean(group)) / std(group)

    Args:
        reward: Reward for this response.
        group_mean: Mean reward across group of responses.
        group_std: Std of rewards across group.

    Returns:
        Group-relative advantage.
    """
    if group_std <= 0.0:
        return reward - group_mean
    return (reward - group_mean) / group_std


def sft_loss_token(
    log_prob: Float64
) -> Float64:
    """Supervised fine-tuning cross-entropy loss for one token.

    L = -log p(y_t | y_{<t}, x)

    Args:
        log_prob: Log probability of target token.

    Returns:
        Token-level SFT loss.
    """
    return -log_prob


def preference_margin_loss(
    chosen_reward: Float64, rejected_reward: Float64, margin: Float64
) -> Float64:
    """Margin-based preference loss: max(0, margin - (chosen - rejected)).

    Args:
        chosen_reward: Reward for preferred response.
        rejected_reward: Reward for rejected response.
        margin: Required margin.

    Returns:
        Hinge loss (0 if preference satisfied).
    """
    var gap = chosen_reward - rejected_reward
    var loss = margin - gap
    if loss < 0.0:
        return 0.0
    return loss
