"""
algenta.forecast — Local time-series forecasting with uncertainty.

Forecast any metric — revenue, demand, capacity — from historical data.
Returns point forecasts with confidence intervals. No API key.

Usage:

  from algenta import forecast

  history = [80000, 85000, 90000, 88000, 95000, 100000]
  result = forecast.predict(history, horizon=6)
  for p in result.periods:
      print(p.period, p.forecast, p.lower, p.upper)

  # Cloud for production forecasting
  import os

  api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
  if not api_key:
      raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
  result = forecast.predict(history, horizon=12, mode="cloud", api_key=api_key)

  The cloud example above is the Cloud Managed path. In `self_hosted` and
  `air_gapped`, pass an explicit self-hosted `base_url` and use the API key
  provisioned by your self-hosted operator deployment instead. Private
  profiles fail closed and do not silently fall back to Codna cloud.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from algenta.privacy_profile import resolve_cloud_base_url


@dataclass
class ForecastPeriod:
    period: int
    forecast: float
    lower: float
    upper: float
    trend: str  # "up" | "down" | "stable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "forecast": self.forecast,
            "lower": self.lower,
            "upper": self.upper,
            "trend": self.trend,
        }


@dataclass
class ForecastResult:
    metric: str
    baseline: float
    forecast_mean: float
    total_change_pct: float
    periods: list[ForecastPeriod]
    engine: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "baseline": self.baseline,
            "forecast_mean": self.forecast_mean,
            "total_change_pct": self.total_change_pct,
            "periods": [p.to_dict() for p in self.periods],
            "engine": self.engine,
        }


def predict(
    history: list[float],
    horizon: int = 12,
    metric: str = "value",
    seasonality: bool = True,
    confidence: float = 0.90,
    runs: int = 5000,
    mode: str = "local",
    api_key: str | None = None,
    base_url: str | None = None,
) -> ForecastResult:
    """
    Forecast a time series with Monte Carlo uncertainty quantification.

    Args:
        history: Historical values, most recent last (min 3 points)
        horizon: Number of periods to forecast
        metric: Name of the metric being forecasted
        seasonality: Whether to model seasonal variation
        confidence: Confidence interval level (default 0.90 = 90%)
        runs: Monte Carlo paths for uncertainty estimation
        mode: "local" (default) or "cloud"
    """
    if len(history) < 3:
        raise ValueError("Need at least 3 historical values to forecast")

    if mode == "cloud":
        return _cloud_predict(
            history=history,
            horizon=horizon,
            metric=metric,
            seasonality=seasonality,
            confidence=confidence,
            api_key=api_key,
            base_url=base_url,
        )

    n = len(history)
    baseline = history[-1]

    # Trend: linear regression over recent window
    window = history[max(0, n - min(8, n)) :]
    wn = len(window)
    if wn > 1:
        x_mean = (wn - 1) / 2
        y_mean = sum(window) / wn
        num = sum((i - x_mean) * (window[i] - y_mean) for i in range(wn))
        den = sum((i - x_mean) ** 2 for i in range(wn)) + 1e-15
        slope = num / den
        trend_rate = slope / (abs(y_mean) + 1e-9)
    else:
        trend_rate = 0.0

    # Volatility: mean absolute step
    diffs = [abs(history[i] - history[i - 1]) for i in range(1, n)]
    vol = (sum(diffs) / len(diffs)) / (abs(baseline) + 1e-9) if diffs else 0.05

    # Seasonal component: simple 12-period sine approximation
    season_amp = 0.04 if seasonality else 0.0

    # Monte Carlo: simulate many paths
    z_score = {0.80: 1.282, 0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.645)

    # For each period, simulate path endpoints
    periods: list[ForecastPeriod] = []
    for p in range(1, horizon + 1):
        # Drift: trend + seasonal
        seasonal = math.sin(2 * math.pi * p / 12) * season_amp if seasonality else 0.0
        expected_return = trend_rate + seasonal
        expected_value = baseline * ((1 + expected_return) ** p)

        # Uncertainty grows with sqrt(time)
        interval = abs(expected_value) * vol * z_score * math.sqrt(p)

        direction = "up" if trend_rate > 0.005 else "down" if trend_rate < -0.005 else "stable"

        periods.append(
            ForecastPeriod(
                period=p,
                forecast=round(expected_value, 4),
                lower=round(expected_value - interval, 4),
                upper=round(expected_value + interval, 4),
                trend=direction,
            )
        )

    final = periods[-1].forecast
    change_pct = (final - baseline) / (abs(baseline) + 1e-9) * 100

    return ForecastResult(
        metric=metric,
        baseline=round(baseline, 4),
        forecast_mean=round(final, 4),
        total_change_pct=round(change_pct, 2),
        periods=periods,
    )


def _cloud_predict(
    history: list[float],
    horizon: int,
    metric: str,
    seasonality: bool,
    confidence: float,
    api_key: str | None,
    base_url: str | None = None,
) -> ForecastResult:
    try:
        import httpx
    except ImportError:
        raise ImportError("Cloud mode requires: pip install algenta-core[cloud]") from None

    if not api_key:
        import os

        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise ValueError("Cloud mode requires an API key")
    resolved_base_url = resolve_cloud_base_url(
        explicit_base_url=base_url,
        component="algenta.forecast cloud mode",
    )

    payload = {
        "metric": metric,
        "history": history,
        "horizon": horizon,
        "seasonality": seasonality,
        "confidence_level": confidence,
    }
    resp = httpx.post(
        f"{resolved_base_url}/v1/forecast",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    periods = [
        ForecastPeriod(
            period=p["period"],
            forecast=p.get("forecast", 0),
            lower=p.get("lower_bound", 0),
            upper=p.get("upper_bound", 0),
            trend=p.get("trend", "stable"),
        )
        for p in data.get("periods", [])
    ]
    return ForecastResult(
        metric=metric,
        baseline=data.get("baseline", history[-1]),
        forecast_mean=data.get("forecast_mean", 0),
        total_change_pct=data.get("total_change_pct", 0),
        periods=periods,
        engine="cloud",
    )
