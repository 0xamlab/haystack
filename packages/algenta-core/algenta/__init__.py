"""
algenta-core — Local simulation, optimization, and decision-making.

Zero dependencies. No API key. Works offline. 100× faster than Python.

Quick start:

  from algenta import decision, optimize, simulate, forecast

  # One line. No docs needed.
  decision("Should I launch this product?", revenue=120000, cost=70000)
  optimize("maximize profit", price=(10, 200), quantity=(100, 5000))
  simulate(revenue=100000, cost=70000, runs=50000)
  forecast.predict([80k, 85k, 90k, 95k, 100k], horizon=6)

  # Cloud: same API, infinite scale
  from algenta import AlgentaClient
  client = AlgentaClient(api_key="de_live_...")
  client.simulate.risk(revenue=100000, cost=70000, runs=1_000_000)

Bundles:
  pip install algenta-core      # this package — local only
  pip install algenta-finance   # financial modeling
  pip install algenta-ml        # ML scoring + feature engineering
  pip install algenta-ai        # LLM inference + agents
  pip install algenta-ops       # DevOps + capacity planning
"""
from __future__ import annotations

from algenta import forecast
from algenta.client import AlgentaClient
from algenta.map import FieldMapping as MappedField
from algenta.map import MapResult, map_data, query_data
from algenta.simple import Result, decision, optimize, simulate

__version__ = "0.1.0"
__all__ = [
    "decision", "optimize", "simulate", "forecast",
    "AlgentaClient", "Result",
    "map_data", "query_data", "MapResult", "MappedField",
]
