"""
drones.mojo — Drone / UAV Engineering Library. Zero Python imports.

Provides thrust, hover power, flight time, range, and sensor calculations.

Public API:
  thrust_to_weight_ratio        — TWR = thrust/weight
  hover_power                   — P = W^1.5 / sqrt(2*ρ*A)
  flight_time_minutes           — t = (battery/power)*60
  max_range                     — R = speed * time/60
  payload_capacity              — PC = MTOW - empty - battery
  disk_loading                  — DL = W/A
  propeller_tip_speed           — v = π*D*RPM/60
  advance_ratio                 — J = V/(n*D)
  battery_energy_density        — ED = E/m
  communication_range_los       — R = sqrt(2*Re*h + h²)
  gsd_from_altitude             — GSD = (alt*sw)/(fl*iw)*1000
  endurance_factor              — EF = (cap*volt*eff/power)*60
"""
from std.math import sqrt, abs as fabs

comptime PI: Float64 = 3.141592653589793


# ── thrust_to_weight_ratio ───────────────────────────────────────────────────


def thrust_to_weight_ratio(total_thrust: Float64, weight: Float64) -> Float64:
    """Thrust-to-weight ratio: TWR = thrust / weight.

    Args:
        total_thrust: Total thrust produced (N).
        weight: Total weight (N).

    Returns:
        Dimensionless TWR.
    """
    if weight == 0.0:
        return 0.0
    return total_thrust / weight


# ── hover_power ──────────────────────────────────────────────────────────────


def hover_power(
    weight: Float64, disk_area: Float64, air_density: Float64
) -> Float64:
    """Induced hover power: P = W^1.5 / sqrt(2 * ρ * A).

    Args:
        weight: Aircraft weight (N).
        disk_area: Total rotor disk area (m²).
        air_density: Air density (kg/m³).

    Returns:
        Hover power (W).
    """
    if disk_area <= 0.0 or air_density <= 0.0:
        return 0.0
    return (weight * sqrt(weight)) / sqrt(2.0 * air_density * disk_area)


# ── flight_time_minutes ─────────────────────────────────────────────────────


def flight_time_minutes(battery_wh: Float64, avg_power_w: Float64) -> Float64:
    """Estimated flight time: t = (battery_wh / avg_power_w) * 60.

    Args:
        battery_wh: Battery energy capacity (Wh).
        avg_power_w: Average power consumption (W).

    Returns:
        Flight time (minutes).
    """
    if avg_power_w <= 0.0:
        return 0.0
    return (battery_wh / avg_power_w) * 60.0


# ── max_range ────────────────────────────────────────────────────────────────


def max_range(speed: Float64, flight_time_min: Float64) -> Float64:
    """Max range: R = speed * time / 60.

    Args:
        speed: Cruise speed (km/h).
        flight_time_min: Flight time (minutes).

    Returns:
        Range (km).
    """
    return speed * flight_time_min / 60.0


# ── payload_capacity ─────────────────────────────────────────────────────────


def payload_capacity(
    max_takeoff_weight: Float64,
    empty_weight: Float64,
    battery_weight: Float64,
) -> Float64:
    """Payload capacity: PC = MTOW - empty - battery.

    Args:
        max_takeoff_weight: Max takeoff weight (kg).
        empty_weight: Empty weight (kg).
        battery_weight: Battery weight (kg).

    Returns:
        Payload capacity (kg).
    """
    return max_takeoff_weight - empty_weight - battery_weight


# ── disk_loading ─────────────────────────────────────────────────────────────


def disk_loading(weight: Float64, disk_area: Float64) -> Float64:
    """Disk loading: DL = W / A.

    Args:
        weight: Weight (N).
        disk_area: Total rotor disk area (m²).

    Returns:
        Disk loading (N/m²).
    """
    if disk_area <= 0.0:
        return 0.0
    return weight / disk_area


# ── propeller_tip_speed ──────────────────────────────────────────────────────


def propeller_tip_speed(rpm: Float64, diameter: Float64) -> Float64:
    """Propeller tip speed: v = π * D * RPM / 60.

    Args:
        rpm: Revolutions per minute.
        diameter: Propeller diameter (m).

    Returns:
        Tip speed (m/s).
    """
    return PI * diameter * rpm / 60.0


# ── advance_ratio ────────────────────────────────────────────────────────────


def advance_ratio(
    velocity: Float64, rpm: Float64, diameter: Float64
) -> Float64:
    """Advance ratio: J = V / (n * D), where n = RPM / 60.

    Args:
        velocity: Forward speed (m/s).
        rpm: Revolutions per minute.
        diameter: Propeller diameter (m).

    Returns:
        Advance ratio (dimensionless).
    """
    var n = rpm / 60.0
    if n * diameter == 0.0:
        return 0.0
    return velocity / (n * diameter)


# ── battery_energy_density ───────────────────────────────────────────────────


def battery_energy_density(energy_wh: Float64, mass_kg: Float64) -> Float64:
    """Battery energy density: ED = E / m.

    Args:
        energy_wh: Battery energy (Wh).
        mass_kg: Battery mass (kg).

    Returns:
        Energy density (Wh/kg).
    """
    if mass_kg <= 0.0:
        return 0.0
    return energy_wh / mass_kg


# ── communication_range_los ──────────────────────────────────────────────────


def communication_range_los(
    altitude: Float64, earth_radius: Float64
) -> Float64:
    """Line-of-sight range: R = sqrt(2*Re*h + h²).

    Args:
        altitude: Altitude above ground (m).
        earth_radius: Earth radius (m), typically 6371000.

    Returns:
        Line-of-sight range (m).
    """
    if altitude < 0.0 or earth_radius <= 0.0:
        return 0.0
    return sqrt(2.0 * earth_radius * altitude + altitude * altitude)


# ── gsd_from_altitude ────────────────────────────────────────────────────────


def gsd_from_altitude(
    focal_length_mm: Float64,
    sensor_width_mm: Float64,
    image_width_px: Float64,
    altitude_m: Float64,
) -> Float64:
    """Ground sampling distance: GSD = (alt * sw) / (fl * iw) * 1000 (cm/px).

    Args:
        focal_length_mm: Camera focal length (mm).
        sensor_width_mm: Sensor width (mm).
        image_width_px: Image width (pixels).
        altitude_m: Altitude (m).

    Returns:
        GSD (cm/px).
    """
    var denom = focal_length_mm * image_width_px
    if denom == 0.0:
        return 0.0
    return (altitude_m * sensor_width_mm) / denom * 1000.0


# ── endurance_factor ─────────────────────────────────────────────────────────


def endurance_factor(
    battery_capacity_ah: Float64,
    voltage: Float64,
    efficiency: Float64,
    power_w: Float64,
) -> Float64:
    """Endurance factor: EF = (cap * volt * eff / power) * 60 (min).

    Args:
        battery_capacity_ah: Battery capacity (Ah).
        voltage: Nominal voltage (V).
        efficiency: System efficiency (0-1).
        power_w: Power consumption (W).

    Returns:
        Endurance (minutes).
    """
    if power_w <= 0.0:
        return 0.0
    return (battery_capacity_ah * voltage * efficiency / power_w) * 60.0
