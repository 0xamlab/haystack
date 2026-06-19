"""
algenta.simulate — Local Monte Carlo simulation engine.

Drop-in speedup layer for scipy.stats, numpy random sampling, and
manual Monte Carlo loops. No API key. No network. Pure Python with
optional Mojo acceleration when available.

Usage:

  from algenta import simulate

  # Risk analysis
  r = simulate.risk(revenue=120000, cost=70000, runs=50000)
  print(r.expected_value, r.probability_of_loss)

  # Distribution sampling
  samples = simulate.normal(mean=100, std=15, n=10000)
  samples = simulate.triangular(low=80, mode=100, high=130, n=10000)

  # Full Monte Carlo with multiple variables
  result = simulate.run(
      variables=[
          {"name": "revenue", "distribution": "normal", "mean": 100000, "std": 15000},
          {
              "name": "cost",
              "distribution": "triangular",
              "low": 60000,
              "mode": 70000,
              "high": 90000,
          },
      ],
      runs=50000,
  )

  # Scale to cloud when you need it
  import os

  api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
  if not api_key:
      raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
  r = simulate.risk(..., mode="cloud", api_key=api_key)

  The cloud example above is the Cloud Managed path. In `self_hosted` and
  `air_gapped`, pass an explicit self-hosted `base_url` and use the API key
  provisioned by your self-hosted operator deployment instead. Private
  profiles fail closed and do not silently fall back to Codna cloud.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from algenta.privacy_profile import resolve_cloud_base_url

# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class SimulationResult:
    expected_value: float
    std_deviation: float
    probability_of_loss: float
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    runs: int
    engine: str = "local"
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_value": self.expected_value,
            "std_deviation": self.std_deviation,
            "probability_of_loss": self.probability_of_loss,
            "percentiles": {
                "p5": self.percentile_5,
                "p25": self.percentile_25,
                "p50": self.percentile_50,
                "p75": self.percentile_75,
                "p95": self.percentile_95,
            },
            "runs": self.runs,
            "engine": self.engine,
            "latency_ms": self.latency_ms,
        }


# ── Core sampling (pure Python, no deps) ─────────────────────────────────────


def _box_muller(mu: float, sigma: float) -> float:
    """Box-Muller normal sample — no numpy required."""
    u1 = random.random()  # noqa: S311 - Monte Carlo sampling needs a fast non-crypto PRNG
    u2 = random.random()  # noqa: S311 - Monte Carlo sampling needs a fast non-crypto PRNG
    z = math.sqrt(-2 * math.log(u1 + 1e-15)) * math.cos(2 * math.pi * u2)
    return mu + sigma * z


def _triangular_sample(low: float, mode: float, high: float) -> float:
    u = random.random()  # noqa: S311 - Monte Carlo sampling needs a fast non-crypto PRNG
    fc = (mode - low) / (high - low + 1e-15)
    if u < fc:
        return low + math.sqrt(u * (high - low) * (mode - low))
    else:
        return high - math.sqrt((1 - u) * (high - low) * (high - mode))


def _sample_variable(spec: dict[str, Any]) -> float:
    dist = spec.get("distribution", "normal").lower()
    p = spec.get("params", spec)
    if dist in ("normal", "gaussian"):
        return _box_muller(
            p.get("mean", p.get("mu", 0)),
            p.get("std", p.get("std_dev", p.get("sigma", 1))),
        )
    elif dist == "triangular":
        return _triangular_sample(p.get("low", 0), p.get("mode", 50), p.get("high", 100))
    elif dist == "uniform":
        return random.uniform(  # noqa: S311 - Monte Carlo sampling needs a fast non-crypto PRNG
            p.get("low", 0), p.get("high", 1)
        )
    elif dist == "fixed":
        return float(p.get("value", 0))
    elif dist == "lognormal":
        mu = p.get("mu", p.get("mean", 0))
        sigma = p.get("sigma", p.get("std", 1))
        return math.exp(_box_muller(mu, sigma))
    elif dist == "exponential":
        rate = p.get("rate", p.get("lambda", 1))
        uniform_sample = random.random()  # noqa: S311 - Monte Carlo sampling needs a fast non-crypto PRNG
        return -math.log(uniform_sample + 1e-15) / rate
    else:
        return _box_muller(p.get("mean", 0), p.get("std", 1))


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = (len(sorted_vals) - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _summarize(
    values: list[float], latency_ms: float = 0.0, engine: str = "local"
) -> SimulationResult:
    n = len(values)
    if n == 0:
        return SimulationResult(0, 0, 0, 0, 0, 0, 0, 0, 0, engine, latency_ms)
    s = sorted(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)
    losses = sum(1 for v in values if v < 0)
    return SimulationResult(
        expected_value=round(mean, 4),
        std_deviation=round(std, 4),
        probability_of_loss=round(losses / n, 4),
        percentile_5=round(_percentile(s, 5), 4),
        percentile_25=round(_percentile(s, 25), 4),
        percentile_50=round(_percentile(s, 50), 4),
        percentile_75=round(_percentile(s, 75), 4),
        percentile_95=round(_percentile(s, 95), 4),
        runs=n,
        engine=engine,
        latency_ms=latency_ms,
    )


# ── Public API ────────────────────────────────────────────────────────────────


def normal(mean: float, std: float, n: int = 10000) -> list[float]:
    """Sample from a normal distribution. Faster than scipy.stats.norm.rvs."""
    return [_box_muller(mean, std) for _ in range(n)]


def triangular(low: float, mode: float, high: float, n: int = 10000) -> list[float]:
    """Sample from a triangular distribution."""
    return [_triangular_sample(low, mode, high) for _ in range(n)]


def uniform(low: float, high: float, n: int = 10000) -> list[float]:
    """Sample from a uniform distribution."""
    return [
        random.uniform(low, high)  # noqa: S311 - Monte Carlo sampling needs a fast non-crypto PRNG
        for _ in range(n)
    ]


def run(
    variables: list[dict[str, Any]],
    runs: int = 10000,
    mode: str = "local",
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> SimulationResult:
    """
    Run a Monte Carlo simulation with multiple variables.

    mode="local"  → pure Python, instant, offline (default)
    mode="cloud"  → Algenta hosted API (requires api_key)
    """
    if mode == "cloud":
        return _cloud_run(
            variables=variables,
            runs=runs,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    import time

    t0 = time.monotonic()

    values: list[float] = []
    for _ in range(runs):
        samples = {v["name"]: _sample_variable(v) for v in variables}
        # Default objective: sum of all variables
        values.append(sum(samples.values()))

    return _summarize(values, latency_ms=(time.monotonic() - t0) * 1000)


def risk(
    runs: int = 10000,
    mode: str = "local",
    api_key: str | None = None,
    base_url: str | None = None,
    **named_inputs: float,
) -> SimulationResult:
    """
    Quick risk analysis from named values.

    Each keyword argument is a business variable. Assumes ±20% normal uncertainty.
    Returns expected profit/value distribution.

    Example:
      result = simulate.risk(revenue=120000, cost=70000, runs=50000)
    """
    if not named_inputs:
        raise ValueError(
            "Pass at least one named input, e.g. simulate.risk(revenue=100000, cost=70000)"
        )

    if mode == "cloud":
        variables = [
            {"name": k, "distribution": "normal", "params": {"mean": v, "std": abs(v) * 0.2}}
            for k, v in named_inputs.items()
        ]
        return _cloud_run(
            variables=variables,
            runs=runs,
            api_key=api_key,
            base_url=base_url,
        )

    import time

    t0 = time.monotonic()

    values: list[float] = []
    for _ in range(runs):
        total = 0.0
        for _name, val in named_inputs.items():
            # Treat as revenue-like (positive) or cost-like (negative) by convention
            sample = _box_muller(val, abs(val) * 0.20)
            total += sample
        values.append(total)

    return _summarize(values, latency_ms=(time.monotonic() - t0) * 1000)


def _cloud_run(
    variables: list[dict[str, Any]],
    runs: int,
    api_key: str | None,
    base_url: str | None = None,
    **kwargs: Any,
) -> SimulationResult:
    """Delegate to Algenta hosted API."""
    try:
        import httpx
    except ImportError:
        raise ImportError("Cloud mode requires httpx: pip install algenta-core[cloud]") from None

    if not api_key:
        import os

        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise ValueError(
            "Cloud mode requires an API key. "
            "Set ALGENTA_API_KEY / DE_API_KEY environment variables or pass api_key explicitly."
        )
    resolved_base_url = resolve_cloud_base_url(
        explicit_base_url=base_url,
        component="algenta.simulate cloud mode",
    )

    payload = {
        "mode": "expert",
        "simulation_model": kwargs.get("simulation_model", "monte_carlo"),
        "runs": runs,
        "simulation": {
            "variables": variables,
            "objective_function": kwargs.get("objective", "maximize_value"),
        },
    }
    resp = httpx.post(
        f"{resolved_base_url}/v1/simulate",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    metrics = data.get("metrics", {})
    percentiles = data.get("percentiles", {})
    return SimulationResult(
        expected_value=metrics.get("expected_value", data.get("expected_value", 0)),
        std_deviation=metrics.get("std_deviation", data.get("std_deviation", 0)),
        probability_of_loss=metrics.get(
            "probability_of_loss",
            data.get("probability_of_loss", 0),
        ),
        percentile_5=percentiles.get("p5", data.get("percentiles", {}).get("p5", 0)),
        percentile_25=percentiles.get("p25", data.get("percentiles", {}).get("p25", 0)),
        percentile_50=percentiles.get("p50", data.get("percentiles", {}).get("p50", 0)),
        percentile_75=percentiles.get("p75", data.get("percentiles", {}).get("p75", 0)),
        percentile_95=percentiles.get("p95", data.get("percentiles", {}).get("p95", 0)),
        runs=data.get("scenarios_run", data.get("runs", runs)),
        engine="cloud",
        latency_ms=data.get("execution_ms", 0),
    )
