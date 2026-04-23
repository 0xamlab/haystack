"""
algenta-core — runtime-first local package for deterministic structured-data execution.

Primary path:

  from algenta import Runtime

  rt = Runtime()
  rt.connect("orders.csv")
  plan = rt.resolve({"metric": "revenue", "group_by": "product_line"})
  result = rt.query(plan)

Supported secondary modes remain available:

  from algenta import decision, optimize, simulate, forecast, map_data, query_data
"""
from __future__ import annotations

from algenta import forecast
from algenta.client import AlgentaClient
from algenta.map import FieldMapping as MappedField
from algenta.map import MapResult, map_data, query_data
from algenta.runtime import (
    AlgentaRuntimeError,
    ImportBundlePreview,
    ImportFailure,
    ImportPreview,
    QueryOutput,
    ResolvedPlan,
    ResolveOutput,
    Runtime,
    RuntimeConfigurationError,
    RuntimeValidationError,
    SourceRegistration,
    VerifyOutput,
)
from algenta.simple import Result, decision, optimize, simulate

__version__ = "0.1.0"
__all__ = [
    "Runtime",
    "ResolvedPlan",
    "ResolveOutput",
    "QueryOutput",
    "VerifyOutput",
    "SourceRegistration",
    "ImportPreview",
    "ImportBundlePreview",
    "ImportFailure",
    "AlgentaRuntimeError",
    "RuntimeConfigurationError",
    "RuntimeValidationError",
    "decision", "optimize", "simulate", "forecast",
    "AlgentaClient", "Result",
    "map_data", "query_data", "MapResult", "MappedField",
]
