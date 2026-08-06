"""
fire_safety.mojo — Fire Safety Engineering Library. Zero Python imports.

Pure Mojo implementations of fundamental fire safety engineering
calculations including fire load density, heat release rate, flashover,
sprinkler activation, smoke layer, evacuation, and ventilation factors.

Public API:
  fire_load_density           — fire load per floor area (MJ/m²)
  heat_release_rate           — HRR from mass loss and heat of combustion
  flashover_mfo               — Thomas flashover correlation
  sprinkler_activation_time   — simplified sprinkler activation
  smoke_layer_height          — simplified smoke layer descent
  evacuation_time             — time to evacuate population
  safe_egress_time            — RSET calculation
  fire_resistance_rating      — FRR from thickness and material
  ventilation_factor          — Fv = Ao * sqrt(Ho)
  fire_severity               — severity = load / Fv
  co_concentration_danger     — CO danger level classification
  occupant_load               — occupant load from area and factor
"""
from std.math import sqrt, abs as fabs


# ── fire_load_density ────────────────────────────────────────────────────────


def fire_load_density(total_fire_load_mj: Float64, floor_area: Float64) -> Float64:
    """FLD = total_fire_load / floor_area  (MJ/m²)."""
    if floor_area == 0.0:
        return 0.0
    return total_fire_load_mj / floor_area


# ── heat_release_rate ────────────────────────────────────────────────────────


def heat_release_rate(mass_loss_rate: Float64, heat_of_combustion: Float64) -> Float64:
    """HRR = mass_loss_rate * heat_of_combustion  (kW)."""
    return mass_loss_rate * heat_of_combustion


# ── flashover_mfo ────────────────────────────────────────────────────────────


def flashover_mfo(
    area_vent: Float64, height_vent: Float64, area_total: Float64
) -> Float64:
    """Q_fo = 750*Av*sqrt(Hv) + 378*At  (Thomas correlation, simplified)."""
    return 750.0 * area_vent * sqrt(height_vent) + 378.0 * area_total


# ── sprinkler_activation_time ────────────────────────────────────────────────


def sprinkler_activation_time(
    rti: Float64, gas_temp: Float64, ambient_temp: Float64, velocity: Float64
) -> Float64:
    """Simplified: t ≈ RTI / sqrt(v).  (ignores temperature ratio for simplicity)."""
    if velocity <= 0.0:
        return 0.0
    return rti / sqrt(velocity)


# ── smoke_layer_height ───────────────────────────────────────────────────────


def smoke_layer_height(
    ceiling_height: Float64, time_s: Float64, hrr: Float64
) -> Float64:
    """Simplified: z ≈ H - 0.1 * sqrt(HRR) * sqrt(t) / H."""
    if ceiling_height == 0.0:
        return 0.0
    var descent = 0.1 * sqrt(hrr) * sqrt(time_s) / ceiling_height
    var z = ceiling_height - descent
    if z < 0.0:
        return 0.0
    return z


# ── evacuation_time ──────────────────────────────────────────────────────────


def evacuation_time(
    population: Float64, exit_width: Float64, flow_rate: Float64
) -> Float64:
    """t = population / (exit_width * flow_rate)."""
    var denom = exit_width * flow_rate
    if denom == 0.0:
        return 0.0
    return population / denom


# ── safe_egress_time ─────────────────────────────────────────────────────────


def safe_egress_time(
    detection: Float64, alarm: Float64, pre_movement: Float64, travel: Float64
) -> Float64:
    """RSET = detection + alarm + pre_movement + travel."""
    return detection + alarm + pre_movement + travel


# ── fire_resistance_rating ───────────────────────────────────────────────────


def fire_resistance_rating(thickness_mm: Float64, material_factor: Float64) -> Float64:
    """FRR = thickness * material_factor  (minutes, simplified)."""
    return thickness_mm * material_factor


# ── ventilation_factor ───────────────────────────────────────────────────────


def ventilation_factor(area_opening: Float64, height_opening: Float64) -> Float64:
    """Fv = Ao * sqrt(Ho)."""
    return area_opening * sqrt(height_opening)


# ── fire_severity ────────────────────────────────────────────────────────────


def fire_severity(fire_load: Float64, vent_factor: Float64) -> Float64:
    """Severity = fire_load / ventilation_factor  (simplified)."""
    if vent_factor == 0.0:
        return 0.0
    return fire_load / vent_factor


# ── co_concentration_danger ──────────────────────────────────────────────────


def co_concentration_danger(ppm: Float64) -> Int:
    """Returns danger level: 0=safe(<35), 1=warning(35-200), 2=danger(>200)."""
    if ppm > 200.0:
        return 2
    if ppm >= 35.0:
        return 1
    return 0


# ── occupant_load ────────────────────────────────────────────────────────────


def occupant_load(floor_area: Float64, occupant_factor: Float64) -> Float64:
    """OL = floor_area / occupant_factor."""
    if occupant_factor == 0.0:
        return 0.0
    return floor_area / occupant_factor
