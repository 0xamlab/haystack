---
icon: gauge-high
description: Measured LLM inference throughput of the CUDA-native session on NVIDIA A100 and L4 — Qwen3-0.6B and Qwen2.5-7B prefill and decode against llama.cpp, vLLM, SGLang and TensorRT-LLM, with methodology.
---

# NVIDIA LLM throughput

This page reports measured throughput of the CUDA-native resident session on
NVIDIA A100-SXM4-40GB and L4, against llama.cpp built with GGML\_CUDA on the same
machines: Qwen3-0.6B-Base (packed-int8 weights, f32 prefill) vs the F16 GGUF, and
Qwen2.5-7B-Instruct (packed-int8 weights, tensor-core prefill) vs the Q8\_0 GGUF and
vs vLLM and SGLang serving the same Hugging Face checkpoint.

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
| Algenta (packed3, cuBLAS tensor-core prefill + tensor-core attention, one-pass) | 10,595 | 12,255 |
| llama.cpp Q8\_0 | 4,680 | 5,089.1 |

Prefill speedup: 2.26x at 256 tokens, 2.41x at 1024 tokens.

### A100-SXM4-40GB — Qwen2.5-7B-Instruct, 256-token server TTFT

The same 256-token race prompt served over HTTP, measured as time-to-first-token
(streaming, greedy, one generated token). No cross-request prompt reuse on any engine;
each server is started fresh and the GPU is drained between engines. Median of 20 runs
(Algenta) / 7 runs (opponents), warmup runs excluded; rel-IQR <= 1% on every cell.

| Engine | TTFT (256 tokens) | Prefill tok/s |
| --- | --- | --- |
| Algenta (packed3, cuBLAS tensor-core prefill + tensor-core attention) | 24.2 ms | 10,595 |
| vLLM 0.27.1 (bfloat16) | 27.1 ms | 9,451 |
| SGLang 0.5.18 (bfloat16) | 34.6 ms | 7,395 |
| llama.cpp Q8\_0 | 57.8 ms | 4,430 |

TTFT speedup at 256 tokens: 1.12x vs vLLM, 1.43x vs SGLang, 2.39x vs llama.cpp Q8\_0.
The Algenta cell is the resident-session measurement (no HTTP layer); its prefill rate
reproduces the pinned-protocol table above within 0.4%.

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
  (f16 inputs, f32 accumulate and output), and the prompt runs through the attention pass
  in a single M-parallel sweep. Attention runs the same tensor-core path: QK^T and PV as
  strided-batched cuBLAS HMMA GEMMs (batched over the KV heads — the grouped-query heads
  ride each batch), a masked softmax between, Q packed head-major f16 with the attention
  scale folded into the pack; the dispatch is shape-fact-gated on the tile row count.
  Same 16/16 greedy-token oracle as every build, plus cross-engine token identity on five
  chat prompts.
* Decode: arithmetic-packed-int8 weights (1.58 B/weight) with captured-graph decode — zero
  per-token host traffic, split-K flash-decoding (32 splits), warp-shuffle attention
  reduction, fused gate/up SwiGLU. Bit-identical to the f32 session (16/16 greedy oracle on
  every build).

## Methodology

* Checkpoints: `Qwen/Qwen3-0.6B-Base` and `Qwen/Qwen2.5-7B-Instruct` (Hugging Face,
  unmodified; the 7B conversion preserves the q/k/v attention biases; the server engines
  serve the same 7B checkpoint files). Workload: fixed
  256-token prompt, greedy (temperature 0); the 7B page adds a 1024-token cell (the race
  prompt repeated x4 — prefill throughput is content-agnostic) and a server TTFT cell
  (streaming time-to-first-token on the 256-token prompt). The 7B oracle is a fp32 CPU
  transformers reference with repetition\_penalty pinned at 1.0.
* Opponent: llama.cpp pinned at 000547513f, GGML\_CUDA, same VM; F16 GGUF for 0.6B, Q8\_0
  GGUF for 7B; fixture via `llama-completion -no-cnv`, prefill cells via `llama-bench`.
  7B server opponents: vLLM 0.27.1 and SGLang 0.5.18, both bfloat16 (the checkpoint
  dtype) with prompt caching disabled (prefix caching / radix cache), vLLM served with
  `--dtype auto` on the same checkpoint; SGLang fed the exact race-prompt token ids.
  Servers run one at a time, are killed between engines, and every timed window is
  solo-GPU.
* Statistics: median per cell (20 runs for the Algenta fixture cells, 7 runs for the
  server cells, warmup excluded), rel-IQR <= 5%; a 16/16 greedy-token oracle gates every
  build before measurement; an optimization variant is recorded only after its bench number
  moves over baseline.
* Hardware: GCP a2-highgpu-1g (A100-SXM4-40GB) and g2-standard-8 (L4), driver 595.71.05,
  Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0; solo-GPU census during every timed window; clocks
  pinned at 1410 MHz on the A100; L4 comparisons on fresh-boot solo runs.

## Apples-to-apples parity re-runs (2026-08-26)

Full-protocol re-measurement with precision and protocol parity held constant: same
quantization class on both sides, open-loop arrivals, greedy decoding, prompt caching
disabled on every engine that has it, CUDA graphs enabled on every engine that has them,
clocks pinned at 1410 MHz, drift armor <= 0.15%.

### Gemma 3 27B — time-to-first-token under C=50 open-loop load (H100)

| Engine | TTFT p50 (ms) |
|---|---|
| algenta | 134 |
| vLLM 0.27.1 | 2,267 |
| SGLang 0.5.18 | 2,578 |
| llama-server F16 | 5,764 |

TTFT speedup under 50-way open-loop load: 16.9x vs vLLM, 19.2x vs SGLang, 43.0x vs
llama-server at equal precision.

### Qwen2.5-7B — equal-quantization prefill (A100)

| Cell | algenta packed-int8 | llama-server Q8\_0 | Speedup |
|---|---|---|---|
| 256-token prefill | 10,639 tok/s | 4,436 tok/s | 2.40x |
| 1024-token prefill | 12,333 tok/s | 5,069 tok/s | 2.43x |

Equal-quantization (int8 vs int8) prefill speedup: 2.40x / 2.43x at 256 / 1024 tokens,
with greedy first-token identity verified against the fp32 oracle on both engines.

### Qwen2.5-7B — prefill and decode vs TensorRT-LLM (A100)

Same-session re-measurement against TensorRT-LLM 1.2.1 (NVCR release container, PyTorch
backend, bfloat16 weights, Hugging Face checkpoint loaded directly, KV-cache and prefix
block reuse disabled, CUDA graphs at engine defaults). Engine-internal timings on both
sides (no HTTP layer); clocks pinned at 1410 MHz; greedy decoding; token counts verified
server-side; median of 20 runs (Algenta) / 7 runs (TensorRT-LLM); rel-IQR <= 4.7% on all
cells; greedy continuations match the fp32 oracle on both engines.

| Engine | Prefill 256 tok/s | Decode tok/s (gen=256) |
| --- | --- | --- |
| Algenta (packed3, cuBLAS tensor-core prefill + tensor-core attention) | 10,751 | 82.8 |
| TensorRT-LLM 1.2.1 (bfloat16, PyTorch backend) | 7,846 | 79.0 |

Prefill speedup at 256 tokens: 1.37x vs TensorRT-LLM. Decode speedup (gen=256): 1.05x vs
TensorRT-LLM.

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
