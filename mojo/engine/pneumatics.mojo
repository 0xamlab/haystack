"""
pneumatics.mojo — Pneumatics / Compressed Air Library.

Provides calculations for pneumatic systems: gas laws, compressor sizing,
cylinder force, pipe losses, and air treatment.

Public API:
  ideal_gas_volume      — V2 = P1*V1/P2 (Boyle's law)
  flow_rate_orifice     — Q = Cd*A*sqrt(2*ΔP/ρ)
  compressor_power      — P = Q*P1*ln(P2/P1)/eff (isothermal)
  pressure_drop_pipe    — ΔP = f*L/D * ρ*v²/2
  air_consumption       — Q = π/4*d²*stroke*2*pressure/101.325*cycles
  cylinder_force        — F = A*P (newtons)
  bore_area             — A = π*d²/4
  piston_speed          — v = 2*stroke*cycles/60 (m/s)
  receiver_volume       — V = Q*t/(Pmax-Pmin)
  free_air_delivery     — FAD = flow*measured/atm
  specific_power        — SP = power/FAD (kW per m³/min)
  dew_point_pressure    — DP ≈ atm_dp + 10*log(ratio)
"""
from std.math import abs as fabs, sqrt, log


comptime PI: Float64 = 3.141592653589793


# ── ideal_gas_volume ─────────────────────────────────────────────────────────


def ideal_gas_volume(
    pressure1: Float64, volume1: Float64, pressure2: Float64
) -> Float64:
    """Boyle's law: V2 = P1 * V1 / P2.

    Args:
        pressure1: Initial absolute pressure.
        volume1: Initial volume.
        pressure2: Final absolute pressure.

    Returns:
        Final volume.
    """
    if fabs(pressure2) < 1e-30:
        return 0.0
    return pressure1 * volume1 / pressure2


# ── flow_rate_orifice ────────────────────────────────────────────────────────


def flow_rate_orifice(
    cd: Float64,
    area: Float64,
    pressure_drop: Float64,
    density: Float64,
) -> Float64:
    """Orifice flow rate: Q = Cd * A * sqrt(2 * ΔP / ρ).

    Args:
        cd: Discharge coefficient.
        area: Orifice area (m²).
        pressure_drop: Pressure drop across orifice (Pa).
        density: Fluid density (kg/m³).

    Returns:
        Volumetric flow rate (m³/s).
    """
    if fabs(density) < 1e-30:
        return 0.0
    var inner = 2.0 * pressure_drop / density
    if inner < 0.0:
        return 0.0
    return cd * area * sqrt(inner)


# ── compressor_power ─────────────────────────────────────────────────────────


def compressor_power(
    flow_rate: Float64,
    p1: Float64,
    p2: Float64,
    efficiency: Float64,
) -> Float64:
    """Isothermal compressor power: P = Q * P1 * ln(P2/P1) / eff.

    Args:
        flow_rate: Volumetric flow rate (m³/s).
        p1: Inlet absolute pressure (Pa).
        p2: Outlet absolute pressure (Pa).
        efficiency: Overall efficiency (0–1).

    Returns:
        Power (watts).
    """
    if fabs(efficiency) < 1e-30 or fabs(p1) < 1e-30:
        return 0.0
    var ratio = p2 / p1
    if ratio <= 0.0:
        return 0.0
    return flow_rate * p1 * log(ratio) / efficiency


# ── pressure_drop_pipe ───────────────────────────────────────────────────────


def pressure_drop_pipe(
    f: Float64,
    length: Float64,
    diameter: Float64,
    density: Float64,
    velocity: Float64,
) -> Float64:
    """Darcy-Weisbach pipe pressure drop: ΔP = f * L/D * ρ * v² / 2.

    Args:
        f: Darcy friction factor.
        length: Pipe length (m).
        diameter: Pipe inner diameter (m).
        density: Air density (kg/m³).
        velocity: Flow velocity (m/s).

    Returns:
        Pressure drop (Pa).
    """
    if fabs(diameter) < 1e-30:
        return 0.0
    return f * length / diameter * density * velocity * velocity / 2.0


# ── air_consumption ──────────────────────────────────────────────────────────


def air_consumption(
    bore_diameter: Float64,
    stroke: Float64,
    pressure: Float64,
    cycles_per_min: Float64,
) -> Float64:
    """Cylinder air consumption: Q = π/4 * d² * stroke * 2 * (P/101.325) * cycles.

    Args:
        bore_diameter: Cylinder bore diameter (m).
        stroke: Stroke length (m).
        pressure: Working gauge pressure (kPa abs) — ratio to atm.
        cycles_per_min: Cycles per minute (double-acting = 2 strokes/cycle).

    Returns:
        Air consumption (m³/min at working pressure).
    """
    var area = PI / 4.0 * bore_diameter * bore_diameter
    return area * stroke * 2.0 * pressure / 101.325 * cycles_per_min


# ── cylinder_force ───────────────────────────────────────────────────────────


def cylinder_force(
    bore_area: Float64, pressure: Float64
) -> Float64:
    """Cylinder force: F = A * P (newtons).

    Args:
        bore_area: Piston bore area (m²).
        pressure: Working pressure (Pa).

    Returns:
        Force (newtons).
    """
    return bore_area * pressure


# ── bore_area ────────────────────────────────────────────────────────────────


def bore_area(diameter: Float64) -> Float64:
    """Bore area: A = π * d² / 4.

    Args:
        diameter: Bore diameter (m).

    Returns:
        Area (m²).
    """
    return PI / 4.0 * diameter * diameter


# ── piston_speed ─────────────────────────────────────────────────────────────


def piston_speed(
    stroke: Float64, cycles_per_min: Float64
) -> Float64:
    """Average piston speed: v = 2 * stroke * cycles / 60 (m/s).

    Args:
        stroke: Stroke length (m).
        cycles_per_min: Cycles per minute.

    Returns:
        Average piston speed (m/s).
    """
    return 2.0 * stroke * cycles_per_min / 60.0


# ── receiver_volume ──────────────────────────────────────────────────────────


def receiver_volume(
    flow_rate: Float64,
    run_time: Float64,
    p_max: Float64,
    p_min: Float64,
) -> Float64:
    """Air receiver volume: V = Q * t / (Pmax - Pmin).

    Args:
        flow_rate: Required flow rate (m³/min or L/s).
        run_time: Desired run time between compressor cycles.
        p_max: Maximum pressure.
        p_min: Minimum pressure.

    Returns:
        Receiver volume.
    """
    var dp = p_max - p_min
    if fabs(dp) < 1e-30:
        return 0.0
    return flow_rate * run_time / dp


# ── free_air_delivery ────────────────────────────────────────────────────────


def free_air_delivery(
    measured_flow: Float64,
    measured_pressure: Float64,
    atm_pressure: Float64,
) -> Float64:
    """Free air delivery: FAD = flow * measured_pressure / atm_pressure.

    Args:
        measured_flow: Measured flow at pressure.
        measured_pressure: Measurement absolute pressure.
        atm_pressure: Atmospheric pressure.

    Returns:
        Free air delivery (at atmospheric conditions).
    """
    if fabs(atm_pressure) < 1e-30:
        return 0.0
    return measured_flow * measured_pressure / atm_pressure


# ── specific_power ───────────────────────────────────────────────────────────


def specific_power(
    power_kw: Float64, fad: Float64
) -> Float64:
    """Specific power: SP = power / FAD (kW per m³/min).

    Args:
        power_kw: Compressor power (kW).
        fad: Free air delivery (m³/min).

    Returns:
        Specific power (kW·min/m³).
    """
    if fabs(fad) < 1e-30:
        return 0.0
    return power_kw / fad


# ── dew_point_pressure ───────────────────────────────────────────────────────


def dew_point_pressure(
    atm_dew_point: Float64, pressure_ratio: Float64
) -> Float64:
    """Pressure dew point (simplified): DP ≈ atm_dp + 10 * log(ratio).

    Args:
        atm_dew_point: Atmospheric dew point (°C).
        pressure_ratio: Pressure ratio (absolute / atmospheric).

    Returns:
        Estimated pressure dew point (°C).
    """
    if pressure_ratio <= 0.0:
        return atm_dew_point
    return atm_dew_point + 10.0 * log(pressure_ratio)
