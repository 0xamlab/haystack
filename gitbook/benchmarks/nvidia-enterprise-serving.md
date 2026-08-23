---
icon: server
description: Measured enterprise characteristics of the CUDA-native engine on NVIDIA A100, L4 and H100 — concurrent serving, single-stream decode, batched decode, prefill, cold start, VRAM, determinism.
---

# NVIDIA enterprise serving

Measured enterprise characteristics of the CUDA-native engine (Qwen3-0.6B-Base, greedy) on
NVIDIA A100-SXM4-40GB, L4 and H100 80GB HBM3, including concurrent-serving wins over
`llama-server` (f16) on the A100 and H100 and single-stream decode wins on all three GPUs.

## Single-stream decode

Resident session with arithmetic-packed-int8 weights (1.58 B/weight) and captured-graph
decode, against llama.cpp (build 10210 pin, GGML\_CUDA, F16) on the same machines:

| GPU | Decode tok/s (gen=64) | Decode tok/s (gen=256) | vs llama.cpp F16 |
| --- | --- | --- | --- |
| A100 | 455.3 | 434.5 | 1.28x / 1.19x |
| H100 | 656.1 | 622.3 | 1.40x / 1.19x |
| L4 | 193.9 | 188.8 | 1.12x / 1.09x |

Against llama.cpp Q8\_0 the packed3 session leads on the A100 at both lengths (455.3 /
434.5 tok/s vs 404.2 / 420.0, 1.13x / 1.03x) and on the H100 at both lengths (557.4 /
593.2 tok/s, 1.18x / 1.05x).

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
| Aggregate tok/s | 617.6 | 594.7 | 1.04x |
| TTFT p50 ms | 507.4 | 638.6 | 1.26x faster |
| TPOT p50 ms | 10.6 | 11.4 | 1.08x faster |

Rag mix (4096-in/512-out), C=8:

| Metric | Algenta | `llama-server` f16 | Lead |
| --- | --- | --- | --- |
| Aggregate tok/s | 242.8 | 72.8 | 3.33x |
| TTFT p50 ms | 4,201.9 | 20,013.2 | 4.76x faster |

Chat TTFT p50 lead as concurrency scales:

| C | Algenta ms | `llama-server` ms | Lead |
| --- | --- | --- | --- |
| 16 | 531.8 | 672.0 | 1.26x faster |
| 32 | 643.8 | 868.8 | 1.35x faster |

### H100 concurrent serving

Same protocol on the H100 (C=8, gate-2-clean round-3 driver, fresh same-session
`llama-server` f16 at `-ngl 99 --parallel 32 -c 163840`):

| Mix | Metric | Algenta | `llama-server` f16 | Lead |
| --- | --- | --- | --- | --- |
| Chat C=8 | Aggregate tok/s | 1,044.1 | 902.4 | 1.16x |
| Chat C=8 | TTFT p50 ms | 286.2 | 345.1 | 1.21x faster |
| Chat C=8 | TPOT p50 ms | 6.3 | 7.1 | 1.13x faster |
| Rag C=8 | Aggregate tok/s | 399.4 | 143.8 | 2.78x |
| Rag C=8 | TTFT p50 ms | 2,423.4 | 5,463.9 | 2.25x faster |

The shipped concurrent configuration is the 2-stream arm; the 4-stream arm matched it in
the verification round.

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

## Cost (tokens per dollar)

On the L4 at the measured spot price ($0.512/h, g2-standard-8, us-central1-a), steady-state
single-stream decode costs $0.753 per million tokens with the packed3 session vs $0.823 with
llama.cpp F16 — 8.5% cheaper per token at equal or better throughput ($/Mtok = 142.226 /
tok/s at that price).

## Determinism

Greedy decoding is token-identical across fresh driver processes: 6/6 identical-prompt rounds
on both GPUs.

## Methodology

* Harness: `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` — closed-loop, warmup
  excluded, greedy (temperature 0) on every arm.
* Bench cells: 20 runs per cell, median, rel-IQR <= 5%. Cold start: median of 3 launches.
* Concurrent cells: 64 requests per cell, closed-loop, medians, rel-IQR <= 5%; gates
  16/16 oracle + 8/8 concurrent token-identity on every shipped build; packed3 batched
  decode, captured-graph decode running under in-flight admission lanes, multi-stream
  admission prefill (2 streams for the TTFT cells, 4 streams for the aggregate and TPOT
  cells). All concurrent cells were re-measured on the round-3 driver after the KV
  compaction addressing fix and re-gated 8/8.
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
