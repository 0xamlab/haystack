"""
meteorology.mojo — Atmospheric science calculations. Zero Python imports.

Public API:
  dew_point                — Td from T and relative humidity
  wet_bulb_temperature     — Tw approximation from T and RH
  pressure_altitude        — altitude from barometric pressure
  relative_humidity        — RH from T and Td
  absolute_humidity        — water vapour density (g/m³)
  wind_chill               — wind chill index (°C)
  heat_index               — apparent temperature (°C)
  potential_temperature    — θ = T*(P0/P)^(R/cp)
  precipitable_water       — integrated column water (mm)
  visibility_extinction    — Beer-Lambert extinction of visibility
"""
from std.math import atan, exp, log, pow, sqrt


def dew_point(temperature: Float64, relative_humidity: Float64) -> Float64:
    """Dew point temperature using Magnus formula.

    Args:
        temperature: Air temperature (°C).
        relative_humidity: Relative humidity (0–100 %).

    Returns:
        Dew point temperature (°C).
    """
    if relative_humidity <= 0.0:
        return temperature - 50.0
    var a = 17.27
    var b = 237.7
    var alpha = a * temperature / (b + temperature) + log(relative_humidity / 100.0)
    return b * alpha / (a - alpha)


def wet_bulb_temperature(temperature: Float64, relative_humidity: Float64) -> Float64:
    """Wet-bulb temperature approximation (Stull 2011).

    Args:
        temperature: Dry-bulb temperature (°C).
        relative_humidity: Relative humidity (0–100 %).

    Returns:
        Wet-bulb temperature (°C).
    """
    if relative_humidity < 0.0 or relative_humidity > 100.0:
        return temperature
    var rh = relative_humidity
    # Stull (2011), J. Appl. Meteor. Climatol. 50:2267, eq. 1 — T in °C, RH in %.
    return (temperature * atan(0.151977 * sqrt(rh + 8.313659))
            + atan(temperature + rh)
            - atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * atan(0.023101 * rh)
            - 4.686035)


def pressure_altitude(pressure_pa: Float64) -> Float64:
    """Pressure altitude from ambient pressure using ISA model.

    Args:
        pressure_pa: Ambient pressure (Pa).

    Returns:
        Pressure altitude (m).
    """
    var p0 = 101325.0  # sea-level standard pressure Pa
    if pressure_pa <= 0.0:
        return 0.0
    return 44330.0 * (1.0 - (pressure_pa / p0) ** (1.0 / 5.255))


def relative_humidity(temperature: Float64, dew_point_temp: Float64) -> Float64:
    """Relative humidity from temperature and dew point.

    Args:
        temperature: Air temperature (°C).
        dew_point_temp: Dew point temperature (°C).

    Returns:
        Relative humidity (%).
    """
    var a = 17.27
    var b = 237.7
    var es_t  = exp(a * temperature / (b + temperature))
    var es_td = exp(a * dew_point_temp / (b + dew_point_temp))
    if es_t <= 0.0:
        return 0.0
    return 100.0 * es_td / es_t


def absolute_humidity(temperature: Float64, relative_humidity: Float64) -> Float64:
    """Absolute humidity (water vapour density).

    Args:
        temperature: Air temperature (°C).
        relative_humidity: Relative humidity (0–100 %).

    Returns:
        Absolute humidity (g/m³).
    """
    var a = 17.27
    var b = 237.7
    var es = 6.1078 * exp(a * temperature / (b + temperature))  # hPa
    var e = es * relative_humidity / 100.0
    var tk = temperature + 273.15
    return 216.7 * e / tk


def wind_chill(temperature: Float64, wind_speed_kmh: Float64) -> Float64:
    """Wind chill index (Environment Canada formula).

    Args:
        temperature: Air temperature (°C, valid ≤ 10°C).
        wind_speed_kmh: Wind speed at 10 m height (km/h, ≥ 5).

    Returns:
        Wind chill equivalent temperature (°C).
    """
    if wind_speed_kmh < 5.0:
        return temperature
    var v016 = wind_speed_kmh ** 0.16
    return 13.12 + 0.6215 * temperature - 11.37 * v016 + 0.3965 * temperature * v016


def heat_index(temperature: Float64, relative_humidity: Float64) -> Float64:
    """Heat index (apparent temperature) using Rothfusz equation.

    Args:
        temperature: Air temperature (°C).
        relative_humidity: Relative humidity (%).

    Returns:
        Heat index (°C).
    """
    var t = temperature
    var r = relative_humidity
    return (-8.78469475556
            + 1.61139411 * t
            + 2.33854883889 * r
            - 0.14611605 * t * r
            - 0.012308094 * t * t
            - 0.0164248277778 * r * r
            + 0.002211732 * t * t * r
            + 0.00072546 * t * r * r
            - 0.000003582 * t * t * r * r)


def potential_temperature(temperature_k: Float64, pressure_pa: Float64) -> Float64:
    """Potential temperature (Poisson formula).

    θ = T * (P0/P)^(R/cp)

    Args:
        temperature_k: Absolute temperature (K).
        pressure_pa: Ambient pressure (Pa).

    Returns:
        Potential temperature (K).
    """
    var p0 = 100000.0  # reference pressure Pa
    if pressure_pa <= 0.0:
        return temperature_k
    return temperature_k * (p0 / pressure_pa) ** 0.2854


def precipitable_water(
    surface_humidity: Float64, scale_height: Float64
) -> Float64:
    """Column precipitable water (exponential humidity profile).

    Args:
        surface_humidity: Surface absolute humidity (g/m³).
        scale_height: Humidity scale height (m).

    Returns:
        Precipitable water (mm).
    """
    if scale_height <= 0.0:
        return 0.0
    return surface_humidity * scale_height / 1000.0


def visibility_extinction(
    extinction_coeff: Float64, path_length: Float64
) -> Float64:
    """Meteorological visibility using Beer-Lambert law.

    Args:
        extinction_coeff: Atmospheric extinction coefficient (km⁻¹).
        path_length: Path length (km).

    Returns:
        Transmission fraction (0–1).
    """
    if extinction_coeff < 0.0 or path_length < 0.0:
        return 1.0
    return exp(-extinction_coeff * path_length)
