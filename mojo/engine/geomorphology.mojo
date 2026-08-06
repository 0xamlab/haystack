"""
geomorphology.mojo — Geomorphology Library.

Provides landscape evolution, fluvial, and morphometric calculations.

Public API:
  stream_power            — Ω = ρgQS (W/m)
  shear_stress_flow       — τ = ρgdS
  shields_parameter       — θ = τ/((ρs-ρf)*g*D)
  settling_velocity_stokes— ws = (ρs-ρf)*g*d²/(18*μ)
  erosion_rate_spl        — E = K*A^m*S^n
  hillslope_diffusion     — qs = Kd * curvature (m²/yr)
  drainage_density        — Dd = L/A (1/m)
  relief_ratio            — Rr = H/L
  sinuosity               — S = Lc/Lv
  hack_law_length         — L = c*A^h
  ruggedness_number       — Rn = H*Dd
  hypsometric_integral    — HI = (mean-min)/(max-min)
"""
from std.math import pow, exp


# ── stream_power ─────────────────────────────────────────────────────────────


def stream_power(
    discharge: Float64, slope: Float64, density: Float64, g: Float64
) -> Float64:
    """Stream power per unit channel length: Ω = ρ*g*Q*S (W/m).

    Args:
        discharge: Volumetric discharge Q (m³/s).
        slope: Channel slope S (dimensionless).
        density: Water density ρ (kg/m³).
        g: Gravitational acceleration (m/s²).

    Returns:
        Stream power Ω in W/m.
    """
    return density * g * discharge * slope


# ── shear_stress_flow ────────────────────────────────────────────────────────


def shear_stress_flow(
    density: Float64, g: Float64, depth: Float64, slope: Float64
) -> Float64:
    """Bed shear stress: τ = ρ*g*d*S.

    Args:
        density: Water density ρ (kg/m³).
        g: Gravitational acceleration (m/s²).
        depth: Flow depth d (m).
        slope: Channel slope S (dimensionless).

    Returns:
        Shear stress τ in Pa.
    """
    return density * g * depth * slope


# ── shields_parameter ────────────────────────────────────────────────────────


def shields_parameter(
    shear_stress: Float64,
    density_s: Float64,
    density_f: Float64,
    g: Float64,
    grain_size: Float64,
) -> Float64:
    """Shields parameter: θ = τ / ((ρs - ρf) * g * D).

    Args:
        shear_stress: Bed shear stress τ (Pa).
        density_s: Sediment density ρs (kg/m³).
        density_f: Fluid density ρf (kg/m³).
        g: Gravitational acceleration (m/s²).
        grain_size: Representative grain diameter D (m).

    Returns:
        Dimensionless Shields parameter θ.
    """
    # Equal densities (or zero g / grain size) zero the denominator, and
    # inf/nan cannot cross the result wire.
    var denom = (density_s - density_f) * g * grain_size
    if denom == 0.0:
        return 0.0
    return shear_stress / denom


# ── settling_velocity_stokes ─────────────────────────────────────────────────


def settling_velocity_stokes(
    density_s: Float64,
    density_f: Float64,
    g: Float64,
    diameter: Float64,
    viscosity: Float64,
) -> Float64:
    """Stokes settling velocity: ws = (ρs - ρf)*g*d² / (18*μ).

    Args:
        density_s: Particle density ρs (kg/m³).
        density_f: Fluid density ρf (kg/m³).
        g: Gravitational acceleration (m/s²).
        diameter: Particle diameter d (m).
        viscosity: Dynamic viscosity μ (Pa·s).

    Returns:
        Settling velocity ws in m/s.
    """
    return (density_s - density_f) * g * diameter * diameter / (18.0 * viscosity)


# ── erosion_rate_spl ─────────────────────────────────────────────────────────


def erosion_rate_spl(
    k: Float64, area: Float64, slope: Float64, m: Float64, n: Float64
) -> Float64:
    """Stream Power Law erosion rate: E = K * A^m * S^n.

    Args:
        k: Erodibility coefficient K.
        area: Upstream drainage area A (m²).
        slope: Local channel slope S.
        m: Area exponent.
        n: Slope exponent.

    Returns:
        Erosion rate E (m/yr or consistent units).
    """
    return k * pow(area, m) * pow(slope, n)


# ── hillslope_diffusion ─────────────────────────────────────────────────────


def hillslope_diffusion(kd: Float64, curvature: Float64) -> Float64:
    """Hillslope diffusive sediment flux: qs = Kd * curvature.

    Args:
        kd: Diffusivity Kd (m²/yr).
        curvature: Surface curvature (1/m, positive = concave up).

    Returns:
        Sediment flux qs (m²/yr).
    """
    return kd * curvature


# ── drainage_density ─────────────────────────────────────────────────────────


def drainage_density(total_stream_length: Float64, basin_area: Float64) -> Float64:
    """Drainage density: Dd = ΣL / A (1/m).

    Args:
        total_stream_length: Total stream length L (m or km).
        basin_area: Basin area A (m² or km²) — same unit system.

    Returns:
        Drainage density Dd (1/m or 1/km).
    """
    return total_stream_length / basin_area


# ── relief_ratio ─────────────────────────────────────────────────────────────


def relief_ratio(relief: Float64, basin_length: Float64) -> Float64:
    """Relief ratio: Rr = H / L.

    Args:
        relief: Basin relief H (max elev - min elev, m).
        basin_length: Basin length L (m).

    Returns:
        Dimensionless relief ratio Rr.
    """
    return relief / basin_length


# ── sinuosity ────────────────────────────────────────────────────────────────


def sinuosity(channel_length: Float64, valley_length: Float64) -> Float64:
    """Channel sinuosity: S = Lc / Lv.

    Args:
        channel_length: Channel (thalweg) length Lc.
        valley_length: Straight-line valley length Lv.

    Returns:
        Sinuosity S (≥1.0 for natural channels).
    """
    return channel_length / valley_length


# ── hack_law_length ──────────────────────────────────────────────────────────


def hack_law_length(c: Float64, area: Float64, h: Float64) -> Float64:
    """Hack's law: L = c * A^h (stream length vs catchment area).

    Args:
        c: Proportionality constant.
        area: Drainage area A.
        h: Hack exponent (typically ~0.6).

    Returns:
        Predicted main-stream length L.
    """
    return c * pow(area, h)


# ── ruggedness_number ────────────────────────────────────────────────────────


def ruggedness_number(relief: Float64, drainage_density_val: Float64) -> Float64:
    """Ruggedness number: Rn = H * Dd.

    Args:
        relief: Basin relief H (m).
        drainage_density_val: Drainage density Dd (1/m).

    Returns:
        Dimensionless ruggedness number Rn.
    """
    return relief * drainage_density_val


# ── hypsometric_integral ─────────────────────────────────────────────────────


def hypsometric_integral(
    mean_elev: Float64, min_elev: Float64, max_elev: Float64
) -> Float64:
    """Hypsometric integral: HI = (mean - min) / (max - min).

    Args:
        mean_elev: Mean basin elevation.
        min_elev: Minimum basin elevation.
        max_elev: Maximum basin elevation.

    Returns:
        Hypsometric integral HI (0–1).
    """
    # A flat basin zeros the denominator, and inf/nan cannot cross the wire.
    if max_elev == min_elev:
        return 0.0
    return (mean_elev - min_elev) / (max_elev - min_elev)
