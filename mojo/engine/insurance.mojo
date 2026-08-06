"""
insurance.mojo — Insurance Mathematics Library. Zero Python imports.

Pure Mojo implementations of actuarial and insurance pricing formulas
including pure/gross premium, loss/expense/combined ratios, claim
frequency & severity, burning cost, Bühlmann credibility, and more.

Public API:
  pure_premium                    — PP = loss / exposure
  gross_premium                   — GP = PP / (1 - ER - PM)
  loss_ratio                      — LR = losses / premiums
  expense_ratio                   — ER = expenses / premiums
  combined_ratio                  — CR = LR + ER
  expected_claim_frequency        — freq = claims / policies
  expected_claim_severity         — severity = losses / claims
  burning_cost                    — BC = losses / exposure
  credibility_buhlmann            — Z = n / (n + k)
  risk_load                       — RL = λ * variance
  aggregate_deductible_savings    — Savings = min(ded, avg) * freq
  retention_rate                  — RR = renewed / total * 100
"""


# ── pure_premium ─────────────────────────────────────────────────────────────


def pure_premium(expected_loss: Float64, exposure: Float64) -> Float64:
    """PP = expected_loss / exposure."""
    return expected_loss / exposure


# ── gross_premium ────────────────────────────────────────────────────────────


def gross_premium(
    pure_premium_val: Float64, expense_ratio: Float64, profit_margin: Float64
) -> Float64:
    """GP = PP / (1 - ER - PM)."""
    return pure_premium_val / (1.0 - expense_ratio - profit_margin)


# ── loss_ratio ───────────────────────────────────────────────────────────────


def loss_ratio(incurred_losses: Float64, earned_premiums: Float64) -> Float64:
    """LR = incurred_losses / earned_premiums."""
    return incurred_losses / earned_premiums


# ── expense_ratio ────────────────────────────────────────────────────────────


def expense_ratio(expenses: Float64, written_premiums: Float64) -> Float64:
    """ER = expenses / written_premiums."""
    return expenses / written_premiums


# ── combined_ratio ───────────────────────────────────────────────────────────


def combined_ratio(loss_r: Float64, expense_r: Float64) -> Float64:
    """CR = LR + ER."""
    return loss_r + expense_r


# ── expected_claim_frequency ─────────────────────────────────────────────────


def expected_claim_frequency(n_claims: Float64, n_policies: Float64) -> Float64:
    """freq = n_claims / n_policies."""
    return n_claims / n_policies


# ── expected_claim_severity ──────────────────────────────────────────────────


def expected_claim_severity(total_losses: Float64, n_claims: Float64) -> Float64:
    """severity = total_losses / n_claims."""
    return total_losses / n_claims


# ── burning_cost ─────────────────────────────────────────────────────────────


def burning_cost(total_losses: Float64, total_exposure: Float64) -> Float64:
    """BC = total_losses / total_exposure."""
    return total_losses / total_exposure


# ── credibility_buhlmann ─────────────────────────────────────────────────────


def credibility_buhlmann(n: Float64, k: Float64) -> Float64:
    """Bühlmann credibility factor: Z = n / (n + k).

    n = number of observations/years.
    k = Bühlmann parameter (variance ratio).
    """
    return n / (n + k)


# ── risk_load ────────────────────────────────────────────────────────────────


def risk_load(variance: Float64, lambda_val: Float64) -> Float64:
    """RL = λ * variance — risk loading on premium."""
    return lambda_val * variance


# ── aggregate_deductible_savings ─────────────────────────────────────────────


def aggregate_deductible_savings(
    deductible: Float64, claim_freq: Float64, avg_claim: Float64
) -> Float64:
    """Savings = min(deductible, avg_claim) * claim_freq.

    Estimates premium savings from applying an aggregate deductible.
    """
    var capped = deductible
    if avg_claim < deductible:
        capped = avg_claim
    return capped * claim_freq


# ── retention_rate ───────────────────────────────────────────────────────────


def retention_rate(renewed: Float64, total: Float64) -> Float64:
    """RR = renewed / total * 100 (percentage)."""
    return renewed / total * 100.0
