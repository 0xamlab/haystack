---
icon: wave-sine
description: Gaussian process regression with RBF and Matern kernels, exact posterior mean and variance.
---

# Gaussian process regression

`gaussian_process` fits exact zero-mean Gaussian processes on flat row-major
feature matrices: covariance construction, its own Cholesky factorization,
posterior mean/variance prediction, and log marginal likelihood. It replaces
`sklearn.gaussian_process` (`GaussianProcessRegressor` with RBF / Matern
nu = 1.5 kernels) and basic GPy usage, with zero Python imports. Fitting is
deterministic and O(n³) — sub-millisecond up to n ≈ 200, with n ≈ 2000 the
practical exact-GP cap.

## Functions

| Function | What it does |
|---|---|
| `kernel_rbf(r, lengthscale, signal_var)` | RBF (squared-exponential) covariance `signal_var · exp(-r²/(2·lengthscale²))` at Euclidean distance r. |
| `kernel_matern32(r, lengthscale, signal_var)` | Matern nu = 3/2 covariance `signal_var · (1 + √3·r/l) · exp(-√3·r/l)`. |
| `gp_fit(x, y, dim, lengthscale, signal_var, noise_var, kernel)` | Fits an exact GP: builds `K + noise_var·I`, Cholesky-factorizes, solves `alpha = K⁻¹y`. `kernel` is `KERNEL_RBF` or `KERNEL_MATERN32`. |
| `gp_predict(x_train, fit, x_new)` | Posterior mean `k*ᵀ alpha` and latent variance `signal_var − ‖L⁻¹k*‖²` (clamped at 0) per query row; O(n²) per point. |
| `gp_loglik(fit, y)` | Log marginal likelihood `-½ yᵀalpha − Σ log L_ii − n/2 · log 2π` of the training targets. |

## Guarantees and failure modes

- **Deterministic.** Refitting identical inputs reproduces `alpha`
  bit-for-bit (asserted in the tests). If the factorization hits a
  non-positive pivot (e.g. `noise_var = 0` with duplicate rows), it retries
  on a deterministic escalating jitter ladder (1e-10, 1e-8, 1e-6 scaled by
  `signal_var + noise_var`), recorded in `fit.jitter` (0.0 normally).
- Predicted variance is the **latent-function** variance and excludes
  observation noise; add `fit.noise_var` for a noisy-observation predictive
  variance. Far from all training points the posterior reverts to the
  prior: mean → 0, variance → `signal_var` (tested to 1e-6).
- Invalid input (empty data, length mismatch, `lengthscale <= 0`,
  `signal_var <= 0`, `noise_var < 0`, unknown kernel) returns
  `ok = False` with empty fields; `gp_loglik` returns NaN on a bad fit or
  wrong-length `y`. No exceptions on the money path.

## Verification

Tests pin the numerics against closed-form references:

- Kernel values: `kernel_rbf(1, 1, 1) = exp(-0.5) = 0.6065306597126334` and
  `kernel_matern32(1, 1, 1) = (1+√3)·e^{-√3} = 0.4833577245965077`, both to
  1e-12; `r = 0` returns exactly `signal_var`.
- 2-point toy (x = [0, 1], y = [1, 2], RBF, l = 1, sv = 1, noise = 0.1)
  against the analytic 2×2 inverse: `alpha = [-0.13425787820991109,
  1.8922104722202504]` (1e-9), prediction at 0.5 has mean
  1.5513877191046792 and variance 0.08727009545489339 (1e-9), and the log
  marginal likelihood equals the closed form −3.5770425527832885 (1e-8;
  Mojo's `std.math` log/exp are ~1e-10-accurate approximations).
- n = 1 closed forms: loglik −1.8270838991417502 and prediction at the
  training point `sv/(sv+noise) · y = 1.2` exactly (1e-12).
- Interpolation sanity for both kernels: mean ≈ `y_i` at training points
  with variance ≈ 0 (tol 1e-3), including duplicate rows and 2-D inputs.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
