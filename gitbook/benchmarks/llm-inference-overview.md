---
icon: gauge-high
description: The full Algenta LLM-inference picture on Apple silicon — token-input prefill, single-stream decode, and batched decode for Qwen3-0.6B-Base, each benchmarked against real installed opponents.
---

# LLM inference overview

Algenta ships a compiled Metal kernel path that runs a real LLM (Qwen3-0.6B-Base) end to end on
Apple silicon — prompt in, tokens out, no server or sidecar. Inference has three distinct workloads,
each with a different bottleneck and its own benchmark here:

| Workload | What it is | Bottleneck | Result | Page |
| --- | --- | --- | --- | --- |
| **Prefill (token input)** | Read the whole prompt, build the KV cache | Compute (batched matmul) | ~10,700 tok/s, 1.049x llama.cpp | [Prefill throughput](llm-prefill-throughput.md) |
| **Decode (single-stream)** | Generate one token at a time, one request | Memory bandwidth (weight sweep/token) | Ahead of llama.cpp & mlx-lm at N>=16 | [Decode throughput](decode-throughput.md) |
| **Batched decode (continuous batching)** | Generate for B requests at once | Weight sweep amortized over B | 2.1-2.6x llama.cpp concurrent at B=8-32 | [Batched decode throughput](batched-decode-throughput.md) |

{% hint style="info" %}
**Measured on Apple M4 Max:** prefill 10,676-10,734 tok/s (llama.cpp 10,199); single-stream decode
leads at generation lengths >= 16; batched decode 2.1-2.6x llama.cpp at B=8-32, as the batched
path sweeps the weights once per step for all B sequences.
{% endhint %}

## Why the three workloads behave differently

* **Prefill** processes every prompt token together, so each projection is one wide
  `[m_rows, d_model] @ weights` matmul — compute-bound, scaling with GEMM tile quality.
* **Single-stream decode** generates one token per step, streaming the full model weights for
  each. Every engine sits near the same memory-bandwidth floor; Algenta leads at generation
  lengths >= 16.
* **Batched decode** steps B sequences per step. The weights are swept once but produce B tokens,
  so the per-token weight cost falls with B — the structural way off the single-stream floor for
  any serving workload with more than one request in flight.

## Cross-cutting properties

* **Any token count.** The prefill path re-grids per call (padded-destination contract), so prompts
  and batches of any size work, not just the measured 256 / B values. Context auto-raises past the
  historical 512 default up to a 65,536 ceiling — deep soaks verified at 2,048 new tokens (0.6B)
  and 1,024 (1.7B), every token reference-checked.
* **Model-agnostic within the Qwen3 family.** Buffer and grid shapes are derived from the
  checkpoint's own dims. Verified end-to-end on Qwen3-0.6B-Base and Qwen3-1.7B with identical greedy
  output (first token matches an independent `transformers` CPU reference) — runnable through the
  SDK's model-agnostic path, see [Model-agnostic LLM
  inference](../guides/run-qwen3-family-inference.md).
* **Cached weight loading.** The one-shot SDK shape persists the exact post-quantization device
  bytes next to each converted checkpoint; second-and-later calls load ~8x fewer bytes and skip
  quantization entirely (3.10x / 1.93x whole-call wall on 0.6B / 1.7B), token-identical to the
  uncached path.
* **Correctness-gated.** Every path checks generated tokens against a reference before any number
  is reported.

## Related

* [Prefill throughput](llm-prefill-throughput.md) — token-input processing.
* [Decode throughput](decode-throughput.md) — single-stream generation vs llama.cpp & mlx-lm.
* [Batched decode throughput](batched-decode-throughput.md) — continuous batching.
* [Metal LLM decode](../engine/qwen3-metal-decode.md) — call it from Python.
* [GPU support](../engine/gpu-support.md) — which GPU lanes are run-verified, and what that covers.
* [NVIDIA LLM throughput](nvidia-llm-throughput.md) — CUDA-native session numbers on A100/L4.
* [Run local LLM decode](../guides/run-qwen3-decode.md) — step-by-step guide.
* [Model-agnostic LLM inference](../guides/run-qwen3-family-inference.md) — the model-agnostic SDK path (0.6B, 1.7B, and other supported shapes).
* [Benchmarks](overview.md) — methodology.
