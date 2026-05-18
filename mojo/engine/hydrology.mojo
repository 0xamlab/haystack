"""
hydrology.mojo — Hydrology & Water Resources Library. Zero Python imports.

Pure Mojo implementations of fundamental hydrology and hydraulic equations
including Manning's equation, Darcy-Weisbach, rational method, SCS curve
number, and groundwater flow.

Public API:
  manning_velocity            — Manning's equation velocity
  manning_discharge           — Manning's equation discharge Q = A*V
  hydraulic_radius            — R_h = A / P
  froude_number               — Fr = V / sqrt(g*d)
  reynolds_number_pipe        — Re = V*D / ν
  darcy_weisbach_head_loss    — hf = f*(L/D)*(V²/2g)
  rational_method_peak_flow   — Q = C*i*A
  time_of_concentration_kirpich — tc = 0.0078 * L^0.77 * S^(-0.385)
  curve_number_runoff         — SCS curve number runoff
  evapotranspiration_hargreaves — Hargreaves ET equation
  specific_yield              — Sy = Vd / Vt
  darcy_groundwater_velocity  — v = K * i
"""
from std.math import sqrt, abs as fabs, exp, log, pow


# ── manning_velocity ──────────────────────────────────────────────────────────


fn manning_velocity(n: Float64, r_h: Float64, slope: Float64) -> Float64:
    """Manning's equation: V = (1/n) * R_h^(2/3) * S^(1/2)."""
    var r_h_23 = exp(2.0 / 3.0 * log(r_h))
    return (1.0 / n) * r_h_23 * sqrt(slope)


# ── manning_discharge ─────────────────────────────────────────────────────────


fn manning_discharge(
    n: Float64, area: Float64, r_h: Float64, slope: Float64
) -> Float64:
    """Q = A * V from Manning's equation."""
    return area * manning_velocity(n, r_h, slope)


# ── hydraulic_radius ──────────────────────────────────────────────────────────


fn hydraulic_radius(area: Float64, wetted_perimeter: Float64) -> Float64:
    """R_h = A / P."""
    return area / wetted_perimeter


# ── froude_number ─────────────────────────────────────────────────────────────


fn froude_number(velocity: Float64, depth: Float64, g: Float64) -> Float64:
    """Fr = V / sqrt(g * d)."""
    return velocity / sqrt(g * depth)


# ── reynolds_number_pipe ──────────────────────────────────────────────────────


fn reynolds_number_pipe(
    velocity: Float64, diameter: Float64, kinematic_viscosity: Float64
) -> Float64:
    """Re = V * D / ν."""
    return velocity * diameter / kinematic_viscosity


# ── darcy_weisbach_head_loss ──────────────────────────────────────────────────


fn darcy_weisbach_head_loss(
    f: Float64,
    length: Float64,
    diameter: Float64,
    velocity: Float64,
    g: Float64,
) -> Float64:
    """hf = f * (L/D) * (V² / (2*g))."""
    return f * (length / diameter) * (velocity * velocity) / (2.0 * g)


# ── rational_method_peak_flow ─────────────────────────────────────────────────


fn rational_method_peak_flow(
    c: Float64, intensity: Float64, area: Float64
) -> Float64:
    """Q = C * i * A (Rational Method)."""
    return c * intensity * area


# ── time_of_concentration_kirpich ─────────────────────────────────────────────


fn time_of_concentration_kirpich(
    length: Float64, slope: Float64
) -> Float64:
    """tc = 0.0078 * L^0.77 * S^(-0.385) (Kirpich formula, minutes)."""
    var l_077 = exp(0.77 * log(length))
    var s_neg = exp(-0.385 * log(slope))
    return 0.0078 * l_077 * s_neg


# ── curve_number_runoff ───────────────────────────────────────────────────────


fn curve_number_runoff(precipitation: Float64, cn: Float64) -> Float64:
    """SCS Curve Number runoff: Q = (P - 0.2*S)² / (P + 0.8*S).

    S = 1000/CN - 10 (in inches).
    Returns 0 if P <= 0.2*S (initial abstraction exceeds precip).
    """
    var s = 1000.0 / cn - 10.0
    var ia = 0.2 * s
    if precipitation <= ia:
        return 0.0
    var numerator = (precipitation - ia) * (precipitation - ia)
    return numerator / (precipitation + 0.8 * s)


# ── evapotranspiration_hargreaves ─────────────────────────────────────────────


fn evapotranspiration_hargreaves(
    t_mean: Float64, t_range: Float64, ra: Float64
) -> Float64:
    """Hargreaves ET: ET = 0.0023 * Ra * (T_mean + 17.8) * T_range^0.5.

    ra = extraterrestrial radiation (MJ/m²/day).
    Returns ET in mm/day.
    """
    return 0.0023 * ra * (t_mean + 17.8) * sqrt(t_range)


# ── specific_yield ────────────────────────────────────────────────────────────


fn specific_yield(volume_drained: Float64, total_volume: Float64) -> Float64:
    """Sy = Vd / Vt."""
    return volume_drained / total_volume


# ── darcy_groundwater_velocity ────────────────────────────────────────────────


fn darcy_groundwater_velocity(k: Float64, gradient: Float64) -> Float64:
    """Darcy's law for groundwater: v = K * i (hydraulic conductivity * gradient)."""
    return k * gradient
