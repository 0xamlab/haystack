"""
battery.mojo — Battery Technology Library. Zero Python imports.

Pure Mojo implementations of fundamental battery science equations
including state of charge, depth of discharge, coulombic efficiency,
energy/power density, C-rate, Peukert capacity, cycle life degradation,
internal resistance, and battery pack calculations.

Public API:
  state_of_charge               — SOC = current/max * 100
  depth_of_discharge            — DOD = 100 - SOC
  coulombic_efficiency          — η = Qdis/Qchg * 100
  energy_density                — ED = E/m (Wh/kg)
  power_density                 — PD = P/m (W/kg)
  c_rate                        — C = I/Q (1/hours)
  discharge_time                — t = 1/C (hours)
  peukert_capacity              — Peukert's law simplified
  cycle_life_degradation        — capacity after N cycles
  internal_resistance_from_voltage — R = (OCV-V)/I
  battery_pack_voltage          — V = n * Vcell
  battery_pack_capacity         — C = n * Ccell (Ah)
"""
from std.math import sqrt, exp, log, abs as fabs


# ── state_of_charge ──────────────────────────────────────────────────────────


def state_of_charge(current_capacity: Float64, max_capacity: Float64) -> Float64:
    """SOC = current_capacity / max_capacity * 100 (%)."""
    if max_capacity <= 0.0:
        return 0.0
    return current_capacity / max_capacity * 100.0


# ── depth_of_discharge ───────────────────────────────────────────────────────


def depth_of_discharge(soc: Float64) -> Float64:
    """DOD = 100 - SOC (%)."""
    return 100.0 - soc


# ── coulombic_efficiency ─────────────────────────────────────────────────────


def coulombic_efficiency(discharge_ah: Float64, charge_ah: Float64) -> Float64:
    """η = Qdis / Qchg * 100 (%)."""
    if charge_ah <= 0.0:
        return 0.0
    return discharge_ah / charge_ah * 100.0


# ── energy_density ───────────────────────────────────────────────────────────


def energy_density(energy_wh: Float64, mass_kg: Float64) -> Float64:
    """Energy density = E / m (Wh/kg)."""
    if mass_kg <= 0.0:
        return 0.0
    return energy_wh / mass_kg


# ── power_density ────────────────────────────────────────────────────────────


def power_density(power_w: Float64, mass_kg: Float64) -> Float64:
    """Power density = P / m (W/kg)."""
    if mass_kg <= 0.0:
        return 0.0
    return power_w / mass_kg


# ── c_rate ───────────────────────────────────────────────────────────────────


def c_rate(current: Float64, capacity: Float64) -> Float64:
    """C-rate = I / Q (1/hours)."""
    if capacity <= 0.0:
        return 0.0
    return current / capacity


# ── discharge_time ───────────────────────────────────────────────────────────


def discharge_time(capacity: Float64, current: Float64) -> Float64:
    """Discharge time t = capacity / current (hours)."""
    if current <= 0.0:
        return 0.0
    return capacity / current


# ── peukert_capacity ─────────────────────────────────────────────────────────


def peukert_capacity(
    rated_capacity: Float64,
    rated_hours: Float64,
    actual_rate: Float64,
    k: Float64,
) -> Float64:
    """Peukert capacity: C = rated * (rated_hours * actual_rate / rated)^(k-1).

    Simplified Peukert's law for actual discharge rate.
    """
    if rated_capacity <= 0.0 or rated_hours <= 0.0:
        return 0.0
    var ratio = rated_hours * actual_rate / rated_capacity
    if ratio <= 0.0:
        return 0.0
    return rated_capacity * exp((k - 1.0) * log(ratio))


# ── cycle_life_degradation ───────────────────────────────────────────────────


def cycle_life_degradation(
    initial_capacity: Float64,
    cycles: Float64,
    degradation_per_cycle: Float64,
) -> Float64:
    """Remaining capacity = initial * (1 - degradation_per_cycle * cycles)."""
    var factor = 1.0 - degradation_per_cycle * cycles
    if factor < 0.0:
        factor = 0.0
    return initial_capacity * factor


# ── internal_resistance_from_voltage ─────────────────────────────────────────


def internal_resistance_from_voltage(
    ocv: Float64, terminal_voltage: Float64, current: Float64
) -> Float64:
    """Internal resistance R = (OCV - V_terminal) / I (Ohms)."""
    if fabs(current) < 1e-15:
        return 0.0
    return (ocv - terminal_voltage) / current


# ── battery_pack_voltage ─────────────────────────────────────────────────────


def battery_pack_voltage(
    cells_in_series: Float64, cell_voltage: Float64
) -> Float64:
    """Pack voltage V = n_series * V_cell."""
    return cells_in_series * cell_voltage


# ── battery_pack_capacity ────────────────────────────────────────────────────


def battery_pack_capacity(
    cells_in_parallel: Float64, cell_capacity: Float64
) -> Float64:
    """Pack capacity C = n_parallel * C_cell (Ah)."""
    return cells_in_parallel * cell_capacity
