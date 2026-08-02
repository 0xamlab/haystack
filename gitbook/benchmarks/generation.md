---
icon: forward-step
description: Decode-loop kernel results — residual-add and full-vocabulary greedy argmax correctness and cost shape, plus the measured, non-amortized cost of growing a KV cache.
---

# Generation

Results for the two orchestration primitives an autoregressive decode loop needs on top of the frozen attention, normalization and feed-forward kernels: a whole-buffer residual add, a full-vocabulary greedy argmax, and KV-cache growth. Every number below names the property being gated and the correctness check that ran with it.

{% hint style="warning" %}
**One of the three findings on this page is unflattering, and it is reported as measured.** KV-cache growth does not amortize: every call re-copies the entire existing cache, not just the new tokens. That is disclosed in its own section below with the actual numbers, not smoothed into a throughput figure.
{% endhint %}

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Precision measured | 64-bit floating point |

Results are reported for this configuration only. Other chip generations and memory configurations are published separately as they are measured, never averaged into a single figure.

## Residual add

`residual_add_flat` is a plain elementwise add over a whole flat buffer — `hidden = residual + block_out`, the operation a decoder layer runs twice (post-attention, post-FFN). There is no shape claim beyond "linear in n, and correct":

| Cells | Cost per cell |
| --- | --- |
| 16,384 | 3.61 ns |
| 131,072 | 0.84 ns |
| 1,048,576 | 0.48 ns |

Cost per cell falls rather than staying flat, for the same reason it falls in the normalization and feed-forward kernels: the fixed cost of fanning work out across cores amortizes over more elements as the buffer grows. The gate is only that it does not rise — it fell to **0.13x** of its starting value across a 64x larger buffer.

**Correctness:** output is bit-identical to a direct scalar loop over the same two buffers.

## Greedy argmax

This is the kernel with a real correctness story worth telling in full. The frozen `llm_sampling.greedy_token_id` formula is deliberately a per-candidate comparison — "is THIS logit the row's maximum" — not a full argmax, and its own docstring takes `max_logit` as an input the caller must already know. `greedy_argmax_flat` is the two-pass driver that turns it into one:

1. A bare linear scan for the row's true maximum. No frozen kernel computes an unconditional reduction-max, and finding one is not itself a sampling decision, so this pass is plain and untouched by any sampling policy.
2. The frozen per-candidate formula, called once per vocabulary entry exactly as published, to report which id matches the maximum found in pass one.

**Why two passes and not one:** a single-pass argmax has to update its own notion of "current best" as it scans, which is a different function from "compare this candidate against an already-known maximum" — the frozen formula that exists. Reusing the frozen formula for the whole job would mean feeding it a maximum it hasn't seen yet, which is not what its own signature accepts. Two passes over the row is the price of composing with the frozen kernel rather than re-deriving it.

**Tie-breaking:** ties resolve to the **first** matching index, matching `numpy.argmax`'s own convention. This is asserted directly, not read off the loop: a row with two positions sharing the maximum (`[2.0, 7.0, 7.0, 1.0]`) resolves to index 1, the first of the two, every time.

**Correctness:** agrees with a reference max-scan at the start, middle and end of a row, on all-negative logits, and on the deliberate tie above.

| Vocabulary | Cost per cell |
| --- | --- |
| 4,096 | 0.67 ns |
| 32,768 | 0.67 ns |
| 151,936 | 0.66 ns |

151,936 is a real model's full vocabulary width, not a round number chosen for the table. Cost per cell across a 37x wider vocabulary changes by **0.99x** — flat, against a gate of 3x.

## KV-cache append: the cost of a fresh copy, every call

`kv_cache_append_flat` grows a decode loop's key/value cache by one step's freshly-projected rows. Read plainly, the implementation allocates a brand-new buffer sized `cache_len + n_new` and copies **both** the entire existing cache and the new values into it — on every call. That is a real `O(cache_len + n_new)` cost per call. It is not an amortized append, and this page does not describe it as one.

Measured by holding the number of newly appended elements fixed at 128 (one layer's K or V row at `head_dim = 128`) and raising the size of the *existing* cache:

| Existing cache | Total time | Cost per appended element | Cost per element copied (existing + new) |
| --- | --- | --- | --- |
| 512 | 590 ns | 4.61 ns | 0.92 ns |
| 8,192 | 7,070 ns | 55.23 ns | 0.85 ns |
| 131,072 | 112,455 ns | 878.55 ns | 0.86 ns |

Each figure above is the mean of 200 calls at that cache size — a single call at the smallest size finishes in well under this host's clock resolution, and averaging is what makes the ratio below meaningful rather than a rounding artifact.

Two different per-element numbers, and they tell two different parts of the same story:

* **Cost per element actually copied** (existing cache plus new values) stays flat — **0.93x** across a 256x larger existing cache, against a gate of 3x. The copy itself is an ordinary, bandwidth-bound copy; it is not doing more work per byte moved as the cache grows.
* **Cost per newly appended element** — the number a caller doing "append N tokens" actually experiences — grew **191x** across the same 256x range. That is the direct consequence of re-copying a cache that did not change: the 128 new elements are a shrinking fraction of what the call actually moves, so the cost attributed to each of them grows with everything else being copied around them.

**What this means for a caller:** correctness is unaffected — the grown buffer is bit-identical to `cache ++ new_vals`, in order, at every size measured. What it does mean is that a caller appending to the same cache repeatedly over a long decode — the exact pattern a generation loop uses — pays a **quadratic total copy cost across the sequence**, not the O(1)-amortized cost a caller might expect from "append." A caller who cares about that should know it before calling this kernel repeatedly in a hot loop, rather than discovering it from a latency graph that bends the wrong way as context grows.

## What is not claimed

* That KV-cache growth here is O(1)-amortized, or that its cost is flat in any sense. It is measurably not: cost per newly appended element rose 191x across a 256x larger existing cache, and that is the headline of this section, not a caveat buried under it.
* Any generation speed, decode throughput, or tokens-per-second figure. These are the cost and correctness properties of three kernels in isolation, not an end-to-end generation number.
* Any comparison against a third-party inference engine or sampling library. These are Algenta's own kernels measured against Algenta's own reference implementations — a direct scalar loop, a reference max-scan, and direct list concatenation.

## Related

* [Benchmarks](overview.md) — methodology and what is not published.
* [Attention](attention.md) — the KV cache these kernels grow sits alongside the tiled attention kernel that reads it.
* [Feed-forward](feed-forward.md) — the other half of a transformer block.
* [Normalization](normalization.md) — the layer norms that surround both.

## Reproduce

Every table on this page comes from one command:

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/bench_llmk.mojo
```

The benchmark prints its own gate results, and fails on the properties described above rather than on absolute times, which vary by machine, thermal state and concurrent load.
