"""test_streaming_windows.mojo — known-value tests for the windowed-aggregate lane.

Hand-written, on ONE eight-element series a reader can work through on paper:

    v = [3, 1, 4, 1, 5, 9, 2, 6],  window = 3

    windows:      [3,1,4]  [1,4,1]  [4,1,5]  [1,5,9]  [5,9,2]  [9,2,6]
    minimum:         1        1        1        1        2        2
    maximum:         4        4        5        9        9        9
    range:           3        3        4        8        7        7
    sum:             8        6       10       15       16       17

so `window_mean` is `[8/3, 2, 10/3, 5, 16/3, 17/3]` and every one of those is asserted as the
exact quotient rather than as a decimal literal. There are six positions, not eight: `8 - 3 + 1`.

`window_summary_prefix(v, 8, 3)` summarises the LAST window, `[9, 2, 6]`, through the frozen
Welford pair `m2 += (x - old_mean) * (x - new_mean)`:

    j=0  x=9  mean = 9                  m2 = 0
    j=1  x=2  mean = 9 + (2-9)/2 = 5.5  m2 = (2-9)(2-5.5) = 24.5
    j=2  x=6  mean = 5.5 + 0.5/3        m2 = 24.5 + 0.5 * (6 - 17/3)

giving mean 17/3, population variance `m2 / 3`, minimum 2 and maximum 9.

The EWM series come out of the frozen updates, which are exact binary fractions at alpha = 0.5:

    ema:  [3, 2, 3, 2, 3.5, 6.25, 4.125, 5.0625]
    emv:  [0, 1, 1.5, 1.75, 3.125, 9.125, 9.078125, 5.41796875]

from `ema = 0.5*x + 0.5*ema_prev` and `emv = 0.5*(emv_prev + 0.5*(x - ema_prev)^2)`, applied in
THAT ORDER -- variance against the PREVIOUS mean, which is what the frozen update requires.
Every one of those sixteen numbers is exact in binary floating point, so they are asserted with
`==` and no tolerance at all.

The forged-struct block pins `window_summary_std`, which is handed a `WindowSummary` decoded from
caller JSON: `NaN <= 0.0` is FALSE, so a forged NaN variance reached `sqrt` and came back NaN,
and one non-finite field makes the WHOLE response a typed error.
"""
from std.math import sqrt

from streaming.contract import (
    MAX_STM_WINDOW,
    STM_EMPTY,
    STM_ERR_COUNT,
    STM_ERR_NON_FINITE,
    STM_ERR_PARAM_RANGE,
    STM_ERR_WINDOW,
    STM_ERR_WORK_BUDGET,
    STM_OK,
    stm_status_name,
    stm_tolerance,
)
from streaming.windows import (
    WINDOW_MAX_SPAN,
    WindowSummary,
    ewma_series,
    ewmvar_series,
    window_max,
    window_mean,
    window_min,
    window_positions,
    window_range,
    window_std,
    window_summary_prefix,
    window_summary_std,
)


fn _probe() -> List[Float64]:
    """[3, 1, 4, 1, 5, 9, 2, 6] — the series whose every window is tabulated above."""
    var out = List[Float64]()
    out.append(3.0)
    out.append(1.0)
    out.append(4.0)
    out.append(1.0)
    out.append(5.0)
    out.append(9.0)
    out.append(2.0)
    out.append(6.0)
    return out^


fn _matches(series: List[Float64], want: List[Float64]) -> Int:
    """How many positions differ EXACTLY. -1 when the lengths disagree."""
    if len(series) != len(want):
        return -1
    var diffs = 0
    for i in range(len(want)):
        if series[i] != want[i]:
            diffs += 1
    return diffs


fn _of(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64, f: Float64) -> List[Float64]:
    """Six hand-written expected values, in window order."""
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    out.append(e)
    out.append(f)
    return out^


fn main() raises:
    print("Running streaming.windows known-value tests...")
    var passed = 0
    var failed = 0
    var v = _probe()

    # ── 1. the restated ceiling still equals the contract's ─────────────────
    if WINDOW_MAX_SPAN == MAX_STM_WINDOW:
        passed += 1
        print("  ✅ this module's window ceiling still equals the contract's:", WINDOW_MAX_SPAN)
    else:
        failed += 1
        print("  ❌ the restated window ceiling drifted from the contract's")

    # ── 2. the hand-tabulated minimum, maximum and range ────────────────────
    var mins = window_min(v, 3)
    var maxs = window_max(v, 3)
    var rng = window_range(v, 3)
    if _matches(mins.values, _of(1.0, 1.0, 1.0, 1.0, 2.0, 2.0)) == 0 \
            and _matches(maxs.values, _of(4.0, 4.0, 5.0, 9.0, 9.0, 9.0)) == 0 \
            and _matches(rng.values, _of(3.0, 3.0, 4.0, 8.0, 7.0, 7.0)) == 0 \
            and mins.n_positions == 6 and mins.window == 3 and mins.valid:
        passed += 1
        print("  ✅ window_min/max/range on [3,1,4,1,5,9,2,6] at window 3 are exactly the",
              "tabulated [1,1,1,1,2,2] / [4,4,5,9,9,9] / [3,3,4,8,7,7] over 6 positions")
    else:
        failed += 1
        print("  ❌ a windowed extreme is wrong:", mins.values[0], maxs.values[0], rng.values[0])

    # ── 3. the monotonic deque agrees with a brute-force rescan ────────────
    #
    # The deque is O(n) and the rescan is O(n*w); they must agree at every position and every
    # window width, which is the only thing that makes the O(n) version worth having.
    var deque_diffs = 0
    for w in range(1, 9):
        var fast_min = window_min(v, w)
        var fast_max = window_max(v, w)
        for start in range(len(v) - w + 1):
            var lo = v[start]
            var hi = v[start]
            for j in range(1, w):
                if v[start + j] < lo:
                    lo = v[start + j]
                if v[start + j] > hi:
                    hi = v[start + j]
            if fast_min.values[start] != lo or fast_max.values[start] != hi:
                deque_diffs += 1
    if deque_diffs == 0:
        passed += 1
        print("  ✅ the O(n) monotonic deque agrees with an O(n*w) rescan at every position for",
              "every window width 1..8 — 36 comparisons, 0 differences")
    else:
        failed += 1
        print("  ❌ the deque disagrees with a rescan at", deque_diffs, "positions")

    # ── 4. the frozen rolling mean, as exact quotients ─────────────────────
    var means = window_mean(v, 3)
    if _matches(means.values, _of(8.0 / 3.0, 2.0, 10.0 / 3.0, 5.0, 16.0 / 3.0, 17.0 / 3.0)) == 0 \
            and means.window == 3 and means.n_positions == 6:
        passed += 1
        print("  ✅ window_mean is exactly [8/3, 2, 10/3, 5, 16/3, 17/3]:", means.values[0],
              means.values[1], means.values[2], means.values[3], means.values[4], means.values[5])
    else:
        failed += 1
        print("  ❌ the frozen rolling mean disagrees with the hand sums")

    # ── 5. the frozen rolling std is the POPULATION std of each window ─────
    var stds = window_std(v, 3)
    var std_diffs = 0
    for start in range(6):
        var s = 0.0
        for j in range(3):
            s += v[start + j]
        var mu = s / 3.0
        var ss = 0.0
        for j in range(3):
            ss += (v[start + j] - mu) * (v[start + j] - mu)
        var want = sqrt(ss / 3.0)
        var diff = stds.values[start] - want
        if diff < 0.0:
            diff = -diff
        if diff > stm_tolerance(want, 0.0):
            std_diffs += 1
    if std_diffs == 0 and stds.n_positions == 6:
        passed += 1
        print("  ✅ window_std matches a per-window population standard deviation computed here",
              "at all 6 positions; window 0 is", stds.values[0], "for mean 8/3")
    else:
        failed += 1
        print("  ❌ the frozen rolling std disagrees at", std_diffs, "positions")

    # ── 6. THE HAND-COMPUTED WELFORD SUMMARY of the last window ───────────
    var summary = window_summary_prefix(v, 8, 3)
    var want_mean = 17.0 / 3.0
    var want_m2 = 24.5 + 0.5 * (6.0 - 17.0 / 3.0)
    var want_var = want_m2 / 3.0
    if summary.present and summary.count == 3 and summary.minimum == 2.0 \
            and summary.maximum == 9.0 and summary.mean == want_mean \
            and summary.variance == want_var \
            and window_summary_std(summary) == sqrt(want_var):
        passed += 1
        print("  ✅ the last window [9,2,6] has mean", summary.mean, "= 17/3, population variance",
              summary.variance, ", minimum 2, maximum 9 and std", window_summary_std(summary),
              "— every one of them the frozen Welford pair's own arithmetic")
    else:
        failed += 1
        print("  ❌ the Welford summary is wrong:", summary.mean, summary.variance)

    # ── 7. a one-observation window has a variance of 0.0 and IS an answer ─
    var single = window_summary_prefix(v, 8, 1)
    if single.present and single.count == 1 and single.mean == 6.0 \
            and single.variance == 0.0 and single.minimum == 6.0 \
            and single.maximum == 6.0 and window_summary_std(single) == 0.0:
        passed += 1
        print("  ✅ a one-observation window is present with mean 6.0 and variance 0.0, and its",
              "standard deviation is 0.0 — a computed zero, which is why absence returns -1.0")
    else:
        failed += 1
        print("  ❌ a single-observation window was reported absent or wrong")

    # ── 8. THE HAND-COMPUTED EWM SERIES, exact binary fractions ───────────
    var ema = ewma_series(v, 0.5)
    var emv = ewmvar_series(v, 0.5)
    var want_ema = List[Float64]()
    want_ema.append(3.0)
    want_ema.append(2.0)
    want_ema.append(3.0)
    want_ema.append(2.0)
    want_ema.append(3.5)
    want_ema.append(6.25)
    want_ema.append(4.125)
    want_ema.append(5.0625)
    var want_emv = List[Float64]()
    want_emv.append(0.0)
    want_emv.append(1.0)
    want_emv.append(1.5)
    want_emv.append(1.75)
    want_emv.append(3.125)
    want_emv.append(9.125)
    want_emv.append(9.078125)
    want_emv.append(5.41796875)
    if _matches(ema.values, want_ema) == 0 and _matches(emv.values, want_emv) == 0 \
            and ema.window == 0 and emv.window == 0 \
            and ema.n_positions == 8 and emv.present[0]:
        passed += 1
        print("  ✅ ewma_series and ewmvar_series match all 16 hand-computed exact binary",
              "fractions with ==; window is reported as 0 because an EWMA has no finite window")
    else:
        failed += 1
        print("  ❌ an EWM value is wrong:", ema.values[7], emv.values[7])

    # The ORDER matters and is asserted: variance advances against the PREVIOUS mean. Advancing
    # the mean first would give 0.5*(0 + 0.5*(1-2)^2) = 0.25 at position 1, not 1.0.
    if emv.values[1] == 1.0 and emv.values[1] != 0.25:
        passed += 1
        print("  ✅ emv[1] is 1.0 and not 0.25 — the variance advances against the mean from",
              "BEFORE the observation, which is the order the frozen update requires")
    else:
        failed += 1
        print("  ❌ the EWM variance is centred on the wrong mean:", emv.values[1])

    # ── 9. window > n has NO windows, and that is not a refusal ───────────
    var too_wide = window_mean(v, 9)
    if too_wide.valid and too_wide.n_positions == 0 and len(too_wide.values) == 0 \
            and too_wide.status == STM_OK and too_wide.window == 9 \
            and window_positions(8, 9) == 0 and window_positions(8, 3) == 6 \
            and window_positions(8, 0) == 0 and window_positions(8, -3) == 0:
        passed += 1
        print("  ✅ window 9 over 8 observations is VALID with 0 positions — the request was",
              "fine and there are no windows in the data, which is a different fact from a",
              "refusal, and window_positions returns 0 rather than a negative count")
    else:
        failed += 1
        print("  ❌ a too-wide window was refused instead of reported empty")

    # ── 10. every refusal typed, and a non-finite refused at the door ──────
    var nan = Float64(0.0) / Float64(0.0)
    var inf = Float64(1.0) / Float64(0.0)
    var with_nan = v.copy()
    with_nan[4] = nan
    var refusals = 0
    if window_min(with_nan, 3).status == STM_ERR_NON_FINITE \
            and not window_min(with_nan, 3).valid:
        refusals += 1
    if window_mean(with_nan, 3).status == STM_ERR_NON_FINITE:
        refusals += 1
    if window_std(with_nan, 3).status == STM_ERR_NON_FINITE:
        refusals += 1
    if ewma_series(with_nan, 0.5).status == STM_ERR_NON_FINITE:
        refusals += 1
    if window_min(v, 0).status == STM_ERR_WINDOW:
        refusals += 1
    if window_min(v, -3).status == STM_ERR_WINDOW:
        refusals += 1
    if window_min(v, WINDOW_MAX_SPAN + 1).status == STM_ERR_WINDOW:
        refusals += 1
    if ewma_series(v, 0.0).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if ewma_series(v, 1.0).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if ewma_series(v, nan).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if ewmvar_series(v, inf).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if window_summary_prefix(v, 9, 3).status == STM_ERR_COUNT:
        refusals += 1
    if window_summary_prefix(v, -3, 3).status == STM_ERR_COUNT:
        refusals += 1
    if window_summary_prefix(v, 0, 3).status == STM_EMPTY:
        refusals += 1
    if window_summary_prefix(v, 3, 4).status == STM_ERR_WINDOW:
        refusals += 1
    if window_summary_prefix(with_nan, 8, 5).status == STM_ERR_NON_FINITE:
        refusals += 1
    if refusals == 16:
        passed += 1
        print("  ✅ 16 unusable requests are refused with typed statuses. A NaN inside a",
              "monotonic deque is the silent case — every comparison against it is false, so it",
              "is never evicted and never wins, and the reported minimum just skips a position")
    else:
        failed += 1
        print("  ❌ only", refusals, "of 16 refusals fired")

    # ── 11. THE WORK BUDGET IS A PRODUCT for std and a sum for mean ────────
    #
    # `window_std` is the frozen O(n*window) exact recompute and `window_mean` is the frozen O(n)
    # sliding sum. Charging `n + window` for the first is how a 1,000,000 x 500,000 request looks
    # cheap and then runs for minutes. Asserted as a BEHAVIOURAL difference on the same input:
    # the same shape is accepted by one and refused by the other.
    var wide = List[Float64]()
    for i in range(40000):
        wide.append(Float64(i % 97))
    var mean_ok = window_mean(wide, 20000)
    var std_refused = window_std(wide, 20000)
    if mean_ok.valid and mean_ok.n_positions == 20001 \
            and not std_refused.valid and std_refused.status == STM_ERR_WORK_BUDGET:
        passed += 1
        print("  ✅ 40,000 observations at window 20,000: the O(n) mean is computed (20,001",
              "positions) and the O(n*w) std is REFUSED under",
              stm_status_name(STM_ERR_WORK_BUDGET),
              "— 800,000,000 element visits behind an identical-looking request")
    else:
        failed += 1
        print("  ❌ the two costs are charged the same:", mean_ok.valid, std_refused.status)

    # ── 12. presence flags are uniformly True in a valid series ────────────
    var all_true = True
    for i in range(len(mins.present)):
        if not mins.present[i]:
            all_true = False
    if all_true and len(mins.present) == len(mins.values) \
            and len(mins.present) == mins.n_positions:
        passed += 1
        print("  ✅ every present flag in a valid series is True and the flag list is exactly as",
              "long as the value list — the shape is checkable, not merely documented")
    else:
        failed += 1
        print("  ❌ the presence flags and the values disagree in length or content")

    # ── 13. A FORGED SUMMARY: the non-finite that becomes a typed error ────
    #
    # `WindowSummary` is decoded from caller JSON when it is handed back to
    # `window_summary_std`. `NaN <= 0.0` is FALSE, so a forged NaN variance sailed past the
    # non-positive guard, reached `sqrt`, and came back NaN -- and one non-finite field makes the
    # WHOLE response a typed error rather than one field being wrong. -1.0 is the refusal because
    # a standard deviation is never negative, where 0.0 is the commonest real answer there is.
    var nan_var = WindowSummary(5.0, nan, 2.0, 9.0, 3, True, STM_OK)
    var inf_var = WindowSummary(5.0, inf, 2.0, 9.0, 3, True, STM_OK)
    var nan_bound = WindowSummary(5.0, 1.0, nan, 9.0, 3, True, STM_OK)
    var absent = WindowSummary(0.0, 0.0, 0.0, 0.0, 0, False, STM_EMPTY)
    var wild_negative = WindowSummary(5.0, -1000000.0, 2.0, 9.0, 3, True, STM_OK)
    var rounding_negative = WindowSummary(5.0, -1.0e-30, 2.0, 9.0, 3, True, STM_OK)
    var negative_count = WindowSummary(5.0, 4.0, 2.0, 9.0, -3, True, STM_OK)
    if window_summary_std(nan_var) == -1.0 and window_summary_std(inf_var) == -1.0 \
            and window_summary_std(nan_bound) == -1.0 \
            and window_summary_std(absent) == -1.0 \
            and window_summary_std(wild_negative) == -1.0 \
            and window_summary_std(negative_count) == -1.0 \
            and window_summary_std(rounding_negative) == 0.0:
        passed += 1
        print("  ✅ a NaN variance, an infinite variance, a NaN bound, an absent summary, a",
              "variance of -1e6 and a count of -3 all return -1.0, while a variance of -1e-30 —",
              "a rounding artefact inside the squared range — is the real 0.0")
    else:
        failed += 1
        print("  ❌ a forged summary produced a non-finite or a plausible 0.0:",
              window_summary_std(nan_var), window_summary_std(wild_negative))

    print("  [streaming.windows] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_streaming_windows: " + String(failed) + " failure(s)")
