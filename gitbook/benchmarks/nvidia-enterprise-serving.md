---
icon: server
description: Measured enterprise characteristics of the CUDA-native engine on NVIDIA A100, L4 and H100 — concurrent serving, single-stream decode, batched decode, prefill, cold start, VRAM, determinism.
---

# NVIDIA enterprise serving

Measured enterprise characteristics of the CUDA-native engine (Qwen3-0.6B-Base, greedy) on
NVIDIA A100-SXM4-40GB, L4 and H100 80GB HBM3, including concurrent-serving wins over
`llama-server` (f16) on the A100 and single-stream decode wins on all three GPUs.

## Single-stream decode

Resident session with arithmetic-packed-int8 weights (1.58 B/weight) and captured-graph
decode, against llama.cpp (build 10210 pin, GGML\_CUDA, F16) on the same machines:

| GPU | Decode tok/s (gen=64) | Decode tok/s (gen=256) | vs llama.cpp F16 |
| --- | --- | --- | --- |
| A100 | 427.1 | 408.7 | 1.20x / 1.11x |
| H100 | 656.1 | 622.3 | 1.40x / 1.19x |
| L4 | 191.1 | 184.8 | 1.12x / 1.07x |

Against llama.cpp Q8\_0 the packed3 session leads on the A100 at gen=64 (427.1 vs 404.2
tok/s, 1.055x) and on the H100 at both lengths (557.4 / 593.2 tok/s, 1.18x / 1.05x).

## Batched decode aggregate

32 sequences in flight, against `llama-server` at the same concurrency:

| Arm | B | A100 aggregate tok/s | L4 aggregate tok/s |
| --- | --- | --- | --- |
| Algenta captured-graph batched | 32 | 810.6 | 634.7 |
| `llama-server` (f16, q8\_0 KV), chat mix | 32 | 752.9 | 600.2 |

## Concurrent serving

Closed-loop concurrent serving on the A100, 64 requests per cell, greedy, against
`llama-server` (f16, `-ngl 99 --parallel 32 -c 163840`) fresh-verified in the same
session.

Chat mix (1024-in/256-out), C=8:

| Metric | Algenta | `llama-server` f16 | Lead |
| --- | --- | --- | --- |
| Aggregate tok/s | 625.8 | 608.7 | 1.03x |
| TTFT p50 ms | 506.8 | 642.8 | 1.27x faster |
| TPOT p50 ms | 9.9 | 11.1 | 1.12x faster |

Rag mix (4096-in/512-out), C=8:

| Metric | Algenta | `llama-server` f16 | Lead |
| --- | --- | --- | --- |
| Aggregate tok/s | 243.2 | 73.5 | 3.30x |
| TTFT p50 ms | 4,204.2 | 19,912.7 | 4.74x faster |

Chat TTFT p50 lead as concurrency scales:

| C | Algenta ms | `llama-server` ms | Lead |
| --- | --- | --- | --- |
| 16 | 524.7 | 666.3 | 1.27x faster |
| 32 | 641.1 | 879.8 | 1.37x faster |

## Prefill

256-token prompt, warm, 20-run medians: 3,260 tok/s vs llama.cpp F16 2,527 tok/s = 1.29x on
the A100. Full fixture tables: [NVIDIA LLM throughput](nvidia-llm-throughput.md).

## Cold start (process launch to first token, median of 3)

| Engine | A100 s | L4 s |
| --- | --- | --- |
| Algenta driver | 6.34 | 6.39 |
| vLLM 0.27.1 (0.6B) | 39.14 | 39.16 |

The single-binary driver cold-starts 6.2x faster than vLLM on both GPUs.

## VRAM footprint at C=32

| Engine | A100 MiB | L4 MiB |
| --- | --- | --- |
| Algenta driver | 5,038 | 4,804 |
| `llama-server` (`-c 163840`, q8\_0 KV) | 11,858 | 11,596 |
| vLLM 0.27.1 (0.6B) | 37,920 | 21,570 |

## Determinism

Greedy decoding is token-identical across fresh driver processes: 6/6 identical-prompt rounds
on both GPUs.

## Methodology

* Harness: `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` — closed-loop, warmup
  excluded, greedy (temperature 0) on every arm.
* Bench cells: 20 runs per cell, median, rel-IQR <= 5%. Cold start: median of 3 launches.
* Concurrent cells: 64 requests per cell, closed-loop, medians, rel-IQR <= 5%; gates
  16/16 oracle + 8/8 token-identity on every shipped build; packed3 batched decode,
  hybrid decode (per-dispatch under lane activity, captured graph otherwise), multi-stream
  admission prefill (2 streams for the TTFT cells, 4 streams for the aggregate and TPOT
  cells).
* Opponents: llama.cpp build 10210 pin, f16 GGUF, `-ngl 99`, `--parallel 32`, `-c 163840`,
  q8\_0 KV, readiness = `/health` plus one real completion; vLLM 0.27.1 with
  `VLLM_USE_FLASHINFER_SAMPLER=0`.
* Hardware: GCP `algenta-ent-a100` (A100-SXM4-40GB), `algenta-ent-l4` (L4) and
  `algenta-ent-h100` (a3-highgpu-8g, H100 80GB HBM3, sm\_90), us-central1-a, driver
  595.71.05, Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0; clocks pinned at 1410 MHz on the A100;
  H100 at sustained 1980 MHz boost with a solo-GPU census per timed window; L4 comparisons
  on fresh-boot solo runs.

## Related

* [NVIDIA LLM throughput](nvidia-llm-throughput.md) — fixture prefill and decode of the same
  session family.
* [GPU support](../engine/gpu-support.md) — the verification matrix.
* [NVIDIA kernel benchmarks](nvidia-kernel-benchmarks.md) — the portable-kernel layer.
* [LLM inference overview](llm-inference-overview.md) — prefill and decode together on Apple
  silicon.
* [Benchmarks](overview.md) — methodology.
