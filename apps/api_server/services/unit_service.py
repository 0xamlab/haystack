"""
Universal Unit Context Service — full pipeline for every numeric domain.

Supported domains and unit types:
  ── Finance ──────────────────────────────────────────────────────────────────
  currency        ISO 4217: USD, EUR, GBP, JPY, CHF, CAD, AUD, SGD, INR, CNY, ...
  percentage      % — scale×100 for display, raw [0,1] or [0,100] for simulation
  bps             basis points — 1 bps = 0.0001; scale×10,000 for display
  financial_ratio IRR, Sharpe, DSCR, LTV, ROE, P/E (unitless or labeled)

  ── Crypto / DeFi ────────────────────────────────────────────────────────────
  crypto          BTC, ETH, SOL, MATIC, USDT, USDC, XRP, BNB, ADA, DOT, AVAX, ...
  crypto_sub      BTC_sat (satoshi=1e-8), ETH_gwei (1e-9), ETH_wei (1e-18),
                  SOL_lamport (1e-9), any token with custom decimals

  ── Date / Time ──────────────────────────────────────────────────────────────
  date            ISO 8601 strings ↔ epoch days
  duration        ns, us, ms, s, min, h, day, wk, mo, yr

  ── Six Sigma / Manufacturing ────────────────────────────────────────────────
  six_sigma       Cpk, Ppk, Cp, σ-level (warn if < 1.0 or < 1.33)
  dpmo            defects per million opportunities
  ppm_defect      parts-per-million defective
  oee             Overall Equipment Effectiveness [0–100%]
  mtbf            mean time between failures (hours)
  mttr            mean time to repair (hours)

  ── Medical / Clinical ───────────────────────────────────────────────────────
  medical_stat    NNT, NNH, OR, HR, RR, ARR, ARI, Cohen's d (labeled, range-validated)
  p_value         p-value [0–1], formatted as "p < 0.001" / "p = 0.042"
  concentration   μg/mL, ng/mL, mg/dL, mmol/L, nmol/L, IU/L, mEq/L
  dose_rate       mg/kg, μg/kg, mg/m², IU/kg

  ── Pharma / Drug Discovery ──────────────────────────────────────────────────
  pharma          IC50, EC50, Ki, Kd (nM, μM, mM), bioavailability %, t½, Cmax, AUC
  half_life       t½ in hours (pharma standard)

  ── Aerospace / Defense ──────────────────────────────────────────────────────
  aerospace       Mach, g_force (g), knots, nmi, lbf, kN, Isp (s)
  radiation       Sv, mSv, μSv, Gy, rad, Bq, Ci, μSv/h

  ── Energy / Utilities ───────────────────────────────────────────────────────
  energy          kWh, MWh, GWh, TWh, kJ, MJ, MMBTU, BTU
  power           W, kW, MW, GW
  carbon          tCO2e, kgCO2e, MtCO2e (emissions)
  fuel            bbl/day, mcf, TJ, toe (oil equivalent)

  ── Environmental / Chemistry ────────────────────────────────────────────────
  ppm_conc        parts-per-million by mass or volume
  ppb_conc        parts-per-billion
  ph              pH [0–14] (logarithmic, range-validated)
  radiation       Bq/m³, μSv/h, mrem/h

  ── Real Estate ──────────────────────────────────────────────────────────────
  real_estate     cap_rate %, NOI ($), price_per_sqft ($/ft²), GRM, DSCR

  ── Supply Chain / Logistics ─────────────────────────────────────────────────
  supply_chain    fill_rate %, service_level %, lead_time (days), stockout %

  ── Actuarial / Insurance ────────────────────────────────────────────────────
  actuarial       q_x mortality, hazard λ, loss_ratio %, combined_ratio %, LER

  ── Scientific / SI ──────────────────────────────────────────────────────────
  si              m, kg, Pa, Hz, mol/L, J, W, °C, K, mol, m², m³, m/s, rad/s
  scientific      generic scientific notation (auto-scales to appropriate prefix)
  count           integer-like non-negative
  probability     strictly [0,1]
  ratio           unitless ratio (validated ≥ 0)
  raw             no formatting, pass-through

Pipeline:
  preprocess(variables, unit_specs) → normalized float values for Mojo
  postprocess(raw_results, unit_specs) → human-readable formatted_result block
  validate(variables, unit_specs) → warnings for out-of-range values
  suggest_unit_specs(domain_hint, variable_name) → auto-suggested UnitSpec
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ── Registries ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

UNIT_TYPES = frozenset([
    "currency", "percentage", "bps", "financial_ratio",
    "crypto", "crypto_sub",
    "date", "duration",
    "six_sigma", "dpmo", "ppm_defect", "oee", "mtbf", "mttr",
    "medical_stat", "p_value", "concentration", "dose_rate",
    "pharma", "half_life",
    "aerospace", "radiation",
    "energy", "power", "carbon", "fuel",
    "ppm_conc", "ppb_conc", "ph",
    "real_estate", "supply_chain", "actuarial",
    "speed", "angular", "sports", "coordinate", "temperature",
    # New: physical dimensions + digital
    "mass", "length", "area", "volume", "density",
    "pressure", "force", "torque",
    "data_size", "data_rate", "frequency", "rate",
    "si", "scientific", "count", "probability", "ratio", "raw", "custom",
])

# ── Physical constants ────────────────────────────────────────────────────────
# Available as symbols in objective_function expressions
PHYSICAL_CONSTANTS: dict[str, float] = {
    "c":        299_792_458.0,          # speed of light (m/s)
    "c_light":  299_792_458.0,
    "G":        6.674e-11,              # gravitational constant (N·m²/kg²)
    "g":        9.80665,                # standard gravity (m/s²)
    "g_earth":  9.80665,
    "hbar":     1.054571817e-34,        # reduced Planck constant (J·s)
    "h_planck": 6.62607015e-34,         # Planck constant (J·s)
    "kB":       1.380649e-23,           # Boltzmann constant (J/K)
    "k_B":      1.380649e-23,
    "NA":       6.02214076e23,          # Avogadro number (mol⁻¹)
    "N_A":      6.02214076e23,
    "R":        8.314462618,            # gas constant (J/mol·K)
    "R_gas":    8.314462618,
    "sigma_SB": 5.670374419e-8,         # Stefan-Boltzmann (W/m²·K⁴)
    "e_charge": 1.602176634e-19,        # elementary charge (C)
    "eps0":     8.8541878128e-12,       # vacuum permittivity (F/m)
    "mu0":      1.25663706212e-6,       # vacuum permeability (H/m)
    "au":       1.495978707e11,         # astronomical unit (m)
    "ly":       9.4607304725808e15,     # light year (m)
    "pc":       3.085677581491367e16,   # parsec (m)
    "pi":       3.141592653589793,
    "e":        2.718281828459045,
    "phi":      1.618033988749895,      # golden ratio
    "c_sound":  343.0,                  # speed of sound in air at 20°C (m/s)
}

# ── Speed units → m/s ─────────────────────────────────────────────────────────
SPEED_TO_MS: dict[str, float] = {
    "m/s":   1.0,  "ms":  1.0,
    "km/h":  1.0 / 3.6,
    "kph":   1.0 / 3.6,
    "mph":   0.44704,
    "mi/h":  0.44704,
    "kts":   0.514444,
    "knots": 0.514444,
    "ft/s":  0.3048,
    "fps":   0.3048,
    "c":     299_792_458.0,             # fraction of speed of light
    "mach":  340.29,                    # Mach 1 at sea level
}
SPEED_DISPLAY_UNITS = {"m/s", "km/h", "kph", "mph", "kts", "ft/s"}

# ── Angular units → radians ───────────────────────────────────────────────────
ANGULAR_TO_RAD: dict[str, float] = {
    "rad":    1.0,
    "deg":    3.141592653589793 / 180.0,
    "°":      3.141592653589793 / 180.0,
    "mrad":   1e-3,
    "arcmin": 3.141592653589793 / (180.0 * 60),
    "arcsec": 3.141592653589793 / (180.0 * 3600),
    "rev":    2 * 3.141592653589793,    # full revolution
    "grad":   3.141592653589793 / 200.0,
}

# ── Temperature conversions (display only — sim always in Kelvin or °C as-is) ─
TEMPERATURE_OFFSETS: dict[str, tuple[float, float]] = {
    # (multiply, add) to convert FROM display unit TO Kelvin
    "°c": (1.0, 273.15),
    "c":  (1.0, 273.15),
    "°f": (5.0/9.0, 255.372),
    "f":  (5.0/9.0, 255.372),
    "k":  (1.0, 0.0),
    "°k": (1.0, 0.0),
    "°r": (5.0/9.0, 0.0),   # Rankine
}

# ── Sports / racing unit registry ────────────────────────────────────────────
SPORTS_UNITS: dict[str, tuple[str, int, str]] = {
    # code: (display_label, precision, type_hint)
    "score":    ("pts", 1, "score"),
    "points":   ("pts", 1, "score"),
    "lap_s":    ("s",   3, "lap_time"),
    "lap_ms":   ("ms",  0, "lap_time"),
    "sector_s": ("s",   3, "sector"),
    "elo":      ("ELO", 0, "elo"),
    "rating":   ("",    1, "score"),
    "margin":   ("",    2, "score"),
    "pos":      ("",    0, "position"),   # race position
    "rank":     ("",    0, "position"),
    "goal":     ("",    0, "count"),
}

# ── ISO 4217 currencies ───────────────────────────────────────────────────────
CURRENCY_PRECISION: dict[str, int] = {
    "USD": 2, "EUR": 2, "GBP": 2, "JPY": 0, "CHF": 2, "CAD": 2,
    "AUD": 2, "HKD": 2, "SGD": 2, "SEK": 2, "NOK": 2, "DKK": 2,
    "NZD": 2, "MXN": 2, "BRL": 2, "INR": 2, "CNY": 2, "KRW": 0,
    "TRY": 2, "ZAR": 2, "AED": 2, "SAR": 2, "ILS": 2, "PLN": 2,
    "THB": 2, "IDR": 0, "CZK": 2, "HUF": 0, "RON": 2, "CLP": 0,
    "COP": 0, "PEN": 2, "VND": 0, "PHP": 2, "NGN": 2, "EGP": 2,
    "PKR": 2, "BDT": 2, "KZT": 2, "UAH": 2, "GHS": 2, "KES": 2,
}
CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",  "EUR": "€",  "GBP": "£",  "JPY": "¥",  "CHF": "Fr",
    "CAD": "C$", "AUD": "A$", "HKD": "HK$","SGD": "S$", "BRL": "R$",
    "INR": "₹",  "CNY": "¥",  "KRW": "₩",  "TRY": "₺",  "ILS": "₪",
    "MXN": "MX$","ZAR": "R",  "PHP": "₱",  "UAH": "₴",  "NGN": "₦",
}

# ── Crypto — whole-coin tickers with display decimals ─────────────────────────
CRYPTO_DISPLAY_DECIMALS: dict[str, int] = {
    "BTC": 8, "ETH": 6, "LTC": 8, "XRP": 6, "SOL": 6,
    "MATIC": 4, "USDT": 2, "USDC": 2, "BUSD": 2, "DAI": 2,
    "BNB": 4, "ADA": 4, "DOT": 4, "AVAX": 4, "LINK": 4,
    "UNI": 4, "ATOM": 4, "NEAR": 4, "FTM": 4, "ALGO": 4,
    "XLM": 4, "VET": 4, "ICP": 4, "THETA": 4, "FIL": 4,
    "AAVE": 4, "COMP": 4, "MKR": 4, "SNX": 4, "YFI": 4,
}

# ── Crypto sub-units: code → (display_name, scale_to_whole_coin) ─────────────
# sim_scale: divide input by this to get whole-coin value for simulation
CRYPTO_SUB_UNITS: dict[str, tuple[str, float, str]] = {
    # (display_label, sim_scale, parent_ticker)
    "BTC_sat":       ("sat",    1e8,   "BTC"),
    "BTC_satoshi":   ("sat",    1e8,   "BTC"),
    "ETH_gwei":      ("Gwei",   1e9,   "ETH"),
    "ETH_mwei":      ("mwei",   1e6,   "ETH"),
    "ETH_kwei":      ("kwei",   1e3,   "ETH"),
    "ETH_wei":       ("wei",    1e18,  "ETH"),
    "SOL_lamport":   ("lamp",   1e9,   "SOL"),
    "XRP_drop":      ("drop",   1e6,   "XRP"),
    "ADA_lovelace":  ("lov",    1e6,   "ADA"),
    "DOT_plank":     ("plank",  1e10,  "DOT"),
    "AVAX_nano":     ("nAVAX",  1e9,   "AVAX"),
    "MATIC_gwei":    ("Gwei",   1e9,   "MATIC"),
    # Generic ERC-20 with 6 decimals (USDT, USDC, etc.)
    "USDT_micro":    ("μUSDT",  1e6,   "USDT"),
    "USDC_micro":    ("μUSDC",  1e6,   "USDC"),
}

# ── Duration ──────────────────────────────────────────────────────────────────
DURATION_TO_SECONDS: dict[str, float] = {
    "ns": 1e-9, "us": 1e-6, "μs": 1e-6, "ms": 1e-3,
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    # "m" removed — conflicts with meters (length). Use "min" for minutes.
    "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "d": 86400.0, "day": 86400.0, "days": 86400.0,
    "w": 604800.0, "wk": 604800.0, "week": 604800.0, "weeks": 604800.0,
    "mo": 2592000.0, "month": 2592000.0, "months": 2592000.0,
    "q": 7776000.0, "quarter": 7776000.0, "quarters": 7776000.0,
    "y": 31536000.0, "yr": 31536000.0, "year": 31536000.0, "years": 31536000.0,
}

# ── Energy units → kWh base ───────────────────────────────────────────────────
ENERGY_TO_KWH: dict[str, float] = {
    "wh": 1e-3, "kwh": 1.0, "mwh": 1e3, "gwh": 1e6, "twh": 1e9,
    "j": 2.778e-7, "kj": 2.778e-4, "mj": 0.2778, "gj": 277.8,
    "btu": 2.931e-4, "mmbtu": 293.1, "therm": 29.31,
    "toe": 11_630.0,  # tonne of oil equivalent
    "tce": 8_140.0,   # tonne of coal equivalent
}

# ── Concentration units → base SI (mol/L) or keep labeled ────────────────────
CONCENTRATION_LABELS: dict[str, str] = {
    "ng/ml": "ng/mL", "ug/ml": "μg/mL", "mg/dl": "mg/dL", "mg/l": "mg/L",
    "mmol/l": "mmol/L", "umol/l": "μmol/L", "nmol/l": "nmol/L",
    "pmol/l": "pmol/L", "iu/l": "IU/L", "meq/l": "mEq/L",
    "g/dl": "g/dL", "g/l": "g/L", "mol/l": "mol/L", "μmol/l": "μmol/L",
    "nm": "nM", "um": "μM", "mm": "mM",  # for drug concentrations
}

# ── Range bounds for validation ───────────────────────────────────────────────
RANGE_BOUNDS: dict[str, tuple[float, float, bool, bool]] = {
    # (min, max, warn_below_min, warn_above_max)
    "probability":   (0.0,  1.0,  True,  True),
    "ph":            (0.0, 14.0,  True,  True),
    "oee":           (0.0,  1.0,  False, True),
    "bps":           (-1e6, 1e6,  False, False),  # just formatting
    "percentage":    (-100.0, 100.0, False, False),
    "six_sigma":     (0.0, 10.0,  False, False),
    "p_value":       (0.0,  1.0,  True,  True),
    "loss_ratio":    (0.0,  2.0,  False, True),
    "half_life":     (0.0,  1e6,  True,  False),
}

# ── Physical dimension conversion tables (all to SI base unit) ───────────────

# Mass → kilograms
MASS_TO_KG: dict[str, float] = {
    "kg": 1.0, "g": 1e-3, "mg": 1e-6, "μg": 1e-9, "ug": 1e-9,
    "ng": 1e-12, "tonne": 1e3, "t": 1e3, "mt": 1e3,  # metric tonne
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237,
    "oz": 0.028349523, "ounce": 0.028349523,
    "stone": 6.35029318, "st": 6.35029318,
    "slug": 14.593903, "ton": 907.18474,  # US short ton
    "long_ton": 1016.047, "tonne_metric": 1000.0,
    "gr": 6.479891e-5, "grain": 6.479891e-5,
    "carat": 2e-4, "ct": 2e-4,
}

# Length → meters
LENGTH_TO_M: dict[str, float] = {
    "m": 1.0, "km": 1e3, "cm": 1e-2, "mm": 1e-3,
    "μm": 1e-6, "um": 1e-6, "nm": 1e-9, "pm": 1e-12,
    "Å": 1e-10, "angstrom": 1e-10,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "yd": 0.9144, "yard": 0.9144,
    "nmi": 1852.0, "nautical_mile": 1852.0,
    "au": 1.495978707e11,
    "ly": 9.4607304725808e15,
    "pc": 3.085677581e16,
    "fathom": 1.8288, "chain": 20.1168, "furlong": 201.168,
    "league": 4828.032,
}

# Area → m²
AREA_TO_M2: dict[str, float] = {
    "m²": 1.0, "m2": 1.0, "km²": 1e6, "km2": 1e6,
    "cm²": 1e-4, "cm2": 1e-4, "mm²": 1e-6, "mm2": 1e-6,
    "ha": 1e4, "hectare": 1e4,
    "acre": 4046.8564, "ac": 4046.8564,
    "ft²": 0.09290304, "ft2": 0.09290304,
    "in²": 6.4516e-4, "in2": 6.4516e-4,
    "mi²": 2589988.11, "mi2": 2589988.11,
    "yd²": 0.83612736, "yd2": 0.83612736,
}

# Volume → liters
VOLUME_TO_L: dict[str, float] = {
    "l": 1.0, "L": 1.0, "litre": 1.0, "liter": 1.0,
    "ml": 1e-3, "mL": 1e-3, "milliliter": 1e-3,
    "cl": 0.01, "cL": 0.01, "dl": 0.1, "dL": 0.1,
    "μl": 1e-6, "ul": 1e-6, "μL": 1e-6,
    "m³": 1000.0, "m3": 1000.0,
    "cm³": 1e-3, "cm3": 1e-3, "cc": 1e-3,
    "mm³": 1e-6, "mm3": 1e-6,
    "gal": 3.78541, "gallon": 3.78541, "us_gal": 3.78541,
    "uk_gal": 4.54609, "imp_gal": 4.54609,
    "qt": 0.946353, "quart": 0.946353,
    "pt": 0.473176, "pint": 0.473176,
    "cup": 0.236588,
    "fl_oz": 0.0295735, "fl.oz": 0.0295735, "floz": 0.0295735,
    "tbsp": 0.0147868, "tsp": 0.00492892,
    "bbl": 158.987, "barrel": 158.987,  # oil barrel
    "ft³": 28.3168, "ft3": 28.3168,
    "in³": 0.0163871, "in3": 0.0163871,
}

# Pressure → Pa
PRESSURE_TO_PA: dict[str, float] = {
    "pa": 1.0, "Pa": 1.0,
    "kpa": 1e3, "kPa": 1e3,
    "mpa": 1e6, "MPa": 1e6,
    "gpa": 1e9, "GPa": 1e9,
    "bar": 1e5, "mbar": 100.0, "μbar": 0.1,
    "atm": 101325.0, "atmosphere": 101325.0,
    "psi": 6894.76, "psig": 6894.76,
    "kpsi": 6894760.0,
    "mmhg": 133.322, "mmHg": 133.322, "torr": 133.322,
    "inhg": 3386.39, "inHg": 3386.39,
    "inh2o": 249.089, "inH2O": 249.089,
    "cmh2o": 98.0665, "cmH2O": 98.0665,
}

# Force → Newtons
FORCE_TO_N: dict[str, float] = {
    "n": 1.0, "N": 1.0,
    "kn": 1e3, "kN": 1e3,
    "mn": 1e6, "MN": 1e6,
    "gn": 1e9, "GN": 1e9,
    "dyn": 1e-5, "dyne": 1e-5,
    "lbf": 4.44822, "pound_force": 4.44822,
    "kgf": 9.80665, "kp": 9.80665,  # kilopond
    "ozf": 0.278014,
    "tonf": 8896.44, "ton_force": 8896.44,
}

# Data size → bytes
DATA_SIZE_TO_BYTES: dict[str, float] = {
    "b":    1.0,   "byte":    1.0,   "bytes":    1.0,
    "kb":   1e3,   "kB":      1e3,   "kilobyte": 1e3,
    "mb":   1e6,   "mB":      1e6,   "megabyte": 1e6,
    "gb":   1e9,   "gB":      1e9,   "gigabyte": 1e9,
    "tb":   1e12,  "tB":      1e12,  "terabyte": 1e12,
    "pb":   1e15,  "pB":      1e15,  "petabyte": 1e15,
    "eb":   1e18,  "eB":      1e18,  "exabyte":  1e18,
    # IEC binary prefixes
    "kib":  1024.0,        "KiB": 1024.0,        "kibibyte": 1024.0,
    "mib":  1024**2,       "MiB": 1048576.0,      "mebibyte": 1048576.0,
    "gib":  1024**3,       "GiB": 1073741824.0,   "gibibyte": 1073741824.0,
    "tib":  1024**4,       "TiB": 1099511627776.0, "tebibyte": 1099511627776.0,
    "pib":  1024**5,       "PiB": 1125899906842624.0,
    # Bits
    "bit":  0.125, "bits": 0.125,
    "kbit": 125.0, "mbit": 125000.0, "gbit": 125000000.0,
}

# Data rate → bits per second
DATA_RATE_TO_BPS: dict[str, float] = {
    "bps":  1.0,   "bit/s":    1.0,
    "kbps": 1e3,   "Kbps": 1e3,  "kilobit/s": 1e3,
    "mbps": 1e6,   "Mbps": 1e6,  "megabit/s": 1e6,
    "gbps": 1e9,   "Gbps": 1e9,  "gigabit/s": 1e9,
    "tbps": 1e12,  "Tbps": 1e12, "terabit/s": 1e12,
    "kb/s": 1e3,   "MB/s": 8e6,  "GB/s": 8e9,
}

# Frequency → Hz
FREQUENCY_TO_HZ: dict[str, float] = {
    "hz": 1.0, "Hz": 1.0,
    "khz": 1e3, "kHz": 1e3,
    "mhz": 1e6, "MHz": 1e6,
    "ghz": 1e9, "GHz": 1e9,
    "thz": 1e12, "THz": 1e12,
    "rpm_hz": 1.0/60,  # rotations per minute → Hz
    "rad_s": 1.0/(2*3.141592653589793),  # rad/s → Hz
}

# ── Domain → suggested unit shorthand for common variable name patterns ───────
# Used by suggest_unit_specs()
DOMAIN_VARIABLE_HINTS: dict[str, dict[str, str]] = {
    "finance": {
        "revenue": "USD", "cost": "USD", "profit": "USD", "loss": "USD",
        "npv": "USD", "irr": "%", "roe": "%", "roa": "%",
        "sharpe": "ratio", "beta": "ratio", "alpha": "bps",
        "spread": "bps", "yield": "%", "rate": "%",
    },
    "crypto": {
        "price": "USD", "btc_price": "USD", "eth_price": "USD",
        "amount": "BTC", "fee": "ETH_gwei", "gas": "ETH_gwei",
        "tvl": "USD", "apy": "%", "apr": "%", "yield": "%",
        "slippage": "bps", "volume": "USD",
    },
    "medical": {
        "mortality": "probability", "survival": "probability",
        "response_rate": "percentage", "dosage": "mg/kg",
        "concentration": "mg/dL", "hazard_ratio": "medical_stat",
        "odds_ratio": "medical_stat", "nnt": "medical_stat",
        "p_value": "p_value", "effect_size": "ratio",
    },
    "pharma": {
        "ic50": "nM", "ec50": "nM", "ki": "nM", "kd": "nM",
        "bioavailability": "%", "half_life": "h",
        "cmax": "ng/ml", "auc": "ng·h/mL", "clearance": "L/h",
        "volume_distribution": "L/kg",
    },
    "manufacturing": {
        "cpk": "six_sigma", "ppk": "six_sigma", "cp": "six_sigma",
        "sigma_level": "six_sigma", "dpmo": "dpmo", "defect_rate": "ppm_defect",
        "oee": "oee", "yield": "percentage", "throughput": "count",
        "mtbf": "hours", "mttr": "hours", "cycle_time": "minutes",
    },
    "aerospace": {
        "velocity": "kts", "altitude": "ft", "mach": "Mach",
        "thrust": "kN", "isp": "s", "range": "nmi",
        "g_force": "g_force", "reliability": "probability",
        "mtbf": "hours", "fuel_consumption": "kg/h",
    },
    "energy": {
        "production": "MWh", "consumption": "MWh", "capacity": "MW",
        "lcoe": "USD", "price": "USD", "emissions": "tCO2e",
        "capacity_factor": "%", "efficiency": "%",
        "heat_rate": "MMBTU", "fuel_cost": "USD",
    },
    "real_estate": {
        "price": "USD", "rent": "USD", "noi": "USD",
        "cap_rate": "%", "grm": "ratio", "dscr": "ratio",
        "ltv": "%", "irr": "%", "occupancy": "%",
        "price_per_sqft": "USD",
    },
    "insurance": {
        "loss_ratio": "percentage", "combined_ratio": "percentage",
        "premium": "USD", "claims": "USD", "mortality": "probability",
        "hazard_rate": "probability", "lapse_rate": "percentage",
    },
    "environmental": {
        "concentration": "μg/m³", "ph": "ph", "do": "mg/L",
        "bod": "mg/L", "radiation": "μSv/h", "emissions": "tCO2e",
        "temperature": "°C", "humidity": "%",
    },
    # ── New domains ───────────────────────────────────────────────────────────
    "racing": {
        "lap_time": "lap_s", "lap": "lap_s", "sector_time": "sector_s",
        "speed": "km/h", "top_speed": "km/h", "velocity": "m/s",
        "rpm": "rpm", "gear": "count", "position": "pos",
        "tyre_degradation": "%", "fuel_load": "kg", "downforce": "N",
        "braking_distance": "m", "lateral_g": "g_force",
        "delta_time": "s", "gap": "s", "interval": "s",
        "pit_time": "s", "stint_length": "count",
    },
    "sports": {
        "score": "score", "points": "points", "goals": "count",
        "distance": "m", "time": "s", "speed": "m/s",
        "elo": "elo", "rating": "elo", "ranking": "count",
        "win_probability": "probability", "expected_goals": "ratio",
        "shots": "count", "possession": "%", "pass_accuracy": "%",
        "height": "m", "weight": "kg", "sprint_speed": "m/s",
        "margin": "score", "handicap": "score",
    },
    "physics": {
        "force": "N", "mass": "kg", "acceleration": "m/s²",
        "velocity": "m/s", "energy": "J", "power": "W",
        "temperature": "K", "pressure": "Pa", "frequency": "Hz",
        "wavelength": "m", "electric_field": "V/m",
        "magnetic_field": "T", "charge": "C", "voltage": "V",
        "current": "A", "resistance": "Ω",
        "lorentz_factor": "ratio",   # γ = 1/sqrt(1-v²/c²)
        "time_dilation": "ratio",    # Δt'/Δt
    },
    "space": {
        "distance": "au", "orbital_radius": "au",
        "velocity": "km/s", "escape_velocity": "km/s",
        "mass": "kg", "diameter": "km",
        "period": "days", "orbital_period": "days",
        "temperature": "K", "luminosity": "W",
        "parallax": "arcsec", "redshift": "ratio",
        "gravity": "m/s²", "density": "kg/m³",
    },
    "relativistic": {
        "velocity": "m/s",            # fraction of c: use sim_scale=c
        "velocity_fraction_c": "ratio",  # v/c ∈ [0,1)
        "lorentz_factor": "ratio",    # γ ≥ 1
        "time_dilation": "ratio",     # Δt/Δτ
        "length_contraction": "ratio",# L/L₀
        "mass_energy": "J",          # E = γmc²
        "rapidity": "ratio",          # φ = atanh(v/c)
    },
    "geospatial": {
        "latitude": "lat", "longitude": "lon",
        "altitude": "altitude_m", "elevation": "altitude_m",
        "distance": "distance_km", "radius": "distance_km",
        "area": "km²", "speed": "km/h", "bearing": "deg",
        "temperature": "°C", "precipitation": "mm",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# ── UnitSpec dataclass ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class UnitSpec:
    """
    Parsed unit specification for any numeric domain.

    Fields:
      type       — unit category (see UNIT_TYPES)
      code       — unit identifier ("USD", "BTC_sat", "Cpk", "nM", "Mach", ...)
      precision  — display decimal places (None = auto-inferred)
      scale      — multiply raw simulation value for display (e.g. 100 for %)
      format     — "standard" | "compact" | "scientific" | "labeled"
      base_unit  — sub-unit label ("satoshi", "wei", "Gwei", ...)
      sim_scale  — divide INPUT by this before simulation (e.g. 1e8 for BTC_sat)
      label      — optional display label suffix (e.g. "IC₅₀", "t½")
      range_min  — validation lower bound (None = no check)
      range_max  — validation upper bound (None = no check)
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
        self.type       = unit_type
        self.code       = code
        self.precision  = precision
        self.scale      = scale
        self.format     = fmt
        self.base_unit  = base_unit
        self.sim_scale  = sim_scale
        self.label      = label
        self.range_min  = range_min
        self.range_max  = range_max

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | str | None) -> UnitSpec:
        if raw is None:
            return cls()
        if isinstance(raw, str):
            return cls._from_string(raw)
        return cls._from_dict(raw)

    @classmethod
    def _from_string(cls, s: str) -> UnitSpec:  # noqa: C901
        s = s.strip()
        su = s.upper()
        sl = s.lower()

        # ── Currency ──────────────────────────────────────────────────────────
        if su in CURRENCY_PRECISION:
            return cls(unit_type="currency", code=su,
                       precision=CURRENCY_PRECISION[su])

        # ── Crypto sub-units ──────────────────────────────────────────────────
        if sl in {k.lower() for k in CRYPTO_SUB_UNITS}:
            # Normalize to canonical key
            key = next(k for k in CRYPTO_SUB_UNITS if k.lower() == sl)
            label, sim_scale, parent = CRYPTO_SUB_UNITS[key]
            return cls(unit_type="crypto_sub", code=key,
                       precision=0 if sim_scale >= 1e6 else 4,
                       sim_scale=sim_scale, base_unit=label,
                       label=f"{label} ({parent})")

        # Crypto sub-units by shorthand like "gwei", "satoshi", "wei"
        _shorthand_map = {
            "satoshi": "BTC_sat", "sat": "BTC_sat",
            "gwei": "ETH_gwei", "wei": "ETH_wei",
            "lamport": "SOL_lamport", "lamp": "SOL_lamport",
            "drop": "XRP_drop",
        }
        if sl in _shorthand_map:
            return cls._from_string(_shorthand_map[sl])

        # ── Whole-coin crypto ─────────────────────────────────────────────────
        if su in CRYPTO_DISPLAY_DECIMALS:
            return cls(unit_type="crypto", code=su,
                       precision=CRYPTO_DISPLAY_DECIMALS[su])

        # ── Percentage ────────────────────────────────────────────────────────
        if s in ("%", "pct", "percent", "percentage"):
            return cls(unit_type="percentage", code="%", precision=2, scale=1.0,
                       range_min=-100.0, range_max=100.0)

        # ── Basis points ──────────────────────────────────────────────────────
        if sl in ("bps", "basis_points", "bp"):
            return cls(unit_type="bps", code="bps", precision=1, scale=10000.0)

        # ── Probability ───────────────────────────────────────────────────────
        if sl in ("probability", "prob", "p"):
            return cls(unit_type="probability", code="probability", precision=4,
                       range_min=0.0, range_max=1.0)

        # ── Count ─────────────────────────────────────────────────────────────
        if sl in ("count", "integer", "int", "#"):
            # Exclude "n" — conflicts with Newton (N) and nano prefix
            return cls(unit_type="count", code="count", precision=0, range_min=0.0)

        # ── Date ──────────────────────────────────────────────────────────────
        if sl in ("date", "datetime", "timestamp", "epoch_days"):
            return cls(unit_type="date", code="date", precision=0)

        # ── Duration ─────────────────────────────────────────────────────────
        # Exclude "m" (meters), "n" (Newton/nano), bare "s" at this stage
        # — those are handled as length/force/SI below
        _duration_explicit = ("h", "hours", "hour", "d", "days", "day",
                               "min", "minutes", "minute",
                               "y", "yr", "years", "year",
                               "mo", "months", "month",
                               "w", "wk", "week", "weeks",
                               "ms", "us", "ns", "μs", "sec", "second", "seconds",
                               "q", "quarter", "quarters")
        if (sl in DURATION_TO_SECONDS and sl not in ("m", "n", "s")) or sl in _duration_explicit:
            return cls(unit_type="duration", code=sl, precision=2)

        # ── Six Sigma / Quality ───────────────────────────────────────────────
        if sl in ("cpk", "ppk", "cp", "pp"):
            # Proper industry notation: Cpk, Ppk, Cp, Pp (not CPK)
            _sigma_labels = {"cpk": "Cpk", "ppk": "Ppk", "cp": "Cp", "pp": "Pp"}
            lbl = _sigma_labels[sl]
            return cls(unit_type="six_sigma", code=lbl, precision=2,
                       range_min=0.0, label=lbl)
        if sl in ("sigma", "sigma_level"):
            return cls(unit_type="six_sigma", code="σ", precision=2,
                       range_min=0.0, range_max=6.5)
        if sl in ("dpmo",):
            return cls(unit_type="dpmo", code="DPMO", precision=0, range_min=0.0)
        if sl in ("ppm_defect", "ppm", "ppm_def"):
            return cls(unit_type="ppm_defect", code="ppm", precision=2, range_min=0.0)
        if sl in ("oee",):
            return cls(unit_type="oee", code="OEE", precision=1, scale=100.0,
                       range_min=0.0, range_max=1.0)
        if sl in ("mtbf",):
            return cls(unit_type="mtbf", code="h", precision=1, range_min=0.0,
                       label="MTBF")
        if sl in ("mttr",):
            return cls(unit_type="mttr", code="h", precision=2, range_min=0.0,
                       label="MTTR")

        # ── Medical stats ─────────────────────────────────────────────────────
        if sl in ("nnt", "number_needed_to_treat"):
            return cls(unit_type="medical_stat", code="NNT", precision=1,
                       range_min=0.0, label="NNT")
        if sl in ("nnh", "number_needed_to_harm"):
            return cls(unit_type="medical_stat", code="NNH", precision=1,
                       range_min=0.0, label="NNH")
        if sl in ("or", "odds_ratio"):
            return cls(unit_type="medical_stat", code="OR", precision=2,
                       range_min=0.0, label="OR")
        if sl in ("hr", "hazard_ratio"):
            return cls(unit_type="medical_stat", code="HR", precision=2,
                       range_min=0.0, label="HR")
        if sl in ("rr", "relative_risk", "risk_ratio"):
            return cls(unit_type="medical_stat", code="RR", precision=2,
                       range_min=0.0, label="RR")
        if sl in ("arr", "absolute_risk_reduction"):
            return cls(unit_type="medical_stat", code="ARR", precision=3,
                       label="ARR")
        if sl in ("cohens_d", "cohen_d", "effect_size"):
            return cls(unit_type="medical_stat", code="d", precision=2,
                       label="Cohen's d")
        if sl in ("p_value", "p-value", "pval"):
            return cls(unit_type="p_value", code="p", precision=4,
                       range_min=0.0, range_max=1.0)

        # ── Pharma ────────────────────────────────────────────────────────────
        if sl in ("nm", "nanomolar"):
            return cls(unit_type="pharma", code="nM", precision=3, label="nM")
        if sl in ("um", "μm", "micromolar"):
            return cls(unit_type="pharma", code="μM", precision=3, label="μM")
        if sl in ("mm", "millimolar"):
            return cls(unit_type="pharma", code="mM", precision=3, label="mM")
        if sl in ("half_life", "t_half", "t1/2", "t½"):
            return cls(unit_type="half_life", code="h", precision=2,
                       range_min=0.0, label="t½")
        if sl in ("bioavailability", "f", "f%"):
            return cls(unit_type="percentage", code="%", precision=1,
                       range_min=0.0, range_max=100.0, label="F")

        # ── Concentration ─────────────────────────────────────────────────────
        if sl in CONCENTRATION_LABELS:
            canonical = CONCENTRATION_LABELS[sl]
            return cls(unit_type="concentration", code=canonical, precision=3)
        # Common clinical
        if sl in ("mg/dl",):
            return cls(unit_type="concentration", code="mg/dL", precision=1)
        if sl in ("mmol/l",):
            return cls(unit_type="concentration", code="mmol/L", precision=2)
        if sl in ("iu/l", "u/l"):
            return cls(unit_type="concentration", code="IU/L", precision=1)

        # ── Aerospace ─────────────────────────────────────────────────────────
        if sl in ("mach",):
            return cls(unit_type="aerospace", code="Mach", precision=2,
                       range_min=0.0, label="Mach")
        if sl in ("g", "g_force", "gee"):
            return cls(unit_type="aerospace", code="g", precision=2,
                       range_min=0.0, label="g")
        if sl in ("kts", "knots", "kt"):
            return cls(unit_type="aerospace", code="kts", precision=1, label="kts")
        if sl in ("nmi", "nm_nautical", "nautical_miles"):
            return cls(unit_type="aerospace", code="nmi", precision=1, label="nmi")
        if sl in ("kn", "kn_thrust"):
            return cls(unit_type="aerospace", code="kN", precision=1, label="kN")
        if sl in ("isp",):
            return cls(unit_type="aerospace", code="s", precision=1, label="Isp")

        # ── Radiation ─────────────────────────────────────────────────────────
        if sl in ("msv", "milli_sievert"):
            return cls(unit_type="radiation", code="mSv", precision=3, range_min=0.0)
        if sl in ("usv", "μsv", "micro_sievert", "μsv/h", "usv/h"):
            code = "μSv/h" if "h" in sl else "μSv"
            return cls(unit_type="radiation", code=code, precision=3, range_min=0.0)
        if sl in ("sv",):
            return cls(unit_type="radiation", code="Sv", precision=4, range_min=0.0)
        if sl in ("bq/m3", "bq/m³"):
            return cls(unit_type="radiation", code="Bq/m³", precision=1, range_min=0.0)

        # ── Energy ────────────────────────────────────────────────────────────
        if sl in ("kwh", "kWh"):
            return cls(unit_type="energy", code="kWh", precision=2)
        if sl in ("mwh",):
            return cls(unit_type="energy", code="MWh", precision=2)
        if sl in ("gwh",):
            return cls(unit_type="energy", code="GWh", precision=2)
        if sl in ("mmbtu",):
            return cls(unit_type="energy", code="MMBTU", precision=3)
        if sl in ("mw",):
            return cls(unit_type="power", code="MW", precision=2)
        if sl in ("gw",):
            return cls(unit_type="power", code="GW", precision=3)
        if sl in ("kw",):
            return cls(unit_type="power", code="kW", precision=2)

        # ── Carbon ────────────────────────────────────────────────────────────
        if sl in ("tco2e", "t_co2e", "mtco2e"):
            code = "MtCO₂e" if sl.startswith("mt") else "tCO₂e"
            return cls(unit_type="carbon", code=code, precision=2, range_min=0.0)
        if sl in ("kgco2e",):
            return cls(unit_type="carbon", code="kgCO₂e", precision=1, range_min=0.0)

        # ── Environmental ─────────────────────────────────────────────────────
        if sl in ("ppm_conc", "ppm_concentration"):
            return cls(unit_type="ppm_conc", code="ppm", precision=3, range_min=0.0)
        if sl in ("ppb_conc", "ppb"):
            return cls(unit_type="ppb_conc", code="ppb", precision=3, range_min=0.0)
        if sl in ("ph",):
            return cls(unit_type="ph", code="pH", precision=2,
                       range_min=0.0, range_max=14.0)

        # ── Real estate ───────────────────────────────────────────────────────
        if sl in ("cap_rate",):
            return cls(unit_type="real_estate", code="%", precision=2,
                       label="cap rate", range_min=0.0)
        if sl in ("grm",):
            return cls(unit_type="real_estate", code="×", precision=1,
                       label="GRM", range_min=0.0)
        if sl in ("dscr",):
            return cls(unit_type="ratio", code="×", precision=2,
                       label="DSCR", range_min=0.0)

        # ── Actuarial ─────────────────────────────────────────────────────────
        if sl in ("loss_ratio", "loss_r"):
            return cls(unit_type="actuarial", code="%", precision=1,
                       scale=100.0, label="LR", range_min=0.0)
        if sl in ("combined_ratio", "combined_r"):
            return cls(unit_type="actuarial", code="%", precision=1,
                       scale=100.0, label="CR", range_min=0.0)

        # ── Mass / Weight ─────────────────────────────────────────────────────
        if sl in MASS_TO_KG:
            return cls(unit_type="mass", code=s, precision=3, range_min=0.0)
        if sl in ("weight", "mass", "kg_mass"):
            return cls(unit_type="mass", code="kg", precision=3, range_min=0.0)

        # ── Length / Height / Distance ────────────────────────────────────────
        if sl in LENGTH_TO_M or sl in ("length", "height", "depth", "width", "distance"):
            code = s if s in LENGTH_TO_M else "m"
            return cls(unit_type="length", code=code, precision=3, range_min=0.0)

        # ── Area ──────────────────────────────────────────────────────────────
        if sl in AREA_TO_M2 or sl in ("area", "surface"):
            code = s if s in AREA_TO_M2 else "m²"
            return cls(unit_type="area", code=code, precision=3, range_min=0.0)
        if sl in ("ha", "hectare", "hectares"):
            return cls(unit_type="area", code="ha", precision=2, range_min=0.0)
        if sl in ("acre", "acres", "ac"):
            return cls(unit_type="area", code="acre", precision=2, range_min=0.0)

        # ── Volume ────────────────────────────────────────────────────────────
        if sl in VOLUME_TO_L or sl in ("volume", "vol", "capacity"):
            code = s if s in VOLUME_TO_L else "L"
            return cls(unit_type="volume", code=code, precision=3, range_min=0.0)

        # ── Density ───────────────────────────────────────────────────────────
        if sl in ("kg/m³", "kg/m3", "g/cm³", "g/cm3", "g/ml", "g/mL",
                  "kg/l", "kg/L", "lb/ft³", "lb/ft3", "density"):
            code = s.replace("3", "³").replace("/l", "/L")
            return cls(unit_type="density", code=code, precision=3, range_min=0.0)

        # ── Pressure ──────────────────────────────────────────────────────────
        if sl in PRESSURE_TO_PA:
            p = 2 if sl in ("bar", "mbar", "atm", "psi") else 0 if sl.startswith("pa") else 3
            return cls(unit_type="pressure", code=s, precision=p, range_min=0.0)
        if sl in ("pressure", "stress"):
            return cls(unit_type="pressure", code="Pa", precision=1, range_min=0.0)

        # ── Force / Torque ────────────────────────────────────────────────────
        if sl in FORCE_TO_N:
            return cls(unit_type="force", code=s, precision=2, range_min=0.0)
        if sl in ("force", "thrust"):
            return cls(unit_type="force", code="N", precision=2, range_min=0.0)
        if sl in ("n·m", "nm_torque", "ft·lb", "ft_lb", "ft_lbf", "n*m", "torque"):
            return cls(unit_type="torque", code=s, precision=2)

        # ── Data size ─────────────────────────────────────────────────────────
        if sl in DATA_SIZE_TO_BYTES or sl in ("data", "storage", "file_size", "memory"):
            code = s if s in DATA_SIZE_TO_BYTES else "MB"
            return cls(unit_type="data_size", code=code, precision=2, range_min=0.0)

        # ── Data rate ─────────────────────────────────────────────────────────
        if sl in DATA_RATE_TO_BPS or sl in ("bandwidth", "throughput_bps", "data_rate"):
            code = s if s in DATA_RATE_TO_BPS else "Mbps"
            return cls(unit_type="data_rate", code=code, precision=2, range_min=0.0)

        # ── Frequency ─────────────────────────────────────────────────────────
        if sl in FREQUENCY_TO_HZ or sl in ("frequency", "freq"):
            code = s if s in FREQUENCY_TO_HZ else "Hz"
            return cls(unit_type="frequency", code=code, precision=3, range_min=0.0)

        # ── Rate / Flux ───────────────────────────────────────────────────────
        if "/" in s and s not in CONCENTRATION_LABELS:
            # Generic rate: events/h, L/min, m³/s, failures/M, etc.
            return cls(unit_type="rate", code=s, precision=3, range_min=0.0)

        # ── Ratio / unitless ─────────────────────────────────────────────────
        if sl in ("ratio", "unitless", "x"):
            return cls(unit_type="ratio", code="×", precision=2, range_min=0.0)

        # ── Speed / velocity ──────────────────────────────────────────────────
        if sl in SPEED_TO_MS or sl in ("speed", "velocity", "vel"):
            display = s if s in SPEED_DISPLAY_UNITS else "m/s"
            return cls(unit_type="speed", code=display, precision=2, range_min=0.0)
        if sl in ("km/h", "kph", "kmh"):
            return cls(unit_type="speed", code="km/h", precision=1, range_min=0.0)
        if sl in ("mph", "mi/h"):
            return cls(unit_type="speed", code="mph", precision=1, range_min=0.0)
        if sl in ("m/s", "ms_speed"):
            return cls(unit_type="speed", code="m/s", precision=2, range_min=0.0)
        if sl in ("rpm",):
            return cls(unit_type="angular", code="rpm", precision=1, range_min=0.0,
                       label="rpm")
        if sl in ("rad/s", "rads"):
            return cls(unit_type="angular", code="rad/s", precision=3, range_min=0.0)
        if sl in ("deg/s", "°/s"):
            return cls(unit_type="angular", code="°/s", precision=2)

        # ── Angular ───────────────────────────────────────────────────────────
        if sl in ("deg", "°", "degrees"):
            return cls(unit_type="angular", code="°", precision=2,
                       range_min=0.0, range_max=360.0)
        if sl in ("rad", "radians"):
            return cls(unit_type="angular", code="rad", precision=4,
                       range_min=0.0, range_max=6.283185307)

        # ── Temperature ───────────────────────────────────────────────────────
        if sl in ("°c", "celsius", "c_temp"):
            return cls(unit_type="temperature", code="°C", precision=2)
        if sl in ("°f", "fahrenheit", "f_temp"):
            return cls(unit_type="temperature", code="°F", precision=2)
        if sl in ("k", "kelvin") and s not in ("K",):
            return cls(unit_type="temperature", code="K",  precision=2, range_min=0.0)
        if s == "K":
            return cls(unit_type="temperature", code="K",  precision=2, range_min=0.0)

        # ── Sports / racing ───────────────────────────────────────────────────
        if sl in SPORTS_UNITS:
            lbl, prec, _ = SPORTS_UNITS[sl]
            return cls(unit_type="sports", code=lbl or sl, precision=prec,
                       range_min=0.0, label=sl)
        if sl in ("elo",):
            return cls(unit_type="sports", code="ELO", precision=0,
                       range_min=0.0, range_max=4000.0, label="ELO")
        if sl in ("lap_time", "lap_s", "laptime"):
            return cls(unit_type="sports", code="s", precision=3,
                       range_min=0.0, label="lap")
        if sl in ("sector_s", "sector_time"):
            return cls(unit_type="sports", code="s", precision=3,
                       range_min=0.0, label="sector")

        # ── Geospatial / coordinate ───────────────────────────────────────────
        if sl in ("lat", "latitude"):
            return cls(unit_type="coordinate", code="°N", precision=6,
                       range_min=-90.0, range_max=90.0, label="lat")
        if sl in ("lon", "lng", "longitude"):
            return cls(unit_type="coordinate", code="°E", precision=6,
                       range_min=-180.0, range_max=180.0, label="lon")
        if sl in ("altitude", "altitude_m", "alt_m"):
            return cls(unit_type="coordinate", code="m", precision=1, label="alt")
        if sl in ("altitude_ft", "alt_ft"):
            return cls(unit_type="coordinate", code="ft", precision=0, label="alt",
                       sim_scale=0.3048)  # ft → m for simulation
        if sl in ("distance_km", "dist_km"):
            return cls(unit_type="coordinate", code="km", precision=3, range_min=0.0)
        if sl in ("distance_mi", "dist_mi"):
            return cls(unit_type="coordinate", code="mi", precision=3, range_min=0.0,
                       sim_scale=1.60934)

        # ── Fallback: SI/scientific ───────────────────────────────────────────
        return cls(unit_type="si", code=s, precision=4)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> UnitSpec:
        unit_type  = str(d.get("type",  d.get("unit_type", "raw"))).lower()
        code       = str(d.get("code",  d.get("unit", "")))
        precision  = d.get("precision")
        scale      = float(d.get("scale", 1.0))
        fmt        = str(d.get("format", "standard"))
        base_unit  = str(d.get("base_unit", ""))
        sim_scale  = float(d.get("sim_scale", 1.0))
        label      = str(d.get("label", ""))
        range_min  = d.get("range_min")
        range_max  = d.get("range_max")

        # Auto-fill currency defaults
        cu = code.upper()
        if unit_type == "currency" and cu in CURRENCY_PRECISION:
            if precision is None:
                precision = CURRENCY_PRECISION[cu]

        # Auto-fill crypto sub-unit defaults
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

        return cls(
            unit_type=unit_type, code=code, precision=precision,
            scale=scale, fmt=fmt, base_unit=base_unit, sim_scale=sim_scale,
            label=label, range_min=range_min, range_max=range_max,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ── Preprocessing ─────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def preprocess_variable(var: dict[str, Any], unit_spec: UnitSpec) -> dict[str, Any]:
    """Normalize variable params before sending to Mojo."""
    params = dict(var.get("params", {}))

    if unit_spec.type == "date":
        for key in ("mean", "mode", "low", "high", "likely", "value"):
            if key in params and isinstance(params[key], str):
                params[key] = _date_to_epoch_days(params[key])

    elif unit_spec.sim_scale not in (1.0, 0.0):
        # Apply scale: divide input by sim_scale (crypto, custom)
        for key in ("mean", "mode", "low", "high", "likely", "value"):
            if key in params and isinstance(params[key], int | float):
                params[key] = float(params[key]) / unit_spec.sim_scale

    return {**var, "params": params}


def validate_variable(var: dict[str, Any], unit_spec: UnitSpec) -> list[str]:
    """Return advisory warnings for a variable given its unit spec."""
    warnings: list[str] = []
    params = var.get("params", {})
    name   = var.get("name", "?")
    utype  = unit_spec.type
    code   = unit_spec.code.upper()

    # Generic range check
    lo = unit_spec.range_min
    hi = unit_spec.range_max
    for key in ("mean", "low", "high", "mode", "value"):
        val = params.get(key)
        if val is None:
            continue
        fval = float(val)
        if lo is not None and fval < lo:
            warnings.append(
                f"Variable '{name}': {key}={val} is below minimum {lo} for unit '{unit_spec.code}'."
            )
        if hi is not None and fval > hi:
            warnings.append(
                f"Variable '{name}': {key}={val} exceeds maximum {hi} for unit '{unit_spec.code}'."
            )

    # Domain-specific checks
    if utype == "currency":
        for key in ("low", "mean", "value"):
            val = params.get(key)
            if val is not None and float(val) < 0:
                warnings.append(
                    f"Variable '{name}': {key}={val} is negative for currency '{code}'. "
                    "Intentional for P&L? Use negative explicitly."
                )

    if utype == "crypto":
        if code == "BTC":
            for key in ("mean", "high", "value"):
                val = params.get(key)
                if val is not None and float(val) > 21_000_000:
                    warnings.append(
                        f"Variable '{name}': {key}={float(val):,.0f} > 21M BTC total supply. "
                        f"Did you mean {float(val)/1e8:.6f} BTC (input in satoshis)? "
                        "Use unit_spec='BTC_sat' and sim_scale=1e8."
                    )
        for key in ("mean", "low", "high", "value"):
            val = params.get(key)
            if val is not None and float(val) < 0:
                warnings.append(
                    f"Variable '{name}': {key}={val} is negative for crypto '{code}'."
                )

    if utype == "crypto_sub":
        parent = unit_spec.label.split("(")[-1].rstrip(")") if "(" in unit_spec.label else ""
        if parent == "ETH":
            for key in ("mean", "high", "value"):
                val = params.get(key)
                if val is not None and float(val) > 1e18 * 1e8:
                    warnings.append(
                        f"Variable '{name}': value seems too large for ETH wei. "
                        "Check if sim_scale is set correctly."
                    )

    if utype == "six_sigma":
        for key in ("mean", "value"):
            val = params.get(key)
            if val is not None:
                fval = float(val)
                if fval < 0.67:
                    warnings.append(
                        f"Variable '{name}': {code}={fval:.2f} is very poor quality "
                        "(< 0.67 → > 10% defect rate). Check units."
                    )
                elif fval > 6.0:
                    warnings.append(
                        f"Variable '{name}': {code}={fval:.2f} exceeds Six Sigma (6σ). "
                        "Values above 2.0 are excellent; above 6.0 is physically rare."
                    )

    if utype == "p_value":
        for key in ("mean", "value"):
            val = params.get(key)
            if val is not None and float(val) > 1.0:
                warnings.append(
                    f"Variable '{name}': p-value={val} > 1.0. p-values are [0,1]."
                )

    if utype == "ph":
        for key in ("mean", "low", "high", "value"):
            val = params.get(key)
            if val is not None and not (0.0 <= float(val) <= 14.0):
                warnings.append(
                    f"Variable '{name}': pH={val} is outside [0,14]."
                )

    if utype == "oee":
        for key in ("mean", "high", "value"):
            val = params.get(key)
            if val is not None:
                fval = float(val)
                # Detect if someone passed 0-100 instead of 0-1
                if fval > 1.0:
                    warnings.append(
                        f"Variable '{name}': OEE={fval}. OEE is typically expressed "
                        "as [0,1]. Use scale=100.0 for display as %. "
                        "If you meant {fval}%, set value={fval/100:.2f}."
                    )

    if utype == "date":
        for key in ("mean", "low", "high", "value"):
            val = params.get(key)
            if val is not None and isinstance(val, int | float):
                if float(val) > 1e9:
                    warnings.append(
                        f"Variable '{name}': {key}={val} looks like Unix epoch seconds "
                        "(> 1e9). Provide epoch days or ISO date string instead."
                    )

    return warnings


# ═══════════════════════════════════════════════════════════════════════════════
# ── Formatting ────────────────────────────────────════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

def format_value(value: float, unit_spec: UnitSpec) -> str:  # noqa: C901
    """Format a single float value with the given unit spec."""
    if not math.isfinite(value):
        return str(value)

    utype = unit_spec.type
    code  = unit_spec.code
    prec  = unit_spec.precision
    fmt   = unit_spec.format
    scale = unit_spec.scale
    label = unit_spec.label
    dv    = value * scale  # display value

    # ── Currency ──────────────────────────────────────────────────────────────
    if utype == "currency":
        symbol = CURRENCY_SYMBOLS.get(code.upper(), code + " ")
        p = prec if prec is not None else CURRENCY_PRECISION.get(code.upper(), 2)
        if fmt == "compact":
            return symbol + _compact(dv, p)
        return symbol + f"{dv:,.{p}f}"

    # ── Crypto (whole coin) ───────────────────────────────────────────────────
    if utype == "crypto":
        p = prec if prec is not None else CRYPTO_DISPLAY_DECIMALS.get(code.upper(), 6)
        if fmt == "compact":
            return f"{dv:.{min(p,4)}g} {code}"
        return f"{dv:.{p}f} {code}"

    # ── Crypto sub-unit ───────────────────────────────────────────────────────
    if utype == "crypto_sub":
        sub_label = unit_spec.base_unit or code
        p = prec if prec is not None else 0
        if dv >= 1e6:
            return f"{dv:,.{max(0, p)}f} {sub_label}"
        return f"{dv:.{p}f} {sub_label}"

    # ── Percentage ────────────────────────────────────────────────────────────
    if utype == "percentage":
        p = prec if prec is not None else 2
        suffix = f" {label}" if label else ""
        return f"{dv:.{p}f}%{suffix}"

    # ── Basis points ─────────────────────────────────────────────────────────
    if utype == "bps":
        p = prec if prec is not None else 1
        return f"{dv:.{p}f} bps"

    # ── Probability ───────────────────────────────────────────────────────────
    if utype == "probability":
        p = prec if prec is not None else 4
        return f"{dv:.{p}f}"

    # ── Count ─────────────────────────────────────────────────────────────────
    if utype == "count":
        return f"{int(round(dv)):,}"

    # ── Date ──────────────────────────────────────────────────────────────────
    if utype == "date":
        return _epoch_days_to_iso(dv)

    # ── Duration ─────────────────────────────────────────────────────────────
    if utype == "duration":
        return _format_duration(dv, code)

    # ── Six Sigma ─────────────────────────────────────────────────────────────
    if utype == "six_sigma":
        p = prec if prec is not None else 2
        lbl = label or code
        return f"{lbl} = {dv:.{p}f}"

    if utype == "dpmo":
        return f"{dv:,.0f} DPMO"

    if utype == "ppm_defect":
        p = prec if prec is not None else 2
        return f"{dv:.{p}f} ppm"

    if utype == "oee":
        p = prec if prec is not None else 1
        return f"{dv:.{p}f}% OEE"

    if utype in ("mtbf", "mttr"):
        lbl = label or code
        p = prec if prec is not None else 1
        return f"{lbl} = {dv:.{p}f} h"

    # ── Medical statistics ────────────────────────────────────────────────────
    if utype == "medical_stat":
        p = prec if prec is not None else 2
        lbl = label or code
        if lbl in ("NNT", "NNH"):
            return f"{lbl} = {dv:.{max(0,p-1)}f}"
        return f"{lbl} {dv:.{p}f}"

    if utype == "p_value":
        if dv < 0.001:
            return "p < 0.001"
        if dv < 0.01:
            return f"p = {dv:.3f}"
        if dv < 0.05:
            return f"p = {dv:.3f}"
        return f"p = {dv:.2f}"

    # ── Concentration ─────────────────────────────────────────────────────────
    if utype == "concentration":
        p = prec if prec is not None else 3
        abs_dv = abs(dv)
        if abs_dv > 0 and (abs_dv < 0.001 or abs_dv >= 1e6):
            return f"{dv:.{p}e} {code}"
        return f"{dv:.{p}f} {code}"

    # ── Pharma ────────────────────────────────────────────────────────────────
    if utype == "pharma":
        p = prec if prec is not None else 3
        lbl = label or code
        abs_dv = abs(dv)
        if abs_dv > 0 and abs_dv < 0.001:
            return f"{dv:.{p}e} {lbl}"
        return f"{dv:.{p}f} {lbl}"

    if utype == "half_life":
        p = prec if prec is not None else 2
        return f"t½ = {dv:.{p}f} h"

    # ── Aerospace ─────────────────────────────────────────────────────────────
    if utype == "aerospace":
        p = prec if prec is not None else 2
        lbl = label or code
        return f"{dv:.{p}f} {lbl}"

    # ── Radiation ─────────────────────────────────────────────────────────────
    if utype == "radiation":
        p = prec if prec is not None else 3
        return f"{dv:.{p}f} {code}"

    # ── Energy ────────────────────────────────────────────────────────────────
    if utype in ("energy", "power", "fuel"):
        p = prec if prec is not None else 2
        if fmt == "compact":
            return _compact(dv, p) + f" {code}"
        return f"{dv:,.{p}f} {code}"

    # ── Carbon ────────────────────────────────────────────────────────────────
    if utype == "carbon":
        p = prec if prec is not None else 2
        if fmt == "compact":
            return _compact(dv, p) + f" {code}"
        return f"{dv:,.{p}f} {code}"

    # ── Environmental ─────────────────────────────────────────────────────────
    if utype in ("ppm_conc", "ppb_conc"):
        p = prec if prec is not None else 3
        return f"{dv:.{p}f} {code}"

    if utype == "ph":
        p = prec if prec is not None else 2
        return f"pH {dv:.{p}f}"

    # ── Real estate / actuarial ───────────────────────────────────────────────
    if utype in ("real_estate", "actuarial"):
        p = prec if prec is not None else 2
        lbl = label or ""
        if code in ("%",):
            return f"{dv:.{p}f}% {lbl}".strip()
        return f"{dv:.{p}f}{code} {lbl}".strip()

    # ── Mass / Weight ──────────────────────────────────────────────────────────
    if utype == "mass":
        p = prec if prec is not None else 3
        kg_val = dv * MASS_TO_KG.get(code.lower(), 1.0)
        if fmt == "compact" or code == "mass":
            if kg_val >= 1e6:
                return f"{kg_val/1e6:.{p}f} Mt"
            if kg_val >= 1e3:
                return f"{kg_val/1e3:.{p}f} t"
            if kg_val >= 1.0:
                return f"{kg_val:.{p}f} kg"
            if kg_val >= 1e-3:
                return f"{kg_val*1e3:.{p}f} g"
            if kg_val >= 1e-6:
                return f"{kg_val*1e6:.{p}f} mg"
            return f"{kg_val*1e9:.{p}f} μg"
        return f"{dv:.{p}f} {code}"

    # ── Length ────────────────────────────────────────────────────────────────
    if utype == "length":
        p = prec if prec is not None else 3
        m_val = dv * LENGTH_TO_M.get(code.lower(), LENGTH_TO_M.get(code, 1.0))
        if fmt == "compact" or code in ("m", "length"):
            if m_val >= 1e12:
                return f"{m_val/1e12:.{p}f} Tm"
            if m_val >= 1e9:
                return f"{m_val/1e9:.{p}f} Gm"
            if m_val >= 1e3:
                return f"{m_val/1e3:.{p}f} km"
            if m_val >= 1.0:
                return f"{m_val:.{p}f} m"
            if m_val >= 1e-2:
                return f"{m_val*100:.{p}f} cm"
            if m_val >= 1e-3:
                return f"{m_val*1000:.{p}f} mm"
            if m_val >= 1e-6:
                return f"{m_val*1e6:.{p}f} μm"
            if m_val >= 1e-9:
                return f"{m_val*1e9:.{p}f} nm"
            return f"{m_val:.{p}e} m"
        return f"{dv:.{p}f} {code}"

    # ── Area ──────────────────────────────────────────────────────────────────
    if utype == "area":
        p = prec if prec is not None else 2
        m2_val = dv * AREA_TO_M2.get(code.lower(), AREA_TO_M2.get(code, 1.0))
        if fmt == "compact":
            if m2_val >= 1e6:
                return f"{m2_val/1e6:.{p}f} km²"
            if m2_val >= 1e4:
                return f"{m2_val/1e4:.{p}f} ha"
            return f"{m2_val:.{p}f} m²"
        return f"{dv:.{p}f} {code}"

    # ── Volume ────────────────────────────────────────────────────────────────
    if utype == "volume":
        p = prec if prec is not None else 3
        l_val = dv * VOLUME_TO_L.get(code.lower(), VOLUME_TO_L.get(code, 1.0))
        if fmt == "compact":
            if l_val >= 1e3:
                return f"{l_val/1e3:.{p}f} m³"
            if l_val >= 1.0:
                return f"{l_val:.{p}f} L"
            if l_val >= 0.001:
                return f"{l_val*1000:.{p}f} mL"
            return f"{l_val*1e6:.{p}f} μL"
        return f"{dv:.{p}f} {code}"

    # ── Density ───────────────────────────────────────────────────────────────
    if utype == "density":
        p = prec if prec is not None else 3
        return f"{dv:.{p}f} {code}"

    # ── Pressure ──────────────────────────────────────────────────────────────
    if utype == "pressure":
        p = prec if prec is not None else 2
        pa_val = dv * PRESSURE_TO_PA.get(code.lower(), PRESSURE_TO_PA.get(code, 1.0))
        if fmt == "compact":
            if pa_val >= 1e9:
                return f"{pa_val/1e9:.{p}f} GPa"
            if pa_val >= 1e6:
                return f"{pa_val/1e6:.{p}f} MPa"
            if pa_val >= 1e3:
                return f"{pa_val/1e3:.{p}f} kPa"
            if pa_val >= 1e2:
                return f"{pa_val/1e5:.{p}f} bar"
            return f"{pa_val:.{p}f} Pa"
        return f"{dv:.{p}f} {code}"

    # ── Force ─────────────────────────────────────────────────────────────────
    if utype in ("force", "torque"):
        p = prec if prec is not None else 2
        return f"{dv:.{p}f} {code}"

    # ── Data size ─────────────────────────────────────────────────────────────
    if utype == "data_size":
        p = prec if prec is not None else 2
        if fmt == "compact" or code.lower() in ("b", "byte", "bytes"):
            b = dv * DATA_SIZE_TO_BYTES.get(code.lower(), DATA_SIZE_TO_BYTES.get(code, 1.0))
            if b >= 1e15:
                return f"{b/1e15:.{p}f} PB"
            if b >= 1e12:
                return f"{b/1e12:.{p}f} TB"
            if b >= 1e9:
                return f"{b/1e9:.{p}f} GB"
            if b >= 1e6:
                return f"{b/1e6:.{p}f} MB"
            if b >= 1e3:
                return f"{b/1e3:.{p}f} KB"
            return f"{b:.0f} B"
        return f"{dv:.{p}f} {code}"

    # ── Data rate ─────────────────────────────────────────────────────────────
    if utype == "data_rate":
        p = prec if prec is not None else 1
        if fmt == "compact":
            bps = dv * DATA_RATE_TO_BPS.get(code.lower(), DATA_RATE_TO_BPS.get(code, 1.0))
            if bps >= 1e12:
                return f"{bps/1e12:.{p}f} Tbps"
            if bps >= 1e9:
                return f"{bps/1e9:.{p}f} Gbps"
            if bps >= 1e6:
                return f"{bps/1e6:.{p}f} Mbps"
            if bps >= 1e3:
                return f"{bps/1e3:.{p}f} Kbps"
            return f"{bps:.{p}f} bps"
        return f"{dv:.{p}f} {code}"

    # ── Frequency ─────────────────────────────────────────────────────────────
    if utype == "frequency":
        p = prec if prec is not None else 3
        if fmt == "compact":
            hz = dv * FREQUENCY_TO_HZ.get(code.lower(), FREQUENCY_TO_HZ.get(code, 1.0))
            if hz >= 1e12:
                return f"{hz/1e12:.{p}f} THz"
            if hz >= 1e9:
                return f"{hz/1e9:.{p}f} GHz"
            if hz >= 1e6:
                return f"{hz/1e6:.{p}f} MHz"
            if hz >= 1e3:
                return f"{hz/1e3:.{p}f} kHz"
            return f"{hz:.{p}f} Hz"
        return f"{dv:.{p}f} {code}"

    # ── Rate / flux ───────────────────────────────────────────────────────────
    if utype == "rate":
        p = prec if prec is not None else 3
        return f"{dv:.{p}g} {code}"

    # ── Ratio / unitless ─────────────────────────────────────────────────────
    if utype == "ratio":
        p = prec if prec is not None else 2
        lbl = label or ""
        return f"{dv:.{p}f}× {lbl}".strip()

    if utype == "financial_ratio":
        p = prec if prec is not None else 2
        lbl = label or code
        return f"{lbl} {dv:.{p}f}"

    # ── Speed ────────────────────────────────────────────────────────────────
    if utype == "speed":
        p = prec if prec is not None else 1
        lbl = code or "m/s"
        if fmt == "compact":
            # Auto-convert to best unit for display
            ms = dv * SPEED_TO_MS.get(lbl.lower(), 1.0)
            if ms >= 340:
                return f"{ms / 340.29:.2f} Mach"
            if ms >= 50:
                return f"{ms * 3.6:.1f} km/h"
            return f"{ms:.2f} m/s"
        return f"{dv:.{p}f} {lbl}"

    # ── Angular ───────────────────────────────────────────────────────────────
    if utype == "angular":
        p = prec if prec is not None else 2
        lbl = code or label or "°"
        if lbl == "rpm":
            return f"{dv:,.{p}f} rpm"
        if lbl in ("rad/s",):
            return f"{dv:.{p}f} rad/s"
        # Degrees — normalize to [0, 360)
        if "°" in lbl or lbl == "deg":
            norm = dv % 360.0
            return f"{norm:.{p}f}°"
        return f"{dv:.{p}f} {lbl}"

    # ── Temperature ───────────────────────────────────────────────────────────
    if utype == "temperature":
        p = prec if prec is not None else 1
        return f"{dv:.{p}f} {code}"

    # ── Sports / racing ───────────────────────────────────────────────────────
    if utype == "sports":
        p = prec if prec is not None else 1
        lbl = label or code or ""
        if lbl in ("lap", "sector") or lbl.startswith("lap") or lbl.startswith("sector"):
            # Format as mm:ss.sss
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

    # ── Geospatial / coordinate ───────────────────────────────────────────────
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

    # ── SI / Scientific ───────────────────────────────────────────────────────
    if utype in ("si", "scientific"):
        p = prec if prec is not None else 4
        abs_dv = abs(dv)
        if fmt == "scientific" or (abs_dv > 0 and (abs_dv < 1e-3 or abs_dv >= 1e9)):
            return f"{dv:.{p}e} {code}".strip()
        return f"{dv:.{p}g} {code}".strip()

    # ── Raw / custom ─────────────────────────────────────────────────────────
    p = prec if prec is not None else 4
    lbl = code or label or ""
    abs_dv = abs(dv)
    if abs_dv > 0 and (abs_dv < 1e-3 or abs_dv >= 1e9):
        return f"{dv:.{p}e} {lbl}".strip()
    return f"{dv:.{p}g} {lbl}".strip()


# ═══════════════════════════════════════════════════════════════════════════════
# ── Pipeline entry points ─────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def preprocess_payload(
    payload: dict[str, Any],
    unit_specs_raw: list[dict | str | None],
) -> tuple[dict[str, Any], list[str]]:
    """Preprocess all variables in the Mojo payload per unit spec."""
    variables = payload.get("variables", [])
    warnings: list[str] = []
    new_variables = []
    for i, var in enumerate(variables):
        spec_raw = unit_specs_raw[i] if i < len(unit_specs_raw) else None
        spec = UnitSpec.from_raw(spec_raw)
        warnings.extend(validate_variable(var, spec))
        new_variables.append(preprocess_variable(var, spec))
    return {**payload, "variables": new_variables}, warnings


def postprocess_results(
    raw_stats: dict[str, float],
    output_unit_specs: list[dict[str, Any] | str | None],
    output_index: int = 0,
) -> dict[str, Any]:
    """Format raw simulation statistics for one output objective."""
    if not output_unit_specs or output_index >= len(output_unit_specs):
        spec = UnitSpec()
    else:
        spec = UnitSpec.from_raw(output_unit_specs[output_index])

    result: dict[str, Any] = {
        "unit": spec.code or "raw",
        "unit_type": spec.type,
        "label": spec.label or spec.code,
    }
    for key, val in raw_stats.items():
        if isinstance(val, int | float) and math.isfinite(val):
            result[f"{key}_formatted"] = format_value(val, spec)
            result[f"{key}_display"]   = val * spec.scale
        else:
            result[f"{key}_formatted"] = str(val) if val is not None else None
    return result


def build_unit_context(
    variables: list[dict[str, Any]],
    unit_specs_raw: list[dict | str | None],
    output_unit_specs_raw: list[dict | str | None] | None,
) -> dict[str, Any]:
    """Build the unit_context block for the DecisionEnvelope."""
    var_context: dict[str, Any] = {}
    for i, var in enumerate(variables):
        spec_raw = unit_specs_raw[i] if i < len(unit_specs_raw) else None
        spec = UnitSpec.from_raw(spec_raw)
        var_context[var.get("name", f"var_{i}")] = {
            "unit": spec.code, "type": spec.type,
            "precision": spec.precision, "scale": spec.scale,
            "sim_scale": spec.sim_scale, "label": spec.label,
        }
    out_context = []
    if output_unit_specs_raw:
        for raw in output_unit_specs_raw:
            spec = UnitSpec.from_raw(raw)
            out_context.append({
                "unit": spec.code, "type": spec.type,
                "precision": spec.precision, "format": spec.format,
                "label": spec.label,
            })
    return {"variables": var_context, "outputs": out_context}


def suggest_unit_specs(
    domain: str,
    variable_names: list[str],
) -> list[str | None]:
    """
    Auto-suggest unit shorthand strings for a list of variable names
    given a domain hint. Returns list aligned with variable_names.
    """
    hints = DOMAIN_VARIABLE_HINTS.get(domain.lower(), {})
    result: list[str | None] = []
    for name in variable_names:
        nl = name.lower().replace("-", "_").replace(" ", "_")
        # Exact match
        if nl in hints:
            result.append(hints[nl])
            continue
        # Substring match
        matched = None
        for hint_key, hint_val in hints.items():
            if hint_key in nl or nl in hint_key:
                matched = hint_val
                break
        result.append(matched)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ── Helpers ───────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

_EPOCH = date(1970, 1, 1)


def _date_to_epoch_days(s: str | float) -> float:
    """Convert ISO 8601 date string or Unix timestamp to epoch days."""
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


def _epoch_days_to_iso(epoch_days: float) -> str:
    try:
        d = date.fromordinal(_EPOCH.toordinal() + int(round(epoch_days)))
        return d.isoformat()
    except (ValueError, OverflowError):
        return str(epoch_days)


def _format_duration(value: float, unit: str) -> str:
    """Format duration with auto-scale to human-readable."""
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


def _compact(value: float, precision: int = 2) -> str:
    """Compact number formatting: 1.2M, 42.5K, 1.23B, etc."""
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


# ═══════════════════════════════════════════════════════════════════════════════
# ── Physical constants for objective_function expressions ────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def get_physical_constants() -> dict[str, float]:
    """
    Return all physical constants for use as expression variables.
    Inject into objective_function eval context so users can write:
      objective_function: "0.5 * mass * velocity**2"          (kinetic energy)
      objective_function: "mass * g * height"                  (potential energy)
      objective_function: "charge * voltage"                   (electrical energy)
      objective_function: "velocity / c"                       (beta factor)
      objective_function: "1 / sqrt(1 - (velocity/c)**2)"     (Lorentz factor γ)
      objective_function: "hbar * frequency"                   (photon energy E=ħω)
      objective_function: "kB * temperature * log(volume)"    (thermodynamics)

    Available constants:
      c         — speed of light (m/s)
      G         — gravitational constant (N·m²/kg²)
      g         — standard gravity (m/s²)
      hbar      — reduced Planck constant (J·s)
      h_planck  — Planck constant (J·s)
      kB        — Boltzmann constant (J/K)
      NA        — Avogadro number (mol⁻¹)
      R         — gas constant (J/mol·K)
      sigma_SB  — Stefan-Boltzmann constant (W/m²·K⁴)
      e_charge  — elementary charge (C)
      eps0      — vacuum permittivity (F/m)
      mu0       — vacuum permeability (H/m)
      au        — astronomical unit (m)
      ly        — light year (m)
      pc        — parsec (m)
      pi        — π
      phi       — golden ratio
      c_sound   — speed of sound in air at 20°C (m/s)
    """
    return dict(PHYSICAL_CONSTANTS)


def eval_with_constants(
    expr: str,
    variables: dict[str, float],
    extra_builtins: dict | None = None,
) -> float:
    """
    Evaluate an expression string with physical constants + variable values.
    Safe: restricted builtins only. Physical constants are automatically available.

    Example:
      eval_with_constants(
          "mass * g * height",
          {"mass": 70.0, "height": 10.0}
      )  # → 6865.0 (potential energy in J)

      eval_with_constants(
          "1 / sqrt(1 - (v/c)**2)",
          {"v": 0.9 * 299_792_458}
      )  # → ~2.294 (Lorentz factor at 0.9c)
    """
    import math as _math
    ctx: dict[str, Any] = dict(PHYSICAL_CONSTANTS)  # type: ignore[assignment]
    ctx.update(variables)  # type: ignore[arg-type]
    ctx.update({  # type: ignore[arg-type]
        "sqrt": _math.sqrt, "exp": _math.exp, "log": _math.log,
        "log10": _math.log10, "log2": _math.log2,
        "abs": abs, "max": max, "min": min, "round": round,
        "floor": _math.floor, "ceil": _math.ceil,
        "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,
        "asin": _math.asin, "acos": _math.acos, "atan": _math.atan,
        "atan2": _math.atan2, "sinh": _math.sinh, "cosh": _math.cosh,
        "tanh": _math.tanh, "pow": pow, "inf": float("inf"),
    })
    if extra_builtins:
        ctx.update(extra_builtins)
    try:
        return float(eval(expr, {"__builtins__": {}}, ctx))  # noqa: S307
    except Exception:
        vals = list(variables.values())
        return float(vals[0]) if vals else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ── Unit conversion engine ────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# Map unit type category → conversion table → SI base
_CONVERSION_TABLES: dict[str, dict[str, float]] = {
    "mass":      MASS_TO_KG,
    "length":    LENGTH_TO_M,
    "area":      AREA_TO_M2,
    "volume":    VOLUME_TO_L,
    "pressure":  PRESSURE_TO_PA,
    "force":     FORCE_TO_N,
    "data_size": DATA_SIZE_TO_BYTES,
    "data_rate": DATA_RATE_TO_BPS,
    "frequency": FREQUENCY_TO_HZ,
    "speed":     SPEED_TO_MS,
    "duration":  DURATION_TO_SECONDS,
    "energy":    ENERGY_TO_KWH,
}

# Units that belong to each category (for compatibility checks)
_UNIT_CATEGORY_MAP: dict[str, str] = {}
for _cat, _tbl in _CONVERSION_TABLES.items():
    for _unit in _tbl:
        _UNIT_CATEGORY_MAP[_unit.lower()] = _cat


def unit_convert(value: float, from_unit: str, to_unit: str) -> float:
    """
    Convert a value from one unit to another within the same physical dimension.

    Supports all dimensions with conversion tables:
      mass:       kg, g, mg, lb, oz, stone, tonne, ...
      length:     m, cm, mm, km, ft, in, mi, nm, Å, ...
      area:       m², km², ft², ha, acre, ...
      volume:     L, mL, m³, gal, bbl, ...
      pressure:   Pa, kPa, bar, psi, atm, mmHg, ...
      force:      N, kN, lbf, kgf, ...
      data_size:  bytes, KB, MB, GB, TB, KiB, MiB, ...
      data_rate:  bps, Kbps, Mbps, Gbps, ...
      frequency:  Hz, kHz, MHz, GHz, THz
      speed:      m/s, km/h, mph, kts, Mach, ...
      duration:   s, min, h, day, week, month, year
      energy:     kWh, MWh, J, MJ, MMBTU, ...

    Also supports temperature:
      °C ↔ °F ↔ K ↔ °R

    Returns the converted value. Raises ValueError if units are incompatible.

    Examples:
      unit_convert(70, 'kg', 'lb')       # → 154.32
      unit_convert(100, 'km/h', 'm/s')   # → 27.78
      unit_convert(36.6, '°C', 'K')      # → 309.75
      unit_convert(100, 'MB', 'MiB')     # → 95.37
      unit_convert(1, 'atm', 'psi')      # → 14.696
    """
    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    if fu == tu:
        return value

    # ── Temperature special case (non-linear) ─────────────────────────────────
    _temp_aliases = {"°c": "c", "celsius": "c", "c_temp": "c",
                     "°f": "f", "fahrenheit": "f", "f_temp": "f",
                     "k": "k", "kelvin": "k", "°k": "k",
                     "°r": "r", "rankine": "r"}
    if fu in _temp_aliases and tu in _temp_aliases:
        # To Kelvin first
        fn = _temp_aliases[fu]
        tn = _temp_aliases[tu]
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

    # ── Linear conversion via SI base ──────────────────────────────────────────
    # Find category for from_unit
    from_cat = _UNIT_CATEGORY_MAP.get(fu)
    to_cat   = _UNIT_CATEGORY_MAP.get(tu)

    if from_cat is None or to_cat is None:
        # Try original case
        from_cat = _UNIT_CATEGORY_MAP.get(from_unit)
        to_cat   = _UNIT_CATEGORY_MAP.get(to_unit)

    if from_cat is None or to_cat is None:
        raise ValueError(
            f"Cannot convert '{from_unit}' → '{to_unit}': "
            f"unit not recognized. "
            f"Supported: {sorted(set(_UNIT_CATEGORY_MAP.values()))}"
        )
    if from_cat != to_cat:
        raise ValueError(
            f"Cannot convert '{from_unit}' ({from_cat}) → '{to_unit}' ({to_cat}): "
            "incompatible physical dimensions."
        )

    tbl   = _CONVERSION_TABLES[from_cat]
    to_si = tbl.get(fu, tbl.get(from_unit, 1.0))
    fr_si = tbl.get(tu, tbl.get(to_unit, 1.0))
    return value * to_si / fr_si


def validate_unit_compatibility(
    from_unit: str,
    to_unit: str,
) -> tuple[bool, str]:
    """
    Check if two units are compatible (same physical dimension).
    Returns (is_compatible, message).

    Examples:
      validate_unit_compatibility('kg', 'lb')    # (True, 'mass: kg → lb')
      validate_unit_compatibility('kg', 'm')     # (False, 'incompatible: mass vs length')
      validate_unit_compatibility('°C', 'K')     # (True, 'temperature: °C → K')
    """
    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    _temp_aliases = {"°c", "celsius", "c_temp", "°f", "fahrenheit", "f_temp",
                     "k", "kelvin", "°k", "°r", "rankine"}
    if fu in _temp_aliases and tu in _temp_aliases:
        return True, f"temperature: {from_unit} → {to_unit}"

    from_cat = _UNIT_CATEGORY_MAP.get(fu, _UNIT_CATEGORY_MAP.get(from_unit))
    to_cat   = _UNIT_CATEGORY_MAP.get(tu, _UNIT_CATEGORY_MAP.get(to_unit))

    if from_cat is None:
        return False, f"'{from_unit}' is not a recognized unit"
    if to_cat is None:
        return False, f"'{to_unit}' is not a recognized unit"
    if from_cat != to_cat:
        return False, f"incompatible: {from_unit} is {from_cat}, {to_unit} is {to_cat}"
    return True, f"{from_cat}: {from_unit} → {to_unit}"
