"""
Universal Unit Context Service — modular package.

Public API (fully backward-compatible with the old unit_service.py):

  UnitSpec                   — parsed unit specification
  format_value               — format a float with units
  preprocess_variable        — normalize variable params before simulation
  validate_variable          — advisory range/sanity warnings
  preprocess_payload         — preprocess entire Mojo payload
  postprocess_results        — format simulation output stats
  build_unit_context         — build unit_context block for DecisionEnvelope
  suggest_unit_specs         — auto-suggest units given domain + variable names
  get_physical_constants     — return all physics constants dict
  eval_with_constants        — evaluate expression with physics constants
  unit_convert               — cross-unit conversion (kg→lb, °C→K, etc.)
  validate_unit_compatibility — check if two units are compatible dimensions

Registries (direct access for power users):
  UNIT_TYPES, PHYSICAL_CONSTANTS
  CURRENCY_PRECISION, CURRENCY_SYMBOLS
  CRYPTO_DISPLAY_DECIMALS, CRYPTO_SUB_UNITS
  MASS_TO_KG, LENGTH_TO_M, AREA_TO_M2, VOLUME_TO_L
  PRESSURE_TO_PA, FORCE_TO_N
  DATA_SIZE_TO_BYTES, DATA_RATE_TO_BPS, FREQUENCY_TO_HZ
  SPEED_TO_MS, DURATION_TO_SECONDS, ENERGY_TO_KWH
  DOMAIN_VARIABLE_HINTS
"""

from __future__ import annotations

# ── Conversion ────────────────────────────────────────────────────────────────
from .converter import unit_convert, validate_unit_compatibility

# ── Formatting ────────────────────────────────────────────────────────────────
from .formatter import _compact, _epoch_days_to_iso, _format_duration, format_value

# ── Pipeline ──────────────────────────────────────────────────────────────────
from .pipeline import (
    build_unit_context,
    eval_with_constants,
    get_physical_constants,
    postprocess_results,
    preprocess_payload,
    suggest_unit_specs,
)

# ── Registries ────────────────────────────────────────────────────────────────
from .registries import (
    AREA_TO_M2,
    CONCENTRATION_LABELS,
    CRYPTO_DISPLAY_DECIMALS,
    CRYPTO_SUB_UNITS,
    CURRENCY_PRECISION,
    CURRENCY_SYMBOLS,
    DATA_RATE_TO_BPS,
    DATA_SIZE_TO_BYTES,
    DOMAIN_VARIABLE_HINTS,
    DURATION_TO_SECONDS,
    ENERGY_TO_KWH,
    FORCE_TO_N,
    FREQUENCY_TO_HZ,
    LENGTH_TO_M,
    MASS_TO_KG,
    PHYSICAL_CONSTANTS,
    PRESSURE_TO_PA,
    RANGE_BOUNDS,
    SPEED_DISPLAY_UNITS,
    SPEED_TO_MS,
    SPORTS_UNITS,
    UNIT_TYPES,
    VOLUME_TO_L,
)

# ── Core types ────────────────────────────────────────────────────────────────
from .spec import UnitSpec

# ── Validation / preprocessing ────────────────────────────────────────────────
from .validate import (
    _date_to_epoch_days,
    preprocess_variable,
    validate_variable,
)

__all__ = [
    # Core
    "UnitSpec",
    # Formatting
    "format_value",
    "_compact",
    "_epoch_days_to_iso",
    "_format_duration",
    # Validation / pre/post-processing
    "_date_to_epoch_days",
    "preprocess_variable",
    "validate_variable",
    "preprocess_payload",
    "postprocess_results",
    "build_unit_context",
    # Domain suggestions
    "suggest_unit_specs",
    # Physics
    "get_physical_constants",
    "eval_with_constants",
    # Conversion
    "unit_convert",
    "validate_unit_compatibility",
    # Registries
    "UNIT_TYPES",
    "PHYSICAL_CONSTANTS",
    "CURRENCY_PRECISION",
    "CURRENCY_SYMBOLS",
    "CRYPTO_DISPLAY_DECIMALS",
    "CRYPTO_SUB_UNITS",
    "DURATION_TO_SECONDS",
    "ENERGY_TO_KWH",
    "CONCENTRATION_LABELS",
    "RANGE_BOUNDS",
    "MASS_TO_KG",
    "LENGTH_TO_M",
    "AREA_TO_M2",
    "VOLUME_TO_L",
    "PRESSURE_TO_PA",
    "FORCE_TO_N",
    "DATA_SIZE_TO_BYTES",
    "DATA_RATE_TO_BPS",
    "FREQUENCY_TO_HZ",
    "SPEED_TO_MS",
    "SPEED_DISPLAY_UNITS",
    "SPORTS_UNITS",
    "DOMAIN_VARIABLE_HINTS",
]
