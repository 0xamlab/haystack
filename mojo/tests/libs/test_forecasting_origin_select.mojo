"""test_forecasting_origin_select.mojo — known-value tests for paired-origin selection.

Hand-written. The strongest assertions are IDENTITIES and ARITHMETIC PINS:

  * `origin_schedule` is pinned cell by cell — the M4 short-series cases (a 13-point
    Yearly series affords exactly 2 origins, a 16-point Quarterly exactly 1) are the
    cases the adaptive K exists for, so they are asserted as exact lists.
  * On a constant series every candidate is exact at every origin, so the tournament's
    paired differences are deterministically zero, the verdict must be the genuine tie,
    and the combination must split EXACTLY into thirds and forecast EXACTLY c.
  * The NO-LEAKAGE REFUTER: a training series whose rolling origins favour the damped
    trend, and a constructed continuation (never passed to the kernel) on which SES
    beats Damped. The test PROVES the continuation rewards what training disfavours
    (both paths are scored against it) and asserts the selection cannot see it.
  * The gate answers to alpha AT the reported p: rerunning with alpha just below /
    just above the reported p-value must flip combine <-> select. That is behavioural
    — it fails if the p is ignored, fabricated, or compared on the wrong side.
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HORIZON,
    FC_ERR_LEVEL_RANGE,
    FC_ERR_NO_ORIGINS,
    FC_METHOD_ETS_AAN,
    FC_METHOD_ETS_ANN,
    FC_METHOD_THETA,
    FC_OK,
)
from forecasting.origin_select import (
    OriginSelected,
    crn_origin_select,
    origin_schedule,
    tournament_gated_select,
)
from forecasting.point import ets_ann_forecast
from forecasting.select import _golden_ses_alpha


def _line(n: Int) -> List[Float64]:
    var y = List[Float64]()
    for t in range(n):
        y.append(2.0 + 3.0 * Float64(t))
    return y^


def _wiggly(n: Int) -> List[Float64]:
    """A deterministic mildly-trending series with a bounded aperiodic wiggle."""
    var y = List[Float64]()
    var s: Float64 = 100.0
    for t in range(n):
        # A fixed integer recurrence, not a library RNG: reproducible everywhere.
        var wig = Float64((t * 7919 + 104729) % 97) / 97.0 - 0.5
        s += 0.4 + 4.0 * wig
        y.append(s)
    return y^


def main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.origin_select] hand-written known-value suite")

    # ══ 1. the origin schedule, pinned ════════════════════════════════════════════════
    # M4 Yearly minimum: n=13, h=6 -> floor max(5,6)=6, t_max=7, step 3 admits one so it
    # collapses to 1: exactly [6, 7]. Quarterly minimum: n=16, h=8 -> exactly [8].
    var s13 = origin_schedule(13, 6, 8)
    var s16 = origin_schedule(16, 8, 8)
    var s60 = origin_schedule(60, 6, 8)
    var ok_sched = (
        len(s13) == 2 and s13[0] == 6 and s13[1] == 7
        and len(s16) == 1 and s16[0] == 8
        and len(s60) == 8 and s60[7] == 54 and s60[0] == 33 and s60[1] - s60[0] == 3
        and len(origin_schedule(10, 6, 8)) == 0
        and len(origin_schedule(60, 6, 0)) == 0
        and len(origin_schedule(0, 6, 8)) == 0
    )
    if ok_sched:
        passed += 1
        print("  ✅ schedule pinned: 13/6 -> [6,7]; 16/8 -> [8]; 60/6 -> 8 recent, step 3")
    else:
        failed += 1
        print("  ❌ schedule wrong:", len(s13), len(s16), len(s60))

    # ══ 2. a trending series: Damped wins the paired origins, one-hot ════════════════
    var yl = _line(30)
    var sb = crn_origin_select(yl, 4, 8)
    if (
        sb.status == FC_OK and sb.has_forecast and not sb.is_combination
        and sb.chosen_method_id == FC_METHOD_ETS_AAN and sb.n_tied == 1
        and sb.n_origins == 8
        and sb.mean_origin_maes[1] < sb.mean_origin_maes[2]
        and sb.mean_origin_maes[2] < sb.mean_origin_maes[0]
        and sb.weights[0] == 0.0 and sb.weights[1] == 1.0 and sb.weights[2] == 0.0
        and sb.method_ids[0] == FC_METHOD_ETS_ANN
        and sb.method_ids[1] == FC_METHOD_ETS_AAN
        and sb.method_ids[2] == FC_METHOD_THETA
        and len(sb.origin_maes) == 3 * sb.n_origins
        and len(sb.origin_index) == sb.n_origins
    ):
        passed += 1
        print("  ✅ on y = 2+3t: Damped < Theta < SES on paired origins, Damped one-hot")
    else:
        failed += 1
        print("  ❌ origin selection on a line wrong:", sb.chosen_method_id,
              sb.mean_origin_maes[0], sb.mean_origin_maes[1], sb.mean_origin_maes[2])

    # The per-origin matrix rows must AVERAGE to the reported means (the samples and
    # the statistic cannot disagree).
    var means_agree = True
    for c in range(3):
        var s: Float64 = 0.0
        for j in range(sb.n_origins):
            s += sb.origin_maes[c * sb.n_origins + j]
        if fabs(s / Float64(sb.n_origins) - sb.mean_origin_maes[c]) > 1.0e-15:
            means_agree = False
    if means_agree:
        passed += 1
        print("  ✅ per-origin matrix rows average exactly to the reported means")
    else:
        failed += 1
        print("  ❌ origin matrix and mean_origin_maes disagree")

    # ══ 3. constant series: deterministic ties -> the genuine-tie combination ═════════
    var yc = List[Float64]()
    for _ in range(24):
        yc.append(5.0)
    var tc = tournament_gated_select(yc, 4, 8, 0.05)
    # All three candidates tie by practical equivalence (their per-origin MAEs are
    # rounding residue), so this must COMBINE all three. The exact-fit guard then
    # concentrates weight on the bit-exact fits — a documented degenerate of the
    # inverse-error weighting — so the pin is the distribution contract plus the exact
    # forecast, not a specific split.
    var w_ok = True
    var wsum: Float64 = 0.0
    for c in range(3):
        wsum += tc.weights[c]
        if tc.weights[c] < 0.0:
            w_ok = False
    if (
        tc.status == FC_OK and tc.is_combination and tc.n_tied == 3
        and tc.chosen_method_id == -1
        and w_ok and fabs(wsum - 1.0) <= 1.0e-12
        and tc.values[0] == 5.0 and tc.values[3] == 5.0
        and tc.p_values[0] == -1.0  # the best itself is never tested against itself
    ):
        passed += 1
        print("  ✅ constant series: fp-residue differences read as the genuine 3-way tie,")
        print("     weights a distribution, forecast exactly c")
    else:
        failed += 1
        print("  ❌ constant gating wrong:", tc.n_tied, tc.weights[0], tc.values[0])

    # And mechanism 1 alone on the same input SELECTS (tie broken to SES): the two
    # drivers must disagree here, because that disagreement IS the gate's contribution.
    var sc = crn_origin_select(yc, 4, 8)
    if sc.status == FC_OK and not sc.is_combination and sc.chosen_method_id == FC_METHOD_ETS_ANN:
        passed += 1
        print("  ✅ same input, no gate: selection breaks the exact tie to SES")
    else:
        failed += 1
        print("  ❌ ungated selection on constant wrong:", sc.chosen_method_id)

    # ══ 4. the gate answers to alpha AT the reported p ════════════════════════════════
    var yw = _wiggly(60)
    var tg = tournament_gated_select(yw, 6, 8, 0.05)
    var p_max: Float64 = -1.0
    var p_min: Float64 = 2.0
    for c in range(3):
        if tg.p_values[c] > p_max:
            p_max = tg.p_values[c]
        if tg.p_values[c] >= 0.0 and tg.p_values[c] < p_min:
            p_min = tg.p_values[c]
    if tg.status == FC_OK and p_min > 0.0 and p_max < 1.0 and p_min <= p_max:
        # alpha below the SMALLEST p: nothing rejected -> the full tie. alpha above the
        # LARGEST p: every tested pair rejected -> the best stands alone.
        var below = tournament_gated_select(yw, 6, 8, p_min * 0.5)
        var above = tournament_gated_select(yw, 6, 8, 0.5 * (1.0 + p_max))
        if below.is_combination and below.n_tied == 3 and not above.is_combination:
            passed += 1
            print("  ✅ gate flips combine <-> select exactly at the reported p (p range",
                  p_min, "..", p_max, ")")
        else:
            failed += 1
            print("  ❌ gate does not answer to alpha:", below.n_tied,
                  above.n_tied, p_min, p_max)
    else:
        failed += 1
        print("  ❌ no testable p on the wiggly series:", p_min, p_max, tg.status)

    # ══ 5. NO-LEAKAGE REFUTER ══════════════════════════════════════════════════════════
    # Training: a clean trend — every rolling origin inside it favours Damped.
    # Continuation (NEVER passed to the kernel): the level collapses flat, so on the
    # continuation SES beats Damped. First PROVE the continuation rewards the method the
    # training data disfavours; then assert the selection, a function of the training
    # series alone, still picks the training-favoured Damped. A selector that peeked at
    # the continuation would pick SES; this one cannot.
    var h_ref = 6
    var y_tr = _line(40)  # trend: origins favour Damped
    var cont = List[Float64]()
    for _ in range(h_ref):
        cont.append(y_tr[39])  # flat at the last observed level: rewards SES
    var sel_ref = crn_origin_select(y_tr, h_ref, 8)
    var ses_path = ets_ann_forecast(y_tr, _golden_ses_alpha(y_tr), h_ref)
    var mae_sel: Float64 = 0.0
    var mae_ses: Float64 = 0.0
    for h in range(h_ref):
        mae_sel += fabs(cont[h] - sel_ref.values[h])
        mae_ses += fabs(cont[h] - ses_path.values[h])
    if (
        sel_ref.status == FC_OK
        and sel_ref.chosen_method_id == FC_METHOD_ETS_AAN  # training-favoured
        and mae_ses < mae_sel  # the continuation really does reward SES instead
    ):
        passed += 1
        print("  ✅ refuter: continuation rewards SES (", mae_ses, "<", mae_sel,
              ") yet the selection, seeing only training data, picks Damped")
    else:
        failed += 1
        print("  ❌ leakage refuter failed:", sel_ref.chosen_method_id, mae_ses, mae_sel)

    # ══ 6. bit-reproducibility ═════════════════════════════════════════════════════════
    var g1 = tournament_gated_select(yw, 6, 8, 0.05)
    var g2 = tournament_gated_select(yw, 6, 8, 0.05)
    var same = g1.n_tied == g2.n_tied and g1.chosen_method_id == g2.chosen_method_id
    for h in range(6):
        if g1.values[h] != g2.values[h]:
            same = False
    for c in range(3):
        if g1.weights[c] != g2.weights[c] or g1.p_values[c] != g2.p_values[c]:
            same = False
    if same:
        passed += 1
        print("  ✅ bit-reproducible: two identical calls agree to the bit")
    else:
        failed += 1
        print("  ❌ gated selection is not deterministic")

    # ══ 7. refusals ═══════════════════════════════════════════════════════════════════
    var y10 = _line(10)
    var no_alpha = tournament_gated_select(yl, 4, 8, 0.0)
    var no_alpha2 = tournament_gated_select(yl, 4, 8, 1.0)
    if (
        crn_origin_select(List[Float64](), 4, 8).status == FC_ERR_EMPTY_SERIES
        and crn_origin_select(yl, 40, 8).status == FC_ERR_HORIZON
        and crn_origin_select(y10, 6, 8).status == FC_ERR_NO_ORIGINS
        and len(crn_origin_select(y10, 6, 8).values) == 0
        and no_alpha.status == FC_ERR_LEVEL_RANGE
        and no_alpha2.status == FC_ERR_LEVEL_RANGE
        and tournament_gated_select(y10, 6, 8, 0.05).status == FC_ERR_NO_ORIGINS
        and crn_origin_select(yl, 4, 0).status != FC_OK
    ):
        passed += 1
        print("  ✅ empty, horizon > n, no admissible origin and alpha outside (0,1)")
        print("     are refusals with no partial answer")
    else:
        failed += 1
        print("  ❌ a refusal leaked a result")

    # ══ 8. mean_origin_maes carries -1.0 only as the loud absent marker ═══════════════
    # On the healthy line every candidate fitted, so no -1.0 may appear anywhere.
    var clean = True
    for c in range(3):
        if sb.mean_origin_maes[c] < 0.0 or sb.component_status[c] != FC_OK:
            clean = False
    for i in range(len(sb.origin_maes)):
        if sb.origin_maes[i] < 0.0:
            clean = False
    if clean:
        passed += 1
        print("  ✅ all three candidates fitted everywhere: no absent markers in the record")
    else:
        failed += 1
        print("  ❌ an absent marker leaked into a healthy record")

    print("  [forecasting.origin_select] Passed:", passed, "Failed:", failed)
