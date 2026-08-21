---
icon: layer-group
description: Batched (continuous-batching) decode for Qwen3-0.6B-Base on Apple silicon — many sequences per weight sweep. 2.1-2.6x llama.cpp concurrent throughput at B=8-32, token-verified.
---

# Batched decode throughput

Single-stream decode generates one token for one sequence at a time; every token pays the full
weight sweep from memory. Batched decode (continuous batching) steps B sequences together, so each
projection becomes one wide `[B, d_model] @ weights` multiply and the weights are swept once for
all B sequences. This page measures the aggregate rate — total generated tokens per second across
all B sequences — for Qwen3-0.6B-Base on one machine, against Algenta's own single-stream decode
and the concurrent serving throughput of installed opponents.

## Results

Aggregate decode tokens per second across all B sequences in flight, `Qwen/Qwen3-0.6B-Base`,
264-token prompts, greedy, Apple M4 Max. Each sequence is ingested into its own KV-cache slot,
then all B are stepped together; the number is total generated tokens across the batch divided by
the decode wall. Median of repeated runs.

| Batch size B | Algenta batched | llama.cpp concurrent | Margin |
| --- | --- | --- | --- |
| 8 | 1,122 tok/s | ~540 tok/s | ~2.1x |
| 16 | 1,790 tok/s | ~690 tok/s | ~2.6x |
| 32 | 2,140 tok/s | ~810 tok/s | ~2.6x |

llama.cpp runs its own slot-based concurrent serving (`llama-server`, B parallel slots, F16
weights); Algenta runs `decode_batched` (one weight sweep per step for all B). mlx-lm has no
concurrent serving mode and is not in this table. Absolute figures move with thermal state;
margins are against llama.cpp's best same-day figures.

* Aggregate throughput keeps rising with B: the weights are swept once per step regardless of B,
  so each extra sequence adds mostly activation + attention work, not another weight sweep.
* Per-sequence rate falls as B rises: the batch trades per-request latency for aggregate
  throughput.
* Token-identical to single-stream decode: for B = 2 through 32, every sequence in the batch
  produces exactly the same greedy token stream as running that prompt alone through
  single-stream decode.
* B=1 routes to single-stream: `decode_batched` delegates one-sequence batches to the serial path
  and returns the same tokens.
* The batched path runs on the same compiled Metal kernel path that ships single-stream decode.

## Methodology

* Checkpoint: `Qwen/Qwen3-0.6B-Base` (Apache-2.0, ungated), the same real checkpoint as the
  single-stream page.
* Timed region: the batched decode loop — one descriptor-table submission steps all B sequences
  together (batched projections, per-sequence flash-decoding attention against each sequence's
  own KV cache, batched lm-head + argmax). Prompt ingest into the per-sequence KV slots is
  excluded from the decode rate.
* Opponent: llama.cpp's own concurrent serving (`llama-server`, B parallel slots). mlx-lm is
  single-stream only and is not measured here.
* Batch sizes: B = 8, 16, 32; aggregate = total generated tokens across the batch / decode wall,
  median of repeated runs each.
* Hardware: Apple M4 Max, integrated GPU via Apple Metal.

## Scope

* Batching amortizes the weight sweep once enough sequences are in flight; single-request
  workloads use single-stream decode (`decode_batched` routes B=1 there).
* Qwen3-0.6B-Base on one M4 Max; other model sizes, hardware and context depths are separate
  measurements.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode together.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — the token-input half.
* [Decode throughput](decode-throughput.md) — the single-stream measurement this extends.
* [Metal LLM decode](../engine/qwen3-metal-decode.md) — the kernel path behind both single-stream
  and batched decode.
* [GPU support](../engine/gpu-support.md) — the lane-by-lane verification matrix behind these
  Metal results.
* [Run local LLM decode](../guides/run-qwen3-decode.md) — install, get the checkpoint, and run a
  decode end to end.
* [Benchmarks](overview.md) — methodology.
