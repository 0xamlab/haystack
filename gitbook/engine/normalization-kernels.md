---
icon: scale-balanced
description: LayerNorm and RMSNorm forward/backward kernels over flat row-major buffers, plus the shared contract that validates their row shapes and epsilon.
---

# Normalization kernels

Three modules for the layer that sits on the residual stream in front of every attention and
feed-forward block: the shared shape/epsilon contract, tensorized LayerNorm, and tensorized RMSNorm.
A norm is `O(rows * cols)` — next to attention it is nearly free — which is exactly why a mistake in
one is dangerous rather than obvious: a wrong `eps`, a row width that does not match the weight
vector, or a variance reduced over the wrong axis does not crash. It produces a model that trains and
is quietly worse. The frozen elementwise kernels (`normalization_layers.layer_norm`,
`normalization_layers.rms_norm`) take the per-row statistics as arguments and only do the final
arithmetic; the reduction that produces those statistics, the backward gradients, and the checks that
the reduction is actually correct are what this family adds.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("normk.contract", "norm_dims_check", [1024, 4096, 1e-6])["result"]
# 380 — NORM_OK: 1024 tokens x 4096 hidden fits the work budget with room to spare

runtime.execute("normk.contract", "norm_status_name", [386])["result"]
# "bad_epsilon"
```

## The modules

| Module | What it does |
| --- | --- |
| `normk.contract` | the status vocabulary (380-389), shape/epsilon validation (`norm_dims_check`), and the overflow-safe work-budget check (`norm_work_fits`) every kernel below calls first |
| `normk.layernorm` | LayerNorm forward and backward over `[n_rows][n_cols]` row-major buffers, plus a variance-formula agreement check and a gradient check against central differences |
| `normk.rmsnorm` | RMSNorm forward and backward over the same layout, plus a check that the forward agrees with the frozen elementwise kernel element-by-element, and its own gradient check |

`normk` owns status codes 380-389, immediately after `attnk`'s 360-379 and immediately before
`mlpk`'s 390-399 — the same order a transformer block runs them in: a norm on the residual stream,
then attention, then a second norm, then the feed-forward sublayer.

## The contract: one status vocabulary, one work budget

`norm_dims_check(n_rows, n_cols, eps)` is the single entry point both kernels call before touching
their input: it rejects an empty dimension (`NORM_ERR_EMPTY_DIM`), a dimension past
`NORM_MAX_COLS` (2^20) or `NORM_MAX_ROWS` (2^24) (`NORM_ERR_DIM_TOO_LARGE`), a bad epsilon
(`NORM_ERR_BAD_EPS`), and — as a separate, third check — a legal-by-dimension shape whose *product*
still overflows the work budget (`NORM_ERR_WORK_TOO_LARGE`). That budget check,
`norm_work_fits(n_rows, n_cols, ceiling)`, grows the ceiling by division one factor at a time instead
of forming `n_rows * n_cols` and comparing: `test_normk_contract.mojo` passes `n_rows = n_cols = 2^40`,
a product that overflows a signed 64-bit multiply to a small or negative number, and confirms it is
still refused. An ordinary shape — 1024 tokens by 4096 hidden — is confirmed to fit the same budget in
the same test.

**Why `eps` is validated rather than clamped.** `eps` is not a tuning knob a kernel is free to
improve on: a checkpoint trained with `1e-6` and served with `1e-5` produces different logits, and
both values look reasonable, so the difference survives every downstream check. `norm_eps_ok` allows
`eps == 0.0` — mathematically correct for a row known to be non-zero — and refuses any negative value,
because `variance + eps` (or `mean_sq + eps`) going negative sends `sqrt` to NaN on otherwise ordinary
input, a failure that surfaces far from `eps`'s definition. Both halves are asserted directly:
`norm_eps_ok(0.0)` and `norm_eps_ok(1.0e-6)` are `True`, `norm_eps_ok(-1.0e-6)` is `False`.

`norm_tol_for(magnitude, n_cols)` is the tolerance every agreement check below uses to decide
"close enough": `1e-14 * (1 + |magnitude|) * (1 + n_cols)`. It grows with the row width because a
norm sums `n_cols` squared terms before dividing, so its rounding error grows with that width — a
fixed `1e-12` that passes at 128 columns is a false negative at 16,384 — and the `1 + magnitude` floor
keeps a value that legitimately normalizes to near zero from being held to an impossible bound.

## RMSNorm, worked

`rmsnorm_fwd_flat(x, gamma, n_rows, n_cols, eps)` computes `ms = mean(x^2) + eps`,
`r = 1/sqrt(ms)`, then `y_j = x_j * r * gamma_j` for every row — the reduction `mean(x^2)` is the
only part not handed to the frozen `rms_norm` kernel. One row, one call:

```python
x = [1.0, 2.0, 3.0, 4.0]
gamma = [1.0, 1.0, 1.0, 1.0]

out = runtime.execute("normk.rmsnorm", "rmsnorm_fwd_flat", [x, gamma, 1, 4, 1e-6])["result"]
out["status"]  # 380 — NORM_OK
out["rstd"]    # [0.3651483473268884]  — 1 / sqrt(mean(x^2) + eps) = 1 / sqrt(7.500001)
out["y"]       # [0.3651483473268884, 0.7302966946537768, 1.0954450419806652, 1.4605933893075536]
```

`mean(x^2)` here is `(1 + 4 + 9 + 16) / 4 = 7.5`, and every `y_j` is exactly `x_j * out["rstd"][0]`
— RMSNorm has no mean subtraction, so it is scale-equivariant rather than shift-equivariant:
`test_normk_rmsnorm.mojo` scales this same kind of row by 1000x and asserts the normalized output
changes by less than `1e-12` at `eps = 0`.

## LayerNorm, worked

`layernorm_fwd_flat(x, gamma, beta, n_rows, n_cols, eps)` computes the row mean, then the variance
of the deviations *from that mean* (not the fused `mean(x^2) - mean(x)^2` form — see below), then
`y_j = (x_j - mu) * rstd * gamma_j + beta_j`. With `gamma = 1` and `beta = 0`, the definition alone
guarantees every output row has mean 0 and variance 1:

```python
gamma = [1.0, 1.0, 1.0, 1.0]
beta = [0.0, 0.0, 0.0, 0.0]

out = runtime.execute("normk.layernorm", "layernorm_fwd_flat", [x, gamma, beta, 1, 4, 0.0])["result"]
out["status"]  # 380 — NORM_OK
out["mean"]    # [2.5]
out["rstd"]    # [0.8944271909999159]  — 1 / sqrt(variance) = 1 / sqrt(1.25)
out["y"]       # [-1.3416407864998738, -0.4472135954999579, 0.4472135954999579, 1.3416407864998738]
```

`test_normk_layernorm.mojo` asserts exactly this property — mean below `1e-14` and variance within
`1e-13` of 1 — on its own pseudo-random rows, and that unlike RMSNorm, LayerNorm is *shift*-equivariant:
adding a constant to every element of a row does not change its normalized output, because the mean
subtraction removes it.

## Why the variance is computed in two passes, measured

The one-pass identity `variance = mean(x^2) - mean(x)^2` fuses both reductions into a single walk of
the row and is the obvious optimization. It is also catastrophically cancelling once a row sits far
from zero — exactly what a residual stream looks like after a few blocks — because the two terms then
agree to most of their significant digits and the subtraction keeps only the noise. `normk.layernorm`
uses the two-pass form instead: the mean first, then `mean((x - mu)^2)`, a second walk of a row that
is already in cache after the first.

`layernorm_variance_agrees_flat(x, n_rows, n_cols)` measures the gap between the two formulas on the
caller's own data rather than asserting it. Reproducing the test file's own deterministic input
(`_pseudo(24, 1)`: 3 rows of 8, values in roughly `[-1, 1]`) gives:

| Data | One-pass vs. two-pass gap | Tolerance | Agree? |
| --- | --- | --- | --- |
| Centred (as generated) | `0.0` | `9.0e-14` | yes |
| Same rows, offset by `+1e8` | `1.691` | `1.18e-13` | **no** |

Offsetting every element by `1e8` — a value the true variance (order 1) does not reflect at all —
turns a formula that agreed exactly on centred data into one that is wrong by more than the quantity
it is supposed to compute. Pushed further, the one-pass form returns a *negative* variance and `sqrt`
produces NaN for perfectly ordinary input; the two-pass forward is unaffected by the same offset,
which is the whole argument for paying for the second pass rather than taking it on faith.

## Backward gradients check themselves against a dropped term

Both kernels' backward passes have a term that a forward-only reading of the algebra drops, and in
both cases the gradient stays finite and plausibly scaled without it — it just trains the model worse
in a way no forward-pass check would catch:

* **RMSNorm:** `dx_j = r * (g_j * dy_j) - x_j * r^3 * SUM_k(dy_k * g_k * x_k) / n`. The coupling term
  — `x_j` times the sum over the whole row — is the one a reader drops.
* **LayerNorm:** `dx = rstd * (dxhat - mean(dxhat) - xhat * mean(dxhat * xhat))`, where
  `xhat = (x - mu) * rstd` and `dxhat = dy * gamma`. Both correction terms are load-bearing: one
  accounts for a perturbed element moving the row's mean, the other for it moving the row's variance.

`rmsnorm_gradcheck_flat` and `layernorm_gradcheck_flat` compare the analytic `dx` against a central
difference of `SUM(y)` with `dy` fixed to all ones (so every term, including the dropped one, is
exercised) and report the worst element's gap against a tolerance built from `step^2` — a central
difference cannot resolve a gradient more precisely than that, so judging it against the forward
kernel's tighter tolerance would fail on correct code. Both test files go further and recompute `dx`
*without* the coupling term — exactly the simplification a careless derivation makes — and assert the
naive version is detectably wrong: it moves `dx` well outside tolerance, which is what makes the
passing gradcheck meaningful rather than a check that could never fail. (Measured cost and precision
for both backward passes are published separately in [Normalization
benchmarks](../benchmarks/normalization.md).)

## Reduction order does not move with thread count

`dgamma` (RMSNorm) and `dgamma`/`dbeta` (LayerNorm) reduce *across rows*, while `dx` is independent
per row. Both modules parallelize `dx` by row band and the parameter gradients by **column** band
instead — each worker owns whole columns and sums them in row order — because splitting the parameter
reduction by row would need a shared accumulator across workers, which is a race, and a locked one
would still sum in whatever order threads happened to arrive. `test_normk_rmsnorm.mojo` checks this
on a shape built specifically to cross the module's parallel threshold — 4096 rows of 8 columns — and
finds its `dgamma` bit-identical to a serial, row-order hand sum regardless of worker count.
`layernorm`'s test checks the simpler special case directly: with `dy` all ones, `dbeta` is exactly
the column sum of `dy`, i.e. `n_rows`, with zero drift.

## Refusal behavior

Both kernels return a non-OK status rather than reading past the end of a buffer or aborting the
worker:

* A negative `eps` is refused (`NORM_ERR_BAD_EPS`, 386) before any `sqrt` runs.
* A `gamma`, `beta`, `x`, `dy`, `mean`, or `rstd` shorter than the shape implies is refused
  (`NORM_ERR_LENGTH_MISMATCH`, 382) rather than read out of bounds.
* The generic "A-Z" probe shape — every input list 5 elements long, every count argument 5 — is
  refused on both kernels (`5 * 5 = 25 > 5`) rather than accepted and left to produce whatever a
  length-5 buffer holds at index 24.

## Verification

`mojo/tests/libs/test_normk_contract.mojo` hand-asserts the status range does not collide with
`attnk`, `gemm`, or `tensorx`'s own OK codes, that the work-budget guard survives a wrapping product,
and both halves of the epsilon rule. `mojo/tests/libs/test_normk_layernorm.mojo` and
`mojo/tests/libs/test_normk_rmsnorm.mojo` assert the normalized-moment and equivariance properties
above, the variance-formula and frozen-kernel agreement checks, both gradient checks and their
provably-failing counterparts, and the length/epsilon/A-Z refusals — all on deterministic pseudo-random
input so a failure reproduces exactly.

**Next:** the [attention kernels](attention-kernels.md) this module's status range sits next to, or
browse the [runtime library catalog](runtime-library-catalog.md) for every function in both modules.
