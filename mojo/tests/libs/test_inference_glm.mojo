"""test_inference_glm.mojo — known-value tests for the logistic and Poisson GLM drivers.

Hand-written. Both families are SATURATED by a single binary covariate, which means the
maximum-likelihood estimate has an elementary closed form, so every coefficient and every
standard error below is checked against algebra rather than against a plausible number.

*Logistic, saturated 2x2.* Three observations at `x = 0` with one success, three at `x = 1`
with two. A saturated model reproduces the group proportions exactly, so `p_0 = 1/3` and
`p_1 = 2/3`, and therefore

    intercept = logit(1/3) = log(1/2) = -0.6931471805599453
    slope     = logit(2/3) - logit(1/3) = log(4) = 1.3862943611198906    (the log odds ratio)
    se(slope) = sqrt(1/a + 1/b + 1/c + 1/d) = sqrt(1 + 1/2 + 1/2 + 1) = sqrt(3)
    se(int)   = sqrt(1/a + 1/b)             = sqrt(1 + 1/2)             = sqrt(1.5)

The two standard errors are the classical 2x2-table forms and they come out of the frozen
`linear_models.logistic_std_errors` to the last bit: 1.7320508075688772 and 1.224744871391589.
The fitted probabilities are independently recovered by the frozen
`linear_models.logistic_predict_proba` and must equal the group proportions.

*Logistic with no covariates.* `p = 0` is an intercept-only model, whose MLE is
`logit(mean(y))` in closed form, with `se = 1 / sqrt(n phat (1-phat))`. For `y = [1,1,1,0]`
that is `log 3 = 1.0986122886681098` and `1/sqrt(4 * 0.1875) = 1.1547005383792515`, and the
log-likelihood is `3 log(0.75) + log(0.25) = -2.2493405787206705`.

*Poisson, saturated.* Three observations at `x = 0` summing to 6 and three at `x = 1` summing
to 30. A saturated log-link model fits each group's mean exactly, so

    intercept = log(6/3)  = log 2 = 0.6931471805599453
    slope     = log(30/3) - log 2 = log 5 = 1.6094379124341003
    se(int)   = sqrt(1 / sum y_0)           = sqrt(1/6)
    se(slope) = sqrt(1/sum y_0 + 1/sum y_1) = sqrt(1/6 + 1/30) = sqrt(0.2)

and the residual deviance `2 sum [y log(y/mu) - (y - mu)]` with `mu` equal to the group means is
1.8519168295566508. `exp(intercept)` and `exp(intercept + slope)` must return 2.0 and 10.0,
which is the same claim reached from the other direction.

*And the refusals, which are the point of the module.* Separable data are refused with a
separating hyperplane as the witness, an iteration cap is refused with its count, a response
outside the family's support is refused, and none of them returns a single coefficient. The
frozen `linear_models.logistic_fit` on the separable case returns
`weights = [26.61180993388579]` with `converged = False` and a standard error of 424777.88 —
that measured value is asserted here directly, so this suite states both what the frozen kernel
does and what this driver does instead.
"""
from std.math import abs as fabs, exp, log, sqrt

from inference.core import (
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_NON_FINITE,
    INF_ERR_NOT_CONVERGED,
    INF_ERR_RESPONSE_RANGE,
    INF_ERR_SEPARABLE,
    INF_ERR_SHAPE,
    INF_ERR_TUNING,
    INF_OK,
    MAX_IRLS_ITER,
    inference_absent,
    inference_finite,
)
from inference.glm import (
    FAMILY_BINOMIAL_LOGIT,
    FAMILY_POISSON_LOG,
    GLM_MARGIN_ABSENT,
    GlmFit,
    glm_input_defect,
    glm_logistic_fit_flat,
    glm_poisson_fit_flat,
)
from linear_models import logistic_fit, logistic_predict_proba, logistic_std_errors
from special_functions import log_gamma


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _no_fit(g: GlmFit) -> Bool:
    """A refusal carries NO coefficients, NO standard errors and NO Wald statistics.

    This is the single property the module exists for: there is no partial fit, so a caller
    cannot read an odds ratio off an unconverged or separable run.
    """
    return (
        g.status != INF_OK
        and not g.converged
        and len(g.coefficients) == 0
        and len(g.std_errors) == 0
        and len(g.wald_z) == 0
        and len(g.wald_p) == 0
        and g.intercept == 0.0
    )


def main():
    var passed: Int = 0
    var failed: Int = 0

    # ── the saturated 2x2 logistic design ─────────────────────────────────────
    var x2 = _floats(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    var y2 = _floats(0.0, 0.0, 1.0, 0.0, 1.0, 1.0)
    var sat = glm_logistic_fit_flat(x2, y2, 6, 1, 0.0, 200, 1.0e-12)

    if (
        sat.status == INF_OK
        and sat.family == FAMILY_BINOMIAL_LOGIT
        and sat.converged
        and len(sat.coefficients) == 1
        and fabs(sat.intercept - log(0.5)) <= 1.0e-9
        and fabs(sat.coefficients[0] - log(4.0)) <= 1.0e-9
        and sat.n_obs == 6
        and sat.n_params == 1
        and sat.n_iter <= sat.max_iter
    ):
        passed += 1
        print("  ✅ the saturated logistic MLE is log(1/2) and log(4) — the log odds ratio")
    else:
        failed += 1
        print("  ❌ saturated logistic:", sat.status, sat.intercept, sat.coefficients[0])

    if (
        len(sat.std_errors) == 2
        and fabs(sat.std_errors[0] - sqrt(3.0)) <= 1.0e-9
        and fabs(sat.std_errors[1] - sqrt(1.5)) <= 1.0e-9
        # the exact values the frozen kernel produces on this toolchain
        and sat.std_errors[0] == 1.7320508075688772
        and sat.std_errors[1] == 1.224744871391589
        and len(sat.wald_z) == 2
        and len(sat.wald_p) == 2
        and fabs(sat.wald_z[0] - sat.coefficients[0] / sat.std_errors[0]) <= 1.0e-15
        # z = log(4)/sqrt(3) = 0.8003, so the two-sided p is 0.4235 — nowhere near
        # significant, which is right for a 2x2 table with six observations
        and fabs(sat.wald_p[0] - 0.4235) <= 1.0e-3
    ):
        passed += 1
        print("  ✅ the standard errors are the 2x2 forms sqrt(3) and sqrt(1.5), bitwise")
    else:
        failed += 1
        print("  ❌ standard errors:", sat.std_errors[0], sqrt(3.0))

    # deviance = -2 log L for individual 0/1 responses (the saturated log-likelihood is 0)
    if (
        fabs(sat.deviance + 2.0 * sat.log_likelihood) <= 1.0e-12
        and sat.deviance > 0.0
        and fabs(sat.log_likelihood + 3.8190850059267407) <= 1.0e-9
    ):
        passed += 1
        print("  ✅ the deviance is -2 log L and the log-likelihood is -3.81908501")
    else:
        failed += 1
        print("  ❌ deviance:", sat.deviance, sat.log_likelihood)

    # ── the fitted probabilities, recovered by an independent frozen kernel ───
    var probs = logistic_predict_proba(x2, sat.coefficients, sat.intercept)
    if (
        len(probs) == 6
        and fabs(probs[0] - 1.0 / 3.0) <= 1.0e-9
        and fabs(probs[1] - 1.0 / 3.0) <= 1.0e-9
        and fabs(probs[2] - 1.0 / 3.0) <= 1.0e-9
        and fabs(probs[3] - 2.0 / 3.0) <= 1.0e-9
        and fabs(probs[4] - 2.0 / 3.0) <= 1.0e-9
        and fabs(probs[5] - 2.0 / 3.0) <= 1.0e-9
    ):
        passed += 1
        print("  ✅ frozen logistic_predict_proba recovers the group proportions 1/3 and 2/3")
    else:
        failed += 1
        print("  ❌ fitted probabilities:", probs[0], probs[3])

    # ── the intercept-only logistic model ─────────────────────────────────────
    var empty = List[Float64]()
    var y_io = _floats(1.0, 1.0, 1.0, 0.0)
    var io = glm_logistic_fit_flat(empty, y_io, 4, 0, 0.0, 200, 1.0e-12)
    if (
        io.status == INF_OK
        and io.converged
        and len(io.coefficients) == 0
        and len(io.std_errors) == 1
        and fabs(io.intercept - log(3.0)) <= 1.0e-9
        and fabs(io.std_errors[0] - 1.0 / sqrt(4.0 * 0.1875)) <= 1.0e-12
        and io.std_errors[0] == 1.1547005383792515
        and fabs(io.log_likelihood - (3.0 * log(0.75) + log(0.25))) <= 1.0e-9
        and io.n_params == 0
    ):
        passed += 1
        print("  ✅ an intercept-only logistic model is logit(ybar) = log 3, se 1/sqrt(0.75)")
    else:
        failed += 1
        print("  ❌ intercept-only logistic:", io.status, io.intercept, log(3.0))

    # ── separable data: the frozen behaviour, then the refusal ────────────────
    var x_sep = _floats(-2.0, -1.0, 1.0, 2.0)
    var y_sep = _floats(0.0, 0.0, 1.0, 1.0)
    var labels = _ints(0, 0, 1, 1)
    var frozen = logistic_fit(x_sep, labels, 0.0, 200, 1.0e-12)
    var frozen_se = logistic_std_errors(x_sep, labels, frozen.weights, frozen.bias, 0.0)
    if (
        # the frozen kernel returns a coefficient and a meaningless standard error
        not frozen.converged
        and frozen.n_iter == 200
        and frozen.weights[0] == 26.61180993388579
        and frozen_se[0] == 424777.880690872
    ):
        passed += 1
        print("  ✅ the frozen kernel returns 26.6 with se 424777.88 on separable data")
    else:
        failed += 1
        print("  ❌ frozen separable behaviour changed:", frozen.weights[0], frozen_se[0])

    var sep = glm_logistic_fit_flat(x_sep, y_sep, 4, 1, 0.0, 200, 1.0e-12)
    var sep_short = glm_logistic_fit_flat(x_sep, y_sep, 4, 1, 0.0, 2, 1.0e-12)
    if (
        _no_fit(sep)
        and sep.status == INF_ERR_SEPARABLE
        and sep.separation_witnessed
        # the witness is a real margin: min{eta : y=1} - max{eta : y=0} > 0
        and sep.separation_margin > 0.0
        and fabs(sep.separation_margin - 53.22361986777158) <= 1.0e-9
        and sep.n_iter == 200
        # a small iteration budget reaches the same refusal, never a coefficient
        and _no_fit(sep_short)
        and sep_short.status == INF_ERR_SEPARABLE
        and sep_short.n_iter == 2
    ):
        passed += 1
        print("  ✅ separable data are REFUSED with a positive-margin witness, at any budget")
    else:
        failed += 1
        print("  ❌ separable case:", sep.status, sep.separation_margin, len(sep.coefficients))

    # An L2 penalty makes the penalized optimum finite, so the estimate exists — and the
    # witness is still reported so a caller knows the estimate is only shrinkage.
    var ridged = glm_logistic_fit_flat(x_sep, y_sep, 4, 1, 1.0, 200, 1.0e-10)
    if (
        ridged.status == INF_OK
        and ridged.converged
        and len(ridged.coefficients) == 1
        and inference_finite(ridged.coefficients[0])
        and ridged.coefficients[0] > 0.0
        and ridged.separation_witnessed
        and ridged.separation_margin > 0.0
    ):
        passed += 1
        print("  ✅ with an L2 penalty the separable fit exists, and still reports the witness")
    else:
        failed += 1
        print("  ❌ penalized separable case:", ridged.status, len(ridged.coefficients))

    # ── non-convergence carries a count and no coefficients ──────────────────
    var slow = glm_logistic_fit_flat(x2, y2, 6, 1, 0.0, 1, 1.0e-14)
    if (
        _no_fit(slow)
        and slow.status == INF_ERR_NOT_CONVERGED
        and slow.n_iter == 1
        and slow.max_iter == 1
        and not slow.separation_witnessed
        and slow.separation_margin == GLM_MARGIN_ABSENT
    ):
        passed += 1
        print("  ✅ an iteration cap is a refusal that reports its count, not a last iterate")
    else:
        failed += 1
        print("  ❌ non-convergence:", slow.status, slow.n_iter, len(slow.coefficients))

    # ── a response outside the family's support ───────────────────────────────
    var y_half = _floats(0.0, 0.5, 1.0, 0.0, 1.0, 1.0)
    var y_neg = _floats(0.0, -3.0, 1.0, 0.0, 1.0, 1.0)
    var y_zeros = _floats(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    var y_ones = _floats(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    var half_fit = glm_logistic_fit_flat(x2, y_half, 6, 1, 0.0, 50, 1.0e-10)
    if (
        _no_fit(half_fit)
        and half_fit.status == INF_ERR_RESPONSE_RANGE
        # the frozen kernel treats any nonzero Int as a success, so -3 there is a success
        and glm_logistic_fit_flat(x2, y_neg, 6, 1, 0.0, 50, 1.0e-10).status
        == INF_ERR_RESPONSE_RANGE
        # one class is not two: an all-zero or all-one response has no log-odds
        and glm_logistic_fit_flat(x2, y_zeros, 6, 1, 0.0, 50, 1.0e-10).status
        == INF_ERR_RESPONSE_RANGE
        and glm_logistic_fit_flat(x2, y_ones, 6, 1, 0.0, 50, 1.0e-10).status
        == INF_ERR_RESPONSE_RANGE
    ):
        passed += 1
        print("  ✅ a 0.5, a -3 and a single-class response are all refused")
    else:
        failed += 1
        print("  ❌ a response outside 0/1 was accepted:", half_fit.status)

    # ── the saturated Poisson design ─────────────────────────────────────────
    var xp = _floats(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    var yp = _floats(1.0, 2.0, 3.0, 8.0, 10.0, 12.0)
    var pois = glm_poisson_fit_flat(xp, yp, 6, 1, 0.0, 200, 1.0e-12)
    if (
        pois.status == INF_OK
        and pois.family == FAMILY_POISSON_LOG
        and pois.converged
        and len(pois.coefficients) == 1
        and fabs(pois.intercept - log(2.0)) <= 1.0e-9
        and fabs(pois.coefficients[0] - log(5.0)) <= 1.0e-9
        # reached from the other direction: the fitted means ARE the group means
        and fabs(exp(pois.intercept) - 2.0) <= 1.0e-9
        and fabs(exp(pois.intercept + pois.coefficients[0]) - 10.0) <= 1.0e-8
    ):
        passed += 1
        print("  ✅ the saturated Poisson MLE is log 2 and log 5; fitted means are 2 and 10")
    else:
        failed += 1
        print("  ❌ saturated Poisson:", pois.status, pois.intercept, pois.coefficients[0])

    if (
        len(pois.std_errors) == 2
        and fabs(pois.std_errors[0] - sqrt(1.0 / 6.0 + 1.0 / 30.0)) <= 1.0e-9
        and fabs(pois.std_errors[1] - sqrt(1.0 / 6.0)) <= 1.0e-9
        and fabs(pois.std_errors[0] - 0.4472135954999579) <= 1.0e-12
        and fabs(pois.std_errors[1] - 0.408248290463863) <= 1.0e-12
        # residual deviance of the saturated-in-x model: 1.8519168295566508
        and fabs(pois.deviance - 1.8519168295566508) <= 1.0e-8
        and pois.deviance > 0.0
        and fabs(pois.wald_z[0] - pois.coefficients[0] / pois.std_errors[0]) <= 1.0e-15
        # z = log(5)/sqrt(0.2) = 3.598, so p is about 0.00032 — strongly significant
        and pois.wald_p[0] < 0.001
    ):
        passed += 1
        print("  ✅ Poisson SEs are sqrt(1/6+1/30) and sqrt(1/6); deviance is 1.85191683")
    else:
        failed += 1
        print("  ❌ Poisson SEs:", pois.std_errors[0], pois.std_errors[1], pois.deviance)

    # ── the Poisson log-likelihood is the FULL one, constant included ─────────
    # `log_likelihood` used to be the KERNEL `sum[y eta - mu]`, i.e. the full log-likelihood
    # plus `sum log Gamma(y+1)`. On this design that constant is 48.181136621270646, so the
    # kernel reported +37.23643587318105 where the log-likelihood is -10.944700748089598: the
    # wrong magnitude AND the wrong sign for a quantity that cannot be positive when every
    # response is an integer count (a sum of log probabilities). The constant cancels in an
    # LRT or an AIC DIFFERENCE on the same response, which is exactly why nothing here caught
    # it and why a caller comparing against another library would have been misled silently.
    #
    # References computed independently in double precision from the group means (mu = 2 for
    # x = 0, mu = 10 for x = 1): sum[y log mu - mu - log Gamma(y+1)]. The tolerance is 1e-7,
    # not 1e-12, because `special_functions.log_gamma` carries 1e-10..2e-9 of absolute error
    # per call on this toolchain (`log_gamma(13.0)` is 19.987214493640607 against a true
    # 19.987214495661885) and six of those are summed. Measured value: -10.944700747447602.
    var ll_ref = -10.944700748089598
    var lgamma_const = 48.181136621270646
    if (
        fabs(pois.log_likelihood - ll_ref) <= 1.0e-7
        # A sum of log probabilities is negative, and the kernel value was not.
        and pois.log_likelihood < 0.0
        # Definitively not the kernel: the two differ by the whole normalizing constant.
        and fabs(pois.log_likelihood - 37.23643587318105) > 48.0
        and fabs((pois.log_likelihood + lgamma_const) - 37.23643587318105) <= 1.0e-7
        # AIC needs no correction term now: -2 log L + 2 (p + 1) with p = 1.
        and fabs((-2.0 * pois.log_likelihood + 4.0) - 25.889401496179196) <= 1.0e-7
        # The binomial family's log-likelihood is untouched by this and still satisfies its
        # own family-specific identity, so the two families now mean the same thing by the
        # same name.
        and fabs(sat.deviance + 2.0 * sat.log_likelihood) <= 1.0e-12
        and sat.log_likelihood < 0.0
    ):
        passed += 1
        print("  ✅ the Poisson log-likelihood is the full -10.94470075, not the kernel +37.24")
    else:
        failed += 1
        print("  ❌ Poisson log-likelihood:", pois.log_likelihood, ll_ref)

    # ── the deviance identity, which only the FULL log-likelihood satisfies ───
    # `deviance = 2 (log_lik_saturated - log_lik)` with
    # `log_lik_saturated = sum[y log y - y - log Gamma(y+1)]`, the saturated count model
    # mu_i = y_i. The `log Gamma` terms cancel between the two sides, so this identity is a
    # statement about the `- mu` and `y log mu` parts AND about the constant being present in
    # both: with the kernel log-likelihood the same expression came out at -94.51 against a
    # deviance of 1.85.
    var ll_sat: Float64 = 0.0
    for i in range(6):
        ll_sat += yp[i] * log(yp[i]) - yp[i] - log_gamma(yp[i] + 1.0)
    # Zero counts and unit counts: `log Gamma(1) = log Gamma(2) = 0` analytically, and the
    # frozen kernel returns 1.2638690094490812e-10 and -1.1542233835371007e-10 instead. Those
    # are taken exactly, so a response of [0,1,0,1,2,4] must land on the hand-built sum to
    # 1e-13 — measured 1.8e-15 — where calling the frozen kernel on the four 0/1 entries would
    # miss it by 2.1929125182396092e-11, two hundred times the tolerance.
    var y_zo = _floats(0.0, 1.0, 0.0, 1.0, 2.0, 4.0)
    var zo = glm_poisson_fit_flat(empty, y_zo, 6, 0, 0.0, 200, 1.0e-12)
    var zo_expected = (
        8.0 * zo.intercept - 6.0 * exp(zo.intercept) - log_gamma(3.0) - log_gamma(5.0)
    )
    if (
        # 2 (ll_sat - ll) against the driver's own deviance: 1.851916822148823 vs
        # 1.8519168301160198, an 8e-9 gap that is the frozen log/log_gamma error in the
        # hand-built side, not a disagreement about the identity.
        fabs(2.0 * (ll_sat - pois.log_likelihood) - pois.deviance) <= 1.0e-7
        # The identity with the kernel log-likelihood was off by 2 * 48.18 = 96.36.
        and fabs(2.0 * (ll_sat - 37.23643587318105) - pois.deviance) > 90.0
        # ... and the deviance is NOT -2 log L for this family, which is the trap the field
        # docs now name: the saturated count model has its own log-likelihood.
        and fabs(pois.deviance + 2.0 * pois.log_likelihood) > 19.0
        and zo.status == INF_OK
        and fabs(zo.log_likelihood - zo_expected) <= 1.0e-13
        and zo.log_likelihood < 0.0
    ):
        passed += 1
        print("  ✅ deviance = 2(ll_sat - ll) holds, and the 0/1 counts contribute exactly 0")
    else:
        failed += 1
        print(
            "  ❌ Poisson deviance identity:",
            2.0 * (ll_sat - pois.log_likelihood),
            pois.deviance,
            zo.log_likelihood - zo_expected,
        )

    # ── the intercept-only Poisson model ─────────────────────────────────────
    var pois_io = glm_poisson_fit_flat(empty, yp, 6, 0, 0.0, 200, 1.0e-12)
    if (
        pois_io.status == INF_OK
        and len(pois_io.coefficients) == 0
        and fabs(pois_io.intercept - log(6.0)) <= 1.0e-9
        # se(log mean) = 1/sqrt(sum y) = 1/6
        and fabs(pois_io.std_errors[0] - 1.0 / 6.0) <= 1.0e-12
        and pois_io.n_iter <= 5
        # The full log-likelihood of the null model, sum[y log 6 - 6 - log Gamma(y+1)]:
        # -19.67779572906067 (kernel: +28.50334089220998). Measured -19.677795728422047.
        and fabs(pois_io.log_likelihood - (-19.67779572906067)) <= 1.0e-7
        and pois_io.log_likelihood < 0.0
        # Same deviance identity as the fitted model, against the SAME saturated value.
        and fabs(2.0 * (ll_sat - pois_io.log_likelihood) - pois_io.deviance) <= 1.0e-7
        # The nested-model LRT is the one quantity the constant cancels out of, so it must be
        # unchanged by this fix: 2 (ll_full - ll_null) == deviance_null - deviance_full,
        # 17.4661900 either way. Stated because it is exactly why the missing term could sit
        # here undetected — every relative comparison was already right.
        and fabs(
            (pois_io.deviance - pois.deviance)
            - 2.0 * (pois.log_likelihood - pois_io.log_likelihood)
        )
        <= 1.0e-7
    ):
        passed += 1
        print("  ✅ an intercept-only Poisson model is log(ybar) = log 6, se 1/sqrt(36)")
    else:
        failed += 1
        print("  ❌ intercept-only Poisson:", pois_io.status, pois_io.intercept, log(6.0))

    # ── Poisson refusals ─────────────────────────────────────────────────────
    var y_pneg = _floats(1.0, -1.0, 3.0, 8.0, 10.0, 12.0)
    var y_rate = _floats(1.5, 2.5, 3.5, 8.5, 10.5, 12.5)
    var pneg = glm_poisson_fit_flat(xp, y_pneg, 6, 1, 0.0, 50, 1.0e-10)
    var pcap = glm_poisson_fit_flat(xp, yp, 6, 1, 0.0, 1, 1.0e-14)
    if (
        _no_fit(pneg)
        and pneg.status == INF_ERR_RESPONSE_RANGE
        # log(0) is not an intercept: an all-zero response has no finite log mean
        and glm_poisson_fit_flat(xp, y_zeros, 6, 1, 0.0, 50, 1.0e-10).status
        == INF_ERR_RESPONSE_RANGE
        # a non-integer non-negative response IS admitted — the same estimating equations are
        # the quasi-Poisson fit for a continuous rate
        and glm_poisson_fit_flat(xp, y_rate, 6, 1, 0.0, 200, 1.0e-12).status == INF_OK
        and _no_fit(pcap)
        and pcap.status == INF_ERR_NOT_CONVERGED
        and pcap.n_iter == 1
    ):
        passed += 1
        print("  ✅ a negative count and an all-zero response are refused; a rate is admitted")
    else:
        failed += 1
        print("  ❌ a Poisson refusal leaked:", pneg.status, pcap.status)

    # ── shared shape and tuning validation ───────────────────────────────────
    var x_nan = _floats(0.0, inference_absent())
    if (
        glm_input_defect(x2, y2, 6, 1, 200, 1.0e-12) == INF_OK
        # the payload does not hold 6 x 2 cells
        and glm_input_defect(x2, y2, 6, 2, 200, 1.0e-12) == INF_ERR_SHAPE
        # len(y) must be exactly n, never the shorter of the two
        and glm_input_defect(x2, _floats(0.0, 1.0), 6, 1, 200, 1.0e-12) == INF_ERR_SHAPE
        and glm_input_defect(x2, y2, 6, 1, 0, 1.0e-12) == INF_ERR_TUNING
        and glm_input_defect(x2, y2, 6, 1, MAX_IRLS_ITER + 1, 1.0e-12) == INF_ERR_TUNING
        and glm_input_defect(x2, y2, 6, 1, 200, 0.0) == INF_ERR_TUNING
        and glm_input_defect(x2, y2, 6, 1, 200, inference_absent()) == INF_ERR_TUNING
        and glm_input_defect(x_nan, _floats(0.0, 1.0), 2, 1, 5, 1.0e-9) == INF_ERR_NON_FINITE
        and glm_input_defect(x2, y2, 0, 1, 5, 1.0e-9) != INF_OK
        and glm_logistic_fit_flat(x2, y2, 6, 1, -1.0, 200, 1.0e-12).status == INF_ERR_TUNING
        and glm_poisson_fit_flat(x2, y2, 6, 1, inference_absent(), 200, 1.0e-12).status
        == INF_ERR_TUNING
    ):
        passed += 1
        print("  ✅ one validator, shared by both families, refuses nine distinct defects")
    else:
        failed += 1
        print("  ❌ input validation:", glm_input_defect(x2, y2, 6, 2, 200, 1.0e-12))

    # ── the A-Z harness shapes, which must refuse rather than abort ──────────
    # The generated suite calls with _lf5 and 5 for every Int, so the design declares 5 x 5 = 25
    # cells backed by 5. Without the guard this indexes x[24] on a five-element list, which is
    # an uncatchable process abort.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    if (
        glm_input_defect(lf5, lf5, 5, 5, 5, 0.5) == INF_ERR_SHAPE
        and _no_fit(glm_logistic_fit_flat(lf5, lf5, 5, 5, 0.5, 5, 0.5))
        and glm_logistic_fit_flat(lf5, lf5, 5, 5, 0.5, 5, 0.5).status == INF_ERR_SHAPE
        and _no_fit(glm_poisson_fit_flat(lf5, lf5, 5, 5, 0.5, 5, 0.5))
        and glm_poisson_fit_flat(lf5, lf5, 5, 5, 0.5, 5, 0.5).status == INF_ERR_SHAPE
        and glm_input_defect(lf5, lf5, 5, 1, MAX_IRLS_ITER, 1.0e-9) == INF_OK
    ):
        passed += 1
        print("  ✅ both harness calls are refused before any index, with no coefficients")
    else:
        failed += 1
        print("  ❌ a harness call was not refused")

    # ── the work budget is a PRODUCT, not one factor ─────────────────────────
    # 100 observations and 256 parameters is inside every individual ceiling and inside the
    # payload's own shape. The COST is max_iter * n * (p+1)^2, so the same design is admitted
    # at one iteration (6.6e6 operations) and refused at a thousand (6.6e9, past MAX_IRLS_WORK
    # = 2^30). A budget that charged only n, or only p, would pass both.
    var wide_x = List[Float64](capacity=25600)
    for i in range(25600):
        wide_x.append(Float64(i % 3))
    var wide_y = List[Float64](capacity=100)
    for i in range(100):
        wide_y.append(Float64(i % 2))
    if (
        glm_input_defect(wide_x, wide_y, 100, 256, 1, 1.0e-9) == INF_OK
        and glm_input_defect(wide_x, wide_y, 100, 256, 1000, 1.0e-9)
        == INF_ERR_DIMENSION_TOO_LARGE
        # the per-dimension ceiling is separate and also enforced
        and glm_input_defect(wide_x, wide_y, 100, 257, 1, 1.0e-9)
        == INF_ERR_DIMENSION_TOO_LARGE
        # The Poisson standard errors invert the information matrix with one verified solve per
        # column, which is O(q^4) and is NOT covered by the IRLS product above. It is charged
        # separately, so a p = 256 Poisson model is refused even though its IRLS cost
        # (1 * 100 * 257^2 = 6.6e6) is tiny — while the logistic path, whose frozen standard
        # errors invert once in O(q^3), accepts the same design.
        and glm_poisson_fit_flat(wide_x, wide_y, 100, 256, 0.0, 1, 1.0e-9).status
        == INF_ERR_DIMENSION_TOO_LARGE
        and glm_input_defect(wide_x, wide_y, 100, 256, 1, 1.0e-9) == INF_OK
    ):
        passed += 1
        print("  ✅ max_iter * n * (p+1)^2 is charged as a product, and q^4 separately")
    else:
        failed += 1
        print("  ❌ work budget:", glm_input_defect(wide_x, wide_y, 100, 256, 1000, 1.0e-9))

    print("  [inference.glm] Passed:", passed, "Failed:", failed)
