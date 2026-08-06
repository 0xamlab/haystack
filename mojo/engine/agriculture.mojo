"""
agriculture.mojo — Agricultural Science Library. Zero Python imports.

Pure Mojo implementations of fundamental agricultural science equations
including crop water needs, fertilizer rates, seed rates, harvest index,
soil lime requirements, and radiation use efficiency.

Public API:
  growing_degree_days              — GDD accumulation
  crop_water_need                  — ETc = ET0 * Kc
  irrigation_efficiency            — η = consumed / delivered
  fertilizer_rate                  — nutrient application rate
  seed_rate                        — seeding rate from population targets
  harvest_index                    — HI = grain / biomass
  yield_per_hectare                — Y = yield / area
  soil_ph_lime_requirement         — lime needed for target pH
  water_use_efficiency             — WUE = yield / water
  photosynthetically_active_radiation — PAR ≈ 0.48 * solar
  leaf_area_index                  — LAI = leaf / ground
  nitrogen_use_efficiency          — NUE = Δyield / N
"""
from std.math import abs as fabs


# ── growing_degree_days ──────────────────────────────────────────────────────


def growing_degree_days(
    t_max: Float64, t_min: Float64, t_base: Float64
) -> Float64:
    """GDD = max(0, (t_max + t_min) / 2 - t_base)."""
    var avg = (t_max + t_min) / 2.0 - t_base
    if avg < 0.0:
        return 0.0
    return avg


# ── crop_water_need ──────────────────────────────────────────────────────────


def crop_water_need(et0: Float64, kc: Float64) -> Float64:
    """ETc = ET0 * Kc (crop evapotranspiration)."""
    return et0 * kc


# ── irrigation_efficiency ────────────────────────────────────────────────────


def irrigation_efficiency(
    water_delivered: Float64, water_consumed: Float64
) -> Float64:
    """η = water_consumed / water_delivered."""
    if water_delivered == 0.0:
        return 0.0
    return water_consumed / water_delivered


# ── fertilizer_rate ──────────────────────────────────────────────────────────


def fertilizer_rate(
    target_yield: Float64,
    nutrient_content: Float64,
    soil_nutrient: Float64,
    efficiency: Float64,
) -> Float64:
    """Rate = (target_yield * nutrient_content - soil_nutrient) / efficiency."""
    if efficiency == 0.0:
        return 0.0
    return (target_yield * nutrient_content - soil_nutrient) / efficiency


# ── seed_rate ────────────────────────────────────────────────────────────────


def seed_rate(
    target_population: Float64,
    germination_rate: Float64,
    purity: Float64,
) -> Float64:
    """SR = target_population / (germination_rate * purity)."""
    var denom = germination_rate * purity
    if denom == 0.0:
        return 0.0
    return target_population / denom


# ── harvest_index ────────────────────────────────────────────────────────────


def harvest_index(grain_weight: Float64, total_biomass: Float64) -> Float64:
    """HI = grain_weight / total_biomass."""
    if total_biomass == 0.0:
        return 0.0
    return grain_weight / total_biomass


# ── yield_per_hectare ────────────────────────────────────────────────────────


def yield_per_hectare(total_yield_kg: Float64, area_ha: Float64) -> Float64:
    """Y = total_yield_kg / area_ha."""
    if area_ha == 0.0:
        return 0.0
    return total_yield_kg / area_ha


# ── soil_ph_lime_requirement ─────────────────────────────────────────────────


def soil_ph_lime_requirement(
    current_ph: Float64, target_ph: Float64, buffer_capacity: Float64
) -> Float64:
    """LR = (target_ph - current_ph) * buffer_capacity."""
    return (target_ph - current_ph) * buffer_capacity


# ── water_use_efficiency ─────────────────────────────────────────────────────


def water_use_efficiency(yield_kg: Float64, water_mm: Float64) -> Float64:
    """WUE = yield_kg / water_mm."""
    if water_mm == 0.0:
        return 0.0
    return yield_kg / water_mm


# ── photosynthetically_active_radiation ──────────────────────────────────────


def photosynthetically_active_radiation(
    solar_radiation: Float64,
) -> Float64:
    """PAR ≈ 0.48 * solar_radiation."""
    return 0.48 * solar_radiation


# ── leaf_area_index ──────────────────────────────────────────────────────────


def leaf_area_index(leaf_area: Float64, ground_area: Float64) -> Float64:
    """LAI = leaf_area / ground_area."""
    if ground_area == 0.0:
        return 0.0
    return leaf_area / ground_area


# ── nitrogen_use_efficiency ──────────────────────────────────────────────────


def nitrogen_use_efficiency(
    yield_increase: Float64, n_applied: Float64
) -> Float64:
    """NUE = yield_increase / n_applied."""
    if n_applied == 0.0:
        return 0.0
    return yield_increase / n_applied
