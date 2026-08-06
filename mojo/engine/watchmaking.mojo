"""
watchmaking.mojo — Watchmaking / Horology Library.

Provides mechanical watch calculations for gears, escapements, power
reserves, and case specifications.

Public API:
  gear_ratio               — GR = driven / driver
  gear_train_ratio         — Total = pre-computed product of ratios
  beats_per_hour           — BPH = freq * 3600 * 2
  frequency_from_bph       — f = BPH / 7200
  mainspring_torque        — τ = F * R
  power_reserve_hours      — PR = stored / per_hour
  balance_wheel_period     — T = 2π * sqrt(I/k)
  escapement_error_spd     — SPD = (actual-nominal)/nominal * 86400
  jewel_count_minimum      — Min = gear_trains * 2 + 1
  water_resistance_atm     — ATM = meters/10 + 1
  case_diameter_mm         — mm = ligne * 2.2558
  crown_winding_turns      — Turns = length / (π * diameter)
"""
from std.math import sqrt

comptime PI: Float64 = 3.141592653589793


# ── gear_ratio ───────────────────────────────────────────────────────────────


def gear_ratio(driver_teeth: Float64, driven_teeth: Float64) -> Float64:
    """Gear ratio: GR = driven / driver.

    Args:
        driver_teeth: Number of teeth on the driving gear.
        driven_teeth: Number of teeth on the driven gear.

    Returns:
        Gear ratio GR.
    """
    return driven_teeth / driver_teeth


# ── gear_train_ratio ─────────────────────────────────────────────────────────


def gear_train_ratio(ratios_product: Float64) -> Float64:
    """Total gear-train ratio (pass the pre-computed product of individual ratios).

    Args:
        ratios_product: Product of all individual gear ratios.

    Returns:
        Total gear-train ratio.
    """
    return ratios_product


# ── beats_per_hour ───────────────────────────────────────────────────────────


def beats_per_hour(frequency_hz: Float64) -> Float64:
    """Beats per hour: BPH = freq * 3600 * 2 (each cycle = 2 beats).

    Args:
        frequency_hz: Oscillation frequency in Hz.

    Returns:
        Beats per hour.
    """
    return frequency_hz * 3600.0 * 2.0


# ── frequency_from_bph ───────────────────────────────────────────────────────


def frequency_from_bph(bph: Float64) -> Float64:
    """Frequency from BPH: f = BPH / 7200 Hz.

    Args:
        bph: Beats per hour.

    Returns:
        Frequency in Hz.
    """
    return bph / 7200.0


# ── mainspring_torque ────────────────────────────────────────────────────────


def mainspring_torque(force: Float64, radius: Float64) -> Float64:
    """Mainspring torque: τ = F * R.

    Args:
        force: Applied force F (N).
        radius: Barrel radius R (m).

    Returns:
        Torque τ in N·m.
    """
    return force * radius


# ── power_reserve_hours ──────────────────────────────────────────────────────


def power_reserve_hours(energy_stored: Float64, energy_per_hour: Float64) -> Float64:
    """Power reserve: PR = stored / per_hour.

    Args:
        energy_stored: Total energy in mainspring (J or mJ).
        energy_per_hour: Energy consumed per hour (same unit).

    Returns:
        Power reserve in hours.
    """
    return energy_stored / energy_per_hour


# ── balance_wheel_period ─────────────────────────────────────────────────────


def balance_wheel_period(inertia: Float64, spring_constant: Float64) -> Float64:
    """Balance wheel period: T = 2π * sqrt(I / k).

    Args:
        inertia: Moment of inertia I (kg·m²).
        spring_constant: Hairspring stiffness k (N·m/rad).

    Returns:
        Period T in seconds.
    """
    return 2.0 * PI * sqrt(inertia / spring_constant)


# ── escapement_error_spd ─────────────────────────────────────────────────────


def escapement_error_spd(actual_bph: Float64, nominal_bph: Float64) -> Float64:
    """Escapement timing error in seconds per day.

    SPD = (actual - nominal) / nominal * 86400.

    Args:
        actual_bph: Measured beats per hour.
        nominal_bph: Nominal (design) beats per hour.

    Returns:
        Timing error in seconds per day (positive = fast).
    """
    return (actual_bph - nominal_bph) / nominal_bph * 86400.0


# ── jewel_count_minimum ──────────────────────────────────────────────────────


def jewel_count_minimum(gear_trains: Int) -> Int:
    """Simplified minimum jewel count: Min = gear_trains * 2 + 1.

    Args:
        gear_trains: Number of gear trains in the movement.

    Returns:
        Minimum jewel count.
    """
    return gear_trains * 2 + 1


# ── water_resistance_atm ────────────────────────────────────────────────────


def water_resistance_atm(meters: Float64) -> Float64:
    """Water resistance in ATM: ATM = meters / 10 + 1.

    Args:
        meters: Depth rating in meters.

    Returns:
        Pressure rating in ATM.
    """
    return meters / 10.0 + 1.0


# ── case_diameter_mm ─────────────────────────────────────────────────────────


def case_diameter_mm(movement_diameter_ligne: Float64) -> Float64:
    """Convert movement diameter from lignes to mm: mm = ligne * 2.2558.

    Args:
        movement_diameter_ligne: Movement diameter in lignes.

    Returns:
        Approximate case diameter in mm.
    """
    return movement_diameter_ligne * 2.2558


# ── crown_winding_turns ──────────────────────────────────────────────────────


def crown_winding_turns(
    mainspring_length: Float64, barrel_diameter: Float64
) -> Float64:
    """Crown winding turns: Turns = length / (π * diameter).

    Args:
        mainspring_length: Mainspring strip length (mm).
        barrel_diameter: Barrel inner diameter (mm).

    Returns:
        Approximate number of winding turns.
    """
    return mainspring_length / (PI * barrel_diameter)
