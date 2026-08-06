"""test_evaluation_gates.mojo — hand-written tests for the regression and drift gates.

Hand-written, never machine-emitted.

**Every gate here is asserted to FAIL on a constructed regression.** A gate is a claim about
rejection, so a suite that only exercises acceptance proves the opposite of what it appears
to. Each failing case below is paired with the passing case that differs from it by one number.

Hand-computable reference values
--------------------------------
metric_gate, lower-is-better, tolerance 0.01:
  (0.09 -> 0.20)   delta 0.11, margin 0.01 - 0.11 = -0.10   FAIL
  (0.09 -> 0.095)  delta 0.005, margin 0.005                PASS
  (0.20 -> 0.09)   an improvement, margin 0.01 + 0.11 = 0.12  PASS
  (0.25 -> 0.50) with tolerance 0.25: delta is EXACTLY 0.25 in binary and equals the
                 tolerance, so this is the documented inclusive boundary  PASS
  (0.09 -> 0.10) with tolerance 0.01: NOT a tie. fl(0.10) - fl(0.09) is
                 0.010000000000000009, five ulps above fl(0.01), so the movement genuinely
                 exceeds the allowance on the values as represented  FAIL, margin -8.67e-18
metric_gate, higher-is-better, tolerance 0.05:
  (0.90 -> 0.80)   wrong-way movement 0.10 > 0.05            FAIL
  (0.90 -> 0.86)   wrong-way movement 0.04 <= 0.05           PASS

metric_regression_gate_flat on Brier, tolerance 0.01:
  baseline  p [0.1, 0.9] y [0, 1] -> (0.01 + 0.01) / 2 = 0.01
  candidate p [0.6, 0.4] y [0, 1] -> (0.36 + 0.36) / 2 = 0.36
  delta 0.35, margin 0.01 - 0.35 = -0.34                     FAIL
The same two datasets gated on ACCURACY instead: baseline 1.0, candidate 0.0, and accuracy is
higher-is-better, so the wrong-way movement is +1.0 and it fails for the opposite sign of
delta. That pair is what shows the direction comes from the metric and not from the caller.

psi_drift_gate_flat, 2 equal-width bins:
  reference [0.1, 0.2, 0.6, 0.7] -> counts [2, 2] -> proportions [0.5, 0.5]
  candidate [0.1, 0.6, 0.7, 0.8] -> counts [1, 3] -> proportions [0.25, 0.75]
  PSI = (0.25-0.5) ln(0.25/0.5) + (0.75-0.5) ln(0.75/0.5)
      = 0.25 * ln 2 + 0.25 * ln 1.5 = 0.17328679513998632 + 0.10136627702704110
      = 0.2746530721670274                    drifted at threshold 0.25, not at 0.30
  candidate [0.6, 0.7, 0.8, 0.9] -> counts [0, 4] -> proportions [0.0, 1.0]
  Bin 0's term is infinite: the reference populated it and the candidate does not. The frozen
  `population_stability_index` returns 0.0 there, so a naive sum UNDERSTATES the drift exactly
  when it is most extreme. The lower bound is the remaining term,
  (1.0 - 0.5) ln(1.0/0.5) = 0.5 ln 2 = 0.34657359027997264, which is already past a 0.25
  threshold — so the verdict is DECIDED (drifted) even though the index itself is absent. At a
  threshold of 0.90 the same lower bound decides nothing and `decided` is False.

The PSI and any log-derived tolerance is 1e-8 relative, which is the measured accuracy of the
frozen `std.math.log` on this toolchain (`log(0.7)` is 2.5e-9 relative from correctly
rounded), not slack for the aggregation. See test_evaluation_scores.mojo.
"""
from std.math import abs as fabs

from evaluation.contract import (
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_DBL_EPSILON,
    EVAL_ERR_BIN_COUNT,
    EVAL_ERR_COUNT,
    EVAL_ERR_EMPTY,
    EVAL_ERR_LABEL_NOT_BINARY,
    EVAL_ERR_INCOMPARABLE_BINNING,
    EVAL_ERR_NON_FINITE,
    EVAL_ERR_PROB_RANGE,
    EVAL_ERR_PSI_INCOMPLETE,
    EVAL_ERR_THRESHOLD,
    EVAL_ERR_TOLERANCE,
    EVAL_ERR_UNKNOWN_METRIC,
    EVAL_METRIC_ACCURACY,
    EVAL_METRIC_BASE_RATE,
    EVAL_METRIC_BRIER,
    EVAL_METRIC_COUNT,
    EVAL_METRIC_ECE,
    EVAL_OK,
    eval_finite,
    eval_status_name,
)
from evaluation.gates import (
    metric_gate,
    metric_regression_gate_flat,
    psi_drift_gate_flat,
)


def close(got: Float64, want: Float64) -> Bool:
    return fabs(got - want) <= 8.0 * EVAL_DBL_EPSILON * fabs(want)


def close_log(got: Float64, want: Float64) -> Bool:
    """1e-8 relative — the frozen `std.math.log`'s measured accuracy, not slack."""
    return fabs(got - want) <= 1e-8 * fabs(want)


def four(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


def two(a: Float64, b: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    return out^


def main() raises:
    var failures = 0
    var checks = 0
    var nan_v = 0.0 / 0.0
    var inf_v = 1.0 / 0.0

    # ── THE GATE FAILS. This is the assertion the whole module exists for ─────
    var bad = metric_gate(0.09, 0.20, 0.01, False)
    checks += 1
    if not bad.decided:
        print("  ❌ a well-formed comparison must reach a verdict")
        failures += 1
    checks += 1
    if bad.passed:
        print("  ❌ a Brier score moving 0.09 -> 0.20 against a 0.01 tolerance MUST FAIL;")
        print("     a gate that has never been shown to fail is decoration")
        failures += 1
    checks += 1
    if not close(bad.delta, 0.11):
        print("  ❌ delta", bad.delta, "want 0.11")
        failures += 1
    checks += 1
    if not close(bad.margin, -0.1):
        print("  ❌ margin", bad.margin, "want 0.01 - 0.11 = -0.10")
        failures += 1
    checks += 1
    if bad.higher_is_better:
        print("  ❌ the direction was not carried through")
        failures += 1

    # ── and passes when it should, one number away ────────────────────────────
    var good = metric_gate(0.09, 0.095, 0.01, False)
    checks += 1
    if not good.decided or not good.passed:
        print("  ❌ 0.09 -> 0.095 inside a 0.01 tolerance must pass")
        failures += 1
    checks += 1
    if not close(good.margin, 0.005):
        print("  ❌ margin", good.margin, "want 0.005")
        failures += 1
    var better = metric_gate(0.20, 0.09, 0.01, False)
    checks += 1
    if not better.passed or not close(better.margin, 0.12):
        print("  ❌ an improvement must pass with margin 0.01 + 0.11 = 0.12:", better.margin)
        failures += 1

    # ── the inclusive boundary, on an EXACT binary tie ───────────────────────
    var tie = metric_gate(0.25, 0.5, 0.25, False)
    checks += 1
    if tie.delta != 0.25:
        print("  ❌ 0.5 - 0.25 must be exactly 0.25:", tie.delta)
        failures += 1
    checks += 1
    if not tie.passed or tie.margin != 0.0:
        print("  ❌ an exact tie at the tolerance passes with a zero margin:",
              tie.passed, tie.margin)
        failures += 1

    # ── the decimal near-tie fails, and `margin` says by how little ──────────
    var near = metric_gate(0.09, 0.10, 0.01, False)
    checks += 1
    if near.passed:
        print("  ❌ fl(0.10) - fl(0.09) exceeds fl(0.01); the comparison is exact on the")
        print("     values as represented and this must fail")
        failures += 1
    checks += 1
    if near.margin >= 0.0 or fabs(near.margin) > 1e-17:
        print("  ❌ the near-tie margin", near.margin, "should be a tiny negative number")
        print("     (measured -8.673617379884035e-18), so a build log explains itself")
        failures += 1

    # ── higher-is-better inverts the sign that counts as a regression ─────────
    var acc_bad = metric_gate(0.90, 0.80, 0.05, True)
    checks += 1
    if acc_bad.passed:
        print("  ❌ accuracy 0.90 -> 0.80 against a 0.05 tolerance MUST FAIL")
        failures += 1
    checks += 1
    if not close(acc_bad.margin, -0.05):
        print("  ❌ margin", acc_bad.margin, "want 0.05 - 0.10 = -0.05")
        failures += 1
    var acc_ok = metric_gate(0.90, 0.86, 0.05, True)
    checks += 1
    if not acc_ok.passed:
        print("  ❌ accuracy 0.90 -> 0.86 inside a 0.05 tolerance must pass")
        failures += 1
    # An IMPROVEMENT under higher-is-better must not be read as a regression.
    var acc_up = metric_gate(0.90, 0.99, 0.0, True)
    checks += 1
    if not acc_up.passed:
        print("  ❌ an improvement must pass even at a zero tolerance")
        failures += 1

    # ── a zero tolerance is a real setting, and it bites ─────────────────────
    var zero_ok = metric_gate(0.5, 0.5, 0.0, False)
    checks += 1
    if not zero_ok.passed or zero_ok.margin != 0.0:
        print("  ❌ no movement at all passes a zero tolerance")
        failures += 1
    var zero_bad = metric_gate(0.5, 0.5000001, 0.0, False)
    checks += 1
    if zero_bad.passed:
        print("  ❌ any wrong-way movement fails a zero tolerance")
        failures += 1

    # ── refusals: undecided, never a default verdict ─────────────────────────
    checks += 1
    var nan_gate = metric_gate(nan_v, 0.5, 0.01, False)
    if nan_gate.decided or nan_gate.status != EVAL_ERR_NON_FINITE:
        print("  ❌ a NaN baseline must be undecided, not passed:",
              eval_status_name(nan_gate.status), nan_gate.decided)
        failures += 1
    checks += 1
    if nan_gate.passed:
        print("  ❌ an undecided gate must not report `passed`; a NaN threshold makes every")
        print("     comparison False and a naive gate reports success having checked nothing")
        failures += 1
    checks += 1
    if metric_gate(0.5, inf_v, 0.01, False).status != EVAL_ERR_NON_FINITE:
        print("  ❌ an infinite candidate must refuse")
        failures += 1
    checks += 1
    if metric_gate(0.5, 0.6, -0.01, False).status != EVAL_ERR_TOLERANCE:
        print("  ❌ a negative tolerance must refuse, not be clamped to zero — clamping")
        print("     would silently build a stricter gate than the caller asked for")
        failures += 1
    checks += 1
    if metric_gate(0.5, 0.6, nan_v, False).status != EVAL_ERR_TOLERANCE:
        print("  ❌ a NaN tolerance must refuse")
        failures += 1

    # ── FINITE inputs whose DIFFERENCE is not representable ──────────────────
    # This is not a hypothetical. Before the guard in `metric_gate`, all three of these
    # returned `decided == True` with `passed == True` and a raw infinity in `delta` and/or
    # `margin` — i.e. the largest regression Float64 can express PASSED a zero-tolerance
    # gate, because `slop = eps * inf` is `inf` and `wrong_way <= tolerance + inf` holds for
    # every tolerance. Both failure modes are asserted: no verdict, and no non-finite field.
    var dbl_max = 1.7976931348623157e308
    checks += 1
    if not eval_finite(dbl_max) or not eval_finite(-dbl_max):
        print("  ❌ DBL_MAX must itself be finite, or this case tests nothing")
        failures += 1
    var over_lo = metric_gate(-dbl_max, dbl_max, 0.0, False)
    checks += 1
    if over_lo.decided or over_lo.passed:
        print("  ❌ (-DBL_MAX -> +DBL_MAX) at tolerance 0.0 is the largest regression there")
        print("     is; it must NOT be decided and must NOT pass:",
              over_lo.decided, over_lo.passed)
        failures += 1
    checks += 1
    if over_lo.status != EVAL_ERR_NON_FINITE:
        print("  ❌ an unrepresentable difference must be typed:",
              eval_status_name(over_lo.status))
        failures += 1
    checks += 1
    if not eval_finite(over_lo.delta) or not eval_finite(over_lo.margin):
        print("  ❌ delta/margin are returned fields and must stay representable:",
              over_lo.delta, over_lo.margin)
        failures += 1
    var over_hi = metric_gate(dbl_max, -dbl_max, 1.0, True)
    checks += 1
    if over_hi.decided or over_hi.passed or over_hi.status != EVAL_ERR_NON_FINITE:
        print("  ❌ the same overflow in the higher-is-better direction must also refuse:",
              over_hi.decided, over_hi.passed, eval_status_name(over_hi.status))
        failures += 1
    checks += 1
    if not eval_finite(over_hi.delta) or not eval_finite(over_hi.margin):
        print("  ❌ over_hi left a non-finite in a result field")
        failures += 1
    # A FINITE delta whose MARGIN still overflows: delta is DBL_MAX, wrong_way is -DBL_MAX,
    # so `abs_tolerance - wrong_way` is +inf. The margin is guarded on its own value.
    var over_margin = metric_gate(0.0, dbl_max, dbl_max, True)
    checks += 1
    if over_margin.decided or over_margin.status != EVAL_ERR_NON_FINITE:
        print("  ❌ a finite delta with an unrepresentable margin must refuse:",
              over_margin.delta, over_margin.margin,
              eval_status_name(over_margin.status))
        failures += 1
    checks += 1
    if not eval_finite(over_margin.margin):
        print("  ❌ margin must be representable on the refusal path too:",
              over_margin.margin)
        failures += 1
    # And the overflow refusal propagates through the dataset-level gate rather than
    # producing a verdict from one comparable side and one incomparable one.
    checks += 1
    var over_reg = metric_gate(-dbl_max, dbl_max, 0.0, True)
    if over_reg.decided:
        print("  ❌ the higher-is-better overflow must refuse too")
        failures += 1
    # Values large but NOT overflowing must still be decided: the guard must not have
    # widened into a refusal of ordinary large numbers.
    var big_ok = metric_gate(0.0, 1.0e308, 0.0, False)
    checks += 1
    if not big_ok.decided or big_ok.passed:
        print("  ❌ 0 -> 1e308 is representable and is a regression: decide it and fail it,",
              big_ok.decided, big_ok.passed)
        failures += 1
    checks += 1
    if not eval_finite(big_ok.delta) or not eval_finite(big_ok.margin):
        print("  ❌ a representable large delta must be reported, not suppressed")
        failures += 1

    checks += 1
    if metric_gate(0.5, 0.6, inf_v, False).status != EVAL_ERR_TOLERANCE:
        print("  ❌ an infinite tolerance is not a threshold")
        failures += 1

    # ── the dataset-level gate: computes both sides, fails on the regression ──
    var base_p = two(0.1, 0.9)
    var base_y = two(0.0, 1.0)
    var cand_p = two(0.6, 0.4)
    var cand_y = two(0.0, 1.0)
    var reg = metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 4,
        EVAL_BIN_EQUAL_WIDTH, 0.01
    )
    checks += 1
    if reg.status != EVAL_OK or not reg.decided:
        print("  ❌ the dataset gate refused a valid comparison:", eval_status_name(reg.status))
        failures += 1
    checks += 1
    if not close(reg.baseline, 0.01):
        print("  ❌ baseline Brier", reg.baseline, "want (0.01 + 0.01)/2 = 0.01")
        failures += 1
    checks += 1
    if not close(reg.candidate, 0.36):
        print("  ❌ candidate Brier", reg.candidate, "want (0.36 + 0.36)/2 = 0.36")
        failures += 1
    checks += 1
    if reg.passed:
        print("  ❌ a Brier score of 0.36 against a baseline of 0.01 MUST FAIL")
        failures += 1
    checks += 1
    if not close(reg.margin, -0.34):
        print("  ❌ margin", reg.margin, "want 0.01 - 0.35 = -0.34")
        failures += 1
    checks += 1
    if reg.metric_id != EVAL_METRIC_BRIER or reg.higher_is_better:
        print("  ❌ the gate must report the metric it used and its direction")
        failures += 1
    # Comparing a dataset against itself is the identity case: zero movement, passes.
    var same = metric_regression_gate_flat(
        base_p, base_y, 2, base_p, base_y, 2, EVAL_METRIC_BRIER, 4,
        EVAL_BIN_EQUAL_WIDTH, 0.0
    )
    checks += 1
    if not same.passed or same.delta != 0.0:
        print("  ❌ a dataset gated against itself must pass with a zero delta:", same.delta)
        failures += 1

    # ── the DIRECTION comes from the metric, demonstrated on the same data ────
    # Accuracy at 0.5: baseline [0.1, 0.9] against [0, 1] is 2/2 = 1.0; candidate
    # [0.6, 0.4] against [0, 1] is 0/2 = 0.0. Accuracy is higher-is-better, so this
    # regression has delta -1.0 while the Brier regression above had delta +0.35. Both fail.
    var acc_reg = metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_ACCURACY, 4,
        EVAL_BIN_EQUAL_WIDTH, 0.01
    )
    checks += 1
    if acc_reg.baseline != 1.0 or acc_reg.candidate != 0.0:
        print("  ❌ accuracy sides", acc_reg.baseline, acc_reg.candidate, "want 1.0, 0.0")
        failures += 1
    checks += 1
    if acc_reg.passed:
        print("  ❌ accuracy 1.0 -> 0.0 MUST FAIL")
        failures += 1
    checks += 1
    if not acc_reg.higher_is_better or acc_reg.delta != -1.0:
        print("  ❌ accuracy must be gated as higher-is-better with delta -1.0:",
              acc_reg.higher_is_better, acc_reg.delta)
        failures += 1
    # And the two gates disagree about the SIGN of a regression, which is the point.
    checks += 1
    if (reg.delta > 0.0) == (acc_reg.delta > 0.0):
        print("  ❌ the two metrics should regress with opposite signs; if they agree, the")
        print("     direction is not coming from the metric")
        failures += 1

    # ── an ECE gate binned identically on both sides is comparable by design ──
    var ece_gate = metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_ECE, 4,
        EVAL_BIN_EQUAL_WIDTH, 0.05
    )
    checks += 1
    if ece_gate.status != EVAL_OK or ece_gate.bins_used != 4:
        print("  ❌ the ECE gate must report the single binning it applied to both sides:",
              eval_status_name(ece_gate.status), ece_gate.bins_used)
        failures += 1
    checks += 1
    if ece_gate.bin_policy != EVAL_BIN_EQUAL_WIDTH:
        print("  ❌ the ECE gate must report its policy")
        failures += 1

    # ── refusals on the dataset gate ─────────────────────────────────────────
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_BASE_RATE, 4, 0, 0.01
    ).status != EVAL_ERR_UNKNOWN_METRIC:
        print("  ❌ the base rate is a property of the labels; 'the base rate regressed' is")
        print("     not a statement about a model and must be refused")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_COUNT, 4, 0, 0.01
    ).status != EVAL_ERR_UNKNOWN_METRIC:
        print("  ❌ an unknown metric must refuse")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 25, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 4, 0, 0.01
    ).status != EVAL_ERR_COUNT:
        print("  ❌ a bad baseline count must refuse the whole gate")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 25, EVAL_METRIC_BRIER, 4, 0, 0.01
    ).status != EVAL_ERR_COUNT:
        print("  ❌ a bad candidate count must refuse the whole gate — a verdict from one")
        print("     valid side and one invalid side is worse than no verdict")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_p, 2, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 4, 0, 0.01
    ).status != EVAL_ERR_LABEL_NOT_BINARY:
        print("  ❌ soft labels on either side must refuse")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 0, 0, 0.01
    ).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ h=0 must refuse")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 4, 0, -1.0
    ).status != EVAL_ERR_TOLERANCE:
        print("  ❌ a negative tolerance must refuse at the dataset level too")
        failures += 1
    checks += 1
    if metric_regression_gate_flat(
        base_p, base_y, 0, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 4, 0, 0.01
    ).status != EVAL_ERR_EMPTY:
        print("  ❌ an empty baseline has no metric to compare")
        failures += 1

    # ── PSI: the known value, and the threshold decides both ways ─────────────
    var refs = four(0.1, 0.2, 0.6, 0.7)
    var cand = four(0.1, 0.6, 0.7, 0.8)
    var psi = psi_drift_gate_flat(refs, 4, cand, 4, 2, 0.25)
    checks += 1
    if psi.status != EVAL_OK or not psi.present:
        print("  ❌ a complete PSI was not reported present:", eval_status_name(psi.status))
        failures += 1
    checks += 1
    if not close_log(psi.psi, 0.2746530721670274):
        print("  ❌ PSI", psi.psi, "want 0.25*ln2 + 0.25*ln1.5 = 0.2746530721670274")
        failures += 1
    checks += 1
    if psi.bins_matched != 2 or psi.bins_unmatched != 0:
        print("  ❌ both bins are populated on both sides:", psi.bins_matched,
              psi.bins_unmatched)
        failures += 1
    checks += 1
    if not psi.decided or not psi.drifted:
        print("  ❌ 0.2747 exceeds a 0.25 threshold — the drift gate MUST FIRE")
        failures += 1
    var psi_ok = psi_drift_gate_flat(refs, 4, cand, 4, 2, 0.30)
    checks += 1
    if not psi_ok.decided or psi_ok.drifted:
        print("  ❌ 0.2747 is below a 0.30 threshold and must not fire")
        failures += 1
    checks += 1
    if psi_ok.psi != psi.psi:
        print("  ❌ the threshold must not change the index")
        failures += 1
    checks += 1
    if psi.psi_lower_bound != psi.psi:
        print("  ❌ a complete index is its own lower bound")
        failures += 1

    # ── PSI with an unmatched bin: absent index, decisive lower bound ─────────
    var gone = four(0.6, 0.7, 0.8, 0.9)
    var inc = psi_drift_gate_flat(refs, 4, gone, 4, 2, 0.25)
    checks += 1
    if inc.status != EVAL_ERR_PSI_INCOMPLETE:
        print("  ❌ an unmatched bin must not be reported under a success status:",
              eval_status_name(inc.status))
        failures += 1
    checks += 1
    if inc.present or inc.psi != 0.0:
        print("  ❌ an incomplete index must be ABSENT with a representable 0.0 in the slot,")
        print("     not a number a caller cannot distinguish from a measurement")
        failures += 1
    checks += 1
    if not close_log(inc.psi_lower_bound, 0.34657359027997264):
        print("  ❌ lower bound", inc.psi_lower_bound, "want 0.5*ln2 = 0.34657359027997264")
        failures += 1
    checks += 1
    if inc.bins_unmatched != 1 or inc.bins_matched != 1:
        print("  ❌ bin accounting", inc.bins_matched, inc.bins_unmatched, "want 1, 1")
        failures += 1
    checks += 1
    if not inc.decided or not inc.drifted:
        print("  ❌ a lower bound of 0.3466 already exceeds 0.25, so the verdict does NOT")
        print("     depend on the missing terms and must be decided")
        failures += 1
    # The same data against a threshold the lower bound cannot reach decides nothing.
    var undecided = psi_drift_gate_flat(refs, 4, gone, 4, 2, 0.90)
    checks += 1
    if undecided.decided or undecided.drifted:
        print("  ❌ a lower bound of 0.3466 says nothing about a 0.90 threshold; reporting")
        print("     'no drift' here would be an answer the data does not support")
        failures += 1
    checks += 1
    if not close_log(undecided.psi_lower_bound, 0.34657359027997264):
        print("  ❌ the lower bound must be reported even when nothing is decided")
        failures += 1
    # A naive sum over the frozen per-bin term would report 0.3466 as THE index and, at a
    # 0.40 threshold, conclude 'no drift' for a candidate that abandoned a whole bin.
    checks += 1
    var naive_trap = psi_drift_gate_flat(refs, 4, gone, 4, 2, 0.40)
    if naive_trap.present or naive_trap.decided or naive_trap.drifted:
        print("  ❌ this is the case a naive PSI gets wrong: the summed terms (0.3466) sit")
        print("     below a 0.40 threshold while the true index is infinite. It must be")
        print("     undecided, not 'no drift'.")
        failures += 1

    # ── identical distributions: PSI exactly zero, nothing drifted ────────────
    var identical = psi_drift_gate_flat(refs, 4, refs, 4, 2, 0.1)
    checks += 1
    if identical.status != EVAL_OK or identical.psi != 0.0 or identical.drifted:
        print("  ❌ identical distributions have PSI exactly 0:", identical.psi)
        failures += 1
    checks += 1
    if not identical.present or not identical.decided:
        print("  ❌ a PSI of zero is a real answer and must be present and decided")
        failures += 1

    # ── a bin neither side occupies is NOT an unmatched bin ──────────────────
    # Both lists sit in bin 1 of 10, so bins 0 and 2..9 are empty on BOTH sides. There is
    # nothing there to compare in either direction, so counting them as unmatched would
    # report the index as incomplete for every empty region of the score space.
    var narrow = two(0.15, 0.15)
    var narrow2 = two(0.15, 0.15)
    var sparse = psi_drift_gate_flat(narrow, 2, narrow2, 2, 10, 0.1)
    checks += 1
    if sparse.status != EVAL_OK or not sparse.present:
        print("  ❌ mutually empty bins must not make the index incomplete:",
              eval_status_name(sparse.status))
        failures += 1
    checks += 1
    if sparse.bins_matched != 1 or sparse.bins_unmatched != 0:
        print("  ❌ bin accounting over 10 bins", sparse.bins_matched, sparse.bins_unmatched,
              "want 1, 0")
        failures += 1

    # ── PSI refusals ─────────────────────────────────────────────────────────
    checks += 1
    if psi_drift_gate_flat(refs, 25, cand, 4, 2, 0.25).status != EVAL_ERR_COUNT:
        print("  ❌ the reference count guard")
        failures += 1
    checks += 1
    if psi_drift_gate_flat(refs, 4, cand, 25, 2, 0.25).status != EVAL_ERR_COUNT:
        print("  ❌ the candidate count guard")
        failures += 1
    checks += 1
    if psi_drift_gate_flat(refs, 0, cand, 4, 2, 0.25).status != EVAL_ERR_EMPTY:
        print("  ❌ an empty reference distribution has no index")
        failures += 1
    checks += 1
    if psi_drift_gate_flat(refs, 4, cand, 4, 0, 0.25).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ h=0 must refuse")
        failures += 1
    checks += 1
    if psi_drift_gate_flat(refs, 4, cand, 4, 2, -0.1).status != EVAL_ERR_THRESHOLD:
        print("  ❌ a negative threshold must refuse")
        failures += 1
    checks += 1
    if psi_drift_gate_flat(refs, 4, cand, 4, 2, nan_v).status != EVAL_ERR_THRESHOLD:
        print("  ❌ a NaN threshold must refuse: every `>` against it is False and the gate")
        print("     would report 'no drift' having compared nothing")
        failures += 1
    var out_of_range = four(0.1, 0.2, 1.5, 0.7)
    checks += 1
    if psi_drift_gate_flat(out_of_range, 4, cand, 4, 2, 0.25).status != EVAL_ERR_PROB_RANGE:
        print("  ❌ a score outside [0, 1] must refuse")
        failures += 1
    var refused_psi = psi_drift_gate_flat(refs, 25, cand, 4, 2, 0.25)
    checks += 1
    if refused_psi.present or refused_psi.decided or refused_psi.drifted:
        print("  ❌ a refused drift gate must carry no verdict")
        failures += 1

    # ── the invariant behind EVAL_ERR_INCOMPARABLE_BINNING being unreachable ──
    # `metric_regression_gate_flat` cross-checks that the two sides report the SAME
    # `bins_used` and `bin_policy` and returns 378 if they do not. It takes one bin count and
    # one policy and hands both to each side, so that check cannot currently fire — it is a
    # certificate verifying a condition it also enforces. Kept, and its deadness asserted
    # here rather than assumed, because the docs say a caller cannot provoke it.
    # Six samples spread across [0, 1] so that both binning policies produce several
    # occupied bins at every h in the sweep.
    var pv = List[Float64]()
    var yv = List[Float64]()
    pv.append(0.05)
    pv.append(0.2)
    pv.append(0.45)
    pv.append(0.55)
    pv.append(0.8)
    pv.append(0.95)
    yv.append(0.0)
    yv.append(0.0)
    yv.append(1.0)
    yv.append(0.0)
    yv.append(1.0)
    yv.append(1.0)
    var prov_trials = 0
    for m in range(5):
        if m == EVAL_METRIC_BASE_RATE:
            continue  # refused as a gate subject by design, tested above
        for hk in range(1, 5):
            for pol in range(2):
                prov_trials += 1
                var gv = metric_regression_gate_flat(
                    pv, yv, 6, pv, yv, 6, m, hk, pol, 0.01
                )
                if gv.status == EVAL_ERR_INCOMPARABLE_BINNING:
                    checks += 1
                    print("  ❌ one bin count and one policy applied to both sides still",
                          "produced incomparable binnings: metric", m, "h", hk,
                          "policy", pol, "— 378 is reachable and the docs are wrong")
                    failures += 1
                    continue
                if not gv.decided:
                    checks += 1
                    print("  ❌ a valid same-data gate was undecided: metric", m, "h", hk,
                          "policy", pol, eval_status_name(gv.status))
                    failures += 1
                    continue
                # Same data on both sides: zero movement, so it must PASS at tolerance 0.01,
                # and the reported provenance must be the arguments that were supplied.
                if gv.delta != 0.0 or not gv.passed:
                    checks += 1
                    print("  ❌ identical datasets must gate to a zero delta and pass:",
                          gv.delta, gv.passed, "metric", m)
                    failures += 1
                    continue
                if m == EVAL_METRIC_ECE:
                    if gv.bins_used != hk or gv.bin_policy != pol:
                        checks += 1
                        print("  ❌ an ECE gate must report the binning it used:",
                              gv.bins_used, gv.bin_policy, "want", hk, pol)
                        failures += 1
    checks += 1
    if prov_trials != 32:
        print("  ❌ the provenance sweep covered", prov_trials, "cases, expected 32")
        failures += 1

    for _ in range(checks - failures):
        print("  ✅ evaluation.gates check")
    print("  [evaluation.gates] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_evaluation_gates failed")
