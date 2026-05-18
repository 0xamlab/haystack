"""
power_systems.mojo — Electrical Power Systems Library. Zero Python imports.

Provides functions for AC/DC power calculations, transformers, line losses,
power factor analysis, and load factor computation.

Public API:
  active_power               — P = V*I*PF
  reactive_power             — Q = V*I*sin(φ)
  apparent_power             — S = V*I
  power_factor_from_pq       — PF = P/S
  three_phase_power          — P = √3 * V * I * PF
  transformer_turns_ratio    — a = Vp/Vs
  transformer_secondary_voltage — Vs = Vp/a
  line_loss                  — P_loss = I²*R
  voltage_drop               — V_drop = 2*I*R*L
  power_efficiency           — η = Pout/Pin
  capacitor_reactive_power   — Qc = V² * 2πfC
  load_factor                — LF = avg/peak
"""

from std.math import sqrt


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime SQRT3: Float64 = 1.7320508075688772


# ── active_power ─────────────────────────────────────────────────────────────


fn active_power(
    voltage: Float64, current: Float64, power_factor: Float64
) -> Float64:
    """Active power: P = V * I * PF."""
    return voltage * current * power_factor


# ── reactive_power ───────────────────────────────────────────────────────────


fn reactive_power(
    voltage: Float64, current: Float64, power_factor: Float64
) -> Float64:
    """Reactive power: Q = V*I*sin(φ), sin = sqrt(1 - PF²)."""
    var pf2 = power_factor * power_factor
    var sin_phi = sqrt(1.0 - pf2)
    return voltage * current * sin_phi


# ── apparent_power ───────────────────────────────────────────────────────────


fn apparent_power(voltage: Float64, current: Float64) -> Float64:
    """Apparent power: S = V * I."""
    return voltage * current


# ── power_factor_from_pq ────────────────────────────────────────────────────


fn power_factor_from_pq(p: Float64, s: Float64) -> Float64:
    """Power factor: PF = P / S."""
    if s == 0.0:
        return 0.0
    return p / s


# ── three_phase_power ───────────────────────────────────────────────────────


fn three_phase_power(
    v_line: Float64, i_line: Float64, pf: Float64
) -> Float64:
    """Three-phase power: P = √3 * V * I * PF."""
    return SQRT3 * v_line * i_line * pf


# ── transformer_turns_ratio ─────────────────────────────────────────────────


fn transformer_turns_ratio(
    v_primary: Float64, v_secondary: Float64
) -> Float64:
    """Turns ratio: a = Vp / Vs."""
    if v_secondary == 0.0:
        return 0.0
    return v_primary / v_secondary


# ── transformer_secondary_voltage ────────────────────────────────────────────


fn transformer_secondary_voltage(
    v_primary: Float64, turns_ratio: Float64
) -> Float64:
    """Secondary voltage: Vs = Vp / a."""
    if turns_ratio == 0.0:
        return 0.0
    return v_primary / turns_ratio


# ── line_loss ────────────────────────────────────────────────────────────────


fn line_loss(current: Float64, resistance: Float64) -> Float64:
    """Line power loss: P_loss = I² * R."""
    return current * current * resistance


# ── voltage_drop ─────────────────────────────────────────────────────────────


fn voltage_drop(
    current: Float64, resistance: Float64, length: Float64
) -> Float64:
    """Voltage drop (round trip): V_drop = 2 * I * R * L."""
    return 2.0 * current * resistance * length


# ── power_efficiency ────────────────────────────────────────────────────────


fn power_efficiency(output_power: Float64, input_power: Float64) -> Float64:
    """Efficiency: η = Pout / Pin."""
    if input_power == 0.0:
        return 0.0
    return output_power / input_power


# ── capacitor_reactive_power ─────────────────────────────────────────────────


fn capacitor_reactive_power(
    voltage: Float64, capacitance: Float64, frequency: Float64
) -> Float64:
    """Capacitor reactive power: Qc = V² * 2πfC."""
    return voltage * voltage * 2.0 * PI * frequency * capacitance


# ── load_factor ──────────────────────────────────────────────────────────────


fn load_factor(avg_demand: Float64, peak_demand: Float64) -> Float64:
    """Load factor: LF = avg_demand / peak_demand."""
    if peak_demand == 0.0:
        return 0.0
    return avg_demand / peak_demand
