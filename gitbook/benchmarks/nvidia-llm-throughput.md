---
icon: gauge-high
description: Measured LLM inference throughput of the CUDA-native session on NVIDIA A100 and L4 — prefill and decode tok/s for Qwen3-0.6B and Qwen2.5-7B against llama.cpp, with configuration and methodology.
---

# NVIDIA LLM throughput

This page reports measured throughput of the CUDA-native resident session on
NVIDIA A100-SXM4-40GB and L4, against llama.cpp built with GGML\_CUDA on the same
machines: Qwen3-0.6B-Base (packed-int8 weights, f32 prefill) vs the F16 GGUF, and
Qwen2.5-7B-Instruct (packed-int8 weights, tensor-core prefill) vs the Q8\_0 GGUF.

## Results

### A100-SXM4-40GB — Qwen3-0.6B-Base

256-token prompt, greedy, resident weights. Median of 20 runs per cell; rel-IQR <= 5% on all
cells.

| Engine | Prefill tok/s | Decode tok/s (gen=64) | Decode tok/s (gen=256) |
| --- | --- | --- | --- |
| Algenta (packed3, v2 prefill GEMMs, CUDA-graph decode) | 3,260 | 427.1 | 408.7 |
| llama.cpp F16 | 2,527 | 356.9 | 366.6 |

### A100-SXM4-40GB — Qwen2.5-7B-Instruct prefill

Prompt prefill, greedy, resident weights, clocks pinned at 1410 MHz. Median of 20 runs per
cell; rel-IQR <= 0.2% on every Algenta cell. The 256-token cell uses the warm regime of the
opponent (its first of five runs pays a one-time kernel-selection cost).

| Engine | Prefill 256 tok/s | Prefill 1024 tok/s |
| --- | --- | --- |
| Algenta (packed3, cuBLAS tensor-core prefill, one-pass flash attention) | 8,494 | 6,968 |
| llama.cpp Q8\_0 | 4,680 | 5,089.1 |

Prefill speedup: 1.82x at 256 tokens, 1.37x at 1024 tokens.

### L4

Decode on g2-standard-8 (sm\_89), same protocol:

| Engine | Decode tok/s (gen=64) | Decode tok/s (gen=256) |
| --- | --- | --- |
| Algenta (packed3, CUDA-graph decode) | 191.1 | 184.8 |
| llama.cpp F16 | 171.3 | 172.6 |

## Implementation notes

* Prefill (0.6B): v2 GEMM family — 4x4 register block on a 64x64 output tile,
  software-pipelined shared-memory loads, one 128-bit `float4` global load per thread per
  tile, bank-conflict-aware layouts. Layer GEMM sum is 9.9x the first generation.
* Prefill (7B): packed-int8 weights are dequantized once into f16 twins at session open
  (one-time ~71 ms, +13.05 GB); the projection GEMMs then run on cuBLAS HMMA tensor cores
  (f16 inputs, f32 accumulate and output), and the prompt runs through the flash attention
  pass in a single M-parallel sweep. Same 16/16 greedy-token oracle as every build, plus
  cross-engine text identity with llama.cpp F16 on five chat prompts.
* Decode: arithmetic-packed-int8 weights (1.58 B/weight) with captured-graph decode — zero
  per-token host traffic, split-K flash-decoding (32 splits), warp-shuffle attention
  reduction, fused gate/up SwiGLU. Bit-identical to the f32 session (16/16 greedy oracle on
  every build).

## Methodology

* Checkpoints: `Qwen/Qwen3-0.6B-Base` and `Qwen/Qwen2.5-7B-Instruct` (Hugging Face,
  unmodified; the 7B conversion preserves the q/k/v attention biases). Workload: fixed
  256-token prompt, greedy (temperature 0); the 7B page adds a 1024-token cell (the race
  prompt repeated x4 — prefill throughput is content-agnostic). The 7B oracle is a fp32
  CPU transformers reference with repetition\_penalty pinned at 1.0.
* Opponent: llama.cpp pinned at 000547513f, GGML\_CUDA, same VM; F16 GGUF for 0.6B, Q8\_0
  GGUF for 7B; fixture via `llama-completion -no-cnv`, prefill cells via `llama-bench`.
* Statistics: 20 runs per cell, median, rel-IQR <= 5%; a 16/16 greedy-token oracle gates every
  build before measurement; an optimization variant is recorded only after its bench number
  moves over baseline.
* Hardware: GCP a2-highgpu-1g (A100-SXM4-40GB) and g2-standard-8 (L4), driver 595.71.05,
  Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0; solo-GPU census during every timed window; clocks
  pinned at 1410 MHz on the A100; L4 comparisons on fresh-boot solo runs.

## Scope

* Results are for Qwen3-0.6B-Base and Qwen2.5-7B-Instruct on the pinned toolchain; the
  session derives buffer and grid shapes from the checkpoint's own dimensions.
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
