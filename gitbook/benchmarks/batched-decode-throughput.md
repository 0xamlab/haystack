---
icon: layer-group
description: Batched (continuous-batching) decode for Qwen3-0.6B-Base on Apple silicon — many sequences per weight sweep. Aggregate throughput crosses single-stream near B=10 and reaches 2.33x at B=32.
---

# Batched decode throughput

Single-stream decode generates one token for one sequence at a time, and is bound by how fast the
model weights can be streamed from memory — every token pays the full weight sweep. Batched decode
(continuous batching) steps **B** sequences together, so each projection becomes one wide
`[B, d_model] @ weights` multiply that sweeps the weights **once for all B sequences**. The weight
cost amortizes across the batch, which is exactly where headroom opens up for a live serving
workload that has more than one request in flight.

This page measures that aggregate rate — total tokens per second across all B sequences — for one
real checkpoint on one machine, against Algenta's own single-stream decode as the baseline.

{% hint style="success" %}
**Batched decode crosses even with single-stream around B=10 and pulls ahead from there — reaching
2.33x the sequential single-stream rate at B=32 (616.7 vs ~265 tok/s), with the batch verified
token-consistent.** The same compiled Metal kernel path that ships the single-stream decode runs the
batched path; nothing external is added.
{% endhint %}

## Why batching is the lever

At batch size 1, every generated token streams the full model weights once. On this machine that
puts every engine — Algenta included — near the same memory-bandwidth floor, which is why
[single-stream decode](decode-throughput.md) is a tight race. With B sequences in flight, the
weights are still swept once per step, but the step now produces B tokens, so the per-token weight
cost falls as B grows. That is the only structural way off the single-stream floor, and it is what a
real serving deployment does whenever more than one request is live.

## Results

Aggregate decode tokens per second across the whole batch, `Qwen/Qwen3-0.6B-Base`, 24 greedy steps
per sequence, median of 3 runs, Apple M4 Max. Baseline is Algenta's own single-stream decode on the
same build (~265 tok/s, one sequence at a time):

| Batch size B | Aggregate tok/s | Per-sequence tok/s | vs single-stream |
| --- | --- | --- | --- |
| 1 | 33.2 | 33.2 | 0.13x |
| 4 | 125.0 | 31.2 | 0.47x |
| 8 | 231.8 | 29.0 | 0.87x |
| 16 | 403.4 | 25.2 | 1.52x |
| 32 | **616.7** | 19.3 | **2.33x** |

Two things are worth reading off this table:

* **Aggregate keeps rising with B.** Weights are swept once per step regardless of B, so each extra
  sequence adds mostly activation + attention work, not another weight sweep.
* **Per-sequence rate falls as B rises** — that is expected and honest to report: the batch is
  trading per-request latency for aggregate throughput, which is the standard serving trade-off.

### Correctness

A faster wrong answer is not a result. The batched path was checked for internal consistency: B
sequences seeded with the same token and stepped together must produce **identical** token streams
(they are the same computation, run side by side), and they do — every step, for every sequence in
the batch. The generated stream is coherent text, not garbage indices.

## Method

* **Checkpoint.** `Qwen/Qwen3-0.6B-Base` (Apache-2.0, ungated), the same real checkpoint as the
  single-stream page.
* **What is timed.** Decode-only wall time per batched step: one descriptor-table submission steps
  all B sequences together (batched projections, per-sequence flash-decoding attention against each
  sequence's own KV cache, per-sequence greedy argmax). Weight load and any prefill are excluded.
* **Baseline.** Algenta's own single-stream decode, same build, same machine, one sequence at a
  time (~265 tok/s).
* **Batch sizes.** B = 1, 4, 8, 16, 32; aggregate = B x steps / wall, median of 3 runs each.
* **Hardware.** Apple M4 Max, integrated GPU via Apple Metal.

## What is not claimed

* **Not yet a comparison against llama.cpp or mlx-lm batched serving.** This page measures
  Algenta's batched decode against Algenta's own single-stream decode. Both opponents' batched /
  concurrent serving modes are the next comparison and are not measured here yet.
* **Small batches are not the win.** At B=1..8 the aggregate is *below* single-stream. Batching
  only pays once there are enough sequences in flight to amortize the weight sweep; if you have one
  request, use single-stream decode.
* **The tail is not yet batched.** The current build runs the final lm-head / argmax as one dispatch
  per sequence and uses the unfused prefill projection kernels, so the fixed per-step cost keeps the
  small-B aggregate low. A batched lm-head and fused per-layer dispatches are the recorded next
  optimizations and will raise this whole curve.
* **One checkpoint, one machine.** Qwen3-0.6B-Base on one M4 Max. Not a claim across other model
  sizes, hardware, or context depths.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode together.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — the token-input half.
* [Decode throughput](decode-throughput.md) — the single-stream race this extends.
* [Qwen3 Metal decode](../engine/qwen3-metal-decode.md) — the kernel
  path behind both single-stream and batched decode.
* [Run Qwen3-0.6B-Base decode on Apple Silicon](../guides/run-qwen3-decode.md) — install, get the
  checkpoint, and run a decode end to end.
* [Benchmarks](overview.md) — methodology and what is not published.
