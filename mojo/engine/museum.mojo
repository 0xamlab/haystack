"""
museum.mojo — Museum Science / Conservation Library. Zero Python imports.

Pure Mojo implementations of museum conservation and collections
management equations including light exposure, climate control,
preservation indices, storage metrics, and valuation.

Public API:
  lux_hours_annual              — LH = lux * hours * days
  uv_exposure                   — UV = uv_ratio * lux (mW/m²)
  relative_humidity_from_temps  — RH ≈ 100 - 5*(Td-Tw)
  moisture_content_equilibrium  — EMC ≈ rh*0.15 + temp*0.01
  time_weighted_preservation_index — TWPI simplified
  light_damage_reciprocity      — Damage ∝ intensity * duration
  climate_stability_score       — Score = 100 - 2*ΔT - ΔRH
  storage_density               — Density = items/area
  collection_growth_rate        — GR = (added-removed)/total * 100
  insurance_value_appreciation  — V = initial*(1+rate)^years
  visitor_density               — VD = visitors/area
  conservation_priority_score   — CPS weighted score
"""
from std.math import sqrt, exp, log, abs as fabs


# ── lux_hours_annual ─────────────────────────────────────────────────────────


def lux_hours_annual(
    lux_level: Float64, hours_per_day: Float64, days_per_year: Float64
) -> Float64:
    """Annual lux-hours = lux * hours_per_day * days_per_year."""
    return lux_level * hours_per_day * days_per_year


# ── uv_exposure ──────────────────────────────────────────────────────────────


def uv_exposure(uv_mw_per_lumen: Float64, lux: Float64) -> Float64:
    """UV exposure = uv_ratio * lux (mW/m²)."""
    return uv_mw_per_lumen * lux


# ── relative_humidity_from_temps ─────────────────────────────────────────────


def relative_humidity_from_temps(
    dry_bulb: Float64, wet_bulb: Float64
) -> Float64:
    """Simplified RH ≈ 100 - 5*(Td - Tw) (%)."""
    return 100.0 - 5.0 * (dry_bulb - wet_bulb)


# ── moisture_content_equilibrium ─────────────────────────────────────────────


def moisture_content_equilibrium(
    rh: Float64, temperature: Float64
) -> Float64:
    """Simplified EMC ≈ rh * 0.15 + temperature * 0.01 (%)."""
    return rh * 0.15 + temperature * 0.01


# ── time_weighted_preservation_index ─────────────────────────────────────────


def time_weighted_preservation_index(
    twpi_ref: Float64, temp: Float64, rh: Float64
) -> Float64:
    """Simplified TWPI ≈ ref * exp(-0.05*(temp-20) - 0.02*(rh-50))."""
    return twpi_ref * exp(-0.05 * (temp - 20.0) - 0.02 * (rh - 50.0))


# ── light_damage_reciprocity ────────────────────────────────────────────────


def light_damage_reciprocity(
    intensity: Float64, duration: Float64
) -> Float64:
    """Light damage proportional to intensity * duration."""
    return intensity * duration


# ── climate_stability_score ──────────────────────────────────────────────────


def climate_stability_score(
    temp_variation: Float64, rh_variation: Float64
) -> Float64:
    """Score = 100 - 2*ΔT - ΔRH (higher = better climate stability)."""
    return 100.0 - 2.0 * temp_variation - rh_variation


# ── storage_density ──────────────────────────────────────────────────────────


def storage_density(items: Float64, floor_area: Float64) -> Float64:
    """Storage density = items / floor_area (items/m²)."""
    if floor_area <= 0.0:
        return 0.0
    return items / floor_area


# ── collection_growth_rate ───────────────────────────────────────────────────


def collection_growth_rate(
    items_added: Float64, items_deaccessioned: Float64, total: Float64
) -> Float64:
    """Growth rate = (added - removed) / total * 100 (%)."""
    if total <= 0.0:
        return 0.0
    return (items_added - items_deaccessioned) / total * 100.0


# ── insurance_value_appreciation ─────────────────────────────────────────────


def insurance_value_appreciation(
    initial_value: Float64, annual_rate: Float64, years: Float64
) -> Float64:
    """V = initial_value * (1 + annual_rate)^years."""
    return initial_value * exp(years * log(1.0 + annual_rate))


# ── visitor_density ──────────────────────────────────────────────────────────


def visitor_density(visitors: Float64, gallery_area: Float64) -> Float64:
    """Visitor density = visitors / gallery_area (people/m²)."""
    if gallery_area <= 0.0:
        return 0.0
    return visitors / gallery_area


# ── conservation_priority_score ──────────────────────────────────────────────


def conservation_priority_score(
    condition: Float64, significance: Float64, risk: Float64
) -> Float64:
    """CPS = condition*0.4 + significance*0.3 + risk*0.3."""
    return condition * 0.4 + significance * 0.3 + risk * 0.3
