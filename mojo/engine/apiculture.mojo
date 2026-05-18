"""
apiculture.mojo — Apiculture (Beekeeping) Science Library. Zero Python imports.

Pure Mojo implementations of fundamental beekeeping and apiculture
science equations including honey yield, colony strength, varroa
monitoring, feeding, foraging, brood viability, and pollination value.

Public API:
  honey_yield_per_hive        — total honey / n_hives
  colony_strength_estimate    — frames * bees_per_frame
  varroa_infestation_rate     — mites/bees * 100
  sugar_syrup_ratio           — sugar/(sugar+water)
  foraging_range_area         — π*r² (km²)
  nectar_to_honey_ratio       — nectar/4 (4:1)
  brood_viability             — hatched/total * 100
  winter_feed_requirement     — months*consumption - (weight-15)
  queen_laying_rate           — identity (eggs/day)
  pollination_value           — crop_value * increase/100
  hive_density_per_hectare    — hives/area
  overwintering_survival_rate — survived/total * 100
"""
from std.math import sqrt, abs as fabs


# ── honey_yield_per_hive ─────────────────────────────────────────────────────


fn honey_yield_per_hive(total_honey_kg: Float64, n_hives: Float64) -> Float64:
    """Yield per hive Y = total_honey_kg / n_hives."""
    return total_honey_kg / n_hives


# ── colony_strength_estimate ─────────────────────────────────────────────────


fn colony_strength_estimate(frames_of_bees: Float64, bees_per_frame: Float64) -> Float64:
    """Population estimate Pop = frames * bees_per_frame."""
    return frames_of_bees * bees_per_frame


# ── varroa_infestation_rate ──────────────────────────────────────────────────


fn varroa_infestation_rate(mites_counted: Float64, bees_sampled: Float64) -> Float64:
    """Infestation rate = mites / bees * 100 (%)."""
    return mites_counted / bees_sampled * 100.0


# ── sugar_syrup_ratio ────────────────────────────────────────────────────────


fn sugar_syrup_ratio(sugar_kg: Float64, water_kg: Float64) -> Float64:
    """Ratio = sugar / (sugar + water) (fraction 0-1)."""
    return sugar_kg / (sugar_kg + water_kg)


# ── foraging_range_area ──────────────────────────────────────────────────────


fn foraging_range_area(radius_km: Float64) -> Float64:
    """Foraging area A = π * r² (km²)."""
    return 3.141592653589793 * radius_km * radius_km


# ── nectar_to_honey_ratio ───────────────────────────────────────────────────


fn nectar_to_honey_ratio(nectar_kg: Float64) -> Float64:
    """Honey ≈ nectar / 4 (typical 4:1 evaporation ratio)."""
    return nectar_kg / 4.0


# ── brood_viability ──────────────────────────────────────────────────────────


fn brood_viability(hatched_cells: Float64, total_cells: Float64) -> Float64:
    """Viability V = hatched / total * 100 (%)."""
    return hatched_cells / total_cells * 100.0


# ── winter_feed_requirement ──────────────────────────────────────────────────


fn winter_feed_requirement(
    colony_weight_kg: Float64, months: Float64, consumption_per_month: Float64,
) -> Float64:
    """Feed = months * consumption - (weight - 15). Simplified estimate (kg)."""
    return months * consumption_per_month - (colony_weight_kg - 15.0)


# ── queen_laying_rate ────────────────────────────────────────────────────────


fn queen_laying_rate(eggs_per_day: Float64) -> Float64:
    """Returns laying rate directly (eggs/day, up to ~2000)."""
    return eggs_per_day


# ── pollination_value ────────────────────────────────────────────────────────


fn pollination_value(crop_yield_increase_pct: Float64, crop_value: Float64) -> Float64:
    """Value = crop_value * increase_pct / 100."""
    return crop_value * crop_yield_increase_pct / 100.0


# ── hive_density_per_hectare ─────────────────────────────────────────────────


fn hive_density_per_hectare(n_hives: Float64, area_ha: Float64) -> Float64:
    """Density = hives / area (hives/ha)."""
    return n_hives / area_ha


# ── overwintering_survival_rate ──────────────────────────────────────────────


fn overwintering_survival_rate(survived: Float64, total: Float64) -> Float64:
    """Survival rate SR = survived / total * 100 (%)."""
    return survived / total * 100.0
