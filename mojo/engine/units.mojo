"""
units.mojo — Physical unit conversion. Zero Python imports.

Replaces the pint library with pure Mojo conversion functions for
length, mass, temperature, time, area, volume, speed, and data units.

Public API:
  convert_length        — m, km, mi, ft, in, cm, mm, yd, nm
  convert_mass          — kg, g, mg, lb, oz, ton, st
  convert_temperature   — C, F, K
  convert_time          — s, ms, us, min, hr, day, week, year
  convert_area          — m2, km2, ft2, acre, hectare
  convert_volume        — L, mL, gal, qt, pt, cup, m3
  convert_speed         — m/s, km/h, mph, knot, ft/s
  convert_data          — B, KB, MB, GB, TB, PB
"""


# ── Length (base: meters) ─────────────────────────────────────────────────────


def _length_factor(unit: String) -> Float64:
    """Return metres-per-unit for the given length unit."""
    if unit == "m":
        return 1.0
    if unit == "km":
        return 1000.0
    if unit == "mi":
        return 1609.344
    if unit == "ft":
        return 0.3048
    if unit == "in":
        return 0.0254
    if unit == "cm":
        return 0.01
    if unit == "mm":
        return 0.001
    if unit == "yd":
        return 0.9144
    if unit == "nm":
        return 1852.0
    return 1.0


def convert_length(value: Float64, from_unit: String, to_unit: String) -> Float64:
    """Convert between length units."""
    return value * (_length_factor(from_unit) / _length_factor(to_unit))


# ── Mass (base: kilograms) ───────────────────────────────────────────────────


def _mass_factor(unit: String) -> Float64:
    """Return kg-per-unit for the given mass unit."""
    if unit == "kg":
        return 1.0
    if unit == "g":
        return 0.001
    if unit == "mg":
        return 0.000001
    if unit == "lb":
        return 0.45359237
    if unit == "oz":
        return 0.028349523125
    if unit == "ton":
        return 1000.0
    if unit == "st":
        return 6.35029318
    return 1.0


def convert_mass(value: Float64, from_unit: String, to_unit: String) -> Float64:
    """Convert between mass units."""
    return value * (_mass_factor(from_unit) / _mass_factor(to_unit))


# ── Temperature (special handling) ────────────────────────────────────────────


def _to_celsius(value: Float64, unit: String) -> Float64:
    """Convert any temperature unit to Celsius."""
    if unit == "C":
        return value
    if unit == "F":
        return (value - 32.0) * 5.0 / 9.0
    if unit == "K":
        return value - 273.15
    return value


def _from_celsius(value_c: Float64, unit: String) -> Float64:
    """Convert Celsius to any temperature unit."""
    if unit == "C":
        return value_c
    if unit == "F":
        return value_c * 9.0 / 5.0 + 32.0
    if unit == "K":
        return value_c + 273.15
    return value_c


def convert_temperature(
    value: Float64, from_unit: String, to_unit: String
) -> Float64:
    """Convert between temperature units (C, F, K)."""
    var celsius = _to_celsius(value, from_unit)
    return _from_celsius(celsius, to_unit)


# ── Time (base: seconds) ─────────────────────────────────────────────────────


def _time_factor(unit: String) -> Float64:
    """Return seconds-per-unit."""
    if unit == "s":
        return 1.0
    if unit == "ms":
        return 0.001
    if unit == "us":
        return 0.000001
    if unit == "min":
        return 60.0
    if unit == "hr":
        return 3600.0
    if unit == "day":
        return 86400.0
    if unit == "week":
        return 604800.0
    if unit == "year":
        return 31557600.0  # Julian year (365.25 days)
    return 1.0


def convert_time(value: Float64, from_unit: String, to_unit: String) -> Float64:
    """Convert between time units."""
    return value * (_time_factor(from_unit) / _time_factor(to_unit))


# ── Area (base: m²) ──────────────────────────────────────────────────────────


def _area_factor(unit: String) -> Float64:
    """Return m²-per-unit."""
    if unit == "m2":
        return 1.0
    if unit == "km2":
        return 1000000.0
    if unit == "ft2":
        return 0.09290304
    if unit == "acre":
        return 4046.8564224
    if unit == "hectare":
        return 10000.0
    return 1.0


def convert_area(value: Float64, from_unit: String, to_unit: String) -> Float64:
    """Convert between area units."""
    return value * (_area_factor(from_unit) / _area_factor(to_unit))


# ── Volume (base: litres) ────────────────────────────────────────────────────


def _volume_factor(unit: String) -> Float64:
    """Return litres-per-unit."""
    if unit == "L":
        return 1.0
    if unit == "mL":
        return 0.001
    if unit == "gal":
        return 3.785411784
    if unit == "qt":
        return 0.946352946
    if unit == "pt":
        return 0.473176473
    if unit == "cup":
        return 0.2365882365
    if unit == "m3":
        return 1000.0
    return 1.0


def convert_volume(
    value: Float64, from_unit: String, to_unit: String
) -> Float64:
    """Convert between volume units."""
    return value * (_volume_factor(from_unit) / _volume_factor(to_unit))


# ── Speed (base: m/s) ────────────────────────────────────────────────────────


def _speed_factor(unit: String) -> Float64:
    """Return (m/s)-per-unit."""
    if unit == "m/s":
        return 1.0
    if unit == "km/h":
        return 1000.0 / 3600.0  # 0.27778
    if unit == "mph":
        return 1609.344 / 3600.0  # 0.44704
    if unit == "knot":
        return 1852.0 / 3600.0  # 0.51444
    if unit == "ft/s":
        return 0.3048
    return 1.0


def convert_speed(
    value: Float64, from_unit: String, to_unit: String
) -> Float64:
    """Convert between speed units."""
    return value * (_speed_factor(from_unit) / _speed_factor(to_unit))


# ── Data (base: bytes, binary 1024) ──────────────────────────────────────────


def _data_factor(unit: String) -> Float64:
    """Return bytes-per-unit (binary, 1024-based)."""
    if unit == "B":
        return 1.0
    if unit == "KB":
        return 1024.0
    if unit == "MB":
        return 1048576.0
    if unit == "GB":
        return 1073741824.0
    if unit == "TB":
        return 1099511627776.0
    if unit == "PB":
        return 1125899906842624.0
    return 1.0


def convert_data(value: Float64, from_unit: String, to_unit: String) -> Float64:
    """Convert between data size units (binary 1024-based)."""
    return value * (_data_factor(from_unit) / _data_factor(to_unit))
