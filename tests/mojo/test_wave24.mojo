"""Tests for Wave 24 — Decision Analysis, Risk Metrics, Series Forecasting."""

from decision_analysis import (
    expected_value,
    expected_utility,
    decision_matrix_best,
    minimax_regret,
    hurwicz_criterion,
    value_of_perfect_info,
    sensitivity_range,
    maximin,
    maximax,
    laplace_criterion,
)
from risk import (
    value_at_risk,
    conditional_var,
    max_drawdown,
    drawdown_series,
    sortino_ratio,
    sharpe_ratio,
    beta,
    alpha,
    information_ratio,
    calmar_ratio,
    downside_deviation,
)
from series import (
    sma_forecast,
    linear_extrapolation,
    weighted_moving_avg,
    exponential_forecast,
    naive_forecast,
    seasonal_naive,
    drift_forecast,
    forecast_accuracy,
    trend_strength,
    detect_seasonality,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helpers to build lists ───────────────────────────────────────────────────


def _f2(a: Float64, b: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    return r^


def _f3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    return r^


def _f5(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    r.append(e)
    return r^


def _f10(
    a: Float64, b: Float64, c: Float64, d: Float64, e: Float64,
    f: Float64, g: Float64, h: Float64, i: Float64, j: Float64,
) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    r.append(e)
    r.append(f)
    r.append(g)
    r.append(h)
    r.append(i)
    r.append(j)
    return r^


def _f6(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64, f: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    r.append(e)
    r.append(f)
    return r^


def _f12(
    a: Float64, b: Float64, c: Float64, d: Float64,
    e: Float64, f: Float64, g: Float64, h: Float64,
    i: Float64, j: Float64, k: Float64, l: Float64,
) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    r.append(b)
    r.append(c)
    r.append(d)
    r.append(e)
    r.append(f)
    r.append(g)
    r.append(h)
    r.append(i)
    r.append(j)
    r.append(k)
    r.append(l)
    return r^


def _payoffs_2x2() -> List[List[Float64]]:
    """Alt 0: [100, 20], Alt 1: [50, 80]."""
    var payoffs = List[List[Float64]]()
    payoffs.append(_f2(100.0, 20.0))
    payoffs.append(_f2(50.0, 80.0))
    return payoffs^


# ── Decision Analysis Tests ──────────────────────────────────────────────────


def test_expected_value() raises:
    print("  test_expected_value...")
    var outcomes = _f2(100.0, -50.0)
    var probs = _f2(0.6, 0.4)
    var ev = expected_value(outcomes, probs)
    _assert_close(ev, 40.0, 1e-9, "EV([100,-50],[0.6,0.4]) should be 40")  # 1

    # All probability on one outcome
    var p2 = _f2(1.0, 0.0)
    _assert_close(expected_value(outcomes, p2), 100.0, 1e-9, "EV with p=1 on first")  # 2
    print("    PASS")


def test_expected_utility() raises:
    print("  test_expected_utility...")
    var outcomes = _f2(10.0, 20.0)
    var probs = _f2(0.5, 0.5)
    var eu = expected_utility(outcomes, probs, 0.5)
    _assert(eu > 0.0, "Expected utility should be positive for positive outcomes")  # 3

    # Log utility (gamma=1)
    var eu_log = expected_utility(outcomes, probs, 1.0)
    _assert(eu_log > 0.0, "Log utility should be positive for x>1")  # 4
    print("    PASS")


def test_decision_matrix_best() raises:
    print("  test_decision_matrix_best...")
    var payoffs = _payoffs_2x2()
    var probs = _f2(0.5, 0.5)
    # EV0 = 60, EV1 = 65 → best = 1
    var best = decision_matrix_best(payoffs, probs)
    _assert(best == 1, "Best alternative should be 1 (EV=65)")  # 5

    # Shift probs: p=[0.9, 0.1] → EV0=92, EV1=53 → best=0
    var probs2 = _f2(0.9, 0.1)
    var payoffs2 = _payoffs_2x2()
    _assert(decision_matrix_best(payoffs2, probs2) == 0, "Best should be 0 with p=[0.9,0.1]")  # 6
    print("    PASS")


def test_minimax_regret() raises:
    print("  test_minimax_regret...")
    # Best per state: [100, 80]
    # Regret: Alt0=[0, 60], Alt1=[50, 0]
    # Max regret: Alt0=60, Alt1=50 → minimax = Alt1 (idx=1)
    var payoffs = _payoffs_2x2()
    _assert(minimax_regret(payoffs) == 1, "Minimax regret should be alt 1")  # 7
    print("    PASS")


def test_maximin() raises:
    print("  test_maximin...")
    # Alt 0: min=20, Alt 1: min=50 → maximin = Alt 1
    var payoffs = _payoffs_2x2()
    _assert(maximin(payoffs) == 1, "Maximin should select alt 1 (min=50)")  # 8

    # Alt with highest minimum is most conservative
    var payoffs2 = List[List[Float64]]()
    payoffs2.append(_f2(200.0, 10.0))
    payoffs2.append(_f2(60.0, 55.0))
    _assert(maximin(payoffs2) == 1, "Maximin selects most conservative")  # 9
    print("    PASS")


def test_maximax() raises:
    print("  test_maximax...")
    # Alt 0: max=100, Alt 1: max=80 → maximax = Alt 0
    var payoffs = _payoffs_2x2()
    _assert(maximax(payoffs) == 0, "Maximax should select alt 0 (max=100)")  # 10

    # Alt with highest maximum is most optimistic
    var payoffs2 = List[List[Float64]]()
    payoffs2.append(_f2(10.0, 5.0))
    payoffs2.append(_f2(3.0, 200.0))
    _assert(maximax(payoffs2) == 1, "Maximax selects most optimistic")  # 11
    print("    PASS")


def test_laplace() raises:
    print("  test_laplace_criterion...")
    # Alt 0: avg=60, Alt 1: avg=65 → laplace = Alt 1
    var payoffs = _payoffs_2x2()
    _assert(laplace_criterion(payoffs) == 1, "Laplace should be alt 1 (avg=65)")  # 12
    print("    PASS")


def test_hurwicz() raises:
    print("  test_hurwicz_criterion...")
    var payoffs = _payoffs_2x2()

    # α=1 → pure maximax
    var h1 = hurwicz_criterion(payoffs, 1.0)
    var payoffs2 = _payoffs_2x2()
    var mx = maximax(payoffs2)
    _assert(h1 == mx, "Hurwicz α=1 should equal maximax")  # 13

    # α=0 → pure maximin
    var payoffs3 = _payoffs_2x2()
    var h0 = hurwicz_criterion(payoffs3, 0.0)
    var payoffs4 = _payoffs_2x2()
    var mn = maximin(payoffs4)
    _assert(h0 == mn, "Hurwicz α=0 should equal maximin")  # 14
    print("    PASS")


def test_evpi() raises:
    print("  test_value_of_perfect_info...")
    var payoffs = _payoffs_2x2()
    var probs = _f2(0.5, 0.5)
    var evpi = value_of_perfect_info(payoffs, probs)
    _assert(evpi >= 0.0, "EVPI must be >= 0")  # 15

    # EVPI = EV_PI - EV_best
    # EV_PI = 0.5*100 + 0.5*80 = 90, EV_best = max(60,65) = 65
    # EVPI = 25
    _assert_close(evpi, 25.0, 1e-9, "EVPI should be 25")  # 16
    print("    PASS")


def test_sensitivity_range() raises:
    print("  test_sensitivity_range...")
    var payoffs = _payoffs_2x2()
    var sr = sensitivity_range(payoffs, 0, 50)
    _assert(len(sr) == 50, "Sensitivity range length should be n_steps")  # 17

    # At p=0 for state 0, only state 1 matters: best=alt1(80>20)
    _assert_close(sr[0][1], 1.0, 1e-9, "At p=0, best should be alt 1")  # 18

    # At p=1 for state 0, only state 0 matters: best=alt0(100>50)
    _assert_close(sr[49][1], 0.0, 1e-9, "At p=1, best should be alt 0")  # 19
    print("    PASS")


# ── Risk Tests ───────────────────────────────────────────────────────────────


def test_sharpe_ratio() raises:
    print("  test_sharpe_ratio...")
    var returns = _f5(0.05, 0.03, 0.04, 0.06, 0.02)
    var sr = sharpe_ratio(returns, 0.0)
    _assert(sr > 0.0, "Sharpe should be positive for positive returns")  # 20

    # Known computation: mean=0.04, std≈0.01414
    _assert_close(sr, 0.04 / 0.014142135623730951, 0.01, "Sharpe value check")  # 21
    print("    PASS")


def test_var() raises:
    print("  test_value_at_risk...")
    var returns = _f10(-0.10, -0.05, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10)
    var var95 = value_at_risk(returns, 0.95)
    _assert(var95 > 0.0, "VaR should be positive (it's a loss measure)")  # 22

    # VaR at 0.95 → 5th percentile of returns (sorted)
    # Sorted: [-0.10, -0.05, 0.02, ...], idx = 0.05*9 = 0.45
    # val = -0.10 * 0.55 + (-0.05) * 0.45 = -0.0775
    # VaR = 0.0775
    _assert_close(var95, 0.0775, 0.001, "VaR(0.95) on known data")  # 23
    print("    PASS")


def test_cvar() raises:
    print("  test_conditional_var...")
    var returns = _f10(-0.10, -0.05, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10)
    var var95 = value_at_risk(returns, 0.95)
    var cvar95 = conditional_var(returns, 0.95)
    # CVaR should be >= VaR (worse loss)
    _assert(cvar95 >= var95 - 1e-9, "CVaR should be >= VaR")  # 24
    print("    PASS")


def test_max_drawdown() raises:
    print("  test_max_drawdown...")
    var values = _f5(100.0, 90.0, 95.0, 80.0, 100.0)
    var mdd = max_drawdown(values)
    # Peak 100, trough 80 → dd = 0.2
    _assert_close(mdd, 0.2, 1e-9, "Max drawdown should be 0.2")  # 25
    print("    PASS")


def test_drawdown_series() raises:
    print("  test_drawdown_series...")
    var values = _f5(100.0, 90.0, 95.0, 80.0, 100.0)
    var dd = drawdown_series(values)
    _assert(len(dd) == 5, "Drawdown series length must match input")  # 26
    _assert_close(dd[0], 0.0, 1e-9, "First drawdown should be 0")  # 27
    _assert_close(dd[1], 0.1, 1e-9, "DD at index 1 = (100-90)/100 = 0.1")  # 28
    print("    PASS")


def test_sortino() raises:
    print("  test_sortino_ratio...")
    var returns = _f5(0.05, -0.02, 0.03, -0.01, 0.04)
    var sr = sortino_ratio(returns, 0.0)
    _assert(sr > -1e300 and sr < 1e300, "Sortino should be finite")  # 29
    print("    PASS")


def test_beta_self() raises:
    print("  test_beta_self...")
    var returns = _f5(0.01, 0.02, -0.01, 0.03, 0.0)
    var b = beta(returns, returns)
    _assert_close(b, 1.0, 1e-9, "Beta of asset with itself should be 1.0")  # 30
    print("    PASS")


def test_alpha_computation() raises:
    print("  test_alpha...")
    # If asset = market, alpha should be 0
    var returns = _f5(0.01, 0.02, -0.01, 0.03, 0.0)
    var a = alpha(returns, returns, 0.0)
    _assert_close(a, 0.0, 1e-9, "Alpha of asset=market should be 0")  # 31

    # Asset consistently outperforms → positive alpha
    var asset = _f5(0.05, 0.06, 0.03, 0.07, 0.04)
    var market = _f5(0.01, 0.02, -0.01, 0.03, 0.0)
    var a2 = alpha(asset, market, 0.0)
    _assert(a2 > 0.0, "Outperforming asset should have positive alpha")  # 32
    print("    PASS")


def test_downside_deviation() raises:
    print("  test_downside_deviation...")
    var returns = _f5(0.05, -0.02, 0.03, -0.01, 0.04)
    var dd = downside_deviation(returns, 0.0)
    _assert(dd >= 0.0, "Downside deviation must be >= 0")  # 33

    # All positive returns → downside dev = 0
    var pos_returns = _f5(0.01, 0.02, 0.03, 0.04, 0.05)
    var dd2 = downside_deviation(pos_returns, 0.0)
    _assert_close(dd2, 0.0, 1e-9, "No downside for all-positive returns")  # 34
    print("    PASS")


def test_information_ratio() raises:
    print("  test_information_ratio...")
    var returns = _f5(0.05, 0.03, 0.04, 0.06, 0.02)
    var bench = _f5(0.02, 0.02, 0.02, 0.02, 0.02)
    var ir = information_ratio(returns, bench)
    _assert(ir > 0.0, "IR should be positive when outperforming")  # 35
    print("    PASS")


def test_calmar_ratio() raises:
    print("  test_calmar_ratio...")
    var returns = _f5(0.01, -0.02, 0.01, -0.03, 0.02)
    var values = _f5(100.0, 98.0, 99.0, 96.0, 98.0)
    var cr = calmar_ratio(returns, values)
    _assert(cr > -1e300 and cr < 1e300, "Calmar ratio should be finite")  # 36
    print("    PASS")


# ── Series Tests ─────────────────────────────────────────────────────────────


def test_naive_forecast() raises:
    print("  test_naive_forecast...")
    var data = _f3(1.0, 2.0, 3.0)
    var fc = naive_forecast(data, 3)
    _assert(len(fc) == 3, "Naive forecast length should be 3")  # 37
    _assert_close(fc[0], 3.0, 1e-9, "Naive forecast[0] = 3")  # 38
    _assert_close(fc[1], 3.0, 1e-9, "Naive forecast[1] = 3")  # 39
    _assert_close(fc[2], 3.0, 1e-9, "Naive forecast[2] = 3")  # 40
    print("    PASS")


def test_sma_forecast() raises:
    print("  test_sma_forecast...")
    var data = _f5(1.0, 2.0, 3.0, 4.0, 5.0)
    var fc = sma_forecast(data, 3, 2)
    # SMA of last 3: (3+4+5)/3 = 4.0
    _assert_close(fc[0], 4.0, 1e-9, "SMA forecast should be 4.0")  # 41
    _assert_close(fc[1], 4.0, 1e-9, "SMA forecast[1] should be 4.0")  # 42
    print("    PASS")


def test_linear_extrapolation() raises:
    print("  test_linear_extrapolation...")
    var data = _f5(1.0, 2.0, 3.0, 4.0, 5.0)
    var fc = linear_extrapolation(data, 2)
    # Perfect linear: y = 1 + 1*x, next: x=5→6, x=6→7
    _assert_close(fc[0], 6.0, 0.01, "Linear extrap[0] approx 6")  # 43
    _assert_close(fc[1], 7.0, 0.01, "Linear extrap[1] approx 7")  # 44
    print("    PASS")


def test_exponential_forecast() raises:
    print("  test_exponential_forecast...")
    var data = _f5(1.0, 2.0, 3.0, 4.0, 5.0)
    var fc = exponential_forecast(data, 0.3, 3)
    # All forecasts should be equal (single exp smoothing)
    _assert_close(fc[0], fc[1], 1e-9, "Exp forecast values should be equal")  # 45
    _assert_close(fc[1], fc[2], 1e-9, "Exp forecast all same")  # 46
    print("    PASS")


def test_seasonal_naive() raises:
    print("  test_seasonal_naive...")
    var data = _f6(1.0, 2.0, 3.0, 1.0, 2.0, 3.0)
    var fc = seasonal_naive(data, 3, 4)
    _assert_close(fc[0], 1.0, 1e-9, "Seasonal naive[0]=1")  # 47
    _assert_close(fc[1], 2.0, 1e-9, "Seasonal naive[1]=2")  # 48
    _assert_close(fc[2], 3.0, 1e-9, "Seasonal naive[2]=3")  # 49
    _assert_close(fc[3], 1.0, 1e-9, "Seasonal naive[3]=1 (cycle)")  # 50
    print("    PASS")


def test_drift_forecast() raises:
    print("  test_drift_forecast...")
    var data = _f5(1.0, 2.0, 3.0, 4.0, 5.0)
    var fc = drift_forecast(data, 3)
    # slope = (5-1)/4 = 1.0, so 6, 7, 8
    _assert_close(fc[0], 6.0, 1e-9, "Drift[0] = 6")  # 51
    _assert_close(fc[1], 7.0, 1e-9, "Drift[1] = 7")  # 52
    # All should be increasing
    _assert(fc[2] > fc[1], "Drift should be increasing for upward trend")  # 53
    print("    PASS")


def test_forecast_accuracy() raises:
    print("  test_forecast_accuracy...")
    var actual = _f5(1.0, 2.0, 3.0, 4.0, 5.0)
    var predicted = _f5(1.1, 2.2, 2.8, 4.1, 4.9)
    var acc = forecast_accuracy(actual, predicted)
    # [MAE, MAPE, RMSE]
    _assert(acc[0] >= 0.0, "MAE >= 0")  # 54
    _assert(acc[1] >= 0.0, "MAPE >= 0")  # 55
    _assert(acc[2] >= 0.0, "RMSE >= 0")  # 56
    print("    PASS")


def test_trend_strength() raises:
    print("  test_trend_strength...")
    # Perfect linear data → trend strength ≈ 1.0
    var data = _f10(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0)
    var ts = trend_strength(data)
    _assert_close(ts, 1.0, 0.01, "Trend strength on linear data approx 1.0")  # 57
    print("    PASS")


def test_detect_seasonality() raises:
    print("  test_detect_seasonality...")
    # Period-3 seasonal data
    var data = _f12(1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0)
    var period = detect_seasonality(data, 6)
    _assert(period == 3, "Detected period should be 3")  # 58
    print("    PASS")


def test_weighted_moving_avg() raises:
    print("  test_weighted_moving_avg...")
    var data = _f5(1.0, 2.0, 3.0, 4.0, 5.0)
    var weights = _f3(1.0, 2.0, 3.0)
    var wma = weighted_moving_avg(data, weights)
    # Last 3 values: 3,4,5 with weights 1,2,3
    # (3*1 + 4*2 + 5*3) / (1+2+3) = 26/6
    _assert_close(wma, 26.0 / 6.0, 1e-9, "WMA check")  # 59
    print("    PASS")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 24 Tests ===")

    print("\n-- Decision Analysis --")
    test_expected_value()
    test_expected_utility()
    test_decision_matrix_best()
    test_minimax_regret()
    test_maximin()
    test_maximax()
    test_laplace()
    test_hurwicz()
    test_evpi()
    test_sensitivity_range()

    print("\n-- Risk Metrics --")
    test_sharpe_ratio()
    test_var()
    test_cvar()
    test_max_drawdown()
    test_drawdown_series()
    test_sortino()
    test_beta_self()
    test_alpha_computation()
    test_downside_deviation()
    test_information_ratio()
    test_calmar_ratio()

    print("\n-- Series Forecasting --")
    test_naive_forecast()
    test_sma_forecast()
    test_linear_extrapolation()
    test_exponential_forecast()
    test_seasonal_naive()
    test_drift_forecast()
    test_forecast_accuracy()
    test_trend_strength()
    test_detect_seasonality()
    test_weighted_moving_avg()

    print("\nAll 59 Wave 24 assertions passed!")
