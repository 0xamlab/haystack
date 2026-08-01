"""test_discrete_event_warmup.mojo — known-value tests for MSER transient detection.

Hand-written. Every MSER score below is computed from the definition

    MSER(d) = (1/(m-d)^2) * sum_{i>=d} (b_i - mean_{i>=d})^2

on a series short enough to do on paper, so the rule is checked against arithmetic rather than
against itself.

Case A — a step transient, batch size 1
---------------------------------------
    obs = [100, 100, 100, 100, 20, 20, 20, 20, 20, 20, 20, 20]      m = 12, boundary = 6

    d = 4 retains eight identical 20s: the deviation sum is 0, so MSER(4) = 0 — the minimum.
    d = 5 and d = 6 also score 0, so the tie rule matters: the SMALLEST d wins, and the answer
    must be 4, not 6. A rule that took the largest would discard two extra observations for no
    gain, and would also land on the boundary and refuse.

    Expected: 4 batches discarded, 4 observations discarded, 8 retained, steady mean exactly
    20.0, MSER exactly 0.0, and `at_search_boundary` False.

Case B — one outlier at the front
---------------------------------
    obs = [10, 0, 0, 0, 0, 0, 0, 0]      m = 8, boundary = 4

    d = 0: mean 1.25, deviation sum = (10-1.25)^2 + 7*(1.25)^2 = 76.5625 + 10.9375 = 87.5,
           MSER(0) = 87.5/64 = 1.3671875
    d = 1: seven zeros, deviation sum 0, MSER(1) = 0 — the minimum.

    Expected: exactly one observation discarded, steady mean 0.0. This is also the case that
    proves a steady mean of ZERO is reported as an ANSWER (`has_estimate` True) and not as an
    absence: 0.0 with the flag set is a real mean, and that distinction is the whole point.

Case C — a series that never settles, and the boundary refusal
--------------------------------------------------------------
    obs = [0, 1, 2, ..., 11]      m = 12, boundary = 6

    For consecutive integers, sum (b_i - mean)^2 over k values is k(k^2-1)/12, so
    MSER(d) = (k^2-1)/(12k) with k = 12-d. That is strictly DECREASING in d, so the minimum sits
    exactly on the boundary d = 6, where k = 6 and MSER = 35/72 = 0.4861111111111111 — asserted
    to the last digit.

    A trend never settles, so there is nothing to truncate TO. Expected: status
    `DE_ERR_NO_STEADY_STATE`, `at_search_boundary` True, and `has_estimate` FALSE with a 0.0
    value slot. Returning the mean of the last six values would be the silent-wrong-answer: a
    plausible number for a quantity that does not exist.

Case D — the ragged tail nobody expects
---------------------------------------
    103 observations at batch size 5 make 20 whole batches and leave 3 over. Those 3 belong to
    no batch mean and are reported in `n_tail_dropped`, because an estimator that silently
    trimmed its own input cannot be reproduced from its inputs.

Case E — the zero-truncation defect: a real transient hidden behind a large common offset
--------------------------------------------------------------------------------------------
    `MSER(d) = (1/k^2) * (Q_d - S_d^2/k)` (`Q_d`, `S_d` the suffix sum of squares and suffix sum
    of the batch means) is a subtraction of two nearly-equal numbers whenever the batch means
    carry a large common offset — a clock that has run a long time, a counter, a price level.
    24 batches, offset `1e10`, a decaying transient of 120, 90, 60, 30 in the first four batches,
    then +-0.4 noise:

        obs[i] = 1e10 + 30*(4-i) for i < 4, else 1e10 + (0.4 if i even else -0.4)

    Computed WITHOUT recentering, `Q_d` and `S_d^2/k` are both of order `24 * (1e10)^2 = 2.4e21`
    at every candidate `d`, so their difference is dominated by float64 rounding (of order
    `2.4e21 * 2^-52`, about `5e5`) rather than by the true deviations (tens to thousands). Every
    candidate's raw deviation sum rounds negative, every one is clamped to the SAME 0.0, and "ties
    go to the smallest d" then picks `d = 0` — discarding NOTHING — even though the first four
    batches are an obvious, decaying, 4x-the-noise transient. That is the zero-truncation defect
    verified by mutation below: reverting the recentering in `warmup_mser_flat` on this exact
    series reproduces `best_d == 0` with a fabricated `mser_value == 0.0`.

    Recentered — subtracting `means[0]` before accumulating, which cannot change any ranking
    because sum-of-squared-deviations is translation invariant — the same series correctly
    truncates at `d = 4`: `n_discarded_obs == 4`, a small nonzero MSER score (~0.008, bounded here
    rather than pinned to a fragile bit pattern), and a steady mean within a thousandth of `1e10`,
    the true noise-free level once the decaying transient is gone.

The bias audit
--------------
On case A with `n_discard = 4`: full mean = (400 + 160)/12 = 46.666666666666664, truncated mean
= 20.0, bias removed = 26.666666666666664 and the relative bias = 4/3. The SIGN is the
diagnosis and is asserted positive here, because a step transient above the steady level pulls
the full mean UP.
"""
from std.math import abs as fabs

from discrete_event.contract import (
    DE_ERR_BATCH_RANGE,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NON_FINITE,
    DE_ERR_NO_STEADY_STATE,
    DE_ERR_TOO_FEW,
    DE_ERR_WARMUP_RANGE,
    DE_MAX_BATCH,
    DE_MAX_OBS,
    DE_OK,
)
from discrete_event.warmup import WARMUP_MIN_BATCHES, warmup_bias_audit, warmup_mser_flat


fn _step() -> List[Float64]:
    var o = List[Float64]()
    for _ in range(4):
        o.append(100.0)
    for _ in range(8):
        o.append(20.0)
    return o^


fn main():
    var passed = 0
    var failed = 0
    print("\n[discrete_event.warmup] known-value suite")

    # ── case A ────────────────────────────────────────────────────────────────
    var step = _step()
    var a = warmup_mser_flat(step, 12, 1)
    var ok_a = a.status == DE_OK and a.n_obs == 12 and a.batch_size == 1
    ok_a = ok_a and a.n_batches == 12 and a.search_boundary == 6
    ok_a = ok_a and a.n_discarded_batches == 4 and a.n_discarded_obs == 4
    ok_a = ok_a and a.n_retained_batches == 8 and a.n_retained_obs == 8
    ok_a = ok_a and a.n_tail_dropped == 0
    ok_a = ok_a and not a.at_search_boundary
    ok_a = ok_a and a.has_mser and a.mser_value == 0.0
    ok_a = ok_a and a.has_estimate and a.steady_mean == 20.0
    ok_a = ok_a and a.has_batch_variance and a.batch_mean_variance == 0.0
    ok_a = ok_a and len(a.batch_means) == 12
    ok_a = ok_a and a.batch_means[0] == 100.0 and a.batch_means[11] == 20.0
    if ok_a:
        passed += 1
        print(
            "  ✅ step transient: 4 discarded (the SMALLEST tying d, not 6), steady mean exactly",
            "20.0, MSER exactly 0.0",
        )
    else:
        failed += 1
        print(
            "  ❌ case A wrong:", a.status, a.n_discarded_obs, a.steady_mean, a.mser_value,
            a.at_search_boundary,
        )

    # ── case B ────────────────────────────────────────────────────────────────
    var spike = List[Float64]()
    spike.append(10.0)
    for _ in range(7):
        spike.append(0.0)
    var b = warmup_mser_flat(spike, 8, 1)
    var ok_b = b.status == DE_OK and b.n_batches == 8 and b.search_boundary == 4
    ok_b = ok_b and b.n_discarded_obs == 1 and b.n_retained_obs == 7
    ok_b = ok_b and b.has_mser and b.mser_value == 0.0
    ok_b = ok_b and b.has_estimate and b.steady_mean == 0.0
    if ok_b:
        passed += 1
        print(
            "  ✅ front outlier: exactly 1 discarded, and a steady mean of 0.0 is an ANSWER",
            "(has_estimate True), not an absence",
        )
    else:
        failed += 1
        print("  ❌ case B wrong:", b.n_discarded_obs, b.has_estimate, b.steady_mean)

    # ── case C: the boundary refusal, with the score derived by hand ──────────
    var trend = List[Float64]()
    for i in range(12):
        trend.append(Float64(i))
    var c = warmup_mser_flat(trend, 12, 1)
    var ok_c = c.status == DE_ERR_NO_STEADY_STATE and c.at_search_boundary
    ok_c = ok_c and c.n_discarded_batches == 6 and c.search_boundary == 6
    ok_c = ok_c and c.has_mser and c.mser_value == 35.0 / 72.0
    ok_c = ok_c and not c.has_estimate and c.steady_mean == 0.0
    if ok_c:
        passed += 1
        print(
            "  ✅ a trend refuses: minimum on the boundary, MSER = 35/72 exactly, and NO steady",
            "estimate is returned",
        )
    else:
        failed += 1
        print(
            "  ❌ case C wrong:", c.status, c.at_search_boundary, c.mser_value, c.has_estimate,
            c.steady_mean,
        )

    # The score really is (k^2-1)/(12k) at k = 6: 35/72 = 0.4861111111111111.
    if c.mser_value == 0.4861111111111111:
        passed += 1
        print("  ✅ the boundary score matches the closed form (k^2-1)/(12k) at k = 6")
    else:
        failed += 1
        print("  ❌ MSER score does not match the consecutive-integer closed form:", c.mser_value)

    # ── case D: the ragged tail ───────────────────────────────────────────────
    var long_series = List[Float64]()
    for i in range(103):
        long_series.append(Float64(i % 7))
    var d = warmup_mser_flat(long_series, 103, 5)
    if d.n_batches == 20 and d.n_tail_dropped == 3 \
            and d.n_retained_obs + d.n_discarded_obs == 100:
        passed += 1
        print("  ✅ 103 observations at batch 5: 20 batches, 3 reported as tail-dropped")
    else:
        failed += 1
        print("  ❌ tail accounting wrong:", d.n_batches, d.n_tail_dropped, d.n_retained_obs)

    # Batch means are the arithmetic means of their own five observations.
    var batch0 = (0.0 + 1.0 + 2.0 + 3.0 + 4.0) / 5.0
    if len(d.batch_means) == 20 and d.batch_means[0] == batch0:
        passed += 1
        print("  ✅ the first batch mean is (0+1+2+3+4)/5 = 2.0, as batched")
    else:
        failed += 1
        print("  ❌ batch means are not means of their own batch:", d.batch_means[0])

    # ── case E: the zero-truncation defect, a real transient behind a huge common offset ──────
    var big = List[Float64]()
    for i in range(24):
        var transient: Float64 = 0.0
        if i < 4:
            transient = 30.0 * Float64(4 - i)
        var noise: Float64 = 0.4
        if i % 2 == 1:
            noise = -0.4
        big.append(1.0e10 + transient + noise)
    var e = warmup_mser_flat(big, 24, 1)
    var ok_e = e.status == DE_OK and e.n_batches == 24 and e.search_boundary == 12
    ok_e = ok_e and not e.at_search_boundary
    ok_e = ok_e and e.n_discarded_batches == 4 and e.n_discarded_obs == 4
    ok_e = ok_e and e.n_retained_batches == 20 and e.n_retained_obs == 20
    ok_e = ok_e and e.has_mser and e.mser_value > 0.001 and e.mser_value < 0.02
    ok_e = ok_e and e.has_estimate and fabs(e.steady_mean - 1.0e10) < 1.0e-3
    if ok_e:
        passed += 1
        print(
            "  ✅ zero-truncation defect fixed: a decaying transient behind a 1e10 common offset",
            "still truncates at d = 4, not the spurious d = 0 the un-recentered arithmetic gives",
        )
    else:
        failed += 1
        print(
            "  ❌ case E wrong:", e.status, e.n_discarded_obs, e.mser_value, e.has_estimate,
            e.steady_mean,
        )

    # Same target series, through the TRUE batch_size=5 path: each of case E's 24 values repeated
    # 5 times as raw observations, so every batch mean is (rounding aside) that same value. Proves
    # the fix is not specific to batch_size=1.
    var big5 = List[Float64]()
    for i in range(24):
        var transient5: Float64 = 0.0
        if i < 4:
            transient5 = 30.0 * Float64(4 - i)
        var noise5: Float64 = 0.4
        if i % 2 == 1:
            noise5 = -0.4
        var v = 1.0e10 + transient5 + noise5
        for _ in range(5):
            big5.append(v)
    var e5 = warmup_mser_flat(big5, 120, 5)
    var ok_e5 = e5.status == DE_OK and e5.n_batches == 24 and e5.search_boundary == 12
    ok_e5 = ok_e5 and not e5.at_search_boundary and e5.n_tail_dropped == 0
    ok_e5 = ok_e5 and e5.n_discarded_batches == 4 and e5.n_discarded_obs == 20
    ok_e5 = ok_e5 and e5.n_retained_batches == 20 and e5.n_retained_obs == 100
    ok_e5 = ok_e5 and e5.has_estimate and fabs(e5.steady_mean - 1.0e10) < 1.0e-3
    if ok_e5:
        passed += 1
        print(
            "  ✅ the same fix holds through true batch_size=5 (MSER-5 proper), not just batch",
            "size 1: 4 batches (20 observations) discarded, not zero",
        )
    else:
        failed += 1
        print(
            "  ❌ case E (batch_size=5) wrong:", e5.status, e5.n_discarded_obs, e5.has_estimate,
            e5.steady_mean,
        )

    # ── refusals ──────────────────────────────────────────────────────────────
    var nan_series = List[Float64]()
    for _ in range(6):
        nan_series.append(1.0)
    nan_series.append(0.0 / 0.0)
    nan_series.append(1.0)
    var refusals = warmup_mser_flat(step, 25, 1).status == DE_ERR_COUNT
    refusals = refusals and warmup_mser_flat(step, 0, 1).status == DE_ERR_EMPTY
    refusals = refusals and warmup_mser_flat(step, -4, 1).status == DE_ERR_EMPTY
    refusals = refusals and warmup_mser_flat(step, 12, 0).status == DE_ERR_BATCH_RANGE
    refusals = refusals and warmup_mser_flat(step, 12, -5).status == DE_ERR_BATCH_RANGE
    refusals = refusals and warmup_mser_flat(step, 12, DE_MAX_BATCH + 1).status == DE_ERR_BATCH_RANGE
    refusals = refusals and warmup_mser_flat(step, 3, 1).status == DE_ERR_TOO_FEW
    refusals = refusals and warmup_mser_flat(step, 12, 4).status == DE_ERR_TOO_FEW
    refusals = refusals and warmup_mser_flat(nan_series, 8, 1).status == DE_ERR_NON_FINITE
    if refusals:
        passed += 1
        print(
            "  ✅ nine refusals: over-count, empty, negative count, three batch-size defects,",
            "too-few-batches from both directions, and a NaN",
        )
    else:
        failed += 1
        print(
            "  ❌ refusal codes wrong:", warmup_mser_flat(step, 25, 1).status,
            warmup_mser_flat(step, 12, 0).status, warmup_mser_flat(step, 3, 1).status,
            warmup_mser_flat(step, 12, 4).status, warmup_mser_flat(nan_series, 8, 1).status,
        )

    # `WARMUP_MIN_BATCHES` batches is the documented floor and must be ACCEPTED.
    var floor_series = List[Float64]()
    for i in range(WARMUP_MIN_BATCHES):
        floor_series.append(1.0 + Float64(i % 2))
    var floor_run = warmup_mser_flat(floor_series, WARMUP_MIN_BATCHES, 1)
    if WARMUP_MIN_BATCHES == 4 and floor_run.status == DE_OK and floor_run.n_batches == 4:
        passed += 1
        print("  ✅ exactly WARMUP_MIN_BATCHES (4) batches is accepted; three is not")
    else:
        failed += 1
        print("  ❌ the documented batch floor is off by one:", floor_run.status)

    # ── the bias audit ────────────────────────────────────────────────────────
    var ba = warmup_bias_audit(step, 12, 4)
    var ok_ba = ba.status == DE_OK and ba.n_obs == 12
    ok_ba = ok_ba and ba.n_discarded == 4 and ba.n_retained == 8
    ok_ba = ok_ba and ba.has_full_mean and ba.full_mean == 560.0 / 12.0
    ok_ba = ok_ba and ba.has_truncated_mean and ba.truncated_mean == 20.0
    ok_ba = ok_ba and ba.has_bias and ba.bias_removed > 0.0
    ok_ba = ok_ba and fabs(ba.bias_removed - 80.0 / 3.0) < 1e-12
    ok_ba = ok_ba and ba.has_relative_bias and fabs(ba.relative_bias - 4.0 / 3.0) < 1e-12
    if ok_ba:
        passed += 1
        print(
            "  ✅ bias audit: full mean 560/12, truncated 20.0, bias +80/3, relative 4/3, and",
            "the SIGN says the transient was above the steady level",
        )
    else:
        failed += 1
        print(
            "  ❌ bias audit wrong:", ba.full_mean, ba.truncated_mean, ba.bias_removed,
            ba.relative_bias,
        )

    # A truncated mean of exactly zero has no relative bias, and that is reported absent.
    var zeros = List[Float64]()
    zeros.append(5.0)
    for _ in range(5):
        zeros.append(0.0)
    var bz = warmup_bias_audit(zeros, 6, 1)
    if bz.status == DE_OK and bz.has_truncated_mean and bz.truncated_mean == 0.0 \
            and bz.has_bias and not bz.has_relative_bias and bz.relative_bias == 0.0:
        passed += 1
        print(
            "  ✅ a zero truncated mean gives an ABSENT relative bias — no ratio to zero is",
            "invented, while the absolute bias is still reported",
        )
    else:
        failed += 1
        print("  ❌ relative bias at a zero denominator:", bz.has_relative_bias, bz.relative_bias)

    # `n_discard` is a range START, so both directions are fatal for different reasons.
    var bias_refusals = warmup_bias_audit(step, 12, -1).status == DE_ERR_WARMUP_RANGE
    bias_refusals = bias_refusals and warmup_bias_audit(step, 12, 12).status == DE_ERR_WARMUP_RANGE
    bias_refusals = bias_refusals and warmup_bias_audit(step, 25, 0).status == DE_ERR_COUNT
    bias_refusals = bias_refusals and warmup_bias_audit(step, 0, 0).status == DE_ERR_EMPTY
    bias_refusals = bias_refusals and warmup_bias_audit(
        step, DE_MAX_OBS + 1, 0
    ).status == DE_ERR_COUNT
    bias_refusals = bias_refusals and warmup_bias_audit(nan_series, 8, 0).status == DE_ERR_NON_FINITE
    if bias_refusals:
        passed += 1
        print(
            "  ✅ a NEGATIVE n_discard is refused (it would subscript obs[-1] and abort the",
            "process), and so is discarding everything",
        )
    else:
        failed += 1
        print(
            "  ❌ bias-audit range guards wrong:", warmup_bias_audit(step, 12, -1).status,
            warmup_bias_audit(step, 12, 12).status, warmup_bias_audit(step, 25, 0).status,
        )

    print("  [discrete_event.warmup] Passed:", passed, "Failed:", failed)
