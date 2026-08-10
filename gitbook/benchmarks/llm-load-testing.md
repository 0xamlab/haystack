---
icon: gauge-circle-notch
description: Enterprise load/stress test of the Algenta Apple-silicon LLM engine — large-token prefill/decode and concurrent requests with latency percentiles and a zero-error determinism gate.
---

# LLM load testing

A serving-load measurement, distinct from the single-request race numbers: an enterprise-style
load/stress harness (`benchmarks/llm_smoke/load_test.py`) run against the production SDK path
(`decode` → runtime worker → Metal) with resident weights. Two lanes — a **token-size stress
matrix** (very large prompts × very large generations) and a **concurrent-request lane** (N
in-flight requests) — plus a correctness gate that applies to every measurement: **greedy
determinism** (identical prompt and parameters reproduce byte-identical token ids) and a
valid-token-range check. Every cell and every request below passed it.

{% hint style="info" %}
**Headline.** The engine runs **8,192-token prompts and 4,096-token generations** end to end,
greedy-deterministic throughout, and served **60 concurrent requests with zero errors**. Rates are
context-dependent — prefill and decode both slow as context grows — and concurrent requests
serialize in the single-stream worker, so aggregate decode throughput is bounded by the
single-stream rate. Both behaviors are measured and reported below, not smoothed over.
{% endhint %}

## Large-token stress

Qwen3-0.6B-Base, Apple M4 Max, resident weights, greedy; median of timed iterations. **Input
scaling** (generation fixed at 1,024 tokens):

| Input tokens | Context | Wall (s) | Prefill tok/s | Decode tok/s |
| --- | --- | --- | --- | --- |
| 1,024 | 2,048 | 6.65 | 7,913 | 174 |
| 2,048 | 3,072 | 9.29 | 5,788 | 126 |
| 4,096 | 5,120 | 13.31 | 3,925 | 88 |
| 8,192 | 9,216 | 23.54 | 2,316 | 54 |

**Output scaling** (prompt fixed at 1,024 tokens):

| Output tokens | Context | Wall (s) | Prefill tok/s | Decode tok/s |
| --- | --- | --- | --- | --- |
| 512 | 1,536 | 3.53 | 7,601 | 186 |
| 1,024 | 2,048 | 7.63 | 6,868 | 150 |
| 2,048 | 3,072 | 16.96 | 6,860 | 128 |
| 4,096 | 5,120 | 40.32 | 6,559 | 105 |

Reading the two tables together: from 1K to 8K input tokens, prefill falls ~3.4× and decode ~3.2×.
That is the long-context attention/KV cost, not a defect — the short-context figures on the
[prefill](llm-prefill-throughput.md) and [decode](decode-throughput.md) pages are the fast regime,
and load at depth pays the attention cost. Every cell remained byte-identical across repeat runs.

## Concurrent request load

512-token prompt, 128-token generation, four rounds per concurrency level, Qwen3-0.6B-Base:

| Concurrency | Requests | Errors | p50 (s) | p95 (s) | p99 (s) | System decode tok/s |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 | 0 | 0.574 | 1.851 | 1.851 | 143 |
| 2 | 8 | 0 | 1.150 | 1.158 | 1.158 | 222 |
| 4 | 16 | 0 | 1.725 | 2.361 | 2.388 | 218 |
| 8 | 32 | 0 | 3.035 | 4.897 | 4.940 | 209 |

* **Zero errors** across all 60 requests; every response was greedy-deterministic for its prompt.
* **Requests serialize.** The single-stream worker handles one request at a time, so per-request
  latency percentiles climb with queue depth (p50 0.57 s at C=1 → 3.0 s at C=8).
* **System throughput** (total generated tokens ÷ elapsed wall) rises from 143 tok/s at C=1 —
  where the fixed per-request cost is visible — to ~210–220 tok/s at C≥2, where queueing keeps the
  GPU busy between requests, then holds flat: the GPU emits one token at a time, so aggregate
  decode cannot exceed the single-stream rate.

{% hint style="warning" %}
**No request-level parallelism yet.** Genuine concurrent scaling is the Slipstream
batched/continuous-decoding path (many sequences per weight sweep) — kernel-complete and measured
on the [batched decode](batched-decode-throughput.md) page, but not yet wired into this serving
path. The numbers above are the baseline that wiring must beat.
{% endhint %}

## Method

* **Harness.** `benchmarks/llm_smoke/load_test.py` — `--mode stress` (token-size matrix) and
  `--mode concurrent` (latency percentiles + throughput); JSON report.
* **Path under test.** Production SDK shape: `algenta.inference.decode` → `MojoRuntime` → AF_UNIX
  worker → model-agnostic entry point → Metal, resident weights (loaded once, adopted per request).
* **Prompt.** Real tokenized text (a repeated factual passage) sized to the target token count —
  not padding.
* **Correctness gate.** Greedy determinism (two identical calls → identical token ids) plus a
  valid-token-range check, enforced on every stress cell and asserted across concurrent outputs.
* **Statistics.** Median of timed iterations per cell; nearest-rank p50/p90/p95/p99 for latency.
* **Hardware.** Apple M4 Max, integrated GPU via Apple Metal.

## What is not claimed

* **One checkpoint.** Measured on Qwen3-0.6B-Base. The 1.7B tier uses the same path but is not
  re-measured here.
* **Not the parallel-decoding number.** Concurrent scaling beyond the single-stream rate is the
  [batched decode](batched-decode-throughput.md) story, not this serving path's.
* **Not a multi-tenant/production SLA study.** Single-machine, single-worker load characterization.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode together.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — short-context prompt processing.
* [Decode throughput](decode-throughput.md) — single-stream generation.
* [Batched decode throughput](batched-decode-throughput.md) — continuous batching.
* [Benchmarks](overview.md) — methodology and what is not published.
