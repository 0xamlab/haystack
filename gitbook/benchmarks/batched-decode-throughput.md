---
icon: layer-group
description: Batched (continuous-batching) decode for Qwen3-0.6B-Base on Apple silicon — many sequences per weight sweep. 2.1-2.6x llama.cpp concurrent throughput at B=8-32, token-verified.
---

# Batched decode throughput

Single-stream decode generates one token for one sequence at a time, and is bound by how fast the
model weights can be streamed from memory — every token pays the full weight sweep. Batched decode
(continuous batching) steps **B** sequences together, so each projection becomes one wide
`[B, d_model] @ weights` multiply that sweeps the weights **once for all B sequences**. The weight
cost amortizes across the batch, which is exactly where headroom opens up for a live serving
workload that has more than one request in flight.

This page measures that aggregate rate — total generated tokens per second across all B sequences —
for one real checkpoint on one machine, against both Algenta's own single-stream decode and the
concurrent serving throughput of the installed opponents.

{% hint style="success" %}
**Batched decode runs 2.1-2.6x the concurrent decode throughput of llama.cpp at B=8-32
(2,140 vs ~810 aggregate tok/s at B=32), with every sequence in the batch verified
token-identical to single-stream decode.** The same compiled Metal kernel path that ships the
single-stream decode runs the batched path; nothing external is added.
{% endhint %}

## Why batching is the lever

At batch size 1, every generated token streams the full model weights once. On this machine that
puts every engine — Algenta included — near the same memory-bandwidth floor, which is why
[single-stream decode](decode-throughput.md) is a tight race. With B sequences in flight, the
weights are still swept once per step, but the step now produces B tokens, so the per-token weight
cost falls as B grows. That is the only structural way off the single-stream floor, and it is what a
real serving deployment does whenever more than one request is live.

## Results

Aggregate decode tokens per second across all B sequences in flight, `Qwen/Qwen3-0.6B-Base`,
264-token prompts, greedy, Apple M4 Max. Each sequence is ingested into its own KV-cache slot, then
all B are stepped together; the number is total generated tokens across the batch divided by the
decode wall. Median of repeated runs.

| Batch size B | Algenta batched | llama.cpp concurrent | Margin |
| --- | --- | --- | --- |
| 8 | 1,122 tok/s | ~540 tok/s | ~2.1x |
| 16 | 1,790 tok/s | ~690 tok/s | ~2.6x |
| 32 | **2,140 tok/s** | ~810 tok/s | **~2.6x** |

llama.cpp runs its own slot-based concurrent serving (`llama-server`, B parallel slots, F16
weights); Algenta runs `decode_batched` (one weight sweep per step for all B). mlx-lm has no
concurrent serving mode, so it is not in this table. Margins are stated conservatively against
llama.cpp's best same-day figures; the machine was warm during part of the measurement window, and
both engines' absolute figures move with thermal state — the margin is the stable quantity.

Two things are worth reading off the table:

* **Aggregate keeps rising with B.** Weights are swept once per step regardless of B, so each extra
  sequence adds mostly activation + attention work, not another weight sweep.
* **Per-sequence rate falls as B rises** — that is expected and honest to report: the batch is
  trading per-request latency for aggregate throughput, which is the standard serving trade-off.

### Correctness

A faster wrong answer is not a result. The batched path was checked two ways:

* **Token-identical to single-stream.** For B = 2 through 32, every sequence in the batch produces
  exactly the same greedy token stream as running that prompt alone through single-stream decode.
  Not "close" — identical.
* **B=1 routes to single-stream.** A one-sequence batch has nothing to batch; `decode_batched`
  delegates it to the serial path and returns the same tokens, so there is no degenerate B=1 batch
  code path.

## Method

* **Checkpoint.** `Qwen/Qwen3-0.6B-Base` (Apache-2.0, ungated), the same real checkpoint as the
  single-stream page.
* **What is timed.** The batched decode loop: one descriptor-table submission steps all B sequences
  together (batched projections, per-sequence flash-decoding attention against each sequence's own
  KV cache, batched lm-head + argmax). Prompt ingest into the per-sequence KV slots is excluded
  from the decode rate.
* **Opponent.** llama.cpp's own concurrent serving (`llama-server`, B parallel slots), the way it
  is actually deployed. mlx-lm is single-stream only and is not measured here.
* **Batch sizes.** B = 8, 16, 32; aggregate = total generated tokens across the batch / decode
  wall, median of repeated runs each.
* **Hardware.** Apple M4 Max, integrated GPU via Apple Metal.

## What is not claimed

* **Small batches are not the win.** Batching only pays once there are enough sequences in flight
  to amortize the weight sweep; if you have one request, use single-stream decode (and
  `decode_batched` itself routes B=1 there).
* **Absolute figures move with thermal state.** Both engines' numbers shift as the machine heats;
  the margin is the stable quantity, and it is stated against llama.cpp's best same-day figures.
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
