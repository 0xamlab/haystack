"""
normk — normalization kernels: RMSNorm, LayerNorm and QK-norm, forward and backward. Zero Python.

Where the frozen tree already is
----------------------------------
`normalization_layers` holds ten scalar helpers, and two of them are exactly the per-element formulas
a transformer needs: `rms_norm(x, rms, gamma, eps)` and `layer_norm(x, mean, variance, gamma, beta,
eps)`. They are frozen, correct, and this package calls them rather than restating them.

What is absent is everything around them. Both take their row statistic as an ARGUMENT — the RMS, or
the mean and variance — so the reduction was always the caller's. That reduction is where a norm goes
wrong: it has an axis to run along, a width that decides its rounding, an order that decides whether
two machines agree, and in LayerNorm's case a choice of formula that can return a negative variance.
None of that is expressible in a scalar helper, and all of it is what `normk` is.

There is also no backward pass anywhere in the frozen tree. A forward-only norm is the failure mode
the plan calls out by name: it looks perfect in inference and silently produces a worse model in
training. Both modules here ship `*_bwd_flat` alongside a `*_gradcheck_flat` that measures the
analytic gradient against central differences, so "the backward is right" is a number rather than a
reading of the algebra.

Two numerical choices, both stated rather than assumed
--------------------------------------------------------
| Choice | Why | How it is evidenced |
|---|---|---|
| LayerNorm variance is TWO-pass, never `mean(x^2) - mean(x)^2` | The one-pass identity catastrophically cancels on a row offset from zero — a residual stream after a few blocks — and can return a negative variance, making `sqrt` produce NaN from a kernel that "worked" | `layernorm_variance_agrees_flat` reports the gap between the two formulas on the caller's own data |
| Cross-row reductions are split by COLUMN, not by row | `dgamma` and `dbeta` sum across rows. One worker per row needs a shared accumulator: a race, and non-deterministic even when locked. Splitting by column gives each worker whole columns summed in row order — parallel and order-stable at once | the determinism promise's "same answer regardless of thread count" half, per backend |

`eps` is validated and then used exactly as given — never floored, never substituted. A checkpoint
trained at `1e-6` and served at `1e-5` produces different logits, and both values look reasonable to
every downstream check.

Modules
-------
  contract   — status codes 380-389, shape and epsilon validation, the tolerance constructor
  rmsnorm    — RMSNorm forward, backward, frozen-kernel agreement and gradcheck
  layernorm  — LayerNorm forward, backward, the variance-formula comparison and gradcheck

Dependency direction is one-way: `normk` uses `tensorx` for finiteness and the frozen
`normalization_layers` for per-element arithmetic, never the reverse.
"""
