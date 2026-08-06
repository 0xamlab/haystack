"""test_forecasting_point.mojo — known-value tests for the ETS / Theta / AR point forecasts.

Hand-written. Every expected number below was derived on paper before the code ran, and the
derivation is in the comment beside the assertion.

Five kinds of assertion do the work:

1. *Exactness on inputs where the answer is known in closed form.* On `y_t = a + b*t` a drift
   forecast is exact, and so are `ets_aan_forecast(alpha=beta=1)` and
   `theta_drift_forecast(alpha=1)`. All three are asserted BIT-EQUAL to each other and to the
   frozen `series.drift_forecast` and `series.linear_extrapolation`, which agree on that input
   because the endpoint slope and the OLS slope coincide there. Agreement between three
   independent computations is evidence; one plausible number is not.

2. *The closed form for the case that is NOT exact.* Classical Theta damps a linear slope by
   `1 - 1/theta`, so on the same series `theta_forecast(theta=2, alpha=1)` must be
   `y_{n-1} + 0.5*b*h` — 21.75, 23.0, 24.25 — and not the true continuation. Asserting
   exactness there would be asserting a bug, so the damped closed form is asserted instead.

3. *Reproduction of a seasonal series.* On `y_t = 2t + s_{t mod 4}` with `s = [1,-1,2,-2]` over
   12 points, `ets_aaa_forecast(alpha=beta=phi=1, period=4)` reproduces the next FOUR true
   values EXACTLY: 25, 25, 30, 28. Every intermediate quantity is dyadic or an exact
   two/three-element average, so the comparison is `==` and not a tolerance. The recovered
   indices are `s + 1` exactly.

4. *A differential demonstration of the defect the interior slice exists to avoid.* The frozen
   `seasonal_component(detrend(y, moving_average_trend(y, 4)), 4)` — which is what
   `decompose_additive` does — is called DIRECTLY here on that same series and asserted to
   produce `[5/3, 1/3, 28/3, 6]`, wildly wrong against a truth of `s + 1`, because the frozen
   trend zero-pads its edges and those raw observations get averaged into the seasonal estimate.
   That is why `_seasonal_indices` slices `[half, n-half)` first.

5. *The frozen failure values, asserted in their raw form next to the wrapper refusing them.*
   `ar_fit_yule_walker(six_points, 10)` really does return ten coefficients with trailing zeros
   — an AR(5) wearing an AR(10) label — and `ar_forecast_checked` refuses it. The frozen
   `decompose_additive` recomposition identity (trend + seasonal + residual == y) is asserted
   too, since `ets_aaa_forecast` is built out of those same three kernels.
"""
from std.math import abs as fabs

from arima import ar_fit_yule_walker
from series import (
    drift_forecast,
    exponential_forecast,
    linear_extrapolation,
    naive_forecast,
    seasonal_naive,
    sma_forecast,
)
from time_series_decompose import (
    decompose_additive,
    detrend,
    moving_average_trend,
    seasonal_component,
)

from forecasting.contract import (
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HORIZON,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_METHOD,
    FC_ERR_PARAM_RANGE,
    FC_ERR_PERIOD,
    FC_METHOD_DRIFT,
    FC_METHOD_ETS_AAA,
    FC_METHOD_MEAN,
    FC_METHOD_NAIVE,
    FC_METHOD_SEASONAL_NAIVE,
    FC_OK,
)
from forecasting.point import (
    PointForecast,
    ar_forecast_checked,
    baseline_forecast,
    deseasonalise_flat,
    ets_aaa_forecast,
    ets_aan_forecast,
    ets_ann_forecast,
    theta_drift_forecast,
    theta_forecast,
)


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _same(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality. Every comparison in this suite is against a value produced by the same
    frozen kernel or by dyadic arithmetic, so a tolerance would hide a real mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _refused(f: PointForecast) -> Bool:
    """A refusal carries no path and no state at all — not a padded one, not a flat one."""
    return (
        f.status != FC_OK
        and not f.has_forecast
        and len(f.values) == 0
        and not f.has_level
        and not f.has_trend
        and not f.has_scale
        and f.n_params == 0
    )


def main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.point] known-value suite")

    # y = 3 + 2.5t over t = 0..7, so y_7 = 20.5 and the slope is exactly 2.5.
    var lin = List[Float64]()
    for t in range(8):
        lin.append(3.0 + 2.5 * Float64(t))

    # ══ three independent computations of the same exact answer ═════════════════════
    # On a pure linear series the endpoint slope (y_T - y_1)/(T-1) and the OLS slope are both
    # exactly 2.5, so drift, linear extrapolation, damped Holt at alpha=beta=phi=1 and
    # theta-drift at alpha=1 must all produce 23.0, 25.5, 28.0, 30.5 — bit for bit.
    var expected_lin = _floats(23.0, 25.5, 28.0, 30.5)
    var frozen_drift = drift_forecast(lin, 4)
    var frozen_line = linear_extrapolation(lin, 4)
    var holt = ets_aan_forecast(lin, 1.0, 1.0, 1.0, 4)
    var theta_d = theta_drift_forecast(lin, 1.0, 4)
    if (
        _same(frozen_drift, expected_lin)
        and _same(frozen_line, expected_lin)
        and holt.status == FC_OK and _same(holt.values, expected_lin)
        and theta_d.status == FC_OK and _same(theta_d.values, expected_lin)
        and holt.level == 20.5 and holt.trend == 2.5
        and theta_d.trend == 2.5
    ):
        passed += 1
        print("  ✅ drift, OLS line, ETS(A,A,N) and theta-drift agree EXACTLY on a linear series")
    else:
        failed += 1
        print("  ❌ linear exactness broken:", holt.values[0], theta_d.values[0], frozen_drift[0])

    # ══ classical Theta DAMPS the slope by 1 - 1/theta. Closed form, not exactness. ══
    # f_h = y_{n-1} + (1 - 1/theta)*b*h = 20.5 + 1.25h at theta = 2: 21.75, 23.0, 24.25.
    var theta2 = theta_forecast(lin, 2.0, 1.0, 3)
    if (
        theta2.status == FC_OK
        and _same(theta2.values, _floats(21.75, 23.0, 24.25))
        and theta2.trend == 2.5
        and theta2.values[2] != expected_lin[2]
    ):
        passed += 1
        print("  ✅ theta=2 halves a linear slope: 21.75 / 23.0 / 24.25, and reports the FULL b")
    else:
        failed += 1
        print("  ❌ theta closed form wrong:", theta2.values[0], theta2.values[1], theta2.values[2])

    # theta = 1 puts zero weight on the trend line, so it degenerates to plain SES. Asserted
    # bit-equal to ETS(A,N,N) at the same alpha rather than "close to".
    var theta1 = theta_forecast(lin, 1.0, 0.3, 4)
    var ses = ets_ann_forecast(lin, 0.3, 4)
    if (
        theta1.status == FC_OK and ses.status == FC_OK
        and _same(theta1.values, ses.values)
        and _same(ses.values, exponential_forecast(lin, 0.3, 4))
    ):
        passed += 1
        print("  ✅ theta=1 IS plain SES, and SES IS the frozen exponential_forecast, bit-equal")
    else:
        failed += 1
        print("  ❌ theta=1 did not degenerate to SES")

    # ══ damping, every value dyadic so equality is exact ════════════════════════════
    # phi = 0.5: multipliers are 0.5, 0.75, 0.875, so 20.5 + 2.5*{...} = 21.75, 22.375, 22.6875.
    var damped = ets_aan_forecast(lin, 1.0, 1.0, 0.5, 3)
    if damped.status == FC_OK and _same(damped.values, _floats(21.75, 22.375, 22.6875)):
        passed += 1
        print("  ✅ damped trend multiplier phi+phi^2+phi^3 gives 21.75 / 22.375 / 22.6875")
    else:
        failed += 1
        print("  ❌ damping wrong:", damped.values[0], damped.values[1], damped.values[2])

    # ══ ETS(A,A,A) reproduces a linear-plus-seasonal series EXACTLY ════════════════
    # y_t = 2t + s[t%4], s = [1,-1,2,-2], t = 0..11.
    # Frozen centered MA (window 4) is 2i-1 on the interior i in [2,10) and 0 at the edges,
    # so the interior detrended values are s[i%4] + 1. Slicing [2,10) and rotating the phase
    # by half = 2 recovers indices [2, 0, 3, -1] = s + 1. adjusted = 2t - 1, Holt at
    # alpha=beta=1 gives level 21 and trend 2, so f_h = 21 + 2h + idx[(11+h)%4]:
    #   h=1: 21+2+2  = 25   true y_12 = 24+1  = 25
    #   h=2: 21+4+0  = 25   true y_13 = 26-1  = 25
    #   h=3: 21+6+3  = 30   true y_14 = 28+2  = 30
    #   h=4: 21+8-1  = 28   true y_15 = 30-2  = 28
    var season = _floats(1.0, -1.0, 2.0, -2.0)
    var seasonal_trend = List[Float64]()
    for t in range(12):
        seasonal_trend.append(2.0 * Float64(t) + season[t % 4])
    var truth = List[Float64]()
    for h in range(1, 5):
        truth.append(2.0 * Float64(11 + h) + season[(11 + h) % 4])
    var aaa = ets_aaa_forecast(seasonal_trend, 1.0, 1.0, 1.0, 4, 4)
    if (
        aaa.status == FC_OK
        and _same(aaa.values, truth)
        and _same(aaa.values, _floats(25.0, 25.0, 30.0, 28.0))
        and aaa.level == 21.0 and aaa.trend == 2.0
        and aaa.n_params == 6
    ):
        passed += 1
        print("  ✅ ETS(A,A,A) reproduces 2t + s[t%4] exactly: 25, 25, 30, 28")
    else:
        failed += 1
        print("  ❌ ETS(A,A,A) wrong:", aaa.values[0], aaa.values[1], aaa.values[2], aaa.values[3])

    var adjust = deseasonalise_flat(seasonal_trend, 4)
    if (
        adjust.status == FC_OK
        and adjust.has_result
        and _same(adjust.indices, _floats(2.0, 0.0, 3.0, -1.0))
        and adjust.n_cycles == 2
        and adjust.index_mean == 1.0
        and adjust.reversible
        and adjust.max_recompose_residual == 0.0
    ):
        passed += 1
        print("  ✅ recovered indices are s+1 = [2, 0, 3, -1]; 2 interior cycles; reversible")
    else:
        failed += 1
        print("  ❌ deseasonalise wrong:", adjust.indices[0], adjust.indices[1],
              adjust.indices[2], adjust.indices[3], adjust.n_cycles)

    # ══ the defect the interior slice exists to avoid, measured on the frozen path ══
    # seasonal_component over the WHOLE detrended series averages the zero-padded edges in:
    #   phase 0: i = 0(edge, y=1), 4(s0+1=2), 8(2)   -> 5/3
    #   phase 1: i = 1(edge, y=1), 5(0),      9(0)   -> 1/3
    #   phase 2: i = 2(3),         6(3),     10(edge, y=22) -> 28/3
    #   phase 3: i = 3(-1),        7(-1),    11(edge, y=20) -> 18/3 = 6
    var raw_trend = moving_average_trend(seasonal_trend, 4)
    var raw_detrended = detrend(seasonal_trend, raw_trend)
    var raw_seasonal = seasonal_component(raw_detrended, 4)
    if (
        raw_seasonal[0] == 5.0 / 3.0
        and raw_seasonal[1] == 1.0 / 3.0
        and raw_seasonal[2] == 28.0 / 3.0
        and raw_seasonal[3] == 6.0
        and raw_trend[0] == 0.0 and raw_trend[11] == 0.0
        and raw_trend[2] == 3.0
    ):
        passed += 1
        print("  ✅ the unsliced frozen path really gives [5/3, 1/3, 28/3, 6] — edge padding")
    else:
        failed += 1
        print("  ❌ frozen edge-padding demonstration failed:", raw_seasonal[0], raw_seasonal[2])

    # The frozen decomposition recomposes to the original — the identity ETS(A,A,A) is built on.
    var parts = decompose_additive(seasonal_trend, 4)
    var recompose_gap: Float64 = 0.0
    for t in range(12):
        var gap = fabs(parts[0][t] + parts[1][t] + parts[2][t] - seasonal_trend[t])
        if gap > recompose_gap:
            recompose_gap = gap
    if len(parts) == 3 and recompose_gap < 1.0e-9:
        passed += 1
        print("  ✅ frozen decompose_additive recomposes to the original within 1e-9")
    else:
        failed += 1
        print("  ❌ recomposition gap:", recompose_gap)

    # ══ a zero-mean seasonal series with no trend is reproduced exactly ═════════════
    # trend is identically 0 (a full-period window of a zero-sum pattern), so the recovered
    # indices ARE s and the deseasonalised series is all zeros: f_h = s[(11+h)%4].
    var pure_season = List[Float64]()
    for t in range(12):
        pure_season.append(season[t % 4])
    var seasonal_only = ets_aaa_forecast(pure_season, 1.0, 1.0, 1.0, 4, 4)
    var adjust2 = deseasonalise_flat(pure_season, 4)
    if (
        seasonal_only.status == FC_OK
        and _same(seasonal_only.values, _floats(1.0, -1.0, 2.0, -2.0))
        and seasonal_only.level == 0.0 and seasonal_only.trend == 0.0
        and _same(adjust2.indices, season)
        and adjust2.index_mean == 0.0
    ):
        passed += 1
        print("  ✅ a zero-mean seasonal series is reproduced exactly; indices are s itself")
    else:
        failed += 1
        print("  ❌ pure-seasonal case wrong:", seasonal_only.values[0], seasonal_only.values[1])

    # period = 1 is "no seasonality" and must reduce EXACTLY to ETS(A,A,N), not approximately.
    var aaa_flat = ets_aaa_forecast(lin, 0.4, 0.3, 0.9, 1, 3)
    var aan_same = ets_aan_forecast(lin, 0.4, 0.3, 0.9, 3)
    if (
        aaa_flat.status == FC_OK
        and _same(aaa_flat.values, aan_same.values)
        and aaa_flat.n_params == 3
    ):
        passed += 1
        print("  ✅ ETS(A,A,A) at period=1 is bit-equal to ETS(A,A,N) — no special case needed")
    else:
        failed += 1
        print("  ❌ period=1 did not reduce to ETS(A,A,N)")

    # ══ the frozen baselines, wrapped, and the two that would abort the worker ══════
    if (
        _same(baseline_forecast(lin, FC_METHOD_NAIVE, 3, 1).values, naive_forecast(lin, 3))
        and _same(baseline_forecast(lin, FC_METHOD_DRIFT, 3, 1).values, drift_forecast(lin, 3))
        and _same(baseline_forecast(lin, FC_METHOD_MEAN, 3, 1).values, sma_forecast(lin, 8, 3))
        and _same(
            baseline_forecast(lin, FC_METHOD_SEASONAL_NAIVE, 4, 4).values,
            seasonal_naive(lin, 4, 4),
        )
        and baseline_forecast(lin, FC_METHOD_NAIVE, 3, 1).values[0] == 20.5
        and baseline_forecast(lin, FC_METHOD_MEAN, 1, 1).values[0] == 11.75
    ):
        passed += 1
        print("  ✅ the four baselines are the frozen kernels verbatim (window mean 11.75)")
    else:
        failed += 1
        print("  ❌ baseline wrappers changed a frozen value")

    # `naive_forecast` reads data[len-1] and `seasonal_naive` indexes n - period + h%period,
    # so an empty series and period > n are process aborts in the frozen kernels. Guarded here.
    var empty = List[Float64]()
    if (
        _refused(baseline_forecast(empty, FC_METHOD_NAIVE, 3, 1))
        and baseline_forecast(empty, FC_METHOD_NAIVE, 3, 1).status == FC_ERR_EMPTY_SERIES
        and _refused(baseline_forecast(lin, FC_METHOD_SEASONAL_NAIVE, 3, 9))
        and baseline_forecast(lin, FC_METHOD_SEASONAL_NAIVE, 3, 9).status
            == FC_ERR_INSUFFICIENT_HISTORY
        and baseline_forecast(lin, FC_METHOD_SEASONAL_NAIVE, 3, 0).status == FC_ERR_PERIOD
        and _refused(baseline_forecast(lin, 99, 3, 1))
        and baseline_forecast(lin, 99, 3, 1).status == FC_ERR_METHOD
    ):
        passed += 1
        print("  ✅ empty series, period > n and an unknown id are refusals, not index reads")
    else:
        failed += 1
        print("  ❌ a baseline guard is missing")

    # ══ AR: the frozen silent clamp is real, and it is made a status ════════════════
    var six = _floats(1.0, 3.0, 2.0, 5.0, 4.0, 6.0)
    var over_fit = ar_fit_yule_walker(six, 10)
    var checked = ar_forecast_checked(six, 10, 3)
    if (
        len(over_fit.phi) == 10
        and over_fit.phi[9] == 0.0
        and over_fit.phi[8] == 0.0
        and _refused(checked)
        and checked.status == FC_ERR_INSUFFICIENT_HISTORY
        and ar_forecast_checked(six, 5, 3).status == FC_OK
        and ar_forecast_checked(six, 0, 3).status == FC_ERR_PARAM_RANGE
    ):
        passed += 1
        print("  ✅ AR(10) on six points really is a padded AR(5) frozen; the wrapper refuses it")
    else:
        failed += 1
        print("  ❌ AR clamp handling wrong:", len(over_fit.phi), checked.status)

    # A constant series has zero autocovariance, so durbin_levinson returns zero coefficients
    # and sigma2 = 0 and the forecast is the sample mean — correct, but all-zero phi is ALSO
    # what a failed fit returns, so has_scale and n_params must distinguish them.
    var flat = _floats(7.0, 7.0, 7.0, 7.0, 7.0, 7.0)
    var flat_ar = ar_forecast_checked(flat, 2, 3)
    if (
        flat_ar.status == FC_OK
        and flat_ar.has_forecast
        and _same(flat_ar.values, _floats(7.0, 7.0, 7.0))
        and flat_ar.scale == 0.0
        and not flat_ar.has_scale
        and flat_ar.n_params == 0
    ):
        passed += 1
        print("  ✅ a degenerate AR fit returns the mean with has_scale=False, n_params=0")
    else:
        failed += 1
        print("  ❌ degenerate AR not distinguishable:", flat_ar.has_scale, flat_ar.n_params)

    # ══ refusals, per rule 4: absent, never a padded or flat stand-in ═══════════════
    if (
        _refused(ets_ann_forecast(lin, 0.5, 9))
        and ets_ann_forecast(lin, 0.5, 9).status == FC_ERR_HORIZON
        and _refused(ets_ann_forecast(lin, 0.0, 3))
        and ets_ann_forecast(lin, 0.0, 3).status == FC_ERR_PARAM_RANGE
        and _refused(theta_forecast(lin, 0.5, 0.5, 3))
        and theta_forecast(lin, 0.5, 0.5, 3).status == FC_ERR_PARAM_RANGE
        and _refused(ets_aaa_forecast(lin, 0.5, 0.5, 1.0, 5, 3))
        and ets_aaa_forecast(lin, 0.5, 0.5, 1.0, 5, 3).status == FC_ERR_PERIOD
        and _refused(ets_aan_forecast(_floats(4.0), 0.5, 0.5, 1.0, 1))
        and ets_aan_forecast(_floats(4.0), 0.5, 0.5, 1.0, 1).status
            == FC_ERR_INSUFFICIENT_HISTORY
        and _refused(ets_aan_forecast(lin, 0.5, 0.5, 1.5, 3))
        and ets_aan_forecast(lin, 0.5, 0.5, 1.5, 3).status == FC_ERR_PARAM_RANGE
    ):
        passed += 1
        print("  ✅ horizon > n, alpha = 0, theta < 1, a short season and n < 2 are all refusals")
    else:
        failed += 1
        print("  ❌ a refusal returned a partial answer")

    # A season the series cannot support one interior cycle of yields no adjustment at all —
    # not `y` unchanged with has_result = True, which would be a wrong answer under success.
    var short_season = deseasonalise_flat(lin, 5)
    if (
        short_season.status == FC_ERR_PERIOD
        and not short_season.has_result
        and len(short_season.adjusted) == 0
        and len(short_season.indices) == 0
        and not short_season.reversible
    ):
        passed += 1
        print("  ✅ an unsupportable period yields NO adjusted series, not the input echoed")
    else:
        failed += 1
        print("  ❌ deseasonalise refusal leaked a result")

    print("  [forecasting.point] Passed:", passed, "Failed:", failed)
