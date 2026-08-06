"""
behavioral_economics.mojo — Behavioral Economics Library. Zero Python imports.

Provides prospect theory, discounting, biases, and nudge calculations.

Public API:
  prospect_theory_value          — v(x) = x^α if x≥0, else -λ*(-x)^α
  probability_weighting          — Prelec weighting function
  hyperbolic_discount            — PV = V / (1 + k*t)
  quasi_hyperbolic_discount      — PV = β*δ^t*V (t>0), V (t=0)
  anchoring_adjusted_estimate    — Est = anchor + adjustment*factor
  endowment_effect_wta_wtp_ratio — Ratio = WTA/WTP
  loss_aversion_coefficient      — λ = |loss_impact|/gain_impact
  mental_accounting_total        — Net = gains + losses
  status_quo_bias                — Bias = cost - benefit
  sunk_cost_ratio                — SCR = sunk/total
  fairness_ultimatum_threshold   — Fair% = offer/total*100
  nudge_effectiveness            — Effect = treated - control
"""
from std.math import exp, log, abs as fabs


# ── prospect_theory_value ────────────────────────────────────────────────────


def prospect_theory_value(
    x: Float64, alpha: Float64, lambda_loss: Float64
) -> Float64:
    """Prospect theory value function: v(x) = x^α if x≥0, else -λ*(-x)^α.

    Args:
        x: Outcome value.
        alpha: Diminishing sensitivity exponent (0-1, e.g. 0.88).
        lambda_loss: Loss aversion coefficient (e.g. 2.25).

    Returns:
        Subjective value.
    """
    if x >= 0.0:
        if x < 1e-30:
            return 0.0
        return exp(alpha * log(x))
    else:
        var abs_x = fabs(x)
        if abs_x < 1e-30:
            return 0.0
        return -lambda_loss * exp(alpha * log(abs_x))


# ── probability_weighting ────────────────────────────────────────────────────


def probability_weighting(p: Float64, gamma: Float64) -> Float64:
    """Prelec probability weighting: w(p) = p^γ / (p^γ + (1-p)^γ)^(1/γ).

    Args:
        p: Objective probability (0-1).
        gamma: Curvature parameter (e.g. 0.61).

    Returns:
        Weighted probability.
    """
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    if gamma <= 0.0:
        return p
    var p_g = exp(gamma * log(p))
    var q_g = exp(gamma * log(1.0 - p))
    var denom = p_g + q_g
    if fabs(denom) < 1e-30:
        return p
    var denom_pow = exp((1.0 / gamma) * log(denom))
    if fabs(denom_pow) < 1e-30:
        return p
    return p_g / denom_pow


# ── hyperbolic_discount ──────────────────────────────────────────────────────


def hyperbolic_discount(
    value: Float64, k: Float64, delay: Float64
) -> Float64:
    """Hyperbolic discount: PV = V / (1 + k*t).

    Args:
        value: Future value.
        k: Discount rate parameter.
        delay: Time delay.

    Returns:
        Present value.
    """
    return value / (1.0 + k * delay)


# ── quasi_hyperbolic_discount ────────────────────────────────────────────────


def quasi_hyperbolic_discount(
    value: Float64, beta: Float64, delta: Float64, period: Float64
) -> Float64:
    """Quasi-hyperbolic discount: PV = β*δ^t*V for t>0, V for t=0.

    Args:
        value: Future value.
        beta: Present bias parameter (0-1).
        delta: Per-period discount factor (0-1).
        period: Time period.

    Returns:
        Present value.
    """
    if period <= 0.0:
        return value
    if delta <= 0.0:
        return 0.0
    return beta * exp(period * log(delta)) * value


# ── anchoring_adjusted_estimate ──────────────────────────────────────────────


def anchoring_adjusted_estimate(
    anchor: Float64, adjustment: Float64, adjustment_factor: Float64
) -> Float64:
    """Anchoring-adjusted estimate: Est = anchor + adjustment * factor.

    Args:
        anchor: Initial anchor value.
        adjustment: Raw adjustment from anchor.
        adjustment_factor: Factor of adjustment (0-1 = insufficient).

    Returns:
        Adjusted estimate.
    """
    return anchor + adjustment * adjustment_factor


# ── endowment_effect_wta_wtp_ratio ──────────────────────────────────────────


def endowment_effect_wta_wtp_ratio(
    wta: Float64, wtp: Float64
) -> Float64:
    """Endowment effect WTA/WTP ratio: Ratio = WTA / WTP.

    Args:
        wta: Willingness to accept.
        wtp: Willingness to pay.

    Returns:
        WTA/WTP ratio (typically > 1).
    """
    if fabs(wtp) < 1e-30:
        return 0.0
    return wta / wtp


# ── loss_aversion_coefficient ────────────────────────────────────────────────


def loss_aversion_coefficient(
    loss_impact: Float64, gain_impact: Float64
) -> Float64:
    """Loss aversion coefficient: λ = |loss_impact| / gain_impact.

    Args:
        loss_impact: Magnitude of loss impact (can be negative).
        gain_impact: Magnitude of gain impact (positive).

    Returns:
        Loss aversion coefficient (typically ~2.0-2.5).
    """
    if fabs(gain_impact) < 1e-30:
        return 0.0
    return fabs(loss_impact) / gain_impact


# ── mental_accounting_total ──────────────────────────────────────────────────


def mental_accounting_total(
    gains: Float64, losses: Float64
) -> Float64:
    """Mental accounting: Net = gains + losses (segregation).

    Args:
        gains: Total gains (positive).
        losses: Total losses (negative or positive magnitude).

    Returns:
        Net mental account balance.
    """
    return gains + losses


# ── status_quo_bias ──────────────────────────────────────────────────────────


def status_quo_bias(
    switching_cost: Float64, switching_benefit: Float64
) -> Float64:
    """Status quo bias: Bias = cost - benefit. Positive means stay.

    Args:
        switching_cost: Perceived cost of switching.
        switching_benefit: Perceived benefit of switching.

    Returns:
        Bias value (positive = stay with status quo).
    """
    return switching_cost - switching_benefit


# ── sunk_cost_ratio ──────────────────────────────────────────────────────────


def sunk_cost_ratio(
    sunk: Float64, total_budget: Float64
) -> Float64:
    """Sunk cost ratio: SCR = sunk / total.

    Args:
        sunk: Sunk (irrecoverable) cost.
        total_budget: Total budget.

    Returns:
        Sunk cost ratio (0-1).
    """
    if fabs(total_budget) < 1e-30:
        return 0.0
    return sunk / total_budget


# ── fairness_ultimatum_threshold ─────────────────────────────────────────────


def fairness_ultimatum_threshold(
    offer: Float64, total: Float64
) -> Float64:
    """Fairness in ultimatum game: Fair% = (offer/total) * 100.

    Args:
        offer: Amount offered.
        total: Total amount to split.

    Returns:
        Fairness percentage (%).
    """
    if fabs(total) < 1e-30:
        return 0.0
    return offer / total * 100.0


# ── nudge_effectiveness ──────────────────────────────────────────────────────


def nudge_effectiveness(
    treated_rate: Float64, control_rate: Float64
) -> Float64:
    """Nudge effectiveness: Effect = treated_rate - control_rate.

    Args:
        treated_rate: Rate in treated group (0-1 or %).
        control_rate: Rate in control group (0-1 or %).

    Returns:
        Treatment effect (same units as inputs).
    """
    return treated_rate - control_rate
