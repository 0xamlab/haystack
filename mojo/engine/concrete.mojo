"""
concrete.mojo — Concrete Technology Library. Zero Python imports.

Provides mix design, strength, durability, and structural calculations.

Public API:
  water_cement_ratio          — w/c = water / cement
  compressive_strength_abrams — fc = a * exp(-b * wc)
  cement_content              — C = water / wc
  aggregate_volume            — V_agg = total - cement - water - air*total/100
  slump_estimate              — slump_mm ≈ 300 * (wc - 0.3)
  maturity_nurse_saul         — M = (T - T0) * time
  modulus_of_elasticity       — Ec = 4700 * sqrt(fc)
  splitting_tensile_strength  — ft = 0.56 * sqrt(fc)
  drying_shrinkage_estimate   — ε ≈ (wc - 0.2) * 0.001 * (1 - agg/100)
  carbonation_depth           — d = k * sqrt(t)
  rebar_development_length    — Ld = db * fy / (4 * 0.56 * sqrt(fc))
  concrete_density_estimate   — ρ = (c + w + a) * (1 - air/100)
"""
from std.math import exp, sqrt, abs as fabs


# ── water_cement_ratio ───────────────────────────────────────────────────────


def water_cement_ratio(water_kg: Float64, cement_kg: Float64) -> Float64:
    """Water-cement ratio: w/c = water / cement.

    Args:
        water_kg: Mass of water (kg).
        cement_kg: Mass of cement (kg).

    Returns:
        Water-cement ratio (dimensionless).
    """
    if fabs(cement_kg) < 1e-30:
        return 0.0
    return water_kg / cement_kg


# ── compressive_strength_abrams ──────────────────────────────────────────────


def compressive_strength_abrams(
    a: Float64, b: Float64, wc_ratio: Float64
) -> Float64:
    """Abrams' law (simplified): fc = a * exp(-b * wc).

    Args:
        a: Strength coefficient (MPa).
        b: Decay constant.
        wc_ratio: Water-cement ratio.

    Returns:
        Compressive strength (MPa).
    """
    return a * exp(-b * wc_ratio)


# ── cement_content ───────────────────────────────────────────────────────────


def cement_content(water: Float64, wc_ratio: Float64) -> Float64:
    """Cement content: C = water / wc.

    Args:
        water: Mass of water (kg).
        wc_ratio: Water-cement ratio.

    Returns:
        Cement content (kg).
    """
    if fabs(wc_ratio) < 1e-30:
        return 0.0
    return water / wc_ratio


# ── aggregate_volume ─────────────────────────────────────────────────────────


def aggregate_volume(
    total_volume: Float64,
    cement_vol: Float64,
    water_vol: Float64,
    air_pct: Float64,
) -> Float64:
    """Aggregate volume: V_agg = total - cement - water - air*total/100.

    Args:
        total_volume: Total mix volume (m³).
        cement_vol: Cement volume (m³).
        water_vol: Water volume (m³).
        air_pct: Air content (%).

    Returns:
        Aggregate volume (m³).
    """
    return total_volume - cement_vol - water_vol - air_pct * total_volume / 100.0


# ── slump_estimate ───────────────────────────────────────────────────────────


def slump_estimate(wc_ratio: Float64) -> Float64:
    """Slump estimate: slump_mm ≈ 300 * (wc - 0.3).

    Simplified linear model for w/c in 0.3–0.7 range.

    Args:
        wc_ratio: Water-cement ratio.

    Returns:
        Estimated slump (mm). Clamped to ≥ 0.
    """
    var s = 300.0 * (wc_ratio - 0.3)
    if s < 0.0:
        return 0.0
    return s


# ── maturity_nurse_saul ──────────────────────────────────────────────────────


def maturity_nurse_saul(
    time_hours: Float64, temp: Float64, datum_temp: Float64
) -> Float64:
    """Nurse-Saul maturity: M = (T - T0) * Δt.

    Args:
        time_hours: Time period (hours).
        temp: Curing temperature (°C).
        datum_temp: Datum temperature (°C), typically -10.

    Returns:
        Maturity (°C·hours).
    """
    var diff = temp - datum_temp
    if diff < 0.0:
        return 0.0
    return diff * time_hours


# ── modulus_of_elasticity ────────────────────────────────────────────────────


def modulus_of_elasticity(fc_mpa: Float64) -> Float64:
    """ACI modulus of elasticity: Ec = 4700 * sqrt(fc) (MPa).

    Args:
        fc_mpa: Compressive strength (MPa).

    Returns:
        Modulus of elasticity (MPa).
    """
    if fc_mpa <= 0.0:
        return 0.0
    return 4700.0 * sqrt(fc_mpa)


# ── splitting_tensile_strength ───────────────────────────────────────────────


def splitting_tensile_strength(fc_mpa: Float64) -> Float64:
    """Splitting tensile strength: ft = 0.56 * sqrt(fc) (MPa).

    Args:
        fc_mpa: Compressive strength (MPa).

    Returns:
        Splitting tensile strength (MPa).
    """
    if fc_mpa <= 0.0:
        return 0.0
    return 0.56 * sqrt(fc_mpa)


# ── drying_shrinkage_estimate ────────────────────────────────────────────────


def drying_shrinkage_estimate(
    wc_ratio: Float64, aggregate_pct: Float64
) -> Float64:
    """Drying shrinkage estimate: ε ≈ (wc - 0.2) * 0.001 * (1 - agg/100).

    Args:
        wc_ratio: Water-cement ratio.
        aggregate_pct: Aggregate content (% of total volume).

    Returns:
        Estimated shrinkage strain (dimensionless).
    """
    return (wc_ratio - 0.2) * 0.001 * (1.0 - aggregate_pct / 100.0)


# ── carbonation_depth ────────────────────────────────────────────────────────


def carbonation_depth(k: Float64, time_years: Float64) -> Float64:
    """Carbonation depth: d = k * sqrt(t) (mm).

    Args:
        k: Carbonation coefficient (mm/√year).
        time_years: Time (years).

    Returns:
        Carbonation depth (mm).
    """
    if time_years <= 0.0:
        return 0.0
    return k * sqrt(time_years)


# ── rebar_development_length ─────────────────────────────────────────────────


def rebar_development_length(
    db: Float64, fy: Float64, fc: Float64
) -> Float64:
    """Rebar development length (simplified): Ld = db * fy / (4 * 0.56 * sqrt(fc)).

    Args:
        db: Bar diameter (mm).
        fy: Yield strength of rebar (MPa).
        fc: Compressive strength of concrete (MPa).

    Returns:
        Development length (mm).
    """
    if fc <= 0.0:
        return 0.0
    return db * fy / (4.0 * 0.56 * sqrt(fc))


# ── concrete_density_estimate ────────────────────────────────────────────────


def concrete_density_estimate(
    cement: Float64,
    water: Float64,
    aggregate: Float64,
    air_pct: Float64,
) -> Float64:
    """Concrete density estimate: ρ = (cement + water + aggregate) * (1 - air/100).

    All masses per m³ of concrete.

    Args:
        cement: Cement mass (kg/m³).
        water: Water mass (kg/m³).
        aggregate: Aggregate mass (kg/m³).
        air_pct: Air content (%).

    Returns:
        Estimated density (kg/m³).
    """
    return (cement + water + aggregate) * (1.0 - air_pct / 100.0)
