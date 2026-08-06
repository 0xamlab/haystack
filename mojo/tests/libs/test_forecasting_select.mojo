"""test_forecasting_select.mojo — known-value tests for per-series selection/combination.

Hand-written. The strongest assertions here are IDENTITIES, not tolerances:

  * On a perfect line the theta-2 line is the series itself (`Z = 2y - L = y` because
    the OLS line of a line is the line, in exact dyadic arithmetic), so the theta
    in-sample MAE is EXACTLY half the SES in-sample MAE — the two golden-section fits
    see bit-identical inputs and return bit-identical alphas. Asserted with `==`.
  * On a constant series every candidate fits exactly (MAE exactly 0.0 for all three:
    the damped fit's heuristic start is exactly (c, 0), which is already the optimum),
    so selection must break the tie to the FIRST candidate (SES — the simpler model)
    and the combination must split the weight EXACTLY into thirds and forecast EXACTLY c.

Ordering on the line is the behavioural known value: SES cannot track a trend (MAE ~ 3,
the slope), classical Theta halves it, the fitted damped trend nearly zeroes it — so the
selector must pick Damped, with the one-hot weight vector saying so.
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HORIZON,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_METHOD_ETS_AAN,
    FC_METHOD_ETS_ANN,
    FC_METHOD_THETA,
    FC_OK,
)
from forecasting.select import (
    SelectedForecast,
    combine_inverse_mae_fitted,
    select_best_fitted,
)


def _line() -> List[Float64]:
    var y = List[Float64]()
    for t in range(12):
        y.append(2.0 + 3.0 * Float64(t))
    return y^


def main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.select] hand-written known-value suite")

    # ══ 1. a trending series selects the trend model ══════════════════════════════════
    var yl = _line()
    var sb = select_best_fitted(yl, 4)
    if (
        sb.status == FC_OK and sb.has_forecast
        and sb.chosen_method_id == FC_METHOD_ETS_AAN and not sb.is_combination
        and sb.maes[1] < sb.maes[2] and sb.maes[2] < sb.maes[0]
        and sb.weights[0] == 0.0 and sb.weights[1] == 1.0 and sb.weights[2] == 0.0
        and sb.method_ids[0] == FC_METHOD_ETS_ANN
        and sb.method_ids[1] == FC_METHOD_ETS_AAN
        and sb.method_ids[2] == FC_METHOD_THETA
        and sb.component_status[0] == FC_OK
        and sb.component_status[1] == FC_OK
        and sb.component_status[2] == FC_OK
    ):
        passed += 1
        print("  ✅ on y = 2+3t: Damped < Theta < SES in-sample, Damped selected one-hot")
    else:
        failed += 1
        print("  ❌ selection on a line wrong:", sb.chosen_method_id,
              sb.maes[0], sb.maes[1], sb.maes[2])

    # The identity: Z = 2y - L = y on an exact line (OLS of a line is the line, and
    # every quantity is a small integer), so the theta-line SES sees bit-identical
    # input and the theta MAE is EXACTLY half the SES MAE. `==`, not a tolerance.
    if sb.maes[2] == 0.5 * sb.maes[0]:
        passed += 1
        print("  ✅ theta in-sample MAE == exactly half the SES MAE (the theta identity)")
    else:
        failed += 1
        print("  ❌ theta identity broken:", sb.maes[2], 0.5 * sb.maes[0])

    # ══ 2. a constant series: exact ties, deterministic outcomes ═════════════════════
    var yc = List[Float64]()
    for _ in range(10):
        yc.append(5.0)
    var sc = select_best_fitted(yc, 3)
    if (
        sc.status == FC_OK and sc.chosen_method_id == FC_METHOD_ETS_ANN
        and sc.maes[0] == 0.0 and sc.maes[1] == 0.0 and sc.maes[2] == 0.0
        and sc.values[0] == 5.0 and sc.values[2] == 5.0
    ):
        passed += 1
        print("  ✅ constant series: all MAEs exactly 0, tie breaks to SES, forecast exactly c")
    else:
        failed += 1
        print("  ❌ constant selection wrong:", sc.chosen_method_id, sc.maes[1])

    var cc = combine_inverse_mae_fitted(yc, 3)
    var third = 1.0 / Float64(3)
    if (
        cc.status == FC_OK and cc.is_combination and cc.chosen_method_id == -1
        and cc.weights[0] == third and cc.weights[1] == third and cc.weights[2] == third
        and cc.values[0] == 5.0
    ):
        passed += 1
        print("  ✅ constant combination: exact three-way split, forecast exactly c")
    else:
        failed += 1
        print("  ❌ constant combination wrong:", cc.weights[0], cc.values[0])

    # ══ 3. combination weights are a distribution over the FITTED candidates ══════════
    var yk = List[Float64]()
    yk.append(107.0)
    for t in range(1, 12):
        yk.append(100.0 + 3.0 * Float64(t))
    var ck = combine_inverse_mae_fitted(yk, 6)
    var wsum: Float64 = 0.0
    var wneg = False
    for i in range(3):
        wsum += ck.weights[i]
        if ck.weights[i] < 0.0:
            wneg = True
    if ck.status == FC_OK and not wneg and fabs(wsum - 1.0) <= 1.0e-12:
        passed += 1
        print("  ✅ inverse-MAE weights are non-negative and sum to 1")
    else:
        failed += 1
        print("  ❌ weights are not a distribution:", wsum)

    # ══ 4. bit-reproducibility ════════════════════════════════════════════════════════
    var c1 = combine_inverse_mae_fitted(yk, 6)
    var c2 = combine_inverse_mae_fitted(yk, 6)
    var same = True
    for k in range(6):
        if c1.values[k] != c2.values[k]:
            same = False
    for i in range(3):
        if c1.weights[i] != c2.weights[i] or c1.maes[i] != c2.maes[i]:
            same = False
    if same:
        passed += 1
        print("  ✅ bit-reproducible: two identical calls agree to the bit")
    else:
        failed += 1
        print("  ❌ selection is not deterministic")

    # ══ 5. no candidate fits -> no forecast, and the absence is typed ════════════════
    var yo = List[Float64]()
    for t in range(8):
        yo.append(1.0e308 if t % 2 == 0 else -1.0e308)
    var so = select_best_fitted(yo, 3)
    var co = combine_inverse_mae_fitted(yo, 3)
    if (
        so.status == FC_ERR_ALL_UNDEFINED and not so.has_forecast and len(so.values) == 0
        and so.maes[0] == -1.0 and so.maes[1] == -1.0 and so.maes[2] == -1.0
        and so.weights[0] == 0.0 and so.weights[1] == 0.0 and so.weights[2] == 0.0
        and co.status == FC_ERR_ALL_UNDEFINED and not co.has_forecast
    ):
        passed += 1
        print("  ✅ every candidate undefined: no forecast, MAEs -1.0 (loud), weights 0")
    else:
        failed += 1
        print("  ❌ a selection among nothing returned something:", so.status, co.status)

    # ══ 6. refusals ══════════════════════════════════════════════════════════════════
    var two = List[Float64]()
    two.append(4.0)
    two.append(5.0)
    if (
        select_best_fitted(List[Float64](), 3).status == FC_ERR_EMPTY_SERIES
        and select_best_fitted(two, 1).status == FC_ERR_INSUFFICIENT_HISTORY
        and combine_inverse_mae_fitted(two, 1).status == FC_ERR_INSUFFICIENT_HISTORY
        and select_best_fitted(yl, 20).status == FC_ERR_HORIZON
        and len(select_best_fitted(yl, 20).values) == 0
    ):
        passed += 1
        print("  ✅ empty, n < 3 and horizon > n are refusals with no partial answer")
    else:
        failed += 1
        print("  ❌ a refusal leaked a result")

    print("  [forecasting.select] Passed:", passed, "Failed:", failed)
