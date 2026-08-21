---
icon: arrow-right-to-bracket
description: Prompt prefill (token-input) throughput for Qwen3-0.6B-Base on Apple silicon — a 256-token prompt at ~10,700 tok/s, ahead of llama.cpp's ~10,199, on any prompt length.
---

# Prefill (token input) throughput

Prefill is the token-input half of inference: the model reads the whole prompt at once and builds
the KV cache, before any token is generated. Unlike decode (one token at a time, memory-bandwidth
bound), prefill is a batched matmul over every prompt token — compute-bound, and the place where a
well-tiled GPU kernel path pulls far ahead of a per-token loop. This page measures that rate for one
real checkpoint against llama.cpp on the same machine.

{% hint style="info" %}
**Algenta prefills a 256-token prompt at 10,676-10,734 tok/s (23.85-23.98 ms) on Apple M4 Max;
llama.cpp measures 10,199 tok/s on the same machine (1.05x).** The kernel path handles any prompt
length and is verified on Qwen3-0.6B-Base and Qwen3-1.7B with identical greedy output.
{% endhint %}

## Results

256-token prompt prefill, tokens per second, Apple M4 Max, resident session (weights uploaded once),
greedy. Algenta is the no-mirror + MSL-parity-GEMM + split-K path:

| Arm | Wall (ms) | Prefill tok/s | Algenta / arm |
| --- | --- | --- | --- |
| **Algenta** (no-mirror + MSL + split-K) | **23.85 - 23.98** | **10,676 - 10,734** | 1.000x |
| llama.cpp (build 10210), fast regime | 25.10 | 10,199 | 1.049x |
| Algenta prior pinned baseline | 27.55 | 9,291.7 | 1.149x |

A fresh process (cold start, warm-up prefills included) reproduces the resident number:
10,698.8 tok/s (0.59% rel-IQR).

### Any prompt length, any Qwen3 model

* **Any token count.** The prefill GEMM path uses a padded-destination contract plus a per-call
  `m_rows` re-grid, so it runs prompts of any length, not only the 256 measured here (gated at
  m_rows 1 / 17 / 127 / 256 / 257 / 512 — ragged and past the tile boundary included).
* **Model-agnostic.** The entry point derives every buffer and grid from the checkpoint's own dims
  (never hardcoded to one model). Verified end-to-end on **Qwen3-0.6B-Base** and **Qwen3-1.7B**:
  the split-K GEMM path is byte-identical-on/off for the generated sequence on both, and the first
  generated token matches an independent `transformers` CPU-fp32 reference.

## Implementation notes

* **Batched matmul prefill.** The whole prompt is one `[m_rows, d_model] @ weights` multiply per
  projection, sweeping each weight matrix once for all prompt tokens.
* **MSL GEMMs at 92% of the MMA ceiling.** The four projection roles run Metal kernels measured
  at ~12.9 TFLOP/s against the M4 Max simdgroup-MMA ceiling of 13.3 TFLOP/s.
* **Split-K for narrow projections.** `o_proj`/`down_proj` split the K dimension across more
  threadgroups with an atomic-float-add epilogue.
* **No-mirror native-packed KV.** The prefill writes the packed-F16 KV cache directly, and decode
  reads it.

## Method

* **Checkpoint.** `Qwen/Qwen3-0.6B-Base` (and separately `Qwen3-1.7B`), real Hugging Face
  checkpoints, unmodified.
* **Prompt.** The fixed 256-token race prompt; greedy (temperature 0 / argmax).
* **What is timed.** The `prefill_batch` call that processes all 256 prompt tokens and yields the
  first generated token — weight load excluded (resident session).
* **Opponent.** llama.cpp build 10210 (Homebrew, Metal), its fast-regime prefill number.
* **Statistics.** 20 runs per cell, median, rel-IQR <= 5%, outliers dropped only if >=16/20 remain.
* **Hardware.** Apple M4 Max, integrated GPU via Apple Metal.

## Scope

* Measured on Qwen3-0.6B-Base and Qwen3-1.7B; the path is Qwen3-shaped.
* Prefill only. Generation speed is on [decode throughput](decode-throughput.md) (single-stream)
  and [batched decode throughput](batched-decode-throughput.md) (many sequences).
* Inference only; no training or fine-tuning results.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode together.
* [Decode throughput](decode-throughput.md) — single-stream generation.
* [Batched decode throughput](batched-decode-throughput.md) — continuous batching.
* [Metal LLM decode](../engine/qwen3-metal-decode.md) — the kernel path.
* [GPU support](../engine/gpu-support.md) — the lane-by-lane verification matrix.
* [Benchmarks](overview.md) — methodology.
