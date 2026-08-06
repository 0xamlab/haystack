"""test_evaluation_scores.mojo — hand-written known-value tests for the metrics.

Hand-written, never machine-emitted. Every reference number below is derived by hand from the
definition and cross-checked against an independent Python transcription; none of it is
"the function agrees with itself".

DATASET A — p [0.1, 0.3, 0.5, 0.7, 0.9], y [0, 0, 1, 1, 1]
-----------------------------------------------------------
Brier      ((0.1)^2 + (0.3)^2 + (0.5)^2 + (0.3)^2 + (0.1)^2) / 5
           = (0.01 + 0.09 + 0.25 + 0.09 + 0.01) / 5 = 0.45 / 5 = 0.09
base rate  3/5 = 0.6         uncertainty  0.6 * 0.4 = 0.24
accuracy   thresholded at 0.5 -> [0,0,1,1,1] == y, so 5/5 = 1.0

h = 5 equal width puts one sample per bin, so within-bin variance is zero and Murphy's
decomposition closes EXACTLY:
  reliability  (1/5) * sum (p_b - y_b)^2 = 0.45 / 5 = 0.09
  resolution   (1/5) * ((0.6)^2 + (0.6)^2 + (0.4)^2 + (0.4)^2 + (0.4)^2)
               = (0.36 + 0.36 + 0.16 + 0.16 + 0.16) / 5 = 1.20 / 5 = 0.24
  0.09 - 0.24 + 0.24 = 0.09 = Brier, so residual = 0.0
  ECE = (0.1 + 0.3 + 0.5 + 0.3 + 0.1) / 5 = 1.3 / 5 = 0.26      MCE = 0.5

h = 1 puts everything in one bin, so the decomposition does NOT close and by a
hand-computable amount:
  mean prediction 2.5/5 = 0.5, mean label 0.6
  reliability  (0.5 - 0.6)^2 = 0.01     resolution  0.0     uncertainty  0.24
  0.01 - 0.0 + 0.24 = 0.25, while Brier is 0.09, so residual = 0.09 - 0.25 = -0.16
That number is the measure of how much the binning is smoothing the decomposition, and it is
the reason `residual` is a returned field rather than an implicit assumption.

log-loss   -(ln 0.9 + ln 0.7 + ln 0.5 + ln 0.7 + ln 0.9) / 5
           = (0.10536051565782630 * 2 + 0.35667494393873245 * 2 + 0.69314718055994531) / 5
           = 1.61721809975306281 / 5 = 0.32344361995061256

THE LOG-LOSS TOLERANCE IS THE FROZEN KERNEL'S, NOT SLACK FOR THE AGGREGATION.
`loss_functions.binary_cross_entropy` calls `std.math.log`, whose accuracy on this toolchain
was measured directly: `log(0.9)` returns -0.10536051567811136 against the correctly rounded
-0.10536051565782630 (2.0e-11 absolute, 1.9e-10 relative) and `log(0.7)` returns
-0.35667494482530565 against -0.35667494393873245 (8.9e-10 absolute, 2.5e-9 relative). The
frozen kernel is not modified and its `log` is not replaced, so the assertion below is
`|got - want| <= 1e-8 * |want|` — an order of magnitude above the measured 1.1e-9 error of
this particular sum, and stated so nobody reads it as a general-purpose fudge.

DATASET B — p [0.2, 0.4, 0.6, 0.8], y [0, 1, 0, 1]   (the binning-dependence case)
----------------------------------------------------------------------------------
Brier 0.2. ECE at h=2 is 0.2; ECE at h=4 is 0.4. Same predictions, same labels, a factor of
two from the bin count alone — which is why every result carrying an `ece` also carries
`bins_used` and `bin_policy`.
  h=2: bin0 {0.2, 0.4} conf 0.3 freq 0.5 gap 0.2 weight 2/4
       bin1 {0.6, 0.8} conf 0.7 freq 0.5 gap 0.2 weight 2/4   -> 0.2
  h=4: gaps 0.2, 0.6, 0.6, 0.2 each weight 1/4                -> 0.4, MCE 0.6

DATASET C — p [0.0, 1.0], y [1, 0]   (both predictions saturated and wrong)
--------------------------------------------------------------------------
Brier = ((0 - 1)^2 + (1 - 0)^2) / 2 = 1.0, the maximum a Brier score can take.
log-loss is INFINITE mathematically. The frozen kernel clamps to 1e-7, so the reported value
is -ln(1e-7) = 16.11809565095832 and `clamped_count` is 2. The clamp is the answer here; the
count is what makes it visible.

DATASET D — p [0.0, 1.0], y [0, 1]   (a perfect classifier)
-----------------------------------------------------------
Brier = 0.0 exactly. log-loss is NOT zero: it is -ln(1 - 1e-7) = 1.00000005e-07 per sample,
entirely an artefact of the clamp, with `clamped_count` 2 saying so. A caller comparing this
to a model that never saturates is comparing a censored number to an uncensored one.
"""
from std.math import abs as fabs

from evaluation.contract import (
    EVAL_BIN_EQUAL_COUNT,
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_DBL_EPSILON,
    EVAL_ERR_BIN_COUNT,
    EVAL_ERR_COUNT,
    EVAL_ERR_EMPTY,
    EVAL_ERR_LABEL_NOT_BINARY,
    EVAL_ERR_PROB_RANGE,
    EVAL_ERR_UNKNOWN_METRIC,
    EVAL_LOG_LOSS_EPS,
    EVAL_METRIC_ACCURACY,
    EVAL_METRIC_BASE_RATE,
    EVAL_METRIC_BRIER,
    EVAL_METRIC_COUNT,
    EVAL_METRIC_ECE,
    EVAL_METRIC_LOG_LOSS,
    EVAL_OK,
    eval_status_name,
)
from evaluation.scores import (
    EVAL_ACCURACY_THRESHOLD,
    brier_decomposition_flat,
    calibration_error_flat,
    evaluate_flat,
    log_loss_flat,
    metric_value_flat,
    reliability_diagram_flat,
)
from loss_functions import binary_cross_entropy


def close(got: Float64, want: Float64) -> Bool:
    """Within 8 ulps of `want` — that value's own magnitude, nothing else's."""
    return fabs(got - want) <= 8.0 * EVAL_DBL_EPSILON * fabs(want)


def close_log(got: Float64, want: Float64) -> Bool:
    """Within 1e-8 relative — the frozen `std.math.log`'s measured accuracy, not slack.

    See the module docstring: `log(0.7)` on this toolchain is 2.5e-9 relative from the
    correctly rounded value, and the frozen kernel that calls it is not being replaced.
    """
    return fabs(got - want) <= 1e-8 * fabs(want)


def pairs_a() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.1)
    out.append(0.3)
    out.append(0.5)
    out.append(0.7)
    out.append(0.9)
    return out^


def labels_a() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(0.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    return out^


def pairs_b() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.2)
    out.append(0.4)
    out.append(0.6)
    out.append(0.8)
    return out^


def labels_b() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(1.0)
    out.append(0.0)
    out.append(1.0)
    return out^


def two(first: Float64, second: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(first)
    out.append(second)
    return out^


def main() raises:
    var failures = 0
    var checks = 0
    var pa = pairs_a()
    var ya = labels_a()
    var pb = pairs_b()
    var yb = labels_b()

    # ── Brier, base rate, accuracy: exact on dataset A ───────────────────────
    var rep = evaluate_flat(pa, ya, 5, 5, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if rep.status != EVAL_OK:
        print("  ❌ A refused:", eval_status_name(rep.status))
        failures += 1
    checks += 1
    if rep.brier != 0.09:
        print("  ❌ A Brier", rep.brier, "want exactly 0.09")
        failures += 1
    checks += 1
    if rep.base_rate != 0.6:
        print("  ❌ A base rate", rep.base_rate, "want 0.6")
        failures += 1
    checks += 1
    if rep.accuracy != 1.0:
        print("  ❌ A accuracy", rep.accuracy, "want 1.0")
        failures += 1
    checks += 1
    if not close(rep.uncertainty, 0.24):
        print("  ❌ A uncertainty", rep.uncertainty, "want 0.24")
        failures += 1
    checks += 1
    if EVAL_ACCURACY_THRESHOLD != 0.5 or rep.accuracy_threshold != 0.5:
        print("  ❌ the accuracy threshold must be stated and be 0.5")
        failures += 1

    # ── the decomposition closes exactly when bins are singletons ────────────
    checks += 1
    if not close(rep.reliability, 0.09):
        print("  ❌ A/h=5 reliability", rep.reliability, "want 0.09")
        failures += 1
    checks += 1
    if not close(rep.resolution, 0.24):
        print("  ❌ A/h=5 resolution", rep.resolution, "want 0.24")
        failures += 1
    checks += 1
    if rep.residual != 0.0:
        print("  ❌ A/h=5 residual", rep.residual, "want exactly 0.0 — singleton bins have")
        print("     no within-bin variance, so Murphy's identity is an identity here")
        failures += 1
    checks += 1
    if not rep.decomposition_closes:
        print("  ❌ A/h=5 decomposition_closes must be True")
        failures += 1

    # ── and does NOT close with one bin, by a hand-computable -0.16 ──────────
    var one = brier_decomposition_flat(pa, ya, 5, 1, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if one.status != EVAL_OK or not one.present:
        print("  ❌ A/h=1 refused:", eval_status_name(one.status))
        failures += 1
    checks += 1
    if not close(one.reliability, 0.01):
        print("  ❌ A/h=1 reliability", one.reliability, "want (0.5-0.6)^2 = 0.01")
        failures += 1
    checks += 1
    if one.resolution != 0.0:
        print("  ❌ A/h=1 resolution", one.resolution, "want exactly 0.0 (one bin, no lift)")
        failures += 1
    checks += 1
    if not close(one.residual, -0.16):
        print("  ❌ A/h=1 residual", one.residual, "want 0.09 - 0.25 = -0.16")
        failures += 1
    checks += 1
    if one.decomposition_closes:
        print("  ❌ A/h=1 must report that the decomposition does NOT close;")
        print("     reporting closure here would hide 0.16 of smoothing")
        failures += 1
    checks += 1
    if one.brier != 0.09:
        print("  ❌ the Brier score is binning-free and must not move with h:", one.brier)
        failures += 1

    # ── ECE and MCE, exact on dataset A ──────────────────────────────────────
    checks += 1
    if not close(rep.ece, 0.26):
        print("  ❌ A/h=5 ECE", rep.ece, "want 1.3/5 = 0.26")
        failures += 1
    checks += 1
    if rep.mce != 0.5:
        print("  ❌ A/h=5 MCE", rep.mce, "want exactly 0.5")
        failures += 1

    # ── ECE is binning-dependent, measured ───────────────────────────────────
    var b2 = calibration_error_flat(pb, yb, 4, 2, EVAL_BIN_EQUAL_WIDTH)
    var b4 = calibration_error_flat(pb, yb, 4, 4, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if not close(b2.ece, 0.2):
        print("  ❌ B/h=2 ECE", b2.ece, "want 0.2")
        failures += 1
    checks += 1
    if not close(b4.ece, 0.4):
        print("  ❌ B/h=4 ECE", b4.ece, "want 0.4")
        failures += 1
    checks += 1
    if not close(b4.mce, 0.6):
        print("  ❌ B/h=4 MCE", b4.mce, "want 0.6")
        failures += 1
    checks += 1
    if b2.bins_used != 2 or b4.bins_used != 4:
        print("  ❌ the bin count must ride with the number:", b2.bins_used, b4.bins_used)
        failures += 1
    checks += 1
    if b2.bin_policy != EVAL_BIN_EQUAL_WIDTH or b4.bin_policy != EVAL_BIN_EQUAL_WIDTH:
        print("  ❌ the policy must ride with the number")
        failures += 1
    # The whole point: without the provenance these two numbers are indistinguishable claims.
    checks += 1
    if close(b2.ece, b4.ece):
        print("  ❌ the binning-dependence case no longer demonstrates dependence")
        failures += 1

    # ── log-loss on A, against the hand-computed sum of logarithms ───────────
    var lla = log_loss_flat(pa, ya, 5)
    checks += 1
    if lla.status != EVAL_OK or not lla.present:
        print("  ❌ A log-loss refused")
        failures += 1
    checks += 1
    if not close_log(lla.log_loss, 0.32344361995061256):
        print("  ❌ A log-loss", lla.log_loss, "want 0.32344361995061256")
        failures += 1
    checks += 1
    if lla.clamped_count != 0:
        print("  ❌ A has no saturated prediction; clamped_count", lla.clamped_count, "want 0")
        failures += 1
    checks += 1
    if lla.eps_used != EVAL_LOG_LOSS_EPS:
        print("  ❌ the reported epsilon must be the stated one")
        failures += 1

    # ── the stated epsilon IS the frozen kernel's clamp ──────────────────────
    # If `binary_cross_entropy` ever changes its internal 1e-7, EVAL_LOG_LOSS_EPS becomes a
    # lie and every `eps_used` in every report becomes wrong. This is the assertion that
    # cannot drift: the kernel's answer at p=0 must equal its answer at p=eps exactly.
    checks += 1
    if binary_cross_entropy(1.0, 0.0) != binary_cross_entropy(1.0, EVAL_LOG_LOSS_EPS):
        print("  ❌ the frozen kernel does not clamp at EVAL_LOG_LOSS_EPS:",
              binary_cross_entropy(1.0, 0.0), binary_cross_entropy(1.0, EVAL_LOG_LOSS_EPS))
        failures += 1
    checks += 1
    if binary_cross_entropy(0.0, 1.0) != binary_cross_entropy(
        0.0, 1.0 - EVAL_LOG_LOSS_EPS
    ):
        print("  ❌ the frozen kernel does not clamp the upper end at 1 - EVAL_LOG_LOSS_EPS")
        failures += 1

    # ── DATASET C: saturated and wrong. Brier 1.0, log-loss censored ─────────
    var pc = two(0.0, 1.0)
    var yc = two(1.0, 0.0)
    var repc = evaluate_flat(pc, yc, 2, 2, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if repc.brier != 1.0:
        print("  ❌ C Brier", repc.brier, "want exactly 1.0, the maximum")
        failures += 1
    checks += 1
    if not close_log(repc.log_loss, 16.11809565095832):
        print("  ❌ C log-loss", repc.log_loss, "want -ln(1e-7) = 16.11809565095832")
        failures += 1
    checks += 1
    if repc.log_loss_clamped != 2:
        print("  ❌ C clamped_count", repc.log_loss_clamped, "want 2 — the number is censored")
        print("     and nothing else in the result would say so")
        failures += 1
    # A mathematically infinite log-loss must arrive as a FINITE field. A raw infinity here
    # makes the whole response a typed transport error rather than a metric.
    checks += 1
    if not (repc.log_loss == repc.log_loss and (repc.log_loss - repc.log_loss) == 0.0):
        print("  ❌ C log-loss is not finite; an infinity in a metric field breaks the whole")
        print("     response, not just this number")
        failures += 1

    # ── DATASET D: perfect, and its log-loss is still not zero ───────────────
    var pd = two(0.0, 1.0)
    var yd = two(0.0, 1.0)
    var repd = evaluate_flat(pd, yd, 2, 2, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if repd.brier != 0.0:
        print("  ❌ D Brier", repd.brier, "want exactly 0.0")
        failures += 1
    checks += 1
    if not close_log(repd.log_loss, 1.00000005e-07):
        print("  ❌ D log-loss", repd.log_loss, "want -ln(1-1e-7) = 1.00000005e-07")
        failures += 1
    checks += 1
    if repd.log_loss_clamped != 2:
        print("  ❌ D clamped_count", repd.log_loss_clamped, "want 2 — a perfect model's")
        print("     nonzero log-loss is entirely the clamp, and the count is the only clue")
        failures += 1
    checks += 1
    if repd.ece != 0.0 or repd.mce != 0.0:
        print("  ❌ D is perfectly calibrated at h=2:", repd.ece, repd.mce)
        failures += 1

    # ── the reliability diagram marks empty bins ABSENT, not calibrated ──────
    # A/h=10: Int(p*10) puts the five samples in bins 1, 3, 5, 7, 9. Bins 0, 2, 4, 6, 8 are
    # empty. The frozen `calibration_curve` reports observed_freq 0.0 there with no flag, so
    # a plot built straight from it draws five points at zero observed frequency.
    var diag = reliability_diagram_flat(pa, ya, 5, 10, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if diag.status != EVAL_OK or len(diag.bin_present) != 10:
        print("  ❌ A/h=10 diagram", eval_status_name(diag.status), len(diag.bin_present))
        failures += 1
    checks += 1
    if diag.bins_occupied != 5:
        print("  ❌ A/h=10 occupied", diag.bins_occupied, "want 5")
        failures += 1
    var wrong_flags = 0
    for b in range(10):
        var expect_present = b == 1 or b == 3 or b == 5 or b == 7 or b == 9
        if diag.bin_present[b] != expect_present:
            wrong_flags += 1
        if not diag.bin_present[b]:
            if diag.bin_count[b] != 0 or diag.bin_conf[b] != 0.0 or diag.bin_freq[b] != 0.0:
                wrong_flags += 1
    checks += 1
    if wrong_flags != 0:
        print("  ❌", wrong_flags, "bin(s) where presence and content disagree")
        failures += 1
    # The x coordinate of a reliability point is the mean PREDICTION, not the bin centre:
    # bin 1 spans [0.1, 0.2) and holds only 0.1, so conf is 0.1 and not 0.15.
    checks += 1
    if diag.bin_conf[1] != 0.1:
        print("  ❌ bin 1 confidence", diag.bin_conf[1], "want the mean prediction 0.1,")
        print("     not the bin centre 0.15")
        failures += 1
    checks += 1
    if diag.bin_freq[1] != 0.0 or diag.bin_freq[9] != 1.0:
        print("  ❌ bin observed frequencies", diag.bin_freq[1], diag.bin_freq[9])
        failures += 1
    var descents = 0
    for b in range(1, 10):
        if diag.bin_lo[b] < diag.bin_lo[b - 1]:
            descents += 1
    checks += 1
    if descents != 0 or diag.bin_lo[0] != 0.0 or diag.bin_hi[9] != 1.0:
        print("  ❌ the diagram's edges are not an ascending axis spanning [0, 1]")
        failures += 1

    # ── metric_value_flat agrees BIT-FOR-BIT with the dedicated drivers ──────
    # Self-consistency is a testable property, so it is tested: two mutually exclusive
    # numbers in one package means a caller can use neither.
    var mv_brier = metric_value_flat(pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH)
    var mv_ll = metric_value_flat(pa, ya, 5, EVAL_METRIC_LOG_LOSS, 5, EVAL_BIN_EQUAL_WIDTH)
    var mv_ece = metric_value_flat(pa, ya, 5, EVAL_METRIC_ECE, 5, EVAL_BIN_EQUAL_WIDTH)
    var mv_acc = metric_value_flat(pa, ya, 5, EVAL_METRIC_ACCURACY, 5, EVAL_BIN_EQUAL_WIDTH)
    var mv_base = metric_value_flat(pa, ya, 5, EVAL_METRIC_BASE_RATE, 5, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if mv_brier.value != rep.brier or mv_ll.value != rep.log_loss:
        print("  ❌ metric_value_flat disagrees with evaluate_flat:",
              mv_brier.value, rep.brier, mv_ll.value, rep.log_loss)
        failures += 1
    checks += 1
    if mv_ece.value != rep.ece or mv_acc.value != rep.accuracy:
        print("  ❌ metric_value_flat ECE/accuracy disagree with evaluate_flat")
        failures += 1
    checks += 1
    if mv_base.value != rep.base_rate:
        print("  ❌ metric_value_flat base rate disagrees with evaluate_flat")
        failures += 1
    checks += 1
    if mv_brier.value != brier_decomposition_flat(
        pa, ya, 5, 5, EVAL_BIN_EQUAL_WIDTH
    ).brier:
        print("  ❌ metric_value_flat Brier disagrees with brier_decomposition_flat")
        failures += 1
    checks += 1
    if mv_ll.value != lla.log_loss:
        print("  ❌ metric_value_flat log-loss disagrees with log_loss_flat:",
              mv_ll.value, lla.log_loss)
        failures += 1
    checks += 1
    if mv_ece.value != calibration_error_flat(pa, ya, 5, 5, EVAL_BIN_EQUAL_WIDTH).ece:
        print("  ❌ metric_value_flat ECE disagrees with calibration_error_flat")
        failures += 1
    # Only the binning metric reports a binning provenance; the others must not imply one.
    checks += 1
    if mv_ece.bins_used != 5 or mv_ece.bin_policy != EVAL_BIN_EQUAL_WIDTH:
        print("  ❌ an ECE must carry its provenance:", mv_ece.bins_used, mv_ece.bin_policy)
        failures += 1
    checks += 1
    if mv_brier.bins_used != 0 or mv_brier.bin_policy != -1:
        print("  ❌ a Brier score must not imply a binning provenance:",
              mv_brier.bins_used, mv_brier.bin_policy)
        failures += 1

    # ── the POLICY changes the ECE too, at an identical bin count ────────────
    # p [0.05, 0.10, 0.15, 0.90], y [0, 0, 1, 1] at h = 2:
    #   equal width  Int(p*2) -> [0,0,0,1]: bin0 {0.05,0.10,0.15} conf 0.1 freq 1/3,
    #                bin1 {0.90} conf 0.9 freq 1
    #                ECE = (3/4)|1/3 - 0.1| + (1/4)|1 - 0.9| = 0.175 + 0.025 = 0.2
    #   equal count  edge = sorted[2] = 0.15: bin0 {0.05,0.10} conf 0.075 freq 0,
    #                bin1 {0.15,0.90} conf 0.525 freq 1
    #                ECE = 0.5*0.075 + 0.5*0.475 = 0.0375 + 0.2375 = 0.275
    # Two policies, one bin count, one dataset, 0.2 against 0.275.
    var pe = List[Float64]()
    pe.append(0.05)
    pe.append(0.10)
    pe.append(0.15)
    pe.append(0.90)
    var ye = List[Float64]()
    ye.append(0.0)
    ye.append(0.0)
    ye.append(1.0)
    ye.append(1.0)
    var ew = calibration_error_flat(pe, ye, 4, 2, EVAL_BIN_EQUAL_WIDTH)
    var ec = calibration_error_flat(pe, ye, 4, 2, EVAL_BIN_EQUAL_COUNT)
    checks += 1
    if not close(ew.ece, 0.2):
        print("  ❌ equal-width ECE", ew.ece, "want 0.2")
        failures += 1
    checks += 1
    if ec.ece != 0.275:
        print("  ❌ equal-count ECE", ec.ece, "want exactly 0.275")
        failures += 1
    checks += 1
    if ew.bin_policy != EVAL_BIN_EQUAL_WIDTH or ec.bin_policy != EVAL_BIN_EQUAL_COUNT:
        print("  ❌ each ECE must report the policy that produced it")
        failures += 1
    checks += 1
    if ew.bins_used != ec.bins_used:
        print("  ❌ the contrast is supposed to hold the bin count fixed")
        failures += 1
    checks += 1
    if close(ew.ece, ec.ece):
        print("  ❌ the two policies produced the same ECE — the case no longer shows that")
        print("     a bin COUNT alone is not enough provenance for a calibration error")
        failures += 1

    # ── refusals: every driver, every field zeroed, no partial answer ────────
    var refused = evaluate_flat(pa, ya, 25, 5, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if refused.status != EVAL_ERR_COUNT:
        print("  ❌ n=25 on a 5-list must refuse:", eval_status_name(refused.status))
        failures += 1
    checks += 1
    if refused.brier_present or refused.ece_present or refused.log_loss_present:
        print("  ❌ a refused report must not mark any metric present")
        failures += 1
    checks += 1
    if refused.brier != 0.0 or refused.ece != 0.0 or refused.log_loss != 0.0:
        print("  ❌ a refused report's value slots must be representable zeros")
        failures += 1
    checks += 1
    if evaluate_flat(pa, ya, 0, 5, EVAL_BIN_EQUAL_WIDTH).status != EVAL_ERR_EMPTY:
        print("  ❌ an empty evaluation set has no metrics — it is not a Brier score of 0.0")
        failures += 1
    checks += 1
    if evaluate_flat(pa, ya, 5, 0, EVAL_BIN_EQUAL_WIDTH).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ h=0 must refuse rather than report a perfect ECE of 0.0")
        failures += 1
    checks += 1
    if log_loss_flat(pa, ya, 25).status != EVAL_ERR_COUNT:
        print("  ❌ log_loss_flat count guard")
        failures += 1
    checks += 1
    if brier_decomposition_flat(pa, ya, 25, 5, 0).status != EVAL_ERR_COUNT:
        print("  ❌ brier_decomposition_flat count guard")
        failures += 1
    checks += 1
    if calibration_error_flat(pa, ya, 25, 5, 0).status != EVAL_ERR_COUNT:
        print("  ❌ calibration_error_flat count guard")
        failures += 1
    checks += 1
    if len(reliability_diagram_flat(pa, ya, 25, 5, 0).bin_lo) != 0:
        print("  ❌ a refused diagram must be empty")
        failures += 1
    checks += 1
    if metric_value_flat(pa, ya, 25, EVAL_METRIC_BRIER, 5, 0).status != EVAL_ERR_COUNT:
        print("  ❌ metric_value_flat count guard")
        failures += 1
    checks += 1
    if metric_value_flat(pa, ya, 5, EVAL_METRIC_COUNT, 5, 0).status != EVAL_ERR_UNKNOWN_METRIC:
        print("  ❌ an unknown metric must refuse, never default to metric 0")
        failures += 1
    checks += 1
    if metric_value_flat(pa, ya, 5, -1, 5, 0).status != EVAL_ERR_UNKNOWN_METRIC:
        print("  ❌ a negative metric id must refuse")
        failures += 1
    # Binning arguments are validated even for the metrics that do not bin, so a caller
    # cannot reuse nonsense arguments for a later ECE.
    checks += 1
    if metric_value_flat(pa, ya, 5, EVAL_METRIC_BRIER, 0, 0).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ a non-binning metric must still validate its binning arguments")
        failures += 1
    var bad_p = pairs_a()
    bad_p[0] = 2.0
    checks += 1
    if evaluate_flat(bad_p, ya, 5, 5, 0).status != EVAL_ERR_PROB_RANGE:
        print("  ❌ a probability of 2.0 must refuse, not be clipped into a plausible metric")
        failures += 1
    var soft_y = labels_a()
    soft_y[0] = 0.25
    checks += 1
    if evaluate_flat(pa, soft_y, 5, 5, 0).status != EVAL_ERR_LABEL_NOT_BINARY:
        print("  ❌ a soft label must refuse: binary_cross_entropy would compute a")
        print("     well-formed cross-entropy that is not a log-loss")
        failures += 1

    # ── a single-class evaluation set: uncertainty 0, resolution 0, still valid ─
    var pos_p = two(0.8, 0.9)
    var pos_y = two(1.0, 1.0)
    var pos = evaluate_flat(pos_p, pos_y, 2, 2, EVAL_BIN_EQUAL_WIDTH)
    checks += 1
    if pos.status != EVAL_OK or pos.base_rate != 1.0:
        print("  ❌ an all-positive set is a valid evaluation set:",
              eval_status_name(pos.status), pos.base_rate)
        failures += 1
    checks += 1
    if pos.uncertainty != 0.0 or pos.resolution != 0.0:
        print("  ❌ with one class there is no uncertainty and no resolution to have:",
              pos.uncertainty, pos.resolution)
        failures += 1
    # Brier = ((0.8-1)^2 + (0.9-1)^2)/2 = (0.04 + 0.01)/2 = 0.025
    checks += 1
    if not close(pos.brier, 0.025):
        print("  ❌ all-positive Brier", pos.brier, "want 0.025")
        failures += 1

    for _ in range(checks - failures):
        print("  ✅ evaluation.scores check")
    print("  [evaluation.scores] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_evaluation_scores failed")
