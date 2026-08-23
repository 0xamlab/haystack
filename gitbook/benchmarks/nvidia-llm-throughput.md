---
icon: gauge-high
description: Measured LLM inference throughput of the CUDA-native session on NVIDIA A100 and L4 — prefill and decode tok/s against llama.cpp F16, with configuration and methodology.
---

# NVIDIA LLM throughput

This page reports measured throughput of the CUDA-native resident session (Qwen3-0.6B-Base,
packed-int8 weights with f32 prefill) on NVIDIA A100-SXM4-40GB and L4, against llama.cpp
built with GGML\_CUDA (F16) on the same machines.

## Results

### A100-SXM4-40GB

256-token prompt, greedy, resident weights. Median of 20 runs per cell; rel-IQR <= 5% on all
cells.

| Engine | Prefill tok/s | Decode tok/s (gen=64) | Decode tok/s (gen=256) |
| --- | --- | --- | --- |
| Algenta (packed3, v2 prefill GEMMs, CUDA-graph decode) | 3,260 | 427.1 | 408.7 |
| llama.cpp F16 | 2,527 | 356.9 | 366.6 |

### L4

Decode on g2-standard-8 (sm\_89), same protocol:

| Engine | Decode tok/s (gen=64) | Decode tok/s (gen=256) |
| --- | --- | --- |
| Algenta (packed3, CUDA-graph decode) | 191.1 | 184.8 |
| llama.cpp F16 | 171.3 | 172.6 |

## Implementation notes

* Prefill: v2 GEMM family — 4x4 register block on a 64x64 output tile, software-pipelined
  shared-memory loads, one 128-bit `float4` global load per thread per tile,
  bank-conflict-aware layouts. Layer GEMM sum is 9.9x the first generation.
* Decode: arithmetic-packed-int8 weights (1.58 B/weight) with captured-graph decode — zero
  per-token host traffic, split-K flash-decoding (32 splits), warp-shuffle attention
  reduction, fused gate/up SwiGLU. Bit-identical to the f32 session (16/16 greedy oracle on
  every build).

## Methodology

* Checkpoint: `Qwen/Qwen3-0.6B-Base` (Hugging Face, unmodified). Workload: fixed 256-token
  prompt, greedy (temperature 0).
* Opponent: llama.cpp pinned at 000547513f, GGML\_CUDA, same VM, F16 GGUF; fixture via
  `llama-completion -no-cnv`.
* Statistics: 20 runs per cell, median, rel-IQR <= 5%; a 16/16 greedy-token oracle gates every
  build before measurement; an optimization variant is recorded only after its bench number
  moves over baseline.
* Hardware: GCP a2-highgpu-1g (A100-SXM4-40GB) and g2-standard-8 (L4), driver 595.71.05,
  Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0; solo-GPU census during every timed window; clocks
  pinned at 1410 MHz on the A100; L4 comparisons on fresh-boot solo runs.

## Scope

* Results are for Qwen3-0.6B-Base on the pinned toolchain; the session derives buffer and
  grid shapes from the checkpoint's own dimensions.
* The CUDA session is benchmark-verified on the hardware above. The shipped SDK serving path
  is Metal; the CI CUDA lane is compile-gated (no GPU on the builder). See
  [GPU support](../engine/gpu-support.md).

## Related

* [NVIDIA LLM serving](nvidia-llm-serving.md) — batched decode aggregate, cold
  start, VRAM and determinism on A100/L4.
* [NVIDIA kernel benchmarks](nvidia-kernel-benchmarks.md) — the portable-kernel layer on
  T4/L4/A100.
* [GPU support](../engine/gpu-support.md) — the verification matrix.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — Metal prefill.
* [Decode throughput](decode-throughput.md) — Metal single-stream decode.
* [LLM inference overview](llm-inference-overview.md) — prefill and decode together on Apple
  silicon.
* [Benchmarks](overview.md) — methodology.
