"""
perfumery.mojo — Perfumery / Fragrance Science Library. Zero Python imports.

Pure Mojo implementations for fragrance formulation, concentration
calculations, note durations, accords, and cost analysis.

Public API:
  concentration_parfum       — C = oil/total * 100
  dilution_ratio             — Ratio = concentrate/(concentrate+diluent)
  evaporation_rate_relative  — RER = substance/reference
  top_note_duration          — Returns 30.0 minutes (typical)
  middle_note_duration       — Returns 240.0 minutes (4 hours)
  base_note_duration         — Returns 1440.0 minutes (24 hours)
  triangle_accord_balance    — Returns min(top,mid,base) if all > 15%
  tenacity_hours             — hours * (1 - final/initial)
  sillage_distance           — concentration * volatility_factor
  cost_per_ml                — cost / volume
  fragrance_strength_scale   — 0-4 scale based on concentration %
  ingredient_proportion      — ingredient/total * 100
"""


# ── concentration_parfum ─────────────────────────────────────────────────────


fn concentration_parfum(
    fragrance_oil_ml: Float64, total_ml: Float64
) -> Float64:
    """Fragrance concentration C = oil/total * 100 (percent)."""
    return fragrance_oil_ml / total_ml * 100.0


# ── dilution_ratio ───────────────────────────────────────────────────────────


fn dilution_ratio(
    concentrate_ml: Float64, diluent_ml: Float64
) -> Float64:
    """Dilution ratio = concentrate / (concentrate + diluent)."""
    return concentrate_ml / (concentrate_ml + diluent_ml)


# ── evaporation_rate_relative ────────────────────────────────────────────────


fn evaporation_rate_relative(
    substance_rate: Float64, reference_rate: Float64
) -> Float64:
    """Relative evaporation rate RER = substance / reference."""
    return substance_rate / reference_rate


# ── top_note_duration ────────────────────────────────────────────────────────


fn top_note_duration() -> Float64:
    """Typical top note duration in minutes (~30 min)."""
    return 30.0


# ── middle_note_duration ─────────────────────────────────────────────────────


fn middle_note_duration() -> Float64:
    """Typical middle (heart) note duration in minutes (~4 hours)."""
    return 240.0


# ── base_note_duration ───────────────────────────────────────────────────────


fn base_note_duration() -> Float64:
    """Typical base note duration in minutes (~24 hours)."""
    return 1440.0


# ── triangle_accord_balance ──────────────────────────────────────────────────


fn triangle_accord_balance(
    top_pct: Float64, mid_pct: Float64, base_pct: Float64
) -> Float64:
    """Triangle accord balance check.
    Returns min(top, mid, base) if all > 15%, else 0.0 (unbalanced).
    """
    if top_pct <= 15.0 or mid_pct <= 15.0 or base_pct <= 15.0:
        return 0.0
    var m = top_pct
    if mid_pct < m:
        m = mid_pct
    if base_pct < m:
        m = base_pct
    return m


# ── tenacity_hours ───────────────────────────────────────────────────────────


fn tenacity_hours(
    initial_intensity: Float64,
    final_intensity: Float64,
    hours: Float64,
) -> Float64:
    """Tenacity = hours * (1 - final/initial)."""
    return hours * (1.0 - final_intensity / initial_intensity)


# ── sillage_distance ────────────────────────────────────────────────────────


fn sillage_distance(
    concentration: Float64, volatility_factor: Float64
) -> Float64:
    """Sillage (projection) distance ≈ concentration * volatility (a.u.)."""
    return concentration * volatility_factor


# ── cost_per_ml ──────────────────────────────────────────────────────────────


fn cost_per_ml(total_cost: Float64, volume_ml: Float64) -> Float64:
    """Cost per milliliter CPM = cost / volume."""
    return total_cost / volume_ml


# ── fragrance_strength_scale ─────────────────────────────────────────────────


fn fragrance_strength_scale(concentration_pct: Float64) -> Int:
    """Fragrance strength on 0-4 scale based on concentration %.
    0 = none (0%), 1 = cologne (<5%), 2 = EDT (5-15%),
    3 = EDP (15-20%), 4 = parfum (>20%).
    """
    if concentration_pct <= 0.0:
        return 0
    if concentration_pct < 5.0:
        return 1
    if concentration_pct < 15.0:
        return 2
    if concentration_pct <= 20.0:
        return 3
    return 4


# ── ingredient_proportion ────────────────────────────────────────────────────


fn ingredient_proportion(
    ingredient_ml: Float64, total_formula_ml: Float64
) -> Float64:
    """Ingredient proportion = ingredient/total * 100 (percent)."""
    return ingredient_ml / total_formula_ml * 100.0
