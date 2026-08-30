---
icon: gauge-high
description: Chunked cross-entropy that never materializes the full logit tensor, and the host-side capacity and dispatch-budget arithmetic for a resident GPU decode session, answered with no device required.
---

# Loss functions and resident-context kernels

Four modules, two unrelated kernel families that happen to share a shape: each answers a capacity
question before the expensive work runs, rather than after it fails. `lossk` computes cross-entropy
loss a CHUNK of tokens at a time so a training step's `[n_tok][vocab]` logit tensor — 2.5 GB at a
2048-token batch against a 151,936-token vocabulary, in 64-bit — never has to exist all at once.
`residentk` answers "would a resident GPU decode session hold this model shape, and what would it
cost" as pure host arithmetic, with no accelerator, no shader compiler, and no `std.gpu` import
anywhere on its contract-reachable path — a caller on plain Linux CI can size a deployment the same
way a caller on the actual GPU host would. Nothing in either family shares code with the other; they
are grouped here because both are budget-checked-before-work families of exactly the kind this corpus
gives their own page, and four modules split two ways would otherwise be two very short pages.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# lossk: chunk a batch's cross-entropy so the full logit tensor never exists
runtime.execute("lossk.cross_entropy", "ce_peak_logit_cells", [2048, 151936, 256])["result"]
# {"chunked_cells": 38895616.0, "materialized_cells": 311164928.0, "ratio": 8.0,
#  "n_chunks": 8, "status": 580} -- a 256-token chunk holds 8x less than materializing
# all 2048 tokens' logits at once, for the exact shape a Qwen3 training step uses

# residentk: would a session hold Qwen3-0.6B-Base, and what would it cost, no GPU needed
runtime.execute("residentk.contract", "residentk_dispatch_budget", [28])["result"]
# 171 -- 28 layers, 6 GPU dispatches each plus 3 fixed per token (n_layers * 6 + 3)
```

## The modules

| Module | What it does |
| --- | --- |
| `lossk.contract` | Status vocabulary (580-599), the work-budget and peak-logit-budget checks, and the target-range guard every `lossk` function validates against first. |
| `lossk.cross_entropy` | Fused projection + chunked cross-entropy, its analytic backward, a chunk-invariance self-check, and a reporter for exactly how many logit cells a given chunk size holds. |
| `residentk.contract` | Status vocabulary (600-619), model-shape and context-fit validation, the per-token GPU dispatch-count budget, resident weight/KV-cache element counts, and the split-K and prefill-GEMM tile-selection policies — all pure host arithmetic. |
| `residentk.probe` | Three device-agnostic facts: were GPU kernels compiled into this binary, is an accelerator present and usable, and — combining both with `residentk.contract`'s arithmetic — would a session at a given model shape actually run, and what would it cost. |

## `lossk`: the loss is where the memory goes, and it's the one layer that can avoid it

Every other layer in a transformer is `O(tokens x hidden)`. The output projection is
`O(tokens x vocab)`, and vocabulary is two orders of magnitude larger than hidden — for a 2048-token
batch against Qwen3's 151,936-token vocabulary, the full logit tensor is 2.5 GB in 64-bit, allocated
to produce a single scalar. Cross-entropy needs only two numbers per token — the logit of the correct
class, and the log-sum-exp over all classes — both of which are reductions, so `lossk.cross_entropy`
produces the logits a CHUNK of tokens at a time, reduces immediately, and reuses the chunk buffer.
Peak logit memory becomes `chunk x vocab` and stops depending on the batch size at all.

| Function | What it does |
| --- | --- |
| `loss_status_name(code)` | Names a `lossk` status code; an unrecognized one returns `"unknown_status"` rather than borrowing a neighbor's meaning. |
| `loss_dims_check(n_tok, d_model, vocab)` | Validates a fused-projection shape: every dimension positive and under its ceiling, and `n_tok * d_model * vocab` under `LOSS_MAX_WORK_CELLS` (2^46). |
| `loss_chunk_check(chunk, vocab)` | The peak-memory bound: refuses (`LOSS_ERR_BAD_CHUNK`) a chunk whose `chunk * vocab` would exceed `LOSS_MAX_LOGIT_CELLS` (2^27, 1 GiB at 64-bit) rather than silently clamping it. |
| `loss_logit_cells(chunk, vocab)` | `chunk * vocab` as a `Float64` — what one chunk will materialize. Negative on a malformed request, so a wrapped count never reads as small. |
| `loss_work_fits(n_tok, d_model, vocab, ceiling)` | `True` when the three-factor product fits `ceiling`, computed by successive division so the check itself never overflows. |
| `loss_targets_in_range(targets, n_tok, vocab)` | `True` when every one of the first `n_tok` targets is `0 <= t < vocab`; a negative target is refused rather than read as a masking sentinel. |
| `loss_scalars_ok(value)` | `True` when a scalar is finite (delegates to `tensorx.contract.tx_finite`, the same finiteness check `residentk_scalars_ok` below uses). |
| `loss_tol_for(magnitude, reduction_width)` | The comparison tolerance for two spellings of a loss of a given size, scaled by both the magnitude and the width of the reduction behind it (rule 4b). |
| `ce_from_logits_flat(logits, targets, n_tok, vocab)` | Cross-entropy from an already-materialized `[n_tok][vocab]` logit tensor — the reference the fused kernel is measured against. |
| `fused_linear_ce_flat(hidden, weight, targets, n_tok, d_model, vocab, chunk)` | Projects and reduces one chunk at a time; the full logit tensor is never allocated. `weight` is `[vocab][d_model]` row-major. |
| `fused_linear_ce_bwd_flat(hidden, weight, targets, n_tok, d_model, vocab)` | Gradients of the fused loss with respect to `hidden` and `weight`. Not chunked — `d_weight` is the size of the weight itself, so chunking the logits here would not change the peak. |
| `ce_peak_logit_cells(n_tok, vocab, chunk)` | Reports what a chunked call actually holds against what the materialized form would, as a measured ratio rather than a docstring claim. |
| `ce_chunk_invariance_flat(hidden, weight, targets, n_tok, d_model, vocab)` | Runs the fused loss at `chunk=1` and `chunk=n_tok` and reports how far apart the two totals land — the property that makes the chunk size a memory knob and not a hidden model change. |

### Status codes

`lossk` owns 580-599, immediately after `mlpk` (390-399) and before `residentk` starts a new package
range at 600. `LOSS_ERR_UNKNOWN_OBJECTIVE` (588) is named in `loss_status_name` but not returned by
any function in these two modules today — reserved for an objective beyond cross-entropy.

| Code | Name | Meaning |
| --- | --- | --- |
| 580 | `ok` | shape and target checks passed, or the requested computation ran |
| 581 | `empty_dimension` | a required dimension was `< 1` |
| 582 | `length_mismatch` | a `List` argument was shorter than the shape it is supposed to cover |
| 583 | `dimension_too_large` | a dimension exceeded this package's own ceiling |
| 584 | `work_budget_exceeded` | `n_tok * d_model * vocab` exceeded `LOSS_MAX_WORK_CELLS` |
| 585 | `non_finite_scalar` | a scalar was NaN or infinite |
| 586 | `target_id_out_of_range` | a target class id was negative or `>= vocab` |
| 587 | `chunk_exceeds_logit_budget` | `chunk * vocab` exceeded `LOSS_MAX_LOGIT_CELLS` |
| 588 | `unknown_objective` | reserved, not currently returned |

### A worked example: uniform logits give exactly `log(vocab)`

With every logit equal, softmax is uniform over the vocabulary, so cross-entropy against any target
is exactly `-log(1/vocab) = log(vocab)`, independent of which class is "correct." This is the actual
hand-written golden-vector case in `test_lossk_cross_entropy.mojo`:

```python
logits = [0.25] * (6 * 9)          # 6 tokens, vocab 9, every logit identical
targets = [0, 3, 6, 0, 3, 6]        # any in-range target -- softmax is uniform regardless

out = runtime.execute("lossk.cross_entropy", "ce_from_logits_flat",
                      [logits, targets, 6, 9])["result"]
out["mean_loss"]
# 2.1972245773362196 -- exactly log(9), to the last representable bit
```

### The two budgets are genuinely different questions

`loss_dims_check(2048, 4096, 151936)` — a real Qwen3-8B-scale training shape — passes: the total
work, `2048 * 4096 * 151936 ~= 1.27e12` cells, is legitimately huge and legitimately allowed, because
chunking is what makes that total tractable. But `loss_chunk_check(2048, 151936)` — passing the
BATCH size where a CHUNK size belongs, the obvious mistake since both are token counts — fails with
`LOSS_ERR_BAD_CHUNK`: `2048 * 151936 = 311,164,928` cells is 2.3x past the 2^27 logit-cell ceiling. A
chunk of 256 tokens against that same vocabulary passes and, per `ce_peak_logit_cells` above, holds
exactly 8x less than materializing the whole batch. One budget bounds what may exist at once; the
other bounds what may exist in total across the whole computation, and a single ceiling could not
express both — total work is supposed to be able to exceed peak memory, that is the entire point of
chunking.

### Chunk invariance is checked to the last bit, not to a tolerance

Per-token losses are summed in token order regardless of how the batch was chunked, so
`ce_chunk_invariance_flat` demands `max_abs_delta == 0.0` between a call at `chunk=1` and a call at
`chunk=n_tok` — not an approximate agreement. The hand-written test sweeps every chunk size from `1`
to `n_tok` and confirms every one gives a bit-identical `mean_loss`. This is a stronger property than
`attnk.flash`'s agreement with `attnk.sdpa` (documented in [Attention
kernels](attention-kernels.md)), which is checked to a tolerance because flash attention genuinely
accumulates in a different order; here the accumulation order is the same regardless of chunk size,
so the two spellings of the loss have no reason to differ by even a rounding bit.

### The backward's gradient check is a cancellation identity, not a symbolic re-derivation

`fused_linear_ce_bwd_flat` returns `d_hidden` and `d_weight`. The test verifies `d_hidden` directly
against a central-difference numerical gradient (agreement to `1e-8`), and separately checks that
summing `d_weight` over the whole vocabulary, for any fixed input dimension, cancels to within
`1e-9` of zero — a consequence of softmax summing to one and the one-hot target also summing to one.
The measured cancellation is `~5e-11`, attributed in the test to `std.math.log` not being correctly
rounded on this toolchain (documented in `lossk.contract`'s `LOSS_TRANSCENDENTAL_FLOOR`, `1e-9`) —
not a defect in the backward pass, which is why the test's tolerance sits an order of magnitude above
the measured floor rather than at zero.

## `residentk`: what a resident decode session would cost, asked with no device

A resident session holds its weights and KV cache on the GPU for the whole generation rather than
re-uploading them every call. `residentk.contract` and `residentk.probe` answer every question about
whether such a session could exist and what it would cost — model shape support, context capacity,
GPU dispatch count per token, resident element counts — as ordinary host arithmetic, importing no
`std.gpu` anywhere. The device-touching code (`residentk.session`, `residentk.kernels`) is private and
not reachable through `runtime.execute` at all; these two modules are the whole contract-facing
surface of the `residentk` package.

| Function | What it does |
| --- | --- |
| `residentk_status_name(code)` | Names a `residentk` status code; unrecognized codes return `"resident_code_out_of_range"`. |
| `residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff)` | Is this a model shape the session can hold: every dimension positive and under its ceiling, `h_q` an exact multiple of `h_kv` (integer GQA group size), `d_head` a power of two (the RoPE/SDPA threadgroup reduction halves a uniform stride), and the model's own staged-vector size under the binary's compiled shared-memory tier. |
| `residentk_context_check(n_prompt, n_new, max_ctx)` | Does `n_prompt + n_new` fit a session opened at `max_ctx` positions, and is `max_ctx` itself under `RESIDENT_MAX_CONTEXT` (65536) — asked once, before the first token, because the KV cache is fixed-capacity and written in place. |
| `residentk_cache_elements(n_layers, h_kv, d_head, max_ctx)` | Float32 elements the KV cache holds at a given `max_ctx`: `n_layers * 2 * max_ctx * h_kv * d_head` (one `k` and one `v` buffer per layer). |
| `residentk_dispatch_budget(n_layers)` | GPU dispatches one decode token costs on the standard path: `n_layers * 6 + 3`. |
| `residentk_dispatch_budget_deep(n_layers)` | The same count once split-K attention is in play, where SDPA becomes a partial-plus-merge pair: `1 + n_layers * 7 + 2`. |
| `residentk_weight_elems(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, max_ctx=512)` | Total resident Float32 element count: every layer's weights, plus the tied embedding/lm_head table, plus the KV cache at `max_ctx`. `0` if the shape is unsupported. |
| `residentk_scalars_ok(eps, scale)` | Both `eps` and the attention scale are finite and strictly positive. |
| `residentk_splitk_should_split(n_keys)` | Is `n_keys` deep enough (`>= 32`, a measured boundary) that splitting the SDPA dispatch pays for its own extra kernel launch. |
| `residentk_splitk_policy(n_keys, n_cores, h_q)` | The split count for this depth, on a GPU with `n_cores` cores running `h_q` query heads — log-linear in `n_keys` between two calibrated anchors, clamped to `[1, residentk_splitk_max_n_splits(n_cores, h_q)]`. |
| `residentk_splitk_max_n_splits(n_cores, h_q)` | The occupancy ceiling `residentk_splitk_policy` can ever return for this `(n_cores, h_q)` pair — what a caller sizes split-K scratch buffers to, once, before any step's `n_keys` is known. |
| `residentk_prefill_gemm_use_narrow_tile(m_rows)` | `True` below `m_rows = 32`: should this prefill's GEMM dispatches use the narrow-tile kernel variant instead of the wide one. |

`residentk.probe`:

| Function | What it does |
| --- | --- |
| `resident_gpu_kernels_compiled()` | Was this binary built with `-D ALGENTA_GPU` — a build fact, the same on every host the binary is copied to. |
| `resident_available()` | Can this binary, on this host, actually open a resident session: both `resident_gpu_kernels_compiled()` AND a present, openable accelerator. |
| `resident_session_probe(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab)` | The full answer for one model shape — shape support, dispatch budget, resident element count, and whether a session could actually run here — as a single `ResidentProbe`. |

### Status codes

`residentk` owns 600-619, immediately after `lossk` (580-599). `metaldispatch` — the actual Metal
decode session documented in [Metal LLM decode](qwen3-metal-decode.md) — starts its own range at
620, adjacent with no gap.

| Code | Name | Meaning |
| --- | --- | --- |
| 600 | `resident_ok` | the session is holding the shape it was asked to, or the step ran |
| 601 | `resident_empty_dimension` | a declared dimension was `< 1` |
| 602 | `resident_dimension_too_large` | a dimension exceeded this package's own ceiling |
| 603 | `resident_head_geometry_unsupported` | `h_q % h_kv != 0`, or `d_head` is not a power of two |
| 604 | `resident_shader_toolchain_absent` | binary built without `-D ALGENTA_GPU` — no kernel compiled in |
| 605 | `resident_no_accelerator_present` | GPU kernels are compiled in, but this host has no usable accelerator |
| 606 | `resident_kv_context_full` | the run needs more KV positions than this session's own `max_ctx` |
| 607 | `resident_weight_length_mismatch` | a weight handed to the session doesn't match its declared shape's element count |
| 608 | `resident_launch_failed` | a device call raised (returned as a status, not thrown, matching `accel`'s convention) |
| 609 | `resident_non_finite_scalar` | `eps` or the attention scale was NaN or infinite |
| 610 | `resident_code_out_of_range` | not one of the codes above |

### A worked example: sizing Qwen3-0.6B-Base with no GPU in sight

`residentk_dims_check(1024, 16, 8, 128, 3072)` — Qwen3-0.6B-Base's real shape — passes despite
`h_q * d_head` (2048) not equaling `d_model` (1024), which a check that assumed the usual identity
would wrongly reject. Its 28-layer dispatch budget and resident footprint are pure arithmetic, and
`resident_session_probe` combines them with the two build/host facts in one call. In the default
build (`-D ALGENTA_GPU` unset — every Linux CI runner in this project) the shape and cost numbers are
still reported, only the two device facts read false:

```python
runtime.execute("residentk.probe", "resident_session_probe",
                [1024, 16, 8, 128, 3072, 28, 151936])["result"]
# {"kernels_compiled": False, "device_present": False, "session_possible": False,
#  "dispatch_budget": 171, "resident_f32_elems": 625410048, "status": 604}
# 604 = resident_shader_toolchain_absent -- the shape is fine, this binary just has no kernels
```

`625,410,048` Float32 elements is `~2.50 GB` at 4 bytes each — the one-time resident cost of Qwen3-
0.6B-Base's weights plus its KV cache at the default 512-position capacity
(`residentk_weight_elems`'s own `max_ctx` default, `RESIDENT_DEFAULT_CONTEXT`). The KV cache alone at
that default is `residentk_cache_elements(28, 8, 128, 512) = 29,360,128` elements
(`~117 MB`); opened instead at the full `RESIDENT_MAX_CONTEXT` safety ceiling of 65536 positions, the
same formula gives `3,758,096,384` elements, `~15.0 GB` — which is exactly why
`RESIDENT_MAX_CONTEXT` is documented as a refusal ceiling and not an allocation size: a session pays
only for the `max_ctx` it actually opens at, and `residentk_context_check`/`residentk_cache_elements`
are what let a caller find out which `max_ctx` a real run needs before opening one.

A shape refusal is reported before either device question is asked: `resident_session_probe(1024, 5,
2, 128, 3072, 2, 151936)` (`h_q=5` not a multiple of `h_kv=2`) returns `status=603` with
`session_possible=False` on every build and every host, so a reader is never sent looking for
hardware that could not have helped in the first place.

### The split-K and prefill-GEMM policies, pinned by their own hand-written suites

Unlike the rest of `residentk.contract`, `residentk_splitk_policy` and
`residentk_prefill_gemm_use_narrow_tile` each have a dedicated hand-written test file
(`test_residentk_splitk_policy.mojo`, `test_residentk_prefill_gemm_policy.mojo`) alongside the
auto-generated smoke coverage in `test_residentk_contract.mojo` — see Verification below. Two
calibration anchors are pinned exactly: on this project's own reference hardware (`n_cores=40`,
Qwen3-0.6B-Base's `h_q=16`), `residentk_splitk_policy(128, 40, 16) == 40` and
`residentk_splitk_policy(1000, 40, 16) == 80`, and `residentk_splitk_max_n_splits(40, 16) == 80`
reproduces the fixed `_ATTN_SPLITK_N_SPLITS_NATIVE = 80` an earlier PR shipped as a single constant —
so a host whose core count cannot be probed degrades to exactly that last-known-good value rather
than to an invented number. For the tile policy, the two real measured anchors are
`residentk_prefill_gemm_use_narrow_tile(5) == True` (narrow measured faster at 5 rows: 110.1 vs 91.6
tok/s) and `residentk_prefill_gemm_use_narrow_tile(256) == False` (wide measured faster at 256 rows:
1165 vs 783.3 tok/s) — a genuine two-way choice, not a single config that wins everywhere.

## Where `residentk` sits relative to `metaldispatch`

`residentk.contract`/`residentk.probe` are the device-agnostic layer; the actual Metal decode session
that runs on a real accelerator is `metaldispatch.*`, documented in [Metal LLM
decode](qwen3-metal-decode.md). That page's own `metaldispatch.contract` module states it plainly:
`metaldispatch_dispatch_budget` "delegates to `residentk.contract`'s own `residentk_dispatch_budget`
rather than restating the formula" — so the `171` this page's own opening example computes is the
identical number `qwen3_i8_allsimd7_decode_flat`'s `dispatches_per_token` field reports back for a
real 28-layer run. `metaldispatch` owns its own, separate 620-639 status range built on the same
per-package ledger convention `residentk.contract` established first (600-619); a code from one
family is never confused with the other. A recent perf fix
(`perf(engine): bucket resident ctx to powers of two`) rounds a session's requested `max_ctx` up to
the next power of two before it becomes part of the resident-session cache key, so shape switches
within the same power-of-two band reuse resident buffers instead of a full teardown and rebuild —
that bucketing floors at this page's own `RESIDENT_DEFAULT_CONTEXT` (512) and is bounded by
`RESIDENT_MAX_CONTEXT` (65536), both imported directly from `residentk.contract`.

`residentk`'s KV cache is also a structurally different design from the one `llmk.generate` documents
in [LLM inference kernels](llm-inference-kernels.md): `kv_cache_append_flat` there builds a new,
larger buffer and copies the whole existing cache into it on every call — the right shape for a CPU
reference path with no persistent session. `residentk`'s cache, by contrast, is allocated once at
`max_ctx` and written one slot per step IN PLACE, with no copy at any step — `residentk_context_check`
exists specifically to refuse a run that would not fit that fixed allocation before the first token,
since there is no larger buffer to grow into afterward.

## Verification

* `lossk.contract` and `lossk.cross_entropy` both have dedicated hand-written suites
  (`test_lossk_contract.mojo`, `test_lossk_cross_entropy.mojo`) that pin the status range, the
  chunk-invariance property to bit equality, the uniform-logits closed form, a numerical-gradient
  check on the backward, and the refusal paths — none of this family's tests are auto-generated
  smoke coverage.
* `residentk.contract` and `residentk.probe` each also have an auto-generated smoke test
  (`test_residentk_contract.mojo`, `test_residentk_probe.mojo`) that calls every function once and
  checks only that it returns without error — these alone would not pin any specific number. The real
  numeric grounding for most of this page's `residentk` claims comes from three dedicated
  hand-written suites: `test_residentk_session.mojo` (the dispatch-budget and resident-element-count
  values used above, plus a full two-layer GPU-vs-CPU token-level golden vector where a GPU build and
  device are available), `test_residentk_splitk_policy.mojo`, and
  `test_residentk_prefill_gemm_policy.mojo`.

**Next:** see [Metal LLM decode](qwen3-metal-decode.md) for the actual GPU session built on
`residentk`'s arithmetic, or [Autograd and training-stability kernels](autograd-and-training-stability-kernels.md)
for `numerical_stability.logsumexp`, the frozen reduction `lossk.cross_entropy` builds its whole
numerical-stability story on.
