"""
aviation.mojo — Aircraft performance and aerodynamics calculations. Zero Python imports.

Public API:
  lift_force                   — L = 0.5*ρ*v²*A*CL
  drag_force                   — D = 0.5*ρ*v²*A*CD
  lift_to_drag_ratio           — L/D
  thrust_required              — T = D (level flight)
  range_breguet               — Breguet range equation
  endurance_breguet            — Breguet endurance equation
  indicated_airspeed           — IAS from dynamic pressure
  true_airspeed                — TAS from IAS and density ratio
  mach_number                  — M = v / a (speed of sound)
  rate_of_climb                — ROC from excess thrust
"""
from std.math import sqrt, log, pow


def lift_force(
    air_density: Float64, velocity: Float64, wing_area: Float64, cl: Float64
) -> Float64:
    """Aerodynamic lift: L = ½·ρ·v²·A·CL.

    Args:
        air_density: Air density (kg/m³).
        velocity: True airspeed (m/s).
        wing_area: Wing reference area (m²).
        cl: Lift coefficient.

    Returns:
        Lift force (N).
    """
    return 0.5 * air_density * velocity * velocity * wing_area * cl


def drag_force(
    air_density: Float64, velocity: Float64, wing_area: Float64, cd: Float64
) -> Float64:
    """Aerodynamic drag: D = ½·ρ·v²·A·CD.

    Args:
        air_density: Air density (kg/m³).
        velocity: True airspeed (m/s).
        wing_area: Wing reference area (m²).
        cd: Drag coefficient.

    Returns:
        Drag force (N).
    """
    return 0.5 * air_density * velocity * velocity * wing_area * cd


def lift_to_drag_ratio(cl: Float64, cd: Float64) -> Float64:
    """Aerodynamic efficiency: L/D = CL/CD.

    Args:
        cl: Lift coefficient.
        cd: Drag coefficient.

    Returns:
        Lift-to-drag ratio.
    """
    if cd <= 0.0:
        return 0.0
    return cl / cd


def thrust_required(
    weight: Float64, cl: Float64, cd: Float64
) -> Float64:
    """Thrust required for level flight: T = W·CD/CL.

    Args:
        weight: Aircraft weight (N).
        cl: Lift coefficient.
        cd: Drag coefficient.

    Returns:
        Thrust required (N).
    """
    if cl <= 0.0:
        return weight
    return weight * cd / cl


def range_breguet(
    ld_ratio: Float64, sfc: Float64, weight_initial: Float64, weight_final: Float64
) -> Float64:
    """Breguet range equation: R = (v/sfc)·(L/D)·ln(Wi/Wf).

    Args:
        ld_ratio: Lift-to-drag ratio.
        sfc: Specific fuel consumption (N/N/s = s⁻¹).
        weight_initial: Initial weight (N).
        weight_final: Final weight after fuel burn (N).

    Returns:
        Range (m). Note: v is embedded in sfc units.
    """
    if sfc <= 0.0 or weight_final <= 0.0 or weight_initial <= weight_final:
        return 0.0
    return (ld_ratio / sfc) * log(weight_initial / weight_final)


def endurance_breguet(
    ld_ratio: Float64, sfc: Float64,
    weight_initial: Float64, weight_final: Float64
) -> Float64:
    """Breguet endurance: E = (1/sfc)·(L/D)·ln(Wi/Wf).

    Args:
        ld_ratio: Lift-to-drag ratio.
        sfc: Specific fuel consumption (s⁻¹).
        weight_initial: Initial weight (N).
        weight_final: Final weight (N).

    Returns:
        Endurance (s).
    """
    if sfc <= 0.0 or weight_final <= 0.0 or weight_initial <= weight_final:
        return 0.0
    return (ld_ratio / sfc) * log(weight_initial / weight_final)


def indicated_airspeed(dynamic_pressure: Float64) -> Float64:
    """Indicated airspeed from dynamic pressure (ISA sea-level density).

    IAS = sqrt(2·q / ρ0)

    Args:
        dynamic_pressure: Dynamic pressure q (Pa).

    Returns:
        Indicated airspeed (m/s).
    """
    var rho0 = 1.225  # ISA sea-level density kg/m³
    if dynamic_pressure < 0.0:
        return 0.0
    return sqrt(2.0 * dynamic_pressure / rho0)


def true_airspeed(ias: Float64, density_ratio: Float64) -> Float64:
    """True airspeed from IAS and density ratio.

    TAS = IAS / sqrt(σ)  where σ = ρ/ρ0

    Args:
        ias: Indicated airspeed (m/s).
        density_ratio: Density ratio σ = ρ/ρ0.

    Returns:
        True airspeed (m/s).
    """
    if density_ratio <= 0.0:
        return ias
    return ias / sqrt(density_ratio)


def mach_number(velocity: Float64, temperature_k: Float64) -> Float64:
    """Mach number: M = v/a where a = sqrt(γ·R·T).

    Args:
        velocity: True airspeed (m/s).
        temperature_k: Static air temperature (K).

    Returns:
        Mach number.
    """
    var gamma = 1.4
    var R = 287.058  # J/kg/K
    var a = sqrt(gamma * R * temperature_k)
    if a <= 0.0:
        return 0.0
    return velocity / a


def rate_of_climb(
    excess_thrust: Float64, weight: Float64, velocity: Float64
) -> Float64:
    """Rate of climb from excess thrust.

    ROC = (T - D) · v / W = excess_power / weight

    Args:
        excess_thrust: T - D, excess thrust (N).
        weight: Aircraft weight (N).
        velocity: True airspeed (m/s).

    Returns:
        Rate of climb (m/s).
    """
    if weight <= 0.0:
        return 0.0
    return excess_thrust * velocity / weight
