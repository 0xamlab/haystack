---
icon: brain
description: Scalar reference formulas for scaled dot-product attention, ten named sparse/long-context attention techniques, flash attention's online-softmax building blocks, and five families of positional encoding.
---

# Attention variant kernels

Four modules that each compute one term of a published attention or positional-encoding formula at
a time — a single `Float64` in, a single `Float64` out, no query/key/value buffer, no shape, no
status code. `transformer_attention` is the plain scaled-dot-product reference (the score, the
softmax weight, the causal mask, the KV-cache footprint); `sparse_attention` covers ten named
sub-quadratic and long-context techniques from the literature (BigBird, Longformer, StreamingLLM,
HyperAttention, linear attention, and others); `flash_attention` exposes the running-max /
running-sum / running-output arithmetic that a tiled flash-attention pass composes, plus paged,
sliding-window, grouped-query and ring-attention formulas; `positional_encoding` covers five ways to
inject position — sinusoidal, RoPE, ALiBi, xPos, and learned. Together they are a calculator for
"what does this paper's equation evaluate to on these numbers", not a production compute path.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("transformer_attention", "scaled_dot_product_attention", [8.0, 64.0])["result"]
# 1.0 — q·k = 8.0, scaled by 1/sqrt(64) = 1/8

runtime.execute("positional_encoding", "alibi_slope", [1.0, 8.0])["result"]
# 0.5 — head 1 of 8 gets ALiBi slope 2^(-8*1/8) = 2^-1
```

## The modules

| Module | What it does |
| --- | --- |
| `transformer_attention` | the scaled dot-product formula and its immediate neighbors, one scalar term at a time — QK score, stable-softmax weight, multi-head split, causal mask, per-weight entropy, KV-cache byte footprint, a flash-style block score, RoPE rotation angle, T5 relative-position bias, and encoder-decoder cross-attention |
| `sparse_attention` | ten named long-context and sub-quadratic attention techniques — local window masking, Longformer global-token scoring, BigBird random block selection, StreamingLLM attention sinks, landmark/retrieval attention, chunked cross-attention, the linear-attention feature map, recurrent memory updates, block-sparse density, and HyperAttention importance sampling |
| `flash_attention` | the online-softmax running state (block max, running normalizer, running output, rescale-on-max-update, final divide) that a tiled flash pass composes, plus paged-KV block scoring, sliding-window masking, block-sparse density, grouped-query-attention head reuse, and ring-attention chunk sizing |
| `positional_encoding` | sinusoidal (Vaswani et al.), RoPE cosine/sine components and their rotation application, ALiBi slopes and additive bias, learned-embedding Xavier init scale, T5-style relative-position buckets, and xPos's position-dependent scale |

## A scalar reference, not a buffer kernel

Every `transformer_attention` function takes the plain numbers a full attention computation would
otherwise produce as intermediates — a dot product, a dimension, a position — and applies exactly
one textbook formula to them:

```python
runtime.execute("transformer_attention", "multi_head_split", [4096.0, 32.0])["result"]
# 128.0 — d_k = d_model / n_heads

runtime.execute("transformer_attention", "causal_mask_value", [5.0, 3.0])["result"]
# 0.0 — key position 3 <= query position 5, attend
runtime.execute("transformer_attention", "causal_mask_value", [3.0, 5.0])["result"]
# -1000000000.0 — key position 5 > query position 3, mask

runtime.execute("transformer_attention", "cross_attention_score", [2.0, 3.0, 64.0])["result"]
# 0.75 — (2.0 * 3.0) / sqrt(64.0)

runtime.execute("transformer_attention", "kv_cache_memory_bytes", [32.0, 32.0, 128.0, 4096.0, 1.0])["result"]
# 2147483648.0 — 2 GiB: 2 (K+V) x 32 layers x 32 heads x 128 d_head x 4096 seq_len x 1 batch x 2 (fp16)
```

`attention_softmax_stable` and `flash_attention`'s running state compute the *same* softmax two
different ways. Take three raw scores `[2.0, 1.0, 3.0]` for one query against three keys — the
row maximum is `3.0` and `sum_exp = exp(2-3) + exp(1-3) + exp(3-3) = 1.5032147244080551`:

```python
runtime.execute("transformer_attention", "attention_softmax_stable", [2.0, 3.0, 1.5032147244080551])["result"]
# 0.24472847105479764 — exp(2.0 - 3.0) / sum_exp, the weight on the first key
```

`attention_entropy(0.24472847105479764, 3.0)` returns `0.34448125552608705` (`-w * log(w)`); the
second argument, `n_keys`, is accepted for the signature the docstring describes as "normalisation
reference" but the current formula never reads it — passing `999.0` instead of `3.0` returns the
identical value.

## Flash attention's running state reproduces the same softmax

`flash_attention`'s five functions are the pieces a blockwise/tiled attention pass calls once per
key (or per key-block) instead of materializing the full score row: `flash_block_max` folds in a
new score, `flash_block_sum_exp` and `flash_block_output` rescale the running normalizer and output
by `exp(old_max - new_max)` whenever the max changes, and `flash_final_normalize` divides at the
end. Feeding the same three scores and values (`v = [10.0, 20.0, 30.0]`) through one key at a time:

```python
# key 0: score 2.0, value 10.0
m = runtime.execute("flash_attention", "flash_block_max", [-1e9, 2.0])["result"]        # 2.0
l = runtime.execute("flash_attention", "flash_block_sum_exp", [0.0, -1e9, 2.0, 2.0])["result"]  # 1.0
o = runtime.execute("flash_attention", "flash_block_output", [0.0, -1e9, 2.0, 1.0, 10.0])["result"]  # 10.0

# key 1: score 1.0, value 20.0 (max unchanged, exp(1-2) = 0.36787944117144233)
m = runtime.execute("flash_attention", "flash_block_max", [m, 1.0])["result"]           # 2.0
l = runtime.execute("flash_attention", "flash_block_sum_exp", [l, 2.0, m, 1.0])["result"]  # 1.3678794411714423
o = runtime.execute("flash_attention", "flash_block_output",
                    [o, 2.0, m, 0.36787944117144233, 20.0])["result"]                  # 17.357588823428847

# key 2: score 3.0, value 30.0 (max updates 2.0 -> 3.0, earlier terms get rescaled)
m = runtime.execute("flash_attention", "flash_block_max", [m, 3.0])["result"]           # 3.0
l = runtime.execute("flash_attention", "flash_block_sum_exp", [l, 2.0, m, 3.0])["result"]  # 1.5032147244080551
o = runtime.execute("flash_attention", "flash_block_output", [o, 2.0, m, 1.0, 30.0])["result"]  # 36.385500076446675

runtime.execute("flash_attention", "flash_final_normalize", [o, l])["result"]
# 24.20512484720024
```

`l` after the third step is exactly `1.5032147244080551` — the same `sum_exp` used in the
`attention_softmax_stable` example above — and the final normalized output, `24.20512484720024`,
matches a plain stable-softmax weighted average of `[10.0, 20.0, 30.0]` computed independently in
Python to every digit shown. That agreement is the whole point of online softmax: the running max
can increase mid-row (as it does at key 2, `2.0 -> 3.0`), which rescales every accumulated term by
`exp(old_max - new_max)` rather than requiring the true row maximum up front.

`grouped_query_attention_scale(32.0, 8.0)` returns `4.0` (each of 8 KV heads serves 4 query heads);
called with `n_kv_heads <= 0.0` it returns `n_query_heads` unchanged rather than dividing by zero.
`ring_attention_chunk_size(seq_len, n_devices)` is `seq_len / n_devices` with `n_devices <= 0.0`
falling back to the full `seq_len` (one device, one chunk). `paged_attention_block_score(query_elem,
key_elem, block_max_key, head_dim)` takes a `block_max_key` argument the docstring describes as
"maximum key element in this block", but the return expression — `(query_elem * key_elem) /
sqrt(head_dim)` — never reads it; the same scaled-dot-product shape as
`transformer_attention.cross_attention_score` and `sparse_attention.longformer_global_score`, both
of which also carry an accepted-but-unused argument (`n_keys` on `attention_entropy`, `is_global` on
`longformer_global_score`) — see the note on this recurring pattern below.

## Ten named techniques, one scalar formula each

`sparse_attention` is a survey, not a single method: each function is a different published
approach to attending to fewer than all `N` keys.

`streaming_llm_sink_score(position, n_sink_tokens, window_size, seq_len)` implements the
StreamingLLM pattern of keeping a handful of initial "sink" tokens plus a sliding recent window —
with `n_sink_tokens=4.0`, `window_size=20.0`, `seq_len=100.0`, positions `0-3` and `80-99` score
`1.0` (attended) and everything in between scores `0.0`:

```python
[runtime.execute("sparse_attention", "streaming_llm_sink_score", [p, 4.0, 20.0, 100.0])["result"]
 for p in (0.0, 3.0, 4.0, 50.0, 79.0, 80.0, 99.0)]
# [1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0]
```

`bigbird_random_block_select(block_id, n_blocks, random_seed, n_random)` picks a block via
`hash = (block_id * 31 + random_seed) mod n_blocks`, selected when `hash < n_random`. It is
deterministic, not random: `bigbird_random_block_select` with `n_blocks=10.0`, `random_seed=7.0`,
`n_random=3.0` selects blocks `3`, `4`, and `5` every time (`hash` values `0`, `1`, `2`) and no
others — the same `(seed, n_blocks, n_random)` always reproduces the same "random" subset, which is
what makes the pattern replayable across a training run rather than a genuine sample.

`hyper_attention_estimate(high_attn_score, random_sample_score, n_high, n_random, seq_len)` combines
an exact score from the important ("heavy hitter") keys with a rescaled estimate from a random
sample of the rest: `hyper_attention_estimate(5.0, 0.1, 32.0, 16.0, 4096.0)` returns
`30.399998412500096` — `5.0 + ((4096 - 32) / (16 + 1e-6)) * 0.1`, the random contribution scaled up
by how many keys one sampled key is standing in for.

`linear_attention_kernel(x)` is the ELU(x) + 1 feature map that replaces softmax to get O(N) linear
attention: `linear_attention_kernel(2.0)` is `3.0` (`x + 1` for `x >= 0`), and
`linear_attention_kernel(-2.0)` is `0.1353352832366127` (`exp(x)`, since `ELU(x) + 1 = exp(x)` for
`x < 0`).

## Five ways to inject position

`positional_encoding` covers the position-encoding families a transformer might use in place of, or
alongside, the causal mask above:

```python
runtime.execute("positional_encoding", "sinusoidal_pe", [1.0, 0.0, 512.0])["result"]
# 0.8414709848078965 — sin(1) for even dim 0 at position 1

runtime.execute("positional_encoding", "alibi_slope", [8.0, 8.0])["result"]
# 0.00390625 — 2^-8, the last head's slope in an 8-head ALiBi stack
runtime.execute("positional_encoding", "alibi_bias", [10.0, 3.0, 0.5])["result"]
# -3.5 — -slope * |10 - 3|

runtime.execute("positional_encoding", "learned_pe_init", [512.0])["result"]
# 0.10825317547305482 — sqrt(6 / d_model), Xavier uniform bound

runtime.execute("positional_encoding", "relative_pe_bucket", [-5.0, 32.0, 128.0])["result"]
# 21.0 — negative side offset (half_buckets=16) plus the exact-range distance 5
```

`rope_cos_component`/`rope_sin_component` here and `transformer_attention.rope_rotation_angle` both
compute a RoPE rotation angle, but take the dimension differently. `rope_rotation_angle(position,
dimension_idx, d_model, base)` takes `dimension_idx` as the already-halved pair index `i` and
divides by `d_model` internally (`theta = position * base^(-2i/d_model)`); `rope_cos_component`/
`rope_sin_component(pos, dim, base)` take the *raw* feature dimension, halve it internally
(`i = dim // 2`), but have **no `d_model` parameter at all** — the angle is `pos * base^(-2i)`, not
`pos * base^(-2i/d_model)`. A caller wanting the standard `d_model`-normalized RoPE angle from
`rope_cos_component` has to fold that normalization into the `base` it passes; `base=10000.0` and
`base=10000.0` do not produce the same angle from the two functions unless `d_model` happens to be
`1.0`. This is a real difference between the two modules' call surfaces, not a documented
convention shared between them — checked directly against both function bodies above, not assumed
from the docstrings, which state the same `θ = pos / base^(2i/d)` formula for both.

## How this relates to `attnk` (Attention kernels)

[Attention kernels](attention-kernels.md) (`attnk.sdpa`, `attnk.flash`, `attnk.mask`, `attnk.rope`,
`attnk.tiled`, `attnk.backward`) operates on flat `[token][head][dim]` buffers with real shapes —
`sdpa_forward_flat`, `flash_forward_flat`, `rope_apply_flat` and friends take explicit
`n_tok_q`/`n_tok_k`/`n_heads`/`head_dim` arguments and a `List[Float64]` of actual Q/K/V data, run a
SIMD-accelerated forward (and, for `attnk.backward`, gradient) pass, and self-check with
`flash_agrees_with_sdpa` and a numerical gradcheck. Grepping both source trees confirms there is no
function-name overlap at all between the two families — `transformer_attention`, `sparse_attention`,
`flash_attention`, and `positional_encoding` (this page) define none of `attnk`'s 20+ public
functions, and vice versa. What this page's four modules provide instead is breadth: named
techniques `attnk` does not implement (BigBird, Longformer, StreamingLLM, HyperAttention, linear
attention, ALiBi, xPos, T5 relative buckets) expressed as single-term scalar formulas rather than
buffer-shaped kernels. Use `attnk` to run an actual forward or backward pass over real tensors; use
this family to evaluate, teach, or prototype one term of a specific published formula, or to
cross-check a value `attnk` produced against the textbook equation it is supposed to implement (as
done for the flash-attention running state above).

## Guardrails return a number, not a status code

None of these four modules has a struct or a status code in the runtime contract — every function
returns a plain `Float64`, and every guard against a degenerate input (a zero dimension, a
non-positive head count) returns a specific fallback value silently rather than an error:

- **Zero or negative dimension → `0.0`.** `scaled_dot_product_attention`, `cross_attention_score`,
  `flash_attention_block_score`, `paged_attention_block_score`, `longformer_global_score`, and
  `chunk_cross_attention_weight` all return `0.0` when their scaling dimension (`d_k`/`head_dim`) is
  `<= 0.0`, rather than dividing by zero or `sqrt` of a negative number.
- **Zero or negative count → a pass-through, not a divide.** `multi_head_split` and
  `grouped_query_attention_scale` return `0.0` and `n_query_heads` respectively when `n_heads`/
  `n_kv_heads <= 0.0`; `ring_attention_chunk_size` returns the untouched `seq_len` when
  `n_devices <= 0.0`.
- **Zero-block density defaults to dense, not sparse.** `sparse_attention_block_density` and
  `block_sparse_density` both return `1.0` — not `0.0` — when their block-count denominator is
  `<= 0.0`, treating "no blocks defined" as "attend to everything" rather than "attend to nothing".
- **Zero or negative scale/base → identity.** `alibi_slope` (`n_heads <= 0.0`), `learned_pe_init`
  (`d_model <= 0.0`), and `xpos_scale` (`base <= 0.0`) all return `1.0` — the no-op value for a
  slope or scale factor — rather than `0.0`, which would zero out every downstream term instead of
  leaving it unchanged.
- **Three functions accept an argument their formula never reads.** `attention_entropy`'s `n_keys`,
  `paged_attention_block_score`'s `block_max_key`, and `longformer_global_score`'s `is_global` are
  all present in the signature and the contract, but none of the three appears in the corresponding
  return expression — passing any value in that slot produces the identical result. This is a
  real property of the current source, not a guess: each is confirmed by reading the function body,
  not just the docstring, which in each case describes a role for the unused argument.

This is a different posture from `attnk`/`tensorx`'s explicit status-code vocabulary (see
[Attention kernels](attention-kernels.md) and
[Tensor buffer primitives](tensorx-kernels.md)): a caller here gets a finite number back in every
case shown in the contract, and has to know which fallback value a given function chose in order to
tell "the math degenerated to a no-op" apart from "this was a real answer".

## Verification

`mojo/tests/libs/test_transformer_attention.mojo`, `test_sparse_attention.mojo`,
`test_flash_attention.mojo`, and `test_positional_encoding.mojo` are auto-generated smoke tests:
each calls every public function once with `0.5` in every argument slot and asserts only that the
result is finite (not NaN or infinite) — there are no pinned expected values in any of the four
files, so none of this family's real numeric behavior is asserted by its own test suite as it
stands today. Every worked number on this page was instead computed independently — by re-deriving
each function's formula from the `.mojo` source quoted above and evaluating it in plain Python — and
the flash-attention running state was additionally cross-checked against a from-scratch stable
softmax implementation (max-subtract, `exp`, sum, normalize) over the same three scores, matching to
every digit shown. `bigbird_random_block_select`'s selected-block set (`{3, 4, 5}` out of 10, given
seed `7.0` and `n_random=3.0`) was likewise checked by evaluating the hash formula for all ten block
IDs by hand, not merely for the one shown.

**Next:** see the buffer-shaped, SIMD-accelerated versions of scaled dot-product attention, flash
attention, masking, and RoPE in [Attention kernels](attention-kernels.md), or how `attnk.rope` and
the rest of the production attention stack wire into a real decode loop in
[LLM inference kernels](llm-inference-kernels.md).
