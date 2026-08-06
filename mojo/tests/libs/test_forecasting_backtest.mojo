"""test_forecasting_backtest.mojo — known-value tests for the rolling-origin harness.

Hand-written. The whole point of a backtest is that its numbers are checkable, so every
expected value below is derivable by hand from the series.

Four kinds of assertion:

1. *A series on which the out-of-sample error is known exactly.* On `y_t = 1 + 3t` a drift
   forecast is exact at every origin, so a drift backtest must report a pooled MAE and RMSE of
   EXACTLY 0.0 over all 13 origins, with per-origin MAE exactly 0.0 too. And a NAIVE forecast on
   the same series is wrong by exactly `3h` at step `h`, so its error matrix is
   `[3, 6, 9]` in every row and its pooled MAE is exactly 6.0 and RMSE exactly `sqrt(42)`.
   Both are closed forms, not approximations.

2. *The origin arithmetic, independently.* `backtest_origin_count` is pure arithmetic, so it is
   tested on its own — 13, 4, 3, 0 and -1 — and then asserted to agree with
   `n_origins_requested` from a real run. Two independent computations agreeing is the point.

3. *Requested / run / refused as three separate numbers.* A configuration that admits 13 origins
   but whose method refuses all 13 returns FC_ERR_ALL_UNDEFINED with `n_origins_refused == 13`
   — deliberately a different status from FC_ERR_NO_ORIGINS, which is a configuration that
   admits none. Both are asserted, because "your windows are too short" and "your method refused
   every window" need different fixes.

4. *The error measures against the frozen kernel, and the exact relation where they differ.*
   `series.forecast_accuracy` is called DIRECTLY here: MAE and RMSE must be BIT-EQUAL to its
   first and third outputs, which is what proves this is not a second implementation. MAPE must
   NOT be equal to its second, and the relation `mape * n_defined == frozen_mape * n_points`
   is asserted exactly — the frozen kernel skips zero actuals and still divides by the full
   length, so its MAPE shrinks as the measure becomes less applicable. On
   `a = [0, 10, 0, 20]` the honest MAPE is 22.5 over 2 defined points and the frozen one is
   11.25 over 4.

The MASE denominator gets its own case for each of its three states: present and positive
(scale 3.0 on a slope-3 training series), present and ZERO (an exactly periodic training
series — a division by zero, so no MASE), and absent (a training series shorter than the
period). Three states, three flag combinations, and 0.0 cannot express all three.
"""
from std.math import abs as fabs, sqrt

from series import forecast_accuracy

from forecasting.backtest import (
    BacktestReport,
    backtest_flat,
    backtest_origin_count,
    backtest_residuals_at_step,
    forecast_errors_flat,
)
from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_METHOD,
    FC_ERR_NO_ORIGINS,
    FC_ERR_PARAM_RANGE,
    FC_METHOD_CROSTON,
    FC_METHOD_DRIFT,
    FC_METHOD_ETS_AAA,
    FC_METHOD_MAX,
    FC_METHOD_NAIVE,
    FC_METHOD_THETA_DRIFT,
    FC_OK,
)


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _refused(r: BacktestReport) -> Bool:
    """A refusal carries no matrix at all — not a partial one, not a zero-filled one."""
    return (
        r.status != FC_OK
        and not r.has_pooled
        and len(r.origin_index) == 0
        and len(r.forecast) == 0
        and len(r.actual) == 0
        and len(r.error) == 0
        and len(r.origin_mae) == 0
        and len(r.origin_rmse) == 0
        and r.n_origins_run == 0
        and r.n_cells == 0
        and r.worst_origin == -1
    )


def main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.backtest] known-value suite")

    # y = 1 + 3t over t = 0..19.
    var lin = List[Float64]()
    for t in range(20):
        lin.append(1.0 + 3.0 * Float64(t))

    # ══ the origin arithmetic, on its own ══════════════════════════════════════════
    # origins are t = min_train, min_train+step, ... while t + horizon <= n, so the count is
    # (n - horizon - min_train)/step + 1:  (20-3-5)/1+1 = 13,  /4+1 = 4,  /5+1 = 3.
    if (
        backtest_origin_count(20, 3, 5, 1) == 13
        and backtest_origin_count(20, 3, 5, 4) == 4
        and backtest_origin_count(20, 3, 5, 5) == 3
        and backtest_origin_count(20, 3, 17, 1) == 1
        and backtest_origin_count(20, 3, 18, 1) == 0
        and backtest_origin_count(5, 3, 5, 1) == 0
        and backtest_origin_count(0, 3, 5, 1) == -1
        and backtest_origin_count(20, 0, 5, 1) == -1
        and backtest_origin_count(20, 3, 0, 1) == -1
        and backtest_origin_count(20, 3, 5, 0) == -1
    ):
        passed += 1
        print("  ✅ origin count 13 / 4 / 3 / 1 / 0, and -1 for an INVALID configuration")
    else:
        failed += 1
        print("  ❌ origin arithmetic wrong:", backtest_origin_count(20, 3, 5, 1))

    # ══ drift on an exactly linear series: zero out-of-sample error everywhere ══════
    var drift = backtest_flat(lin, FC_METHOD_DRIFT, 3, 5, 1, True, 1, 1, 0.5, 0.5, 1.0, 2.0)
    var all_zero = True
    for i in range(len(drift.error)):
        if drift.error[i] != 0.0:
            all_zero = False
    for j in range(len(drift.origin_mae)):
        if drift.origin_mae[j] != 0.0 or drift.origin_rmse[j] != 0.0:
            all_zero = False
    if (
        drift.status == FC_OK
        and drift.n_origins_requested == 13
        and drift.n_origins_run == 13
        and drift.n_origins_refused == 0
        and drift.n_cells == 39
        and drift.mae == 0.0
        and drift.rmse == 0.0
        and drift.has_pooled
        and all_zero
        and drift.origin_index[0] == 5
        and drift.origin_index[12] == 17
        and drift.worst_origin == 0
        and drift.worst_origin_mae == 0.0
    ):
        passed += 1
        print("  ✅ drift on 1+3t: 13 origins, 39 cells, every error EXACTLY 0.0")
    else:
        failed += 1
        print("  ❌ drift backtest wrong:", drift.n_origins_run, drift.mae, drift.n_cells)

    # The two independent computations of the origin count must agree.
    if drift.n_origins_requested == backtest_origin_count(20, 3, 5, 1):
        passed += 1
        print("  ✅ n_origins_requested agrees with the standalone origin arithmetic")
    else:
        failed += 1
        print("  ❌ the two origin counts disagree")

    # ══ naive on the same series: wrong by exactly 3h at step h ════════════════════
    # error = actual - forecast = (y_{t+h} - y_{t-1}) = 3h for h = 1,2,3 -> 3, 6, 9.
    # MAE = (3+6+9)/3 = 6 exactly. RMSE = sqrt((9+36+81)/3) = sqrt(42).
    var naive = backtest_flat(lin, FC_METHOD_NAIVE, 3, 5, 5, False, 1, 1, 0.5, 0.5, 1.0, 2.0)
    var rows_match = naive.n_origins_run == 3
    for j in range(naive.n_origins_run):
        if (
            naive.error[j * 3] != 3.0
            or naive.error[j * 3 + 1] != 6.0
            or naive.error[j * 3 + 2] != 9.0
            or naive.origin_mae[j] != 6.0
        ):
            rows_match = False
    if (
        naive.status == FC_OK
        and rows_match
        and naive.mae == 6.0
        and naive.rmse == sqrt(42.0)
        and naive.origin_index[0] == 5
        and naive.origin_index[1] == 10
        and naive.origin_index[2] == 15
        and not naive.expanding
    ):
        passed += 1
        print("  ✅ naive on 1+3t is wrong by exactly 3h: MAE 6.0, RMSE sqrt(42)")
    else:
        failed += 1
        print("  ❌ naive backtest wrong:", naive.mae, naive.rmse, naive.n_origins_run)

    # ══ expanding and sliding are different statistics ═════════════════════════════
    # A series whose slope changes: a sliding window of 5 sees only the recent slope, an
    # expanding window averages both. Theta-drift uses the OLS slope, so the two must differ.
    var kinked = List[Float64]()
    for t in range(20):
        kinked.append(Float64(t) if t < 10 else 10.0 + 5.0 * Float64(t - 10))
    var wide = backtest_flat(
        kinked, FC_METHOD_THETA_DRIFT, 2, 5, 1, True, 1, 1, 1.0, 0.5, 1.0, 2.0
    )
    var narrow = backtest_flat(
        kinked, FC_METHOD_THETA_DRIFT, 2, 5, 1, False, 1, 1, 1.0, 0.5, 1.0, 2.0
    )
    if (
        wide.status == FC_OK and narrow.status == FC_OK
        and wide.n_origins_run == narrow.n_origins_run
        and wide.expanding and not narrow.expanding
        and wide.mae != narrow.mae
    ):
        passed += 1
        print("  ✅ expanding and sliding windows give different errors on a kinked series")
    else:
        failed += 1
        print("  ❌ window policy had no effect:", wide.mae, narrow.mae)

    # ══ requested / run / refused, and the two "nothing happened" statuses ═════════
    # ETS(A,A,A) at period 4 needs a window of at least 8, and min_train is 5, so every one of
    # the 13 admissible origins is refused. That is NOT the same as admitting no origin.
    var all_refused = backtest_flat(
        lin, FC_METHOD_ETS_AAA, 3, 5, 1, False, 4, 1, 0.5, 0.5, 1.0, 2.0
    )
    var none_admitted = backtest_flat(
        _floats(1.0, 2.0, 3.0, 4.0, 5.0, 6.0), FC_METHOD_NAIVE, 3, 4, 1, True,
        1, 1, 0.5, 0.5, 1.0, 2.0,
    )
    if (
        all_refused.status == FC_ERR_ALL_UNDEFINED
        and all_refused.n_origins_requested == 13
        and all_refused.n_origins_refused == 13
        and _refused(all_refused)
        and none_admitted.status == FC_ERR_NO_ORIGINS
        and none_admitted.n_origins_requested == 0
        and none_admitted.n_origins_refused == 0
        and _refused(none_admitted)
    ):
        passed += 1
        print("  ✅ 'every origin refused' and 'no origin admitted' are separate statuses")
    else:
        failed += 1
        print("  ❌ origin census wrong:", all_refused.status, all_refused.n_origins_refused,
              none_admitted.status)

    # A window shorter than the horizon cannot support the forecast it is asked for — the
    # per-origin form of the horizon rule, refused up front so the message names the cause.
    if (
        backtest_flat(lin, FC_METHOD_NAIVE, 6, 5, 1, True, 1, 1, 0.5, 0.5, 1.0, 2.0).status
            == FC_ERR_INSUFFICIENT_HISTORY
        and backtest_flat(lin, 99, 3, 5, 1, True, 1, 1, 0.5, 0.5, 1.0, 2.0).status
            == FC_ERR_METHOD
        and backtest_flat(lin, FC_METHOD_NAIVE, 3, 0, 1, True, 1, 1, 0.5, 0.5, 1.0, 2.0).status
            == FC_ERR_PARAM_RANGE
        and backtest_flat(lin, FC_METHOD_NAIVE, 3, 5, 0, True, 1, 1, 0.5, 0.5, 1.0, 2.0).status
            == FC_ERR_PARAM_RANGE
        and backtest_flat(lin, FC_METHOD_MAX + 1, 3, 5, 1, True, 1, 1, 0.5, 0.5, 1.0, 2.0).status
            == FC_ERR_METHOD
    ):
        passed += 1
        print("  ✅ min_train < horizon, an unknown id and a zero step are all refusals")
    else:
        failed += 1
        print("  ❌ a backtest guard is missing")

    # Croston is reachable through the same harness, and refuses windows with no demand.
    var sparse = List[Float64]()
    for t in range(24):
        sparse.append(4.0 if t % 6 == 2 else 0.0)
    var croston_bt = backtest_flat(
        sparse, FC_METHOD_CROSTON, 2, 8, 2, True, 1, 1, 0.4, 0.4, 1.0, 2.0
    )
    if (
        croston_bt.status == FC_OK
        and croston_bt.n_origins_run > 0
        and croston_bt.n_origins_run + croston_bt.n_origins_refused
            == croston_bt.n_origins_requested
        and croston_bt.method_id == FC_METHOD_CROSTON
    ):
        passed += 1
        print("  ✅ Croston runs in the harness and run + refused == requested")
    else:
        failed += 1
        print("  ❌ Croston backtest wrong:", croston_bt.status, croston_bt.n_origins_run)

    # ══ residual columns, and the wrapping-multiply regression ═════════════════════
    var column1 = backtest_residuals_at_step(naive.error, naive.n_origins_run, 3, 1)
    var column2 = backtest_residuals_at_step(naive.error, naive.n_origins_run, 3, 2)
    if (
        len(column1) == 3 and column1[0] == 6.0 and column1[2] == 6.0
        and len(column2) == 3 and column2[0] == 9.0
        and len(backtest_residuals_at_step(naive.error, naive.n_origins_run, 3, 3)) == 0
        and len(backtest_residuals_at_step(naive.error, naive.n_origins_run, 3, -1)) == 0
        and len(backtest_residuals_at_step(naive.error, 5, 3, 0)) == 0
        and len(backtest_residuals_at_step(_floats(1.0, 2.0), 3, 6148914691236517206, 0)) == 0
    ):
        passed += 1
        print("  ✅ residual columns are per lead time; a wrapping shape returns EMPTY")
    else:
        failed += 1
        print("  ❌ residual column extraction wrong:", len(column1))

    # ══ the error measures, against the frozen kernel ══════════════════════════════
    # a = [0, 10, 0, 20], f = [1, 8, 0, 25]:
    #   MAE  = (1+2+0+5)/4 = 2                          RMSE = sqrt((1+4+0+25)/4) = sqrt(7.5)
    #   MAPE defined only at a=10 (0.2) and a=20 (0.25) -> (0.45/2)*100 = 22.5, 2 undefined
    #   frozen MAPE divides the same 0.45 by 4          -> 11.25
    #   sMAPE: 2*1/1 = 2, 2*2/18, (0,0) undefined, 2*5/45 -> (2 + 4/18 + 10/45)/3 * 100
    #   MASE denominator on a slope-3 training series at period 1 is exactly 3, so 2/3.
    var actual = _floats(0.0, 10.0, 0.0, 20.0)
    var predicted = _floats(1.0, 8.0, 0.0, 25.0)
    var report = forecast_errors_flat(actual, predicted, lin, 1)
    var frozen = forecast_accuracy(actual, predicted)
    if (
        report.status == FC_OK
        and report.mae == frozen[0]
        and report.rmse == frozen[2]
        and report.mae == 2.0
        and report.rmse == sqrt(7.5)
        and report.has_mae and report.has_rmse
    ):
        passed += 1
        print("  ✅ MAE and RMSE are BIT-EQUAL to the frozen forecast_accuracy: 2.0, sqrt(7.5)")
    else:
        failed += 1
        print("  ❌ MAE/RMSE not identical to frozen:", report.mae, frozen[0])

    if (
        report.has_mape
        and report.mape == 22.5
        and report.n_defined_mape == 2
        and report.n_undefined_mape == 2
        and frozen[1] == 11.25
        and report.mape != frozen[1]
        and report.mape * Float64(report.n_defined_mape)
            == frozen[1] * Float64(report.n_points)
    ):
        passed += 1
        print("  ✅ honest MAPE 22.5 over 2 points; frozen 11.25 over 4; relation exact")
    else:
        failed += 1
        print("  ❌ MAPE accounting wrong:", report.mape, report.n_defined_mape, frozen[1])

    # (2 + 4/18 + 10/45)/3 * 100 = 81.481481481481... The literal expression below is folded
    # by the COMPILER at higher-than-double precision, so it yields the exactly-rounded
    # 81.48148148148148 while the kernel's left-to-right double accumulation yields
    # 81.4814814814815 — one ulp apart, both correct. This is the one comparison in this suite
    # that cannot be `==`, and the tolerance is 8 ulps of THIS quantity's own magnitude and of
    # nothing else.
    var expected_smape = (2.0 + 4.0 / 18.0 + 10.0 / 45.0) / 3.0 * 100.0
    var smape_gap = fabs(report.smape - expected_smape)
    if (
        report.has_smape
        and smape_gap <= 8.0 * 2.220446049250313e-16 * expected_smape
        and report.n_defined_smape == 3
        and report.n_undefined_smape == 1
    ):
        passed += 1
        print("  ✅ sMAPE has its OWN undefined set (the 0-forecast-for-0-actual point)")
    else:
        failed += 1
        print("  ❌ sMAPE wrong:", report.smape, expected_smape, report.n_defined_smape)

    # ══ MASE in all three of its states ═══════════════════════════════════════════
    var periodic = _floats(1.0, 2.0, 1.0, 2.0, 1.0, 2.0)
    var zero_scale = forecast_errors_flat(actual, predicted, periodic, 2)
    var no_scale = forecast_errors_flat(actual, predicted, _floats(5.0), 4)
    if (
        report.has_scale and report.scale_denominator == 3.0
        and report.has_mase and report.mase == 2.0 / 3.0
        and zero_scale.has_scale and zero_scale.scale_denominator == 0.0
        and not zero_scale.has_mase
        and not no_scale.has_scale
        and no_scale.scale_denominator == 0.0
        and not no_scale.has_mase
        and zero_scale.status == FC_OK and no_scale.status == FC_OK
    ):
        passed += 1
        print("  ✅ MASE: present (2/3), denominator ZERO, and denominator ABSENT are distinct")
    else:
        failed += 1
        print("  ❌ MASE states not distinguishable:", report.scale_denominator,
              zero_scale.has_scale, no_scale.has_scale)

    # An inapplicable MAPE must not withhold a perfectly good MAE.
    var all_zero_actual = _floats(0.0, 0.0, 0.0)
    var some_forecast = _floats(1.0, -2.0, 3.0)
    var zeros_report = forecast_errors_flat(all_zero_actual, some_forecast, lin, 1)
    if (
        zeros_report.status == FC_OK
        and zeros_report.has_mae and zeros_report.mae == 2.0
        and not zeros_report.has_mape
        and zeros_report.mape == 0.0
        and zeros_report.n_defined_mape == 0
        and zeros_report.n_undefined_mape == 3
        and zeros_report.has_smape and zeros_report.smape == 200.0
    ):
        passed += 1
        print("  ✅ every actual zero: MAPE absent with a count of 3, MAE still 2.0")
    else:
        failed += 1
        print("  ❌ all-zero-actual handling wrong:", zeros_report.has_mape,
              zeros_report.n_undefined_mape, zeros_report.mae)

    if (
        forecast_errors_flat(actual, _floats(1.0), lin, 1).status == FC_ERR_LENGTH_MISMATCH
        and forecast_errors_flat(List[Float64](), List[Float64](), lin, 1).status
            == FC_ERR_EMPTY_SERIES
        and not forecast_errors_flat(actual, _floats(1.0), lin, 1).has_mae
    ):
        passed += 1
        print("  ✅ unequal lengths and an empty pair are refusals with no measures at all")
    else:
        failed += 1
        print("  ❌ error-report refusals wrong")

    print("  [forecasting.backtest] Passed:", passed, "Failed:", failed)
