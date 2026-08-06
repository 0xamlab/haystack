"""
data_quality.leakage — what can be PROVEN from the data, and what is only suspicious.

Zero Python imports.

The distinction this module refuses to blur
------------------------------------------
A feature perfectly correlated with the target is SUSPICIOUS. It is not proof: a genuinely
predictive feature in a well-behaved problem can correlate at 0.99, and a leaked one can
correlate at 0.2 if it leaks only for a subpopulation. A feature computed FROM THE FUTURE
is proof — but only if something in the data says when each value was observed.

So this module reports two kinds of finding and never presents one as the other:

  PROVABLE FROM THE DATA ALONE
    * `proven_target_copy` — the feature column IS the target column: identical presence
      masks and, on every present row, equal values under `contract.dq_values_equal`. This
      is a fact about the columns, not an inference.
    * `proven_affine` — the feature is `a * target + b` for constants `a`, `b`, with `a`
      non-zero, verified on every compared row within a tolerance built from THAT ROW's OWN
      OBSERVED FEATURE VALUE. A non-constant deterministic function of the target cannot
      have been computed without the target.

  SUSPICIOUS, EXPLICITLY NOT PROOF
    * `abs_pearson` above `corr_threshold` sets `suspicious_correlation`. That flag means
      "look at this", and the verdict it produces is `DQ_LEAK_SUSPICIOUS`, never a proven
      one.
    * `missingness_agreement` above `missingness_threshold` sets `suspicious_missingness`:
      the feature being ABSENT predicts the class. Missingness-as-label is a real leak
      pattern and it is invisible to any check that looks only at values — but a feature
      can also be missing for reasons correlated with the outcome without leaking, so it
      is a flag and not a proof.

  NOT DETECTABLE HERE AT ALL, and said so
    * whether a value was computed from information unavailable at prediction time. There
      is no signature of that in a column of numbers. `LeakageReport.temporal_checked` is
      therefore ALWAYS False, so a clean data-only report cannot be read as "no leakage".
      `leakage_timing_flat` is the check that can prove it, it needs per-row timestamps the
      caller supplies, and it returns a DIFFERENT struct so the two claims can never be
      confused for one another.

Frozen kernels called
---------------------
EXISTING-FROZEN: `stat_tests.pearson_r` is the correlation. It is also a frozen
failure-as-value: it returns `CorrResult(0.0, 1.0)` both for `n < 3` and for a zero
denominator, so "the correlation is zero" and "there is no correlation to compute" are the
same return value. This module decides the preconditions FIRST — at least three compared
rows, and neither column constant — and sets `has_pearson` from that, never from the
number. `contract.dq_values_equal` is the identity; `contract.dq_ulp_tolerance` is the only
tolerance.

MISSING-DRIVER, which is this file: `feature_selection.f_test_scores` and
`information_gain` score a feature against a target, and a score is not a verdict. Nothing
in the tree separated provable from suspicious, and nothing reported the row a proof rests
on.

Why the affine proof does not use `regression.ols_simple`
--------------------------------------------------------
Least squares answers "what is the best affine fit", which is a different question from "is
this exactly affine". Its coefficients accumulate error over all `n` rows, so an exact
relation verified against them needs a tolerance that grows with `n` — and a tolerance that
grows with the number of OTHER rows is the defect rule 4b is about. Instead the candidate
map is derived from the two compared rows with the SMALLEST and LARGEST target value (the
best-conditioned pair available, and an exactly-affine relation gives the same map from any
pair) and then verified on every row with a per-row tolerance. `ols_simple` stays frozen
and reachable for callers who want the fit.

WHAT THE PER-ROW TOLERANCE IS SCALED BY, and the one wrong answer that hid here
------------------------------------------------------------------------------
Row `i`'s claim is `feature[i] == a * target[i] + b`. The quantity being judged is the
residual `feature[i] - predicted`, so the ONLY magnitude allowed into its tolerance is
`|feature[i]|` — the magnitude of that row's own observed value. It is emphatically NOT
`|a * target[i]| + |b|`, which is what shipped: those are the two INTERMEDIATES whose SUM
is the prediction, and when the fit is ill-conditioned they cancel. Measured on an epoch-
nanosecond target (`1.7e18 + [0, 1024, 2048, 3072]`) against `feature = [1, 50, 2, 90]`
the two intermediates are each ~4.93e16 while the prediction they sum to is ~29, so the
tolerance came out at 350 for a quantity of order 1 and a 42% prediction error was returned
as PROOF. That is rule 4b in a subtler dress: scaling by cancelling intermediates is
scaling by a magnitude that has nothing to do with the item being judged.

The consequence of the correct scaling, stated rather than hidden: a relation that IS
exactly affine in the reals but whose two-point fit cancels catastrophically in Float64
comes back `proven_affine = False` with `has_affine = True` and a large
`affine_max_residual`. That is a false NEGATIVE on a field whose whole meaning is "proven",
and it is the right direction to fail: the arithmetic available cannot verify the claim, so
the claim is not made. Such a feature is still reported — its `abs_pearson` is 1.0, so the
verdict is `DQ_LEAK_SUSPICIOUS`.

A CONSTANT feature is not an affine image, even though it fits one
-----------------------------------------------------------------
`f(t) = c` satisfies `a = 0`, `b = c` with residual exactly 0.0 on every row, so the
arithmetic "proves" it — and the finding is worthless: computing a constant column requires
zero knowledge of the target, which is the opposite of leakage. An all-default, all-zero or
all-one-value column is common in real tables, so returning the module's highest-severity
verdict for one hard-blocks a clean pipeline. The affine branch therefore requires the
feature to be non-constant on the compared rows, exactly as it already required the target
to be non-constant, and reports `feature_constant_on_compared` as the reason. `has_affine`
is False there: a degenerate map is not a map, and a 0.0 residual under a False proof flag
would read as the same self-contradiction in reverse.

Status and verdict codes: leakage owns 430-439 of the package's 400-449. A verdict is a
code from the same space, so a caller that logs one integer can always resolve it through
`contract.dq_status_name`.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_data_quality_leakage.mojo
benchmark: benchmarks/mojo_benchmarks/bench_data_quality.mojo
docs: gitbook/engine/data-quality.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from stat_tests import pearson_r

from data_quality.contract import (
    DQ_ERR_LENGTH_MISMATCH,
    DQ_OK,
    dq_is_finite,
    dq_mask_defect,
    dq_status_name,
    dq_ulp_tolerance,
    dq_values_equal,
)

# ── status / verdict codes: leakage owns 430-439 ──────────────────────────────
comptime DQ_LEAK_NONE: Int = 430
comptime DQ_LEAK_SUSPICIOUS: Int = 431
comptime DQ_LEAK_PROVEN_TARGET_COPY: Int = 432
comptime DQ_LEAK_PROVEN_AFFINE: Int = 433
comptime DQ_LEAK_INSUFFICIENT: Int = 434
comptime DQ_LEAK_PROVEN_FUTURE: Int = 435
comptime DQ_LEAK_ERR_THRESHOLD: Int = 436

# Ulps of slack allowed when verifying the affine candidate at one row. The prediction
# `a * t + b` is two operations away from `a` and `b`, each of which is three operations
# away from the two data points it was derived from, so eight ulps is the accumulated
# relative error and sixteen is that with margin. It is a COUNT, not a magnitude: the
# magnitude in the tolerance comes from the row's own prediction (see `dq_ulp_tolerance`).
comptime DQ_LEAK_AFFINE_ULPS: Int = 16

# Compared rows below which nothing can be said. Two points define any affine map, so two
# is the floor for a fit; `pearson_r` itself needs three.
comptime DQ_LEAK_MIN_AFFINE_ROWS: Int = 2
comptime DQ_LEAK_MIN_PEARSON_ROWS: Int = 3


struct LeakageReport(Copyable, Movable):
    """What the data alone says about a feature/target pair.

    `verdict` is the single code a caller branches on, and its precedence is fixed: a PROOF
    first (TARGET_COPY, then AFFINE), then SUSPICIOUS, then INSUFFICIENT, then NONE.

    INSUFFICIENT ranks BELOW suspicious deliberately. It means "no finding, and the values
    could not have produced one" — fewer than two compared rows, or a target that is
    constant across them. It must not suppress a missingness finding, which is computed
    over every live TARGET row and is therefore available precisely when the feature is so
    often absent that few rows are comparable. Ranking it above suspicion hid exactly that
    case: a feature missing for every positive row scored `missingness_agreement` 1.0 while
    the verdict said "too few comparable rows".

    Nothing here can ever produce `DQ_LEAK_PROVEN_FUTURE`; only `leakage_timing_flat` can.

    `has_affine` False means no candidate map was fitted at all, and the three reasons are
    readable from the other fields: fewer than `DQ_LEAK_MIN_AFFINE_ROWS` compared rows,
    `target_constant_on_compared`, or `feature_constant_on_compared`. A constant feature
    fits `a = 0` exactly and is deliberately not a finding — see the module docstring.

    Every Float64 field is paired with a `has_*` flag and holds 0.0 when the flag is False.
    """

    var status: Int
    var verdict: Int
    var n_rows: Int
    var n_compared: Int
    var n_present_pairs: Int
    var target_constant_on_compared: Bool
    var feature_constant_on_compared: Bool
    var proven_target_copy: Bool
    var proven_affine: Bool
    var has_affine: Bool
    var affine_slope: Float64
    var affine_intercept: Float64
    var has_affine_residual: Bool
    var affine_max_residual: Float64
    var affine_worst_row: Int
    var has_pearson: Bool
    var abs_pearson: Float64
    var suspicious_correlation: Bool
    var has_missingness_agreement: Bool
    var missingness_agreement: Float64
    var suspicious_missingness: Bool
    var temporal_checked: Bool

    def __init__(out self, status: Int, n_rows: Int):
        self.status = status
        self.verdict = status
        self.n_rows = n_rows
        self.n_compared = 0
        self.n_present_pairs = 0
        self.target_constant_on_compared = False
        self.feature_constant_on_compared = False
        self.proven_target_copy = False
        self.proven_affine = False
        self.has_affine = False
        self.affine_slope = 0.0
        self.affine_intercept = 0.0
        self.has_affine_residual = False
        self.affine_max_residual = 0.0
        self.affine_worst_row = -1
        self.has_pearson = False
        self.abs_pearson = 0.0
        self.suspicious_correlation = False
        self.has_missingness_agreement = False
        self.missingness_agreement = 0.0
        self.suspicious_missingness = False
        # Always False in this struct. A timestamp check is the only thing that can prove
        # future information, and it lives in `leakage_timing_flat`.
        self.temporal_checked = False


struct LeakageTimingReport(Copyable, Movable):
    """The one proof of future information: a feature observed after the target event.

    Separate from `LeakageReport` on purpose. A single struct carrying both would let a
    caller read a correlation flag and a timing flag as interchangeable evidence, and they
    are not: one is a hint and the other is a fact.

    `n_unrepresentable_lead_rows` counts the proven rows whose lead `feature_time -
    target_time` OVERFLOWS Float64. The proof survives (the row is still counted in
    `n_future_rows` and can still be the `first_future_row`); only the SIZE of the lead is
    unavailable, and when that count is non-zero `has_max_future_lead` is False, because the
    largest lead is then not a representable number. Reporting the largest FINITE lead
    instead would understate a lookahead by an unbounded factor — measured: one row leading
    by 2e308 alongside one leading by 10.0 reported `max_future_lead = 10.0`, a ten-unit
    clock skew, which is precisely the reading this field exists to distinguish from a real
    lookahead.
    """

    var status: Int
    var verdict: Int
    var n_rows: Int
    var n_compared: Int
    var n_future_rows: Int
    var n_simultaneous_rows: Int
    var n_unrepresentable_lead_rows: Int
    var first_future_row: Int
    var proven_future_information: Bool
    var has_max_future_lead: Bool
    var max_future_lead: Float64

    def __init__(out self, status: Int, n_rows: Int):
        self.status = status
        self.verdict = status
        self.n_rows = n_rows
        self.n_compared = 0
        self.n_future_rows = 0
        self.n_simultaneous_rows = 0
        self.n_unrepresentable_lead_rows = 0
        self.first_future_row = -1
        self.proven_future_information = False
        self.has_max_future_lead = False
        self.max_future_lead = 0.0


def leakage_status_name(code: Int) -> String:
    """Name for a status or verdict this module can return. One vocabulary, in `contract`.

    @capability leakage_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    return dq_status_name(code)


def _live(values: List[Float64], mask: List[Bool], index: Int) -> Bool:
    """Present and finite at `index`. Both lists are known to be `n_rows` long by then."""
    return mask[index] and dq_is_finite(values[index])


def leakage_scan_flat(
    feature: List[Float64], feature_mask: List[Bool],
    target: List[Float64], target_mask: List[Bool], n_rows: Int,
    corr_threshold: Float64, missingness_threshold: Float64,
) -> LeakageReport:
    """Every leakage check that can be made from a feature and a target alone.

    A row is COMPARED when the feature and the target are both present and finite there;
    every value-based finding is over those rows and `n_compared` says how many there were.
    A non-finite value is excluded rather than propagated: one NaN in a correlation makes
    the coefficient NaN, and a NaN defeats every `> threshold` test silently.

    Both thresholds must be in [0, 1] — a threshold outside that range would make a flag
    either unreachable or always set, and either reads as a check that ran.

    The affine proof needs BOTH columns non-constant on the compared rows and judges each
    row's residual against THAT ROW's own observed feature magnitude. Both conditions are
    the module docstring's subject; both were wrong answers before they were conditions.

    What the verdict does NOT mean: `DQ_LEAK_NONE` means "no data-alone signal", not "no
    leakage". `temporal_checked` is False in every report this function returns.

    @capability leakage_scan_flat
    complexity: O(n_rows log n_rows)
    counts:
    - n_rows == len(feature, feature_mask, target, target_mask) [kernel_validated]
    - dim n_rows [kernel_validated]
    @endcapability
    """
    var mask_defect = dq_mask_defect(feature_mask, n_rows)
    if mask_defect != DQ_OK:
        return LeakageReport(mask_defect, 0)
    if dq_mask_defect(target_mask, n_rows) != DQ_OK:
        return LeakageReport(DQ_ERR_LENGTH_MISMATCH, 0)
    if len(feature) != n_rows or len(target) != n_rows:
        return LeakageReport(DQ_ERR_LENGTH_MISMATCH, 0)
    if not dq_is_finite(corr_threshold) or corr_threshold < 0.0 or corr_threshold > 1.0:
        return LeakageReport(DQ_LEAK_ERR_THRESHOLD, n_rows)
    if (
        not dq_is_finite(missingness_threshold)
        or missingness_threshold < 0.0
        or missingness_threshold > 1.0
    ):
        return LeakageReport(DQ_LEAK_ERR_THRESHOLD, n_rows)

    var out = LeakageReport(DQ_OK, n_rows)

    # ── the compared rows, and the columns' own degeneracy ────────────────────
    var f_live = List[Float64]()
    var t_live = List[Float64]()
    var live_rows = List[Int]()
    for r in range(n_rows):
        if feature_mask[r] and target_mask[r]:
            out.n_present_pairs += 1
        if not _live(feature, feature_mask, r):
            continue
        if not _live(target, target_mask, r):
            continue
        f_live.append(feature[r])
        t_live.append(target[r])
        live_rows.append(r)
    out.n_compared = len(live_rows)

    # Named for the row set they describe. These are facts about the COMPARED rows only;
    # a target can be constant there and varied over the whole column, which is what
    # happens when a feature is absent for every row of one class.
    out.target_constant_on_compared = _all_equal(t_live)
    out.feature_constant_on_compared = _all_equal(f_live)

    # ── proof 1: the feature IS the target ────────────────────────────────────
    # Over ALL rows, not just the compared ones: identical columns must agree about
    # absence too. Requires at least one row present in both, so two all-null columns are
    # not "the same column" by vacuous agreement.
    if out.n_present_pairs > 0:
        var identical = True
        for r in range(n_rows):
            if feature_mask[r] != target_mask[r]:
                identical = False
                break
            if feature_mask[r] and not dq_values_equal(feature[r], target[r]):
                identical = False
                break
        out.proven_target_copy = identical

    # ── proof 2: the feature is an exact affine image of the target ───────────
    # BOTH columns must be non-constant on the compared rows. A constant target has no map
    # to fit; a constant FEATURE fits `a = 0, b = c` exactly and that relation carries no
    # information about the target at all (see the module docstring). Consulting the flag
    # that the pearson branch below already consults is the whole fix.
    if (
        out.n_compared >= DQ_LEAK_MIN_AFFINE_ROWS
        and not out.target_constant_on_compared
        and not out.feature_constant_on_compared
    ):
        var lo = 0
        var hi = 0
        for i in range(1, len(t_live)):
            if t_live[i] < t_live[lo]:
                lo = i
            if t_live[i] > t_live[hi]:
                hi = i
        var span = t_live[hi] - t_live[lo]
        if span != 0.0 and dq_is_finite(span):
            var slope = (f_live[hi] - f_live[lo]) / span
            var intercept = f_live[lo] - slope * t_live[lo]
            if dq_is_finite(slope) and dq_is_finite(intercept):
                out.has_affine = True
                out.affine_slope = slope
                out.affine_intercept = intercept
                var worst: Float64 = 0.0
                var worst_row = -1
                var exact = True
                for i in range(len(t_live)):
                    # The product is checked SEPARATELY from the sum, and that is load
                    # bearing twice over. It is a real condition — `slope * t_i` can
                    # overflow while the fit itself is finite — and observing the rounded
                    # product forbids the compiler from contracting `slope * t + intercept`
                    # into a fused multiply-add. An FMA rounds once where this rounds twice,
                    # and measured on the ill-conditioned epoch-nanosecond fit the two
                    # disagree: worst residual 54.0 unfused, 56.63268660610705 fused. Both
                    # are valid IEEE, which is exactly why the evaluation order has to be
                    # pinned here rather than left to the target's instruction set — a
                    # reported number that changes with the machine is not a result.
                    var scaled = slope * t_live[i]
                    if not dq_is_finite(scaled):
                        exact = False
                        continue
                    var predicted = scaled + intercept
                    if not dq_is_finite(predicted):
                        exact = False
                        continue
                    var residual = fabs(f_live[i] - predicted)
                    # Tolerance from the magnitude of the ONE quantity being judged: this
                    # row's own observed feature value. NOT `|slope*t_i| + |intercept|` —
                    # those are cancelling INTERMEDIATES, and sizing the slack by them
                    # accepted a 42% prediction error as an exact relation (module
                    # docstring, "WHAT THE PER-ROW TOLERANCE IS SCALED BY").
                    var tol = dq_ulp_tolerance(fabs(f_live[i]), DQ_LEAK_AFFINE_ULPS)
                    if residual > tol:
                        exact = False
                    if worst_row < 0 or residual > worst:
                        worst = residual
                        worst_row = live_rows[i]
                out.has_affine_residual = worst_row >= 0
                out.affine_max_residual = worst if worst_row >= 0 else 0.0
                out.affine_worst_row = worst_row
                out.proven_affine = exact and worst_row >= 0

    # ── suspicion 1: correlation. A number, not evidence. ────────────────────
    # `pearson_r` returns r = 0.0 for n < 3 and for a zero denominator, so both
    # preconditions are decided here and `has_pearson` never comes from the number.
    if (
        out.n_compared >= DQ_LEAK_MIN_PEARSON_ROWS
        and not out.target_constant_on_compared
        and not out.feature_constant_on_compared
    ):
        var corr = pearson_r(f_live, t_live)
        if dq_is_finite(corr.r):
            out.has_pearson = True
            out.abs_pearson = fabs(corr.r)
            out.suspicious_correlation = out.abs_pearson >= corr_threshold

    # ── suspicion 2: missingness predicts the class ───────────────────────────
    var agreement = _missingness_agreement(feature_mask, target, target_mask, n_rows)
    if agreement >= 0.0:
        out.has_missingness_agreement = True
        out.missingness_agreement = agreement
        out.suspicious_missingness = agreement >= missingness_threshold

    out.verdict = _verdict(out)
    return out^


def _all_equal(values: List[Float64]) -> Bool:
    """True when every value is the same under the package's identity. False when empty.

    Nothing is not one thing, so an empty list is NOT constant (rule 4).
    """
    if len(values) == 0:
        return False
    for i in range(1, len(values)):
        if not dq_values_equal(values[0], values[i]):
            return False
    return True


def _missingness_agreement(
    feature_mask: List[Bool], target: List[Float64], target_mask: List[Bool], n_rows: Int
) -> Float64:
    """How well "the feature is missing" predicts a BINARY target's class, or -1.0.

    -1.0 means the question does not apply, and it is a sentinel outside the [0.5, 1.0]
    range a real answer occupies rather than a plausible value. It is returned when the
    target is not binary over its live rows, when either the present or the absent group of
    the feature is empty (the rule would degenerate to "predict the majority", which
    measures the target's balance and not the feature's missingness), or when there are no
    live target rows at all.

    The number is the accuracy of the better of the two rules "absent -> class 1,
    present -> class 0" and its flip, so 0.5 is chance and 1.0 is perfect prediction.
    """
    var classes = List[Float64]()
    for r in range(n_rows):
        if not target_mask[r] or not dq_is_finite(target[r]):
            continue
        var seen = False
        for c in range(len(classes)):
            if dq_values_equal(classes[c], target[r]):
                seen = True
                break
        if not seen:
            classes.append(target[r])
            if len(classes) > 2:
                return -1.0
    if len(classes) != 2:
        return -1.0

    var absent_c1 = 0
    var present_c1 = 0
    var absent_c0 = 0
    var present_c0 = 0
    var n_live = 0
    for r in range(n_rows):
        if not target_mask[r] or not dq_is_finite(target[r]):
            continue
        n_live += 1
        var is_c1 = dq_values_equal(target[r], classes[1])
        if feature_mask[r]:
            if is_c1:
                present_c1 += 1
            else:
                present_c0 += 1
        else:
            if is_c1:
                absent_c1 += 1
            else:
                absent_c0 += 1
    if n_live == 0:
        return -1.0
    var n_absent = absent_c0 + absent_c1
    var n_present = present_c0 + present_c1
    if n_absent == 0 or n_present == 0:
        return -1.0
    var rule_a = Float64(absent_c1 + present_c0) / Float64(n_live)
    var rule_b = Float64(absent_c0 + present_c1) / Float64(n_live)
    return rule_a if rule_a > rule_b else rule_b


def _verdict(report: LeakageReport) -> Int:
    """The one code a caller branches on: proof, then suspicion, then insufficiency.

    See `LeakageReport` for why INSUFFICIENT ranks below SUSPICIOUS rather than above it.
    """
    if report.proven_target_copy:
        return DQ_LEAK_PROVEN_TARGET_COPY
    if report.proven_affine:
        return DQ_LEAK_PROVEN_AFFINE
    if report.suspicious_correlation or report.suspicious_missingness:
        return DQ_LEAK_SUSPICIOUS
    if (
        report.target_constant_on_compared
        or report.n_compared < DQ_LEAK_MIN_AFFINE_ROWS
    ):
        return DQ_LEAK_INSUFFICIENT
    return DQ_LEAK_NONE


def leakage_timing_flat(
    feature_time: List[Float64], target_time: List[Float64],
    observed_mask: List[Bool], n_rows: Int,
) -> LeakageTimingReport:
    """The only proof of future information: a feature observed AFTER the target event.

    `feature_time[r]` is when the feature's value became known and `target_time[r]` is when
    the target event occurred, on any common monotone scale the caller chooses (epoch
    seconds, a period index — the unit never enters the comparison). `observed_mask[r]`
    says whether row `r` has both timestamps; a row without them is not compared, and
    `n_compared` reports how many were.

    STRICTLY greater is the proof. `feature_time == target_time` is counted separately in
    `n_simultaneous_rows` and is NOT proof: two events stamped at the same instant have no
    order at that resolution, and calling a tie leakage would make the finding an artefact
    of the timestamp's precision.

    `max_future_lead` is the largest `feature_time - target_time` over the proven rows, so
    a caller can tell a one-second clock skew from a thirty-day lookahead. It is ABSENT in
    two distinct cases, and the two are distinguishable from `n_future_rows`:

      * `n_future_rows == 0` — no row proves anything, so there is no lead. Reporting 0.0
        here would mean simultaneity, which is a real and different finding.
      * `n_future_rows > 0` and `n_unrepresentable_lead_rows > 0` — at least one proven
        row's lead overflows Float64 (both timestamps finite, their difference not), so the
        largest lead is not a representable number. Reporting the largest FINITE lead
        instead is the wrong answer this field is most likely to be asked for: measured, a
        row leading by 2e308 beside a row leading by 10.0 reported 10.0.

    So `has_max_future_lead` is True only when at least one row proves lookahead AND every
    proven row's lead is representable. A lead of 0.0 under a True flag remains impossible.

    @capability leakage_timing_flat
    complexity: O(n_rows)
    counts:
    - n_rows == len(feature_time, target_time, observed_mask) [kernel_validated]
    - dim n_rows [kernel_validated]
    @endcapability
    """
    var mask_defect = dq_mask_defect(observed_mask, n_rows)
    if mask_defect != DQ_OK:
        return LeakageTimingReport(mask_defect, 0)
    if len(feature_time) != n_rows or len(target_time) != n_rows:
        return LeakageTimingReport(DQ_ERR_LENGTH_MISMATCH, 0)

    var out = LeakageTimingReport(DQ_OK, n_rows)
    var worst: Float64 = 0.0
    var have_worst = False
    for r in range(n_rows):
        if not observed_mask[r]:
            continue
        if not dq_is_finite(feature_time[r]) or not dq_is_finite(target_time[r]):
            continue
        out.n_compared += 1
        if feature_time[r] == target_time[r]:
            out.n_simultaneous_rows += 1
            continue
        if feature_time[r] <= target_time[r]:
            continue
        out.n_future_rows += 1
        if out.first_future_row < 0:
            out.first_future_row = r
        # Both timestamps are finite and strictly ordered, so `lead` is positive — but it
        # can still OVERFLOW (1e308 - -1e308 == +inf). Counted, never written to a slot.
        var lead = feature_time[r] - target_time[r]
        if not dq_is_finite(lead):
            out.n_unrepresentable_lead_rows += 1
            continue
        if not have_worst or lead > worst:
            worst = lead
            have_worst = True
    if out.n_compared == 0:
        out.verdict = DQ_LEAK_INSUFFICIENT
        return out^
    if out.n_future_rows > 0:
        out.proven_future_information = True
        out.verdict = DQ_LEAK_PROVEN_FUTURE
        # The MAXIMUM lead exists only if every proven row's lead is representable. One
        # overflowing row makes the maximum non-finite, and a non-finite maximum is absent
        # (slot 0.0), not "the largest of the others" — that understates without bound.
        if have_worst and out.n_unrepresentable_lead_rows == 0:
            out.has_max_future_lead = True
            out.max_future_lead = worst
    else:
        out.verdict = DQ_LEAK_NONE
    return out^
