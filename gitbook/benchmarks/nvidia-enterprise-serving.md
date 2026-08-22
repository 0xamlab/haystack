---
icon: server
description: Measured enterprise characteristics of the CUDA-native engine on NVIDIA A100 and L4 — single-stream decode, batched decode aggregate, prefill, cold start, VRAM footprint, determinism.
---

# NVIDIA enterprise serving

This page reports measured enterprise characteristics of the CUDA-native engine
(Qwen3-0.6B-Base, greedy) on NVIDIA A100-SXM4-40GB and L4. Concurrent-serving numbers are
in qualification with the continuous-batching driver and will be published on qualification.

## Single-stream decode (packed3 captured graph)

Resident session with arithmetic-packed-int8 weights (1.58 B/weight) and captured-graph
decode, against llama.cpp (build 10210 pin, GGML\_CUDA) on the same machines:

| GPU | Decode tok/s (gen=64) | Decode tok/s (gen=256) | vs llama.cpp F16 | vs llama.cpp Q8\_0 (gen=64) |
| --- | --- | --- | --- | --- |
| A100 | 427.1 | 408.7 | 1.20x / 1.11x | 1.055x |
| L4 | 191.1 | 184.8 | 1.12x / 1.07x | — |

Method: 20-run medians, rel-IQR <= 5%, greedy, solo-GPU census during every timed window;
clocks pinned at 1410 MHz on the A100; L4 comparisons on fresh-boot solo runs (the L4 is
DVFS-sensitive). Full fixture tables: [NVIDIA LLM throughput](nvidia-llm-throughput.md).

## Batched decode aggregate

Decode with B sequences in flight (synchronized batch; prefill outside the timed window),
against `llama-server` serving aggregate at the same concurrency:

| Arm | B | A100 aggregate tok/s | L4 aggregate tok/s |
| --- | --- | --- | --- |
| Algenta captured-graph batched | 32 | 810.6 | 634.7 |
| `llama-server` (f16, q8\_0 KV), chat mix | 32 slots | 752.9 | 600.2 |

## Prefill

Fixture (256-token prompt, warm, 20-run medians): 3,260 tok/s vs llama.cpp F16 2,527 tok/s
= 1.29x on the A100. Full table and methodology: [NVIDIA LLM
throughput](nvidia-llm-throughput.md).

## Cold start (process launch to first token, median of 3)

| Engine | A100 s | L4 s |
| --- | --- | --- |
| Algenta driver | 6.34 | 6.39 |
| vLLM 0.27.1 (0.6B) | 39.14 | 39.16 |

The single-binary driver cold-starts 6.2x faster than vLLM on both GPUs.

## VRAM footprint at C=32 (nvidia-smi, 500 ms sampling)

| Engine | A100 MiB | L4 MiB |
| --- | --- | --- |
| Algenta driver | 5,038 | 4,804 |
| `llama-server` (`-c 163840`, q8\_0 KV) | 11,858 | 11,596 |
| vLLM 0.27.1 (0.6B) | 37,920 | 21,570 |

The driver holds the resident session plus KV in 5 GB; vLLM reserves ~90% of the card by
design (`--gpu-memory-utilization` defaults to 0.9).

## Determinism (greedy, two fresh processes per round, 6 identical-prompt rounds)

* Algenta driver: 6/6 token-identical on A100 and L4.
* `llama-server`: 6/6 token-identical on both GPUs at temperature 0.

## In qualification

* Concurrent OpenAI-compatible serving with the continuous-batching driver (request path
  over the batched decode stack above); TTFT/TPOT percentiles and aggregate throughput at
  concurrency 1-32 will be published on qualification.
* Qwen2.5-7B / Llama-3.1-8B driver lanes.

## Methodology

* Harness: `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` — closed-loop, warmup
  excluded, greedy (temperature 0) on every arm.
* Bench cells: 20 runs per cell, median, rel-IQR <= 5%. Cold start: median of 3 launches.
* Opponents: llama.cpp build 10210 pin, f16 GGUF, `-ngl 99`, `--parallel 32`, `-c 163840`,
  q8\_0 KV, readiness = `/health` plus one real completion; vLLM 0.27.1 with
  `VLLM_USE_FLASHINFER_SAMPLER=0`.
* Hardware: GCP `algenta-ent-a100` (A100-SXM4-40GB) and `algenta-ent-l4` (L4),
  us-central1-a, driver 595.71.05, Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0.
* Solo-GPU runs: a gpuwatch census recorded exactly one PID on each GPU during every timed
  window.

## Scope

* Results are for Qwen3-0.6B-Base; 7B-class driver lanes are in qualification.
* H100/FP8 datacenter lanes are not pursued; the pinned toolchain exposes no tensor-core
  surface.

## Related

* [NVIDIA LLM throughput](nvidia-llm-throughput.md) — fixture prefill and decode of the same
  session family.
* [GPU support](../engine/gpu-support.md) — the verification matrix.
* [NVIDIA kernel benchmarks](nvidia-kernel-benchmarks.md) — the portable-kernel layer.
* [LLM inference overview](llm-inference-overview.md) — prefill and decode together on Apple
  silicon.
* [Benchmarks](overview.md) — methodology.
