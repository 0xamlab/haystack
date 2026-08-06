"""
wind_energy.mojo — Wind Energy Engineering Library. Zero Python imports.

Provides turbine power, efficiency, wake, and wind resource calculations.

Public API:
  wind_power_available    — P = 0.5*ρ*A*v³
  betz_limit              — 16/27 ≈ 0.5926
  power_coefficient       — Cp = P_actual / P_available
  tip_speed_ratio         — λ = ω*R/V
  swept_area              — A = π*R²
  annual_energy_production— AEP = P * CF * hours
  capacity_factor         — CF = E_actual / (P_rated * hours)
  wind_shear_power_law    — v = v_ref * (z/z_ref)^α
  weibull_mean_wind_speed — v_mean ≈ c * 0.886 (k≈2)
  energy_density          — ED = 0.5*ρ*v³
  rotor_thrust            — T = 0.5*Ct*ρ*A*v²
  wake_velocity           — simplified Jensen model
"""
from std.math import exp, log, sqrt, abs as fabs


# ── constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793


# ── wind_power_available ─────────────────────────────────────────────────────


def wind_power_available(
    density: Float64, area: Float64, velocity: Float64
) -> Float64:
    """Wind power available: P = 0.5 * ρ * A * v³.

    Args:
        density: Air density (kg/m³).
        area: Swept area (m²).
        velocity: Wind speed (m/s).

    Returns:
        Available power (W).
    """
    return 0.5 * density * area * velocity * velocity * velocity


# ── betz_limit ───────────────────────────────────────────────────────────────


def betz_limit() -> Float64:
    """Betz limit: maximum power coefficient = 16/27.

    Returns:
        Betz limit ≈ 0.5926.
    """
    return 16.0 / 27.0


# ── power_coefficient ────────────────────────────────────────────────────────


def power_coefficient(
    actual_power: Float64, available_power: Float64
) -> Float64:
    """Power coefficient: Cp = P_actual / P_available.

    Args:
        actual_power: Actual extracted power (W).
        available_power: Total available wind power (W).

    Returns:
        Power coefficient (dimensionless).
    """
    if fabs(available_power) < 1e-30:
        return 0.0
    return actual_power / available_power


# ── tip_speed_ratio ──────────────────────────────────────────────────────────


def tip_speed_ratio(
    omega: Float64, radius: Float64, wind_speed: Float64
) -> Float64:
    """Tip speed ratio: λ = ω * R / V.

    Args:
        omega: Rotor angular velocity (rad/s).
        radius: Rotor radius (m).
        wind_speed: Free-stream wind speed (m/s).

    Returns:
        Tip speed ratio (dimensionless).
    """
    if fabs(wind_speed) < 1e-30:
        return 0.0
    return omega * radius / wind_speed


# ── swept_area ───────────────────────────────────────────────────────────────


def swept_area(radius: Float64) -> Float64:
    """Swept area: A = π * R².

    Args:
        radius: Rotor radius (m).

    Returns:
        Swept area (m²).
    """
    return PI * radius * radius


# ── annual_energy_production ─────────────────────────────────────────────────


def annual_energy_production(
    power_kw: Float64, capacity_factor: Float64, hours: Float64
) -> Float64:
    """AEP = P * CF * hours.

    Args:
        power_kw: Rated power (kW).
        capacity_factor: Capacity factor (0-1).
        hours: Number of hours (e.g. 8760 for a year).

    Returns:
        Annual energy production (kWh).
    """
    return power_kw * capacity_factor * hours


# ── capacity_factor ──────────────────────────────────────────────────────────


def capacity_factor(
    actual_energy: Float64, rated_power: Float64, hours: Float64
) -> Float64:
    """Capacity factor: CF = E_actual / (P_rated * hours).

    Args:
        actual_energy: Actual energy produced (kWh).
        rated_power: Rated power (kW).
        hours: Time period (hours).

    Returns:
        Capacity factor (0-1).
    """
    var denom = rated_power * hours
    if fabs(denom) < 1e-30:
        return 0.0
    return actual_energy / denom


# ── wind_shear_power_law ─────────────────────────────────────────────────────


def wind_shear_power_law(
    v_ref: Float64,
    z: Float64,
    z_ref: Float64,
    alpha: Float64,
) -> Float64:
    """Wind shear power law: v = v_ref * (z/z_ref)^α.

    Args:
        v_ref: Reference wind speed (m/s).
        z: Target height (m).
        z_ref: Reference height (m).
        alpha: Wind shear exponent.

    Returns:
        Wind speed at height z (m/s).
    """
    if z_ref <= 0.0 or z <= 0.0:
        return 0.0
    return v_ref * exp(alpha * log(z / z_ref))


# ── weibull_mean_wind_speed ──────────────────────────────────────────────────


def weibull_mean_wind_speed(c: Float64, k: Float64) -> Float64:
    """Weibull mean wind speed: v_mean ≈ c * 0.886 (for k≈2).

    Uses Γ(1+1/k) ≈ 0.886 for k=2 (Rayleigh).

    Args:
        c: Weibull scale parameter (m/s).
        k: Weibull shape parameter.

    Returns:
        Mean wind speed (m/s).
    """
    return c * 0.886


# ── energy_density ───────────────────────────────────────────────────────────


def energy_density(density: Float64, velocity: Float64) -> Float64:
    """Wind energy density: ED = 0.5 * ρ * v³ (W/m²).

    Args:
        density: Air density (kg/m³).
        velocity: Wind speed (m/s).

    Returns:
        Energy density (W/m²).
    """
    return 0.5 * density * velocity * velocity * velocity


# ── rotor_thrust ─────────────────────────────────────────────────────────────


def rotor_thrust(
    ct: Float64,
    density: Float64,
    area: Float64,
    velocity: Float64,
) -> Float64:
    """Rotor thrust: T = 0.5 * Ct * ρ * A * v².

    Args:
        ct: Thrust coefficient.
        density: Air density (kg/m³).
        area: Swept area (m²).
        velocity: Wind speed (m/s).

    Returns:
        Thrust force (N).
    """
    return 0.5 * ct * density * area * velocity * velocity


# ── wake_velocity ────────────────────────────────────────────────────────────


def wake_velocity(
    v0: Float64,
    ct: Float64,
    x: Float64,
    d: Float64,
) -> Float64:
    """Simplified Jensen wake model: v_w = v0*(1 - (1-sqrt(1-ct))/(1+k*x/D)²).

    Uses wake decay constant k = 0.075.

    Args:
        v0: Free-stream wind speed (m/s).
        ct: Thrust coefficient.
        x: Downstream distance (m).
        d: Rotor diameter (m).

    Returns:
        Wake velocity (m/s).
    """
    if fabs(d) < 1e-30:
        return v0
    comptime k_wake: Float64 = 0.075
    var deficit_num = 1.0 - sqrt(1.0 - ct)
    var expansion = 1.0 + k_wake * x / d
    var deficit = deficit_num / (expansion * expansion)
    return v0 * (1.0 - deficit)
