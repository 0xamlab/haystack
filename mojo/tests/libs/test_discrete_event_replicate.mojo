"""test_discrete_event_replicate.mojo — the closed-form validation of the simulator.

Hand-written. This is the suite that decides whether the package is right, because an M/M/1
queue is one of the few simulations with an EXACT analytical answer to be wrong against.

The interval, from hand arithmetic and a published table
-------------------------------------------------------
`replicate_ci_flat([1, 2, 3, 4, 5], 5, 0.95)`:

    mean            = 15/5 = 3.0                                    (exact)
    sample variance = (4+1+0+1+4)/4 = 10/4 = 2.5                     (exact)
    standard error  = sqrt(2.5/5) = sqrt(0.5) = 0.7071067811865476
    t(0.975, df=4)  = 2.7764451051977987                             (reference: R `qt`)
    half width      = 2.7764451051977987 * 0.7071067811865476 = 1.96324316...
    interval        = 3.0 -+ 1.96324316 = [1.03675684, 4.96324316]

The critical value is checked against the REFERENCE value from R's `qt(0.975, 4)`, not against
whatever the tree happens to compute — that is the only way the assertion is independent of the
quantile implementation. The tree's bisection agrees to 3.6e-10 at df 4 and 8.6e-10 at df 9
(reference `qt(0.975, 9) = 2.2621571627982044`), so the assertions allow 1e-8 and would catch any
change an order of magnitude larger. A normal quantile would give 1.9599639845400536 here, a 29%
narrower interval, so the test also distinguishes a t interval from a normal one.

The M/M/1 coverage check, and why it is the package's keystone
-------------------------------------------------------------
For lambda = 1, mu = 2: Wq = 0.5, W = 1.0, L = 1.0 and utilisation = 0.5, exactly. The simulator
runs 10 independent replications of 4000 customers each and forms four 95% intervals. All four
exact values must fall inside their interval. They do, and the seed is fixed, so the assertion
is stable forever. If it ever fails, the simulator is wrong — the algebra is not.

Repeated at rho = 0.9, where the queue is 18 times more congested and convergence is far slower,
and for M/M/2 (lambda = 1.2, mu = 1), where Wq comes from the frozen Erlang C:

    A = 1.2, rho = 0.6, C = [A^2/2 * 2/(2-A)] / [1 + A + A^2/2 * 2/(2-A)] = 1.8/4 = 0.45
    Wq = C/(c*mu - lambda) = 0.45/0.8 = 0.5625,  W = 1.5625,  L = 1.2 * 1.5625 = 1.875

A CHECK THAT CANNOT FAIL IS WORTH NOTHING, so the suite also pins a configuration where coverage
DOES fail: rho = 0.95 with only 400 customers per replication. There the initialisation
transient is a large fraction of the run, MSER discards 55 observations, and three of the four
intervals still sit BELOW the exact values — the estimate is biased low and the package says so
rather than reporting a comfortable four-of-four. Truncation cannot manufacture a run length.
That asymmetry is the evidence that the coverage flags mean something.

Where the warm-up truncation lands, and why zero is the right answer at 4000 customers
------------------------------------------------------------------------------------
At rho = 0.5 with 4000 customers the pilot has 800 batches of 5. MSER trades bias against
variance, and discarding a batch costs variance in proportion to 1/(m-d)^2 while the transient
is a few batches out of 800. So it declines to truncate, and `warmup_jobs_used` is 0 — asserted,
because a warm-up rule that always discarded something would be a rule that ignored the
trade-off it exists to make.
"""
from std.math import abs as fabs

from discrete_event.contract import (
    DE_ERR_BATCH_RANGE,
    DE_ERR_CAPACITY,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_LEVEL_RANGE,
    DE_ERR_NON_FINITE,
    DE_ERR_RATE_RANGE,
    DE_ERR_SEED_RANGE,
    DE_ERR_TOO_FEW_REPS,
    DE_ERR_UNSTABLE,
    DE_MAX_JOBS,
    DE_MAX_REPLICATIONS,
    DE_OK,
)
from discrete_event.replicate import replicate_ci_flat, replicate_mm1_flat


fn _five() -> List[Float64]:
    var o = List[Float64]()
    for i in range(5):
        o.append(Float64(i + 1))
    return o^


fn main():
    var passed = 0
    var failed = 0
    print("\n[discrete_event.replicate] known-value suite")

    # ── the interval, against hand arithmetic and a published t value ──────────
    var five = _five()
    var ci = replicate_ci_flat(five, 5, 0.95)
    var ok_ci = ci.status == DE_OK and ci.n_reps == 5 and ci.level == 0.95
    ok_ci = ok_ci and ci.has_mean and ci.mean == 3.0
    ok_ci = ok_ci and ci.has_variance and ci.variance == 2.5
    ok_ci = ok_ci and ci.has_std_error and ci.std_error == 0.7071067811865476
    ok_ci = ok_ci and ci.has_t_critical
    ok_ci = ok_ci and fabs(ci.t_critical - 2.7764451051977987) < 1.0e-8
    ok_ci = ok_ci and ci.has_ci and ci.has_half_width
    ok_ci = ok_ci and fabs(ci.half_width - 1.9632431617297454) < 1.0e-12
    ok_ci = ok_ci and fabs(ci.ci_lower - 1.0367568382702546) < 1.0e-12
    ok_ci = ok_ci and fabs(ci.ci_upper - 4.9632431617297454) < 1.0e-12
    ok_ci = ok_ci and ci.ci_upper - ci.mean == ci.mean - ci.ci_lower
    if ok_ci:
        passed += 1
        print(
            "  ✅ mean 3.0, variance 2.5, se sqrt(0.5), t(0.975,4) = 2.7764451052 vs",
            "reference qt(0.975,4), interval [1.03675684, 4.96324316] and symmetric",
        )
    else:
        failed += 1
        print(
            "  ❌ interval arithmetic wrong:", ci.mean, ci.variance, ci.std_error, ci.t_critical,
            ci.ci_lower, ci.ci_upper,
        )

    # A t interval, not a normal one: the normal 97.5% quantile is 1.959964.
    if ci.t_critical > 2.7 and ci.t_critical < 2.8:
        passed += 1
        print("  ✅ the pivot is Student-t on 4 df, not the normal 1.959964")
    else:
        failed += 1
        print("  ❌ the critical value is not a t on 4 df:", ci.t_critical)

    # A wider level must widen the interval; a narrower one must narrow it.
    var ci99 = replicate_ci_flat(five, 5, 0.99)
    var ci80 = replicate_ci_flat(five, 5, 0.80)
    if ci99.has_ci and ci80.has_ci and ci99.half_width > ci.half_width \
            and ci80.half_width < ci.half_width and ci99.mean == ci.mean:
        passed += 1
        print("  ✅ 99% is wider and 80% narrower than 95%, around the same mean")
    else:
        failed += 1
        print("  ❌ the level does not order the interval widths")

    # ── one replication: a mean exists, an interval does not ──────────────────
    var one = List[Float64]()
    one.append(7.0)
    var c1 = replicate_ci_flat(one, 1, 0.95)
    if c1.status == DE_ERR_TOO_FEW_REPS and c1.has_mean and c1.mean == 7.0 \
            and not c1.has_ci and c1.ci_lower == 0.0 and c1.ci_upper == 0.0 \
            and not c1.has_variance:
        passed += 1
        print(
            "  ✅ one replication: the mean is present and real, the interval is ABSENT with a",
            "representable 0.0 in both bounds — not a zero-width interval",
        )
    else:
        failed += 1
        print("  ❌ single-replication handling wrong:", c1.status, c1.has_mean, c1.has_ci)

    # Zero variance is a real answer, and gives a real interval of width zero.
    var flat_estimates = List[Float64]()
    for _ in range(4):
        flat_estimates.append(2.0)
    var cflat = replicate_ci_flat(flat_estimates, 4, 0.95)
    if cflat.status == DE_OK and cflat.mean == 2.0 and cflat.has_variance \
            and cflat.variance == 0.0 and cflat.has_ci and cflat.half_width == 0.0 \
            and cflat.ci_lower == 2.0 and cflat.ci_upper == 2.0:
        passed += 1
        print("  ✅ four identical replications: variance 0.0 is an answer and the interval is a point")
    else:
        failed += 1
        print("  ❌ zero-variance interval wrong:", cflat.variance, cflat.half_width)

    # ── refusals on the interval driver ───────────────────────────────────────
    var nan_list = List[Float64]()
    nan_list.append(1.0)
    nan_list.append(0.0 / 0.0)
    nan_list.append(3.0)
    var ci_refusals = replicate_ci_flat(five, 25, 0.95).status == DE_ERR_COUNT
    ci_refusals = ci_refusals and replicate_ci_flat(five, 0, 0.95).status == DE_ERR_EMPTY
    ci_refusals = ci_refusals and replicate_ci_flat(five, -2, 0.95).status == DE_ERR_EMPTY
    ci_refusals = ci_refusals and replicate_ci_flat(five, 5, 0.0).status == DE_ERR_LEVEL_RANGE
    ci_refusals = ci_refusals and replicate_ci_flat(five, 5, 1.0).status == DE_ERR_LEVEL_RANGE
    ci_refusals = ci_refusals and replicate_ci_flat(five, 5, -0.5).status == DE_ERR_LEVEL_RANGE
    ci_refusals = ci_refusals and replicate_ci_flat(nan_list, 3, 0.95).status == DE_ERR_NON_FINITE
    ci_refusals = ci_refusals and replicate_ci_flat(
        five, DE_MAX_REPLICATIONS + 1, 0.95
    ).status == DE_ERR_COUNT
    if ci_refusals:
        passed += 1
        print(
            "  ✅ eight interval refusals: over-count, empty, negative, both open-interval level",
            "bounds, a negative level, a NaN estimate, and the replication ceiling",
        )
    else:
        failed += 1
        print(
            "  ❌ interval refusal codes wrong:", replicate_ci_flat(five, 25, 0.95).status,
            replicate_ci_flat(five, 5, 1.0).status, replicate_ci_flat(nan_list, 3, 0.95).status,
        )

    # ── THE KEYSTONE: M/M/1, rho = 0.5 ───────────────────────────────────────
    var v = replicate_mm1_flat(1.0, 2.0, 4000, 1, 10, 12345, 0.95, 5)
    var ok_v = v.status == DE_OK and v.n_reps_requested == 10 and v.n_reps_run == 10
    ok_v = ok_v and v.n_reps_refused == 0 and v.n_customers == 4000 and v.capacity == 1
    ok_v = ok_v and v.closed_form_rho == 0.5 and v.closed_form_wait == 0.5
    ok_v = ok_v and v.closed_form_system == 1.0 and v.closed_form_number == 1.0
    ok_v = ok_v and v.n_metrics_checked == 4 and v.n_metrics_covered == 4
    ok_v = ok_v and v.wait_covered and v.system_covered
    ok_v = ok_v and v.number_covered and v.util_covered
    ok_v = ok_v and v.has_wait_ci and v.wait_ci_lower < 0.5 and v.wait_ci_upper > 0.5
    ok_v = ok_v and v.has_system_ci and v.system_ci_lower < 1.0 and v.system_ci_upper > 1.0
    ok_v = ok_v and v.has_number_ci and v.number_ci_lower < 1.0 and v.number_ci_upper > 1.0
    ok_v = ok_v and v.has_util_ci and v.util_ci_lower < 0.5 and v.util_ci_upper > 0.5
    ok_v = ok_v and v.has_t_critical and fabs(v.t_critical - 2.2621571627982044) < 1.0e-8
    if ok_v:
        passed += 1
        print(
            "  ✅ M/M/1 rho=0.5, 10 x 4000: ALL FOUR exact values (Wq 0.5, W 1.0, L 1.0,",
            "rho 0.5) fall inside their 95% intervals, t(0.975,9) = 2.2621571628",
        )
    else:
        failed += 1
        print(
            "  ❌ M/M/1 validation failed:", v.status, v.n_metrics_covered, "of",
            v.n_metrics_checked, "Wq", v.wait_ci_lower, v.wait_mean, v.wait_ci_upper,
            "W", v.system_ci_lower, v.system_ci_upper,
            "L", v.number_ci_lower, v.number_ci_upper,
            "rho", v.util_ci_lower, v.util_ci_upper,
        )

    # The pilot declines to truncate at this length, and the accounting says so.
    if v.warmup_jobs_used == 0 and v.pilot_batch_size == 5 and v.pilot_n_batches == 800 \
            and v.pilot_tail_dropped == 0:
        passed += 1
        print(
            "  ✅ 800 pilot batches, no truncation chosen — MSER honouring the bias/variance",
            "trade-off rather than always discarding",
        )
    else:
        failed += 1
        print(
            "  ❌ pilot accounting wrong:", v.warmup_jobs_used, v.pilot_n_batches,
            v.pilot_tail_dropped,
        )

    # (n_reps + 1) runs charged, not n_reps: the pilot is real work.
    if v.work_charged == 11 * 304000:
        passed += 1
        print("  ✅ work charged for 11 runs (10 replications plus the pilot), not 10")
    else:
        failed += 1
        print("  ❌ work charge wrong:", v.work_charged)

    # Bit-identical on a repeat: the whole comparison premise.
    var v2 = replicate_mm1_flat(1.0, 2.0, 4000, 1, 10, 12345, 0.95, 5)
    var det_ok = v2.wait_mean == v.wait_mean and v2.system_mean == v.system_mean
    det_ok = det_ok and v2.number_mean == v.number_mean and v2.util_mean == v.util_mean
    det_ok = det_ok and v2.wait_ci_lower == v.wait_ci_lower
    det_ok = det_ok and v2.wait_ci_upper == v.wait_ci_upper
    det_ok = det_ok and v2.warmup_jobs_used == v.warmup_jobs_used
    if det_ok:
        passed += 1
        print("  ✅ the same seed reproduces all four means and all four bounds bit-for-bit")
    else:
        failed += 1
        print("  ❌ two identical validations disagreed")

    # A different seed must move the estimates but leave the exact answer alone.
    var v3 = replicate_mm1_flat(1.0, 2.0, 4000, 1, 10, 999, 0.95, 5)
    if v3.status == DE_OK and v3.wait_mean != v.wait_mean \
            and v3.closed_form_wait == v.closed_form_wait:
        passed += 1
        print("  ✅ a different seed moves the estimate and not the closed form")
    else:
        failed += 1
        print("  ❌ the seed is not reaching the replications:", v3.wait_mean, v.wait_mean)

    # ── rho = 0.9: eighteen times more congested, still covered ───────────────
    var hi = replicate_mm1_flat(0.9, 1.0, 8000, 1, 20, 999, 0.95, 5)
    var ok_hi = hi.status == DE_OK and hi.n_reps_run == 20
    ok_hi = ok_hi and fabs(hi.closed_form_wait - 9.0) < 1.0e-12
    ok_hi = ok_hi and fabs(hi.closed_form_system - 10.0) < 1.0e-12
    ok_hi = ok_hi and fabs(hi.closed_form_number - 9.0) < 1.0e-12
    ok_hi = ok_hi and hi.closed_form_rho == 0.9
    ok_hi = ok_hi and hi.n_metrics_covered == 4
    if ok_hi:
        passed += 1
        print("  ✅ M/M/1 rho=0.9, 20 x 8000: Wq 9, W 10, L 9, rho 0.9 all covered")
    else:
        failed += 1
        print(
            "  ❌ high-utilisation validation failed:", hi.n_metrics_covered, "of",
            hi.n_metrics_checked, hi.wait_ci_lower, hi.wait_mean, hi.wait_ci_upper,
        )

    # ── M/M/2, with Wq from the frozen Erlang C ──────────────────────────────
    var mmc = replicate_mm1_flat(1.2, 1.0, 4000, 2, 10, 12345, 0.95, 5)
    var ok_mmc = mmc.status == DE_OK and mmc.capacity == 2
    ok_mmc = ok_mmc and mmc.closed_form_rho == 0.6
    ok_mmc = ok_mmc and fabs(mmc.closed_form_wait - 0.5625) < 1.0e-12
    ok_mmc = ok_mmc and fabs(mmc.closed_form_system - 1.5625) < 1.0e-12
    ok_mmc = ok_mmc and fabs(mmc.closed_form_number - 1.875) < 1.0e-12
    ok_mmc = ok_mmc and mmc.n_metrics_covered == 4
    if ok_mmc:
        passed += 1
        print(
            "  ✅ M/M/2 (1.2, 1.0): Erlang C = 0.45 gives Wq 0.5625, W 1.5625, L 1.875 —",
            "all four covered",
        )
    else:
        failed += 1
        print(
            "  ❌ M/M/2 validation failed:", mmc.closed_form_wait, mmc.closed_form_system,
            mmc.closed_form_number, mmc.n_metrics_covered,
        )

    # ── the check has TEETH: a run too short to be unbiased must FAIL it ──────
    var short_run = replicate_mm1_flat(0.95, 1.0, 400, 1, 20, 4, 0.95, 5)
    var ok_short = short_run.status == DE_OK and short_run.n_reps_run == 20
    ok_short = ok_short and short_run.warmup_jobs_used == 55
    ok_short = ok_short and short_run.n_metrics_checked == 4
    ok_short = ok_short and short_run.n_metrics_covered == 1
    ok_short = ok_short and not short_run.wait_covered
    ok_short = ok_short and short_run.wait_ci_upper < short_run.closed_form_wait
    if ok_short:
        passed += 1
        print(
            "  ✅ rho=0.95 with only 400 customers: MSER discards 55 and the intervals still",
            "sit BELOW the exact values — 1 of 4 covered. The check can fail, so it means",
            "something",
        )
    else:
        failed += 1
        print(
            "  ❌ the short high-utilisation run did not report its bias:", short_run.status,
            short_run.warmup_jobs_used, short_run.n_metrics_covered, short_run.wait_ci_upper,
            short_run.closed_form_wait,
        )

    # ── refusals on the validation driver ─────────────────────────────────────
    var nan = 0.0 / 0.0
    var refusals = replicate_mm1_flat(2.0, 2.0, 400, 1, 10, 1, 0.95, 5).status == DE_ERR_UNSTABLE
    refusals = refusals and replicate_mm1_flat(
        3.0, 1.0, 400, 2, 10, 1, 0.95, 5
    ).status == DE_ERR_UNSTABLE
    refusals = refusals and replicate_mm1_flat(0.0, 2.0, 400, 1, 10, 1, 0.95, 5).status == DE_ERR_RATE_RANGE
    refusals = refusals and replicate_mm1_flat(1.0, nan, 400, 1, 10, 1, 0.95, 5).status == DE_ERR_RATE_RANGE
    refusals = refusals and replicate_mm1_flat(1.0, 2.0, 0, 1, 10, 1, 0.95, 5).status == DE_ERR_EMPTY
    refusals = refusals and replicate_mm1_flat(
        1.0, 2.0, DE_MAX_JOBS + 1, 1, 10, 1, 0.95, 5
    ).status == DE_ERR_DIMENSION_TOO_LARGE
    refusals = refusals and replicate_mm1_flat(1.0, 2.0, 400, 0, 10, 1, 0.95, 5).status == DE_ERR_CAPACITY
    refusals = refusals and replicate_mm1_flat(1.0, 2.0, 400, 1, 1, 1, 0.95, 5).status == DE_ERR_TOO_FEW_REPS
    refusals = refusals and replicate_mm1_flat(
        1.0, 2.0, 400, 1, DE_MAX_REPLICATIONS + 1, 1, 0.95, 5
    ).status == DE_ERR_DIMENSION_TOO_LARGE
    refusals = refusals and replicate_mm1_flat(1.0, 2.0, 400, 1, 10, -1, 0.95, 5).status == DE_ERR_SEED_RANGE
    refusals = refusals and replicate_mm1_flat(1.0, 2.0, 400, 1, 10, 1, 1.0, 5).status == DE_ERR_LEVEL_RANGE
    refusals = refusals and replicate_mm1_flat(1.0, 2.0, 400, 1, 10, 1, 0.95, 0).status == DE_ERR_BATCH_RANGE
    if refusals:
        passed += 1
        print(
            "  ✅ twelve validation refusals, including rho = 1 for one server and rho = 1.5",
            "for two — an unstable queue has no steady state to cover",
        )
    else:
        failed += 1
        print(
            "  ❌ validation refusal codes wrong:",
            replicate_mm1_flat(2.0, 2.0, 400, 1, 10, 1, 0.95, 5).status,
            replicate_mm1_flat(1.0, 2.0, 400, 1, 1, 1, 0.95, 5).status,
            replicate_mm1_flat(1.0, 2.0, 400, 1, 10, 1, 0.95, 0).status,
        )

    # Every refusal leaves the four intervals declared ABSENT, not zero-width.
    var refused = replicate_mm1_flat(2.0, 2.0, 400, 1, 10, 1, 0.95, 5)
    if not refused.has_wait_ci and not refused.has_system_ci \
            and not refused.has_number_ci and not refused.has_util_ci \
            and refused.n_metrics_checked == 0 and refused.n_metrics_covered == 0 \
            and not refused.wait_covered:
        passed += 1
        print("  ✅ a refusal reports zero metrics CHECKED, distinctly from zero metrics covered")
    else:
        failed += 1
        print("  ❌ a refusal leaked an interval:", refused.has_wait_ci, refused.n_metrics_checked)

    print("  [discrete_event.replicate] Passed:", passed, "Failed:", failed)
