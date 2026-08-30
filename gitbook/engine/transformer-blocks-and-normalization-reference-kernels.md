---
icon: diagram-project
description: Scalar reference formulas for assembling a transformer block (residual, pre/post-norm, causal mask, FFN), a broad normalization catalog beyond LayerNorm/RMSNorm, general non-transformer NN primitives, and single-expression fusion patterns.
---

# Transformer blocks and normalization reference kernels

Four modules of small, single-value formulas for the arithmetic a transformer implementation is
built out of, at a level below the tensorized production kernels: `transformer_blocks` assembles
the pieces of a full pre-norm or post-norm block — residual add, causal masking, one-head
attention weighting, the two feed-forward linears — around sublayer outputs computed elsewhere;
`normalization_layers` is a textbook-breadth reference of normalization formulas (batch, instance,
group, spectral, weight norm, RMSNorm, AdaLN, DeepNorm's alpha) that takes precomputed statistics
rather than reducing over a buffer itself; `nn_layers` is a general, non-transformer-specific set
of neural-net building blocks (dense layer, activations, losses, dropout, a self-reducing batch
norm, Xavier init); and `fused_kernels` writes out the single-expression fusion patterns — score +
mask, matmul + bias + activation, RoPE + attention, add + norm — that a hand-written fused kernel
body actually contains, plus a formula for the memory traffic fusing them saves. Every function in
all four modules operates on plain `Float64` scalars (or, in `nn_layers`, flat `List[Float64]`
vectors) — there is no row/column shape, no batching, and no backward pass; these are the formulas,
not the kernel that runs them at scale.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("transformer_blocks", "gated_feedforward", [3.0, 2.0])["result"]
# 5.284782467867295 -- SiLU(2.0) * 3.0: SiLU(gate)=2.0/(1+exp(-2.0))=1.7615941559557649

runtime.execute("normalization_layers", "rms_norm", [3.0, 2.0, 1.5, 1e-6])["result"]
# 2.249999718750053 -- x / sqrt(rms^2 + eps) * gamma = 3.0 / sqrt(4.000001) * 1.5
```

## The modules

| Module | What it does |
| --- | --- |
| `transformer_blocks` | the scalar formulas that assemble a full pre-norm/post-norm transformer block — residual connections, causal masking, one-head attention weighting, `multi_head_split_head`'s per-head scale, and the two FFN linear layers — around sublayer outputs computed elsewhere |
| `normalization_layers` | a broad reference catalog of normalization formulas beyond LayerNorm and RMSNorm — batch (inference), instance, group, spectral, and weight norm, AdaLN, and DeepNorm's residual-scaling alpha — each taking precomputed mean/variance/statistics rather than reducing over a buffer itself |
| `nn_layers` | general, non-transformer-specific neural-net building blocks — a dense (fully connected) layer, four activations, MSE and binary cross-entropy loss, dropout, a batch norm that computes its own mean/variance, leaky ReLU, and Xavier/Glorot weight initialization |
| `fused_kernels` | single-expression fusion patterns — attention score + scale + mask, softmax + mask, layernorm + scale/shift, matmul + bias + ReLU/GELU, RoPE rotation fused into a QK score, residual + norm, dropout + residual — plus `kernel_fusion_savings`, an estimate of the HBM traffic fusion avoids |

## How this relates to the production kernel families

This is not the same content as [MLP block kernels](mlp-block-kernels.md) or [Normalization
kernels](normalization-kernels.md), and it is not a duplicate under a different name either. Those
two pages document `mlpk.*` and `normk.*`: tensorized, row-major, `[n_tok][d_model]`-shaped kernels
with backward passes, gradient checks, status-code refusal, and a shared work-budget contract —
production code built to be timed against a real `torch` layer. The four modules here have none of
that: no status codes, no `n_rows`/`n_cols` shape arguments, no backward. `normalization_layers`
even supplies the exact functions [`normalization-kernels.md`](normalization-kernels.md) calls out
by name as the "frozen elementwise kernels" that `normk.layernorm` and `normk.rmsnorm` build their
tensorized reductions on top of — `normalization_layers.layer_norm` and `normalization_layers.rms_norm`
are literally those two functions, taking a mean/variance (or RMS) that the caller already computed.
What `normalization_layers` adds beyond that overlap is eight more formulas `normk` has no equivalent
for at all: batch/instance/group/spectral/weight norm, AdaLN, and DeepNorm's alpha.
`transformer_blocks` and `fused_kernels` have no equivalent module in the `mlpk`/`normk`/`attnk`
families either — nothing there assembles a residual-plus-norm pattern, applies a causal mask to a
single logit, or writes out a fused matmul-bias-activation expression as one function. `nn_layers` is
narrower in scope than either: it is not transformer-specific at all, and its `batch_norm` computes
mean and variance from whatever vector it is given, which is a different operation from
`normalization_layers.batch_norm_inference`'s frozen running statistics (see below).

## Assembling a block, one scalar at a time

`transformer_blocks.residual_connection` and `pre_norm_residual`-style adds are the simplest thing
in the family — `x + sublayer_out` — but several of the higher-level functions carry a parameter
their formula doesn't actually use, because the docstring documents where the call sits in a larger
pipeline even though the function itself only computes the final step:

```python
runtime.execute("transformer_blocks", "pre_norm", [1.5, 0.9, -0.3])["result"]
# 1.2 -- x + sublayer_out; norm_out (the LayerNorm(x) that fed the sublayer) is accepted
# and documented but never appears in the return expression
```

`pre_norm(x, norm_out, sublayer_out)`'s docstring is `y = x + sublayer(LayerNorm(x))` — `norm_out`
is that `LayerNorm(x)`, already consumed by whatever computed `sublayer_out` upstream, so the
residual-add step this function performs genuinely has no arithmetic use for it. The same pattern
appears in `multi_head_split_head(embedding_val, head, head_dim, d_model)`: the docstring describes
slicing a projected embedding to `[head * head_dim : (head+1) * head_dim]`, but the function returns
only `embedding_val / sqrt(head_dim)` — `head` and `d_model` are validated for sign (`d_model <= 0`
refuses) but never used to select anything, because the actual per-head slice has to happen at the
call site; this function only supplies the attention scale factor.

`post_norm` is a sharper version of the same gap. Its docstring is `y = LayerNorm(x + sublayer(x))`,
but the body is:

```python
runtime.execute("transformer_blocks", "post_norm", [1.0, 0.5, 2.0, 0.1])["result"]
# 3.1 -- (x + sublayer_out) * norm_scale + norm_bias == (1.0 + 0.5) * 2.0 + 0.1
```

There is no mean subtraction and no variance division anywhere in it — the function's own docstring
says so directly ("Simplified: applies residual then a single scale/shift" / "partial — caller
handles full norm"). `norm_scale` and `norm_bias` are named for LayerNorm's γ and β, but what this
function computes is residual-add followed by a plain affine transform; the normalization half of
"post-norm" has to be done by the caller, either before this call (passing an already-normalized
`sublayer_out`) or with `normalization_layers.layer_norm` on the result.

`causal_mask_logit` and `gated_feedforward` are the two functions in this module with real
branching logic:

```python
runtime.execute("transformer_blocks", "causal_mask_logit", [2.5, 3.0, 5.0])["result"]
# -1000000000.0 -- key_pos (5) > query_pos (3): a future token, masked to -1e9
runtime.execute("transformer_blocks", "causal_mask_logit", [2.5, 5.0, 3.0])["result"]
# 2.5 -- key_pos (3) <= query_pos (5): a past-or-current token, unchanged

runtime.execute("transformer_blocks", "gated_feedforward", [3.0, 2.0])["result"]
# 5.284782467867295 -- SwiGLU: SiLU(gate) * x, SiLU(2.0) = 2.0 / (1 + exp(-2.0))
```

`feedforward_layer1` and `feedforward_layer2` are both a plain `x * weight + bias` — the first
layer's own docstring says to "apply activation (GELU/SiLU) outside this function," which is exactly
what `fused_kernels.fused_matmul_bias_gelu` below does in one step instead of two.

## The wider normalization catalog

`normalization_layers.layer_norm`, `rms_norm`, `batch_norm_inference`, `group_norm_scale`, and
`instance_norm` share one shape — `(x - center) / sqrt(spread + eps) * gamma + beta`, or, for
RMSNorm, the same without the mean subtraction — differing only in what `center` and `spread` mean
for that variant:

```python
runtime.execute("normalization_layers", "layer_norm", [2.0, 1.5, 0.8, 1.2, 0.1, 1e-5])["result"]
# 0.7708162006617845 -- (2.0 - 1.5) / sqrt(0.8 + 1e-5) * 1.2 + 0.1

runtime.execute("normalization_layers", "batch_norm_inference", [5.0, 4.0, 2.25, 1.0, 0.0, 1e-5])["result"]
# 0.6666651851901234 -- (5.0 - running_mean) / sqrt(running_var + eps) * gamma + beta
```

`adaptive_layer_norm` (AdaLN, from diffusion transformers) layers a conditioning-derived scale and
shift on top of a plain LayerNorm: `ln * (1 + gamma_cond) + beta_cond`, where `ln` itself is
`(x - mean) / sqrt(variance + eps)` with no separate γ/β of its own:

```python
runtime.execute("normalization_layers", "adaptive_layer_norm", [2.0, 1.0, 1.0, 0.5, 0.2, 1e-5])["result"]
# 1.6999925000562495 -- ln = 0.9999950000374997; ln * (1 + 0.5) + 0.2
```

`weight_norm_magnitude` and `spectral_norm_estimate` are the two functions here that are not a
per-element normalization at all. `weight_norm_magnitude(weight_vector_norm, g_param)` returns
`g_param / weight_vector_norm` — the reparameterization weight-norm splits a weight vector into a
direction and a learned magnitude `g`; a non-positive `weight_vector_norm` is refused to `0.0` rather
than dividing by zero. `spectral_norm_estimate(sigma_prev, u_dot_w_v)` is a pure pass-through — it
returns `u_dot_w_v` unchanged, `sigma_prev` unused — because in real power iteration the *caller*
already computed the new estimate as `u^T W v`; this function exists to name that value at the call
site, not to compute anything.

`deep_norm_alpha(n_layers)` is worth checking against its own docstring:

```python
runtime.execute("normalization_layers", "deep_norm_alpha", [6.0])["result"]
# 1.8612097182041991 -- (2 * 6) ** 0.25
```

The docstring reads "alpha = (2N)^(1/4) for encoder, (8N)^(1/4) for decoder," but the function has
no encoder/decoder argument and only ever computes `exp(log(2 * n_layers) / 4)`, i.e. `(2N)^(1/4)` —
the encoder form. A caller that needs the decoder form has to multiply `n_layers` by 4 before calling
(since `(8N)^(1/4) == (2 * 4N)^(1/4)`), because the function itself has no branch that produces it.

## `batch_norm` means two different things across these two modules

`nn_layers.batch_norm(x, gamma, beta)` and `normalization_layers.batch_norm_inference(x,
running_mean, running_var, gamma, beta, eps)` are not the same operation despite the shared name.
`normalization_layers.batch_norm_inference` is the textbook inference-time BN: frozen running
statistics computed during training, passed in as arguments, never touching the current input's own
mean or variance. `nn_layers.batch_norm` computes its own mean and variance from whatever vector `x`
it is handed:

```python
x = [1.0, 2.0, 3.0, 4.0]
runtime.execute("nn_layers", "batch_norm", [x, 1.0, 0.0])["result"]
# [-1.3416407811333109, -0.44721359371110364, 0.44721359371110364, 1.3416407811333109]
# mean=2.5, variance=1.25, std=sqrt(1.25 + 1e-8); standardizes THIS vector, not a batch statistic
```

Whether that is a real batch norm depends entirely on what axis the caller packs into `x`: passed
one feature's values across a batch, it behaves like batch norm; passed one sample's activations
across features, the same formula is doing what LayerNorm does. The function does not know or care
which — it standardizes whatever list it is given, with a hardcoded `eps = 1e-8` that isn't a
parameter at all (unlike every `eps` in `normalization_layers`, which is always caller-supplied).

## General NN primitives, not transformer-specific

`nn_layers` is where a dense layer, the standard activation and loss zoo, and weight init live —
none of it assumes an attention mechanism exists:

```python
inp = [1.0, 2.0, 3.0]
weights = [[1.0, 0.0, 1.0], [0.0, 1.0, 1.0]]   # 2 outputs x 3 inputs
bias = [0.5, -0.5]
runtime.execute("nn_layers", "dense_forward", [inp, weights, bias])["result"]
# [4.5, 4.5] -- output[i] = bias[i] + sum_j(weights[i][j] * input[j])

runtime.execute("nn_layers", "mse_loss", [[1.0, 2.0, 3.0], [1.5, 1.5, 2.5]])["result"]
# 0.25 -- mean((predicted - actual)^2)

runtime.execute("nn_layers", "cross_entropy_loss", [[0.9, 0.1, 0.8], [1.0, 0.0, 1.0]])["result"]
# 0.14462152754328741 -- binary cross-entropy, clamped to [1e-15, 1-1e-15] before log()
```

`init_weights_xavier(n_in, n_out)` draws `U(-limit, limit)` with `limit = sqrt(6 / (n_in + n_out))`
— for `n_in = n_out = 4`, `limit = 0.8660254037844386` — and clamps both dimensions to
`MAX_NN_DIM = 1024` before allocating, so a wire-supplied `n_in = 10_000_000` produces a bounded
`1024`-wide matrix instead of an allocation bomb, rather than refusing outright. `nn_layers.dropout`
is the one function in this whole family that is not deterministic given its inputs: it calls
`std.random.random_float64()` internally to decide which elements to zero, so two calls with
identical arguments produce different output. `transformer_blocks.dropout_scale` and
`fused_kernels.fused_dropout_residual` are the deterministic counterparts — both take the keep/drop
decision (`is_kept`) as an argument rather than sampling it, so they are pure functions of their
inputs; whatever samples the mask is the caller's responsibility.

## Fusion patterns as single expressions

Every function in `fused_kernels` is what a hand-written fused kernel body actually computes — two
or three ordinary operations folded into one expression so an intermediate value never round-trips
through memory:

```python
# score = q*k/sqrt(head_dim), masked additively -- QK^T scale and causal mask in one expression
runtime.execute("fused_kernels", "fused_attention_score", [0.8, 1.2, 64.0, -1e9, 0.0])["result"]
# 0.12 -- unmasked: 0.8 * 1.2 / sqrt(64)

# linear + bias + GELU (tanh approximation) in one expression
runtime.execute("fused_kernels", "fused_matmul_bias_gelu", [1.2, -0.5])["result"]
# 0.5305701347045902 -- pre-activation x = 0.7; GELU_tanh(0.7)
```

`fused_matmul_bias_gelu` uses the same tanh-approximation GELU documented in [MLP block
kernels](mlp-block-kernels.md#two-gelu-conventions-and-neither-is-the-default): at `x = 0.7`, the
erf-form reference is `0.5306254434438489`, a gap of about `5.5e-5` — small, and in the same
direction and rough magnitude as the gap that page measures between the two GELU conventions at
other points on the curve, for the same reason (tanh is an approximation to erf, not an identical
formula).

`kernel_fusion_savings(n_fused_ops, bytes_per_intermediate, n_elements)` turns the "fusion avoids a
memory round-trip" claim into a number: `(n_fused_ops - 1) * bytes_per_intermediate * n_elements` —
one op has nothing to fuse with, so `n_fused_ops <= 1.0` returns `0.0` rather than a negative byte
count:

```python
runtime.execute("fused_kernels", "kernel_fusion_savings", [4.0, 4.0, 1024.0])["result"]
# 12288.0 -- (4 - 1) intermediate round-trips avoided * 4 bytes * 1024 elements
```

## Refusal and edge-case behavior

None of these four modules uses status codes the way `attnk`/`mlpk`/`normk` do; each guards its own
handful of division-by-zero and out-of-range cases inline, returning `0.0` or an empty list instead:

* `transformer_blocks.dropout_scale(x, keep_prob)` and `multi_head_split_head(..., head_dim,
  d_model)` both return `0.0` when their divisor guard trips (`keep_prob <= 0.0`; `head_dim <= 0.0
  or d_model <= 0.0`) rather than dividing by zero.
* `normalization_layers.weight_norm_magnitude(weight_vector_norm, g_param)` returns `0.0` when
  `weight_vector_norm <= 0.0` for the same reason.
* `fused_kernels.fused_dropout_residual` and `fused_softmax_mask` both treat "not kept" / "not valid"
  as a short-circuit: the first returns `x` unchanged (the sublayer contributes nothing), the second
  returns `0.0` (a masked position has zero softmax weight), in each case skipping the division
  entirely rather than computing it and discarding the result.
* `nn_layers.dense_forward`, `softmax_layer`, `mse_loss`, and `cross_entropy_loss` all check their
  list arguments' lengths before indexing: a `bias` shorter than the weight-row count, a weight row
  wider than `input`, an empty `x` passed to `softmax_layer`, or a mismatched `predicted`/`actual`
  pair all return an empty list or `0.0` instead of reading past the end of a `List` — in Mojo, that
  read is an **uncatchable** abort that kills the whole worker process, not a catchable exception, so
  the check has to run before the read, not after.

## Verification

`mojo/tests/libs/test_transformer_blocks.mojo`, `test_normalization_layers.mojo`,
`test_nn_layers.mojo`, and `test_fused_kernels.mojo` are auto-generated coverage smoke tests: each
calls every function once on a shared, arbitrary fixture value (`0.5` for every scalar argument, a
fixed five-element list for vector arguments) and checks only that the result is finite (for
scalars) or non-empty/callable-without-error (for lists) — none of the four pins a specific numeric
output. The worked examples above were hand-traced against the real formulas in
`mojo/engine/transformer_blocks.mojo`, `normalization_layers.mojo`, `nn_layers.mojo`, and
`fused_kernels.mojo`, and every number given can be reproduced by re-running the same arithmetic in
plain Python.

**Next:** the tensorized, backward-capable siblings this family sits below —
[MLP block kernels](mlp-block-kernels.md) for gated feed-forward and embedding lookup, and
[Normalization kernels](normalization-kernels.md) for LayerNorm/RMSNorm with real reductions and
gradient checks — or browse the [runtime library catalog](runtime-library-catalog.md) for every
module and function.
