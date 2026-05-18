"""
soil_science.mojo — Soil Science Library. Zero Python imports.

Pure Mojo implementations of fundamental soil science equations including
texture validation, bulk/particle density, porosity, water content,
field capacity, wilting point, CEC, organic carbon, and infiltration.

Public API:
  soil_texture_sand_silt_clay     — Validate sum ≈ 100
  bulk_density                    — ρb = mass/volume (g/cm³)
  particle_density_typical        — Returns 2.65 g/cm³ (quartz standard)
  total_porosity                  — n = 1 - ρb/ρs
  volumetric_water_content        — θ = Vw/Vt
  gravimetric_water_content       — w = Mw/Ms
  field_capacity_estimate         — FC ≈ 0.15 + 0.005*clay%
  wilting_point_estimate          — WP ≈ 0.04 + 0.003*clay%
  available_water                 — AW = (FC-WP)*depth/100
  cation_exchange_capacity_estimate — CEC ≈ 0.5*clay + 2.0*OM
  soil_organic_carbon             — SOC ≈ OM / 1.724
  infiltration_rate_horton        — f = fc + (f0-fc)*exp(-k*t)
"""
from std.math import abs as fabs, exp


# ── soil_texture_sand_silt_clay ──────────────────────────────────────────────


fn soil_texture_sand_silt_clay(
    sand: Float64, silt: Float64, clay: Float64
) -> Bool:
    """Validate that sand + silt + clay ≈ 100 (within ±1.0 tolerance)."""
    var total = sand + silt + clay
    return fabs(total - 100.0) <= 1.0


# ── bulk_density ─────────────────────────────────────────────────────────────


fn bulk_density(dry_mass: Float64, total_volume: Float64) -> Float64:
    """ρb = dry_mass / total_volume (g/cm³)."""
    return dry_mass / total_volume


# ── particle_density_typical ─────────────────────────────────────────────────


fn particle_density_typical() -> Float64:
    """Returns 2.65 g/cm³ — typical particle density for quartz/mineral soils."""
    return 2.65


# ── total_porosity ───────────────────────────────────────────────────────────


fn total_porosity(bulk_density_val: Float64, particle_density_val: Float64) -> Float64:
    """n = 1 - ρb/ρs (dimensionless, 0-1 range)."""
    return 1.0 - bulk_density_val / particle_density_val


# ── volumetric_water_content ─────────────────────────────────────────────────


fn volumetric_water_content(water_volume: Float64, total_volume: Float64) -> Float64:
    """θ = Vw / Vt (dimensionless, 0-1 range)."""
    return water_volume / total_volume


# ── gravimetric_water_content ────────────────────────────────────────────────


fn gravimetric_water_content(water_mass: Float64, dry_soil_mass: Float64) -> Float64:
    """w = Mw / Ms (dimensionless)."""
    return water_mass / dry_soil_mass


# ── field_capacity_estimate ──────────────────────────────────────────────────


fn field_capacity_estimate(clay_pct: Float64) -> Float64:
    """FC ≈ 0.15 + 0.005 * clay% (simplified pedotransfer function)."""
    return 0.15 + 0.005 * clay_pct


# ── wilting_point_estimate ───────────────────────────────────────────────────


fn wilting_point_estimate(clay_pct: Float64) -> Float64:
    """WP ≈ 0.04 + 0.003 * clay% (simplified pedotransfer function)."""
    return 0.04 + 0.003 * clay_pct


# ── available_water ──────────────────────────────────────────────────────────


fn available_water(
    field_capacity: Float64, wilting_point: Float64, root_depth_cm: Float64
) -> Float64:
    """AW = (FC - WP) * depth / 100 (cm of available water)."""
    return (field_capacity - wilting_point) * root_depth_cm / 100.0


# ── cation_exchange_capacity_estimate ────────────────────────────────────────


fn cation_exchange_capacity_estimate(clay_pct: Float64, om_pct: Float64) -> Float64:
    """CEC ≈ 0.5*clay% + 2.0*OM% (meq/100g, simplified)."""
    return 0.5 * clay_pct + 2.0 * om_pct


# ── soil_organic_carbon ──────────────────────────────────────────────────────


fn soil_organic_carbon(om_pct: Float64) -> Float64:
    """SOC ≈ OM / 1.724 (Van Bemmelen factor)."""
    return om_pct / 1.724


# ── infiltration_rate_horton ─────────────────────────────────────────────────


fn infiltration_rate_horton(
    f0: Float64, fc: Float64, k: Float64, t: Float64
) -> Float64:
    """Horton's infiltration: f = fc + (f0 - fc) * exp(-k*t).

    f0 = initial infiltration rate (mm/hr).
    fc = steady-state infiltration rate (mm/hr).
    k  = decay constant (1/hr).
    t  = time (hr).
    """
    return fc + (f0 - fc) * exp(-k * t)
