---
icon: stopwatch
description: Large-token load test of the Algenta Apple-silicon engine vs llama.cpp and MLX-LM — prefill and decode throughput at 1K-8K-token prompts and 512-4096-token generations, single-stream.
---

# LLM large-token load testing

A serving-load measurement across the three serious Apple-Silicon engines, at the token volumes real
workloads actually use. The single-request race numbers elsewhere in this section measure a 256-token
prompt — the fast, GEMM-bound regime. This page measures the other regime: prompts of 1,024 to 8,192
tokens and generations of 512 to 4,096 tokens, where attention over a deep KV cache becomes the
dominant cost. Same machine, same checkpoint, same greedy rule, each engine at its native weight
precision.

## Results

Qwen3-0.6B-Base, Apple M4 Max, resident weights, greedy; median of two rotating-order passes.
**Prefill tok/s / decode tok/s** per engine per cell.

**Input scaling** (generation fixed at 512 tokens):

| Input tokens | Context | Algenta pf/dc | llama.cpp F16 pf/dc | MLX-LM bf16 pf/dc |
| --- | --- | --- | --- | --- |
| 1,024 | 1,536 | 6,621 / 183 | 8,658 / 220 | 8,319 / 206 |
| 4,101 | 4,613 | 4,063 / 94 | 4,918 / 140 | 7,854 / 173 |
| 8,198 | 8,710 | 2,460 / 57 | 3,713 / 120 | 5,046 / 164 |

**Output scaling** (prompt fixed at 1,024 tokens):

| Output tokens | Context | Algenta pf/dc | llama.cpp F16 pf/dc | MLX-LM bf16 pf/dc |
| --- | --- | --- | --- | --- |
| 512 | 1,536 | 6,621 / 183 | 8,658 / 220 | 8,319 / 206 |
| 2,048 | 3,072 | 6,088 / 143 | 7,681 / 134 | 7,074 / 187 |
| 4,096 | 5,120 | 5,835 / 112 | 9,208 / 190 | 8,703 / 179 |

Reading the two tables together:

* **Every engine slows as context grows** — prefill and decode both fall with deeper KV caches; that
  is the attention cost, not an engine defect.
* **At these volumes Algenta currently trails both controls.** Its int8 path leads the 256-token
  race (see the prefill/decode throughput pages), but once attention dominates, its single-stream
  decode attention is the limiting term: 57 tok/s at 8,198 input vs llama.cpp's 120 and MLX's 164.
* **Decode falls faster than prefill** for Algenta as output length grows (183 → 112 tok/s from 512
  to 4,096 output), the per-step KV-read cost compounding over the generation.

## Method

* **Harness.** `benchmarks/llm_smoke/load_test_3way.py` — builds byte-identical prompts (repeated
  factual text, truncated to the target token count) and runs all three engines on the same tokens,
  rotating engine order across passes so no engine always rides the same thermal slot.
* **Engines.** Algenta = production SDK path (`decode` → runtime worker → Metal, int8 weights).
  llama.cpp = resident `llama-server` on the F16 GGUF, `/completion`. MLX-LM = resident model in its
  own venv. Each at its native precision (int8 / F16 / bf16) — the way each engine actually ships.
* **What is timed.** Steady-state prefill (prompt processing) and decode (generation) rates, resident
  weights, per-cell median across passes.
* **Correctness.** All three produce valid continuations of the same prompt tokens; Algenta's path is
  additionally gated by the campaign's token oracle.
* **Hardware.** Apple M4 Max, integrated GPU via Metal.

## What is not claimed

* **Single-stream only.** This measures one request at a time. Concurrent-serving throughput is a
  different quantity — the engine's batched/continuous-batching decode path targets that regime.
* **One checkpoint, one precision per engine.** Qwen3-0.6B-Base; each engine at its native weight
  format. A quantized llama.cpp GGUF or a different model would shift the absolute numbers.
* **Not a latency-percentile SLA study.** This is steady-state throughput at large token volume.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode + batching together.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — the short-context regime.
* [Decode throughput](decode-throughput.md) — single-stream generation at race depth.
* [Batched decode throughput](batched-decode-throughput.md) — concurrent-serving throughput.
* [Benchmarks](overview.md) — methodology and what is not published.
