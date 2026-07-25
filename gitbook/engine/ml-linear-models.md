---
icon: chart-line
description: Trainable logistic regression and elastic-net linear models with exact coordinate-descent math.
---

# Trainable linear models

`linear_models` replaces `sklearn.linear_model` (`LogisticRegression`,
`ElasticNet`, `Lasso`) and statsmodels `Logit` with pure Mojo, zero Python
imports. It complements the closed-form OLS/ridge kernel (`regression.mojo`)
with iterative fits: L2-regularized logistic regression via damped Newton
(IRLS) with backtracking line search, and elastic-net linear regression via
cyclic coordinate descent with exact soft-thresholding. Fully deterministic
— there is no RNG anywhere in the kernel.

## Functions

| Function | What it does |
|---|---|
| `logistic_fit(X, y, l2, max_iter, tol)` | L2-regularized logistic regression on flat row-major X (bias never penalized). Each Newton step solves `(X'WX + l2 I) d = grad` and halves the step if the penalized log-likelihood would decrease. Returns weights, bias, `converged`, `n_iter`, and the unpenalized log-likelihood. |
| `logistic_predict_proba(X, weights, bias)` | `P(y=1) = sigmoid(X·w + bias)` per row, with a numerically stable sigmoid. |
| `logistic_std_errors(X, y, weights, bias, l2)` | Standard errors from the inverse observed information `(X'WX + l2 I)^-1`, ordered `[se_w0, .., se_w{p-1}, se_bias]`; pass `l2=0` for plain-MLE, statsmodels-style SEs. |
| `elasticnet_fit(X, y, l1, l2, max_iter, tol=1e-10)` | Elastic net minimizing `(1/2n)·RSS + l1·L1(w) + (l2/2)·L2(w)^2` (bias unpenalized). `l1=l2=0` reproduces OLS; `l1=0` is ridge on this scaling. |

## Guarantees and edge behavior

Soft-thresholding is exact, so irrelevant features land on 0.0 **exactly**,
not near zero — the tests require an orthogonal irrelevant feature to be
below 1e-15 and an all-zero column to be pinned at literal `0.0`. Malformed
input (empty y, ragged X) returns a default result with `converged=False`
rather than trapping. With `l2 = 0` on separable data, logistic weights grow
until `max_iter` while probabilities stay finite and well-ordered; a small
ridge (the tests use `l2 = 1e-3`) keeps the optimum finite and the fitted
probabilities strictly increasing in x.

## Verification against closed-form references

The tests pin values that are checkable by hand (and against statsmodels):

- **Exact 2×2-table MLE**: groups with event rates 1/4 and 3/4 give the
  closed form `w = 2 ln 3 = 2.1972245773362196`,
  `bias = ln(1/3) = -1.0986122886681098`; `logistic_fit` matches both to
  1e-6, with log-likelihood `-4.498681156950466` and fitted probabilities
  recovering the group rates 0.25 / 0.75.
- **Standard errors**: on the same table the hand-inverted information
  matrix gives `se_w = sqrt(8/3) = 1.632993161855452`,
  `se_bias = sqrt(4/3) = 1.1547005383792515`; matched to 1e-4.
- **Elastic net fixed points**: on a centered orthogonal design with
  `l1=0.5, l2=0.25`, `w0 = S(4, 0.5)/(2 + 0.25) = 1.5555555555555556` to
  1e-12; lasso-only shrinkage `w0 = S(4, 0.5)/2 = 1.75` exactly;
  ridge-only `w = 4/3` on centered data; `l1=l2=0` recovers OLS
  (`w=2, b=1`); overwhelming `l1=100` kills all weights and leaves
  `bias = mean(y)`.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
