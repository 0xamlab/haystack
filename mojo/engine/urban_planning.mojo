"""
urban_planning.mojo — Urban Planning Library. Zero Python imports.

Pure Mojo implementations of urban planning metrics including
density, zoning ratios, walkability, traffic, housing, and
infrastructure calculations.

Public API:
  population_density             — PD = pop / area
  floor_area_ratio               — FAR = floor_area / plot_area
  lot_coverage                   — LC = footprint / lot * 100
  green_space_ratio              — GSR = green / total * 100
  walk_score_distance_decay      — score = max(0, 1 - d/d_max)
  vehicle_miles_traveled         — VMT = trips * distance
  parking_requirement            — spaces = units * ratio
  traffic_level_of_service       — V/C ratio
  housing_affordability_ratio    — HAR = price / income
  jobs_housing_balance           — JHB = jobs / housing
  infrastructure_cost_per_unit   — cost / units_served
  impervious_surface_ratio       — ISR = impervious / total * 100
"""
from std.math import sqrt, exp, log, abs as fabs


# ── population_density ───────────────────────────────────────────────────────


fn population_density(population: Float64, area_sq_km: Float64) -> Float64:
    """PD = population / area (people per sq km)."""
    return population / area_sq_km


# ── floor_area_ratio ─────────────────────────────────────────────────────────


fn floor_area_ratio(total_floor_area: Float64, plot_area: Float64) -> Float64:
    """FAR = total_floor_area / plot_area."""
    return total_floor_area / plot_area


# ── lot_coverage ─────────────────────────────────────────────────────────────


fn lot_coverage(building_footprint: Float64, lot_area: Float64) -> Float64:
    """LC = (building_footprint / lot_area) * 100."""
    return building_footprint / lot_area * 100.0


# ── green_space_ratio ────────────────────────────────────────────────────────


fn green_space_ratio(green_area: Float64, total_area: Float64) -> Float64:
    """GSR = (green_area / total_area) * 100."""
    return green_area / total_area * 100.0


# ── walk_score_distance_decay ────────────────────────────────────────────────


fn walk_score_distance_decay(distance_m: Float64, max_distance: Float64) -> Float64:
    """score = max(0, 1 - distance / max_distance)."""
    var score = 1.0 - distance_m / max_distance
    if score < 0.0:
        return 0.0
    return score


# ── vehicle_miles_traveled ───────────────────────────────────────────────────


fn vehicle_miles_traveled(trips: Float64, avg_distance: Float64) -> Float64:
    """VMT = trips * avg_distance."""
    return trips * avg_distance


# ── parking_requirement ──────────────────────────────────────────────────────


fn parking_requirement(units: Float64, spaces_per_unit: Float64) -> Float64:
    """Spaces = units * spaces_per_unit."""
    return units * spaces_per_unit


# ── traffic_level_of_service ─────────────────────────────────────────────────


fn traffic_level_of_service(volume: Float64, capacity: Float64) -> Float64:
    """V/C ratio (volume to capacity)."""
    return volume / capacity


# ── housing_affordability_ratio ──────────────────────────────────────────────


fn housing_affordability_ratio(median_price: Float64, median_income: Float64) -> Float64:
    """HAR = median_price / median_income."""
    return median_price / median_income


# ── jobs_housing_balance ─────────────────────────────────────────────────────


fn jobs_housing_balance(jobs: Float64, housing_units: Float64) -> Float64:
    """JHB = jobs / housing_units."""
    return jobs / housing_units


# ── infrastructure_cost_per_unit ─────────────────────────────────────────────


fn infrastructure_cost_per_unit(total_cost: Float64, units_served: Float64) -> Float64:
    """Cost per unit = total_cost / units_served."""
    return total_cost / units_served


# ── impervious_surface_ratio ─────────────────────────────────────────────────


fn impervious_surface_ratio(impervious_area: Float64, total_area: Float64) -> Float64:
    """ISR = (impervious_area / total_area) * 100."""
    return impervious_area / total_area * 100.0
