"""test_evaluation_contract.mojo — hand-written tests for the evaluation input contract.

Hand-written, never machine-emitted.

Two kinds of assertion live here, and only one of them is about arithmetic.

**The refusals.** `eval_pairs_status` is the guard whose absence is a remote process-abort
primitive: reading past the end of a `List` in Mojo kills the worker and no `try`/`except`
above it helps. Every count case below (`n` past either list, negative `n`, `n` over the
sample ceiling) is asserted to return a typed status. If any of them indexed instead, this
process would die here rather than report a failed check — so the suite completing at all is
part of the evidence.

**The budget arithmetic.** `eval_work_fits(3, 6148914691236517206, 100)` is the exact input
that walked past a `rows * cols <= ceiling` guard in `sparse_numerics` and ended the worker:
the product wraps to 2, which is comfortably under 100. A division-based check has no such
failure mode, and the assertion pins the specific number rather than the principle.

`eval_log2_ceil` reference values, verified by hand:
    n:      1  2  3  4  5  8  9  16  17  1000  1024  1025
    ceil:   0  1  2  2  3  3  4   4   5    10    10    11
"""
from evaluation.contract import (
    EVAL_BIN_EQUAL_COUNT,
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_DBL_EPSILON,
    EVAL_ERR_ALPHA_RANGE,
    EVAL_ERR_BIN_COUNT,
    EVAL_ERR_BIN_POLICY,
    EVAL_ERR_COUNT,
    EVAL_ERR_DIM_TOO_LARGE,
    EVAL_ERR_EMPTY,
    EVAL_ERR_LABEL_LENGTH,
    EVAL_ERR_LABEL_NOT_BINARY,
    EVAL_ERR_NON_FINITE,
    EVAL_ERR_PROB_RANGE,
    EVAL_ERR_THRESHOLD,
    EVAL_LOG_LOSS_EPS,
    EVAL_MAX_BINS,
    EVAL_MAX_RESAMPLES,
    EVAL_MAX_RESAMPLE_WORK,
    EVAL_MAX_SAMPLES,
    EVAL_METRIC_ACCURACY,
    EVAL_METRIC_BASE_RATE,
    EVAL_METRIC_BRIER,
    EVAL_METRIC_COUNT,
    EVAL_METRIC_ECE,
    EVAL_METRIC_LOG_LOSS,
    EVAL_OK,
    eval_bin_policy_name,
    eval_bins_status,
    eval_ece_comparable,
    eval_finite,
    eval_log2_ceil,
    eval_metric_higher_is_better,
    eval_metric_name,
    eval_pairs_status,
    eval_resample_work_fits,
    eval_scores_status,
    eval_status_is_ok,
    eval_status_name,
    eval_work_fits,
)


def good_probs() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.1)
    out.append(0.3)
    out.append(0.5)
    out.append(0.7)
    out.append(0.9)
    return out^


def good_labels() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(0.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    return out^


def main() raises:
    var failures = 0
    var checks = 0
    var p = good_probs()
    var y = good_labels()
    var nan_v = 0.0 / 0.0
    var inf_v = 1.0 / 0.0

    # ── the status range is exactly the one the package claims to own ─────────
    # 360-379 inclusive, twenty codes, every one named. A code outside the range must NOT
    # get a name: a caller logging an integer has to recover one meaning from it, and a
    # neighbour's vocabulary answering for an unallocated code is how two packages come to
    # disagree about what 81 means.
    checks += 1
    if EVAL_OK != 360 or EVAL_ERR_THRESHOLD != 379:
        print("  ❌ the declared status range moved:", EVAL_OK, EVAL_ERR_THRESHOLD)
        failures += 1
    var unnamed = 0
    for code in range(360, 380):
        if eval_status_name(code) == String("unknown_status_code"):
            unnamed += 1
    checks += 1
    if unnamed != 0:
        print("  ❌", unnamed, "code(s) in 360-379 have no name")
        failures += 1
    checks += 1
    if eval_status_name(359) != String("unknown_status_code"):
        print("  ❌ 359 is not this package's and must not be named")
        failures += 1
    checks += 1
    if eval_status_name(380) != String("unknown_status_code"):
        print("  ❌ 380 is not this package's and must not be named")
        failures += 1
    checks += 1
    if not eval_status_is_ok(EVAL_OK) or eval_status_is_ok(EVAL_ERR_EMPTY):
        print("  ❌ eval_status_is_ok does not agree with EVAL_OK")
        failures += 1

    # ── the vocabularies ─────────────────────────────────────────────────────
    checks += 1
    if EVAL_METRIC_COUNT != 5 or EVAL_METRIC_ECE != 4:
        print("  ❌ the metric vocabulary changed size without a version bump")
        failures += 1
    var unnamed_metrics = 0
    for m in range(0, EVAL_METRIC_COUNT):
        if eval_metric_name(m) == String("unknown_metric"):
            unnamed_metrics += 1
    checks += 1
    if unnamed_metrics != 0:
        print("  ❌", unnamed_metrics, "metric id(s) unnamed")
        failures += 1
    checks += 1
    if eval_metric_name(EVAL_METRIC_COUNT) != String("unknown_metric"):
        print("  ❌ an id past the vocabulary must not be named")
        failures += 1
    # Direction belongs to the metric: accuracy up is better, every loss down is better.
    checks += 1
    if not eval_metric_higher_is_better(EVAL_METRIC_ACCURACY):
        print("  ❌ accuracy must be higher-is-better")
        failures += 1
    checks += 1
    if eval_metric_higher_is_better(EVAL_METRIC_BRIER):
        print("  ❌ a lower Brier score is better, not worse")
        failures += 1
    checks += 1
    if eval_metric_higher_is_better(EVAL_METRIC_LOG_LOSS):
        print("  ❌ a lower log-loss is better, not worse")
        failures += 1
    checks += 1
    if eval_metric_higher_is_better(EVAL_METRIC_ECE):
        print("  ❌ a lower calibration error is better, not worse")
        failures += 1
    checks += 1
    if eval_bin_policy_name(EVAL_BIN_EQUAL_WIDTH) != String("equal_width"):
        print("  ❌ equal-width policy name")
        failures += 1
    checks += 1
    if eval_bin_policy_name(EVAL_BIN_EQUAL_COUNT) != String("equal_count"):
        print("  ❌ equal-count policy name")
        failures += 1
    checks += 1
    if eval_bin_policy_name(2) != String("unknown_bin_policy"):
        print("  ❌ an unallocated policy must not be named")
        failures += 1

    # ── finiteness, one predicate ────────────────────────────────────────────
    checks += 1
    if not eval_finite(0.0) or not eval_finite(-1e308):
        print("  ❌ eval_finite rejected a finite value")
        failures += 1
    checks += 1
    if eval_finite(nan_v) or eval_finite(inf_v) or eval_finite(-inf_v):
        print("  ❌ eval_finite accepted a non-finite value")
        failures += 1

    # ── the count guard. If any of these indexed, this process would be dead ──
    checks += 1
    if eval_pairs_status(p, y, 5) != EVAL_OK:
        print("  ❌ a valid pair was refused:", eval_status_name(eval_pairs_status(p, y, 5)))
        failures += 1
    checks += 1
    if eval_pairs_status(p, y, 25) != EVAL_ERR_COUNT:
        print("  ❌ n=25 on a 5-element list was not refused")
        failures += 1
    checks += 1
    if eval_pairs_status(p, y, -3) != EVAL_ERR_COUNT:
        print("  ❌ a negative count was not refused")
        failures += 1
    checks += 1
    if eval_pairs_status(p, y, 0) != EVAL_ERR_EMPTY:
        print("  ❌ an empty evaluation set must be EVAL_ERR_EMPTY, not a metric of 0.0")
        failures += 1
    checks += 1
    if eval_pairs_status(p, y, EVAL_MAX_SAMPLES + 1) != EVAL_ERR_DIM_TOO_LARGE:
        print("  ❌ the sample ceiling is not enforced")
        failures += 1
    # A short LABEL list gets its own code, so the caller knows which side is wrong.
    var short_labels = List[Float64]()
    short_labels.append(0.0)
    short_labels.append(1.0)
    checks += 1
    if eval_pairs_status(p, short_labels, 5) != EVAL_ERR_LABEL_LENGTH:
        print("  ❌ a short label list must be distinguishable from a short prediction list")
        failures += 1
    checks += 1
    if eval_scores_status(p, 25) != EVAL_ERR_COUNT:
        print("  ❌ eval_scores_status count guard")
        failures += 1
    checks += 1
    if eval_scores_status(p, 5) != EVAL_OK:
        print("  ❌ eval_scores_status refused valid scores")
        failures += 1

    # ── value-domain refusals: never clipped, never thresholded ──────────────
    var bad_prob = good_probs()
    bad_prob[2] = 1.5
    checks += 1
    if eval_pairs_status(bad_prob, y, 5) != EVAL_ERR_PROB_RANGE:
        print("  ❌ a probability of 1.5 must be refused, not clipped to 1.0")
        failures += 1
    var neg_prob = good_probs()
    neg_prob[0] = -0.25
    checks += 1
    if eval_pairs_status(neg_prob, y, 5) != EVAL_ERR_PROB_RANGE:
        print("  ❌ a negative probability must be refused")
        failures += 1
    var nan_prob = good_probs()
    nan_prob[1] = nan_v
    checks += 1
    if eval_pairs_status(nan_prob, y, 5) != EVAL_ERR_NON_FINITE:
        print("  ❌ a NaN prediction must be refused before any metric touches it")
        failures += 1
    var inf_prob = good_probs()
    inf_prob[4] = inf_v
    checks += 1
    if eval_pairs_status(inf_prob, y, 5) != EVAL_ERR_NON_FINITE:
        print("  ❌ an infinite prediction must be refused")
        failures += 1
    var soft_label = good_labels()
    soft_label[3] = 0.5
    checks += 1
    if eval_pairs_status(p, soft_label, 5) != EVAL_ERR_LABEL_NOT_BINARY:
        print("  ❌ a label of 0.5 must be refused, not thresholded")
        failures += 1
    var nan_label = good_labels()
    nan_label[0] = nan_v
    checks += 1
    if eval_pairs_status(p, nan_label, 5) != EVAL_ERR_NON_FINITE:
        print("  ❌ a NaN label must report non-finite, not not-binary")
        failures += 1
    # A score of 1.0 and of 0.0 are both legal probabilities and must NOT be refused.
    var extremes = List[Float64]()
    extremes.append(0.0)
    extremes.append(1.0)
    checks += 1
    if eval_scores_status(extremes, 2) != EVAL_OK:
        print("  ❌ 0.0 and 1.0 are valid probabilities and were refused")
        failures += 1

    # ── binning arguments ────────────────────────────────────────────────────
    checks += 1
    if eval_bins_status(10, EVAL_BIN_EQUAL_WIDTH) != EVAL_OK:
        print("  ❌ a valid binning was refused")
        failures += 1
    checks += 1
    if eval_bins_status(0, EVAL_BIN_EQUAL_WIDTH) != EVAL_ERR_BIN_COUNT:
        print("  ❌ n_bins=0 must be refused: the frozen curve returns empty lists there,")
        print("     which a driver that did not check would read as a perfect ECE of 0.0")
        failures += 1
    checks += 1
    if eval_bins_status(-4, EVAL_BIN_EQUAL_WIDTH) != EVAL_ERR_BIN_COUNT:
        print("  ❌ a negative bin count was not refused")
        failures += 1
    checks += 1
    if eval_bins_status(EVAL_MAX_BINS + 1, EVAL_BIN_EQUAL_WIDTH) != EVAL_ERR_BIN_COUNT:
        print("  ❌ the bin ceiling is not enforced")
        failures += 1
    checks += 1
    if eval_bins_status(EVAL_MAX_BINS, EVAL_BIN_EQUAL_WIDTH) != EVAL_OK:
        print("  ❌ the ceiling itself must be allowed")
        failures += 1
    checks += 1
    if eval_bins_status(10, 7) != EVAL_ERR_BIN_POLICY:
        print("  ❌ an unknown policy must be refused, not defaulted to equal-width")
        failures += 1

    # ── incomparable binnings are refused, not compared ──────────────────────
    checks += 1
    if not eval_ece_comparable(10, EVAL_BIN_EQUAL_WIDTH, 10, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ identical binnings must be comparable")
        failures += 1
    checks += 1
    if eval_ece_comparable(10, EVAL_BIN_EQUAL_WIDTH, 20, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ 10 bins and 20 bins are not the same statistic")
        failures += 1
    checks += 1
    if eval_ece_comparable(10, EVAL_BIN_EQUAL_WIDTH, 10, EVAL_BIN_EQUAL_COUNT):
        print("  ❌ equal-width and equal-count are not the same statistic")
        failures += 1
    checks += 1
    if eval_ece_comparable(0, EVAL_BIN_EQUAL_WIDTH, 0, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ two invalid binnings are two refusals, not a comparison")
        failures += 1

    # ── ceil(log2(n)), hand-verified table ───────────────────────────────────
    var log_n = List[Int]()
    var log_want = List[Int]()
    log_n.append(0); log_want.append(0)
    log_n.append(1); log_want.append(0)
    log_n.append(2); log_want.append(1)
    log_n.append(3); log_want.append(2)
    log_n.append(4); log_want.append(2)
    log_n.append(5); log_want.append(3)
    log_n.append(8); log_want.append(3)
    log_n.append(9); log_want.append(4)
    log_n.append(16); log_want.append(4)
    log_n.append(17); log_want.append(5)
    log_n.append(1000); log_want.append(10)
    log_n.append(1024); log_want.append(10)
    log_n.append(1025); log_want.append(11)
    for i in range(len(log_n)):
        checks += 1
        if eval_log2_ceil(log_n[i]) != log_want[i]:
            print("  ❌ eval_log2_ceil(", log_n[i], ")=", eval_log2_ceil(log_n[i]),
                  "want", log_want[i])
            failures += 1
    checks += 1
    if eval_log2_ceil(-8) != 0:
        print("  ❌ a negative n has no bit width; 0 is the only safe answer")
        failures += 1

    # ── the wrapping multiply, by the exact number that killed a worker ──────
    # 3 * 6148914691236517206 == 2 in wrapping 64-bit arithmetic, so a guard written as
    # `a * b <= ceiling` accepts this as 2 <= 100.
    checks += 1
    if eval_work_fits(3, 6148914691236517206, 100):
        print("  ❌ eval_work_fits was walked past by the wrapping product 3 * 6148914691236517206")
        failures += 1
    checks += 1
    if not eval_work_fits(10, 10, 100):
        print("  ❌ 10 * 10 == 100 must fit a ceiling of 100 exactly")
        failures += 1
    checks += 1
    if eval_work_fits(11, 10, 100):
        print("  ❌ 11 * 10 == 110 must not fit a ceiling of 100")
        failures += 1
    checks += 1
    if not eval_work_fits(0, 6148914691236517206, 1):
        print("  ❌ zero work always fits")
        failures += 1
    checks += 1
    if eval_work_fits(-1, 10, 100) or eval_work_fits(10, 10, -1):
        print("  ❌ a negative factor or ceiling is malformed, not a fit")
        failures += 1

    # ── the resample budget charges the PRODUCT, and the sort inside it ──────
    # A shape that fits when charged n_boot * n must STOP fitting when the per-replicate
    # sort of a quantile-binned ECE is also charged. That difference is the whole point:
    # measured elsewhere in this tree as 0.49s against 23.89s at an identical declared cost.
    checks += 1
    if not eval_resample_work_fits(1000, 1000, 10, EVAL_METRIC_BRIER, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ a 1000 x 1000 Brier bootstrap should fit the budget")
        failures += 1
    # n_boot * n = 2^32 == EVAL_MAX_RESAMPLE_WORK, so factor 1 fits exactly and any extra
    # factor cannot. 65536 * 65536 = 2^32.
    checks += 1
    if not eval_work_fits(65536, 65536, EVAL_MAX_RESAMPLE_WORK):
        print("  ❌ 2^16 * 2^16 == 2^32 must fit a ceiling of 2^32")
        failures += 1
    checks += 1
    if not eval_resample_work_fits(65536, 65536, 10, EVAL_METRIC_BRIER, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ the exact-ceiling shape must fit when the factor is 1")
        failures += 1
    checks += 1
    if eval_resample_work_fits(65536, 65536, 10, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_COUNT):
        print("  ❌ the same shape with a per-replicate sort costs ceil(log2(n))=16x more")
        print("     and must NOT fit — a budget that charges one factor is not a budget")
        failures += 1
    # An equal-WIDTH ECE pays no sort, but it DOES rebuild the whole h-bin partition inside
    # every replicate. The shape above sits exactly on the ceiling when only samples are
    # charged, so ten bins per replicate must push it over. Brier at the identical shape must
    # still fit, because Brier never bins: that pair is the assertion that the bin term is
    # charged to the metric that pays it and to no other.
    checks += 1
    if eval_resample_work_fits(65536, 65536, 10, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ an equal-width ECE rebuilds the partition per replicate, so 10 bins x")
        print("     65536 replicates is real work on top of a shape already exactly at the")
        print("     ceiling, and must NOT fit")
        failures += 1
    # Drop the replicate count enough to pay for the bins and it fits again, so the refusal
    # above is a charge and not a blanket ban on binned bootstraps.
    checks += 1
    if not eval_resample_work_fits(65526, 65536, 10, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ the same ECE shape with room for the bin term must fit")
        failures += 1

    # ── the bin term is MULTIPLIED by n_boot, which is the measured defect ────
    # Before this was charged, all four of these returned True at an identical declared cost
    # of 4096 units while the wall clock spread 133x: 9.2 ms at h=1 against 1231.9 ms at
    # h=4096, rising to ~195x at n_boot = EVAL_MAX_RESAMPLES. The budget rated the worst of
    # them at 0.024% of its own ceiling. So: the maximum legal replicate count must FALL as h
    # grows, and the largest legal binned request must be refused at the largest legal h.
    checks += 1
    if not eval_resample_work_fits(
        EVAL_MAX_RESAMPLES, 1, 1, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH
    ):
        print("  ❌ 2^20 replicates of one sample into one bin is small and must fit")
        failures += 1
    checks += 1
    if eval_resample_work_fits(
        EVAL_MAX_RESAMPLES, 1, EVAL_MAX_BINS, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH
    ):
        print("  ❌ 2^20 replicates x 4096 bins is 2^32 bin-rebuilds and must be refused;")
        print("     charging n_bins only for its sign is charging it zero")
        failures += 1
    # Brier at that same shape does no binning at all and must stay legal, so the refusal
    # above cannot be a length ceiling in disguise.
    checks += 1
    if not eval_resample_work_fits(
        EVAL_MAX_RESAMPLES, 1, EVAL_MAX_BINS, EVAL_METRIC_BRIER, EVAL_BIN_EQUAL_WIDTH
    ):
        print("  ❌ a Brier bootstrap never bins and must not be charged for h")
        failures += 1
    # Monotone in h: the charge is a real function of the bin count, not a threshold at 4096.
    var prev_fit = True
    var non_monotone = 0
    var bin_sweep = List[Int]()
    bin_sweep.append(1)
    bin_sweep.append(16)
    bin_sweep.append(256)
    bin_sweep.append(1024)
    bin_sweep.append(4096)
    for t in range(len(bin_sweep)):
        var fits = eval_resample_work_fits(
            EVAL_MAX_RESAMPLES, 1, bin_sweep[t], EVAL_METRIC_ECE,
            EVAL_BIN_EQUAL_WIDTH,
        )
        if fits and not prev_fit:
            non_monotone += 1
        prev_fit = fits
    checks += 1
    if non_monotone != 0 or prev_fit:
        print("  ❌ the bin charge must be monotone in h and must refuse 2^20 x 4096;")
        print("     fits-at-4096 =", prev_fit, " non-monotone transitions =", non_monotone)
        failures += 1
    # A huge n_bins must not be able to wrap the per-replicate sum into a small number.
    checks += 1
    if eval_resample_work_fits(2, 2, 1 << 40, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ a 2^40 bin count must not fit; if it does, the per-replicate addition")
        print("     wrapped")
        failures += 1
    checks += 1
    if eval_resample_work_fits(
        3, 6148914691236517206, 1, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH
    ):
        print("  ❌ the wrapping-product operand must not fit the resample budget either")
        failures += 1

    checks += 1
    if eval_resample_work_fits(-1, 10, 10, EVAL_METRIC_BRIER, EVAL_BIN_EQUAL_WIDTH):
        print("  ❌ a negative replicate count is not a fit")
        failures += 1

    # ── the ceilings are derived, and the derivation is asserted ─────────────
    # EVAL_MAX_SAMPLES is (1 << 26) / 4: the tree's per-object element budget divided by
    # the four n-length arrays a driver here holds live at once (rule 1c). If someone
    # raises the constant without revisiting the array count, this fails.
    checks += 1
    if EVAL_MAX_SAMPLES != (1 << 26) // 4:
        print("  ❌ EVAL_MAX_SAMPLES is no longer (1 << 26) / 4:", EVAL_MAX_SAMPLES)
        failures += 1
    checks += 1
    if EVAL_MAX_BINS != 4096 or EVAL_MAX_RESAMPLES != (1 << 20):
        print("  ❌ a declared ceiling moved:", EVAL_MAX_BINS, EVAL_MAX_RESAMPLES)
        failures += 1
    checks += 1
    if EVAL_MAX_RESAMPLE_WORK != (1 << 32):
        print("  ❌ the work ceiling moved:", EVAL_MAX_RESAMPLE_WORK)
        failures += 1
    # DBL_EPSILON is the real one: 1 + eps != 1 while 1 + eps/2 == 1.
    checks += 1
    if not (1.0 + EVAL_DBL_EPSILON != 1.0 and 1.0 + EVAL_DBL_EPSILON / 2.0 == 1.0):
        print("  ❌ EVAL_DBL_EPSILON is not machine epsilon for Float64")
        failures += 1
    checks += 1
    if EVAL_LOG_LOSS_EPS != 1e-7:
        print("  ❌ the stated log-loss clamp is not 1e-7")
        failures += 1
    checks += 1
    if EVAL_METRIC_BASE_RATE != 3:
        print("  ❌ a metric id moved, which re-addresses every recorded result")
        failures += 1

    for _ in range(checks - failures):
        print("  ✅ evaluation.contract check")
    print("  [evaluation.contract] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_evaluation_contract failed")
