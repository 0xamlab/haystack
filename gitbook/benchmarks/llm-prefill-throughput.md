---
icon: arrow-right-to-bracket
description: Prompt prefill (token-input) throughput for Qwen3-0.6B-Base on Apple silicon — Algenta processes a 256-token prompt at ~10,700 tok/s, ahead of llama.cpp's ~10,199 and 1.15x its own prior baseline, on any prompt length.
---

# Prefill (token input) throughput

Prefill is the token-input half of inference: the model reads the whole prompt at once and builds
the KV cache, before any token is generated. Unlike decode (one token at a time, memory-bandwidth
bound), prefill is a batched matmul over every prompt token — compute-bound, and the place where a
well-tiled GPU kernel path pulls far ahead of a per-token loop. This page measures that rate for one
real checkpoint against llama.cpp on the same machine.

{% hint style="success" %}
**Algenta prefills a 256-token prompt at ~10,700 tok/s (23.9 ms end-to-end), 1.049x llama.cpp's
~10,199 tok/s fast regime and 1.15x its own prior pinned baseline.** The same kernel path handles
**any prompt length** (not just 256) and is **model-agnostic** — verified on both Qwen3-0.6B-Base
and Qwen3-1.7B with identical greedy output.
{% endhint %}

## Results

256-token prompt prefill, tokens per second, Apple M4 Max, resident session (weights uploaded once),
greedy. Algenta is the no-mirror + MSL-parity-GEMM + split-K path:

| Arm | Wall (ms) | Prefill tok/s | vs Algenta |
| --- | --- | --- | --- |
| **Algenta** (no-mirror + MSL + split-K) | **23.85 - 23.98** | **10,676 - 10,734** | 1.000x |
| llama.cpp (build 10210), fast regime | 25.10 | 10,199 | 1.049x faster |
| Algenta prior pinned baseline | 27.55 | 9,291.7 | 1.149x faster |

Fresh-process (cold start, warm-up prefills included) reproduces the resident number: 10,698.8 tok/s
(0.59% rel-IQR, PASS) — so the result is not an artifact of a long-lived warm session.

### Any prompt length, any Qwen3 model

* **Any token count.** The prefill GEMM path uses a padded-destination contract plus a per-call
  `m_rows` re-grid, so it runs prompts of any length, not only the 256 measured here (gated at
  m_rows 1 / 17 / 127 / 256 / 257 / 512 — ragged and past the tile boundary included).
* **Model-agnostic.** The entry point derives every buffer and grid from the checkpoint's own dims
  (never hardcoded to one model). Verified end-to-end on **Qwen3-0.6B-Base** and **Qwen3-1.7B**:
  the split-K GEMM path is byte-identical-on/off for the generated sequence on both, and the first
  generated token matches an independent `transformers` CPU-fp32 reference.

## What makes it fast

* **Batched matmul prefill, not a per-token loop.** The whole prompt is one `[m_rows, d_model] @
  weights` multiply per projection, sweeping each weight matrix once for all prompt tokens.
* **Hand-written MSL GEMMs at the hardware wall.** The four projection roles run Metal kernels
  measured at ~12.9 TFLOP/s, ~92% of the M4 Max simdgroup-MMA ceiling (13.3 TFLOP/s).
* **Split-K GPU-fill for narrow projections.** `o_proj`/`down_proj` (few output columns, few
  threadgroups) split the K dimension across more threadgroups with an atomic-float-add epilogue,
  lifting them to the wall instead of leaving cores idle.
* **No-mirror native-packed KV.** The prefill writes the packed-F16 KV cache directly (no second
  "mirror" pass), which decode then reads.

## Method

* **Checkpoint.** `Qwen/Qwen3-0.6B-Base` (and separately `Qwen3-1.7B`), real Hugging Face
  checkpoints, unmodified.
* **Prompt.** The fixed 256-token race prompt; greedy (temperature 0 / argmax).
* **What is timed.** The `prefill_batch` call that processes all 256 prompt tokens and yields the
  first generated token — weight load excluded (resident session).
* **Opponent.** llama.cpp build 10210 (Homebrew, Metal), its fast-regime prefill number.
* **Statistics.** 20 runs per cell, median, rel-IQR <= 5%, outliers dropped only if >=16/20 remain.
* **Hardware.** Apple M4 Max, integrated GPU via Apple Metal.

## What is not claimed

* **One checkpoint family.** Measured on Qwen3-0.6B-Base and Qwen3-1.7B. Other model families are
  not part of this page (the path is Qwen3-shaped).
* **Prefill only.** This page measures prompt processing. Generation speed is
  [decode throughput](decode-throughput.md) (single-stream) and
  [batched decode throughput](batched-decode-throughput.md) (many sequences).
* **Not a training or fine-tuning claim.** Inference prefill only.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode together.
* [Decode throughput](decode-throughput.md) — single-stream generation.
* [Batched decode throughput](batched-decode-throughput.md) — continuous batching.
* [Qwen3 Metal decode](../engine/qwen3-metal-decode.md) — the kernel path.
* [Benchmarks](overview.md) — methodology and what is not published.
