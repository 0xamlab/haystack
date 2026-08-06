"""test_streaming_drift.mojo — known-value tests for the Page-Hinkley and DDM lanes.

Hand-written. Every reference is derivable with a calculator from the frozen update rules, which
are quoted here so a reader can check the arithmetic without opening another file:

  * `pandas_groupby.group_mean_update(mean, x, n)` is `mean + (x - mean) / n`.
  * Page-Hinkley then keeps `cum_up += x - mean - delta` with `min_up = min(min_up, cum_up)`,
    and the upward statistic is `cum_up - min_up`.

THE TRACE, hand-computed on `[0,0,0,0,0,4,4,4,4,4]` with `delta = 0`. The first five
observations leave every accumulator at exactly 0, because `x == mean == 0`. Then:

    k=6   mean = 0 + (4-0)/6 = 2/3          cum_up = 4 - 2/3   = 10/3      statistic = 10/3
    k=7   mean = 2/3 + (4-2/3)/7 = 8/7      cum_up = 10/3 + 20/7 = 130/21  statistic = 130/21
    k=8   mean = 8/7 + (4-8/7)/8 = 3/2      cum_up = 130/21 + 5/2         statistic = 365/42
    k=10  mean = 2                          cum_up = ... = 12.912698...

`min_up` stays 0 throughout because `cum_up` never goes below 0, so the statistic IS `cum_up`.
With `threshold = 5.0` the crossing is at k = 7, so `change_index` is 6 -- zero-based, and the
FIRST crossing, because detection is sticky. Both the index and the statistic are asserted.

DDM's references are the frozen rule's own algebra:

  * A series of all-correct predictions has `p = 0`, hence `s = 0`, hence no instant where a
    standard error exists -- so every level is 0 by construction, not by measurement.
  * 40 correct predictions followed by one error gives `p = 1/41` and `s > 0` at that instant,
    and the frozen rule compares `p + s > p_min + s_min + drift * s_min`. The minimum is
    recorded AT that same instant, so the two sides are equal but for `drift * s_min > 0`, and
    the level is 0. Before this module tracked the minimum only where `s > 0`, that first single
    error reported DRIFT on a `p` of 1/41.

The forged-struct block pins the non-finite hole: `page_hinkley_verdict` returned
`state.statistic` verbatim, and one non-finite field makes the WHOLE response a typed error.
"""
from streaming.contract import (
    STM_EMPTY,
    STM_ERR_COUNT,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_NON_FINITE,
    STM_ERR_PARAM_RANGE,
    STM_OK,
    stm_status_name,
    stm_tolerance,
)
from streaming.drift import (
    DDM_MIN_OBSERVATIONS,
    PageHinkleyState,
    ddm_levels,
    ddm_scan,
    page_hinkley_init,
    page_hinkley_resume,
    page_hinkley_scan,
    page_hinkley_scan_prefix,
    page_hinkley_step,
    page_hinkley_verdict,
)


def _close(got: Float64, want: Float64) -> Bool:
    """Equal within the package's own per-quantity allowance.

    `stm_tolerance(want, 0.0)` is `64 * DBL_EPSILON * |want|` -- scaled by THE NUMBER BEING
    JUDGED and nothing else. Not by a sum over the series, not by `1 + |want|`, and not by a
    tolerance the caller passed in.
    """
    var diff = got - want
    if diff < 0.0:
        diff = -diff
    return diff <= stm_tolerance(want, 0.0)


def _step_series() -> List[Float64]:
    """Five zeros then five fours: the series whose Page-Hinkley trace is hand-computed above."""
    var out = List[Float64]()
    for _ in range(5):
        out.append(0.0)
    for _ in range(5):
        out.append(4.0)
    return out^


def main() raises:
    print("Running streaming.drift known-value tests...")
    var passed = 0
    var failed = 0

    # ── 1. THE HAND-COMPUTED TRACE, step by step ────────────────────────────
    var series = _step_series()
    var state = page_hinkley_init()
    var stat_at_5 = 0.0
    var stat_at_6 = 0.0
    var stat_at_7 = 0.0
    var stat_at_8 = 0.0
    for i in range(len(series)):
        state = page_hinkley_step(state, series[i], 0.0, 5.0)
        if i == 4:
            stat_at_5 = state.statistic
        elif i == 5:
            stat_at_6 = state.statistic
        elif i == 6:
            stat_at_7 = state.statistic
        elif i == 7:
            stat_at_8 = state.statistic
    if stat_at_5 == 0.0 and _close(stat_at_6, 10.0 / 3.0) \
            and _close(stat_at_7, 130.0 / 21.0) and _close(stat_at_8, 365.0 / 42.0):
        passed += 1
        print("  ✅ the trace matches the hand arithmetic: statistic is 0.0 through five zeros,",
              "then 10/3 =", stat_at_6, ", 130/21 =", stat_at_7, ", 365/42 =", stat_at_8)
    else:
        failed += 1
        print("  ❌ the Page-Hinkley trace does not match:", stat_at_6, stat_at_7, stat_at_8)

    # ── 2. the crossing index is the FIRST one, zero-based ──────────────────
    #
    # 10/3 = 3.33 is below 5.0 and 130/21 = 6.19 is above it, so the crossing is at k = 7 and
    # `change_index` is 6. Detection is sticky, so it stays 6 for the remaining observations
    # rather than tracking the most recent crossing: the caller asked WHERE the change was.
    var verdict = page_hinkley_verdict(state, 5.0)
    if verdict.present and verdict.detected and verdict.change_index == 6 \
            and verdict.n_seen == 10 and verdict.threshold == 5.0 \
            and _close(verdict.statistic, 12.912698412698412):
        passed += 1
        print("  ✅ the first crossing is index 6 (k = 7, where 130/21 = 6.19 passes 5.0) and it",
              "stays 6 through five more observations; final statistic", verdict.statistic)
    else:
        failed += 1
        print("  ❌ the crossing index or final statistic is wrong:", verdict.change_index,
              verdict.statistic)

    # ── 3. a threshold nothing reaches is NOT detected, and -1 is not an index ─
    var quiet = page_hinkley_scan(series, 0.0, 100.0)
    if quiet.present and not quiet.detected and quiet.change_index == -1 \
            and _close(quiet.statistic, 12.912698412698412):
        passed += 1
        print("  ✅ at threshold 100.0 nothing is detected and change_index is -1 — never a",
              "subscript, and the statistic is still reported so a caller can see how close it got")
    else:
        failed += 1
        print("  ❌ a high threshold produced a detection:", quiet.detected, quiet.change_index)

    # ── 4. scan == step-by-step, and resume == scan over the concatenation ──
    var scanned = page_hinkley_scan(series, 0.0, 5.0)
    if scanned.detected == verdict.detected \
            and scanned.change_index == verdict.change_index \
            and scanned.statistic == verdict.statistic:
        passed += 1
        print("  ✅ page_hinkley_scan reproduces the step-by-step drive exactly")
    else:
        failed += 1
        print("  ❌ scan and step disagree")

    var first_half = List[Float64]()
    var second_half = List[Float64]()
    for i in range(len(series)):
        if i < 4:
            first_half.append(series[i])
        else:
            second_half.append(series[i])
    var resumed = page_hinkley_resume(
        page_hinkley_resume(page_hinkley_init(), first_half, 0.0, 5.0),
        second_half, 0.0, 5.0,
    )
    if resumed.valid and resumed.mean == state.mean and resumed.cum_up == state.cum_up \
            and resumed.min_up == state.min_up and resumed.cum_down == state.cum_down \
            and resumed.max_down == state.max_down and resumed.count == state.count \
            and resumed.change_index == state.change_index:
        passed += 1
        print("  ✅ resuming from a stored state over two chunks reproduces all five scalars of",
              "the one-pass state with ==, so the detector is EXACTLY resumable")
    else:
        failed += 1
        print("  ❌ the detector is not exactly resumable")

    # ── 5. a DOWNWARD shift is detected too ────────────────────────────────
    var down_series = List[Float64]()
    for _ in range(5):
        down_series.append(4.0)
    for _ in range(5):
        down_series.append(0.0)
    var down = page_hinkley_scan(down_series, 0.0, 5.0)
    if down.present and down.detected and down.change_index >= 5:
        passed += 1
        print("  ✅ a downward step is detected at index", down.change_index,
              "— the detector is two-sided, so a metric that collapses is not silence")
    else:
        failed += 1
        print("  ❌ a downward shift was missed")

    # ── 6. a series with no change is not detected ─────────────────────────
    var flat = List[Float64]()
    for i in range(200):
        flat.append(1.0 + Float64(i % 3) * 0.001)
    var flat_verdict = page_hinkley_scan(flat, 0.05, 5.0)
    if flat_verdict.present and not flat_verdict.detected:
        passed += 1
        print("  ✅ 200 observations of bounded noise around 1.0 produce NO detection at",
              "delta 0.05, threshold 5.0 — statistic", flat_verdict.statistic)
    else:
        failed += 1
        print("  ❌ a false positive on a flat series")

    # ── 7. absence: an empty series is not "no drift" ──────────────────────
    var fresh = page_hinkley_init()
    var refusals = 0
    if fresh.valid and not page_hinkley_verdict(fresh, 5.0).present \
            and page_hinkley_verdict(fresh, 5.0).status == STM_EMPTY \
            and page_hinkley_verdict(fresh, 5.0).statistic == 0.0 \
            and not page_hinkley_verdict(fresh, 5.0).detected:
        refusals += 1
    if not page_hinkley_scan(List[Float64](), 0.0, 5.0).present:
        refusals += 1
    if page_hinkley_scan_prefix(series, 11, 0.0, 5.0).status == STM_ERR_COUNT:
        refusals += 1
    if page_hinkley_scan_prefix(series, -3, 0.0, 5.0).status == STM_ERR_COUNT:
        refusals += 1
    if page_hinkley_scan(series, -1.0, 5.0).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if page_hinkley_scan(series, 0.0, 0.0).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if page_hinkley_scan(series, 0.0, Float64(1.0) / Float64(0.0)).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if page_hinkley_scan(series, Float64(0.0) / Float64(0.0), 5.0).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    var with_nan = series.copy()
    with_nan[3] = Float64(0.0) / Float64(0.0)
    if page_hinkley_scan(with_nan, 0.0, 5.0).status == STM_ERR_NON_FINITE:
        refusals += 1
    if refusals == 9:
        passed += 1
        print("  ✅ 9 unusable requests are refused or reported ABSENT: a detector that has seen",
              "nothing is", stm_status_name(STM_EMPTY),
              "and NOT 'no drift' — the dashboard-goes-green-because-input-stopped failure")
    else:
        failed += 1
        print("  ❌ only", refusals, "of 9 refusals fired")

    # ── 8. DDM: all-correct is level 0 everywhere, BY CONSTRUCTION ─────────
    #
    # p = 0 gives s = sqrt(0 * 1 / n) = 0, so there is no instant at which a standard error
    # exists, and this module reports 0 rather than feeding the frozen rule a minimum that means
    # "no information". Derivable without running anything.
    var all_correct = List[Bool]()
    for _ in range(60):
        all_correct.append(False)
    var correct_levels = ddm_levels(all_correct, 2.0, 3.0)
    var nonzero = 0
    for i in range(len(correct_levels)):
        if correct_levels[i] != 0:
            nonzero += 1
    var correct_verdict = ddm_scan(all_correct, 2.0, 3.0)
    if len(correct_levels) == 60 and nonzero == 0 and correct_verdict.present \
            and not correct_verdict.detected and correct_verdict.statistic == 0.0:
        passed += 1
        print("  ✅ 60 correct predictions give level 0 at all 60 instants and no drift —",
              "p = 0 means s = 0 means no standard error exists to compare against")
    else:
        failed += 1
        print("  ❌ a perfect series reported drift:", nonzero, correct_verdict.detected)

    # ── 9. THE DEGENERATE MINIMUM. One error after 40 correct is NOT drift. ─
    #
    # Measured before this module tracked the minimum only where s > 0: 40 correct predictions
    # followed by errors reported DRIFT at the very first error, index 40, on a p of 1/41.
    var one_error = List[Bool]()
    for _ in range(40):
        one_error.append(False)
    one_error.append(True)
    for _ in range(9):
        one_error.append(False)
    var one_levels = ddm_levels(one_error, 2.0, 3.0)
    var one_verdict = ddm_scan(one_error, 2.0, 3.0)
    if len(one_levels) == 50 and one_levels[40] == 0 and not one_verdict.detected \
            and one_verdict.change_index == -1:
        passed += 1
        print("  ✅ 40 correct then ONE error reports level", one_levels[40], "at index 40 and no",
              "drift — the frozen rule is no longer handed an s_min of 0 that makes any single",
              "error satisfy p + s > p_min")
    else:
        failed += 1
        print("  ❌ a single error after a perfect run reported drift:", one_levels[40])

    # ── 10. a real regime change IS detected ───────────────────────────────
    var regime = List[Bool]()
    for i in range(80):
        regime.append(i % 10 == 0)
    for i in range(80):
        regime.append(i % 10 != 0)
    var regime_verdict = ddm_scan(regime, 2.0, 3.0)
    var regime_levels = ddm_levels(regime, 2.0, 3.0)
    var worst = 0
    for i in range(len(regime_levels)):
        if regime_levels[i] > worst:
            worst = regime_levels[i]
    if regime_verdict.present and regime_verdict.detected \
            and regime_verdict.change_index >= 80 \
            and regime_verdict.statistic == 2.0 and worst == 2 \
            and regime_levels[regime_verdict.change_index] == 2:
        passed += 1
        print("  ✅ an error rate rising from 10% to 90% at index 80 is detected at index",
              regime_verdict.change_index, "with the frozen rule's level 2, and the level at",
              "that index really is 2 — the verdict and the trace agree")
    else:
        failed += 1
        print("  ❌ a real regime change was missed:", regime_verdict.detected,
              regime_verdict.change_index, worst)

    # ── 11. DDM absence and refusals are distinguishable from all-zeros ────
    var short = List[Bool]()
    for _ in range(DDM_MIN_OBSERVATIONS - 1):
        short.append(True)
    var ddm_refusals = 0
    if not ddm_scan(short, 2.0, 3.0).present \
            and ddm_scan(short, 2.0, 3.0).status == STM_EMPTY \
            and len(ddm_levels(short, 2.0, 3.0)) == 0:
        ddm_refusals += 1
    if len(ddm_levels(regime, 3.0, 2.0)) == 0 \
            and ddm_scan(regime, 3.0, 2.0).status == STM_ERR_PARAM_RANGE:
        ddm_refusals += 1
    if len(ddm_levels(regime, 0.0, 3.0)) == 0:
        ddm_refusals += 1
    if len(ddm_levels(regime, Float64(0.0) / Float64(0.0), 3.0)) == 0:
        ddm_refusals += 1
    if ddm_refusals == 4 and len(correct_levels) == 60:
        passed += 1
        print("  ✅ a too-short series, a drift level below the warning level, a zero warning",
              "level and a NaN level all return an EMPTY list — distinguishable from the",
              "60 zeros above, which say 'checked at every instant, nothing wrong'")
    else:
        failed += 1
        print("  ❌ only", ddm_refusals, "of 4 DDM refusals fired")

    # ── 12. A FORGED STATE: the non-finite that becomes a typed error ──────
    #
    # `page_hinkley_verdict` returned `state.statistic` VERBATIM, and `PageHinkleyState` is
    # decoded from caller JSON. One non-finite field makes the WHOLE response a typed error
    # rather than one field being wrong, so a forged NaN statistic took the response down with
    # it. Every scalar is checked, not just the one returned, because `page_hinkley_step` folds
    # all five into the next statistic.
    var nan = Float64(0.0) / Float64(0.0)
    var inf = Float64(1.0) / Float64(0.0)
    var nan_stat = PageHinkleyState(
        0.0, 0.0, 0.0, 0.0, 0.0, 5, False, -1, nan, STM_OK, True
    )
    var inf_cum = PageHinkleyState(
        0.0, inf, 0.0, 0.0, 0.0, 5, False, -1, 1.0, STM_OK, True
    )
    var v_nan = page_hinkley_verdict(nan_stat, 5.0)
    var v_inf = page_hinkley_verdict(inf_cum, 5.0)
    if not v_nan.present and v_nan.status == STM_ERR_NON_FINITE \
            and v_nan.statistic == 0.0 \
            and not v_inf.present and v_inf.status == STM_ERR_NON_FINITE \
            and not page_hinkley_step(nan_stat, 1.0, 0.0, 5.0).valid \
            and not page_hinkley_resume(nan_stat, series, 0.0, 5.0).valid:
        passed += 1
        print("  ✅ a forged NaN statistic and an infinite cum_up are refused under",
              stm_status_name(STM_ERR_NON_FINITE),
              "by verdict, step and resume, and the value slot comes back as a representable 0.0")
    else:
        failed += 1
        print("  ❌ a non-finite state field reached the response:", v_nan.statistic, v_nan.status)

    # ── 13. an INCOHERENT state is refused, so a reported index means something ─
    var impossible_index = PageHinkleyState(
        0.0, 0.0, 0.0, 0.0, 0.0, 3, True, 900, 1.0, STM_OK, True
    )
    var undetected_index = PageHinkleyState(
        0.0, 0.0, 0.0, 0.0, 0.0, 3, False, 7, 1.0, STM_OK, True
    )
    var negative_count = PageHinkleyState(
        0.0, 0.0, 0.0, 0.0, 0.0, -5, False, -1, 1.0, STM_OK, True
    )
    if not page_hinkley_verdict(impossible_index, 5.0).present \
            and page_hinkley_verdict(impossible_index, 5.0).status == STM_ERR_PARAM_RANGE \
            and not page_hinkley_verdict(undetected_index, 5.0).present \
            and not page_hinkley_verdict(negative_count, 5.0).present \
            and not page_hinkley_step(impossible_index, 1.0, 0.0, 5.0).valid:
        passed += 1
        print("  ✅ change_index 900 after 3 observations, a change_index of 7 with detected",
              "False, and a negative count are all refused — a returned change_index now names",
              "an observation that arrived")
    else:
        failed += 1
        print("  ❌ an incoherent state was echoed back")

    # ── 14. an invalid state propagates as a refusal, never as a number ────
    if not page_hinkley_step(_bad_state(), 1.0, 0.0, 5.0).valid \
            and page_hinkley_step(_bad_state(), 1.0, 0.0, 5.0).status \
                == STM_ERR_INVALID_SKETCH \
            and not page_hinkley_verdict(_bad_state(), 5.0).present:
        passed += 1
        print("  ✅ an invalid state is refused under", stm_status_name(STM_ERR_INVALID_SKETCH),
              "rather than read")
    else:
        failed += 1
        print("  ❌ an invalid state was read")

    print("  [streaming.drift] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_streaming_drift: " + String(failed) + " failure(s)")


def _bad_state() -> PageHinkleyState:
    """A state marked invalid, the way every refusal in this module returns one."""
    return PageHinkleyState(0.0, 0.0, 0.0, 0.0, 0.0, 0, False, -1, 0.0, 373, False)
