"""
Variable preprocessing (date→epoch, crypto scaling) and validation warnings.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .spec import UnitSpec

# No external crypto registry needed — validation uses spec.type directly


_EPOCH = date(1970, 1, 1)


def _date_to_epoch_days(s: str | float) -> float:
    if isinstance(s, int | float):
        return float(s)
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            return float((d - _EPOCH).days)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.timestamp() / 86400.0
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return 0.0


def preprocess_variable(var: dict[str, Any], unit_spec: UnitSpec) -> dict[str, Any]:
    """Normalize variable params before sending to Mojo simulation engine."""
    params = dict(var.get("params", {}))
    utype  = unit_spec.type

    if utype == "date":
        for key in ("mean", "mode", "low", "high", "likely", "value"):
            if key in params and isinstance(params[key], str):
                params[key] = _date_to_epoch_days(params[key])

    elif unit_spec.sim_scale not in (1.0, 0.0):
        for key in ("mean", "mode", "low", "high", "likely", "value"):
            if key in params and isinstance(params[key], int | float):
                params[key] = float(params[key]) / unit_spec.sim_scale

    return {**var, "params": params}


def validate_variable(var: dict[str, Any], unit_spec: UnitSpec) -> list[str]:
    """Return advisory warning strings for a variable given its unit spec."""
    warnings: list[str] = []
    params = var.get("params", {})
    name   = var.get("name", "?")
    utype  = unit_spec.type
    code   = unit_spec.code.upper()

    lo = unit_spec.range_min
    hi = unit_spec.range_max
    for key in ("mean", "low", "high", "mode", "value"):
        val = params.get(key)
        if val is None:
            continue
        fval = float(val)
        if lo is not None and fval < lo:
            warnings.append(
                f"Variable '{name}': {key}={val} is below minimum "
                f"{lo} for unit '{unit_spec.code}'."
            )
        if hi is not None and fval > hi:
            warnings.append(
                f"Variable '{name}': {key}={val} exceeds maximum "
                f"{hi} for unit '{unit_spec.code}'."
            )

    if utype == "currency":
        for key in ("low", "mean", "value"):
            val = params.get(key)
            if val is not None and float(val) < 0:
                warnings.append(
                    f"Variable '{name}': {key}={val} is negative for currency '{code}'. "
                    "Intentional for P&L? Use negative explicitly.")

    if utype == "crypto":
        if code == "BTC":
            for key in ("mean", "high", "value"):
                val = params.get(key)
                if val is not None and float(val) > 21_000_000:
                    warnings.append(
                        f"Variable '{name}': {key}={float(val):,.0f} > 21M BTC total supply. "
                        f"Did you mean {float(val)/1e8:.6f} BTC (input in satoshis)? "
                        "Use unit_spec='BTC_sat' and sim_scale=1e8.")
        for key in ("mean", "low", "high", "value"):
            val = params.get(key)
            if val is not None and float(val) < 0:
                warnings.append(f"Variable '{name}': {key}={val} is negative for crypto '{code}'.")

    if utype == "six_sigma":
        for key in ("mean", "value"):
            val = params.get(key)
            if val is not None:
                fval = float(val)
                if fval < 0.67:
                    warnings.append(
                        f"Variable '{name}': {code}={fval:.2f} is very poor "
                        "quality (< 0.67). Check units."
                    )
                elif fval > 6.0:
                    warnings.append(
                        f"Variable '{name}': {code}={fval:.2f} exceeds "
                        "Six Sigma (6σ). Values > 2.0 are excellent."
                    )

    if utype == "p_value":
        for key in ("mean", "value"):
            val = params.get(key)
            if val is not None and float(val) > 1.0:
                warnings.append(f"Variable '{name}': p-value={val} > 1.0. p-values are [0,1].")

    if utype == "ph":
        for key in ("mean", "low", "high", "value"):
            val = params.get(key)
            if val is not None and not (0.0 <= float(val) <= 14.0):
                warnings.append(f"Variable '{name}': pH={val} is outside [0,14].")

    if utype == "oee":
        for key in ("mean", "high", "value"):
            val = params.get(key)
            if val is not None and float(val) > 1.0:
                fval = float(val)
                warnings.append(
                    f"Variable '{name}': OEE={fval} > 1.0. OEE is [0,1]. "
                    f"Did you mean {fval/100:.2f} (input as %)?")

    if utype == "date":
        for key in ("mean", "low", "high", "value"):
            val = params.get(key)
            if val is not None and isinstance(val, int | float) and float(val) > 1e9:
                warnings.append(
                    f"Variable '{name}': {key}={val} looks like Unix epoch seconds "
                    "(> 1e9). Provide epoch days or ISO date string.")

    return warnings
