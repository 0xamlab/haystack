---
title: Algenta LLM Modules — Live
emoji: 🧠
colorFrom: purple
colorTo: blue
sdk: docker
license: apache-2.0
short_description: Real Mojo LLM kernels executing live in your browser
tags: [mojo, llm, embeddings, vector-search, kernels]
fullWidth: true
header: mini
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta-llm-modules/resolve/main/social.png
---

# 🧠 Algenta LLM Modules — Live

**Real Mojo kernels from the signed `algenta-runtime-native` wheel, executing in your browser
session. No API key. No simulations.**

Every tab on this Space executes the actual runtime modules — the same code that ships in
[`algenta-runtime-native`](https://pypi.org/project/algenta-runtime-native/) 1.0.5 behind
[`algenta`](https://pypi.org/project/algenta/) 1.0.17 — and shows you the live request/response
JSON, the in-kernel latency the wrapper measured, and the exact Python call to reproduce it.

## The tabs

- **🧠 Live module runner** — six real executions:
  - **🔤 Tokenize** — `text.tokenizer` lexical kernels on your text, plus `bpe_tokenizer`
    training metrics computed from the real counts (that module is BPE *metrics*, not a
    learned tokenizer — labeled as such).
  - **🔎 Mini-KB retrieval** — your query over a seeded 8-doc KB. Text → vectors is a
    deterministic demo hash-embedder in Python (**labeled — not a neural model**); every
    vector op (`embeddings.*`, `sparse_vector.*`) is a live Mojo kernel call.
  - **⚡ Attention lab** — exact causal attention at 8×8, computed twice: naive numpy vs the
    runtime's flash online-softmax recurrence, one kernel call per step (~520 calls), parity
    checked to 1e-9. Both paths timed live, with the transport-overhead caveat stated on the
    label.
  - **🧭 Column ranker** — `vector_kernels.ranker.run_column_rank_v2`, the semantic
    schema-matching kernel: query column name → ranked candidates with score decomposition,
    confidence gap, ambiguity flag.
  - **📦 Serving math** — the engine's own accounting kernels: `kv_cache`, `paged_kv_cache`,
    `continuous_batching`, `inference_cost_latency`, `speculative_decoding` on your shape.
  - **🎯 Sampling · eval · alignment** — `llm_sampling` + `generation_loop` gates,
    `rerank_eval` + `vector_search` + `vector_similarity` metrics, `rlhf_dpo` losses.
- **📚 The 22 modules** — the full catalog with honest status (all 22 probed **RUNS LIVE** in
  this container; they are pure compute kernels, not a hosted LLM) plus a button that executes
  a proven probe call for any module, live.
- **🚀 Use it yourself** — install lines, the mojo-quickstart, the self-host CTA (free under
  the Community license), and links to the sister Spaces.

## What "live" means here

The Space runs `python:3.14-slim` (required: the runtime wheel targets CPython 3.14,
manylinux_2_35_x86_64). On first call, the wrapper verifies the runtime's signed manifest and
artifact hash, then executes in-process through the bundled worker — no daemon, no TCP
listener, no outbound calls, no `ALGENTA_LICENSE` needed for these library kernels.

Nothing here is canned: there is no Python compute fallback and no pre-recorded output. If a
kernel fails, the tab shows the failure.

## Run it locally

```bash
docker build -t algenta-llm-modules .
docker run -p 7860:7860 algenta-llm-modules
```

## Attribution

**Algenta** — the runtime wheel is proprietary and verified against its signed manifest; the
wrapper, SDK, quickstarts, and this Space's app code are Apache-2.0. No engine code runs here.

Sister Spaces: [⚡ Speed Arena](https://huggingface.co/spaces/thyn-ai/algenta-speed-arena) ·
[🤖 Algenta for LLM Agents](https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents) ·
[🛡️ governed tool calls](https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls)
