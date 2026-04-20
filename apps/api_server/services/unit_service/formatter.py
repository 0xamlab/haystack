"""
format_value — display a float with the correct unit formatting for every domain.
"""

from __future__ import annotations

import math
from datetime import date

from .registries import (
    AREA_TO_M2,
    CRYPTO_DISPLAY_DECIMALS,
    CURRENCY_PRECISION,
    CURRENCY_SYMBOLS,
    DATA_RATE_TO_BPS,
    DATA_SIZE_TO_BYTES,
    DURATION_TO_SECONDS,
    FREQUENCY_TO_HZ,
    LENGTH_TO_M,
    MASS_TO_KG,
    PRESSURE_TO_PA,
    SPEED_TO_MS,
    VOLUME_TO_L,
)
from .spec import UnitSpec

_EPOCH = date(1970, 1, 1)


def _compact(value: float, precision: int = 2) -> str:
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"{value / 1e12:.{precision}f}T"
    if abs_val >= 1e9:
        return f"{value / 1e9:.{precision}f}B"
    if abs_val >= 1e6:
        return f"{value / 1e6:.{precision}f}M"
    if abs_val >= 1e3:
        return f"{value / 1e3:.{precision}f}K"
    return f"{value:.{precision}f}"


def _epoch_days_to_iso(epoch_days: float) -> str:
    try:
        d = date.fromordinal(_EPOCH.toordinal() + int(round(epoch_days)))
        return d.isoformat()
    except (ValueError, OverflowError):
        return str(epoch_days)


def _format_duration(value: float, unit: str) -> str:
    seconds = value * DURATION_TO_SECONDS.get(unit.lower(), 1.0)
    if abs(seconds) < 0.001:
        return f"{seconds * 1e6:.2f} μs"
    if abs(seconds) < 1.0:
        return f"{seconds * 1000:.2f} ms"
    if abs(seconds) < 120:
        return f"{seconds:.2f} s"
    if abs(seconds) < 7200:
        return f"{seconds / 60:.2f} min"
    if abs(seconds) < 172800:
        return f"{seconds / 3600:.2f} h"
    if abs(seconds) < 730 * 86400:
        return f"{seconds / 86400:.2f} days"
    return f"{seconds / 31536000:.2f} years"


def format_value(value: float, unit_spec: UnitSpec) -> str:  # noqa: C901
    """Format a single float value with the given unit spec."""
    if not math.isfinite(value):
        return str(value)

    utype = unit_spec.type
    code = unit_spec.code
    prec = unit_spec.precision
    fmt = unit_spec.format
    scale = unit_spec.scale
    label = unit_spec.label
    dv = value * scale

    if utype == "currency":
        symbol = CURRENCY_SYMBOLS.get(code.upper(), code + " ")
        p = prec if prec is not None else CURRENCY_PRECISION.get(code.upper(), 2)
        return symbol + (_compact(dv, p) if fmt == "compact" else f"{dv:,.{p}f}")

    if utype == "crypto":
        p = prec if prec is not None else CRYPTO_DISPLAY_DECIMALS.get(code.upper(), 6)
        return f"{dv:.{min(p, 4)}g} {code}" if fmt == "compact" else f"{dv:.{p}f} {code}"

    if utype == "crypto_sub":
        sub_label = unit_spec.base_unit or code
        p = prec if prec is not None else 0
        return f"{dv:,.{max(0, p)}f} {sub_label}" if dv >= 1e6 else f"{dv:.{p}f} {sub_label}"

    if utype == "percentage":
        p = prec if prec is not None else 2
        suffix = f" {label}" if label else ""
        return f"{dv:.{p}f}%{suffix}"

    if utype == "bps":
        return f"{dv:.{prec if prec is not None else 1}f} bps"

    if utype == "probability":
        return f"{dv:.{prec if prec is not None else 4}f}"

    if utype == "count":
        return f"{int(round(dv)):,}"

    if utype == "date":
        return _epoch_days_to_iso(dv)

    if utype == "duration":
        return _format_duration(dv, code)

    if utype == "six_sigma":
        return f"{label or code} = {dv:.{prec if prec is not None else 2}f}"

    if utype == "dpmo":
        return f"{dv:,.0f} DPMO"

    if utype == "ppm_defect":
        return f"{dv:.{prec if prec is not None else 2}f} ppm"

    if utype == "oee":
        return f"{dv:.{prec if prec is not None else 1}f}% OEE"

    if utype in ("mtbf", "mttr"):
        return f"{label or code} = {dv:.{prec if prec is not None else 1}f} h"

    if utype == "medical_stat":
        p = prec if prec is not None else 2
        lbl = label or code
        if lbl in ("NNT", "NNH"):
            return f"{lbl} = {dv:.{max(0, p - 1)}f}"
        return f"{lbl} {dv:.{p}f}"

    if utype == "p_value":
        if dv < 0.001:
            return "p < 0.001"
        if dv < 0.05:
            return f"p = {dv:.3f}"
        return f"p = {dv:.2f}"

    if utype == "concentration":
        p = prec if prec is not None else 3
        abs_dv = abs(dv)
        if abs_dv > 0 and (abs_dv < 0.001 or abs_dv >= 1e6):
            return f"{dv:.{p}e} {code}"
        return f"{dv:.{p}f} {code}"

    if utype == "pharma":
        p = prec if prec is not None else 3
        lbl = label or code
        return f"{dv:.{p}e} {lbl}" if abs(dv) > 0 and abs(dv) < 0.001 else f"{dv:.{p}f} {lbl}"

    if utype == "half_life":
        return f"t½ = {dv:.{prec if prec is not None else 2}f} h"

    if utype == "aerospace":
        return f"{dv:.{prec if prec is not None else 2}f} {label or code}"

    if utype == "radiation":
        return f"{dv:.{prec if prec is not None else 3}f} {code}"

    if utype in ("energy", "power", "fuel"):
        p = prec if prec is not None else 2
        return _compact(dv, p) + f" {code}" if fmt == "compact" else f"{dv:,.{p}f} {code}"

    if utype == "carbon":
        p = prec if prec is not None else 2
        return _compact(dv, p) + f" {code}" if fmt == "compact" else f"{dv:,.{p}f} {code}"

    if utype in ("ppm_conc", "ppb_conc"):
        return f"{dv:.{prec if prec is not None else 3}f} {code}"

    if utype == "ph":
        return f"pH {dv:.{prec if prec is not None else 2}f}"

    if utype in ("real_estate", "actuarial"):
        p = prec if prec is not None else 2
        lbl = label or ""
        return f"{dv:.{p}f}% {lbl}".strip() if code == "%" else f"{dv:.{p}f}{code} {lbl}".strip()

    if utype == "ratio":
        return f"{dv:.{prec if prec is not None else 2}f}× {label or ''}".strip()

    if utype == "financial_ratio":
        return f"{label or code} {dv:.{prec if prec is not None else 2}f}"

    if utype == "mass":
        p = prec if prec is not None else 3
        kg_val = dv * MASS_TO_KG.get(code.lower(), 1.0)
        if fmt == "compact":
            if kg_val >= 1e6:
                return f"{kg_val / 1e6:.{p}f} Mt"
            if kg_val >= 1e3:
                return f"{kg_val / 1e3:.{p}f} t"
            if kg_val >= 1.0:
                return f"{kg_val:.{p}f} kg"
            if kg_val >= 1e-3:
                return f"{kg_val * 1e3:.{p}f} g"
            if kg_val >= 1e-6:
                return f"{kg_val * 1e6:.{p}f} mg"
            return f"{kg_val * 1e9:.{p}f} μg"
        return f"{dv:.{p}f} {code}"

    if utype == "length":
        p = prec if prec is not None else 3
        m_val = dv * LENGTH_TO_M.get(code.lower(), LENGTH_TO_M.get(code, 1.0))
        if fmt == "compact":
            if m_val >= 1e3:
                return f"{m_val / 1e3:.{p}f} km"
            if m_val >= 1.0:
                return f"{m_val:.{p}f} m"
            if m_val >= 1e-2:
                return f"{m_val * 100:.{p}f} cm"
            if m_val >= 1e-3:
                return f"{m_val * 1000:.{p}f} mm"
            if m_val >= 1e-6:
                return f"{m_val * 1e6:.{p}f} μm"
            if m_val >= 1e-9:
                return f"{m_val * 1e9:.{p}f} nm"
            return f"{m_val:.{p}e} m"
        return f"{dv:.{p}f} {code}"

    if utype == "area":
        p = prec if prec is not None else 2
        m2_val = dv * AREA_TO_M2.get(code.lower(), AREA_TO_M2.get(code, 1.0))
        if fmt == "compact":
            if m2_val >= 1e6:
                return f"{m2_val / 1e6:.{p}f} km²"
            if m2_val >= 1e4:
                return f"{m2_val / 1e4:.{p}f} ha"
            return f"{m2_val:.{p}f} m²"
        return f"{dv:.{p}f} {code}"

    if utype == "volume":
        p = prec if prec is not None else 3
        l_val = dv * VOLUME_TO_L.get(code.lower(), VOLUME_TO_L.get(code, 1.0))
        if fmt == "compact":
            if l_val >= 1e3:
                return f"{l_val / 1e3:.{p}f} m³"
            if l_val >= 1.0:
                return f"{l_val:.{p}f} L"
            if l_val >= 0.001:
                return f"{l_val * 1000:.{p}f} mL"
            return f"{l_val * 1e6:.{p}f} μL"
        return f"{dv:.{p}f} {code}"

    if utype == "density":
        return f"{dv:.{prec if prec is not None else 3}f} {code}"

    if utype == "pressure":
        p = prec if prec is not None else 2
        pa_val = dv * PRESSURE_TO_PA.get(code.lower(), PRESSURE_TO_PA.get(code, 1.0))
        if fmt == "compact":
            if pa_val >= 1e9:
                return f"{pa_val / 1e9:.{p}f} GPa"
            if pa_val >= 1e6:
                return f"{pa_val / 1e6:.{p}f} MPa"
            if pa_val >= 1e3:
                return f"{pa_val / 1e3:.{p}f} kPa"
            if pa_val >= 1e2:
                return f"{pa_val / 1e5:.{p}f} bar"
            return f"{pa_val:.{p}f} Pa"
        return f"{dv:.{p}f} {code}"

    if utype in ("force", "torque"):
        return f"{dv:.{prec if prec is not None else 2}f} {code}"

    if utype == "data_size":
        p = prec if prec is not None else 2
        if fmt == "compact" or code.lower() in ("b", "byte", "bytes"):
            b = dv * DATA_SIZE_TO_BYTES.get(code.lower(), DATA_SIZE_TO_BYTES.get(code, 1.0))
            if b >= 1e15:
                return f"{b / 1e15:.{p}f} PB"
            if b >= 1e12:
                return f"{b / 1e12:.{p}f} TB"
            if b >= 1e9:
                return f"{b / 1e9:.{p}f} GB"
            if b >= 1e6:
                return f"{b / 1e6:.{p}f} MB"
            if b >= 1e3:
                return f"{b / 1e3:.{p}f} KB"
            return f"{b:.0f} B"
        return f"{dv:.{p}f} {code}"

    if utype == "data_rate":
        p = prec if prec is not None else 1
        if fmt == "compact":
            bps = dv * DATA_RATE_TO_BPS.get(code.lower(), DATA_RATE_TO_BPS.get(code, 1.0))
            if bps >= 1e12:
                return f"{bps / 1e12:.{p}f} Tbps"
            if bps >= 1e9:
                return f"{bps / 1e9:.{p}f} Gbps"
            if bps >= 1e6:
                return f"{bps / 1e6:.{p}f} Mbps"
            if bps >= 1e3:
                return f"{bps / 1e3:.{p}f} Kbps"
            return f"{bps:.{p}f} bps"
        return f"{dv:.{p}f} {code}"

    if utype == "frequency":
        p = prec if prec is not None else 3
        if fmt == "compact":
            hz = dv * FREQUENCY_TO_HZ.get(code.lower(), FREQUENCY_TO_HZ.get(code, 1.0))
            if hz >= 1e12:
                return f"{hz / 1e12:.{p}f} THz"
            if hz >= 1e9:
                return f"{hz / 1e9:.{p}f} GHz"
            if hz >= 1e6:
                return f"{hz / 1e6:.{p}f} MHz"
            if hz >= 1e3:
                return f"{hz / 1e3:.{p}f} kHz"
            return f"{hz:.{p}f} Hz"
        return f"{dv:.{p}f} {code}"

    if utype == "rate":
        return f"{dv:.{prec if prec is not None else 3}g} {code}"

    if utype == "speed":
        p = prec if prec is not None else 1
        lbl = code or "m/s"
        if fmt == "compact":
            ms = dv * SPEED_TO_MS.get(lbl.lower(), 1.0)
            if ms >= 340:
                return f"{ms / 340.29:.2f} Mach"
            if ms >= 50:
                return f"{ms * 3.6:.1f} km/h"
            return f"{ms:.2f} m/s"
        return f"{dv:.{p}f} {lbl}"

    if utype == "angular":
        p = prec if prec is not None else 2
        lbl = code or label or "°"
        if lbl == "rpm":
            return f"{dv:,.{p}f} rpm"
        if lbl == "rad/s":
            return f"{dv:.{p}f} rad/s"
        if "°" in lbl or lbl == "deg":
            return f"{dv % 360.0:.{p}f}°"
        return f"{dv:.{p}f} {lbl}"

    if utype == "temperature":
        return f"{dv:.{prec if prec is not None else 1}f} {code}"

    if utype == "sports":
        p = prec if prec is not None else 1
        lbl = label or code or ""
        if lbl.startswith("lap") or lbl.startswith("sector"):
            if dv >= 60:
                mins = int(dv // 60)
                secs = dv - mins * 60
                return f"{mins}:{secs:06.3f} ({lbl})"
            return f"{dv:.3f} s ({lbl})"
        if code == "ELO" or lbl == "ELO":
            return f"ELO {dv:,.0f}"
        if code == "pts":
            return f"{dv:.{p}f} pts"
        return f"{dv:.{p}f} {lbl}".strip()

    if utype == "coordinate":
        p = prec if prec is not None else 4
        lbl = label or ""
        if lbl == "lat":
            ns = "N" if dv >= 0 else "S"
            return f"{abs(dv):.{p}f}° {ns}"
        if lbl == "lon":
            ew = "E" if dv >= 0 else "W"
            return f"{abs(dv):.{p}f}° {ew}"
        return f"{dv:.{p}f} {code}".strip()

    if utype in ("si", "scientific"):
        p = prec if prec is not None else 4
        abs_dv = abs(dv)
        if fmt == "scientific" or (abs_dv > 0 and (abs_dv < 1e-3 or abs_dv >= 1e9)):
            return f"{dv:.{p}e} {code}".strip()
        return f"{dv:.{p}g} {code}".strip()

    p = prec if prec is not None else 4
    lbl = code or label or ""
    abs_dv = abs(dv)
    if abs_dv > 0 and (abs_dv < 1e-3 or abs_dv >= 1e9):
        return f"{dv:.{p}e} {lbl}".strip()
    return f"{dv:.{p}g} {lbl}".strip()
