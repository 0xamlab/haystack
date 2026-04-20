"""
Unit registries — all lookup tables, conversion factors, and domain hints.
No logic here; only data constants.
"""
from __future__ import annotations

# ── Unit type catalogue ────────────────────────────────────────────────────────
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
    "mass", "length", "area", "volume", "density",
    "pressure", "force", "torque",
    "data_size", "data_rate", "frequency", "rate",
    "si", "scientific", "count", "probability", "ratio", "raw", "custom",
])

# ── Physical constants ────────────────────────────────────────────────────────
PHYSICAL_CONSTANTS: dict[str, float] = {
    "c":        299_792_458.0,
    "c_light":  299_792_458.0,
    "G":        6.674e-11,
    "g":        9.80665,
    "g_earth":  9.80665,
    "hbar":     1.054571817e-34,
    "h_planck": 6.62607015e-34,
    "kB":       1.380649e-23,
    "k_B":      1.380649e-23,
    "NA":       6.02214076e23,
    "N_A":      6.02214076e23,
    "R":        8.314462618,
    "R_gas":    8.314462618,
    "sigma_SB": 5.670374419e-8,
    "e_charge": 1.602176634e-19,
    "eps0":     8.8541878128e-12,
    "mu0":      1.25663706212e-6,
    "au":       1.495978707e11,
    "ly":       9.4607304725808e15,
    "pc":       3.085677581491367e16,
    "pi":       3.141592653589793,
    "e":        2.718281828459045,
    "phi":      1.618033988749895,
    "c_sound":  343.0,
}

# ── Speed → m/s ───────────────────────────────────────────────────────────────
SPEED_TO_MS: dict[str, float] = {
    "m/s": 1.0, "ms": 1.0,
    "km/h": 1.0/3.6, "kph": 1.0/3.6,
    "mph": 0.44704, "mi/h": 0.44704,
    "kts": 0.514444, "knots": 0.514444,
    "ft/s": 0.3048, "fps": 0.3048,
    "c": 299_792_458.0,
    "mach": 340.29,
}
SPEED_DISPLAY_UNITS = {"m/s", "km/h", "kph", "mph", "kts", "ft/s"}

# ── Angular → radians ─────────────────────────────────────────────────────────
ANGULAR_TO_RAD: dict[str, float] = {
    "rad": 1.0,
    "deg": 3.141592653589793 / 180.0,
    "°":   3.141592653589793 / 180.0,
    "mrad": 1e-3,
    "arcmin": 3.141592653589793 / (180.0 * 60),
    "arcsec": 3.141592653589793 / (180.0 * 3600),
    "rev": 2 * 3.141592653589793,
    "grad": 3.141592653589793 / 200.0,
}

# ── Temperature (display → Kelvin: multiply + add) ───────────────────────────
TEMPERATURE_OFFSETS: dict[str, tuple[float, float]] = {
    "°c": (1.0, 273.15), "c": (1.0, 273.15),
    "°f": (5.0/9.0, 255.372), "f": (5.0/9.0, 255.372),
    "k": (1.0, 0.0), "°k": (1.0, 0.0),
    "°r": (5.0/9.0, 0.0),
}

# ── Sports / racing ───────────────────────────────────────────────────────────
SPORTS_UNITS: dict[str, tuple[str, int, str]] = {
    "score": ("pts", 1, "score"), "points": ("pts", 1, "score"),
    "lap_s": ("s", 3, "lap_time"), "lap_ms": ("ms", 0, "lap_time"),
    "sector_s": ("s", 3, "sector"),
    "elo": ("ELO", 0, "elo"), "rating": ("", 1, "score"),
    "margin": ("", 2, "score"), "pos": ("", 0, "position"),
    "rank": ("", 0, "position"), "goal": ("", 0, "count"),
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
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "Fr",
    "CAD": "C$", "AUD": "A$", "HKD": "HK$", "SGD": "S$", "BRL": "R$",
    "INR": "₹", "CNY": "¥", "KRW": "₩", "TRY": "₺", "ILS": "₪",
    "MXN": "MX$", "ZAR": "R", "PHP": "₱", "UAH": "₴", "NGN": "₦",
}

# ── Crypto ────────────────────────────────────────────────────────────────────
CRYPTO_DISPLAY_DECIMALS: dict[str, int] = {
    "BTC": 8, "ETH": 6, "LTC": 8, "XRP": 6, "SOL": 6,
    "MATIC": 4, "USDT": 2, "USDC": 2, "BUSD": 2, "DAI": 2,
    "BNB": 4, "ADA": 4, "DOT": 4, "AVAX": 4, "LINK": 4,
    "UNI": 4, "ATOM": 4, "NEAR": 4, "FTM": 4, "ALGO": 4,
    "XLM": 4, "VET": 4, "ICP": 4, "THETA": 4, "FIL": 4,
    "AAVE": 4, "COMP": 4, "MKR": 4, "SNX": 4, "YFI": 4,
}
CRYPTO_SUB_UNITS: dict[str, tuple[str, float, str]] = {
    "BTC_sat": ("sat", 1e8, "BTC"), "BTC_satoshi": ("sat", 1e8, "BTC"),
    "ETH_gwei": ("Gwei", 1e9, "ETH"), "ETH_mwei": ("mwei", 1e6, "ETH"),
    "ETH_kwei": ("kwei", 1e3, "ETH"), "ETH_wei": ("wei", 1e18, "ETH"),
    "SOL_lamport": ("lamp", 1e9, "SOL"), "XRP_drop": ("drop", 1e6, "XRP"),
    "ADA_lovelace": ("lov", 1e6, "ADA"), "DOT_plank": ("plank", 1e10, "DOT"),
    "AVAX_nano": ("nAVAX", 1e9, "AVAX"), "MATIC_gwei": ("Gwei", 1e9, "MATIC"),
    "USDT_micro": ("μUSDT", 1e6, "USDT"), "USDC_micro": ("μUSDC", 1e6, "USDC"),
}

# ── Duration → seconds ────────────────────────────────────────────────────────
# Note: "m" excluded — conflicts with meters. Use "min" for minutes.
DURATION_TO_SECONDS: dict[str, float] = {
    "ns": 1e-9, "us": 1e-6, "μs": 1e-6, "ms": 1e-3,
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "d": 86400.0, "day": 86400.0, "days": 86400.0,
    "w": 604800.0, "wk": 604800.0, "week": 604800.0, "weeks": 604800.0,
    "mo": 2592000.0, "month": 2592000.0, "months": 2592000.0,
    "q": 7776000.0, "quarter": 7776000.0, "quarters": 7776000.0,
    "y": 31536000.0, "yr": 31536000.0, "year": 31536000.0, "years": 31536000.0,
}

# ── Energy → kWh ──────────────────────────────────────────────────────────────
ENERGY_TO_KWH: dict[str, float] = {
    "wh": 1e-3, "kwh": 1.0, "mwh": 1e3, "gwh": 1e6, "twh": 1e9,
    "j": 2.778e-7, "kj": 2.778e-4, "mj": 0.2778, "gj": 277.8,
    "btu": 2.931e-4, "mmbtu": 293.1, "therm": 29.31,
    "toe": 11_630.0, "tce": 8_140.0,
}

# ── Concentration label canonicalization ─────────────────────────────────────
CONCENTRATION_LABELS: dict[str, str] = {
    "ng/ml": "ng/mL", "ug/ml": "μg/mL", "mg/dl": "mg/dL", "mg/l": "mg/L",
    "mmol/l": "mmol/L", "umol/l": "μmol/L", "nmol/l": "nmol/L",
    "pmol/l": "pmol/L", "iu/l": "IU/L", "meq/l": "mEq/L",
    "g/dl": "g/dL", "g/l": "g/L", "mol/l": "mol/L", "μmol/l": "μmol/L",
    "nm": "nM", "um": "μM", "mm": "mM",
}

# ── Range bounds for validation ───────────────────────────────────────────────
RANGE_BOUNDS: dict[str, tuple[float, float, bool, bool]] = {
    "probability": (0.0, 1.0, True, True),
    "ph": (0.0, 14.0, True, True),
    "oee": (0.0, 1.0, False, True),
    "bps": (-1e6, 1e6, False, False),
    "percentage": (-100.0, 100.0, False, False),
    "six_sigma": (0.0, 10.0, False, False),
    "p_value": (0.0, 1.0, True, True),
    "loss_ratio": (0.0, 2.0, False, True),
    "half_life": (0.0, 1e6, True, False),
}

# ── Physical dimension conversion tables ─────────────────────────────────────

MASS_TO_KG: dict[str, float] = {
    "kg": 1.0, "g": 1e-3, "mg": 1e-6, "μg": 1e-9, "ug": 1e-9,
    "ng": 1e-12, "tonne": 1e3, "t": 1e3, "mt": 1e3,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237,
    "oz": 0.028349523, "ounce": 0.028349523,
    "stone": 6.35029318, "st": 6.35029318,
    "slug": 14.593903, "ton": 907.18474,
    "long_ton": 1016.047, "tonne_metric": 1000.0,
    "gr": 6.479891e-5, "grain": 6.479891e-5,
    "carat": 2e-4, "ct": 2e-4,
}

LENGTH_TO_M: dict[str, float] = {
    "m": 1.0, "km": 1e3, "cm": 1e-2, "mm": 1e-3,
    "μm": 1e-6, "um": 1e-6, "nm": 1e-9, "pm": 1e-12,
    "Å": 1e-10, "angstrom": 1e-10,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "yd": 0.9144, "yard": 0.9144,
    "nmi": 1852.0, "nautical_mile": 1852.0,
    "au": 1.495978707e11, "ly": 9.4607304725808e15, "pc": 3.085677581e16,
    "fathom": 1.8288, "chain": 20.1168, "furlong": 201.168, "league": 4828.032,
}

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

VOLUME_TO_L: dict[str, float] = {
    "l": 1.0, "L": 1.0, "litre": 1.0, "liter": 1.0,
    "ml": 1e-3, "mL": 1e-3, "milliliter": 1e-3,
    "cl": 0.01, "cL": 0.01, "dl": 0.1, "dL": 0.1,
    "μl": 1e-6, "ul": 1e-6, "μL": 1e-6,
    "m³": 1000.0, "m3": 1000.0, "cm³": 1e-3, "cm3": 1e-3, "cc": 1e-3,
    "mm³": 1e-6, "mm3": 1e-6,
    "gal": 3.78541, "gallon": 3.78541, "us_gal": 3.78541,
    "uk_gal": 4.54609, "imp_gal": 4.54609,
    "qt": 0.946353, "quart": 0.946353,
    "pt": 0.473176, "pint": 0.473176,
    "cup": 0.236588,
    "fl_oz": 0.0295735, "fl.oz": 0.0295735, "floz": 0.0295735,
    "tbsp": 0.0147868, "tsp": 0.00492892,
    "bbl": 158.987, "barrel": 158.987,
    "ft³": 28.3168, "ft3": 28.3168,
    "in³": 0.0163871, "in3": 0.0163871,
}

PRESSURE_TO_PA: dict[str, float] = {
    "pa": 1.0, "Pa": 1.0,
    "kpa": 1e3, "kPa": 1e3, "mpa": 1e6, "MPa": 1e6, "gpa": 1e9, "GPa": 1e9,
    "bar": 1e5, "mbar": 100.0, "μbar": 0.1,
    "atm": 101325.0, "atmosphere": 101325.0,
    "psi": 6894.76, "psig": 6894.76, "kpsi": 6894760.0,
    "mmhg": 133.322, "mmHg": 133.322, "torr": 133.322,
    "inhg": 3386.39, "inHg": 3386.39,
    "inh2o": 249.089, "inH2O": 249.089,
    "cmh2o": 98.0665, "cmH2O": 98.0665,
}

FORCE_TO_N: dict[str, float] = {
    "n": 1.0, "N": 1.0, "kn": 1e3, "kN": 1e3,
    "mn": 1e6, "MN": 1e6, "gn": 1e9, "GN": 1e9,
    "dyn": 1e-5, "dyne": 1e-5,
    "lbf": 4.44822, "pound_force": 4.44822,
    "kgf": 9.80665, "kp": 9.80665,
    "ozf": 0.278014, "tonf": 8896.44, "ton_force": 8896.44,
}

DATA_SIZE_TO_BYTES: dict[str, float] = {
    "b": 1.0, "byte": 1.0, "bytes": 1.0,
    "kb": 1e3, "kB": 1e3, "kilobyte": 1e3,
    "mb": 1e6, "mB": 1e6, "megabyte": 1e6,
    "gb": 1e9, "gB": 1e9, "gigabyte": 1e9,
    "tb": 1e12, "tB": 1e12, "terabyte": 1e12,
    "pb": 1e15, "pB": 1e15, "petabyte": 1e15,
    "eb": 1e18, "eB": 1e18, "exabyte": 1e18,
    "kib": 1024.0, "KiB": 1024.0, "kibibyte": 1024.0,
    "mib": 1048576.0, "MiB": 1048576.0, "mebibyte": 1048576.0,
    "gib": 1073741824.0, "GiB": 1073741824.0, "gibibyte": 1073741824.0,
    "tib": 1099511627776.0, "TiB": 1099511627776.0, "tebibyte": 1099511627776.0,
    "pib": 1125899906842624.0, "PiB": 1125899906842624.0,
    "bit": 0.125, "bits": 0.125,
    "kbit": 125.0, "mbit": 125000.0, "gbit": 125000000.0,
}

DATA_RATE_TO_BPS: dict[str, float] = {
    "bps": 1.0, "bit/s": 1.0,
    "kbps": 1e3, "Kbps": 1e3, "kilobit/s": 1e3,
    "mbps": 1e6, "Mbps": 1e6, "megabit/s": 1e6,
    "gbps": 1e9, "Gbps": 1e9, "gigabit/s": 1e9,
    "tbps": 1e12, "Tbps": 1e12, "terabit/s": 1e12,
    "kb/s": 1e3, "MB/s": 8e6, "GB/s": 8e9,
}

FREQUENCY_TO_HZ: dict[str, float] = {
    "hz": 1.0, "Hz": 1.0,
    "khz": 1e3, "kHz": 1e3,
    "mhz": 1e6, "MHz": 1e6,
    "ghz": 1e9, "GHz": 1e9,
    "thz": 1e12, "THz": 1e12,
    "rpm_hz": 1.0/60,
    "rad_s": 1.0/(2*3.141592653589793),
}

# ── Domain variable hints ─────────────────────────────────────────────────────
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
        "lorentz_factor": "ratio", "time_dilation": "ratio",
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
        "velocity": "m/s", "velocity_fraction_c": "ratio",
        "lorentz_factor": "ratio", "time_dilation": "ratio",
        "length_contraction": "ratio", "mass_energy": "J", "rapidity": "ratio",
    },
    "geospatial": {
        "latitude": "lat", "longitude": "lon",
        "altitude": "altitude_m", "elevation": "altitude_m",
        "distance": "distance_km", "radius": "distance_km",
        "area": "km²", "speed": "km/h", "bearing": "deg",
        "temperature": "°C", "precipitation": "mm",
    },
}
