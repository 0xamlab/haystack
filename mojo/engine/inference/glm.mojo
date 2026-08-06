"""
inference.glm — logistic and Poisson regression by IRLS, honestly. Zero Python imports.

Why this module exists
----------------------
`linear_models.logistic_fit` is a correct damped-Newton IRLS and it is frozen and reused
here unchanged. What it cannot do is refuse. It returns its last iterate with
`converged = False`, so the three outcomes a caller has to distinguish — a fit, a fit that
ran out of iterations, and a model whose maximum-likelihood estimate does not exist — arrive
as the same shape of answer with one boolean between them. Measured on this toolchain:

    logistic_fit(X=[-2,-1,1,2], y=[0,0,1,1], l2=0, max_iter=200, tol=1e-12)
        -> weights [26.61180993388579], bias -3.9e-07, converged False, n_iter 200
       logistic_std_errors(...) -> [424777.880690872, 424777.88069175486]

Those data are perfectly separable, so the MLE is at infinity: there is no finite
coefficient vector to report, and 26.6 is simply where 200 iterations happened to stop. A
caller who reads `weights` gets a number, an odds ratio of 3.6e11, and a standard error that
says nothing. The fit "succeeds" numerically while meaning nothing, which is the exact shape
rule 4 exists to prevent.

There is no Poisson regression in the tree at all — no log-link IRLS, no count-family
deviance — so `glm_poisson_fit_flat` is a new driver rather than a wrapper.

What is reused rather than rebuilt
----------------------------------
* `linear_models.logistic_fit` — the entire logistic IRLS: damped Newton, backtracking line
  search on the penalized log-likelihood, warm-started intercept. Not one line of it is
  reimplemented here. This module validates before it, diagnoses after it, and refuses.
* `linear_models.logistic_std_errors` — the standard errors from the inverse observed
  information, called unchanged.
* `inference.core.wls_solve_flat` — the Poisson IRLS step, which is in turn the frozen
  `linear_models._solve_linear_system` behind the frozen
  `linalg_ext.mat_is_positive_definite` rank test and a per-row residual verification.
* `math_ext.norm_cdf` through `inference.core.inference_norm_sf_two_sided` — the Wald
  p-values.
* `inference.core.inference_t_quantile` is deliberately NOT used for the intervals: a GLM
  Wald interval is a normal-approximation interval, and `math_ext.norm_ppf` is the frozen
  quantile for it.
* `sparse_numerics.csr.dims_fit` through `inference.core.inference_dims_fit` — the design
  matrix shape, checked by division because `n * p == len(x)` is a wrapping multiply.
* `special_functions.log_gamma` — the Poisson log-likelihood's `- sum log Gamma(y + 1)`
  normalizing term, called unchanged. No factorial is implemented here: `log Gamma(y+1)` is
  `log(y!)` at every integer count and it is also the continuation the admitted non-integer
  (quasi-Poisson) response needs, so one frozen call covers both.

The separation certificate, and exactly what it claims (rule 4d)
----------------------------------------------------------------
`separation_witnessed` is True when the fitted linear predictor `z_i = x_i . beta + bias`
SEPARATES the two classes with a strictly positive margin:

    max { z_i : y_i = 0 }  <  min { z_i : y_i = 1 }        (or the same with the labels
                                                            swapped, for a negative slope)

When that holds, `beta` itself is a witness that a separating hyperplane exists, so the
likelihood can be increased without bound by scaling it up and the MLE does not exist. The
claim is therefore EXACT in the direction it is made, and the witness is reported
(`separation_margin`) so a caller can check it independently.

What it does NOT claim, stated because rule 4d's cautionary case was a certificate that
omitted a condition it needed: a False `separation_witnessed` does not prove the data are
NOT separable. The fit's own hyperplane failing to separate is not a proof that no hyperplane
separates; deciding that exactly is a linear-programming feasibility question. This costs a
caller nothing, because separable data cannot reach a success status by the other route
either: with the MLE at infinity the iterate keeps growing and the run ends at the iteration
cap, which is `INF_ERR_NOT_CONVERGED`. Both branches refuse; the witness only makes the
diagnosis specific. The suite asserts BOTH branches on separable data — with a generous
iteration budget it is refused as separable, with a tiny one as unconverged, and never with
coefficients.

Rule 4 in this module
---------------------
* An IRLS fit that did not converge has no coefficients. `INF_ERR_NOT_CONVERGED` carries
  `n_iter` and `max_iter` and an EMPTY coefficient list. Returning the last iterate is what
  the frozen kernel does and what a caller then reports as an odds ratio.
* A separable logistic model has no coefficients: `INF_ERR_SEPARABLE`, with the margin.
* A response outside the family's support is not a response: `INF_ERR_RESPONSE_RANGE` for a
  logistic `y` that is not exactly 0.0 or 1.0 (a 0.5 is not "closer to 1"), and for a
  negative or non-finite Poisson `y`.
* A singular information matrix has no standard errors: `INF_ERR_RANK_DEFICIENT`, rather
  than the zeros `linalg.mat_solve` returns for a singular system or the skipped pivot
  `linear_models._solve_linear_system` leaves at 0.0.
* An iterate that leaves the representable range is `INF_ERR_DIVERGED`. A Poisson log link
  exponentiates, so `eta = 1000` is `inf` and every subsequent quantity is NaN; the check is
  on `eta` BEFORE the exponential, because after it the tolerance comparisons are all NaN
  and every one of them is False (rule 4d's nan trap).

Closed forms this module is pinned against
------------------------------------------
Both families are SATURATED by a single binary covariate, so the MLE has a closed form and
the suite uses it rather than a plausible-looking number:

* logistic, three observations at `x = 0` with one success and three at `x = 1` with two:
  `bias = log(1/2)`, `slope = log(4)`, `se = [sqrt(3), sqrt(1.5)]` (the 2x2-table forms
  `sqrt(1/a + 1/b + 1/c + 1/d)` and `sqrt(1/a + 1/b)`). Verified against the frozen kernel:
  `-0.6931471805596628`, `1.386294361119326`, `1.7320508075688772`, `1.224744871391589`.
* logistic with NO covariates (`p = 0`, an intercept-only model): `bias = logit(mean(y))`
  and `se = 1 / sqrt(n p (1-p))`. For `y = [1,1,1,0]`: `log 3 = 1.0986122886681098` and
  `1/sqrt(0.75) = 1.1547005383792515`.
* Poisson, three observations at `x = 0` summing to 6 and three at `x = 1` summing to 30:
  `intercept = log 2`, `slope = log 5`, `se = [sqrt(1/6), sqrt(1/6 + 1/30)]`.

Status codes 320-339 belong to the `inference` package; this module allocates none of its
own (rule 4e).

Bounds, per rule 1c and "bounding memory is not bounding work"
-------------------------------------------------------------
`n <= MAX_INFERENCE_OBS`, `p <= MAX_INFERENCE_PARAMS`, `n * p == len(x)` by division, and
`len(y) == n` exactly. None of that bounds the COST, which is
`max_iter * n * (p+1)^2` for the normal-equations accumulation plus `max_iter * (p+1)^3` for
the solves, so `MAX_IRLS_WORK` is charged against the product with
`inference_product3_fits` — a budget that counts one factor of a product is not a budget.
`max_iter` is separately capped at `MAX_IRLS_ITER`.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_glm.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, exp, log, sqrt

from inference.core import (
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_DIVERGED,
    INF_ERR_EMPTY,
    INF_ERR_NON_FINITE,
    INF_ERR_NOT_CONVERGED,
    INF_ERR_RANK_DEFICIENT,
    INF_ERR_RESPONSE_RANGE,
    INF_ERR_SEPARABLE,
    INF_ERR_SHAPE,
    INF_ERR_TUNING,
    INF_OK,
    MAX_INFERENCE_OBS,
    MAX_INFERENCE_PARAMS,
    MAX_IRLS_ITER,
    MAX_IRLS_WORK,
    inference_dims_fit,
    inference_finite,
    inference_norm_sf_two_sided,
    inference_product3_fits,
    inference_scaled_tol,
    wls_solve_flat,
)
from linear_models import logistic_fit, logistic_std_errors
from special_functions import log_gamma

# A Poisson log link exponentiates its linear predictor. exp(709.78) is the largest finite
# double, so an eta past this is a diverged iterate and is caught BEFORE the exponential —
# after it every downstream tolerance comparison is NaN and therefore False, which is the
# trap rule 4d names.
comptime GLM_MAX_ETA: Float64 = 700.0

# A margin is a distance, so a negative value cannot be one: -1.0 says the separation
# witness was never computed. Same convention as `optimization.assignment`'s absent defect.
comptime GLM_MARGIN_ABSENT: Float64 = -1.0

comptime FAMILY_BINOMIAL_LOGIT: String = "binomial_logit"
comptime FAMILY_POISSON_LOG: String = "poisson_log"


@fieldwise_init
struct GlmFit(Copyable, Movable):
    """A fitted generalized linear model, or a refusal that says which one it is.

    `coefficients` and `std_errors` are EMPTY unless `status == INF_OK`. There is no
    "partial" fit: an unconverged, separable, rank-deficient or diverged run carries no
    numbers, because the alternative is a caller reporting an odds ratio of 3.6e11.

    `coefficients` holds the `p` covariate coefficients; `intercept` is separate because the
    frozen `logistic_fit` adds the intercept internally and this driver keeps that contract —
    X must NOT contain a column of ones. `std_errors` has `p + 1` entries ordered
    `[coef_0 .. coef_{p-1}, intercept]`, matching `logistic_std_errors`.

    `wald_z` and `wald_p` are the same length and order as `std_errors`. A zero standard
    error yields an absent (NaN) z rather than an infinite one, and `inference_finite` is the
    test for it.

    `separation_witnessed` / `separation_margin`: see the module docstring for exactly what
    the witness claims and what it does not.

    `n_iter` and `max_iter` are reported on success as well as on refusal, because "converged
    on the last permitted iteration" is worth seeing.

    `log_likelihood` IS THE FULL LOG-LIKELIHOOD OF THE FITTED MODEL, normalizing constant
    included, for BOTH families — the number another library reports, directly comparable to
    it, and directly usable as `AIC = -2 log_likelihood + 2 k`:

        binomial, individual 0/1 responses:  sum[ y log mu + (1-y) log(1-mu) ]
        Poisson, log link:                   sum[ y log mu - mu - log Gamma(y + 1) ]

    The `- log Gamma(y+1)` term is the one a "log-likelihood" is most often quietly missing,
    because it cancels in every likelihood-ratio test and every AIC difference computed on
    the SAME response vector. It does not cancel against another library, against a different
    response vector, or in an absolute figure, so it is included rather than documented away.
    On the suite's saturated Poisson design the two differ by 48.18 and by SIGN.

    `deviance` is the RESIDUAL deviance, `2 * (log_likelihood_saturated - log_likelihood)`,
    for both families. For individual 0/1 binomial responses the saturated log-likelihood is
    exactly 0, so there `deviance == -2 * log_likelihood`; for the Poisson family it is NOT,
    because a count model's saturated fit `mu_i = y_i` has its own nonzero log-likelihood.
    Reading `-2 * log_likelihood` as a Poisson deviance is therefore wrong by
    `2 * log_likelihood_saturated`, and the suite asserts the identity in the form above.
    """

    var status: Int
    var family: String
    var n_obs: Int
    var n_params: Int
    var converged: Bool
    var n_iter: Int
    var max_iter: Int
    var intercept: Float64
    var coefficients: List[Float64]
    var std_errors: List[Float64]
    var wald_z: List[Float64]
    var wald_p: List[Float64]
    var log_likelihood: Float64
    var deviance: Float64
    var separation_witnessed: Bool
    var separation_margin: Float64


def _glm_failure(
    code: Int, family: String, n: Int, p: Int, iters: Int, max_iter: Int,
    witnessed: Bool, margin: Float64,
) -> GlmFit:
    return GlmFit(
        code, family, n, p, False, iters, max_iter, 0.0,
        List[Float64](), List[Float64](), List[Float64](), List[Float64](),
        0.0, 0.0, witnessed, margin,
    )


def glm_input_defect(
    x: List[Float64], y: List[Float64], n: Int, p: Int,
    max_iter: Int, tol: Float64,
) -> Int:
    """`INF_OK`, or the one status describing what is wrong with this design and response.

    PUBLIC and the SINGLE shape/bound validator for both families in this module, so the two
    cannot disagree about what a valid model is — rule 3's "one declared input invariant
    enforced at three different strengths" is the defect this shape avoids. Family-specific
    response checks (0/1 for the logit link, non-negative for the log link) stay with their
    own driver, because they are not the same condition.

    `p == 0` is admitted: an intercept-only model is a real model whose answer is
    `logit(mean(y))` or `log(mean(y))`, and both frozen and new code handle it.

    @capability glm_input_defect
    complexity: O(n * p)
    counts:
    - n * p == len(x) [kernel_validated]
    - n == len(y) [kernel_validated]
    @endcapability
    """
    if n <= 0:
        return INF_ERR_EMPTY
    if n > MAX_INFERENCE_OBS or p > MAX_INFERENCE_PARAMS or p < 0:
        return INF_ERR_DIMENSION_TOO_LARGE
    if not inference_dims_fit(n, p, len(x)):
        return INF_ERR_SHAPE
    if len(y) != n:
        return INF_ERR_SHAPE
    if max_iter < 1 or max_iter > MAX_IRLS_ITER:
        return INF_ERR_TUNING
    if not inference_finite(tol) or tol <= 0.0:
        return INF_ERR_TUNING
    # Cost is max_iter * n * (p+1)^2 for the accumulation. Charged as a product so no
    # single factor can pay for another's size; see the module docstring.
    if not inference_product3_fits(max_iter, n, (p + 1) * (p + 1), MAX_IRLS_WORK):
        return INF_ERR_DIMENSION_TOO_LARGE
    for i in range(len(x)):
        if not inference_finite(x[i]):
            return INF_ERR_NON_FINITE
    for i in range(n):
        if not inference_finite(y[i]):
            return INF_ERR_NON_FINITE
    return INF_OK


def _linear_predictors(
    x: List[Float64], beta: List[Float64], intercept: Float64, n: Int, p: Int
) -> List[Float64]:
    """`eta_i = x_i . beta + intercept` for the flat row-major design matrix.

    Callers have already validated `n * p == len(x)` and `len(beta) == p`, so every read is
    in range; that validation is not repeated here because this is private and a second
    check at a different strength is the defect rule 3 names.
    """
    var eta = List[Float64](capacity=n)
    for i in range(n):
        var z = intercept
        for j in range(p):
            z += x[i * p + j] * beta[j]
        eta.append(z)
    return eta^


def _separation_margin(eta: List[Float64], y: List[Float64], n: Int) -> Float64:
    """The separating margin of `eta` between the two label classes, or `GLM_MARGIN_ABSENT`.

    Returns `min{eta_i : y_i = 1} - max{eta_i : y_i = 0}` when that is strictly positive, and
    otherwise the mirror quantity for a negative-slope separation. A positive return value is
    a WITNESS: `beta` separates the classes, so scaling it up increases the likelihood
    without bound and the MLE does not exist.

    `GLM_MARGIN_ABSENT` (-1.0) means no separation was witnessed, and is outside the range of
    a margin so it cannot be read as "separated by zero". A class with no members at all
    returns absent too: one label class cannot be separated from an empty one, and the
    intercept-only model that produces it is refused earlier as a degenerate response.
    """
    var have0 = False
    var have1 = False
    var max0: Float64 = 0.0
    var min0: Float64 = 0.0
    var max1: Float64 = 0.0
    var min1: Float64 = 0.0
    for i in range(n):
        if y[i] == 0.0:
            if not have0 or eta[i] > max0:
                max0 = eta[i]
            if not have0 or eta[i] < min0:
                min0 = eta[i]
            have0 = True
        else:
            if not have1 or eta[i] > max1:
                max1 = eta[i]
            if not have1 or eta[i] < min1:
                min1 = eta[i]
            have1 = True
    if not have0 or not have1:
        return GLM_MARGIN_ABSENT
    var up = min1 - max0
    var down = min0 - max1
    var best = up if up > down else down
    if best > 0.0:
        return best
    return GLM_MARGIN_ABSENT


def _wald(std_errors: List[Float64], coefficients: List[Float64], intercept: Float64) -> List[Float64]:
    """Wald z statistics in `std_errors` order: `[coef_0 .. coef_{p-1}, intercept]`.

    A zero or non-finite standard error yields an absent z (NaN) rather than an infinity: an
    estimate with no measurable uncertainty has no z statistic, and reporting `inf` would
    make the p-value 0.0 — a certainty manufactured out of a singular information matrix.
    """
    var out = List[Float64]()
    var p = len(coefficients)
    for j in range(p + 1):
        var estimate = coefficients[j] if j < p else intercept
        var se = std_errors[j]
        if not inference_finite(se) or se <= 0.0:
            var zero: Float64 = 0.0
            out.append(zero / zero)
        else:
            out.append(estimate / se)
    return out^


def glm_logistic_fit_flat(
    x: List[Float64], y: List[Float64], n: Int, p: Int,
    l2: Float64, max_iter: Int, tol: Float64,
) -> GlmFit:
    """Logistic regression by IRLS, refusing every outcome that has no coefficients.

    The fit itself is the frozen `linear_models.logistic_fit` — damped Newton with a
    backtracking line search on the penalized log-likelihood — called once, unchanged. `X` is
    flat row-major `n x p` and must NOT contain a column of ones; the intercept is added
    internally by the frozen kernel and returned separately.

    `y` must be exactly 0.0 or 1.0 per observation. The frozen kernel accepts any `Int` and
    treats every nonzero as 1, so `y = 0.5` there is a success and `y = -3` is a success;
    here both are `INF_ERR_RESPONSE_RANGE`, because a response outside the family's support
    is not a response.

    The diagnosis order is deliberate and each step is the more specific explanation of the
    step after it: separation (the MLE does not exist) before non-convergence (we did not
    find it), and non-convergence before rank deficiency (we cannot price it). All three
    return no coefficients.

    `deviance` is `-2 * log_likelihood` for the binomial family with individual 0/1
    responses, where the saturated log-likelihood is exactly 0. That coincidence is
    family-specific and does NOT hold for the Poisson driver below, whose saturated model has
    its own nonzero log-likelihood; see the `GlmFit` docstring for the general form.

    @capability glm_logistic_fit_flat
    complexity: O(max_iter * n * (p+1)^2)
    counts:
    - n * p == len(x) [kernel_validated]
    - n == len(y) [kernel_validated]
    @endcapability
    """
    var defect = glm_input_defect(x, y, n, p, max_iter, tol)
    if defect != INF_OK:
        return _glm_failure(
            defect, FAMILY_BINOMIAL_LOGIT, n, p, 0, max_iter, False, GLM_MARGIN_ABSENT
        )
    if not inference_finite(l2) or l2 < 0.0:
        return _glm_failure(
            INF_ERR_TUNING, FAMILY_BINOMIAL_LOGIT, n, p, 0, max_iter, False,
            GLM_MARGIN_ABSENT,
        )

    var labels = List[Int](capacity=n)
    var n_positive = 0
    for i in range(n):
        if y[i] != 0.0 and y[i] != 1.0:
            return _glm_failure(
                INF_ERR_RESPONSE_RANGE, FAMILY_BINOMIAL_LOGIT, n, p, 0, max_iter,
                False, GLM_MARGIN_ABSENT,
            )
        if y[i] == 1.0:
            n_positive += 1
            labels.append(1)
        else:
            labels.append(0)
    # One class is not two. A response that never varies has no log-odds: every fitted
    # probability is 0 or 1, the intercept diverges, and the frozen kernel's clamped
    # warm start (ybar pinned into [1e-3, 1-1e-3]) hides that behind a finite answer.
    if n_positive == 0 or n_positive == n:
        return _glm_failure(
            INF_ERR_RESPONSE_RANGE, FAMILY_BINOMIAL_LOGIT, n, p, 0, max_iter,
            False, GLM_MARGIN_ABSENT,
        )

    var fit = logistic_fit(x, labels, l2, max_iter, tol)
    if len(fit.weights) != p:
        return _glm_failure(
            INF_ERR_SHAPE, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter, max_iter,
            False, GLM_MARGIN_ABSENT,
        )
    for j in range(p):
        if not inference_finite(fit.weights[j]):
            return _glm_failure(
                INF_ERR_DIVERGED, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter, max_iter,
                False, GLM_MARGIN_ABSENT,
            )
    if not inference_finite(fit.bias):
        return _glm_failure(
            INF_ERR_DIVERGED, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter, max_iter,
            False, GLM_MARGIN_ABSENT,
        )

    var eta = _linear_predictors(x, fit.weights, fit.bias, n, p)
    var margin = _separation_margin(eta, y, n)
    var witnessed = margin > 0.0
    # An L2 penalty makes the penalized optimum finite even on separable data, so the
    # separation refusal applies to the UNPENALIZED fit only. With a penalty the estimate
    # exists; the witness is still reported so a caller knows why it is shrunk.
    if witnessed and l2 == 0.0:
        return _glm_failure(
            INF_ERR_SEPARABLE, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter, max_iter,
            True, margin,
        )
    if not fit.converged:
        return _glm_failure(
            INF_ERR_NOT_CONVERGED, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter, max_iter,
            witnessed, margin,
        )

    var se = logistic_std_errors(x, labels, fit.weights, fit.bias, l2)
    if len(se) != p + 1:
        return _glm_failure(
            INF_ERR_RANK_DEFICIENT, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter, max_iter,
            witnessed, margin,
        )
    for j in range(p + 1):
        if not inference_finite(se[j]) or se[j] <= 0.0:
            return _glm_failure(
                INF_ERR_RANK_DEFICIENT, FAMILY_BINOMIAL_LOGIT, n, p, fit.n_iter,
                max_iter, witnessed, margin,
            )

    var z = _wald(se, fit.weights, fit.bias)
    var pvals = List[Float64](capacity=p + 1)
    for j in range(p + 1):
        pvals.append(inference_norm_sf_two_sided(z[j]))
    return GlmFit(
        INF_OK, FAMILY_BINOMIAL_LOGIT, n, p, True, fit.n_iter, max_iter, fit.bias,
        fit.weights.copy(), se^, z^, pvals^,
        fit.log_likelihood, -2.0 * fit.log_likelihood, witnessed, margin,
    )


def glm_poisson_fit_flat(
    x: List[Float64], y: List[Float64], n: Int, p: Int,
    l2: Float64, max_iter: Int, tol: Float64,
) -> GlmFit:
    """Poisson regression with a log link by IRLS. Genuinely new: the tree has no count GLM.

    `beta = [coef_0 .. coef_{p-1}, intercept]` internally, so the intercept is always fitted
    and X must NOT contain a column of ones — the same contract as the logistic driver, whose
    frozen kernel imposes it.

    Each step is the standard log-link IRLS: `mu = exp(eta)`, working weights `w = mu`,
    working response `z = eta + (y - mu)/mu`, and the normal equations
    `(X'WX + l2 I) beta = X'Wz` solved by `inference.core.wls_solve_flat`, which refuses a
    rank-deficient system instead of returning zeros for it. The intercept is never
    penalized, matching the frozen logistic kernel.

    Convergence is decided PER COEFFICIENT against that coefficient's own magnitude:
    `|delta_j| <= inference_scaled_tol(|beta_j|, tol)`, i.e. the caller's absolute tolerance
    plus DBL_EPSILON times the size of the thing being judged (rule 4b). It is not a norm
    over the whole vector, which would let a large coefficient's units pay for a small
    coefficient's movement, and there is no `1 + |x|` floor to make a "relative" test
    secretly absolute.

    `y` must be finite and non-negative. Non-integer values are ADMITTED on purpose — the
    same estimating equations are the quasi-Poisson fit for a non-negative continuous rate,
    which is a real use — but a negative response is outside the family's support and is
    `INF_ERR_RESPONSE_RANGE`.

    `deviance` is `2 * sum[ y log(y/mu) - (y - mu) ]` with the `y log y` term taken as 0 at
    `y = 0`, which is its limit.

    `log_likelihood` is the FULL Poisson log-likelihood,
    `sum[ y log mu - mu - log Gamma(y + 1) ]`, so it is the same quantity another library
    reports for the same data and `AIC = -2 log_likelihood + 2 (p + 1)` needs no correction
    term. `log Gamma(y+1)` is `log(y!)` at integer counts and is the right continuation for
    the non-integer responses this driver admits. Note that `deviance != -2 * log_likelihood`
    for this family — the saturated count model has its own nonzero log-likelihood, and the
    two are related by `deviance = 2 (log_lik_saturated - log_lik)`, with
    `log_lik_saturated = sum[ y log y - y - log Gamma(y + 1) ]`. That identity is asserted in
    the suite, which is also how a caller can check this number independently.

    A `log Gamma(y + 1)` that overflows makes the log-likelihood non-finite even when every
    `mu` is representable; that is `INF_ERR_DIVERGED` with no numbers, never a NaN in a field.

    ACCURACY OF THE NORMALIZING TERM, stated because it is the frozen kernel's and not this
    driver's: `special_functions.log_gamma` carries about 1e-10 to 2e-9 of absolute error per
    call on this toolchain (measured: `log_gamma(4.0)` is 1.7917594702642976 against a true
    1.791759469228055, `log_gamma(13.0)` is 19.987214493640607 against 19.987214495661885), so
    a log-likelihood over `n` observations inherits roughly `n * 1e-9`. The `y = 0` and `y = 1`
    observations contribute exactly 0 rather than the kernel's 1.3e-10, which is where that
    error would otherwise concentrate in count data.

    @capability glm_poisson_fit_flat
    complexity: O(max_iter * n * (p+1)^2)
    counts:
    - n * p == len(x) [kernel_validated]
    - n == len(y) [kernel_validated]
    @endcapability
    """
    var defect = glm_input_defect(x, y, n, p, max_iter, tol)
    if defect != INF_OK:
        return _glm_failure(
            defect, FAMILY_POISSON_LOG, n, p, 0, max_iter, False, GLM_MARGIN_ABSENT
        )
    if not inference_finite(l2) or l2 < 0.0:
        return _glm_failure(
            INF_ERR_TUNING, FAMILY_POISSON_LOG, n, p, 0, max_iter, False,
            GLM_MARGIN_ABSENT,
        )
    var total: Float64 = 0.0
    for i in range(n):
        if y[i] < 0.0:
            return _glm_failure(
                INF_ERR_RESPONSE_RANGE, FAMILY_POISSON_LOG, n, p, 0, max_iter,
                False, GLM_MARGIN_ABSENT,
            )
        total += y[i]
    # log(0) is not an intercept. An all-zero response gives mu = 0 everywhere, so the log
    # mean is -inf and no finite coefficient vector exists.
    if total <= 0.0:
        return _glm_failure(
            INF_ERR_RESPONSE_RANGE, FAMILY_POISSON_LOG, n, p, 0, max_iter,
            False, GLM_MARGIN_ABSENT,
        )

    var q = p + 1
    # The standard errors invert the information matrix by running one VERIFIED solve per
    # column (`_inverse_diagonal_se`), which is O(q^4) overall. `glm_input_defect` charges
    # `max_iter * n * q^2` — the IRLS loop — and that product does not cover this one, so it is
    # charged separately here: a budget that counts one factor of a product is not a budget,
    # and this path is reachable with a converging model whose IRLS cost is small. q^4 inside
    # MAX_IRLS_WORK (2^30) means q <= 181, so a Poisson model may declare at most 180
    # covariates; the logistic path is unaffected because the frozen
    # `logistic_std_errors` inverts once in O(q^3).
    if not inference_product3_fits(q, q * q, q, MAX_IRLS_WORK):
        return _glm_failure(
            INF_ERR_DIMENSION_TOO_LARGE, FAMILY_POISSON_LOG, n, p, 0, max_iter,
            False, GLM_MARGIN_ABSENT,
        )
    var beta = List[Float64](capacity=q)
    for _ in range(q):
        beta.append(0.0)
    # Warm start: the intercept at the log of the response mean, which is the exact MLE of
    # an intercept-only model, so `p == 0` converges on the first step.
    beta[p] = log(total / Float64(n))

    var converged = False
    var iters = 0
    for _ in range(max_iter):
        iters += 1
        var a = List[Float64](capacity=q * q)
        for _ in range(q * q):
            a.append(0.0)
        var rhs = List[Float64](capacity=q)
        for _ in range(q):
            rhs.append(0.0)

        for i in range(n):
            var eta = beta[p]
            for j in range(p):
                eta += x[i * p + j] * beta[j]
            # Checked BEFORE the exponential: past this point mu is inf and every
            # tolerance comparison downstream would be NaN and therefore False.
            if not inference_finite(eta) or eta > GLM_MAX_ETA or eta < -GLM_MAX_ETA:
                return _glm_failure(
                    INF_ERR_DIVERGED, FAMILY_POISSON_LOG, n, p, iters, max_iter,
                    False, GLM_MARGIN_ABSENT,
                )
            var mu = exp(eta)
            if not inference_finite(mu) or mu <= 0.0:
                return _glm_failure(
                    INF_ERR_DIVERGED, FAMILY_POISSON_LOG, n, p, iters, max_iter,
                    False, GLM_MARGIN_ABSENT,
                )
            var w = mu
            var z = eta + (y[i] - mu) / mu
            for r in range(q):
                var xr = x[i * p + r] if r < p else 1.0
                rhs[r] += w * xr * z
                for c in range(q):
                    var xc = x[i * p + c] if c < p else 1.0
                    a[r * q + c] += w * xr * xc
        # Ridge on the covariates only; the intercept is never penalized. Also the only
        # thing that can make a collinear design solvable, which is why l2 > 0 is a
        # supported request rather than a refusal.
        for j in range(p):
            a[j * q + j] += l2

        var step = wls_solve_flat(a, rhs, q)
        if step.status != INF_OK:
            return _glm_failure(
                step.status, FAMILY_POISSON_LOG, n, p, iters, max_iter,
                False, GLM_MARGIN_ABSENT,
            )
        var all_small = True
        for j in range(q):
            if not inference_finite(step.beta[j]):
                return _glm_failure(
                    INF_ERR_DIVERGED, FAMILY_POISSON_LOG, n, p, iters, max_iter,
                    False, GLM_MARGIN_ABSENT,
                )
            var delta = step.beta[j] - beta[j]
            # Judged quantity: this coefficient's movement. Scale: this coefficient's own
            # magnitude, plus the caller's absolute tolerance. Never a vector norm.
            if fabs(delta) > inference_scaled_tol(step.beta[j], tol):
                all_small = False
            beta[j] = step.beta[j]
        if all_small:
            converged = True
            break

    if not converged:
        return _glm_failure(
            INF_ERR_NOT_CONVERGED, FAMILY_POISSON_LOG, n, p, iters, max_iter,
            False, GLM_MARGIN_ABSENT,
        )

    # Observed information at the optimum, which for the canonical log link is X'WX with
    # W = diag(mu). Built EXACTLY symmetric (upper triangle mirrored) so the symmetry test
    # in `wls_solve_flat` is testing the solve's input and not this loop's rounding.
    var info = List[Float64](capacity=q * q)
    for _ in range(q * q):
        info.append(0.0)
    var log_lik: Float64 = 0.0
    var deviance: Float64 = 0.0
    for i in range(n):
        var eta = beta[p]
        for j in range(p):
            eta += x[i * p + j] * beta[j]
        var mu = exp(eta)
        if not inference_finite(mu) or mu <= 0.0:
            return _glm_failure(
                INF_ERR_DIVERGED, FAMILY_POISSON_LOG, n, p, iters, max_iter,
                False, GLM_MARGIN_ABSENT,
            )
        # THE FULL Poisson log-likelihood, normalizing constant included:
        # `sum[ y eta - mu - log Gamma(y + 1) ]`. The `- log Gamma(y+1)` term is what makes
        # this number the same quantity every other library calls a Poisson
        # log-likelihood. Dropping it (the kernel `sum[y eta - mu]`) leaves a value that is
        # correct for every LIKELIHOOD-RATIO or AIC comparison on the SAME response vector,
        # because the constant cancels — and silently wrong as an absolute figure, wrong
        # against another library, and wrong across two different response vectors. It also
        # broke the deviance identity: `deviance = 2 (log_lik_saturated - log_lik)` holds for
        # the full form and not for the kernel. Measured on the suite's saturated design
        # (y = [1,2,3,8,10,12], mu = [2,2,2,10,10,10]): full -10.944700748089598, kernel
        # 37.23643587318105 — a gap of 48.18 and the wrong SIGN, so the kernel does not even
        # look like a log-likelihood.
        #
        # `log Gamma(y+1)` rather than a factorial loop: it is `log(y!)` at every integer and
        # it is the continuation this driver needs anyway, since a non-integer `y` is admitted
        # on purpose (the quasi-Poisson rate fit).
        #
        # `y == 0` and `y == 1` are taken as exactly 0.0 instead of calling it, because
        # `log Gamma(1) = log Gamma(2) = 0` analytically and the frozen kernel does not return
        # 0 there: MEASURED on this toolchain, `log_gamma(1.0)` is 1.2638690094490812e-10 and
        # `log_gamma(2.0)` is -1.1542233835371007e-10. Those two values are the most common
        # entries in count data, so the error accumulates with `n` — 1.2e-4 of pure noise at
        # `n = 1e6`, all of it from a term that is analytically zero. This is NOT a clamp of
        # small `log_gamma` results: at `y = 0.5`, an admitted quasi-Poisson rate,
        # `log Gamma(1.5) = -0.1208` is a real contribution and is used.
        var log_y_factorial: Float64 = 0.0
        if y[i] != 0.0 and y[i] != 1.0:
            log_y_factorial = log_gamma(y[i] + 1.0)
        log_lik += y[i] * eta - mu - log_y_factorial
        if y[i] > 0.0:
            deviance += 2.0 * (y[i] * log(y[i] / mu) - (y[i] - mu))
        else:
            deviance += 2.0 * mu
        for r in range(q):
            var xr = x[i * p + r] if r < p else 1.0
            for c in range(r, q):
                var xc = x[i * p + c] if c < p else 1.0
                info[r * q + c] += mu * xr * xc
    for j in range(p):
        info[j * q + j] += l2
    for r in range(q):
        for c in range(r + 1, q):
            info[c * q + r] = info[r * q + c]

    # Rule 4: a non-finite may not travel in a result struct under a success status. Both
    # sums are now capable of it independently of the iterate — `log Gamma(y + 1)` overflows
    # for an astronomically large response even when every `mu` is finite — and a NaN
    # `log_likelihood` would make every downstream comparison against it False, which is the
    # trap where an audit passes having counted zero violations.
    if not inference_finite(log_lik) or not inference_finite(deviance):
        return _glm_failure(
            INF_ERR_DIVERGED, FAMILY_POISSON_LOG, n, p, iters, max_iter,
            False, GLM_MARGIN_ABSENT,
        )

    var se = _inverse_diagonal_se(info, q)
    if len(se) != q:
        return _glm_failure(
            INF_ERR_RANK_DEFICIENT, FAMILY_POISSON_LOG, n, p, iters, max_iter,
            False, GLM_MARGIN_ABSENT,
        )
    var coefficients = List[Float64](capacity=p)
    for j in range(p):
        coefficients.append(beta[j])
    var z = _wald(se, coefficients, beta[p])
    var pvals = List[Float64](capacity=q)
    for j in range(q):
        pvals.append(inference_norm_sf_two_sided(z[j]))
    return GlmFit(
        INF_OK, FAMILY_POISSON_LOG, n, p, True, iters, max_iter, beta[p],
        coefficients^, se^, z^, pvals^,
        log_lik, deviance, False, GLM_MARGIN_ABSENT,
    )


def _inverse_diagonal_se(info: List[Float64], q: Int) -> List[Float64]:
    """Standard errors `sqrt(diag(info^-1))`, or an EMPTY list if `info` is not invertible.

    One `wls_solve_flat` per unit basis vector, so the rank test, the symmetry test and the
    per-row residual verification apply to every column of the inverse rather than to a
    single solve. An empty return is the refusal — `linear_models._invert_matrix` returns an
    empty list for a singular matrix and this keeps that convention, but unlike a Gauss-Jordan
    inverse it cannot leave a near-singular column silently wrong, because each solve is
    verified.

    A negative diagonal entry cannot be a variance, so it is refused rather than clamped to
    zero, which is what `logistic_std_errors` does (`if v < 0.0: v = 0.0`).
    """
    var out = List[Float64](capacity=q)
    for j in range(q):
        var unit = List[Float64](capacity=q)
        for k in range(q):
            unit.append(1.0 if k == j else 0.0)
        var col = wls_solve_flat(info, unit, q)
        if col.status != INF_OK:
            return List[Float64]()
        var v = col.beta[j]
        if not inference_finite(v) or v < 0.0:
            return List[Float64]()
        out.append(sqrt(v))
    return out^
