"""
UnitSpec — parsed unit specification dataclass with full shorthand resolution.
"""
from __future__ import annotations

from typing import Any

from .registries import (
    AREA_TO_M2,
    CONCENTRATION_LABELS,
    CRYPTO_DISPLAY_DECIMALS,
    CRYPTO_SUB_UNITS,
    CURRENCY_PRECISION,
    DATA_RATE_TO_BPS,
    DATA_SIZE_TO_BYTES,
    DURATION_TO_SECONDS,
    FORCE_TO_N,
    FREQUENCY_TO_HZ,
    LENGTH_TO_M,
    MASS_TO_KG,
    PRESSURE_TO_PA,
    SPEED_DISPLAY_UNITS,
    SPEED_TO_MS,
    SPORTS_UNITS,
    VOLUME_TO_L,
)


class UnitSpec:
    """
    Parsed unit specification for any numeric domain.

    Shorthand strings: "USD", "BTC", "BTC_sat", "gwei", "%", "bps",
    "kg", "m", "L", "Pa", "N", "Hz", "MB", "Mbps", "°C", "lap_s", ...

    Full dict form: {type, code, precision, scale, format, base_unit, sim_scale, label}
    """
    __slots__ = ("type", "code", "precision", "scale", "format",
                 "base_unit", "sim_scale", "label", "range_min", "range_max")

    def __init__(
        self,
        unit_type: str = "raw",
        code: str = "",
        precision: int | None = None,
        scale: float = 1.0,
        fmt: str = "standard",
        base_unit: str = "",
        sim_scale: float = 1.0,
        label: str = "",
        range_min: float | None = None,
        range_max: float | None = None,
    ) -> None:
        self.type      = unit_type
        self.code      = code
        self.precision = precision
        self.scale     = scale
        self.format    = fmt
        self.base_unit = base_unit
        self.sim_scale = sim_scale
        self.label     = label
        self.range_min = range_min
        self.range_max = range_max

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | str | None) -> UnitSpec:
        if raw is None:
            return cls()
        if isinstance(raw, str):
            return cls._from_string(raw)
        return cls._from_dict(raw)

    @classmethod
    def _from_string(cls, s: str) -> UnitSpec:  # noqa: C901
        s  = s.strip()
        su = s.upper()
        sl = s.lower()

        if su in CURRENCY_PRECISION:
            return cls(unit_type="currency", code=su, precision=CURRENCY_PRECISION[su])

        if sl in {k.lower() for k in CRYPTO_SUB_UNITS}:
            key = next(k for k in CRYPTO_SUB_UNITS if k.lower() == sl)
            lbl, sim_scale, parent = CRYPTO_SUB_UNITS[key]
            return cls(unit_type="crypto_sub", code=key,
                       precision=0 if sim_scale >= 1e6 else 4,
                       sim_scale=sim_scale, base_unit=lbl, label=f"{lbl} ({parent})")

        _shorthand_map = {
            "satoshi": "BTC_sat", "sat": "BTC_sat",
            "gwei": "ETH_gwei", "wei": "ETH_wei",
            "lamport": "SOL_lamport", "lamp": "SOL_lamport",
            "drop": "XRP_drop",
        }
        if sl in _shorthand_map:
            return cls._from_string(_shorthand_map[sl])

        if su in CRYPTO_DISPLAY_DECIMALS:
            return cls(unit_type="crypto", code=su, precision=CRYPTO_DISPLAY_DECIMALS[su])

        if s in ("%", "pct", "percent", "percentage"):
            return cls(unit_type="percentage", code="%", precision=2,
                       range_min=-100.0, range_max=100.0)

        if sl in ("bps", "basis_points", "bp"):
            return cls(unit_type="bps", code="bps", precision=1, scale=10000.0)

        if sl in ("probability", "prob", "p"):
            return cls(unit_type="probability", code="probability", precision=4,
                       range_min=0.0, range_max=1.0)

        if sl in ("count", "integer", "int", "#"):
            return cls(unit_type="count", code="count", precision=0, range_min=0.0)

        if sl in ("date", "datetime", "timestamp", "epoch_days"):
            return cls(unit_type="date", code="date", precision=0)

        _duration_explicit = ("h", "hours", "hour", "d", "days", "day",
                               "min", "minutes", "minute",
                               "y", "yr", "years", "year",
                               "mo", "months", "month",
                               "w", "wk", "week", "weeks",
                               "ms", "us", "ns", "μs", "sec", "second", "seconds",
                               "q", "quarter", "quarters")
        if (sl in DURATION_TO_SECONDS and sl not in ("m", "n", "s")) or sl in _duration_explicit:
            return cls(unit_type="duration", code=sl, precision=2)

        if sl in ("cpk", "ppk", "cp", "pp"):
            lbl = {"cpk": "Cpk", "ppk": "Ppk", "cp": "Cp", "pp": "Pp"}[sl]
            return cls(unit_type="six_sigma", code=lbl, precision=2, range_min=0.0, label=lbl)
        if sl in ("sigma", "sigma_level"):
            return cls(unit_type="six_sigma", code="σ", precision=2, range_min=0.0, range_max=6.5)
        if sl == "dpmo":
            return cls(unit_type="dpmo", code="DPMO", precision=0, range_min=0.0)
        if sl in ("ppm_defect", "ppm", "ppm_def"):
            return cls(unit_type="ppm_defect", code="ppm", precision=2, range_min=0.0)
        if sl == "oee":
            return cls(
                unit_type="oee",
                code="OEE",
                precision=1,
                scale=100.0,
                range_min=0.0,
                range_max=1.0,
            )
        if sl == "mtbf":
            return cls(unit_type="mtbf", code="h", precision=1, range_min=0.0, label="MTBF")
        if sl == "mttr":
            return cls(unit_type="mttr", code="h", precision=2, range_min=0.0, label="MTTR")

        if sl in ("nnt", "number_needed_to_treat"):
            return cls(
                unit_type="medical_stat",
                code="NNT",
                precision=1,
                range_min=0.0,
                label="NNT",
            )
        if sl in ("nnh", "number_needed_to_harm"):
            return cls(
                unit_type="medical_stat",
                code="NNH",
                precision=1,
                range_min=0.0,
                label="NNH",
            )
        if sl in ("or", "odds_ratio"):
            return cls(unit_type="medical_stat", code="OR", precision=2, range_min=0.0, label="OR")
        if sl in ("hr", "hazard_ratio"):
            return cls(unit_type="medical_stat", code="HR", precision=2, range_min=0.0, label="HR")
        if sl in ("rr", "relative_risk", "risk_ratio"):
            return cls(unit_type="medical_stat", code="RR", precision=2, range_min=0.0, label="RR")
        if sl in ("arr", "absolute_risk_reduction"):
            return cls(unit_type="medical_stat", code="ARR", precision=3, label="ARR")
        if sl in ("cohens_d", "cohen_d", "effect_size"):
            return cls(unit_type="medical_stat", code="d", precision=2, label="Cohen's d")
        if sl in ("p_value", "p-value", "pval"):
            return cls(unit_type="p_value", code="p", precision=4, range_min=0.0, range_max=1.0)

        if sl in ("nm", "nanomolar"):
            return cls(unit_type="pharma", code="nM", precision=3, label="nM")
        if sl in ("um", "μm", "micromolar"):
            return cls(unit_type="pharma", code="μM", precision=3, label="μM")
        if sl in ("mm", "millimolar"):
            return cls(unit_type="pharma", code="mM", precision=3, label="mM")
        if sl in ("half_life", "t_half", "t1/2", "t½"):
            return cls(unit_type="half_life", code="h", precision=2, range_min=0.0, label="t½")
        if sl in ("bioavailability", "f", "f%"):
            return cls(
                unit_type="percentage",
                code="%",
                precision=1,
                range_min=0.0,
                range_max=100.0,
                label="F",
            )

        if sl in CONCENTRATION_LABELS:
            return cls(unit_type="concentration", code=CONCENTRATION_LABELS[sl], precision=3)
        if sl == "mg/dl":
            return cls(unit_type="concentration", code="mg/dL", precision=1)
        if sl == "mmol/l":
            return cls(unit_type="concentration", code="mmol/L", precision=2)
        if sl in ("iu/l", "u/l"):
            return cls(unit_type="concentration", code="IU/L", precision=1)

        if sl == "mach":
            return cls(unit_type="aerospace", code="Mach", precision=2, range_min=0.0, label="Mach")
        if sl in ("g", "g_force", "gee"):
            return cls(unit_type="aerospace", code="g", precision=2, range_min=0.0, label="g")
        if sl in ("kts", "knots", "kt"):
            return cls(unit_type="aerospace", code="kts", precision=1, label="kts")
        if sl in ("nmi", "nm_nautical", "nautical_miles"):
            return cls(unit_type="aerospace", code="nmi", precision=1, label="nmi")
        if sl in ("kn", "kn_thrust"):
            return cls(unit_type="aerospace", code="kN", precision=1, label="kN")
        if sl == "isp":
            return cls(unit_type="aerospace", code="s", precision=1, label="Isp")

        if sl in ("msv", "milli_sievert"):
            return cls(unit_type="radiation", code="mSv", precision=3, range_min=0.0)
        if sl in ("usv", "μsv", "micro_sievert", "μsv/h", "usv/h"):
            code = "μSv/h" if "h" in sl else "μSv"
            return cls(unit_type="radiation", code=code, precision=3, range_min=0.0)
        if sl == "sv":
            return cls(unit_type="radiation", code="Sv", precision=4, range_min=0.0)
        if sl in ("bq/m3", "bq/m³"):
            return cls(unit_type="radiation", code="Bq/m³", precision=1, range_min=0.0)

        if sl in ("kwh", "kWh"):
            return cls(unit_type="energy", code="kWh", precision=2)
        if sl == "mwh":
            return cls(unit_type="energy", code="MWh", precision=2)
        if sl == "gwh":
            return cls(unit_type="energy", code="GWh", precision=2)
        if sl == "mmbtu":
            return cls(unit_type="energy", code="MMBTU", precision=3)
        if sl == "mw":
            return cls(unit_type="power", code="MW", precision=2)
        if sl == "gw":
            return cls(unit_type="power", code="GW", precision=3)
        if sl == "kw":
            return cls(unit_type="power", code="kW", precision=2)

        if sl in ("tco2e", "t_co2e", "mtco2e"):
            code = "MtCO₂e" if sl.startswith("mt") else "tCO₂e"
            return cls(unit_type="carbon", code=code, precision=2, range_min=0.0)
        if sl == "kgco2e":
            return cls(unit_type="carbon", code="kgCO₂e", precision=1, range_min=0.0)

        if sl in ("ppm_conc", "ppm_concentration"):
            return cls(unit_type="ppm_conc", code="ppm", precision=3, range_min=0.0)
        if sl in ("ppb_conc", "ppb"):
            return cls(unit_type="ppb_conc", code="ppb", precision=3, range_min=0.0)
        if sl == "ph":
            return cls(unit_type="ph", code="pH", precision=2, range_min=0.0, range_max=14.0)

        if sl == "cap_rate":
            return cls(
                unit_type="real_estate",
                code="%",
                precision=2,
                label="cap rate",
                range_min=0.0,
            )
        if sl == "grm":
            return cls(unit_type="real_estate", code="×", precision=1, label="GRM", range_min=0.0)
        if sl == "dscr":
            return cls(unit_type="ratio", code="×", precision=2, label="DSCR", range_min=0.0)

        if sl in ("loss_ratio", "loss_r"):
            return cls(
                unit_type="actuarial",
                code="%",
                precision=1,
                scale=100.0,
                label="LR",
                range_min=0.0,
            )
        if sl in ("combined_ratio", "combined_r"):
            return cls(
                unit_type="actuarial",
                code="%",
                precision=1,
                scale=100.0,
                label="CR",
                range_min=0.0,
            )

        if sl in MASS_TO_KG:
            return cls(unit_type="mass", code=s, precision=3, range_min=0.0)
        if sl in ("weight", "mass", "kg_mass"):
            return cls(unit_type="mass", code="kg", precision=3, range_min=0.0)

        if sl in LENGTH_TO_M or sl in ("length", "height", "depth", "width", "distance"):
            code = s if s in LENGTH_TO_M else "m"
            return cls(unit_type="length", code=code, precision=3, range_min=0.0)

        if sl in AREA_TO_M2 or sl in ("area", "surface"):
            code = s if s in AREA_TO_M2 else "m²"
            return cls(unit_type="area", code=code, precision=3, range_min=0.0)
        if sl in ("ha", "hectare", "hectares"):
            return cls(unit_type="area", code="ha", precision=2, range_min=0.0)
        if sl in ("acre", "acres", "ac"):
            return cls(unit_type="area", code="acre", precision=2, range_min=0.0)

        if sl in VOLUME_TO_L or sl in ("volume", "vol", "capacity"):
            code = s if s in VOLUME_TO_L else "L"
            return cls(unit_type="volume", code=code, precision=3, range_min=0.0)

        if sl in ("kg/m³", "kg/m3", "g/cm³", "g/cm3", "g/ml", "g/mL",
                  "kg/l", "kg/L", "lb/ft³", "lb/ft3", "density"):
            code = s.replace("3", "³").replace("/l", "/L")
            return cls(unit_type="density", code=code, precision=3, range_min=0.0)

        if sl in PRESSURE_TO_PA:
            p = 2 if sl in ("bar", "mbar", "atm", "psi") else 0 if sl.startswith("pa") else 3
            return cls(unit_type="pressure", code=s, precision=p, range_min=0.0)
        if sl in ("pressure", "stress"):
            return cls(unit_type="pressure", code="Pa", precision=1, range_min=0.0)

        if sl in FORCE_TO_N:
            return cls(unit_type="force", code=s, precision=2, range_min=0.0)
        if sl in ("force", "thrust"):
            return cls(unit_type="force", code="N", precision=2, range_min=0.0)
        if sl in ("n·m", "nm_torque", "ft·lb", "ft_lb", "ft_lbf", "n*m", "torque"):
            return cls(unit_type="torque", code=s, precision=2)

        if sl in DATA_SIZE_TO_BYTES or sl in ("data", "storage", "file_size", "memory"):
            code = s if s in DATA_SIZE_TO_BYTES else "MB"
            return cls(unit_type="data_size", code=code, precision=2, range_min=0.0)

        if sl in DATA_RATE_TO_BPS or sl in ("bandwidth", "throughput_bps", "data_rate"):
            code = s if s in DATA_RATE_TO_BPS else "Mbps"
            return cls(unit_type="data_rate", code=code, precision=2, range_min=0.0)

        if sl in FREQUENCY_TO_HZ or sl in ("frequency", "freq"):
            code = s if s in FREQUENCY_TO_HZ else "Hz"
            return cls(unit_type="frequency", code=code, precision=3, range_min=0.0)

        if "/" in s and s not in CONCENTRATION_LABELS:
            return cls(unit_type="rate", code=s, precision=3, range_min=0.0)

        if sl in ("ratio", "unitless", "x"):
            return cls(unit_type="ratio", code="×", precision=2, range_min=0.0)

        if sl in SPEED_TO_MS or sl in ("speed", "velocity", "vel"):
            display = s if s in SPEED_DISPLAY_UNITS else "m/s"
            return cls(unit_type="speed", code=display, precision=2, range_min=0.0)
        if sl in ("km/h", "kph", "kmh"):
            return cls(unit_type="speed", code="km/h", precision=1, range_min=0.0)
        if sl in ("mph", "mi/h"):
            return cls(unit_type="speed", code="mph", precision=1, range_min=0.0)
        if sl in ("m/s", "ms_speed"):
            return cls(unit_type="speed", code="m/s", precision=2, range_min=0.0)
        if sl == "rpm":
            return cls(unit_type="angular", code="rpm", precision=1, range_min=0.0, label="rpm")
        if sl in ("rad/s", "rads"):
            return cls(unit_type="angular", code="rad/s", precision=3, range_min=0.0)
        if sl in ("deg/s", "°/s"):
            return cls(unit_type="angular", code="°/s", precision=2)

        if sl in ("deg", "°", "degrees"):
            return cls(unit_type="angular", code="°", precision=2, range_min=0.0, range_max=360.0)
        if sl in ("rad", "radians"):
            return cls(
                unit_type="angular",
                code="rad",
                precision=4,
                range_min=0.0,
                range_max=6.283185307,
            )

        if sl in ("°c", "celsius", "c_temp"):
            return cls(unit_type="temperature", code="°C", precision=2)
        if sl in ("°f", "fahrenheit", "f_temp"):
            return cls(unit_type="temperature", code="°F", precision=2)
        if sl in ("k", "kelvin") or s == "K":
            return cls(unit_type="temperature", code="K", precision=2, range_min=0.0)

        if sl in SPORTS_UNITS:
            lbl, prec, _ = SPORTS_UNITS[sl]
            return cls(unit_type="sports", code=lbl or sl, precision=prec, range_min=0.0, label=sl)
        if sl == "elo":
            return cls(
                unit_type="sports",
                code="ELO",
                precision=0,
                range_min=0.0,
                range_max=4000.0,
                label="ELO",
            )
        if sl in ("lap_time", "lap_s", "laptime"):
            return cls(unit_type="sports", code="s", precision=3, range_min=0.0, label="lap")
        if sl in ("sector_s", "sector_time"):
            return cls(unit_type="sports", code="s", precision=3, range_min=0.0, label="sector")

        if sl in ("lat", "latitude"):
            return cls(
                unit_type="coordinate",
                code="°N",
                precision=6,
                range_min=-90.0,
                range_max=90.0,
                label="lat",
            )
        if sl in ("lon", "lng", "longitude"):
            return cls(
                unit_type="coordinate",
                code="°E",
                precision=6,
                range_min=-180.0,
                range_max=180.0,
                label="lon",
            )
        if sl in ("altitude", "altitude_m", "alt_m"):
            return cls(unit_type="coordinate", code="m", precision=1, label="alt")
        if sl in ("altitude_ft", "alt_ft"):
            return cls(
                unit_type="coordinate",
                code="ft",
                precision=0,
                label="alt",
                sim_scale=0.3048,
            )
        if sl in ("distance_km", "dist_km"):
            return cls(unit_type="coordinate", code="km", precision=3, range_min=0.0)
        if sl in ("distance_mi", "dist_mi"):
            return cls(
                unit_type="coordinate",
                code="mi",
                precision=3,
                range_min=0.0,
                sim_scale=1.60934,
            )

        return cls(unit_type="si", code=s, precision=4)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> UnitSpec:
        unit_type = str(d.get("type", d.get("unit_type", "raw"))).lower()
        code      = str(d.get("code", d.get("unit", "")))
        precision = d.get("precision")
        scale     = float(d.get("scale", 1.0))
        fmt       = str(d.get("format", "standard"))
        base_unit = str(d.get("base_unit", ""))
        sim_scale = float(d.get("sim_scale", 1.0))
        label     = str(d.get("label", ""))
        range_min = d.get("range_min")
        range_max = d.get("range_max")

        cu = code.upper()
        if unit_type == "currency" and cu in CURRENCY_PRECISION and precision is None:
            precision = CURRENCY_PRECISION[cu]

        if unit_type == "crypto_sub" and code in CRYPTO_SUB_UNITS:
            lbl, sscale, parent = CRYPTO_SUB_UNITS[code]
            if sim_scale == 1.0:
                sim_scale = sscale
            if not base_unit:
                base_unit = lbl
            if not label:
                label = f"{lbl} ({parent})"

        if range_min is not None:
            range_min = float(range_min)
        if range_max is not None:
            range_max = float(range_max)

        return cls(unit_type=unit_type, code=code, precision=precision,
                   scale=scale, fmt=fmt, base_unit=base_unit, sim_scale=sim_scale,
                   label=label, range_min=range_min, range_max=range_max)
