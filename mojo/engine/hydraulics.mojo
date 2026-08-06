"""Hydraulic Systems Library — Wave 95."""

from std.math import sqrt, log, exp, abs


def pascals_law_force(pressure: Float64, area: Float64) -> Float64:
    """F = P * A."""
    return pressure * area


def pascals_law_pressure(force: Float64, area: Float64) -> Float64:
    """P = F / A."""
    return force / area


def hydraulic_advantage(area_output: Float64, area_input: Float64) -> Float64:
    """MA = A_out / A_in."""
    return area_output / area_input


def flow_rate_cylinder(area: Float64, velocity: Float64) -> Float64:
    """Q = A * v."""
    return area * velocity


def cylinder_velocity(flow_rate: Float64, area: Float64) -> Float64:
    """v = Q / A."""
    return flow_rate / area


def pump_displacement(flow_rate: Float64, rpm: Float64) -> Float64:
    """D = Q / RPM (per revolution)."""
    return flow_rate / rpm


def hydraulic_power(pressure: Float64, flow_rate: Float64) -> Float64:
    """P = pressure * Q (watts, P in Pa, Q in m³/s)."""
    return pressure * flow_rate


def system_pressure_loss(flow_rate: Float64, resistance: Float64) -> Float64:
    """ΔP = Q² * R (simplified)."""
    return flow_rate * flow_rate * resistance


def accumulator_volume(gas_precharge: Float64, min_pressure: Float64, max_pressure: Float64) -> Float64:
    """V = Vp * (Pmax/Pmin - 1)."""
    return gas_precharge * (max_pressure / min_pressure - 1.0)


def relief_valve_flow(pressure: Float64, cracking_pressure: Float64, gain: Float64) -> Float64:
    """Q = (P - Pc) * gain if P > Pc else 0."""
    if pressure > cracking_pressure:
        return (pressure - cracking_pressure) * gain
    return 0.0


def oil_compressibility(volume: Float64, pressure_change: Float64, bulk_modulus: Float64) -> Float64:
    """ΔV = V * ΔP / B."""
    return volume * pressure_change / bulk_modulus


def cylinder_bore_from_force(force: Float64, pressure: Float64) -> Float64:
    """d = sqrt(4*F / (π*P))."""
    var pi = 3.141592653589793
    return sqrt(4.0 * force / (pi * pressure))
