"""
unit_convert — cross-unit conversion engine.
validate_unit_compatibility — check if two units are in the same physical dimension.
"""

from __future__ import annotations

from .registries import (
    AREA_TO_M2,
    DATA_RATE_TO_BPS,
    DATA_SIZE_TO_BYTES,
    DURATION_TO_SECONDS,
    ENERGY_TO_KWH,
    FORCE_TO_N,
    FREQUENCY_TO_HZ,
    LENGTH_TO_M,
    MASS_TO_KG,
    PRESSURE_TO_PA,
    SPEED_TO_MS,
    VOLUME_TO_L,
)

_CONVERSION_TABLES: dict[str, dict[str, float]] = {
    "mass": MASS_TO_KG,
    "length": LENGTH_TO_M,
    "area": AREA_TO_M2,
    "volume": VOLUME_TO_L,
    "pressure": PRESSURE_TO_PA,
    "force": FORCE_TO_N,
    "data_size": DATA_SIZE_TO_BYTES,
    "data_rate": DATA_RATE_TO_BPS,
    "frequency": FREQUENCY_TO_HZ,
    "speed": SPEED_TO_MS,
    "duration": DURATION_TO_SECONDS,
    "energy": ENERGY_TO_KWH,
}

_UNIT_CATEGORY_MAP: dict[str, str] = {}
for _cat, _tbl in _CONVERSION_TABLES.items():
    for _unit in _tbl:
        _UNIT_CATEGORY_MAP[_unit.lower()] = _cat

_TEMP_ALIASES = {
    "°c": "c",
    "celsius": "c",
    "c_temp": "c",
    "°f": "f",
    "fahrenheit": "f",
    "f_temp": "f",
    "k": "k",
    "kelvin": "k",
    "°k": "k",
    "°r": "r",
    "rankine": "r",
}


def unit_convert(value: float, from_unit: str, to_unit: str) -> float:
    """
    Convert a numeric value from one unit to another within the same physical dimension.

    Supported dimensions: mass, length, area, volume, pressure, force,
    data_size, data_rate, frequency, speed, duration, energy.
    Also: temperature (°C ↔ °F ↔ K ↔ °R).

    Raises ValueError for unrecognized or incompatible units.

    Examples:
      unit_convert(70, 'kg', 'lb')       → 154.32
      unit_convert(100, 'km/h', 'm/s')   → 27.78
      unit_convert(36.6, '°C', 'K')      → 309.75
      unit_convert(1, 'GiB', 'MiB')      → 1024.0
      unit_convert(1, 'atm', 'psi')      → 14.696
    """
    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    if fu == tu:
        return value

    # ── Temperature (non-linear) ──────────────────────────────────────────────
    if fu in _TEMP_ALIASES and tu in _TEMP_ALIASES:
        fn = _TEMP_ALIASES[fu]
        tn = _TEMP_ALIASES[tu]
        to_k = {
            "c": value + 273.15,
            "f": (value + 459.67) * 5 / 9,
            "k": value,
            "r": value * 5 / 9,
        }
        k = to_k.get(fn, value)
        from_k = {
            "c": k - 273.15,
            "f": k * 9 / 5 - 459.67,
            "k": k,
            "r": k * 9 / 5,
        }
        return from_k.get(tn, k)

    # ── Linear conversion via SI base ─────────────────────────────────────────
    from_cat = _UNIT_CATEGORY_MAP.get(fu, _UNIT_CATEGORY_MAP.get(from_unit))
    to_cat = _UNIT_CATEGORY_MAP.get(tu, _UNIT_CATEGORY_MAP.get(to_unit))

    if from_cat is None:
        raise ValueError(f"Cannot convert '{from_unit}': unit not recognized.")
    if to_cat is None:
        raise ValueError(f"Cannot convert '{to_unit}': unit not recognized.")
    if from_cat != to_cat:
        raise ValueError(
            f"Cannot convert '{from_unit}' ({from_cat}) → '{to_unit}' ({to_cat}): "
            "incompatible physical dimensions."
        )

    tbl = _CONVERSION_TABLES[from_cat]
    to_si = tbl.get(fu, tbl.get(from_unit, 1.0))
    fr_si = tbl.get(tu, tbl.get(to_unit, 1.0))
    return value * to_si / fr_si


def validate_unit_compatibility(from_unit: str, to_unit: str) -> tuple[bool, str]:
    """
    Check if two units belong to the same physical dimension.
    Returns (is_compatible, message).

    Examples:
      validate_unit_compatibility('kg', 'lb')  → (True, 'mass: kg → lb')
      validate_unit_compatibility('kg', 'm')   → (False, 'incompatible: ...')
      validate_unit_compatibility('°C', 'K')   → (True, 'temperature: °C → K')
    """
    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    if fu in _TEMP_ALIASES and tu in _TEMP_ALIASES:
        return True, f"temperature: {from_unit} → {to_unit}"

    from_cat = _UNIT_CATEGORY_MAP.get(fu, _UNIT_CATEGORY_MAP.get(from_unit))
    to_cat = _UNIT_CATEGORY_MAP.get(tu, _UNIT_CATEGORY_MAP.get(to_unit))

    if from_cat is None:
        return False, f"'{from_unit}' is not a recognized unit"
    if to_cat is None:
        return False, f"'{to_unit}' is not a recognized unit"
    if from_cat != to_cat:
        return False, f"incompatible: {from_unit} is {from_cat}, {to_unit} is {to_cat}"
    return True, f"{from_cat}: {from_unit} → {to_unit}"
