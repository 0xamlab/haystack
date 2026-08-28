---
icon: layer-group
description: Scaled dot-product attention, flash attention, causal/sliding-window masking, RoPE, and analytic backward gradients, in flat row-major layouts with grouped-query support.
---

# Attention kernels

Seven kernel modules for the arithmetic underneath a transformer's attention block: a materialized
reference implementation, a memory-efficient tiled/flash path that has to prove it agrees with that
reference, the masks that make attention causal or windowed or packed, rotary position embeddings,
and the analytic gradients for training. All operate on flat, row-major `[token][head][dim]` buffers
with grouped-query attention (`h_kv < h_q`, each KV head serving `h_q / h_kv` query heads) — there is
no tensor library underneath, the shape is the calling convention.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("attnk.contract", "attn_dims_check", [1, 2, 1, 4, 4, 8])["result"]
# 360 — ATTN_OK: 2 query heads, 1 KV head, group size 2, divides evenly

runtime.execute("attnk.rope", "rope_inv_freq", [4, 10000.0])["result"]
# [1.0, 0.01] — one inverse frequency per dimension pair, theta ** (-2i / head_dim)
```

## The modules

| Module | What it does |
| --- | --- |
| `attnk.contract` | shape/scalar validation, status and backend name lookups, and the work-budget checks every other module in this family calls first |
| `attnk.sdpa` | scaled dot-product attention, materialized — the slow, obviously-correct reference everything else is measured against |
| `attnk.flash` | the tiled flash-attention forward pass, plus `flash_agrees_with_sdpa`, which runs both and checks they agree |
| `attnk.mask` | causal, sliding-window, padding, and block-diagonal (packed-sequence) additive bias construction |
| `attnk.rope` | rotary position embeddings — inverse frequencies, cos/sin tables (including the Llama-3 frequency scaling), and the forward/inverse rotation |
| `attnk.tiled` | the production forward paths (`tiled`, `direct`, and a deliberately-`unstable` one for comparison), plus FLOP counting and a reference-delta diagnostic |
| `attnk.backward` | analytic gradients for Q/K/V, plus a numerical gradient check against them |

## A materialized reference, worked by hand

`sdpa_forward_flat` takes `q`, `k`, `v` as flat `[token][head][dim]` buffers and an additive `bias`
shared across heads, and returns both the output and the per-row log-sum-exp:

```python
q = [1.0, 0.0, 0.0, 1.0]        # 2 tokens x 1 head x 2 dims
k = [1.0, 0.0, 0.0, 1.0]
v = [10.0, 20.0, 30.0, 40.0]

out = runtime.execute("attnk.sdpa", "sdpa_forward_flat",
                      [q, k, v, [], 2, 2, 1, 1, 2, 0.5, False])["result"]
out["v"][0]
# [17.550813375961578, 27.550813375961578, 22.449186624038415, 32.44918662403842]
out["v"][1]
# [0.9740769843439637, 0.9740769843439637] — lse per (head, query) row
```

Token 0's query is orthogonal to token 1's key and parallel to token 0's key, so the two raw
scores before softmax are `[0.5, 0.0]` — worked out independently in plain Python (`exp`/`log`,
no library), the softmax weights are `[0.6224593312, 0.3775406688]` and the weighted average of
`v` matches the kernel's output to the last representable bit both implementations share; the
handful of differing low bits are Mojo's own transcendental functions rounding a fraction of an
ULP differently from CPython's, not a different answer.

## Flash attention has to prove it agrees with the reference

`flash_agrees_with_sdpa` runs the same inputs through both the tiled flash kernel and
`sdpa_forward_flat`, then compares output and log-sum-exp against a tolerance built from each
row's own magnitude:

```python
agreement = runtime.execute("attnk.flash", "flash_agrees_with_sdpa",
                            [q, k, v, [], 2, 2, 1, 1, 2, 0.5, False, 1])["result"]
agreement["v"]
# [3.552713678800501e-15, 0.0, 1.0623530147548535e-12, True, 4, 360]
```

The third element is `True` — flash and the reference agree to `1e-15`, not because they compute
attention the same way (flash never materializes the full `n_tok_q x n_tok_k` score matrix; the
reference does, on purpose, so it has something simple to be wrong against) but because both
implementations are computing the same softmax-weighted average under different accumulation
orders. The log-sum-exp comparison is the sharper of the two checks — it depends on every score in
the row, where the output is a weighted average that can hide two compensating errors.

## A causal mask is a bias, not a boolean

```python
mask = runtime.execute("attnk.mask", "mask_causal_flat", [3, 3, 0])["result"]
mask["v"][0]
# [0.0, -1000000000.0, -1000000000.0,
#  0.0, 0.0, -1000000000.0,
#  0.0, 0.0, 0.0]
```

A flat `3x3` additive bias: query 0 can only see key 0, query 1 sees keys 0-1, query 2 sees all
three. Adding this to the raw scores before softmax — rather than zeroing weights afterward — is
what lets `sdpa_forward_flat`'s own `bias` argument carry causal, sliding-window, padding, and
packed-sequence masking through the identical code path without a separate masked variant of the
kernel.

## A rotation the kernel can invert to check itself

`rope_apply_flat` and `rope_apply_inverse_flat` are exact inverses of each other — a property that
catches a wrong pairing, a wrong sign, or a wrong table index all at once, which comparing against a
handful of expected numbers would not:

```python
table = runtime.execute("attnk.rope", "rope_table", [4, 2, 10000.0])["result"]
cos_t, sin_t = table["v"][0], table["v"][1]

x = [1.0, 2.0, 3.0, 4.0]        # 1 token x 1 head x 4 dims
rotated = runtime.execute("attnk.rope", "rope_apply_flat",
                          [x, cos_t, sin_t, 1, 1, 4, [1], False])["result"]
rotated["v"][0]
# [-1.9841106485555495, 1.959900667493101, 2.4623779024123156, 4.019799668336732]

back = runtime.execute("attnk.rope", "rope_apply_inverse_flat",
                       [rotated["v"][0], cos_t, sin_t, 1, 1, 4, [1], False])["result"]
back["v"][0]
# [1.0000000000062432, 1.999999999990699, 2.9999999999940625, 4.000000000003489]
```

`x` comes back to eleven decimal places, which is exactly what "negate the rotation angle" should
produce: a rotation is orthogonal, so applying it and then its inverse is the identity up to
floating-point roundoff, on any input, any head count, any layout. `position` is passed per token
rather than assumed equal to the token's index for exactly this reason — a packed batch restarts
positions at each document boundary, and a kernel that assumed otherwise would rotate the second
document as if it continued the first.

{% hint style="info" %}
**Interleaved vs. non-interleaved pairing is a real choice, not a detail.** `rope_apply_flat`'s
`interleaved` flag selects which two dimensions form a rotation pair: GPT-J pairs adjacent
dimensions (`2i, 2i+1`); GPT-NeoX (and the example above) pairs a dimension with the one half a
head-width away (`i, i + head_dim/2`). Loading a checkpoint trained with one convention and rotating
with the other produces output that runs without error and is simply wrong.
{% endhint %}

## Backward gradients check themselves against a numerical estimate

```python
grad = runtime.execute("attnk.backward", "attn_bwd_gradcheck_flat",
                       [q, k, v, 2, 2, 1, 1, 2, 0.5, 0.0001])["result"]
grad["v"]
# [9.135439071883411e-10, 1.140014848623605e-07, True, 4, 360]
```

`attn_bwd_gradcheck_flat` perturbs each input by the given step, re-runs the materialized reference
forward pass, and compares the resulting finite-difference gradient against `sdpa_bwd_flat`'s
analytic one — `True` here means the two agree to within the precision a `1e-4` step can resolve.
This is the same self-checking shape as `flash_agrees_with_sdpa` above: rather than asserting a
handful of hand-computed gradient values, the kernel carries its own independent way of being wrong.

## See also

* [Data integrity and encoding](data-integrity-and-encoding.md) — the same "recompute and compare"
  verification shape, applied to HMAC and Merkle proofs instead of gradients
* [Declared capabilities](capabilities.md) — what each kernel says about determinism, seeds and cost
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
