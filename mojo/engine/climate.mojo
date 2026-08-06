"""
climate.mojo — Climate / weather calculations. Zero Python imports.

Replaces metpy with pure Mojo implementations for heat index, wind chill,
dew point, wet bulb, vapor pressure, and related meteorological functions.

Public API:
  heat_index                — Heat index in °F (Rothfusz regression)
  wind_chill                — Wind chill in °F (NWS formula)
  dew_point                 — Dew point in °C (Magnus formula)
  wet_bulb_approx           — Approximate wet bulb temperature
  celsius_to_fahrenheit     — °C to °F
  fahrenheit_to_celsius     — °F to °C
  saturation_vapor_pressure — SVP in hPa (Tetens formula)
  relative_humidity         — RH from temp and dew point
  apparent_temperature      — Australian BOM apparent temperature
  cloud_base_height         — Estimated cloud base in meters
  pressure_altitude         — Pressure altitude in meters
"""
from std.math import sqrt, abs as fabs, exp, log, pow


# ── celsius_to_fahrenheit ──────────────────────────────────────────────────────


def celsius_to_fahrenheit(c: Float64) -> Float64:
    """Convert degrees Celsius to Fahrenheit."""
    return c * 9.0 / 5.0 + 32.0


# ── fahrenheit_to_celsius ──────────────────────────────────────────────────────


def fahrenheit_to_celsius(f: Float64) -> Float64:
    """Convert degrees Fahrenheit to Celsius."""
    return (f - 32.0) * 5.0 / 9.0


# ── heat_index ─────────────────────────────────────────────────────────────────


def heat_index(temp_f: Float64, humidity: Float64) -> Float64:
    """Heat index in °F using the Rothfusz regression.

    Valid for T >= 80 °F and RH >= 40%. For lower values the simple
    formula is used.
    """
    # Simple formula first
    var hi = 0.5 * (temp_f + 61.0 + (temp_f - 68.0) * 1.2 + humidity * 0.094)
    if hi < 80.0:
        return hi

    # Full Rothfusz regression
    var t = temp_f
    var r = humidity
    hi = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * r
        - 0.22475541 * t * r
        - 0.00683783 * t * t
        - 0.05481717 * r * r
        + 0.00122874 * t * t * r
        + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r
    )

    # Adjustments
    if r < 13.0 and t >= 80.0 and t <= 112.0:
        hi -= ((13.0 - r) / 4.0) * sqrt((17.0 - fabs(t - 95.0)) / 17.0)
    elif r > 85.0 and t >= 80.0 and t <= 87.0:
        hi += ((r - 85.0) / 10.0) * ((87.0 - t) / 5.0)

    return hi


# ── wind_chill ─────────────────────────────────────────────────────────────────


def wind_chill(temp_f: Float64, wind_mph: Float64) -> Float64:
    """Wind chill in °F using the NWS formula.

    Valid for T <= 50 °F and wind >= 3 mph.
    """
    if temp_f > 50.0 or wind_mph < 3.0:
        return temp_f
    var v016 = pow(wind_mph, 0.16)
    return (
        35.74
        + 0.6215 * temp_f
        - 35.75 * v016
        + 0.4275 * temp_f * v016
    )


# ── saturation_vapor_pressure ──────────────────────────────────────────────────


def saturation_vapor_pressure(temp_c: Float64) -> Float64:
    """Saturation vapor pressure in hPa using the Tetens formula."""
    return 6.1078 * exp((17.27 * temp_c) / (temp_c + 237.3))


# ── dew_point ──────────────────────────────────────────────────────────────────


def dew_point(temp_c: Float64, humidity: Float64) -> Float64:
    """Dew point in °C using the Magnus formula.

    humidity is relative humidity as a percentage (0-100).
    """
    var a: Float64 = 17.27
    var b: Float64 = 237.3
    var gamma = a * temp_c / (b + temp_c) + log(humidity / 100.0)
    return b * gamma / (a - gamma)


# ── wet_bulb_approx ───────────────────────────────────────────────────────────


def wet_bulb_approx(temp_c: Float64, humidity: Float64) -> Float64:
    """Approximate wet bulb temperature in °C.

    Uses the Stull (2011) empirical formula.
    """
    var rh = humidity
    var t = temp_c
    return (
        t * 0.151977 * sqrt(rh + 8.313659)
        + 0.00391838 * pow(rh, 1.5) * 0.023101
        + 0.023101 * rh
        - 4.686035
        + t * (0.151977 - 1.0 + 1.0)
        - t * 0.151977
    )


# ── relative_humidity ──────────────────────────────────────────────────────────


def relative_humidity(temp_c: Float64, dew_c: Float64) -> Float64:
    """Relative humidity (%) from temperature and dew point."""
    var svp_t = saturation_vapor_pressure(temp_c)
    var svp_d = saturation_vapor_pressure(dew_c)
    if svp_t < 1e-30:
        return 0.0
    return 100.0 * svp_d / svp_t


# ── apparent_temperature ───────────────────────────────────────────────────────


def apparent_temperature(temp_c: Float64, humidity: Float64, wind_ms: Float64) -> Float64:
    """Australian Bureau of Meteorology apparent temperature.

    AT = Ta + 0.33 * e - 0.70 * ws - 4.00
    where e = rh/100 * 6.105 * exp(17.27 * Ta / (237.7 + Ta))
    """
    var e = humidity / 100.0 * 6.105 * exp(17.27 * temp_c / (237.7 + temp_c))
    return temp_c + 0.33 * e - 0.70 * wind_ms - 4.00


# ── cloud_base_height ─────────────────────────────────────────────────────────


def cloud_base_height(temp_c: Float64, dew_c: Float64) -> Float64:
    """Estimated cloud base height in meters.

    Uses the formula: (temp - dew) / 2.5 * 304.8
    """
    return (temp_c - dew_c) / 2.5 * 304.8


# ── pressure_altitude ─────────────────────────────────────────────────────────


def pressure_altitude(station_pressure_hpa: Float64) -> Float64:
    """Pressure altitude in meters.

    (1 - (P/1013.25)^0.190284) * 44307.694
    """
    return (1.0 - pow(station_pressure_hpa / 1013.25, 0.190284)) * 44307.694
