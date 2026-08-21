---
icon: gauge-high
description: Measured LLM inference throughput of the CUDA-native session on NVIDIA A100 and L4 — prefill and decode tok/s against llama.cpp at matching precision, with configuration and methodology.
---

# NVIDIA LLM throughput

This page reports measured throughput of the CUDA-native resident session (Qwen3-0.6B-Base) on
NVIDIA A100-SXM4-40GB and L4, against llama.cpp built with GGML\_CUDA on the same machines.

## Results — A100-SXM4-40GB

256-token prompt, greedy, resident weights. Median of 20 runs per cell; rel-IQR <= 5% on all cells.

| Engine / format | Prefill tok/s | Decode tok/s (gen=64) | Decode tok/s (gen=256) |
| --- | --- | --- | --- |
| Algenta (f32, v2 GEMMs, CUDA-graph decode) | 3,260 | 329.8 | 318.9 |
| llama.cpp F16 | 2,527 | 356.9 | 366.6 |
| llama.cpp Q8\_0 | 13,028 | 404.2 | 419.8 |

* The llama.cpp F16 prefill row is per-process first use; its warm prefill (llama-bench pp256)
  is 14,101 tok/s.
* The Algenta per-dispatch decode path (no graph) measures 70.8 / 55.8 tok/s.
* Algenta weights are Float32 on this toolchain; see Implementation notes for the quantized-format
  status.

## Results — L4

Same protocol on g2-standard-8 (sm\_89).

| Engine / format | Prefill tok/s | Decode tok/s (gen=64) | Decode tok/s (gen=256) |
| --- | --- | --- | --- |
| Algenta (f32, CUDA-graph decode) | 262.1 | 98.1 | 97.2 |
| llama.cpp F16 | 2,165 (cold) | 171.3 | 172.6 |
| llama.cpp Q8\_0 | 13,438 (cold) | 263.2 | 268.3 |

Warm references (llama-bench): F16 pp256 7,555 / tg128 176.8; Q8\_0 pp256 11,247 / tg128 277.4.
Algenta decode on the L4 runs at 86% of the fp32 weight-bandwidth floor (2.62 GB/token at
300 GB/s).

## Implementation notes

* **Prefill.** v2 GEMM family: 4x4 register block on a 64x64 output tile, software-pipelined
  shared-memory loads, one 128-bit `float4` global load per thread per tile, bank-conflict-aware
  layouts. Layer GEMM sum is 9.9x the first generation; wide roles reach 29-38% of the A100's
  19.5 TFLOP/s FP32 SIMT peak (probe-measured ceiling: 90%).
* **Decode.** One CUDA graph per session with zero per-token host traffic, split-K
  flash-decoding (32 splits), warp-shuffle attention reduction; 4.6x the per-dispatch path.
* **Weight format.** The pinned Mojo 1.0.0 / MAX 26.5 CUDA backend serves only Float32 vector
  loads at memory bandwidth (probe battery: f16 4-7% of peak, int8 1-2%, Int32 ~2%) and exposes
  no tensor-core or inline-asm surface to user code. Decode is therefore fp32-weight-bandwidth
  bound; quantized CUDA weight formats activate when the backend load paths change.

## Methodology

* **Checkpoint.** `Qwen/Qwen3-0.6B-Base` (Hugging Face, unmodified). Workload: fixed 256-token
  prompt, greedy (temperature 0).
* **Opponent.** llama.cpp pinned at 000547513f, GGML\_CUDA, same VM; fixture via
  `llama-completion -no-cnv`; warm references via llama-bench.
* **Statistics.** 20 runs per cell, median, rel-IQR <= 5%; a 16/16 greedy-token oracle gates
  every build before measurement; an optimization arm is accepted only after its bench number
  moves over baseline.
* **Hardware.** GCP a2-highgpu-1g (A100-SXM4-40GB) and g2-standard-8 (L4), driver 595.71.05,
  Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0; clocks sampled during the timed regions.

## Scope

* Results are for Qwen3-0.6B-Base on the pinned toolchain; the session derives buffer and grid
  shapes from the checkpoint's own dimensions.
* The CUDA session is benchmark-verified on the hardware above. The shipped SDK serving path is
  Metal; the CI CUDA lane is compile-gated (no GPU on the builder). See
  [GPU support](../engine/gpu-support.md).

## Related

* [NVIDIA kernel benchmarks](nvidia-kernel-benchmarks.md) — the portable-kernel layer on T4/L4/A100.
* [GPU support](../engine/gpu-support.md) — the verification matrix.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — Metal prefill.
* [Decode throughput](decode-throughput.md) — Metal single-stream decode.
* [LLM inference overview](llm-inference-overview.md) — prefill and decode together on Apple silicon.
* [Benchmarks](overview.md) — methodology.
