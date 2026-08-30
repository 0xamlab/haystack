---
icon: repeat
description: Scalar formulas for KV-cache memory and eviction (plain and paged), sampling and generation-loop decisions, speculative-decoding accept-rate math, and continuous-batching scheduling -- the arithmetic underneath an LLM serving loop, not the loop itself.
---

# KV cache and autoregressive generation kernels

Six modules, sixty-one functions, every one of them a plain scalar formula: `Float64` in, `Float64`
out, no buffers, no structs (`"structs": []` for all six in the runtime contract). This is the
arithmetic underneath the parts of serving an LLM that are not attention or a matmul: how many bytes
a KV cache costs per layer and in total, which entries a paging or eviction policy should keep next,
whether a candidate token clears a temperature/top-k/top-p/min-p/repetition-penalty gate, whether
generation should stop, how many tokens a speculative-decoding step is expected to accept and at what
speedup, and whether a continuous-batching scheduler can admit, preempt, or chunk a request this
iteration. Where `llmk` and `metaldispatch` (see [LLM inference kernels](llm-inference-kernels.md)
and [Metal LLM decode](qwen3-metal-decode.md)) are two different concrete decode loops running real
flat tensor buffers through a real Qwen3 checkpoint, this family is the formula layer underneath:
some of its functions are imported and called directly by those two concrete loops, and some exist
as standalone planning math with no wired-in caller in this tree yet -- both are true, for different
functions, and this page says which is which.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Qwen3-0.6B-Base's real config: 28 layers, 8 KV heads, head_dim 128
# (benchmarks/llm_smoke/decode_metal_probe.mojo's own comment) -- FP16 storage, 2048-token context.
per_layer = runtime.execute("kv_cache", "kv_cache_memory_per_layer", [1, 2048, 8, 128, 2])["result"]
per_layer            # 8388608.0 -- 8 MiB of K+V for one layer, batch size 1

total = runtime.execute("kv_cache", "kv_cache_total_memory", [per_layer, 28])["result"]
total                 # 234881024.0 -- 224 MiB across all 28 layers
```

## The modules

| Module | What it does |
| --- | --- |
| `kv_cache` | plain (non-paged) KV-cache memory sizing and utilization, LRU/H2O eviction scores, radix-tree shared-prefix length, and INT8 KV-cache quantization round-trip error |
| `paged_kv_cache` | vLLM-style paged KV-cache math: page-table lookup, block-count/compaction/copy costs, prefix-sharing savings, speculative-branch memory, LRU/Belady eviction, and two context-extension RoPE scaling factors |
| `llm_sampling` | token-selection score/threshold formulas -- temperature, top-k/top-p/min-p, repetition/frequency/presence penalties, beam-search scoring, length penalty, and locally-typical sampling |
| `generation_loop` | the same sampling decisions restated as loop-control accept/reject and stop signals, plus an entropy-adaptive (eta) sampling gate `llm_sampling` doesn't have |
| `speculative_decoding` | draft-then-verify math (acceptance probability, expected accepted tokens, theoretical speedup) alongside grammar-guided decoding, contrastive decoding, Medusa heads, token healing, and LLM watermarking |
| `continuous_batching` | iteration-level scheduling: admission control, preemption scoring, chunked prefill, decode throughput, time-to-first-token, head-of-line blocking, and per-request beam-search memory |

## One memory formula, restated six times

`kv_cache_memory_per_layer`'s formula -- `2 x batch x seq_len x n_heads x head_dim x dtype_bytes`,
the leading `2` for storing both K and V -- is not centralized anywhere in this family. The identical
five-number product is inlined again, under different local names, in five more places:

- `kv_cache.prefix_cache_hit_bytes` bundles `n_layers` into the same product directly, rather than
  composing it from `kv_cache_memory_per_layer` + `kv_cache_total_memory`.
- `paged_kv_cache.cache_compaction_gain`'s inner `bytes_per_block` is the identical product with
  `block_size_tokens` standing in for `seq_len`.
- `paged_kv_cache.prefix_sharing_savings`'s inner `prefix_bytes` is the same product again, argument
  order reshuffled.
- `paged_kv_cache.speculative_branch_memory` uses `n_branches x speculation_depth` as its token count
  in the same product.
- `paged_kv_cache.block_copy_cost`'s inner `block_bytes` is the same product again, divided by
  bandwidth for a transfer time instead of a size.
- `continuous_batching.beam_memory_per_request`'s inner `per_beam` is the same product again,
  multiplied by `beam_width`.

None of the six imports a shared helper for it -- each module restates the multiplication locally,
the same "duplicated on purpose" shape [Classical ML algorithms](ml-classical-algorithms.md)
documents for its own distance functions. Concretely, at Qwen3-0.6B-Base's real config and the same
2,048-token, FP16 baseline as the opening example (8 MiB/layer, 224 MiB total):

```python
runtime.execute("paged_kv_cache", "prefix_sharing_savings", [2048, 4, 28, 8, 128, 2])["result"]
# 704643072.0 -- 672 MiB saved when 4 sequences share one 2048-token system prompt
# instead of each caching its own independent copy

runtime.execute("continuous_batching", "beam_memory_per_request", [4, 2048, 28, 8, 128, 2])["result"]
# 939524096.0 -- 896 MiB for a beam_width=4 search over that same 2048-token budget
# (4x the same 224 MiB baseline, one beam's KV cache each)
```

## Quantization error, radix prefixes, and one trivial append

`kv_quantization_error(value, scale, zero_point)` round-trips a value through an 8-bit code the way
`tensorx.pack`'s frozen quantization math does elsewhere in this tree, clamping to the signed INT8
range (`[-128, 127]`) rather than wrapping past it:

```python
runtime.execute("kv_cache", "kv_quantization_error", [3.14, 0.05, 0.0])["result"]
# 0.010000000000000231 -- an ordinary round-off error, well inside the INT8 grid

runtime.execute("kv_cache", "kv_quantization_error", [20.0, 0.1, 0.0])["result"]
# 7.299999999999999 -- clamped: at zero_point=0 the largest representable code is 127 * 0.1 = 12.7,
# so a value of 20.0 loses 7.3 to the clamp, not to rounding
```

`radix_cache_shared_prefix_len(prefix_a_len, prefix_b_len, match_len)` caps a claimed match length at
the shorter of the two sequences (`match_len=12` against prefix lengths 10 and 15 returns `10.0`, not
`12.0`) -- a real prefix cannot be longer than the shorter string it is a prefix of, so a caller's
overcounted match is corrected rather than trusted. `incremental_decode_kv_append(current_len)` is the
simplest function in the family: `current_len + 1`, a named increment that exists so a decode loop's
cache-growth step has a call in the runtime dispatch catalog at all -- it is not, and does not wrap,
`llmk.generate.kv_cache_append_flat`, the function that actually appends real K/V rows to a real
buffer (see [LLM inference kernels](llm-inference-kernels.md)).

## Paging: blocks, page tables, and two RoPE scalers that stand alone

`paged_attention_block_count(seq_len, block_size)` is a ceiling division done through `Int64`
truncation rather than a `ceil` call -- `Int64((seq_len + block_size - 1) / block_size)` -- at
vLLM's typical 16-token block:

```python
runtime.execute("kv_cache", "paged_attention_block_count", [2048, 16])["result"]
# 128.0 -- 2048 tokens fill exactly 128 blocks

runtime.execute("kv_cache", "paged_attention_block_count", [2001, 16])["result"]
# 126.0 -- 2001 tokens need a mostly-empty 126th block; 2000 would only have needed 125
```

`paged_kv_cache.page_table_lookup(virtual_block_id, page_table_entry)` simply returns
`page_table_entry` unchanged, ignoring `virtual_block_id` entirely -- not dead code, but a named
placeholder for a step whose real virtual-to-physical mapping table lives on the caller's side.
`speculative_decoding.token_healing_overlap` (returns `overlap_chars` unchanged) and
`llm_sampling.top_k_threshold` (returns `k_th_logit` unchanged) are two more examples of the same
pattern: each exists to give a name, in the runtime dispatch catalog, to a step whose actual logic is
computed elsewhere and simply threaded through.

`dynamic_ntk_rope_scale(seq_len, base_context, alpha)` and `context_extension_factor(original_max_len,
target_max_len)` compute two different context-extension scaling factors -- NTK-aware
(`(seq_len / base_context)^alpha`) and simple linear (`target / original`) -- but neither is called by
the RoPE table this engine actually builds: `attnk.rope.rope_table_llama3`, the Llama-3
frequency-scaled table `metaldispatch.qwen3_prefill_decode` imports directly (see
[Attention kernels](attention-kernels.md)), implements its own, different frequency-scaling formula
and never calls into either of these two. They are standalone planning formulas for a context-
extension strategy this tree has not wired into a real RoPE table yet, not a second, competing
implementation of the one that already ships.

## Eviction: four scoring policies, never compared to each other

Four independent eviction-priority formulas live across the two KV-cache modules --
`kv_cache.kv_eviction_score_lru` (time since last access), `kv_cache.kv_eviction_score_h2o`
(attention-mass x recency, the Heavy-Hitter Oracle heuristic), `paged_kv_cache.cache_eviction_lru_score`
(the same LRU idea restated in step counts instead of wall-clock time), and
`paged_kv_cache.cache_eviction_beladys_score` (distance to next use, with a `1e9` sentinel for "never
used again" -- the offline-optimal policy a real cache can only approximate, since it would need to
know the future). No function in this family ranks or compares candidates under more than one policy
at once; each call scores one candidate under one named policy, and picking an eviction victim out of
a batch of scored candidates is left entirely to the caller.

## Two sampling modules, some of the same arithmetic under two names

`llm_sampling` and `generation_loop` overlap almost function-for-function, and the overlap is the same
handful of sampling primitives phrased twice, not two different ideas that happen to collide:
`llm_sampling` mostly returns a *value* (a scaled logit, a threshold, a score) for the caller to act
on; `generation_loop` mostly returns a *decision* (`1.0`/`0.0`, accept or reject). Three pairs are
close enough to check directly against each other's source:

- `temperature_scale(logit, temperature)` and `temperature_logit_scale(logit, temperature)` have
  byte-identical bodies: `logit * 1e9` at `temperature <= 0` (routing toward greedy), `logit /
  temperature` otherwise.
- `top_p_cumulative(sorted_prob, cumulative_so_far, p)` and `top_p_cumulative_accept(cumulative_prob,
  token_prob, p)` share the identical comparison (`< p`, return `1.0`/`0.0`) against their second
  positional argument, and both leave their first argument completely unused in the body.
- `typical_p_score(token_log_prob, entropy)` returns `abs(token_log_prob + entropy)`;
  `typical_sampling_accept`'s internal `surprise - entropy` works out to `-(token_log_prob + entropy)`
  before its own `abs()` -- the identical magnitude, one sign convention apart, then compared against
  a `tau` threshold `typical_p_score` never sees.

Two more pairs genuinely diverge rather than duplicate: `min_p_threshold(max_prob, min_p)` returns the
raw threshold `max_prob x min_p`; `min_p_accept(token_prob, max_prob, min_p)` returns the
already-applied decision. And `llm_sampling.token_frequency_penalty` folds frequency *and* presence
penalty into one call; `generation_loop` splits the same idea into two independent functions,
`frequency_penalty_logit` and `presence_penalty_logit`, callable one without the other.

A real production caller settles which module wins in practice. `metaldispatch.qwen3_prefill_decode`'s
sampled decode arm (the `..._sampled` entry point [Metal LLM decode](qwen3-metal-decode.md) documents)
imports exactly five functions for its logit pipeline, and every one is from `llm_sampling` --
`repetition_penalty_scale`, `token_frequency_penalty`, `temperature_scale`, `min_p_threshold`, and
`top_p_cumulative` -- applied in that order (penalties, then temperature, then a locally sorted
top-k slice, then min-p, then top-p) against a real logit vector before drawing a token.
`generation_loop` is never imported there, or anywhere else in this tree outside its own generated
dispatch entry and its own smoke test: every one of its ten functions is reachable through
`runtime.execute("generation_loop", ...)`, but none is a real caller's chosen path today. Top-k itself
is the one stage neither module's own top-k primitive is used for -- the real pipeline sorts and
slices the candidate list directly instead of calling `llm_sampling.top_k_threshold`'s identity
pass-through or `generation_loop.top_k_accept`'s rank comparison.

Beyond the sampling gates, `llm_sampling` and `generation_loop` each own territory the other doesn't
touch: `beam_score_update`, `length_penalty` and `pow_approx` (beam-search scoring) exist only in
`llm_sampling`; `eos_stop_score` (the stopping criterion) and `eta_sampling_accept` (entropy-adaptive
sampling) exist only in `generation_loop`.

## Not just speculative decoding

`speculative_decoding`'s own docstring names its actual scope as three separate topics, not one:
"Speculative decoding, constrained decoding, structured output." Four functions are the draft-then-
verify math proper -- `speculative_accept_prob`, `speculative_expected_tokens`, `draft_model_speedup`,
and `medusa_head_acceptance` (the Medusa multi-head variant of the same accept-ratio idea, one head
per lookahead position). The other six have nothing to do with a draft model at all:
`json_grammar_logit_mask` and `constrained_beam_score` are grammar-constrained decoding,
`structured_repair_score` is retry scoring for malformed structured output, `contrastive_decode_score`
is contrastive decoding (amplifying an expert model against an amateur one), `token_healing_overlap`
adjusts logits at a prompt/continuation token boundary, and `watermark_green_list_bias` is LLM
watermarking (its own docstring calls its green-list rule "simplified": token parity via
`(token_id + green_list_hash) % 2`, not a real cryptographic hash). A reader looking for one of these
six topics specifically has to know to look inside `speculative_decoding.py` -- there is no separate
module for any of them.

## Speculative decoding's math, and the memory it costs

The draft-then-verify probability math and the KV-cache memory it costs live in two different
modules -- worth knowing if you go looking for "speculative decoding" and only open one file.
`speculative_accept_prob(target_prob, draft_prob)` is the standard acceptance rule, `min(1, p_target /
p_draft)`:

```python
runtime.execute("speculative_decoding", "speculative_accept_prob", [0.45, 0.6])["result"]
# 0.75 -- the draft model over-weighted this token relative to the target; accept with probability 0.75

runtime.execute("speculative_decoding", "speculative_accept_prob", [0.5, 0.2])["result"]
# 1.0 -- the target model likes this token MORE than the draft did; always accept
```

`speculative_expected_tokens(acceptance_rate, speculation_depth)` turns a measured per-token
acceptance rate into an expected number of tokens accepted per speculative step -- `(1 -
alpha^(gamma+1)) / (1 - alpha)` -- and `draft_model_speedup` turns that expectation into a wall-clock
multiplier against naive one-token-at-a-time decoding. Chained, at a rate a real draft/target pair
might see (an 80% acceptance rate, four draft tokens per step):

```python
expected = runtime.execute("speculative_decoding", "speculative_expected_tokens", [0.8, 4])["result"]
expected   # 3.3616 -- out of a possible 5 (4 drafts + 1 guaranteed resample), ~3.36 accepted per step

runtime.execute("speculative_decoding", "draft_model_speedup",
                [expected, 50, 8, 4])["result"]
# 2.0497560975609757 -- against a 50ms target-model forward pass and an 8ms draft-model forward pass
```

roughly 2x faster than decoding one token per 50ms target-model step, for a draft model costing
roughly a sixth as much per step here. The KV memory that speculation costs is a separate call, one
module over: `paged_kv_cache.speculative_branch_memory(n_branches, speculation_depth, n_layers,
n_heads, head_dim, dtype_bytes)` -- the same restated memory formula from the section above, with
`n_branches x speculation_depth` standing in for the token count.

## Continuous batching: one iteration's admission, scheduling, and preemption math

`continuous_batching`'s ten functions are the arithmetic behind an iteration-level (vLLM-style)
scheduler's per-step decisions: whether to admit a new request, how many sequences fit in the next
decode iteration, which running sequence to preempt first if memory runs short, how to split a long
prompt into prefill chunks (`chunked_prefill_chunks(5000, 2048)` returns `3.0` -- the same
ceiling-via-`Int64` shape as `paged_attention_block_count` above), and the resulting
throughput/latency numbers a caller reports.

`admission_control_accept(request_kv_tokens, available_kv_tokens, safety_margin)` reserves a fraction
of the KV budget before ever comparing a request against it:

```python
runtime.execute("continuous_batching", "admission_control_accept", [8000, 10000, 0.1])["result"]
# 1.0 -- effective budget is 10000 * (1 - 0.1) = 9000; 8000 fits

runtime.execute("continuous_batching", "admission_control_accept", [9500, 10000, 0.1])["result"]
# 0.0 -- 9500 exceeds that same 9000-token effective budget; rejected outright, not queued past it
```

`preemption_score(seq_priority, tokens_generated, kv_cache_tokens)` -- `kv_cache_tokens /
(seq_priority x (tokens_generated + 1))` -- is written to protect sunk cost: a sequence that already
generated many tokens scores lower (survives longer) than an equally-sized, equal-priority sequence
that just started, even though the docstring's own one-line summary ("preempt low-priority long
sequences") reads as if length alone decided it:

```python
runtime.execute("continuous_batching", "preemption_score", [1, 2, 800])["result"]
# 266.6666666666667 -- priority 1, barely started (2 tokens generated), holding 800 KV tokens

runtime.execute("continuous_batching", "preemption_score", [1, 200, 800])["result"]
# 3.9800995024875623 -- same priority, same memory footprint, 200 tokens of sunk progress

runtime.execute("continuous_batching", "preemption_score", [5, 2, 800])["result"]
# 53.333333333333336 -- same as the first call, but priority 5 partly protects it
```

the barely-started sequence scores 67x higher than the one 200 tokens in -- "preempt the newest,
cheapest-to-restart request first," with priority as a second, independent brake, exactly the
behavior a fair scheduler wants even though the docstring's prose alone doesn't make that obvious.

## Guarantees

- **Every function in this family is a pure scalar formula.** No `List`, no `struct`, no
  randomness, no I/O -- every one of the six modules' contract entries declares `"structs": []`, and
  every argument and return value is a bare `Float64`. Scoring or filtering a whole vocabulary, batch,
  or candidate set is the caller's loop, not this layer's.
- **A division guard returns a safe default, never `NaN`/`inf`.** `max_tokens <= 0` in
  `kv_cache_utilization`, `bandwidth_gbs <= 0` in `block_copy_cost`, `avg_seq_remaining <= 0` in
  `iteration_level_batch_size`, and `theoretical_max_compute <= 0` in `batching_efficiency` all
  return `0.0`; `avg_wait_ms <= 0` in `head_of_line_blocking_score` and `total_time <= 0` in
  `draft_model_speedup` return `1.0` (no blocking / no speedup, not undefined); `draft_prob <= 0` in
  `speculative_accept_prob` and `medusa_prob <= 0` in `medusa_head_acceptance` return `1.0` (always
  accept, rather than dividing by zero).
- **INT8 quantization clamps, never wraps.** `kv_quantization_error`'s reconstructed code is clamped
  to `[-128, 127]` before it is used, so an out-of-range value pays a large, disclosed error rather
  than silently wrapping to the opposite sign.
- **A ceiling is computed by truncating, not calling `ceil`.** `paged_attention_block_count` and
  `chunked_prefill_chunks` both compute `Int64((x + y - 1) / y)` -- the standard integer
  ceiling-division idiom -- rather than depending on a floating-point `ceil`.
- **An eviction score is a name, not a ranking.** All four eviction formulas
  (`kv_eviction_score_lru`, `kv_eviction_score_h2o`, `cache_eviction_lru_score`,
  `cache_eviction_beladys_score`) score exactly one candidate against one policy; comparing scores
  across candidates, or across policies, is left entirely to the caller.

## Verification

The six `mojo/tests/libs/test_*.mojo` files behind this family (`test_kv_cache.mojo`,
`test_paged_kv_cache.mojo`, `test_llm_sampling.mojo`, `test_generation_loop.mojo`,
`test_speculative_decoding.mojo`, `test_continuous_batching.mojo`) are auto-generated coverage smoke
tests: each calls every function once against a shared, arbitrary all-`0.5` argument fixture and
checks only that the result is finite -- none pins a specific numeric output. The worked examples on
this page were hand-traced against the real formulas in `mojo/engine/kv_cache.mojo`,
`paged_kv_cache.mojo`, `llm_sampling.mojo`, `generation_loop.mojo`, `speculative_decoding.mojo`, and
`continuous_batching.mojo`, and every number given can be reproduced by re-running the same
arithmetic. The cross-module relationships this page documents (`llm_sampling.greedy_token_id`
imported by `llmk.generate.greedy_argmax_flat`; five `llm_sampling` functions imported by
`metaldispatch.qwen3_prefill_decode`'s sampled decode arm; `generation_loop`, `kv_cache`,
`paged_kv_cache`, `speculative_decoding`, and `continuous_batching` imported by no concrete driver in
this tree outside their own generated dispatch table) were confirmed directly against the real
`from ... import ...` statements in `mojo/engine/llmk/generate.mojo` and
`mojo/engine/metaldispatch/qwen3_prefill_decode.mojo`, not inferred from naming alone.

**Next:** [LLM inference kernels](llm-inference-kernels.md) for the concrete CPU reference decode
loop that calls `llm_sampling.greedy_token_id` directly, or [Metal LLM decode](qwen3-metal-decode.md)
for the production GPU sampled-decode path built on five more `llm_sampling` functions.
