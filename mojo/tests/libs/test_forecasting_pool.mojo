"""test_forecasting_pool.mojo — known-value tests for wide-pool training-holdout selection.

Hand-written. The two tests that carry the module's reason to exist:

  * THE REGIME-BREAK SERIES (trend body, plateau tail). The in-sample one-step criterion
    (`forecasting.select`) is dominated by the 30-point trend body and picks Damped; the
    last-horizon TRAINING-holdout criterion sees the plateau and picks Naive2 — and on a
    constructed continuation of the plateau (never an input to anything) the holdout
    pick's error is >5x smaller. Criterion changed the answer, and the answer is better:
    both halves asserted, neither narrated.
  * THE REFUTER SERIES (pure trend, M4-Yearly minimum shape n=13/h=6). A test window
    that collapses to zero would reward SES or Naive2; the pool CANNOT see any test
    window (the signature has no such argument) and must select Holt, whose holdout MAE
    on the trend tail is exactly 0.0. Selecting a method the training data does not
    support is the leak this module is built to make impossible.

The fit-refit split is asserted structurally: on the break series the Naive2 HOLDOUT row
is exactly 68.0 (last value of the TRUNCATED window, `y[29]`) while its FULL row is
exactly 68.1 (`y[35]`) — two different numbers only a genuine fit-on-prefix /
refit-on-full implementation produces.

Blend arithmetic is pinned on synthetic matrices with binary-exact values (weights
2/10 and 8/10, means of small integers, medians of odd sets), so the assertions are
`==`, not tolerances, wherever the arithmetic is exact.
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HORIZON,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_METHOD,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_PERIOD,
    FC_METHOD_ETS_AAN,
    FC_OK,
)
from forecasting.pool import (
    POOL_CAND_COMB,
    POOL_CAND_DAMPED,
    POOL_CAND_ETS_AAA,
    POOL_CAND_HOLT,
    POOL_CAND_NAIVE2,
    POOL_CAND_SES,
    POOL_CAND_SNAIVE,
    POOL_CAND_THETA,
    POOL_MODE_INV_MAE,
    POOL_MODE_MEAN,
    POOL_MODE_MEDIAN,
    POOL_MODE_SELECT,
    POOL_N_CANDIDATES,
    pool_blend_flat,
    pool_candidate_name,
    pool_holdout_forecast,
    pool_holdout_report,
    pool_mode_name,
)
from forecasting.select import select_best_fitted


fn _break_series() -> List[Float64]:
    """30 points of y = 10 + 2t, then a 6-point plateau with a deterministic wiggle."""
    var y = List[Float64]()
    for t in range(30):
        y.append(10.0 + 2.0 * Float64(t))
    y.append(68.2)
    y.append(67.9)
    y.append(68.1)
    y.append(67.8)
    y.append(68.0)
    y.append(68.1)
    return y^


fn _trend_13() -> List[Float64]:
    """A pure line at the M4-Yearly minimum shape: n = 13, so u = 7 with h = 6."""
    var y = List[Float64]()
    for t in range(13):
        y.append(50.0 + 3.0 * Float64(t))
    return y^


fn main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.pool] hand-written known-value suite")

    # ══ 1. THE HEADLINE: holdout picks differently from in-sample, and better ═════════
    var yb = _break_series()
    var rb = pool_holdout_report(yb, yb, 1, 6)
    var fb = pool_holdout_forecast(yb, yb, 1, 6, POOL_MODE_SELECT, 0)
    var sb = select_best_fitted(yb, 6)
    if (
        rb.status == FC_OK and rb.has_report and rb.n_train == 36 and rb.n_fit == 30
        and fb.status == FC_OK and fb.chosen_candidate == POOL_CAND_NAIVE2
        and not fb.is_combination
        and sb.status == FC_OK and sb.chosen_method_id == FC_METHOD_ETS_AAN
    ):
        passed += 1
        print("  ✅ break series: in-sample picks Damped, training-holdout picks Naive2")
    else:
        failed += 1
        print("  ❌ break-series picks wrong:", fb.chosen_candidate, sb.chosen_method_id)

    # Apples-to-apples reversal on the SHARED candidates: in-sample orders
    # Damped < SES, the holdout tail orders SES < Damped. Same series, same models.
    if (
        rb.holdout_mae[POOL_CAND_SES] < rb.holdout_mae[POOL_CAND_DAMPED]
        and sb.maes[1] < sb.maes[0]
    ):
        passed += 1
        print("  ✅ the two criteria ORDER the shared candidates oppositely")
    else:
        failed += 1
        print("  ❌ no criterion reversal:", rb.holdout_mae[POOL_CAND_SES],
              rb.holdout_mae[POOL_CAND_DAMPED], sb.maes[0], sb.maes[1])

    # The constructed continuation of the plateau — built HERE, an input to NOTHING
    # above — must reward the holdout pick by a wide margin (>5x, measured ~31x).
    var future = List[Float64]()
    future.append(68.0)
    future.append(68.2)
    future.append(67.9)
    future.append(68.1)
    future.append(68.0)
    future.append(67.9)
    var mae_pool: Float64 = 0.0
    var mae_insample: Float64 = 0.0
    for k in range(6):
        mae_pool += fabs(future[k] - fb.values[k])
        mae_insample += fabs(future[k] - sb.values[k])
    if mae_pool * 5.0 < mae_insample:
        passed += 1
        print("  ✅ on the continuation the holdout pick is >5x better than the in-sample pick")
    else:
        failed += 1
        print("  ❌ holdout pick not better on the future:", mae_pool, mae_insample)

    # Fit-on-prefix vs refit-on-full, asserted on numbers only that split produces:
    # Naive2's holdout row anchors at y[29] = 68.0, its full row at y[35] = 68.1.
    var prefix_ok = True
    for k in range(6):
        if rb.holdout_values[POOL_CAND_NAIVE2 * 6 + k] != 68.0:
            prefix_ok = False
        if rb.full_values[POOL_CAND_NAIVE2 * 6 + k] != 68.1:
            prefix_ok = False
    if prefix_ok and len(rb.holdout_values) == 48 and len(rb.full_values) == 48:
        passed += 1
        print("  ✅ naive2 holdout row anchors at y[29], full row at y[35] — the refit is real")
    else:
        failed += 1
        print("  ❌ fit/refit split broken:", rb.holdout_values[POOL_CAND_NAIVE2 * 6],
              rb.full_values[POOL_CAND_NAIVE2 * 6])

    # Non-seasonal pool: ets_aaa and snaive are OUT, typed as FC_ERR_PERIOD, never 0-weight OK.
    if (
        rb.candidate_status[POOL_CAND_ETS_AAA] == FC_ERR_PERIOD
        and rb.candidate_status[POOL_CAND_SNAIVE] == FC_ERR_PERIOD
        and rb.holdout_mae[POOL_CAND_ETS_AAA] == -1.0
        and rb.holdout_mae[POOL_CAND_SNAIVE] == -1.0
    ):
        passed += 1
        print("  ✅ period == 1 excludes ets_aaa and snaive with FC_ERR_PERIOD and loud MAEs")
    else:
        failed += 1
        print("  ❌ period-1 exclusion wrong:", rb.candidate_status[POOL_CAND_ETS_AAA])

    # ══ 2. THE REFUTER SERIES: a rewarding test window cannot buy selection ═══════════
    var yt = _trend_13()
    var rt = pool_holdout_report(yt, yt, 1, 6)
    var ft = pool_holdout_forecast(yt, yt, 1, 6, POOL_MODE_SELECT, 0)
    # A future that collapses to zero would reward SES (holdout MAE 10.53) or Naive2
    # (10.5) over Holt (exactly 0.0). The pool has no argument through which that future
    # could arrive, and the training data supports exactly one answer.
    if (
        ft.status == FC_OK and ft.chosen_candidate == POOL_CAND_HOLT
        and rt.holdout_mae[POOL_CAND_HOLT] == 0.0
        and ft.chosen_candidate != POOL_CAND_SES
        and ft.chosen_candidate != POOL_CAND_NAIVE2
        and rt.holdout_mae[POOL_CAND_SES] > 10.0
        and rt.holdout_mae[POOL_CAND_NAIVE2] > 10.0
    ):
        passed += 1
        print("  ✅ pure trend at n=13: Holt selected (holdout MAE exactly 0), never SES/Naive2")
    else:
        failed += 1
        print("  ❌ refuter series selection wrong:", ft.chosen_candidate,
              rt.holdout_mae[POOL_CAND_HOLT])

    # Exact holdout fit takes the WHOLE inverse-MAE weight (the overflow rule).
    var fi = pool_holdout_forecast(yt, yt, 1, 6, POOL_MODE_INV_MAE, 0)
    if (
        fi.status == FC_OK and fi.weights[POOL_CAND_HOLT] == 1.0
        and fi.weights[POOL_CAND_SES] == 0.0 and fi.chosen_candidate == POOL_CAND_HOLT
        and not fi.is_combination
    ):
        passed += 1
        print("  ✅ exact holdout fit takes the whole weight; a pool of one is not a combination")
    else:
        failed += 1
        print("  ❌ exact-fit weighting wrong:", fi.weights[POOL_CAND_HOLT])

    # Determinism: the same training data gives the bit-identical decision, twice.
    var fb2 = pool_holdout_forecast(yb, yb, 1, 6, POOL_MODE_SELECT, 0)
    var same = fb2.chosen_candidate == fb.chosen_candidate
    for k in range(6):
        if fb2.values[k] != fb.values[k]:
            same = False
    for i in range(POOL_N_CANDIDATES):
        if fb2.weights[i] != fb.weights[i] or fb2.holdout_mae[i] != fb.holdout_mae[i]:
            same = False
    if same:
        passed += 1
        print("  ✅ bit-identical decision on a repeated call")
    else:
        failed += 1
        print("  ❌ selection is not deterministic")

    # SELECT reads the ranking's head; top_k is validated but cannot change the winner.
    var fk = pool_holdout_forecast(yb, yb, 1, 6, POOL_MODE_SELECT, 2)
    if fk.chosen_candidate == fb.chosen_candidate and fk.values[0] == fb.values[0]:
        passed += 1
        print("  ✅ POOL_MODE_SELECT is invariant to top_k")
    else:
        failed += 1
        print("  ❌ top_k changed a hard selection")

    # ══ 2b. The pool is the INTERSECTION of both fits ═════════════════════════════════
    # A calm 16-point body, then the last 4 TRAINING points jump to ~1e307. The
    # truncated fit never sees the jump and succeeds for every trend model; the FULL
    # refit overflows Holt/Damped/Comb (FC_ERR_ALL_UNDEFINED) and Theta's OLS sums
    # (FC_ERR_NON_FINITE). A candidate with no shippable full-training path must leave
    # the pool — keeping it would hand the blend its zero-filled placeholder row.
    var yj = List[Float64]()
    for t in range(16):
        yj.append(100.0 + Float64(t))
    yj.append(1.0e307)
    yj.append(2.0e307)
    yj.append(3.0e307)
    yj.append(4.0e307)
    var rj = pool_holdout_report(yj, yj, 1, 4)
    var gj = pool_holdout_forecast(yj, yj, 1, 4, POOL_MODE_INV_MAE, 0)
    if (
        rj.status == FC_OK
        and rj.candidate_status[POOL_CAND_HOLT] == FC_ERR_ALL_UNDEFINED
        and rj.candidate_status[POOL_CAND_DAMPED] == FC_ERR_ALL_UNDEFINED
        and rj.candidate_status[POOL_CAND_COMB] == FC_ERR_ALL_UNDEFINED
        and rj.candidate_status[POOL_CAND_THETA] == FC_ERR_NON_FINITE
        and rj.holdout_mae[POOL_CAND_HOLT] == -1.0
        and rj.candidate_status[POOL_CAND_SES] == FC_OK
        and rj.candidate_status[POOL_CAND_NAIVE2] == FC_OK
        and gj.status == FC_OK
        and gj.weights[POOL_CAND_SES] == 0.5 and gj.weights[POOL_CAND_NAIVE2] == 0.5
        and gj.weights[POOL_CAND_HOLT] == 0.0
        and gj.values[0] > 3.9e307
    ):
        passed += 1
        print("  ✅ a holdout-only success leaves the pool: no zero-row placeholder is blendable")
    else:
        failed += 1
        print("  ❌ intersection rule broken:", rj.candidate_status[POOL_CAND_HOLT],
              gj.weights[POOL_CAND_SES], gj.values[0])

    # ══ 3. Seasonal known values: binary-exact factors, exact assertions ══════════════
    # Constant base 100 under S = [1.25, 0.75, 1.5, 0.5] — every product is exact in
    # binary, so the seasonal mapping is asserted with ==, not tolerances.
    var sraw = List[Float64]()
    var sdes = List[Float64]()
    for t in range(24):
        var s: Float64 = 1.25
        if t % 4 == 1:
            s = 0.75
        elif t % 4 == 2:
            s = 1.5
        elif t % 4 == 3:
            s = 0.5
        sraw.append(100.0 * s)
        sdes.append(100.0)
    var rs = pool_holdout_report(sraw, sdes, 4, 4)
    var fs = pool_holdout_forecast(sraw, sdes, 4, 4, POOL_MODE_SELECT, 0)
    if (
        rs.status == FC_OK
        and rs.si_future[0] == 1.25 and rs.si_future[1] == 0.75
        and rs.si_future[2] == 1.5 and rs.si_future[3] == 0.5
        and rs.candidate_status[POOL_CAND_ETS_AAA] == FC_OK
        and rs.candidate_status[POOL_CAND_SNAIVE] == FC_OK
        and rs.holdout_mae[POOL_CAND_SNAIVE] == 0.0
        and rs.holdout_mae[POOL_CAND_NAIVE2] == 0.0
        and fs.chosen_candidate == POOL_CAND_SES
        and fs.values[0] == 125.0 and fs.values[1] == 75.0
        and fs.values[2] == 150.0 and fs.values[3] == 50.0
    ):
        passed += 1
        print("  ✅ seasonal constant: SIout tiling exact, tie breaks to SES, pattern exact")
    else:
        failed += 1
        print("  ❌ seasonal known values wrong:", fs.chosen_candidate, fs.values[0])

    # The exact-fit split among EXACT candidates only: SES, Theta, Comb, sNaive and
    # Naive2 reproduce the pattern to the bit (MAE exactly 0.0); the Nelder-Mead fits
    # land within 3e-14 but NOT at zero, so each exact candidate weighs exactly 1/5.
    var gs = pool_holdout_forecast(sraw, sdes, 4, 4, POOL_MODE_INV_MAE, 0)
    var fifth = 1.0 / Float64(5)
    if (
        gs.status == FC_OK and gs.is_combination
        and gs.weights[POOL_CAND_SES] == fifth
        and gs.weights[POOL_CAND_THETA] == fifth
        and gs.weights[POOL_CAND_COMB] == fifth
        and gs.weights[POOL_CAND_SNAIVE] == fifth
        and gs.weights[POOL_CAND_NAIVE2] == fifth
        and gs.weights[POOL_CAND_HOLT] == 0.0
        and gs.weights[POOL_CAND_DAMPED] == 0.0
        and gs.weights[POOL_CAND_ETS_AAA] == 0.0
        and gs.values[0] == 125.0 and gs.values[3] == 50.0
    ):
        passed += 1
        print("  ✅ five exact fits split the weight exactly; near-exact NM fits weigh 0")
    else:
        failed += 1
        print("  ❌ exact-split weights wrong:", gs.weights[POOL_CAND_SES],
              gs.weights[POOL_CAND_HOLT])

    # ══ 4. Blend arithmetic on synthetic matrices (no fitting, exact numbers) ═════════
    # Candidate 2's row is far from the others so a median and a mean DISAGREE at
    # every step — an arithmetic-sequence column would make the two identical and the
    # median assertion vacuous (a mutation to mean was measured passing; this is the fix).
    var full = List[Float64]()
    full.append(1.0)
    full.append(2.0)    # candidate 0
    full.append(3.0)
    full.append(4.0)    # candidate 1
    full.append(10.0)
    full.append(20.0)   # candidate 2
    var maes = List[Float64]()
    maes.append(0.5)
    maes.append(0.25)
    maes.append(0.125)
    var ok3 = List[Int]()
    for _ in range(3):
        ok3.append(FC_OK)

    var bsel = pool_blend_flat(full, maes, ok3, 3, 2, POOL_MODE_SELECT, 0)
    var bmean = pool_blend_flat(full, maes, ok3, 3, 2, POOL_MODE_MEAN, 2)
    var bmed3 = pool_blend_flat(full, maes, ok3, 3, 2, POOL_MODE_MEDIAN, 3)
    var bmed2 = pool_blend_flat(full, maes, ok3, 3, 2, POOL_MODE_MEDIAN, 2)
    if (
        bsel.chosen_candidate == 2 and bsel.values[0] == 10.0 and bsel.values[1] == 20.0
        and bmean.values[0] == 6.5 and bmean.values[1] == 12.0    # mean of rows 2 and 1
        and bmean.weights[1] == 0.5 and bmean.weights[2] == 0.5 and bmean.weights[0] == 0.0
        and bmed3.values[0] == 3.0 and bmed3.values[1] == 4.0     # odd median = middle row, NOT the mean 14/3
        and bmed2.values[0] == 6.5 and bmed2.values[1] == 12.0    # even median = middle mean
        and bmed3.is_combination and bmed3.chosen_candidate == -1
    ):
        passed += 1
        print("  ✅ blend arithmetic exact: argmin, top-2 mean, odd and even medians")
    else:
        failed += 1
        print("  ❌ blend arithmetic wrong:", bsel.values[0], bmean.values[0],
              bmed3.values[0], bmed2.values[0])

    # Inverse-MAE weights over a pool with a refusal: inverses (2, --, 8) normalise to
    # exactly 0.2 / 0.8, and the refused row keeps weight 0 without repair.
    var maes_r = List[Float64]()
    maes_r.append(0.5)
    maes_r.append(-1.0)
    maes_r.append(0.125)
    var st_r = List[Int]()
    st_r.append(FC_OK)
    st_r.append(FC_ERR_NON_FINITE)
    st_r.append(FC_OK)
    var binv = pool_blend_flat(full, maes_r, st_r, 3, 2, POOL_MODE_INV_MAE, 0)
    if (
        binv.status == FC_OK and binv.weights[0] == 0.2 and binv.weights[1] == 0.0
        and binv.weights[2] == 0.8
        and fabs(binv.values[0] - (0.2 * 1.0 + 0.8 * 10.0)) < 1.0e-12
    ):
        passed += 1
        print("  ✅ inverse-MAE weights 0.2/0.8 around a refused candidate")
    else:
        failed += 1
        print("  ❌ inverse weights wrong:", binv.weights[0], binv.weights[2])

    # A single survivor IS that candidate, whatever the mode asked for.
    var st_one = List[Int]()
    st_one.append(FC_ERR_NON_FINITE)
    st_one.append(FC_OK)
    st_one.append(FC_ERR_NON_FINITE)
    var bone = pool_blend_flat(full, maes, st_one, 3, 2, POOL_MODE_MEAN, 0)
    if (
        bone.status == FC_OK and bone.chosen_candidate == 1 and not bone.is_combination
        and bone.values[0] == 3.0 and bone.weights[1] == 1.0
    ):
        passed += 1
        print("  ✅ a pool of one is reported as that candidate, not a one-member 'mean'")
    else:
        failed += 1
        print("  ❌ single-survivor blend wrong:", bone.chosen_candidate)

    # Ties break to the LOWEST index — deterministic, and the simpler candidate.
    var maes_t = List[Float64]()
    for _ in range(3):
        maes_t.append(0.5)
    var btie = pool_blend_flat(full, maes_t, ok3, 3, 2, POOL_MODE_SELECT, 0)
    if btie.chosen_candidate == 0:
        passed += 1
        print("  ✅ an exact MAE tie selects the lowest candidate index")
    else:
        failed += 1
        print("  ❌ tie break wrong:", btie.chosen_candidate)

    # ══ 5. Refusals are typed, and contradictions are refused rather than repaired ════
    var maes_bad = List[Float64]()
    maes_bad.append(0.5)
    maes_bad.append(-1.0)   # claims FC_OK below — a contradiction, not a datum
    maes_bad.append(0.125)
    var inf_full = full.copy()
    inf_full[0] = 1.0 / 0.0
    var st_none = List[Int]()
    for _ in range(3):
        st_none.append(FC_ERR_NON_FINITE)
    var short_maes = List[Float64]()
    short_maes.append(0.5)
    if (
        pool_blend_flat(full, maes_bad, ok3, 3, 2, POOL_MODE_SELECT, 0).status == FC_ERR_PARAM_RANGE
        and pool_blend_flat(inf_full, maes, ok3, 3, 2, POOL_MODE_SELECT, 0).status == FC_ERR_NON_FINITE
        and pool_blend_flat(full, maes, ok3, 3, 2, 9, 0).status == FC_ERR_METHOD
        and pool_blend_flat(full, maes, ok3, 3, 2, POOL_MODE_MEAN, 4).status == FC_ERR_PARAM_RANGE
        and pool_blend_flat(full, short_maes, ok3, 3, 2, POOL_MODE_SELECT, 0).status == FC_ERR_LENGTH_MISMATCH
        and pool_blend_flat(full, maes, ok3, 3, 0, POOL_MODE_SELECT, 0).status == FC_ERR_HORIZON
        and pool_blend_flat(full, maes, st_none, 3, 2, POOL_MODE_SELECT, 0).status == FC_ERR_ALL_UNDEFINED
    ):
        passed += 1
        print("  ✅ blend refusals: contradiction, non-finite, mode, top_k, shape, horizon, empty pool")
    else:
        failed += 1
        print("  ❌ a blend refusal was mistyped")

    var y10 = List[Float64]()
    for t in range(10):
        y10.append(Float64(t) + 1.0)
    var y9 = List[Float64]()
    for t in range(9):
        y9.append(Float64(t) + 1.0)
    var y20 = List[Float64]()
    var d20 = List[Float64]()
    for t in range(20):
        y20.append(Float64(t) + 1.0)
        d20.append(Float64(t) + 1.0)
    d20[18] = 0.0   # a zero deseasonalised value under a NONZERO raw one: no finite factor
    if (
        pool_holdout_report(List[Float64](), List[Float64](), 1, 4).status == FC_ERR_EMPTY_SERIES
        and pool_holdout_report(y10, y9, 1, 4).status == FC_ERR_LENGTH_MISMATCH
        and pool_holdout_report(y10, y10, 1, 6).status == FC_ERR_INSUFFICIENT_HISTORY
        and pool_holdout_report(y10, y10, 0, 3).status == FC_ERR_PERIOD
        and pool_holdout_report(y10, y10, 11, 3).status == FC_ERR_PERIOD
        and pool_holdout_report(y10, y10, 1, 0).status == FC_ERR_HORIZON
        and pool_holdout_report(y20, d20, 1, 4).status == FC_ERR_PARAM_RANGE
        and pool_holdout_forecast(y20, y20, 1, 4, 9, 0).status == FC_ERR_METHOD
        and pool_holdout_forecast(y20, y20, 1, 4, POOL_MODE_MEAN, 9).status == FC_ERR_PARAM_RANGE
        and not pool_holdout_forecast(y10, y9, 1, 4, POOL_MODE_SELECT, 0).has_forecast
        and pool_holdout_forecast(y10, y9, 1, 4, POOL_MODE_SELECT, 0).candidate_status[0] == FC_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ report refusals: empty, mismatch, short holdout, period, horizon, bad factor")
    else:
        failed += 1
        print("  ❌ a report refusal was mistyped")

    # ══ 6. The vocabularies are total and loud ════════════════════════════════════════
    if (
        pool_candidate_name(POOL_CAND_SES) == "ses"
        and pool_candidate_name(POOL_CAND_ETS_AAA) == "ets_aaa"
        and pool_candidate_name(POOL_CAND_NAIVE2) == "naive2"
        and pool_candidate_name(99) == "unknown_candidate"
        and pool_mode_name(POOL_MODE_SELECT) == "select"
        and pool_mode_name(POOL_MODE_INV_MAE) == "inverse_mae"
        and pool_mode_name(POOL_MODE_MEDIAN) == "median"
        and pool_mode_name(99) == "unknown_mode"
    ):
        passed += 1
        print("  ✅ candidate and mode names: total, loud on unknowns")
    else:
        failed += 1
        print("  ❌ a vocabulary hole")

    print("  [forecasting.pool] Passed:", passed, "Failed:", failed)
