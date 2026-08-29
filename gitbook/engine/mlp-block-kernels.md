---
icon: cubes
description: Gated feed-forward activations (SwiGLU and both GEGLU conventions), token embedding lookup, and the shared feed-forward/vocabulary shape contract, forward and backward, in flat row-major layouts.
---

# MLP block kernels

Four kernel modules for the arithmetic outside a transformer's attention block: the embedding
table lookup that turns an integer token id into a vector, the two-projection gated activation
that makes a feed-forward layer more than a matmul, and the shape/status contract both call
first. `mlpk.activation` and `mlpk.gated_ffn` compute the *same* per-element formulas from two
different drivers on purpose — one is a tensorized, gradient-checked reference; the other is a
fused, SIMD, band-parallel kernel built to be timed against a `F.silu(gate) * up`-style torch
expression, and its own test file cross-checks every one of its four gate kernels against the
first. All four modules operate on flat, row-major `[token][dim]` buffers — there is no tensor
library underneath, the shape is the calling convention.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("mlpk.contract", "mlp_vocab_check", [1024, 151936, 4096])["result"]
# 390 — MLP_OK: a real Qwen3 vocabulary, 151,936 rows x 4096 dims, fits the work budget

runtime.execute("mlpk.activation", "mlp_gelu_erf", [1.0])["result"]
# 0.8413447460685429 — the erf-convention GELU, matching a correctly-rounded reference to 1e-7
```

## The modules

| Module | What it does |
| --- | --- |
| `mlpk.contract` | shape/scalar validation for feed-forward and vocabulary dimensions, status and backend-name lookups, and the worker-count clamp every other module in this family calls first |
| `mlpk.activation` | the gradient-checked reference: SwiGLU and both GEGLU variants (tanh and erf-form), forward and backward, over a real `[n_tok][d_ff]` buffer, plus `mlp_gelu_agreement`, which measures the gap between the two GELU conventions rather than picking one |
| `mlpk.embedding` | token embedding table lookup (gather) and its scatter-add gradient, with every id bounds-checked before a single read — an out-of-range id is an unrecoverable worker abort in Mojo, not a catchable exception |
| `mlpk.gated_ffn` | fused, SIMD, band-parallel gate kernels built to be benchmarked against torch, plus `swiglu_ffn_block` — a full three-GEMM SwiGLU feed-forward layer |

## Two GELU conventions, and neither is the default

`activations.mojo` (the frozen, pre-existing kernel tree) has three GELU spellings — `gelu`,
`gelu_fast`, `gelu_new` — and every one of them is the *tanh* approximation, including `gelu`,
whose own docstring opens "Gaussian Error Linear Unit (exact)" over a tanh body. Measured against
the erf form (`x * 0.5 * (1 + erf(x / sqrt(2)))`) over `[-4, 4]`, the gap is **4.73e-4 at x =
2.7** — small enough to look like a rounding difference, large enough that Hugging Face treats
the two as different activations (`hidden_act: "gelu"` means erf; `"gelu_new"` and
`"gelu_pytorch_tanh"` mean tanh). A checkpoint trained under one and served under the other
doesn't error, it just gets quietly worse.

`mlpk.activation.mlp_gelu_erf` supplies the missing erf form as its own contract, and
`mlp_gelu_agreement` reports the gap as a number instead of resolving it:

```python
agreement = runtime.execute("mlpk.activation", "mlp_gelu_agreement", [-4.0, 4.0, 2001])["result"]
agreement["v"][0], agreement["v"][2]
# (~4.73e-4, False) — the gap the test pins to lie strictly between 4e-4 and 5e-4, and
# within_tolerance is False BY DESIGN: these are two different activations, not two roundings
```

Golden values for `mlp_gelu_erf`, checked against a correctly-rounded double reference to 1e-7:

| x | `mlp_gelu_erf(x)` |
| --- | --- |
| -2.0 | -0.04550026389635842 |
| -1.0 | -0.15865525393145707 |
| 0.0 | 0.0 |
| 1.0 | 0.8413447460685429 |
| 2.0 | 1.9544997361036416 |

{% hint style="info" %}
**`mlp_activation_known` has no default.** An unrecognized activation selector is refused
(`gated_ffn_fwd_flat(..., kind=99)` returns `MLP_ERR_UNKNOWN_ACTIVATION`, 397) rather than falling
back to SwiGLU. Defaulting would be right for Llama-family checkpoints and silently wrong for
every GELU one — the same reasoning that keeps `mlp_gelu_erf` from being named `*_exact`:
`std.math.erf` on this toolchain is itself only accurate to about 2e-8 (at x=2.0 it returns
`0.9953222865616017` against a correctly rounded `0.9953222650189527`), so the erf path is named
for its *convention*, not for bit-parity it doesn't have.
{% endhint %}

## A gather has to prove every id is in range before it reads one

`embedding_fwd_flat` reads `weight[id * d_model + j]`. In Mojo, a read past the end of a `List` is
an **uncatchable** bounds assertion — it aborts the whole worker process, not just the request,
and no `try`/`except` above it helps. So every id is checked against `vocab` before a single read,
and an out-of-range id gets its own status rather than being silently clamped (a clamped id would
train the wrong row and the run would complete, which is worse than an error).

```python
weight = [float(i) for i in range(24)]   # a 6-row x 4-dim table, values 0..23
ids = [2, 0, 2, 5]

out = runtime.execute("mlpk.embedding", "embedding_fwd_flat", [weight, ids, 4, 6, 4])["result"]
out["v"][0][0:4]
# [8.0, 9.0, 10.0, 11.0]    — token 0 -> id 2 -> row 2 -> weight[8:12]
out["v"][0][12:16]
# [20.0, 21.0, 22.0, 23.0]  — token 3 -> id 5 -> row 5, the last row
```

The backward is a scatter-add — several tokens can map to the same vocabulary row — and it
accumulates in the row's rightful order regardless of how many workers ran, by splitting the work
by *column* rather than by token:

```python
dy = [1.0] * 16   # n_tok(4) * d_model(4)

grad = runtime.execute("mlpk.embedding", "embedding_bwd_flat", [dy, ids, 4, 6, 4])["result"]
grad["v"][0][8], grad["v"][0][0], grad["v"][0][20]
# (2.0, 1.0, 1.0) — row 2 accumulated twice (ids 2 and 2), rows 0 and 5 once each
grad["v"][1]
# 3 — n_touched counts DISTINCT rows (3), not tokens (4)
```

Refusals, matched to the exact call shape the generated A-Z conformance suite makes (a
five-element list and `5` for every `Int` argument — here, a request to read `weight[24]` from a
5-element buffer):

```python
runtime.execute("mlpk.embedding", "embedding_fwd_flat",
                [[0.5] * 5, [5] * 5, 5, 5, 5])["result"]
# {"v": [[], 0, 0, 392]} — MLP_ERR_LENGTH_MISMATCH, refused before a single read

runtime.execute("mlpk.embedding", "embedding_fwd_flat", [weight, [6], 1, 6, 4])["result"]
# {"v": [[], 0, 0, 396]} — MLP_ERR_TOKEN_OUT_OF_RANGE: id == vocab (the classic off-by-one),
# refused rather than clamped to the last row
```

## The reference and the fused kernel have to agree

`mlpk.gated_ffn`'s four gate kernels (`swiglu_gate`, `geglu_tanh_gate`, `geglu_tanh_fast_gate`,
`geglu_erf_gate`) exist because a fused, one-array-write SIMD driver is what a real feed-forward
layer needs to be timed against torch — `activations.swiglu` alone is scalar algebra, not
something you can put opposite `F.silu(gate) * up`. Its own test file cross-checks all four
against `mlpk.activation.gated_ffn_fwd_flat`'s reference: bit-identical for SwiGLU, and ~1e-13
apart for the two GELU-based gates, where the gap is a benign left-to-right association order
(`0.5 * g * (1 + f)` here vs `(0.5 * (1 + f)) * g` there) — the same order-of-operations rounding
the GELU convention table above documents between `gelu_fast` and `gelu_new`.

```python
runtime.execute("mlpk.gated_ffn", "gate_bytes_moved", [500])["result"]
# 12000.0 — read gate + read up + write out, 24 bytes/element x 500 elements
```

Band-splitting across workers is a scheduling choice, not a second computation — a
`swiglu_gate` call run serially and one run auto-parallel produce bit-identical output:

```python
big_n = 1 << 17   # 131072, above the ~32k-element threshold where parallelizing starts to pay off
# gate_vals, up_vals: any two float64 lists of length big_n
serial = runtime.execute("mlpk.gated_ffn", "swiglu_gate", [gate_vals, up_vals, big_n, 1])["result"]
auto = runtime.execute("mlpk.gated_ffn", "swiglu_gate", [gate_vals, up_vals, big_n, 0])["result"]

serial["v"][3], auto["v"][3]        # backend_used
# (0, 1) -> "cpu_simd", "cpu_simd_parallel"
serial["v"][0] == auto["v"][0]
# True
```

`swiglu_ffn_block` composes three `gemm.blocked.sgemm_flat` projections around the gate into one
full layer, and reports the FLOP count as it goes — worked out by hand from the module's own
formula for a 6-token, `d_model=5`, `d_ff=8` block:

```python
# x: 6 tokens x 5 d_model; wg/wu: 5 x 8 gate/up projections; wd: 8 x 5 down projection
blk = runtime.execute("mlpk.gated_ffn", "swiglu_ffn_block",
                      [x, wg, wu, wd, 6, 5, 8])["result"]
blk["v"][1], blk["v"][2]
# (6, 5) — rows = tokens, cols = d_model: the block's output shape
blk["v"][4]
# 1584.0 == 2*6*5*8*2 (two projections in) + 2*6*8*5 (the projection out) + 3*6*8 (the gate)
```

## The count-relation guard shows up in every module here

`mlp_pair_ok` and `mlp_block_dims_ok` exist for the same reason `embedding`'s bounds check does: a
caller-supplied element count `n` greater than a buffer's real length is exactly the shape of bug
that fires an uncatchable bounds assertion elsewhere in this tree rather than a catchable
exception. Both are refused, not crashed on:

```python
short = [1.0, 2.0, 3.0]
runtime.execute("mlpk.gated_ffn", "swiglu_gate", [short, short, 100, 0])["result"]
# {"v": [[], 0, 0, 0, 0.0, 392]} — MLP_ERR_LENGTH_MISMATCH: n=100 past a 3-element buffer

runtime.execute("mlpk.gated_ffn", "swiglu_gate", [[0.5] * 5, [0.5] * 5, 5, 5])["result"]
# status 390 (MLP_OK) — n == the real buffer length succeeds; the guard is exact, not merely strict
```

## Composing into a real forward pass

Neither this family nor `attnk` assembles a transformer block by itself. That composition is
exercised end to end in `benchmarks/llm_smoke/qwen3_forward.mojo`, which runs a real
Qwen3-0.6B-Base checkpoint through the published kernels and checks the result against the
reference model's own forward pass. Every embedding gather in it is
`mlpk.embedding.embedding_fwd_flat`; every gated-FFN activation is
`mlpk.activation.gated_ffn_fwd_flat`; every RMSNorm (including Qwen3's QK-Norm) is
`normk.rmsnorm.rmsnorm_fwd_flat`; every rotary embedding and attention call go through
`attnk.rope`/`attnk.mask`/`attnk.sdpa`; every projection is `gemm.blocked.sgemm_flat`. The one
piece none of those packages already had — an elementwise residual add over two whole buffers,
needed to wire the pieces into layers — is `llmk.residual.residual_add_flat`, added for exactly
this composition and documented alongside it in `mojo/engine/llmk/__init__.mojo`.

## Verification

* `test_mlpk_contract.mojo` pins the 390-399 status range against tensorx (300-319), gemm
  (320-339), attnk (360-379) and normk (380-389) so no code can collide with a neighboring
  package, confirms `mlp_work_fits` catches a three-factor product that wraps 64 bits, and checks a
  real Qwen3-8B feed-forward shape (2048 x 4096 x 12288) and a real Qwen3 vocabulary (151,936 x
  4096) both pass.
* `test_mlpk_activation.mojo` pins the GELU convention gap, checks the erf form against five
  correctly-rounded golden points, and proves each gradcheck can *fail*: it recomputes the SwiGLU
  gate gradient with the term a reader typically drops (`sigmoid(g)` alone, missing the
  `g*(1-s)` product-rule term) and confirms the truncated version moves the gradient by more than
  1e-3 — a gradcheck that can't fail is decoration.
* `test_mlpk_embedding.mojo` is built around the abort hazard: it asserts the exact A-Z
  conformance-suite call shape is refused rather than aborting the worker, that an id equal to
  `vocab` is refused rather than clamped, and that a 4096-token scatter-add is bit-identical to a
  serial reference regardless of worker count.
* `test_mlpk_gated_ffn.mojo` cross-checks all four gate kernels against `mlpk.activation`'s
  reference, confirms serial and auto-parallel `swiglu_gate` produce identical output, and runs a
  full `swiglu_ffn_block` through three real GEMMs.

**Next:** see how these compose with rotary embeddings and masked attention in
[Attention kernels](attention-kernels.md), or browse the [engine catalog](catalog.md).
