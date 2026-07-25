---
icon: arrow-trend-up
description: NIPALS PLS1 regression for collinear and wide (p > n) feature matrices, sklearn-matched.
---

# Partial least squares regression (PLS1)

`pls` fits partial least squares regression for a single response vector
with the NIPALS algorithm — replacing
`sklearn.cross_decomposition.PLSRegression` for one `y`, with zero Python
imports. PLS projects X onto latent components of maximal covariance with
y, staying stable on collinear or wide feature blocks where the normal
equations behind closed-form OLS/ridge degrade. It complements
`regression.mojo` (closed-form OLS/ridge) and `linear_models.mojo`
(iterative logistic / elastic-net).

## Functions

| Function | What it does |
|---|---|
| `pls_fit(x, n_rows, n_cols, y, n_components, max_iter, tol)` | NIPALS PLS1 fit on a flat row-major X. Per component: weights `w = E'f/‖E'f‖`, scores `t = Ew`, loadings, y-loading, then deflation; coefficients `B = W (P'W)⁻¹ q`. Returns a `PLSResult`. |
| `pls_predict(model, x_row)` | Predict y for one raw feature row; the model's centering/scaling state maps back to original units. Wrong-length rows and empty models return `y_mean`. |
| `pls_predict_rows(model, x, n_rows)` | Predict every row of a flat row-major raw feature matrix; empty list on shape mismatch. |
| `pls_r2(model, x, n_rows, y)` | R² = 1 − SS_res / SS_tot of model predictions on a raw (X, y) set. |

`PLSResult` carries weights W, loadings P, scores T (component-major),
y-loadings q, coefficients B (standardized space), the centering/scaling
state, per-component explained-variance fractions for X and y, and
per-component NIPALS iteration counts.

## Guarantees

- **Fully deterministic** — no RNG anywhere in the fit.
- X columns and y are centered and scaled internally (sample std, ddof=1;
  zero-variance columns get scale 1.0); predictions are in original units.
- The component count is clamped to `min(n_cols, n_rows − 1)` and
  extraction stops early once no X/y covariance remains — you may get
  fewer components than requested, never garbage ones.
- Graceful degradation: invalid shapes return an empty model; zero
  components (constant y, n = 1, `n_components = 0`) leave coefficients at
  zero so prediction falls back to `y_mean`.

## Verification

Known-value tests pin the algebra, not just behavior:

- A hand-derived 2×2 fixture matches NIPALS exactly to 1e-9: weights and
  loadings `(1/√2, 1/√2)`, scores `(−1, 1)`, y-loading `1/√2`, coefs
  `(0.5, 0.5)`, explained variance 1 for both X and y.
- A rank-2 collinear fixture (`x3 = x1 − 2·x2`, y noiseless in the column
  space) is recovered with exactly 2 components: R² > 0.999 and maximum
  prediction error below 1e-6 — the regime where plain normal equations
  degrade.
- Structural invariants: score vectors mutually orthogonal (normalized
  dot < 1e-8), weight vectors unit-norm to 1e-9, explained-variance-y sums
  to 1 on fully explained data.
- Edge cases proven: constant y and constant (zero-variance) columns,
  n = 1, shape mismatches, and over-requested component counts all degrade
  to the documented fallbacks.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
