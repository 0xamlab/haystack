---
icon: bolt
description: A parallel decode-shaped matrix-vector product, KV-cache growth, greedy argmax, whole-buffer residual add, and the shared status vocabulary that a real autoregressive decode loop composes them into.
---

# LLM inference kernels

`llmk` is four small modules that exist because wiring a real Qwen3 checkpoint through Algenta's
existing attention/norm/MLP kernels (`attnk`, `normk`, `mlpk`, `gemm`) left exactly a few gaps a
decode loop cannot work without: an elementwise add of two whole hidden-state buffers (the residual
stream), the KV-cache append and full-vocabulary argmax a decode step needs that no other package
supplied, and a parallel matrix-vector product for the one projection shape a frozen kernel computes
single-threaded by its own documented design. Nothing here duplicates embedding lookup or rotary
position embeddings — those already existed (`mlpk.embedding`, `attnk.rope`) and this family calls
them rather than reimplementing them.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]   # 2 rows x 3 cols, row-major: [[1,2,3],[4,5,6]]
x = [1.0, 1.0]

result = runtime.execute("llmk.gemv_fast", "gemv_transposed_parallel_flat", [a, x, 2, 3])["result"]
result["y"]        # [5.0, 7.0, 9.0] -- A^T @ x, summed down each column
result["status"]   # 560 -- LLMK_OK
```

## The modules

| Module | What it does |
| --- | --- |
| `llmk.contract` | the status vocabulary (codes 560-579) and the four shape checks every other function in this family calls before doing any work |
| `llmk.gemv_fast` | a parallel transposed matrix-vector product for the one decode-step projection shape `gemm.blocked.gemv_flat` computes on a single thread, by that kernel's own documented design |
| `llmk.generate` | the two decode-loop primitives no frozen kernel already supplied: KV-cache growth and a full-vocabulary greedy argmax |
| `llmk.residual` | elementwise add of two whole flat buffers — the residual-stream add a transformer layer needs twice, where only a scalar one-`Float64`-at-a-time helper existed before |

## Two gaps, not three

`llmk.contract`'s own docstring records the actual audit: wiring a real Qwen3-0.6B-Base checkpoint
through the kernel tree found three candidate gaps, and two of them were already closed elsewhere.
Embedding-table gather already existed as `mlpk.embedding.embedding_fwd_flat`; half-split rotary
embeddings already existed as `attnk.rope.rope_apply_flat(..., interleaved=False)` — the GPT-NeoX
split-half convention, which is exactly Qwen3's. Both are called directly rather than shadowed under
`llmk`'s own status codes. The one thing genuinely absent was an elementwise add of two *whole*
flat buffers: `transformer_blocks.residual_connection` and `fused_kernels.fused_add_norm` are both
frozen and scalar, one `Float64` at a time, and looping either by hand at every call site is exactly
the "last line of the kernel, not the kernel" pattern the rest of this plane already named for
attention, norm and the FFN. `llmk.residual` supplies that one driver.

`llmk.generate` and `llmk.gemv_fast` were added in later sessions, once an actual decode loop
(`benchmarks/llm_smoke/qwen3_generate.mojo`) was wired on top of the prefill-only forward pass
`qwen3_forward.mojo` runs: a decode loop needs to grow a KV cache and pick a token, and it needs its
per-layer projections to not run on one core out of sixteen. Both additions stayed inside `llmk`'s
own 560-579 status range — nothing was renumbered.

## Status vocabulary and the shape checks (contract)

`llmk` owns status codes **560-579**, sitting after `tensorx` (300-319), `gemm` (320-339),
`accel`/`causal_inference` (340-359), `attnk` (360-379), `normk` (380-389) and `mlpk` (390-399), and
before `lossk` (580-599). Four dimension checks, one per consumer, are the gate every other function
in this family calls first:

| Code | Name | Meaning |
| --- | --- | --- |
| 560 | `llmk_ok` | the kernel ran and every element of the output is defined |
| 561 | `llmk_empty_dimension` | a required dimension was < 1 |
| 562 | `llmk_a_length_mismatch` | `residual_add_flat`: `len(a) != n` |
| 563 | `llmk_b_length_mismatch` | `residual_add_flat`: `len(b) != n` |
| 564 | `llmk_dimension_too_large` | a dimension exceeds `LLMK_MAX_DIM` (`1 << 24`) |
| 565 | `llmk_code_out_of_range` | not one of these codes — `llmk_status_name`'s own fallback |
| 566 | `llmk_cache_length_mismatch` | `kv_cache_append_flat`: `len(cache) != cache_len` |
| 567 | `llmk_new_length_mismatch` | `kv_cache_append_flat`: `len(new_vals) != n_new` |
| 568 | `llmk_logits_length_mismatch` | `greedy_argmax_flat`: `len(logits) != n` |
| 569 | `llmk_gemv_a_length_mismatch` | `gemv_transposed_parallel_flat`: `len(a) != m * n` |
| 570 | `llmk_gemv_x_length_mismatch` | `gemv_transposed_parallel_flat`: `len(x) != m` |
| 571 | `llmk_cache_capacity_exceeded` | internal only: the reserved-capacity append would overrun its buffer |

Code 571 belongs to `_kv_cache_append_into_flat`, a leading-underscore internal function that is not
runtime-discoverable (see `apps/runtime/mojo_inventory.py`'s underscore skip) — it is listed here
anyway because the module's docstring is explicit that every `llmk`-owned code, public or not, lives
in this one vocabulary.

```python
runtime.execute("llmk.contract", "llmk_residual_dims_check", [6, 6, 6])["result"]
# 560 -- both operands really are length 6

runtime.execute("llmk.contract", "llmk_residual_dims_check", [6, 2, 6])["result"]
# 562 -- `a` was claimed length 6 but is actually 2 elements long

runtime.execute("llmk.contract", "llmk_status_name", [562])["result"]
# "llmk_a_length_mismatch"
```

`LLMK_MAX_DIM` is `1 << 24`, the same order of magnitude as `normk.contract.NORM_MAX_ROWS` — a
residual add over `tokens * d_model` at any real transformer shape sits far below it; the ceiling
exists to refuse a caller who passes a byte count or an unbounded accumulation length where an
element count belongs, rather than allocate against it.

## A parallel path for one frozen kernel's known-slow shape

`gemm.blocked.gemv_flat(..., trans=True)` computes `y = A^T @ x` for a transposed weight matrix — the
exact shape `qwen3_generate.mojo`'s per-layer Q/K/V/O/gate/up/down projections need during decode —
and that kernel's own docstring says its transposed branch is scalar on purpose: *"a caller who cares
about speed transposes once up front instead."* Seven of every eight decode-step matmuls hit that
scalar path, so fifteen of sixteen physical cores sat idle for seven of every eight matmuls per step;
only the eighth call (the untransposed `lm_head` projection) already hit the parallelized branch.
`gemm/blocked.mojo` stays frozen and unmodified — `llmk.gemv_fast` adds a parallel path for the same
shape in a new, additive namespace instead.

The reason it partitions differently than the untransposed kernel's own parallel branch is the axis:
for fixed output column `j`, `y[j] = sum_i A[i, j] * x[i]` is a strided reduction, so the scalar loop
runs `i` outer and `j` inner — for each input row it broadcasts `x[i]` and walks `A`'s row
contiguously, scattering into every `y[j]` at once. That is the SIMD-friendly direction, but it means
partitioning by input row the way the untransposed branch partitions output rows would need a lock or
a per-thread partial-sum reduction. The output columns are what is safe to hand out disjointly, so
`gemv_transposed_parallel_flat` splits `y`'s `n` columns into contiguous bands via
`std.algorithm.parallelize`, and each worker runs the same `i`-outer, `j`-inner loop confined to its
own band — no cross-thread writes, no lock.

The hand-computable case, below the fan-out threshold:

```python
a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]   # [[1, 2, 3], [4, 5, 6]], row-major
x = [1.0, 1.0]

r = runtime.execute("llmk.gemv_fast", "gemv_transposed_parallel_flat", [a, x, 2, 3])["result"]
r["y"]   # [5.0, 7.0, 9.0] -- column sums: [1+4, 2+5, 3+6]
```

At `m=2, n=3` the 6-cell shape is far below `PARALLEL_MIN_CELLS` (`1 << 16`, 65,536 cells), so the
call delegates straight to the frozen `gemv_flat` rather than fanning out — the test file confirms
this delegation path returns the exact same answer the frozen kernel does, not a second, independently
drifting implementation. The parallel column-band path is exercised, and checked against
`gemv_flat`, at shapes that actually clear the threshold: a 300x300 (90,000-cell) case and a
rectangular 128x1536 case — closer to a real Q/K/V/gate/up/down projection shape — both agree with
the frozen scalar kernel to within `1e-9` worst absolute delta.

## KV-cache growth and greedy argmax

`kv_cache_append_flat(cache, new_vals, cache_len, n_new)` returns `out = cache ++ new_vals`, called
twice per layer per decode step (once for K, once for V) — a decode step projects K/V for only the
newly generated token(s) and must append them to what every earlier step (prefill included) already
produced:

```python
cache = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
new_vals = [100.0, 101.0, 102.0]

r = runtime.execute("llmk.generate", "kv_cache_append_flat", [cache, new_vals, 6, 3])["result"]
r["out"]   # [0, 1, 2, 3, 4, 5, 100, 101, 102]
r["n"]     # 9
```

`greedy_argmax_flat(logits, n)` is the full-vocabulary argmax a decode step needs to pick the next
token. It is built on `llm_sampling.greedy_token_id`, which is deliberately a per-candidate
comparison — its own signature takes `max_logit` as something the caller already knows, not a bare
reduction-max. `greedy_argmax_flat` supplies the two passes that make it a full argmax: a linear scan
for the row's true maximum, then the frozen per-candidate formula, called once per vocabulary entry
exactly as published, to report which id matches it. Ties resolve to the **first** matching id —
`numpy.argmax`'s own convention:

```python
mid = [1.0, 9.0, 3.0]
runtime.execute("llmk.generate", "greedy_argmax_flat", [mid, 3])["result"]
# {"token_id": 1, "logit": 9.0, "status": 560}

tied = [2.0, 7.0, 7.0, 1.0]
runtime.execute("llmk.generate", "greedy_argmax_flat", [tied, 4])["result"]["token_id"]
# 1 -- the FIRST of the two 7.0s, not id 2
```

The test file also runs this at the actual scale a decode step calls it at: a full 151,936-wide
Qwen3-0.6B-Base vocabulary row with a planted maximum at id 12095 (annotated in the test as "a real
Qwen3-0.6B-Base 'Paris' id, from the forward-pass phase") — `greedy_argmax_flat` finds it correctly
at that width.

### The hot loop doesn't call `kv_cache_append_flat`

`kv_cache_append_flat` is `O(cache_len + n_new)` by design — every call allocates a brand-new list and
copies the *entire* existing cache into it, plus the new values. That is fine for a caller who calls
it once, or a bounded number of times, against a cache that is not what's growing in a hot loop —
`benchmarks/mojo_benchmarks/bench_llmk.mojo` measures this directly and discloses it as a real,
non-bug property: cost per newly appended element rises as the existing cache grows, because the call
is dominated by re-copying content that did not change. A decode loop that calls this twice per layer
per step, every step, against the same cache pays that cost quadratically across the whole sequence.

`qwen3_generate.mojo`'s decode loop no longer calls it. It calls two internal, leading-underscore,
not-runtime-discoverable primitives instead: `_kv_cache_reserve_flat(max_elements)` allocates an
entire per-layer K (or V) cache once, zero-filled, at its known maximum size — the same
`n_prompt + N_NEW_MAX` bound the loop already computes to size its shared RoPE table — and
`_kv_cache_append_into_flat(cache, new_vals, cache_len, n_new)` writes `new_vals` into
`cache[cache_len : cache_len + n_new]` in place and returns only a status code: no new allocation, no
re-copy of existing content, ever. `test_llmk_generate.mojo` measures the cost shape directly:
appending 128 new elements into a cache already holding 2,048 elements, versus into one already
holding 2,048 + 131,072 = 133,120 elements (about 65x larger), the gate requires the cost per
newly-appended element to grow no more than 3x between the two — flat, not the `O(cache_len)` growth
`kv_cache_append_flat` itself has. `kv_cache_append_flat` is otherwise unchanged and still exactly
correct; it is simply no longer the function this one hot loop calls.

## Residual add

`residual_add_flat(a, b, n)` computes `out[i] = a[i] + b[i]` for `i` in `[0, n)` — the whole-buffer
driver a transformer decoder layer calls twice per layer (post-attention, post-FFN) to add the
sublayer's output back onto the residual stream:

```python
a = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
b = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0]

r = runtime.execute("llmk.residual", "residual_add_flat", [a, b, 6])["result"]
r["out"]   # [10.0, 10.0, 10.0, 10.0, 10.0, 10.0] -- a[i] + b[i] == 10.0 for every i, by construction
```

The test file also runs this at 4,096 elements — a `d_model`-scale hidden-state buffer — and gets a
worst absolute delta of exactly `0.0` against the elementwise sum computed independently, so both
sizes agree bit-for-bit; `residual_add_flat`'s own `PARALLEL_MIN_CELLS` (`1 << 15`, 32,768 cells) is
above both, so both exercise the same single-threaded loop, and the buffer only fans out across
`parallelize` workers past that count.

## Guarantees

* **Deterministic, no randomness anywhere in this family** — every module's capability block
  declares `deterministic: true`, `seed_requirements: none`.
* **Exact-length shape checks, not best-effort ones.** Every public function's dimensions are
  checked against the real buffer lengths before any element is read; a caller's wrong claimed
  length is refused with a specific status code, never read past the end. A `List` read past its end
  in Mojo is an uncatchable process abort, not a catchable exception — this is the actual hazard the
  checks exist to prevent, stated explicitly in `test_llmk_residual.mojo` and
  `test_llmk_generate.mojo`.
* **A dimension of zero (or the wrong sign) is refused, not silently accepted as an empty success.**
  `n_new = 0` is refused for `kv_cache_append_flat` because a decode step always adds at least one
  token; `n = 0` is refused for both `residual_add_flat` and `greedy_argmax_flat`.
* **`LLMK_MAX_DIM` (`1 << 24`) bounds every dimension** across all four modules — a ceiling, not a
  realistic transformer size.
* **Delegation, not duplication, below a real fan-out threshold.** Both `llmk.gemv_fast` and
  `llmk.residual` fall back to a plain serial loop (or the frozen `gemv_flat`) below their own
  `PARALLEL_MIN_CELLS`, rather than paying `parallelize`'s fan-out/join cost on work too small to
  benefit from it.

## How this composes into a decode step

`qwen3_generate.mojo` is the one driver that uses all four `llmk` modules together, alongside
`attnk.rope`/`attnk.mask`/`attnk.sdpa`, `normk.rmsnorm`, `mlpk.embedding`/`mlpk.activation`, and
`gemm.blocked`. Per decode step: embed the one new token (`mlpk.embedding`), project Q/K/V through
`gemv_transposed_parallel_flat` instead of the frozen scalar `gemv_flat` path, apply RoPE
(`attnk.rope`), grow the running K/V cache (`llmk.generate`'s internal, reserved-capacity
primitives), run causal-masked attention against the full grown cache
(`attnk.sdpa`/`attnk.mask`, with `n_tok_q=1`), add the residual (`llmk.residual`) after attention and
again after the gated FFN (`mlpk.activation`), normalize (`normk.rmsnorm`), and pick the next token
with `greedy_argmax_flat`.

This is the CPU reference decode path — the one whose output every other implementation gets checked
against. It is a separate code path from the compiled int8 Metal kernel `metaldispatch.qwen3_decode`
runs on Apple Silicon: that module's own imports pull in `attnk.rope` (for table sizing) and its own
fused GPU shader (`_MBQwen3I8AllSimd7`), but never `llmk` — the production GPU path does not layer on
top of these CPU primitives, it is cross-checked against them (and against an independent
`transformers` reference) as a separate implementation of the same arithmetic.

## Verification

* `mojo/tests/libs/test_llmk_contract.mojo` — the generated call-shape smoke test for all five
  contract functions.
* `mojo/tests/libs/test_llmk_gemv_fast.mojo` — the hand-computable 2x3 case, a non-uniform (and
  negative) weight vector checked against `gemv_flat` exactly, a 300x300 and a rectangular 128x1536
  case checked against `gemv_flat` to `1e-9`, and shape-mismatch refusals.
* `mojo/tests/libs/test_llmk_generate.mojo` — KV-cache growth in order, growth from an empty
  (prefill's own) cache, the internal reserved-capacity path's bit-identical output and flat cost
  shape, greedy argmax at every logit position including exact ties and a full 151,936-wide vocab
  row, and every shape refusal.
* `mojo/tests/libs/test_llmk_residual.mojo` — basic correctness, a 4,096-element decoder-layer-scale
  buffer, and both operands' length refusals.
* `benchmarks/mojo_benchmarks/bench_llmk.mojo` — the timing gate that measures and discloses
  `kv_cache_append_flat`'s real `O(cache_len + n_new)` cost shape, side by side with the internal
  reserved-capacity path's flat one.

**Next:** [Attention kernels](attention-kernels.md) for the SDPA/RoPE/mask half of the same decode
step, or [Metal LLM decode](qwen3-metal-decode.md) for the production GPU-accelerated path this CPU
reference is checked against.
