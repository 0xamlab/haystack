"""
solar_energy.mojo — Solar Energy Engineering Library. Zero Python imports.

Provides solar irradiance, panel output, temperature, position, and economics.

Public API:
  solar_irradiance_on_surface — I = GHI * cos(θ)
  panel_power_output          — P = A * η * G
  temperature_derate          — P = Pmax*(1+coeff*(Tcell-Tstc))
  cell_temperature_noct       — Tcell = Tamb + (NOCT-20)/800*G
  solar_declination           — δ = 23.45*sin(2π*(284+n)/365)
  hour_angle                  — ω = 15*(t-12)
  solar_altitude              — sin(α) = sin(lat)*sin(δ)+cos(lat)*cos(δ)*cos(ω)
  capacity_factor_solar       — CF = kWh/(kW*hours)
  lcoe                        — LCOE = cost/energy
  payback_period              — PP = cost/savings
  inverter_efficiency         — η = Pac/Pdc
  string_voltage              — V = n * Vmp
"""
from std.math import sin, cos, sqrt, exp, log, abs as fabs


# ── constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793
comptime DEG2RAD: Float64 = 3.141592653589793 / 180.0


# ── solar_irradiance_on_surface ──────────────────────────────────────────────


def solar_irradiance_on_surface(
    ghi: Float64, cos_incidence: Float64
) -> Float64:
    """Irradiance on surface: I = GHI * cos(θ).

    Args:
        ghi: Global horizontal irradiance (W/m²).
        cos_incidence: Cosine of angle of incidence.

    Returns:
        Surface irradiance (W/m²).
    """
    return ghi * cos_incidence


# ── panel_power_output ───────────────────────────────────────────────────────


def panel_power_output(
    area: Float64, efficiency: Float64, irradiance: Float64
) -> Float64:
    """Panel power: P = A * η * G.

    Args:
        area: Panel area (m²).
        efficiency: Panel efficiency (0-1).
        irradiance: Irradiance (W/m²).

    Returns:
        Power output (W).
    """
    return area * efficiency * irradiance


# ── temperature_derate ───────────────────────────────────────────────────────


def temperature_derate(
    pmax_stc: Float64,
    temp_coeff: Float64,
    cell_temp: Float64,
    stc_temp: Float64,
) -> Float64:
    """Temperature-derated power: P = Pmax * (1 + coeff*(Tcell - Tstc)).

    Args:
        pmax_stc: Maximum power at STC (W).
        temp_coeff: Temperature coefficient (%/°C as decimal, e.g. -0.004).
        cell_temp: Actual cell temperature (°C).
        stc_temp: STC temperature (°C), typically 25.

    Returns:
        Derated power (W).
    """
    return pmax_stc * (1.0 + temp_coeff * (cell_temp - stc_temp))


# ── cell_temperature_noct ────────────────────────────────────────────────────


def cell_temperature_noct(
    ambient: Float64, noct: Float64, irradiance: Float64
) -> Float64:
    """Cell temperature NOCT model: Tcell = Tamb + (NOCT-20)/800 * G.

    Args:
        ambient: Ambient temperature (°C).
        noct: Nominal operating cell temperature (°C).
        irradiance: Irradiance (W/m²).

    Returns:
        Cell temperature (°C).
    """
    return ambient + (noct - 20.0) / 800.0 * irradiance


# ── solar_declination ────────────────────────────────────────────────────────


def solar_declination(day_of_year: Float64) -> Float64:
    """Solar declination: δ = 23.45 * sin(2π*(284+n)/365).

    Args:
        day_of_year: Day of year (1-365).

    Returns:
        Declination angle (degrees).
    """
    return 23.45 * sin(2.0 * PI * (284.0 + day_of_year) / 365.0)


# ── hour_angle ───────────────────────────────────────────────────────────────


def hour_angle(solar_time_hours: Float64) -> Float64:
    """Hour angle: ω = 15 * (solar_time - 12).

    Args:
        solar_time_hours: Solar time in hours (0-24).

    Returns:
        Hour angle (degrees).
    """
    return 15.0 * (solar_time_hours - 12.0)


# ── solar_altitude ───────────────────────────────────────────────────────────


def solar_altitude(
    latitude: Float64, declination: Float64, hour_ang: Float64
) -> Float64:
    """Solar altitude angle: sin(α) = sin(lat)*sin(δ)+cos(lat)*cos(δ)*cos(ω).

    All inputs in degrees.

    Args:
        latitude: Observer latitude (degrees).
        declination: Solar declination (degrees).
        hour_ang: Hour angle (degrees).

    Returns:
        Solar altitude angle (degrees).
    """
    var lat_r = latitude * DEG2RAD
    var dec_r = declination * DEG2RAD
    var ha_r = hour_ang * DEG2RAD
    var sin_alt = sin(lat_r) * sin(dec_r) + cos(lat_r) * cos(dec_r) * cos(ha_r)
    # Clamp to [-1, 1]
    if sin_alt > 1.0:
        sin_alt = 1.0
    if sin_alt < -1.0:
        sin_alt = -1.0
    # asin via atan2-equivalent: asin(x) = atan2(x, sqrt(1-x²)) — use identity
    # asin(x) = x + x³/6 + ... or use exp/log trick — simplest: return degrees
    # Using: asin(x) in radians then convert
    # asin(x) = atan2(x, sqrt(1-x*x)) — but we don't have atan2
    # Use series or the identity: result_rad where sin(result_rad) = sin_alt
    # Simpler: just compute and return via the available math
    # asin(x) = PI/2 - acos(x), but we don't have acos either
    # Best approach: return the sin_alt value and let tests check sin(altitude)
    # Actually, let's compute asin manually via the Newton method or identity
    # asin(x) = x + x^3/6 + 3x^5/40 + 15x^7/336 ... (Taylor, |x|<1)
    # For better accuracy, use: asin(x) = atan(x/sqrt(1-x²))
    # and atan(x) = x - x³/3 + x⁵/5 - ... or use a rational approx
    # Simplest robust: iterative or just return sin_alt and document it
    # Let's use a good polynomial approximation of asin
    var abs_x = fabs(sin_alt)
    var result: Float64 = 0.0
    if abs_x <= 1.0:
        # Approximation: asin(x) ≈ x*(1 + x²*(1/6 + x²*(3/40 + x²*15/336)))
        var x2 = abs_x * abs_x
        result = abs_x * (1.0 + x2 * (1.0 / 6.0 + x2 * (3.0 / 40.0 + x2 * (15.0 / 336.0 + x2 * 105.0 / 3456.0))))
        # For |x| > 0.7, use identity asin(x) = PI/2 - asin(sqrt(1-x²))
        if abs_x > 0.7:
            var complement = sqrt(1.0 - x2)
            var c2 = complement * complement
            var asin_c = complement * (1.0 + c2 * (1.0 / 6.0 + c2 * (3.0 / 40.0 + c2 * (15.0 / 336.0 + c2 * 105.0 / 3456.0))))
            result = PI / 2.0 - asin_c
    if sin_alt < 0.0:
        result = -result
    return result / DEG2RAD


# ── capacity_factor_solar ────────────────────────────────────────────────────


def capacity_factor_solar(
    annual_kwh: Float64, rated_kw: Float64, hours_year: Float64
) -> Float64:
    """Capacity factor: CF = kWh / (kW * hours).

    Args:
        annual_kwh: Annual energy output (kWh).
        rated_kw: Rated capacity (kW).
        hours_year: Hours in period (e.g. 8760).

    Returns:
        Capacity factor (0-1).
    """
    var denom = rated_kw * hours_year
    if fabs(denom) < 1e-30:
        return 0.0
    return annual_kwh / denom


# ── lcoe ─────────────────────────────────────────────────────────────────────


def lcoe(total_cost: Float64, total_energy: Float64) -> Float64:
    """Levelized cost of energy: LCOE = cost / energy ($/kWh).

    Args:
        total_cost: Total lifetime cost ($).
        total_energy: Total lifetime energy (kWh).

    Returns:
        LCOE ($/kWh).
    """
    if fabs(total_energy) < 1e-30:
        return 0.0
    return total_cost / total_energy


# ── payback_period ───────────────────────────────────────────────────────────


def payback_period(system_cost: Float64, annual_savings: Float64) -> Float64:
    """Simple payback period: PP = cost / savings.

    Args:
        system_cost: System cost ($).
        annual_savings: Annual savings ($/year).

    Returns:
        Payback period (years).
    """
    if fabs(annual_savings) < 1e-30:
        return 0.0
    return system_cost / annual_savings


# ── inverter_efficiency ──────────────────────────────────────────────────────


def inverter_efficiency(ac_output: Float64, dc_input: Float64) -> Float64:
    """Inverter efficiency: η = Pac / Pdc.

    Args:
        ac_output: AC output power (W).
        dc_input: DC input power (W).

    Returns:
        Efficiency (0-1).
    """
    if fabs(dc_input) < 1e-30:
        return 0.0
    return ac_output / dc_input


# ── string_voltage ───────────────────────────────────────────────────────────


def string_voltage(modules_in_series: Float64, vmp: Float64) -> Float64:
    """String voltage: V = n * Vmp.

    Args:
        modules_in_series: Number of modules in series.
        vmp: Voltage at maximum power per module (V).

    Returns:
        String voltage (V).
    """
    return modules_in_series * vmp
