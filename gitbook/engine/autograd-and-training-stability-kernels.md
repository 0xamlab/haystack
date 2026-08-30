---
icon: diagram-project
description: Reverse-mode autodiff graph bookkeeping, per-operation gradient formulas, ten optimizer update rules, and the loss-scaling/NaN-guard/numerically-safe primitives that keep a training loop from diverging.
---

# Autograd and training-stability kernels

Five modules for the arithmetic underneath a training loop, as opposed to the arithmetic underneath
a single forward pass: the computation-graph bookkeeping reverse-mode autodiff needs (fan-out
counting, checkpointing's recompute-vs-memory tradeoff, topological ordering, JVP/VJP), the local
gradient formula for each elementary operation a graph node might be, ten optimizer update rules from
plain SGD through Adam, AdamW, LARS and Lion, the training-loop guards that keep mixed-precision and
long runs from silently diverging (dynamic loss scaling, gradient/loss NaN detection, warmup and
cosine LR schedules, EMA, overflow-skip), and the numerically-safe primitives — `logsumexp`,
`softmax`, Kahan summation, Welford's online variance — that loss functions and normalization layers
build on to avoid overflow and catastrophic cancellation. Every function in this family is a pure
scalar (or `List[Float64]`) computation with no persistent state and no struct in its return type: the
caller owns the moment estimates, running norms, and step counters, and calls these once per
parameter (or once per step) to advance them. This is deep-learning training infrastructure — it has
no relationship to the `ml.*` classical-statistics/ML namespace documented elsewhere in this corpus
(logistic regression, gradient-boosted trees, HMMs, and the rest), which fits models with closed-form
or coordinate-descent solvers that never touch a computation graph or an Adam optimizer at all.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# One Adam step, with eps left as its own argument.
runtime.execute("gradient_descent", "adam_update", [1.0, 0.2, 0.04, 0.1, 1e-8])["result"]
# 0.9000000049999998 — bias-corrected m_hat=0.2, v_hat=0.04: 1.0 - 0.1*0.2/(sqrt(0.04)+1e-8)

# Global-norm gradient clipping scale, applied to every parameter's gradient.
runtime.execute("autograd_graph", "gradient_norm_clip_scale", [8.0, 2.0])["result"]
# 0.25 — grad norm 8.0 exceeds max_norm 2.0, so every gradient gets multiplied by 2.0/8.0
```

## The modules

| Module | What it does |
| --- | --- |
| `autograd_graph` | reverse-mode computation-graph primitives — fan-out counting, gradient accumulation, checkpointing's recompute-vs-memory-save cost ratio, topological sort keys, loss scaling, JVP/VJP, dead-node pruning, and global gradient-norm clip scale |
| `autograd_ops` | the local gradient formula for ten elementary operations — add, mul, exp, log, ReLU, sigmoid, tanh, pow, the chain rule itself, and the diagonal of the softmax Jacobian |
| `gradient_descent` | ten optimizer parameter-update rules — SGD, SGD+momentum, Adam, AdamW, RMSProp, AdaGrad, LARS, Lion, gradient-norm clipping, and cosine-annealing learning rate |
| `training_stability` | training-loop guards — dynamic AMP loss-scale adjustment, finite-value checks, gradient accumulation across micro-batches, linear warmup and warmup+cosine LR schedules, EMA weight tracking, overflow-skip step counting, loss-spike detection, and a Chinchilla compute-budget step count |
| `numerical_stability` | numerically safe building blocks — stable `logsumexp`/`softmax`/`log_softmax`, Kahan compensated summation, Welford's online mean/variance, stable sigmoid/log-sigmoid/softplus, `log_add_exp`, probability normalization, relative error, and divide-by-near-zero protection |

## Reverse-mode autodiff is graph bookkeeping, not a graph object

`autograd_graph` has no `Node` struct — every function takes the handful of scalars a graph
implementation would otherwise store on a node and returns the one updated scalar. `grad_accumulate`
is literally `current_grad + incoming_grad` — the sum a node's gradient buffer needs when more than
one downstream consumer sends it a gradient — and `node_output_count` increments the fan-out counter
that tells a backward pass when every consumer has reported in.

`checkpointing_cost` is the actual decision behind activation checkpointing: given how much memory
recomputing an activation would save and how expensive that recompute is against the hardware's own
FLOPs and memory-bandwidth numbers, it returns `recompute_time / memory_time` — under 1.0 means
checkpointing that segment is a net win.

```python
runtime.execute("autograd_graph", "checkpointing_cost", [1e9, 1e11, 1e13, 1e10])["result"]
# 0.09999999999999999 — recompute_time = 1e11/1e13 = 0.01s, memory_time = 1e9/1e10 = 0.1s;
# recomputing this segment costs 10x less time than the memory bandwidth it would take to keep it
```

`memory_efficient_backward_step` answers the companion question — how much memory a checkpointed
segmentation actually keeps resident:

```python
runtime.execute("autograd_graph", "memory_efficient_backward_step", [1e8, 4, 1e10])["result"]
# 0.04 — 4 segments x 1e8 bytes stored = 4e8 bytes, 4% of the 1e10-byte total without checkpointing
```

`jacobian_vector_product` and `vector_jacobian_product` are the forward- and reverse-mode halves of
the same local Jacobian-vector contraction — `local_jacobian * tangent` going forward,
`upstream_grad * local_jacobian` going backward — kept as two named functions rather than one because
a caller building a JVP-based graph and one building a VJP-based (standard backprop) graph read the
argument order differently even though the arithmetic is identical multiplication.

## Per-operation local gradients feed the chain rule, not the other way around

`autograd_ops` has one function per elementary operation a graph node could be, each computing
`∂(op)/∂x`, and a separate `chain_rule` function (`upstream * local_grad`) that a caller applies
after getting the local gradient from whichever of the other nine functions matches the node's
operation. None of the nine gradient functions call `chain_rule` themselves — multiplying by the
upstream gradient is folded directly into each one (`grad_mul` is already `other * upstream`, not
`other` followed by a separate multiply), so `chain_rule` exists for the case where a caller already
has a bare local Jacobian element from somewhere else and needs to combine it with an upstream
gradient by hand.

```python
runtime.execute("autograd_ops", "grad_sigmoid", [0.5, 1.0])["result"]
# 0.25 — sigmoid(0) = 0.5, and sigma(1-sigma) at sigma=0.5 is exactly 0.25, the maximum
# slope of the sigmoid curve; this is why gradients vanish away from x=0, not at it

runtime.execute("autograd_ops", "grad_pow", [2.0, 3.0, 1.0])["result"]
# 12.0 — d/dx(x^3) at x=2 is 3*2^2 = 12

runtime.execute("autograd_ops", "grad_log", [0.5, 1.0])["result"]
# 2.0 — d/dx(log x) at x=0.5 is 1/0.5
```

`grad_log` refuses rather than propagate a domain error: it returns `0.0` for `x <= 0.0` instead of
dividing by a non-positive number. `grad_pow` is computed as `n * exp((n-1) * log(x))` — the
log-then-exp form needed to raise a non-integer exponent — and only short-circuits to `0.0` when
`x == 0.0` and `n < 1.0` exactly; every other non-positive `x` (a negative base, or zero with
`n >= 1.0`) falls through to the same formula with `1e-300` substituted for `x`, since `log` cannot
take a non-positive argument at all. That substitution happens to reproduce the right answer at the
boundary `n == 1.0` (the `(n-1)` exponent is `0`, so the substituted value cancels out and
`grad_pow(0.0, 1.0, 1.0)` correctly returns `1.0`) and comes close for `n > 1.0` (`grad_pow(0.0, 2.0,
1.0)` returns `2.0000000000000475e-300`, numerically indistinguishable from the true `0.0`) — but it
is not a correct derivative for a **negative** base with an odd integer exponent: `grad_pow(-2.0, 3.0,
1.0)` returns `0.0` where `d/dx(x^3)` at `x=-2` is actually `3*(-2)^2 = 12.0`. This is a real gap in
`grad_pow`, not a documentation omission — a caller differentiating through a node that legitimately
takes negative bases to an odd power should not rely on it. `grad_sigmoid`, `grad_tanh`, and
`grad_softmax_diag` all take the *forward-pass
output* (`sigmoid_out`, `tanh_out`, `softmax_i`), not the input `x` — the standard trick that lets a
backward pass reuse a value already computed on the forward pass instead of recomputing `sigmoid(x)`
from `x` a second time.

## Ten optimizer update rules, one parameter and one call at a time

`gradient_descent` has no optimizer object holding `(m, v, step)` per parameter — that state is the
caller's to keep (typically one flat array per moment, indexed alongside the parameters), and each
function takes that state in and returns one updated parameter value out. `adam_update` and
`adamw_update` both take already bias-corrected `m_hat`/`v_hat` — the `1 - beta1^t` / `1 - beta2^t`
correction is the caller's arithmetic, not this function's, which is why the signature has no `step`
or `beta1`/`beta2` argument at all.

```python
runtime.execute("gradient_descent", "adagrad_update", [1.0, 0.5, 0.0, 0.1, 1e-8])["result"]
# 0.900000002 — new_acc = 0 + 0.5^2 = 0.25, sqrt(0.25) = 0.5 exactly,
# so this step is param - lr*grad/(0.5+eps), a hair above the idealized 1.0 - 0.1

runtime.execute("gradient_descent", "lars_update", [1.0, 0.5, 10.0, 2.0, 0.01, 0.001, 0.0001])["result"]
# 0.9999750074962519 — LARS's own trust-ratio local_lr = 0.001*10.0/(2.0+0.0001*10.0) = 0.0049975,
# far smaller than the global lr=0.01 alone would give, which is the point of layer-wise scaling:
# a layer with a small gradient norm relative to its parameter norm gets a gentler effective step

runtime.execute("gradient_descent", "lion_update", [1.0, 0.1, 0.5, 0.01, 0.9, 0.99, 0.01])["result"]
# 0.9899 — c = sign(0.9*0.1 + 0.1*0.5) = sign(0.14) = +1, so the update magnitude (lr*(1+wd*param))
# is identical regardless of whether the raw gradient was 0.5 or 50.0; Lion's update size depends
# only on the sign of the momentum-blended gradient, never its magnitude
```

`lion_update`'s `sign_c` is `0.0` (not `+1` or `-1`) exactly when the momentum-blended gradient is
`0.0`, the one case where the update is pure weight decay with no gradient-direction term at all.
`lars_update` and `gradient_clipping` both refuse to divide into a non-positive denominator: LARS
returns the parameter unchanged if `grad_norm + weight_decay * param_norm <= 0.0`, and
`gradient_clipping` is a no-op — the raw gradient passes through — whenever `grad_norm <= max_norm`,
so a well-behaved step costs nothing beyond one comparison.

## Training-loop guards: what decides whether a step happens at all

`training_stability` is the layer that watches the training loop itself rather than any one
parameter — deciding whether a step's gradients are trustworthy, whether the loss scale needs to
move, and what learning rate this step should use.

```python
runtime.execute("training_stability", "loss_scale_adjust", [65536.0, 1.0, 2.0, 2.0, 2000.0, 0.0])["result"]
# 32768.0 — overflow_occurred > 0.5, so the AMP loss scale halves this step rather than growing

runtime.execute("training_stability", "loss_spike_detector", [8.0, 2.0, 4.0])["result"]
# 0.0 — 8.0 / 2.0 == 4.0 exactly equals the threshold, and the check is a strict '>', not '>=';
# 8.01 / 2.0 = 4.005 does trip it (returns 1.0) — the boundary itself never counts as a spike

runtime.execute("training_stability", "gradient_accumulation_step", [0.3, 0.8, 4.0])["result"]
# 0.5 — the accumulator already holds 0.3 from three prior micro-batches (0.8, 0.4, 0.0,
# each folded in as g/4); this fourth call folds in 0.8/4=0.2, landing on 0.5 — the plain
# arithmetic mean of the four micro-batch gradients [0.8, 0.4, 0.0, 0.8]
```

`is_finite_check` and `grad_norm_finite` both use the same two-part test — `value != value` catches
NaN (the one IEEE 754 value that compares unequal to itself), and a magnitude bound catches Inf
without calling a library `isinf` — but at different thresholds: `is_finite_check` refuses past
`1e308` (just under `Float64`'s max), while `grad_norm_finite` refuses a gradient norm past `1e8`,
because a legitimately huge-but-finite gradient norm is itself a training-health signal a caller
wants to act on long before it reaches `Float64`'s actual ceiling. `overflow_skip_step` is the
companion to `loss_scale_adjust`: the optimizer step counter does not advance on an overflowed step
(the update is discarded, not applied at a wrong scale), which keeps the step count and the
scheduler's `step` argument in sync with the number of updates that actually landed.

## Numerically safe primitives underneath the loss

`numerical_stability` is what a loss function or a softmax layer calls instead of the textbook
formula, specifically to survive inputs the textbook formula cannot. `logsumexp` is the clearest
case: computing `log(sum(exp(x_i)))` directly overflows the moment any `x_i` exceeds about 709 (where
`exp` overflows `Float64`), but subtracting the row max before exponentiating never does, because
every shifted term is `<= 0`:

```python
runtime.execute("numerical_stability", "logsumexp", [1000.0, 1000.0])["result"]
# 1000.6931471805599 — exp(1000) alone would overflow to inf; exp(1000-1000)=exp(0)=1 never does,
# and the max (1000.0) is added back in log-space at the end: 1000 + log(2)
```

`kahan_sum`'s compensated summation is not a marginal improvement — accumulating 100,000 copies of
`0.1` with a plain running total drifts to `10000.000000018848` (an error of `1.88e-8`, from
100,000 individual roundings each losing a fraction of a bit), while Kahan summation of the identical
input lands on exactly `10000.0`, matching an arbitrary-precision sum to the last bit. `welford_mean_var`
computes mean and variance in one pass with the same guarantee Welford's algorithm is known for —
`welford_mean_var([1.0, 2.0, 3.0, 4.0, 5.0])` returns `[3.0, 2.0]`, the population mean and variance,
without ever forming `sum(x)` or `sum(x^2)` (whose difference is where the classic single-pass
variance formula loses precision on data far from zero).

`sigmoid_stable` branches on the sign of `x` specifically so it never evaluates `exp` at a large
positive argument: `1/(1+exp(-x))` for `x >= 0` only ever exponentiates a non-positive number, and the
mirror-image form `exp(x)/(1+exp(x))` for `x < 0` does the same on the other side. The naive single
formula `1/(1+exp(-x))` raises `OverflowError` in plain Python at `x = -1000` (it needs `exp(1000)`);
`sigmoid_stable(-1000.0)` returns `0.0` with nothing thrown, because it never takes that branch.
`softplus` similarly short-circuits above `x = 20.0` (returning `x` directly, since `log(1+exp(x))
approx x` there to `Float64` precision) and below `x = -20.0` (returning `exp(x)`, since `log(1+eps)
approx eps`), computing the full `log(1 + exp(x))` only in between. `relative_error` and `safe_divide`
both guard the same failure mode from opposite ends: `relative_error` falls back to the raw absolute
error (`|approx|`) when `|exact| < 1e-300` rather than dividing by a number indistinguishable from
zero, and `safe_divide` returns its caller-supplied `default` under the identical threshold rather
than producing `inf`.

## What this family is not

Nothing in this family imports, or is imported by, another kernel module — a search of every
`from <module> import` line across `mojo/engine/` finds these five modules referenced only from the
generated runtime dispatch table, never from another hand-written kernel. That is a real distinction
from three other places gradients and training show up in this corpus:

* **[LSTM sequence training (BPTT)](ml-sequence-training.md)** — `seq_training.bptt_train_lstm` is a
  complete, self-contained training loop with its own **locally implemented** Adam optimizer and
  global-norm gradient clipping baked directly into that one function, for that one architecture. It
  does not call `gradient_descent.adam_update` or `gradient_descent.gradient_clipping` — the two
  implementations compute the same textbook Adam and the same clip-by-global-norm formula
  independently, in two different files, because `seq_training` predates this family and was never
  rewired to depend on it.
* **[Attention kernels](attention-kernels.md)**'s `attnk.backward` and **[MLP block
  kernels](mlp-block-kernels.md)**'s gated-FFN backward path compute analytic gradients too, but for
  one specific fused tensor operation each (scaled dot-product attention, SwiGLU/GEGLU) over flat
  `[token][dim]` buffers — not the generic per-scalar operation-by-operation formulas `autograd_ops`
  provides. A caller wiring a custom graph node for, say, a sigmoid activation reaches for
  `autograd_ops.grad_sigmoid`; a caller running a full attention block's backward pass reaches for
  `attnk.backward` directly, and never touches this family at all.
* **The `ml.*` namespace** (logistic regression via IRLS, elastic-net via coordinate descent,
  gradient-boosted trees, HMMs, and the rest) fits models with closed-form or iterative-but-graph-free
  solvers. None of those kernels build a computation graph, call an elementwise gradient function, or
  hold an Adam moment estimate — this family and that one do not overlap in either direction.

## Verification

All five test files in this batch (`mojo/tests/libs/test_autograd_graph.mojo`,
`test_autograd_ops.mojo`, `test_gradient_descent.mojo`, `test_training_stability.mojo`,
`test_numerical_stability.mojo`) are auto-generated smoke tests: each one calls every public function
with a fixed, generic input (typically `0.5` for scalars, `[0.5, 0.6, 0.7, 0.4, 0.3]` for
`List[Float64]` arguments) and asserts only that the result is finite — there is no pinned numeric
assertion anywhere in this batch to cross-check a worked example against. Every worked number in this
page was instead computed independently in plain Python from the formula in the module's own
docstring and source (`mojo/engine/autograd_graph.mojo`, `autograd_ops.mojo`, `gradient_descent.mojo`,
`training_stability.mojo`, `numerical_stability.mojo`), the same way a prior batch of this corpus
handled `ml.classifiers`/`ml.random_forest` when those test files turned out to be smoke-only too. The
Kahan-summation and `logsumexp` overflow examples were additionally checked against `math.fsum` and
against the `OverflowError` plain Python raises on the naive formula, so the claimed advantage is a
real, reproducible one rather than an assertion about the kernel's own internals.

**Next:** see the fused, tensor-level analytic backward passes these per-scalar formulas are the
building blocks for in [Attention kernels](attention-kernels.md) and [MLP block
kernels](mlp-block-kernels.md), or browse the [Runtime library catalog](runtime-library-catalog.md)
for every module and function.
