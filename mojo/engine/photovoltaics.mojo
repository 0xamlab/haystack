"""
photovoltaics.mojo — Solar photovoltaic system calculations. Zero Python imports.

Public API:
  cell_efficiency              — η = P_max / (G * A)
  fill_factor                  — FF = P_max / (Voc * Isc)
  power_output                 — P = η * G * A
  temperature_coefficient      — dP/dT correction
  energy_yield                 — kWh/kWp from performance ratio
  irradiance_on_tilted_plane   — POA from horizontal irradiance
  lcoe_solar                   — levelized cost of energy
  capacity_factor              — actual / theoretical max output
  peak_sun_hours               — PSH from daily irradiance
  system_pr                    — performance ratio
"""
from std.math import cos, exp


def cell_efficiency(p_max: Float64, irradiance: Float64, area: Float64) -> Float64:
    """PV cell efficiency: η = P_max / (G·A).

    Args:
        p_max: Maximum power output (W).
        irradiance: Incident irradiance (W/m²).
        area: Cell/module area (m²).

    Returns:
        Efficiency (fraction 0–1).
    """
    if irradiance <= 0.0 or area <= 0.0:
        return 0.0
    return p_max / (irradiance * area)


def fill_factor(p_max: Float64, voc: Float64, isc: Float64) -> Float64:
    """Fill factor of a solar cell.

    FF = P_max / (Voc · Isc)

    Args:
        p_max: Maximum power (W).
        voc: Open-circuit voltage (V).
        isc: Short-circuit current (A).

    Returns:
        Fill factor (0–1).
    """
    if voc <= 0.0 or isc <= 0.0:
        return 0.0
    return p_max / (voc * isc)


def power_output(
    efficiency: Float64, irradiance: Float64, area: Float64
) -> Float64:
    """PV system power output: P = η·G·A.

    Args:
        efficiency: Module efficiency (fraction).
        irradiance: Plane-of-array irradiance (W/m²).
        area: Total module area (m²).

    Returns:
        Power (W).
    """
    return efficiency * irradiance * area


def temperature_coefficient(
    p_stc: Float64, gamma: Float64, cell_temp: Float64
) -> Float64:
    """Temperature-corrected power output.

    P(T) = P_STC · (1 + γ·(T - 25))

    Args:
        p_stc: Power at STC (W, 25°C, 1000 W/m²).
        gamma: Power temperature coefficient (per °C, typically -0.004 to -0.005).
        cell_temp: Actual cell temperature (°C).

    Returns:
        Temperature-corrected power (W).
    """
    return p_stc * (1.0 + gamma * (cell_temp - 25.0))


def energy_yield(peak_power_kw: Float64, peak_sun_hours: Float64, pr: Float64) -> Float64:
    """Annual energy yield.

    E = P_peak · PSH · PR · 365

    Args:
        peak_power_kw: System peak power (kWp).
        peak_sun_hours: Daily peak sun hours (h/day).
        pr: Performance ratio (0–1).

    Returns:
        Annual energy yield (kWh/yr).
    """
    return peak_power_kw * peak_sun_hours * pr * 365.0


def irradiance_on_tilted_plane(
    g_horizontal: Float64, tilt_rad: Float64, sun_zenith_rad: Float64
) -> Float64:
    """Global irradiance on a tilted surface (simplified).

    Args:
        g_horizontal: Global horizontal irradiance (W/m²).
        tilt_rad: Panel tilt angle from horizontal (rad).
        sun_zenith_rad: Solar zenith angle (rad).

    Returns:
        Plane-of-array irradiance estimate (W/m²).
    """
    if g_horizontal <= 0.0:
        return 0.0
    var cos_incidence = cos(tilt_rad) * cos(sun_zenith_rad)
    if cos_incidence < 0.0:
        return 0.0
    return g_horizontal * cos_incidence / (cos(sun_zenith_rad) + 1e-10)


def lcoe_solar(
    capex: Float64, opex_annual: Float64, energy_annual: Float64,
    lifetime_years: Float64, discount_rate: Float64
) -> Float64:
    """Levelized cost of energy for a solar PV system.

    Args:
        capex: Capital expenditure (USD).
        opex_annual: Annual operating cost (USD/yr).
        energy_annual: Annual energy production (kWh/yr).
        lifetime_years: System lifetime (years).
        discount_rate: Discount rate (fraction, e.g. 0.05).

    Returns:
        LCOE (USD/kWh).
    """
    if energy_annual <= 0.0 or lifetime_years <= 0.0:
        return 0.0
    # CRF = r(1+r)^n / ((1+r)^n - 1)
    var r = discount_rate
    var n = lifetime_years
    var crf: Float64
    if r <= 0.0:
        crf = 1.0 / n
    else:
        var rn = (1.0 + r) ** n
        crf = r * rn / (rn - 1.0)
    var total_cost = capex * crf + opex_annual
    return total_cost / energy_annual


def capacity_factor(
    actual_energy: Float64, installed_kw: Float64, hours: Float64
) -> Float64:
    """Capacity factor of a solar installation.

    CF = actual_energy / (P_installed · hours)

    Args:
        actual_energy: Actual energy produced (kWh).
        installed_kw: Installed capacity (kW).
        hours: Time period (h).

    Returns:
        Capacity factor (0–1).
    """
    var theoretical = installed_kw * hours
    if theoretical <= 0.0:
        return 0.0
    return actual_energy / theoretical


def peak_sun_hours(daily_irradiation: Float64) -> Float64:
    """Peak sun hours from daily irradiation.

    PSH = H / 1000 W/m²

    Args:
        daily_irradiation: Daily solar irradiation (Wh/m²/day).

    Returns:
        Peak sun hours (h/day).
    """
    return daily_irradiation / 1000.0


def system_pr(
    actual_yield: Float64, reference_yield: Float64
) -> Float64:
    """Performance ratio of a PV system.

    PR = Ya / Yr

    Args:
        actual_yield: Actual system yield (kWh/kWp).
        reference_yield: Reference yield = irradiation/1kW (h).

    Returns:
        Performance ratio (0–1).
    """
    if reference_yield <= 0.0:
        return 0.0
    return actual_yield / reference_yield
