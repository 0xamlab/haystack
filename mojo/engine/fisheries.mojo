"""
fisheries.mojo — Fisheries Science Library. Zero Python imports.

Pure Mojo implementations of fundamental fisheries science equations
including CPUE, MSY, surplus production, mortality rates, growth models,
condition indices, and stock-recruitment relationships.

Public API:
  catch_per_unit_effort       — CPUE = C/E
  maximum_sustainable_yield   — MSY = r*K/4
  biomass_at_msy              — B_MSY = K/2
  schaefer_surplus_production — SP = r*B*(1-B/K)
  fishing_mortality           — F = C/B
  total_mortality             — Z = F + M
  exploitation_rate           — E = F/Z
  survival_rate               — S = exp(-Z)
  von_bertalanffy_length      — L(t) = Linf*(1-exp(-k*(t-t0)))
  condition_factor            — K = 100*W/L³
  gonadosomatic_index         — GSI = Wg/Wb * 100
  stock_recruitment_bevholt   — R = α*S/(β+S)
"""
from std.math import sqrt, exp, log, abs as fabs


# ── catch_per_unit_effort ────────────────────────────────────────────────────


def catch_per_unit_effort(total_catch: Float64, total_effort: Float64) -> Float64:
    """CPUE = C / E."""
    if total_effort <= 0.0:
        return 0.0
    return total_catch / total_effort


# ── maximum_sustainable_yield ────────────────────────────────────────────────


def maximum_sustainable_yield(r: Float64, k: Float64) -> Float64:
    """MSY = r * K / 4 (Schaefer model)."""
    return r * k / 4.0


# ── biomass_at_msy ───────────────────────────────────────────────────────────


def biomass_at_msy(k: Float64) -> Float64:
    """B_MSY = K / 2."""
    return k / 2.0


# ── schaefer_surplus_production ──────────────────────────────────────────────


def schaefer_surplus_production(
    r: Float64, biomass: Float64, k: Float64
) -> Float64:
    """Surplus Production SP = r * B * (1 - B/K)."""
    if k <= 0.0:
        return 0.0
    return r * biomass * (1.0 - biomass / k)


# ── fishing_mortality ────────────────────────────────────────────────────────


def fishing_mortality(catch: Float64, biomass: Float64) -> Float64:
    """Fishing mortality F = C / B."""
    if biomass <= 0.0:
        return 0.0
    return catch / biomass


# ── total_mortality ──────────────────────────────────────────────────────────


def total_mortality(fishing_mort: Float64, natural_mort: Float64) -> Float64:
    """Total mortality Z = F + M."""
    return fishing_mort + natural_mort


# ── exploitation_rate ────────────────────────────────────────────────────────


def exploitation_rate(fishing_mort: Float64, total_mort: Float64) -> Float64:
    """Exploitation rate E = F / Z."""
    if total_mort <= 0.0:
        return 0.0
    return fishing_mort / total_mort


# ── survival_rate ────────────────────────────────────────────────────────────


def survival_rate(total_mort: Float64) -> Float64:
    """Annual survival rate S = exp(-Z)."""
    return exp(-total_mort)


# ── von_bertalanffy_length ───────────────────────────────────────────────────


def von_bertalanffy_length(
    l_inf: Float64, k: Float64, t: Float64, t0: Float64
) -> Float64:
    """Von Bertalanffy growth: L(t) = Linf * (1 - exp(-k*(t-t0)))."""
    return l_inf * (1.0 - exp(-k * (t - t0)))


# ── condition_factor ─────────────────────────────────────────────────────────


def condition_factor(weight_g: Float64, length_cm: Float64) -> Float64:
    """Fulton's condition factor K = 100 * W / L³."""
    if length_cm <= 0.0:
        return 0.0
    return 100.0 * weight_g / (length_cm * length_cm * length_cm)


# ── gonadosomatic_index ─────────────────────────────────────────────────────


def gonadosomatic_index(
    gonad_weight: Float64, body_weight: Float64
) -> Float64:
    """GSI = gonad_weight / body_weight * 100 (%)."""
    if body_weight <= 0.0:
        return 0.0
    return gonad_weight / body_weight * 100.0


# ── stock_recruitment_bevholt ────────────────────────────────────────────────


def stock_recruitment_bevholt(
    alpha: Float64, beta: Float64, spawners: Float64
) -> Float64:
    """Beverton-Holt stock-recruitment: R = α*S / (β + S)."""
    var denom = beta + spawners
    if fabs(denom) < 1e-15:
        return 0.0
    return alpha * spawners / denom
