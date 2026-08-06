"""
corrosion.mojo — Corrosion Engineering Library. Zero Python imports.

Provides corrosion rate calculations, pitting analysis, galvanic corrosion,
electrochemistry (Nernst, Tafel), cathodic protection, and service life
estimation for the Codna Decision Engine.

Public API:
  corrosion_rate_mpy              — Weight-loss corrosion rate (mils/year)
  corrosion_rate_mmpy             — Weight-loss corrosion rate (mm/year)
  pitting_rate                    — Pitting penetration rate
  pitting_factor                  — Max pit depth / avg penetration
  galvanic_potential_difference   — |E1 - E2| volts
  nernst_potential                — Nernst equation for electrode potential
  passivation_current_density     — Current density i = I/A
  tafel_overpotential             — Tafel equation η = a + b*log10(i)
  metal_loss_from_rate            — Projected metal loss (mm)
  remaining_wall_thickness        — Wall thickness after loss
  cathodic_protection_current     — Required CP current
  service_life_estimate           — Estimated service life (years)
"""
from std.math import abs as fabs, log


# ── Corrosion rate from weight loss ──────────────────────────────────────────


def corrosion_rate_mpy(
    weight_loss: Float64,
    density: Float64,
    area: Float64,
    time_hours: Float64,
) -> Float64:
    """Corrosion rate in mils per year.

    CR = (534 * W) / (D * A * T)
    W = weight loss (mg), D = density (g/cm³),
    A = area (in²), T = exposure time (hours).
    """
    return (534.0 * weight_loss) / (density * area * time_hours)


def corrosion_rate_mmpy(
    weight_loss: Float64,
    density: Float64,
    area: Float64,
    time_hours: Float64,
) -> Float64:
    """Corrosion rate in mm per year.

    CR = (87600 * W) / (D * A * T)
    W = weight loss (mg), D = density (g/cm³),
    A = area (cm²), T = exposure time (hours).
    """
    return (87600.0 * weight_loss) / (density * area * time_hours)


# ── Pitting analysis ────────────────────────────────────────────────────────


def pitting_rate(max_pit_depth: Float64, time: Float64) -> Float64:
    """Pitting penetration rate PR = depth / time."""
    return max_pit_depth / time


def pitting_factor(max_pit_depth: Float64, avg_penetration: Float64) -> Float64:
    """Pitting factor PF = max_pit_depth / avg_penetration."""
    return max_pit_depth / avg_penetration


# ── Galvanic / electrochemistry ──────────────────────────────────────────────


def galvanic_potential_difference(e1: Float64, e2: Float64) -> Float64:
    """Galvanic potential difference ΔE = |E1 - E2| volts."""
    return fabs(e1 - e2)


def nernst_potential(
    e0: Float64,
    n: Float64,
    q_ratio: Float64,
    temperature: Float64,
) -> Float64:
    """Nernst equation: E = E0 - (RT / nF) * ln(Q).

    R = 8.314 J/(mol·K), F = 96485 C/mol.
    temperature in Kelvin, n = electron count, q_ratio = reaction quotient.
    """
    var r: Float64 = 8.314
    var f: Float64 = 96485.0
    return e0 - (r * temperature / (n * f)) * log(q_ratio)


def passivation_current_density(
    current: Float64, area: Float64
) -> Float64:
    """Passivation current density i = I / A  (A/cm²)."""
    return current / area


def tafel_overpotential(
    a: Float64, b: Float64, current_density: Float64
) -> Float64:
    """Tafel equation: η = a + b * log10(i).

    log10(x) = ln(x) / ln(10).
    """
    var log10_i = log(current_density) / log(10.0)
    return a + b * log10_i


# ── Metal loss & service life ────────────────────────────────────────────────


def metal_loss_from_rate(rate_mmpy: Float64, years: Float64) -> Float64:
    """Metal loss (mm) = rate (mm/yr) * years."""
    return rate_mmpy * years


def remaining_wall_thickness(
    original: Float64, loss: Float64
) -> Float64:
    """Remaining wall thickness t_rem = original - loss (mm)."""
    return original - loss


def cathodic_protection_current(
    area: Float64, current_density: Float64
) -> Float64:
    """Required cathodic-protection current I = A * i_cp (A)."""
    return area * current_density


def service_life_estimate(
    wall_thickness: Float64, corrosion_rate: Float64
) -> Float64:
    """Estimated service life (years) = wall_thickness / corrosion_rate."""
    return wall_thickness / corrosion_rate
