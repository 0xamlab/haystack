"""
supply_chain.mojo — Supply Chain Optimization. Zero Python imports.

Replaces custom Python SCM code with pure Mojo implementations of
lead time demand, bullwhip effect, forecast errors, EPQ, TCO,
service levels, and forecasting methods.

Public API:
  lead_time_demand               — Expected demand during lead time
  bullwhip_effect                — Bullwhip ratio
  forecast_error_mae             — Mean Absolute Error
  forecast_error_mape            — Mean Absolute Percentage Error
  forecast_bias                  — Mean(forecast - actual)
  tracking_signal                — Cumulative error / MAD
  economic_production_qty        — EPQ formula
  total_cost_of_ownership        — Sum of cost components
  service_level_type1            — Cycle service level
  fill_rate_type2                — Type 2 fill rate
  moving_average_forecast        — Simple moving average forecast
  exponential_smoothing_forecast — Single exponential smoothing forecast
"""

from std.math import sqrt, abs as fabs


# ── lead_time_demand ─────────────────────────────────────────────────────────


def lead_time_demand(demand_rate: Float64, lead_time: Float64) -> Float64:
    """Expected demand during lead time = demand_rate * lead_time."""
    return demand_rate * lead_time


# ── bullwhip_effect ──────────────────────────────────────────────────────────


def bullwhip_effect(demand_variance: Float64, order_variance: Float64) -> Float64:
    """Bullwhip ratio: order_variance / demand_variance.
    Ratio > 1 indicates amplification of demand signal."""
    if demand_variance < 1e-30:
        return 0.0
    return order_variance / demand_variance


# ── forecast_error_mae ───────────────────────────────────────────────────────


def forecast_error_mae(actual: List[Float64], forecast: List[Float64]) -> Float64:
    """Mean Absolute Error between actual and forecast."""
    if len(forecast) != len(actual):
        return 0.0
    var n = len(actual)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        total += fabs(actual[i] - forecast[i])
    return total / Float64(n)


# ── forecast_error_mape ──────────────────────────────────────────────────────


def forecast_error_mape(actual: List[Float64], forecast: List[Float64]) -> Float64:
    """Mean Absolute Percentage Error. Skips zero actuals."""
    if len(forecast) != len(actual):
        return 0.0
    var n = len(actual)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    var count = 0
    for i in range(n):
        if fabs(actual[i]) > 1e-30:
            total += fabs((actual[i] - forecast[i]) / actual[i])
            count += 1
    if count == 0:
        return 0.0
    return total / Float64(count) * 100.0


# ── forecast_bias ────────────────────────────────────────────────────────────


def forecast_bias(actual: List[Float64], forecast: List[Float64]) -> Float64:
    """Mean(forecast - actual). Positive = over-forecasting."""
    if len(forecast) != len(actual):
        return 0.0
    var n = len(actual)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        total += forecast[i] - actual[i]
    return total / Float64(n)


# ── tracking_signal ──────────────────────────────────────────────────────────


def tracking_signal(actual: List[Float64], forecast: List[Float64]) -> Float64:
    """Tracking signal = cumulative error / MAD.
    MAD = Mean Absolute Deviation of errors."""
    if len(forecast) != len(actual):
        return 0.0
    var n = len(actual)
    if n == 0:
        return 0.0
    var cum_error: Float64 = 0.0
    var mad: Float64 = 0.0
    for i in range(n):
        var err = forecast[i] - actual[i]
        cum_error += err
        mad += fabs(err)
    mad /= Float64(n)
    if mad < 1e-30:
        return 0.0
    return cum_error / mad


# ── economic_production_qty ──────────────────────────────────────────────────


def economic_production_qty(demand: Float64, setup_cost: Float64, holding_cost: Float64, production_rate: Float64) -> Float64:
    """EPQ = sqrt(2*D*S / (H*(1 - D/P))).
    demand=D, setup_cost=S, holding_cost=H, production_rate=P."""
    if production_rate <= demand:
        return 0.0
    if holding_cost < 1e-30:
        return 0.0
    var ratio = 1.0 - demand / production_rate
    if ratio < 1e-30:
        return 0.0
    return sqrt(2.0 * demand * setup_cost / (holding_cost * ratio))


# ── total_cost_of_ownership ──────────────────────────────────────────────────


def total_cost_of_ownership(purchase: Float64, ordering: Float64, holding: Float64, shortage: Float64) -> Float64:
    """TCO = sum of all cost components."""
    return purchase + ordering + holding + shortage


# ── service_level_type1 ──────────────────────────────────────────────────────


def service_level_type1(stockout_probability: Float64) -> Float64:
    """Cycle service level = 1 - P(stockout)."""
    return 1.0 - stockout_probability


# ── fill_rate_type2 ──────────────────────────────────────────────────────────


def fill_rate_type2(expected_shortage: Float64, demand: Float64) -> Float64:
    """Type 2 fill rate = 1 - E[shortage] / demand."""
    if demand < 1e-30:
        return 0.0
    return 1.0 - expected_shortage / demand


# ── moving_average_forecast ──────────────────────────────────────────────────


def moving_average_forecast(data: List[Float64], periods: Int) -> Float64:
    """Forecast next period = average of last N periods."""
    var n = len(data)
    if n == 0 or periods <= 0:
        return 0.0
    var actual_periods = periods
    if actual_periods > n:
        actual_periods = n
    var total: Float64 = 0.0
    for i in range(n - actual_periods, n):
        total += data[i]
    return total / Float64(actual_periods)


# ── exponential_smoothing_forecast ───────────────────────────────────────────


def exponential_smoothing_forecast(data: List[Float64], alpha: Float64) -> Float64:
    """Next period forecast using Simple Exponential Smoothing (SES).
    F(t+1) = alpha * Y(t) + (1-alpha) * F(t), with F(1) = Y(0)."""
    var n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]
    var forecast = data[0]
    for i in range(1, n):
        forecast = alpha * data[i] + (1.0 - alpha) * forecast
    return forecast
