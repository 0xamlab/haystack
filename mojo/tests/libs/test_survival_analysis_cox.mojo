"""test_survival_analysis_cox.mojo — known values for the Efron Cox proportional-hazards fit.

Hand-written. The reference is an independently written Python Efron partial likelihood
maximised by numerically-differentiated Newton -- a different likelihood evaluator, a
different derivative source and a different linear solver from the kernel's analytic score,
analytic information and Cholesky. Dataset (8 rows, 2 covariates, a tie at t=1, a tie at
t=3, censoring at 2 and 5):

    x1 x2   t  event            reference (Python, independent)
     0  1   1    1              beta   = [-0.2413839573056762, 0.04458087834011487]
     1  0   1    1              se     = [ 0.4087650874795277, 0.398339210926859]
     2  1   2    0              loglik = -7.9227983586741475
     0  3   3    1              null   = -8.11969625295725
     1  2   3    1
     3  0   4    1              Breslow on the SAME data: [-0.20834402502483543,
     2  2   5    0                                          0.013760142011319091]
     0  0   6    1

1. THE TIE RULE IS DISCRIMINATED, not assumed. Efron and Breslow differ by 0.033 in beta_1 on
   this sample, which is far larger than the agreement tolerance, so the suite proves the
   kernel implements the tie rule it claims and not the cheaper one.
2. A ZERO COEFFICIENT IS NOT A REFUSAL. 2 rows with 2 covariates makes the observed
   information exactly `x x^T` for one centred row -- rank 1 -- while remaining numerically
   positive definite by a 2e-10 pivot, so the frozen `mat_is_positive_definite` admits it and
   the frozen `mat_solve` then returns its all-zeros singular sentinel. A zero step satisfies
   both convergence tests trivially, and the kernel used to report `status = ok`,
   `converged = true`, `beta = [0, 0]`, `loglik == loglik_null`, `lr = 0` with
   `score = [-0.534, -0.057]`: a published coefficient of zero on a sample whose MLE is at
   infinity. That is now `information_matrix_not_positive_definite`, and the assertion below
   fails against the unrepaired kernel.
3. THE ITERATION CEILING IS ONE NUMBER. `COX_MAX_ITER == PAR_MAX_ITER` is asserted here
   because the capability gate requires each file to declare its own literal ceiling, and two
   literals in two files with no assertion between them are a drift waiting to happen.
"""
from std.math import abs as fabs

from survival_analysis.base import (
    SA_ERR_BAD_ITER,
    SA_ERR_BAD_TOL,
    SA_ERR_NO_COVARIATE_VARIATION,
    SA_ERR_SEPARATION,
    SA_ERR_SHAPE,
    SA_ERR_SINGULAR_INFORMATION,
    SA_ERR_TOO_MANY_COVARIATES,
    SA_OK,
    sa_status_name,
)
from survival_analysis.cox import (
    COX_MAX_ITER,
    cox_baseline_cumhaz,
    cox_fit,
    cox_linear_predictor,
)
from survival_analysis.parametric import PAR_MAX_ITER

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
    var slop = rel * fabs(want)
    if slop < rel:
        slop = rel
    return fabs(got - want) <= slop


fn main() raises:
    var passed = 0
    var failed = 0
    print("[survival_analysis.cox] hand-written known values")

    var x = _f(0.0, 1.0, 1.0, 0.0, 2.0, 1.0, 0.0, 3.0, 1.0, 2.0, 3.0, 0.0, 2.0, 2.0, 0.0, 0.0)
    var t = _f(1.0, 1.0, 2.0, 3.0, 3.0, 4.0, 5.0, 6.0)
    var e = _i(1, 1, 0, 1, 1, 1, 0, 1)
    var fit = cox_fit(x, 8, 2, t, e, 400, 1e-12)

    if fit.status != SA_OK or fit.n_covariates != 2:
        failed += 1
        print("  ❌ cox_fit refused:", sa_status_name(fit.status))
    else:
        # The reference was produced by numerical differentiation, so it is itself only good
        # to about 1e-9; the tolerance is that of the REFERENCE, stated rather than tuned.
        var beta_ok = _rel(fit.beta[0], -0.2413839573056762, 1e-8) and _rel(
            fit.beta[1], 0.04458087834011487, 1e-7
        )
        var se_ok = _rel(fit.std_error[0], 0.4087650874795277, 1e-8) and _rel(
            fit.std_error[1], 0.398339210926859, 1e-8
        )
        var ll_ok = _rel(fit.loglik, -7.9227983586741475, 1e-9) and _rel(
            fit.loglik_null, -8.11969625295725, 1e-9
        )
        if beta_ok and se_ok and ll_ok and fit.has_loglik and fit.n_events == 6:
            passed += 1
            print("  ✅ beta, SEs, log-likelihood and null all agree with an independently"
                  " written Efron partial likelihood + numerical-differentiation Newton")
        else:
            failed += 1
            print("  ❌ Efron known values:", fit.beta[0], fit.beta[1], fit.std_error[0],
                  fit.loglik, fit.loglik_null)

        # ── 1. the tie rule is discriminated from Breslow ────────────────────
        var breslow_b0 = -0.20834402502483543
        if fabs(fit.beta[0] - breslow_b0) > 0.03 and fabs(fit.beta[0] + 0.2413839573056762) < 1e-8:
            passed += 1
            print("  ✅ the fit is Efron, not Breslow: the two differ by 0.033 in beta_1 on"
                  " this tied sample and the kernel lands on the Efron value")
        else:
            failed += 1
            print("  ❌ the tie rule is not discriminated")

        # the score is zero at the optimum and the LR statistic is non-negative
        if fit.max_abs_score < 1e-9 and fit.lr_statistic >= 0.0 and fit.loglik_monotone:
            passed += 1
            print("  ✅ the returned point is stationary (max |score| =", fit.max_abs_score,
                  "), the LR statistic is non-negative and the ascent was monotone")
        else:
            failed += 1
            print("  ❌ stationarity/LR/monotonicity:", fit.max_abs_score, fit.lr_statistic)

        # the linear predictor and the baseline hazard at the fitted beta
        var beta = _f(fit.beta[0], fit.beta[1])
        var lp = cox_linear_predictor(x, 8, 2, beta)
        var bl = cox_baseline_cumhaz(x, 8, 2, t, e, beta)
        if lp.status == SA_OK and bl.status == SA_OK and bl.monotone:
            var mono = True
            for j in range(1, bl.n_event_times):
                if bl.cum_hazard[j] < bl.cum_hazard[j - 1]:
                    mono = False
                if bl.baseline_survival[j] > bl.baseline_survival[j - 1]:
                    mono = False
            if mono and bl.n_event_times == 4:
                passed += 1
                print("  ✅ the baseline cumulative hazard is non-decreasing and its survival"
                      " non-increasing over the 4 distinct event times, at the fitted beta")
            else:
                failed += 1
                print("  ❌ baseline monotonicity")
        else:
            failed += 1
            print("  ❌ linear predictor or baseline refused:", sa_status_name(lp.status),
                  sa_status_name(bl.status))

    # ── 2. a rank-1 information matrix is not a fit of zero ──────────────────
    var deg = cox_fit(
        _f(0.7516799999999997, 1.14126, -0.31655999999999984, 1.0266000000000002),
        2, 2, _f(71709000.0, 58989000.00000001), _i(1, 1), 400, 1e-13,
    )
    if deg.status == SA_ERR_SINGULAR_INFORMATION:
        passed += 1
        print("  ✅ 2 rows x 2 covariates is refused as"
              " information_matrix_not_positive_definite; it used to return status ok with"
              " beta = [0, 0] and a score of -0.534")
    else:
        failed += 1
        print("  ❌ the rank-1 case returned", sa_status_name(deg.status), "with",
              len(deg.beta), "coefficients")
    if deg.status != SA_OK and len(deg.beta) == 0:
        passed += 1
        print("  ✅ the refusal carries no coefficient list at all, so beta[0] cannot be read"
              " as zero")
    else:
        failed += 1
        print("  ❌ a refused fit still exposes coefficients")

    # ── 3. the iteration ceiling is one number for the package ───────────────
    if COX_MAX_ITER == PAR_MAX_ITER and COX_MAX_ITER == 500:
        passed += 1
        print("  ✅ COX_MAX_ITER == PAR_MAX_ITER == 500: the two file-local literals the"
              " capability gate requires have not drifted apart")
    else:
        failed += 1
        print("  ❌ iteration ceilings differ:", COX_MAX_ITER, PAR_MAX_ITER)

    # ── refusals, including the hostile (List, Int) pairs ────────────────────
    var wrap = 6148914691236517206
    if 3 * wrap == 2:
        passed += 1
        print("  ✅ 3 * 6148914691236517206 == 2: the wrapping multiply exists in this"
              " compiler, so a guard written on the product is not a guard")
    else:
        failed += 1
        print("  ❌ the wrapping-multiply premise does not hold here")

    var refusals = (
        cox_fit(_f(1.0, 2.0), 3, wrap, t, e, 10, 1e-8).status == SA_ERR_TOO_MANY_COVARIATES
        and cox_fit(x, 8, 65, t, e, 10, 1e-8).status == SA_ERR_TOO_MANY_COVARIATES
        and cox_fit(x, -1, 2, t, e, 10, 1e-8).status == SA_ERR_SHAPE
        and cox_fit(x, 8, -2, t, e, 10, 1e-8).status == SA_ERR_SHAPE
        and cox_fit(x, 7, 2, t, e, 10, 1e-8).status == SA_ERR_SHAPE
        and cox_fit(x, 8, 2, t, e, 0, 1e-8).status == SA_ERR_BAD_ITER
        and cox_fit(x, 8, 2, t, e, -5, 1e-8).status == SA_ERR_BAD_ITER
        and cox_fit(x, 8, 2, t, e, COX_MAX_ITER + 1, 1e-8).status == SA_ERR_BAD_ITER
        and cox_fit(x, 8, 2, t, e, 10, 0.0).status == SA_ERR_BAD_TOL
        and cox_fit(x, 8, 2, t, e, 10, 2.0).status == SA_ERR_BAD_TOL
    )
    if refusals:
        passed += 1
        print("  ✅ n_cols = 6148914691236517206 (the wrapping pair), 65 covariates,"
              " negative n_rows/n_cols, a short matrix, max_iter 0/-5/501 and tol 0/2"
              " are each refused with their own code")
    else:
        failed += 1
        print("  ❌ a refusal path did not fire")

    # a constant covariate carries no information and is named as such
    var const_x = _f(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    if cox_fit(const_x, 8, 1, t, e, 10, 1e-8).status == SA_ERR_NO_COVARIATE_VARIATION:
        passed += 1
        print("  ✅ a constant covariate is refused as covariate_is_constant, not fitted at 0")
    else:
        failed += 1
        print("  ❌ a constant covariate was accepted")

    # perfect separation: the earlier time always has the larger covariate
    var sep = cox_fit(_f(0.0, 1.0), 2, 1, _f(1.0, 2.0), _i(1, 1), 400, 1e-10)
    if sep.status == SA_ERR_SEPARATION or sep.status == SA_ERR_SINGULAR_INFORMATION:
        passed += 1
        print("  ✅ a separating covariate is refused (", sa_status_name(sep.status),
              ") rather than reported as a hazard ratio at the |beta| ceiling")
    else:
        failed += 1
        print("  ❌ separation was fitted:", sa_status_name(sep.status))

    var lf5 = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _i(5, 5, 5, 5, 5)
    if (
        cox_fit(lf5, 5, 5, lf5, li5, 5, 0.5).status != SA_OK
        and cox_linear_predictor(lf5, 5, 5, lf5).status != SA_OK
        and cox_baseline_cumhaz(lf5, 5, 5, lf5, li5, lf5).status != SA_OK
    ):
        passed += 1
        print("  ✅ the fixed 5-element/5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was accepted")

    print("  [survival_analysis.cox] Passed:", passed, "Failed:", failed)
