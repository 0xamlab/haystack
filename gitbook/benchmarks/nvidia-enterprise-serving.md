---
icon: server
description: Measured enterprise serving of the CUDA-native driver on NVIDIA A100 and L4 — TTFT, TPOT and aggregate tok/s vs llama.cpp and vLLM at concurrency 1–32, batch decode, cold start, VRAM, determinism.
---

# NVIDIA enterprise serving

This page reports measured serving behavior of the CUDA-native serving driver
(Qwen3-0.6B-Base, greedy) on NVIDIA A100-SXM4-40GB and L4, against llama.cpp `llama-server`
(build 10210 pin) and vLLM 0.27.1 on the same machines. The serving driver is a batch-1
resident session; batched decode is measured with the bench arms in a separate section.

## Results

### Serving concurrency — chat mix (1k-in/256-out, 64 requests per cell)

Driver TTFT is driver-reported service time (stdin read to first token, queue wait excluded);
`llama-server` and vLLM TTFT is harness-measured wall time and includes queue wait. Driver
aggregate tok/s does not scale with concurrency; its concurrency columns show queueing
latency, not parallelism.

#### A100-SXM4-40GB

| Engine | C | TTFT p50/p90/p99 ms | TPOT p50/p99 ms | Aggregate tok/s |
| --- | --- | --- | --- | --- |
| Algenta driver (batch-1) | 1 | 538.6 / 539.3 / 540.0 | 48.41 / 48.69 | 19.9 |
| Algenta driver (batch-1) | 8 | 538.9 / 539.3 / 539.6 | 48.44 / 48.75 | 19.9 |
| Algenta driver (batch-1) | 16 | 538.7 / 539.3 / 539.7 | 48.43 / 48.78 | 19.9 |
| Algenta driver (batch-1) | 32 | 538.9 / 539.4 / 539.9 | 48.45 / 48.72 | 19.9 |
| `llama-server` (f16, q8\_0 KV) | 1 | 115.0 / 118.0 / 119.0 | 3.6 / 3.6 | 249.1 |
| `llama-server` (f16, q8\_0 KV) | 8 | 446.5 / 827.9 / 888.9 | 11.1 / 16.9 | 573.6 |
| `llama-server` (f16, q8\_0 KV) | 16 | 465.3 / 717.7 / 1203.3 | 22.1 / 27.5 | 634.6 |
| `llama-server` (f16, q8\_0 KV) | 32 | 689.2 / 1317.4 / 1544.1 | 39.9 / 45.2 | 752.9 |
| vLLM 0.27.1 | 1 | 26.4 / 27.1 / 30.4 | 2.4 / 2.4 | 401.5 |
| vLLM 0.27.1 | 8 | 79.5 / 91.4 / 103.3 | 3.5 / 3.6 | 2114.2 |
| vLLM 0.27.1 | 16 | 94.0 / 137.1 / 153.1 | 4.4 / 4.6 | 3356.2 |
| vLLM 0.27.1 | 32 | 102.1 / 282.4 / 320.0 | 6.6 / 6.7 | 4542.4 |

vLLM reference rows for Qwen2.5-7B-Instruct (the driver 7B lane is not built):

| Engine | C | TTFT p50/p90/p99 ms | TPOT p50/p99 ms | Aggregate tok/s |
| --- | --- | --- | --- | --- |
| vLLM 0.27.1 (7B) | 1 | 77.4 / 78.2 / 78.6 | 12.4 / 12.4 | 78.7 |
| vLLM 0.27.1 (7B) | 8 | 89.1 / 151.3 / 359.9 | 14.2 / 14.7 | 528.5 |
| vLLM 0.27.1 (7B) | 16 | 92.1 / 520.0 / 781.3 | 16.6 / 18.3 | 821.5 |
| vLLM 0.27.1 (7B) | 32 | 249.5 / 1405.2 / 1679.1 | 20.2 / 25.9 | 1232.1 |

#### L4

| Engine | C | TTFT p50/p90/p99 ms | TPOT p50/p99 ms | Aggregate tok/s |
| --- | --- | --- | --- | --- |
| Algenta driver (batch-1) | 1 | 702.7 / 708.6 / 710.2 | 44.94 / 45.15 | 21.0 |
| Algenta driver (batch-1) | 8 | 702.9 / 707.1 / 708.9 | 44.96 / 45.20 | 21.0 |
| Algenta driver (batch-1) | 16 | 702.5 / 706.6 / 710.8 | 44.96 / 45.23 | 21.0 |
| Algenta driver (batch-1) | 32 | 681.0 / 692.5 / 699.3 | 44.93 / 45.14 | 21.1 |
| `llama-server` (f16, q8\_0 KV) | 1 | 127.0 / 130.4 / 132.1 | 6.6 / 6.7 | 141.1 |
| `llama-server` (f16, q8\_0 KV) | 8 | 520.0 / 616.4 / 684.7 | 15.9 / 23.9 | 408.1 |
| `llama-server` (f16, q8\_0 KV) | 16 | 569.5 / 1005.7 / 1536.8 | 29.9 / 37.2 | 475.5 |
| `llama-server` (f16, q8\_0 KV) | 32 | 889.4 / 1950.2 / 2299.5 | 49.6 / 55.5 | 600.2 |
| vLLM 0.27.1 | 1 | 29.2 / 30.6 / 31.3 | 6.2 / 6.2 | 159.4 |
| vLLM 0.27.1 | 8 | 110.2 / 151.5 / 177.7 | 9.9 / 10.3 | 773.9 |
| vLLM 0.27.1 | 16 | 161.0 / 269.4 / 402.5 | 14.9 / 15.4 | 1031.8 |
| vLLM 0.27.1 | 32 | 275.4 / 735.9 / 887.4 | 23.9 / 24.4 | 1285.2 |

### Serving concurrency — rag mix (4k-in/512-out), C=8

| GPU | Engine | TTFT p50/p90/p99 ms | TPOT p50/p99 ms | Aggregate tok/s |
| --- | --- | --- | --- | --- |
| A100 | Algenta driver (batch-1) | 5118.0 / — / — | 175.4 / — | 5.4 |
| A100 | `llama-server` (f16, q8\_0 KV) | 816.6 / 1191.8 / 1564.4 | 15.4 / 16.4 | 476.6 |
| A100 | vLLM 0.27.1 | 123.0 / 155.3 / 210.2 | 5.5 / 5.6 | 1401.7 |
| L4 | Algenta driver (batch-1) | 7099.4 / — / — | 142.1 / — | 6.4 |
| L4 | `llama-server` (f16, q8\_0 KV) | 679.9 / 1552.1 / 2140.2 | 26.6 / 27.5 | 288.1 |
| L4 | vLLM 0.27.1 | 294.4 / 417.9 / 796.8 | 21.1 / 21.5 | 368.4 |

Driver rag rows carry p50 only. On a batch-1 driver the closed-loop queue waits exceed the
harness default 600 s per-request deadline at C=8, so the rag cells ran with a 3600 s
per-request deadline. The driver rag row at C=32 is pending a known-issue fix; see Scope.

### Batched decode (bench arms)

Decode-only bench cells with B sequences in flight; prefill runs outside the timed window.

| Arm | B | A100 aggregate tok/s | L4 aggregate tok/s |
| --- | --- | --- | --- |
| Algenta per-dispatch batched (W1) | 32 | 802.4 | 633.5 |
| Algenta captured-graph batched (W2) | 32 | 810.6 | 634.7 |
| `llama-server` serving aggregate, chat mix, C=32 | 32 slots | 752.9 | 600.2 |

* The W1/W2 rows are bench-batch numbers (synchronized batch, no request path); the
  `llama-server` row is the serving aggregate from the matrix above. The comparison is
  bench-batch vs server slots.
* The batched stack is bench-only today; the serving driver is batch-1 (see Scope).

### Single-stream decode (packed3 captured graph)

The packed3 resident session with captured-graph decode, against the llama.cpp controls from
[NVIDIA LLM throughput](nvidia-llm-throughput.md):

| GPU | Decode tok/s (gen=64) | Decode tok/s (gen=256) | vs llama.cpp F16 | vs llama.cpp Q8\_0 |
| --- | --- | --- | --- | --- |
| A100 | 420.8 | 402.4 | 1.18x / 1.10x | 1.04x / 0.96x |
| L4 | 191.1 | 184.8 | 1.12x / 1.07x | 0.73x / 0.69x |

### Prefill

* Fixture (256-token prompt, warm, 20-run medians): 3,260 tok/s vs llama.cpp F16
  2,527 tok/s = 1.29x. Full table and methodology: [NVIDIA LLM
  throughput](nvidia-llm-throughput.md).
* Serving TTFT context at C=1 on the A100: driver chat TTFT 538.6 ms (f32 v2 prefill,
  batch-1) vs `llama-server` 115.0 ms vs vLLM 26.4 ms.

### Cold start (process launch to first token, median of 3)

| Engine | A100 s | L4 s |
| --- | --- | --- |
| Algenta driver | 6.34 | 6.39 |
| `llama-server` | 1.82 | 1.84 |
| vLLM 0.27.1 (0.6B) | 39.14 | 39.16 |

The driver cold start is 6.2x faster than vLLM on both GPUs.

### VRAM peaks at C=32 (nvidia-smi, 500 ms sampling)

| Engine | A100 MiB | L4 MiB |
| --- | --- | --- |
| Algenta driver | 5,038 | 4,804 |
| `llama-server` (`-c 163840`, q8\_0 KV) | 11,858 | 11,596 |
| vLLM 0.27.1 (0.6B) | 37,920 | 21,570 |

vLLM reserves ~90% of the card by design (`--gpu-memory-utilization` defaults to 0.9).

### Determinism (greedy, two fresh processes per round, 6 identical-prompt rounds)

* Algenta driver: 6/6 token-identical on A100, 6/6 on L4.
* `llama-server`: 6/6 token-identical on both GPUs at temperature 0.

## Methodology

* Harness: `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` — closed-loop, 64 requests
  per cell, warmup excluded, greedy (temperature 0) on every arm.
* Mixes: chat ~1k tokens in / 256 out; rag 4,096 in / 512 out.
* Bench arms (batched decode, single-stream decode, prefill fixture): 20 runs per cell,
  median, rel-IQR <= 5%. Cold start: median of 3 process launches.
* Opponents: llama.cpp build 10210 pin, f16 GGUF, `-ngl 99`, `--parallel 32`, `-c 163840`,
  q8\_0 KV cache, readiness = `/health` plus one real completion; vLLM 0.27.1 with
  `VLLM_USE_FLASHINFER_SAMPLER=0`.
* Models: Qwen3-0.6B-Base on all three engines; the Qwen2.5-7B-Instruct rows are vLLM
  reference rows only.
* Hardware: GCP `algenta-ent-a100` (A100-SXM4-40GB) and `algenta-ent-l4` (L4),
  us-central1-a, driver 595.71.05, Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0.
* Solo-GPU runs: a gpuwatch census recorded exactly one PID on each GPU during every timed
  window.
* Clocks: pinned at 1410 MHz on the A100. The L4 is DVFS-sensitive — post-load runs measured
  2.1-2.4x slower than fresh-boot runs — so all reported L4 comparisons use fresh-boot solo
  runs.

## Scope

* The serving driver is batch-1 resident: aggregate throughput does not scale with
  concurrency, and the batched decode stack is bench-only today.
* Aggregate throughput at C >= 8 loses to vLLM (tensor-core prefill and continuous batching).
* TTFT loses to both opponents' warm servers.
* The driver rag row at C=32 is pending a known-issue fix (reproducible deadlock of the
  resident session under a 32-deep backlog).
* Qwen2.5-7B-Instruct is served only via the vLLM reference rows; the driver 7B lane is not
  built.
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
