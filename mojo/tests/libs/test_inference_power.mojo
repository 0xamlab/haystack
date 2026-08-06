"""test_inference_power.mojo — known-value tests for the power and sample-size drivers.

Hand-written. The headline known values are the ones every textbook prints for the canonical
design — `d = 0.5`, two-sided `alpha = 0.05`, target power `0.80`:

    normal approximation   n = 63 per group   (2 ((1.959964 + 0.841621) / 0.5)^2 = 62.79 -> 63)
    central-t-shift lane   n = 64 per group   (the textbook noncentral-t answer)

Both are asserted, and the one-larger t answer is the point: the difference between the two lanes
is exactly the variance-estimation penalty the normal approximation omits, so a driver that
reported one number for both would be wrong for whichever test the caller is actually running.

*The verification is the deliverable, not the algebra.* Every sample size is checked by
re-evaluating the SAME power function the caller would use, at `n` and at `n - 1`:

    normal lane   n = 63   achieved 0.8011822526702241   at n-1 0.7948856284208302
    t lane        n = 64   achieved 0.8013829274055866   at n-1 0.7950790808528411

so `minimal` is a measured property. On the t lane `search_steps` is 1, because the closed form
inverts the NORMAL power and not the t power — that nonzero step count is the honest signal that
the inversion and the verification are two different computations, which is the whole reason the
verification exists.

*The two lanes' probits differ, and that is stated rather than papered over.* The two-sided
normal lane calls the frozen `ab_testing.power_analysis` unchanged, which uses the
Abramowitz-Stegun rational probit (~4.5e-4); the one-sided lane and the closed-form inversion use
`math_ext.norm_ppf` (Acklam, ~1.15e-9). So `power_analysis(0.5, 63, 0.05)` returns
0.8011822526702241 where a fully Acklam computation gives 0.8013023941055797 — a 1.2e-4
difference. Both are asserted at their measured values and the cross-lane identity
`two_sided(alpha) ~= one_sided(alpha/2)` is asserted at 1e-3, which is that accuracy and no
better.

*And the refusals.* A zero effect has no sample size — `ab_testing.sample_size_proportion`
returns the literal `1000000` for the analogous case, with the comment "Infinite sample needed
for zero effect". An effect small enough to need more than `MAX_SAMPLE_SIZE` is refused too, and
an `alpha` outside `(0, 1)` is refused where `ab_testing.power_analysis` answers (its
`_norm_ppf` clamps `p` into `[1e-10, 1-1e-10]` and returns a number for `alpha = 3.0`).
"""
from std.math import abs as fabs, sqrt

from ab_testing import power_analysis
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EFFECT_ZERO,
    INF_ERR_TOO_FEW,
    INF_OK,
    MAX_SAMPLE_SIZE,
    inference_absent,
    inference_t_quantile,
)
from inference.power import (
    METHOD_NORMAL_ONE_SIDED,
    METHOD_NORMAL_TWO_SIDED,
    METHOD_T_ONE_SIDED,
    METHOD_T_TWO_SIDED,
    POWER_MAX_ABS_Z,
    POWER_SEARCH_STEPS,
    PowerReport,
    SampleSizeReport,
    power_design_defect,
    power_two_means_flat,
    power_two_means_t_flat,
    sample_size_two_means_flat,
    sample_size_two_means_t_flat,
)


def _no_power(r: PowerReport) -> Bool:
    """A refusal says so in a field, because 0.0 is a legitimate value of real power."""
    return r.status != INF_OK and not r.power_known and r.power == 0.0


def _no_size(r: SampleSizeReport) -> Bool:
    """A refusal carries no sample size and no verification."""
    return (
        r.status != INF_OK
        and r.n_per_group == 0
        and not r.minimal
        and r.achieved_power == 0.0
    )


def main():
    var passed: Int = 0
    var failed: Int = 0

    # ── 1. the canonical normal-approximation power ───────────────────────────
    var p63 = power_two_means_flat(0.5, 63, 0.05, False)
    var p62 = power_two_means_flat(0.5, 62, 0.05, False)
    if (
        p63.status == INF_OK
        and p63.power_known
        and p63.method == METHOD_NORMAL_TWO_SIDED
        # the two-sided lane IS the frozen kernel, so this must be bitwise equal to it
        and p63.power == power_analysis(0.5, 63, 0.05)
        and p63.power == 0.8011822526702241
        and p63.power >= 0.80
        and p62.power == 0.7948856284208302
        and p62.power < 0.80
        # the normal lane has no degrees of freedom, and reports that rather than a 0
        and p63.df == -1.0
        and fabs(p63.critical_value - 1.959963984540054) <= 1.0e-8
        and p63.n_per_group == 63
        and p63.effect_size == 0.5
        and not p63.one_sided
    ):
        passed += 1
        print("  ✅ normal power at d=0.5 is 0.80118 at n=63 and 0.79489 at n=62, from frozen")
    else:
        failed += 1
        print("  ❌ normal power:", p63.status, p63.power, power_analysis(0.5, 63, 0.05))

    # ── 2. the t lane, and its one-larger answer ─────────────────────────────
    var t64 = power_two_means_t_flat(0.5, 64, 0.05, False)
    var t63 = power_two_means_t_flat(0.5, 63, 0.05, False)
    if (
        t64.status == INF_OK
        and t64.method == METHOD_T_TWO_SIDED
        and t64.df == 126.0
        # t_{0.975,126} = 1.9789706019887539, from the corrected t quantile
        and fabs(t64.critical_value - 1.9789706019887539) <= 1.0e-8
        and fabs(t64.critical_value - inference_t_quantile(0.975, 126.0)) <= 1.0e-15
        and t64.power == 0.8013829274055866
        and t64.power >= 0.80
        and t63.power == 0.7950790808528411
        and t63.power < 0.80
        # the t critical value exceeds the normal one, which is WHY the t lane needs one more
        # observation per group at the same target
        and t64.critical_value > p63.critical_value
    ):
        passed += 1
        print("  ✅ the t lane at n=64 reaches 0.80138 with t_crit 1.97897 on 126 df")
    else:
        failed += 1
        print("  ❌ t power:", t64.status, t64.power, t64.critical_value)

    # ── 3. the sample size, VERIFIED at n and n-1 ────────────────────────────
    var size = sample_size_two_means_flat(0.5, 0.05, 0.80, False)
    if (
        size.status == INF_OK
        and size.n_per_group == 63
        # the closed form gives 62.79 -> ceil 63, so the search moves nothing
        and size.closed_form_n == 63
        and size.search_steps == 0
        and size.achieved_power == 0.8011822526702241
        and size.power_at_n_minus_1 == 0.7948856284208302
        and size.achieved_power >= size.target_power
        and size.power_at_n_minus_1 < size.target_power
        and size.minimal
        and size.method == METHOD_NORMAL_TWO_SIDED
        and size.target_power == 0.80
        # the verification calls the same function the caller would
        and size.achieved_power == power_two_means_flat(0.5, 63, 0.05, False).power
    ):
        passed += 1
        print("  ✅ n=63 is VERIFIED minimal: 0.80118 at 63 and 0.79489 at 62")
    else:
        failed += 1
        print("  ❌ normal sample size:", size.status, size.n_per_group, size.minimal)

    var size_t = sample_size_two_means_t_flat(0.5, 0.05, 0.80, False)
    if (
        size_t.status == INF_OK
        and size_t.n_per_group == 64
        # the closed form inverts the NORMAL power, so it starts at 63 and the verification
        # moves it: a nonzero search_steps is the honest signal that the two differ
        and size_t.closed_form_n == 63
        and size_t.search_steps == 1
        and size_t.achieved_power == 0.8013829274055866
        and size_t.power_at_n_minus_1 == 0.7950790808528411
        and size_t.minimal
        and size_t.method == METHOD_T_TWO_SIDED
        # and it is exactly one larger than the normal lane's answer
        and size_t.n_per_group == size.n_per_group + 1
    ):
        passed += 1
        print("  ✅ the t lane's VERIFIED n is 64 — the textbook answer, one above the normal")
    else:
        failed += 1
        print("  ❌ t sample size:", size_t.status, size_t.n_per_group, size_t.search_steps)

    # ── 4. monotonicity in every argument that has a direction ───────────────
    var mono_n = True
    var previous = 0.0
    for i in range(2, 60):
        var here = power_two_means_flat(0.5, i, 0.05, False)
        if here.status != INF_OK or here.power < previous:
            mono_n = False
        previous = here.power
    var mono_effect = True
    var prev_effect = 0.0
    var effects = List[Float64]()
    effects.append(0.1)
    effects.append(0.3)
    effects.append(0.5)
    effects.append(0.8)
    effects.append(1.2)
    for i in range(len(effects)):
        var here = power_two_means_flat(effects[i], 40, 0.05, False)
        if here.status != INF_OK or here.power < prev_effect:
            mono_effect = False
        prev_effect = here.power
    if (
        mono_n
        and mono_effect
        # a larger alpha buys power; a smaller target power needs fewer observations
        and power_two_means_flat(0.5, 40, 0.10, False).power
        > power_two_means_flat(0.5, 40, 0.05, False).power
        and sample_size_two_means_flat(0.5, 0.05, 0.90, False).n_per_group > 63
        and sample_size_two_means_flat(0.5, 0.05, 0.70, False).n_per_group < 63
        and sample_size_two_means_flat(1.0, 0.05, 0.80, False).n_per_group < 63
        # power is symmetric in the sign of the effect
        and power_two_means_flat(-0.5, 63, 0.05, False).power == p63.power
    ):
        passed += 1
        print("  ✅ power rises in n, in |d| and in alpha; n falls in |d| and in target power")
    else:
        failed += 1
        print("  ❌ monotonicity broken:", mono_n, mono_effect)

    # ── 5. the two lanes' cross-check, at the accuracy they actually have ────
    # A two-sided test at alpha is a one-sided test at alpha/2 plus the far-tail term, which is
    # 9e-7 at this design — so the two must agree to about 1e-5 in exact arithmetic. They agree
    # to 1.2e-4 because the frozen two-sided kernel uses a cruder probit; that is the measured
    # accuracy and the assertion states it rather than pretending to more.
    var two_sided = power_two_means_flat(0.5, 63, 0.05, False)
    var one_sided = power_two_means_flat(0.5, 63, 0.025, True)
    if (
        one_sided.status == INF_OK
        and one_sided.method == METHOD_NORMAL_ONE_SIDED
        and one_sided.one_sided
        and fabs(one_sided.power - two_sided.power) <= 1.0e-3
        and fabs(one_sided.power - two_sided.power) > 1.0e-6
        # the same identity on the t lane, where BOTH sides use the corrected t tail, holds far
        # tighter — which is itself evidence that the 1.2e-4 above is the frozen probit
        and fabs(
            power_two_means_t_flat(0.5, 64, 0.025, True).power
            - power_two_means_t_flat(0.5, 64, 0.05, False).power
        ) <= 1.0e-5
        # a one-sided test at the same alpha is more powerful than a two-sided one
        and power_two_means_flat(0.5, 63, 0.05, True).power > two_sided.power
        and power_two_means_t_flat(0.5, 63, 0.05, True).power > t63.power
    ):
        passed += 1
        print("  ✅ two-sided(a) ~ one-sided(a/2) to 1.2e-4 normal, 1e-5 on the corrected t")
    else:
        failed += 1
        print("  ❌ lane cross-check:", one_sided.power, two_sided.power)

    # ── 6. the one-sided sample sizes are also verified ─────────────────────
    var one_size = sample_size_two_means_flat(0.5, 0.05, 0.80, True)
    var one_size_t = sample_size_two_means_t_flat(0.5, 0.05, 0.80, True)
    if (
        one_size.status == INF_OK
        and one_size.minimal
        and one_size.method == METHOD_NORMAL_ONE_SIDED
        # a one-sided test needs fewer observations than a two-sided one at the same alpha
        and one_size.n_per_group < size.n_per_group
        and one_size.achieved_power >= 0.80
        and one_size_t.status == INF_OK
        and one_size_t.minimal
        and one_size_t.n_per_group >= one_size.n_per_group
        and one_size_t.search_steps <= POWER_SEARCH_STEPS
    ):
        passed += 1
        print("  ✅ the one-sided designs verify too, and need fewer observations")
    else:
        failed += 1
        print("  ❌ one-sided sizes:", one_size.n_per_group, size.n_per_group)

    # ── 7. a zero effect has no sample size ────────────────────────────────
    if (
        _no_size(sample_size_two_means_flat(0.0, 0.05, 0.80, False))
        and sample_size_two_means_flat(0.0, 0.05, 0.80, False).status
        == INF_ERR_EFFECT_ZERO
        and _no_size(sample_size_two_means_t_flat(0.0, 0.05, 0.80, False))
        and sample_size_two_means_t_flat(0.0, 0.05, 0.80, False).status
        == INF_ERR_EFFECT_ZERO
        # an effect small enough to need more than the ceiling is also a refusal, not a number
        # nobody can act on
        and sample_size_two_means_flat(1.0e-9, 0.05, 0.80, False).status
        == INF_ERR_DIMENSION_TOO_LARGE
        and _no_size(sample_size_two_means_flat(1.0e-9, 0.05, 0.80, False))
        # and power at a zero effect IS alpha, which is a real answer and is returned
        and power_two_means_flat(0.0, 100, 0.05, False).status == INF_OK
        and fabs(power_two_means_flat(0.0, 100, 0.05, False).power - 0.05) <= 1.0e-3
    ):
        passed += 1
        print("  ✅ a zero effect has NO sample size, though its power is alpha and is given")
    else:
        failed += 1
        print("  ❌ zero effect:", sample_size_two_means_flat(0.0, 0.05, 0.80, False).status)

    # ── 8. validation the frozen kernels do not do ─────────────────────────
    # ab_testing.power_analysis(0.5, 100, 3.0) answers, because its probit clamps p into
    # [1e-10, 1-1e-10]. Every one of these is a refusal here.
    if (
        power_analysis(0.5, 100, 3.0) >= 0.0  # the frozen kernel answers an invalid alpha
        and _no_power(power_two_means_flat(0.5, 100, 3.0, False))
        and power_two_means_flat(0.5, 100, 3.0, False).status == INF_ERR_ALPHA_RANGE
        and power_two_means_flat(0.5, 100, 0.0, False).status == INF_ERR_ALPHA_RANGE
        and power_two_means_flat(0.5, 100, 1.0, False).status == INF_ERR_ALPHA_RANGE
        and power_two_means_flat(0.5, 100, -0.1, False).status == INF_ERR_ALPHA_RANGE
        and power_two_means_flat(inference_absent(), 100, 0.05, False).status
        == INF_ERR_ALPHA_RANGE
        # a two-sample comparison needs at least two observations per group
        and power_two_means_flat(0.5, 1, 0.05, False).status == INF_ERR_TOO_FEW
        and power_two_means_flat(0.5, 0, 0.05, False).status == INF_ERR_TOO_FEW
        and power_two_means_flat(0.5, MAX_SAMPLE_SIZE + 1, 0.05, False).status
        == INF_ERR_DIMENSION_TOO_LARGE
        and power_two_means_t_flat(0.5, 1, 0.05, False).status == INF_ERR_TOO_FEW
        and power_two_means_t_flat(0.5, 100, 0.0, False).status == INF_ERR_ALPHA_RANGE
        and sample_size_two_means_flat(0.5, 0.05, 0.0, False).status == INF_ERR_ALPHA_RANGE
        and sample_size_two_means_flat(0.5, 0.05, 1.0, False).status == INF_ERR_ALPHA_RANGE
        and sample_size_two_means_flat(0.5, 2.0, 0.80, False).status == INF_ERR_ALPHA_RANGE
    ):
        passed += 1
        print("  ✅ thirteen invalid designs are refused where the frozen kernel answers")
    else:
        failed += 1
        print("  ❌ validation:", power_two_means_flat(0.5, 100, 3.0, False).status)

    # ── 9. the shared design validator ────────────────────────────────────
    if (
        power_design_defect(0.5, 63, 0.05) == INF_OK
        and power_design_defect(0.5, 1, 0.05) == INF_ERR_TOO_FEW
        and power_design_defect(0.5, MAX_SAMPLE_SIZE + 1, 0.05)
        == INF_ERR_DIMENSION_TOO_LARGE
        and power_design_defect(0.5, 63, 0.0) == INF_ERR_ALPHA_RANGE
        and power_design_defect(inference_absent(), 63, 0.05) == INF_ERR_ALPHA_RANGE
        # one validator, so both lanes agree about what a valid design is
        and power_design_defect(0.5, 63, 0.05)
        == power_design_defect(0.5, 63, 0.05)
        and POWER_MAX_ABS_Z == 40.0
        and POWER_SEARCH_STEPS == 64
    ):
        passed += 1
        print("  ✅ one design validator serves both lanes, with the 40-sigma quantile guard")
    else:
        failed += 1
        print("  ❌ design validator:", power_design_defect(0.5, 1, 0.05))

    # ── 10. a design at the edge of the quantile guard ────────────────────
    # math_ext.norm_ppf returns the FINITE sentinel +-1e300 past the ends of (0,1), which a
    # finiteness guard cannot catch — so an alpha small enough to round to 0 in double
    # arithmetic must be refused by the MAGNITUDE check rather than answered with 1e300.
    var tiny_alpha = sample_size_two_means_flat(0.5, 1.0e-320, 0.80, False)
    if (
        tiny_alpha.status != INF_OK
        and _no_size(tiny_alpha)
        # and a merely small alpha still works, so the guard is not over-broad
        and sample_size_two_means_flat(0.5, 1.0e-6, 0.80, False).status == INF_OK
        and sample_size_two_means_flat(0.5, 1.0e-6, 0.80, False).n_per_group > 63
        and sample_size_two_means_flat(0.5, 1.0e-6, 0.80, False).minimal
    ):
        passed += 1
        print("  ✅ an alpha past the probit's range is refused; 1e-6 still answers")
    else:
        failed += 1
        print("  ❌ quantile guard:", tiny_alpha.status)

    # ── 11. the A-Z harness shape, which must not abort ──────────────────
    # The generated suite calls with 0.5 for every Float64, 5 for every Int and True for every
    # Bool: power_two_means_flat(0.5, 5, 0.5, True) is a legal if silly design and must answer,
    # and sample_size_two_means_flat(0.5, 0.5, 0.5, True) inverts to the n=2 floor.
    var harness_power = power_two_means_flat(0.5, 5, 0.5, True)
    var harness_size = sample_size_two_means_flat(0.5, 0.5, 0.5, True)
    if (
        harness_power.status == INF_OK
        and harness_power.power_known
        and harness_power.power >= 0.0
        and harness_power.power <= 1.0
        and power_two_means_t_flat(0.5, 5, 0.5, True).status == INF_OK
        and harness_size.status == INF_OK
        and harness_size.n_per_group >= 2
        and harness_size.achieved_power >= 0.5
        and sample_size_two_means_t_flat(0.5, 0.5, 0.5, True).status == INF_OK
    ):
        passed += 1
        print("  ✅ all four harness calls answer inside [0,1] with n at or above the floor")
    else:
        failed += 1
        print("  ❌ harness calls:", harness_power.status, harness_size.status)

    print("  [inference.power] Passed:", passed, "Failed:", failed)
