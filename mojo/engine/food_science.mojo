"""
food_science.mojo — Food Science Library. Zero Python imports.

Pure Mojo implementations of fundamental food science equations
including water activity, pH, shelf life, thermal processing,
moisture content, and caloric calculations.

Public API:
  water_activity                 — aw ≈ mole_fraction (Raoult's simplified)
  ph_from_h_concentration        — pH = -log10([H+])
  shelf_life_q10                 — Life = base / q10^(ΔT/10)
  thermal_death_time             — t = D * log_reduction
  d_value_from_z                 — D = D_ref * 10^((T_ref-T)/z)
  pasteurization_units           — PU = time * 10^((T-T_ref)/z)
  brix_to_sugar_g_per_l          — Sugar ≈ brix * 10 (g/L simplified)
  caloric_density                — kcal = 4*P + 9*F + 4*C + 7*A
  moisture_content_wet_basis     — MC = water/total * 100
  moisture_content_dry_basis     — MC = water/dry * 100
  freezing_point_depression      — ΔTf = Kf * m
  blanching_time_estimate        — t ≈ thickness²/(4*D)
"""
from std.math import sqrt, exp, log, abs as fabs


# ── water_activity ───────────────────────────────────────────────────────────


def water_activity(mole_fraction_water: Float64) -> Float64:
    """Simplified Raoult's law: aw ≈ mole fraction of water."""
    return mole_fraction_water


# ── ph_from_h_concentration ──────────────────────────────────────────────────


def ph_from_h_concentration(h_conc: Float64) -> Float64:
    """pH = -log10([H+]).  Uses ln(x)/ln(10)."""
    comptime LN10 = log(10.0)
    return -log(h_conc) / LN10


# ── shelf_life_q10 ───────────────────────────────────────────────────────────


def shelf_life_q10(base_life: Float64, q10: Float64, temp_increase: Float64) -> Float64:
    """Shelf life = base_life / q10^(ΔT/10)."""
    var exponent = temp_increase / 10.0
    # q10^exp = exp(exp * ln(q10))
    return base_life / exp(exponent * log(q10))


# ── thermal_death_time ───────────────────────────────────────────────────────


def thermal_death_time(d_value: Float64, log_reduction: Float64) -> Float64:
    """t = D * log_reduction."""
    return d_value * log_reduction


# ── d_value_from_z ───────────────────────────────────────────────────────────


def d_value_from_z(d_ref: Float64, z_value: Float64, temp: Float64, ref_temp: Float64) -> Float64:
    """D = D_ref * 10^((T_ref - T) / z)."""
    comptime LN10 = log(10.0)
    var exponent = (ref_temp - temp) / z_value
    return d_ref * exp(exponent * LN10)


# ── pasteurization_units ─────────────────────────────────────────────────────


def pasteurization_units(time_min: Float64, temp: Float64, z_value: Float64, ref_temp: Float64) -> Float64:
    """PU = time * 10^((T - T_ref) / z)."""
    comptime LN10 = log(10.0)
    var exponent = (temp - ref_temp) / z_value
    return time_min * exp(exponent * LN10)


# ── brix_to_sugar_g_per_l ───────────────────────────────────────────────────


def brix_to_sugar_g_per_l(brix: Float64) -> Float64:
    """Sugar ≈ brix * 10 (g/L simplified)."""
    return brix * 10.0


# ── caloric_density ──────────────────────────────────────────────────────────


def caloric_density(protein_g: Float64, fat_g: Float64, carb_g: Float64, alcohol_g: Float64) -> Float64:
    """kcal = 4*P + 9*F + 4*C + 7*A (Atwater factors)."""
    return 4.0 * protein_g + 9.0 * fat_g + 4.0 * carb_g + 7.0 * alcohol_g


# ── moisture_content_wet_basis ───────────────────────────────────────────────


def moisture_content_wet_basis(water_mass: Float64, total_mass: Float64) -> Float64:
    """MC_wb = (water / total) * 100."""
    return water_mass / total_mass * 100.0


# ── moisture_content_dry_basis ───────────────────────────────────────────────


def moisture_content_dry_basis(water_mass: Float64, dry_mass: Float64) -> Float64:
    """MC_db = (water / dry) * 100."""
    return water_mass / dry_mass * 100.0


# ── freezing_point_depression ────────────────────────────────────────────────


def freezing_point_depression(kf: Float64, molality: Float64) -> Float64:
    """ΔTf = Kf * m."""
    return kf * molality


# ── blanching_time_estimate ──────────────────────────────────────────────────


def blanching_time_estimate(thickness_mm: Float64, diffusivity: Float64) -> Float64:
    """t ≈ thickness² / (4 * D)  (simplified heat penetration)."""
    return (thickness_mm * thickness_mm) / (4.0 * diffusivity)
