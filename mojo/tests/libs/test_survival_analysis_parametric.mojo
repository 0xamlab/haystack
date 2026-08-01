"""test_survival_analysis_parametric.mojo — known values for the Weibull and lognormal MLEs.

Hand-written. Two of the four groups below are CLOSED FORMS a reader can verify without
running anything; the other two come from estimators written independently in Python.

1. THE LOGNORMAL CLOSED FORM. With no censoring the MLE is `mu = mean(log t)`,
   `sigma = sqrt(mean((log t - mu)^2))`. On `times = 1, 2, 4, 8` the log-times are
   `0, ln2, 2ln2, 3ln2`, so

       mu    = 1.5 ln 2      = 1.0397207708399179
       sigma = sqrt(1.25) ln 2 = 0.7749621070721792

   and the log-likelihood collapses because `sum z_i^2 = n` by construction:

       loglik = -sum log t_i - n log sigma - (n/2) log 2pi - n/2 = -8.814872636480125
       aic    = 4 - 2 loglik = 21.62974527296025

   The comparison tolerance is 1e-9 RELATIVE, not machine epsilon: this tree's `log` is about
   1e-10 off correctly-rounded, and a golden value must respect that floor rather than pretend
   the kernel is exact.

2. THE LIKELIHOOD THAT HAS NO MAXIMUM. `[3, 3, 1]` with `event = [1, 1, 0]` has both failures
   at one recorded time and its only censored row below them, so `mu = log 3, sigma -> 0`
   drives the likelihood to `+infinity`; verified independently in Python at
   `sigma = 1e-1 -> +0.57`, `1e-4 -> +14.39`, `1e-10 -> +42.02`, `1e-200 -> +916.99`. The
   correct answer is a refusal. Before the repair the kernel returned `status = ok`,
   `sigma = 2.2e-08`, `loglik = +31.21`, `AIC = -58.42` -- and at `tol = 1e-4` the same data
   gave `AIC = -25.63`, a 33-unit swing from the tolerance alone. So the refusal is asserted
   at FOUR tolerances and TWO iteration limits: a verdict that moves with `tol` is not a
   verdict. These assertions fail against the unrepaired kernel at every one of the six.
3. THE SIBLING ASYMMETRY IS CLOSED. `weibull_mle` already refused that sample through its
   no-sign-change bracket test. Both families are asserted to refuse it now, because a caller
   comparing AIC across families saw Weibull refuse and lognormal "win" with AIC = -58.
4. THE WEIBULL CENSORED MLE against an independent Python profile-bisection AND an
   independent direct 2-D maximisation of the same likelihood, on
   `times = 10, 20, 25, 30, 35, 40, 45, 50, 55, 60`,
   `event = 1, 1, 0, 1, 1, 0, 1, 0, 1, 0`:

       shape 2.0780874260301454   scale 51.40436958826231   loglik -29.09786344694982
       ks_distance_vs_km 0.10208250101925287

   plus the two identities the module publishes, `g(k_hat) = 0` and
   `sum (t_i/eta)^k - r = 0`, asserted at the RETURNED parameters.
"""
from std.math import abs as fabs
from std.math import log, sqrt

from survival_analysis.base import (
    SA_ERR_BAD_ITER,
    SA_ERR_BAD_TOL,
    SA_ERR_CENSOR_LENGTH,
    SA_ERR_EMPTY,
    SA_ERR_LIKELIHOOD_UNBOUNDED,
    SA_ERR_NONPOSITIVE_TIME,
    SA_ERR_NOT_CONVERGED,
    SA_ERR_NO_EVENTS,
    SA_OK,
    sa_status_name,
)
from survival_analysis.parametric import PAR_MAX_ITER, lognormal_mle, weibull_mle

comptime EPS: Float64 = 2.220446049250313e-16


fn _f(*v: Float64) -> List[Float64]:
    var o = List[Float64]()
    for i in range(len(v)):
        o.append(v[i])
    return o^


fn _i(*v: Int) -> List[Int]:
    var o = List[Int]()
    for i in range(len(v)):
        o.append(v[i])
    return o^


fn _rel(got: Float64, want: Float64, rel: Float64) -> Bool:
    """Per-ITEM relative comparison against THAT item's own magnitude."""
    var slop = rel * fabs(want)
    if slop < rel:
        slop = rel
    return fabs(got - want) <= slop


fn main() raises:
    var passed = 0
    var failed = 0
    print("[survival_analysis.parametric] hand-written known values")

    # ── 1. the lognormal closed form ─────────────────────────────────────────
    var un = lognormal_mle(_f(1.0, 2.0, 4.0, 8.0), _i(1, 1, 1, 1), 200, 1e-13)
    if un.status != SA_OK:
        failed += 1
        print("  ❌ uncensored lognormal refused:", sa_status_name(un.status))
    else:
        var ln2 = log(2.0)
        var want_mu = 1.5 * ln2
        var want_sigma = sqrt(1.25) * ln2
        if (
            _rel(un.mu, want_mu, 1e-9)
            and _rel(un.sigma, want_sigma, 1e-9)
            and _rel(un.loglik, -8.814872636480125, 1e-9)
            and _rel(un.aic, 21.62974527296025, 1e-9)
            and un.loglik_monotone
            and un.n_censored == 0
        ):
            passed += 1
            print("  ✅ uncensored [1,2,4,8]: mu = 1.5 ln2, sigma = sqrt(1.25) ln2,"
                  " loglik = -8.814872636480125, aic = 21.62974527296025")
        else:
            failed += 1
            print("  ❌ closed form:", un.mu, want_mu, un.sigma, want_sigma, un.loglik)
        if un.loglik_worst_decrease <= un.loglik_decrease_budget:
            passed += 1
            print("  ✅ the EM log-likelihood never decreased past its own error budget"
                  " (worst", un.loglik_worst_decrease, "of", un.loglik_decrease_budget, ")")
        else:
            failed += 1
            print("  ❌ monotonicity diagnostic inconsistent with an ok status")

    # ── 2. the unbounded likelihood, at six settings ─────────────────────────
    var t3 = _f(3.0, 3.0, 1.0)
    var e3 = _i(1, 1, 0)
    var tols = _f(1e-4, 1e-6, 1e-10, 1e-13)
    var all_refused = True
    for i in range(len(tols)):
        var r = lognormal_mle(t3, e3, 200, tols[i])
        if r.status != SA_ERR_LIKELIHOOD_UNBOUNDED:
            all_refused = False
            print("     tol", tols[i], "->", sa_status_name(r.status), "sigma", r.sigma)
    var r30 = lognormal_mle(t3, e3, 30, 1e-13)
    var r500 = lognormal_mle(t3, e3, PAR_MAX_ITER, 1e-13)
    if r30.status != SA_ERR_LIKELIHOOD_UNBOUNDED or r500.status != SA_ERR_LIKELIHOOD_UNBOUNDED:
        all_refused = False
    if all_refused:
        passed += 1
        print("  ✅ [3,3,1]/[1,1,0] refused as likelihood_unbounded_no_mle_exists at"
              " tol 1e-4/1e-6/1e-10/1e-13 and max_iter 30/500 -- the verdict does not"
              " depend on the stopping rule")
    else:
        failed += 1
        print("  ❌ the unbounded sample was fitted at some setting")

    # nothing that could be read as an estimate comes back with the refusal
    if (
        r500.mu == 0.0
        and r500.sigma == 0.0
        and r500.loglik == 0.0
        and r500.aic == 0.0
        and not r500.converged
        and not r500.has_ks
    ):
        passed += 1
        print("  ✅ the refusal carries no parameter, no loglik and no AIC")
    else:
        failed += 1
        print("  ❌ the refusal carried numbers a caller could mistake for a fit")

    # second reproducer, and the boundary case that must still be FITTED
    var second = lognormal_mle(_f(100.0, 100.0, 100.0, 40.0, 70.0), _i(1, 1, 1, 0, 0), 200, 1e-6)
    # the same sample with one censored row moved ABOVE the tied failures has a maximum
    var above = lognormal_mle(_f(100.0, 100.0, 100.0, 40.0, 170.0), _i(1, 1, 1, 0, 0), 400, 1e-12)
    if second.status == SA_ERR_LIKELIHOOD_UNBOUNDED and above.status == SA_OK:
        passed += 1
        print("  ✅ tied failures with every censored row BELOW them are refused; moving one"
              " censored row above them restores a maximum and the fit is returned")
    else:
        failed += 1
        print("  ❌ the existence test is not discriminating:", sa_status_name(second.status),
              sa_status_name(above.status))

    # a nearly-tied sample is NOT refused: it has a real, small-sigma MLE
    var near = lognormal_mle(_f(3.0, 3.0000000001, 1.0), _i(1, 1, 0), 400, 1e-13)
    if near.status == SA_OK and near.sigma > 0.0:
        passed += 1
        print("  ✅ failures at 3.0 and 3.0000000001 are NOT refused: exact ties are the"
              " degenerate family, near-ties have a genuine small-sigma answer")
    else:
        failed += 1
        print("  ❌ a near-tie was refused as degenerate:", sa_status_name(near.status))

    # ── 3. both families agree on the degenerate sample ──────────────────────
    var w3 = weibull_mle(t3, e3, 200, 1e-13)
    if w3.status == SA_ERR_NOT_CONVERGED and r500.status == SA_ERR_LIKELIHOOD_UNBOUNDED:
        passed += 1
        print("  ✅ Weibull refuses (no sign change) and lognormal refuses (no maximum) on"
              " the same sample; neither family can 'win' a model comparison by default")
    else:
        failed += 1
        print("  ❌ family asymmetry still open:", sa_status_name(w3.status))

    # ── 4. the Weibull censored MLE ──────────────────────────────────────────
    var tw = _f(10.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0)
    var ew = _i(1, 1, 0, 1, 1, 0, 1, 0, 1, 0)
    var wf = weibull_mle(tw, ew, 400, 1e-13)
    if wf.status != SA_OK:
        failed += 1
        print("  ❌ weibull_mle refused:", sa_status_name(wf.status))
    else:
        if (
            _rel(wf.shape, 2.0780874260301454, 1e-8)
            and _rel(wf.scale, 51.40436958826231, 1e-8)
            and _rel(wf.loglik, -29.09786344694982, 1e-8)
            and _rel(wf.ks_distance_vs_km, 0.10208250101925287, 1e-8)
            and wf.n_events == 6
            and wf.n_censored == 4
        ):
            passed += 1
            print("  ✅ Weibull shape 2.0780874260301454, scale 51.40436958826231,"
                  " loglik -29.09786344694982, KS-vs-KM 0.10208250101925287")
        else:
            failed += 1
            print("  ❌ Weibull known values:", wf.shape, wf.scale, wf.loglik,
                  wf.ks_distance_vs_km)
        # Each identity is judged against ITS OWN scale and floor. `g(k_hat)` is a ratio of
        # two sums in which the shifted-power errors largely cancel, and it comes back at
        # -9.3e-15. `sum (t/eta)^k - r` is a sum of magnitude `r = 6` built from `exp` and
        # `log`, whose accuracy in this tree is ~1e-10 RELATIVE, so its floor is
        # `1e-10 * 6 = 6e-10` and it comes back at -5.5e-10. Judging the second against the
        # first's tolerance would be judging one item by another item's scale.
        if fabs(wf.shape_equation_residual) < 1e-13 and fabs(wf.scale_identity_residual) < (
            1e-9 * 6.0
        ):
            passed += 1
            print("  ✅ both defining identities vanish at the RETURNED parameters to their"
                  " own floors: g(k) =", wf.shape_equation_residual,
                  ", sum (t/eta)^k - r =", wf.scale_identity_residual)
        else:
            failed += 1
            print("  ❌ the returned parameters do not satisfy their own equations")

    # ── refusals ─────────────────────────────────────────────────────────────
    var empty_f = List[Float64]()
    var empty_i = List[Int]()
    var refusals = (
        weibull_mle(empty_f, empty_i, 10, 1e-8).status == SA_ERR_EMPTY
        and weibull_mle(tw, _i(1, 1), 10, 1e-8).status == SA_ERR_CENSOR_LENGTH
        and weibull_mle(_f(0.0, 1.0), _i(1, 1), 10, 1e-8).status == SA_ERR_NONPOSITIVE_TIME
        and lognormal_mle(_f(0.0, 1.0), _i(1, 1), 10, 1e-8).status == SA_ERR_NONPOSITIVE_TIME
        and weibull_mle(tw, _i(0, 0, 0, 0, 0, 0, 0, 0, 0, 0), 10, 1e-8).status == SA_ERR_NO_EVENTS
        and lognormal_mle(tw, _i(0, 0, 0, 0, 0, 0, 0, 0, 0, 0), 10, 1e-8).status
        == SA_ERR_NO_EVENTS
        and weibull_mle(tw, ew, 0, 1e-8).status == SA_ERR_BAD_ITER
        and weibull_mle(tw, ew, -5, 1e-8).status == SA_ERR_BAD_ITER
        and weibull_mle(tw, ew, PAR_MAX_ITER + 1, 1e-8).status == SA_ERR_BAD_ITER
        and lognormal_mle(tw, ew, PAR_MAX_ITER + 1, 1e-8).status == SA_ERR_BAD_ITER
        and weibull_mle(tw, ew, 10, 0.0).status == SA_ERR_BAD_TOL
        and weibull_mle(tw, ew, 10, 2.0).status == SA_ERR_BAD_TOL
    )
    if refusals:
        passed += 1
        print("  ✅ empty, length mismatch, time 0, all-censored, max_iter 0/-5/501 and"
              " tol 0/2 are each refused with their own code")
    else:
        failed += 1
        print("  ❌ a refusal path did not fire")

    # a time of exactly 0 is legal for a KM curve and illegal here; that asymmetry is
    # deliberate and is asserted rather than left to a reader to discover
    if weibull_mle(_f(0.0, 1.0, 2.0), _i(1, 1, 1), 10, 1e-8).status == SA_ERR_NONPOSITIVE_TIME:
        passed += 1
        print("  ✅ t = 0 is refused here though base.sa_validate_observations accepts it:"
              " these estimators take log t and that is their constraint, not the package's")
    else:
        failed += 1
        print("  ❌ t = 0 was accepted by a log-domain estimator")

    var lf5 = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _i(5, 5, 5, 5, 5)
    if weibull_mle(lf5, li5, 5, 0.5).status != SA_OK and lognormal_mle(
        lf5, li5, 5, 0.5
    ).status != SA_OK:
        passed += 1
        print("  ✅ the fixed 5-element/5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was accepted")

    print("  [survival_analysis.parametric] Passed:", passed, "Failed:", failed)
