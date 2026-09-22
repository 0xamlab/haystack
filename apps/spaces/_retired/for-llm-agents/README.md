---
title: Algenta for LLM Agents
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.28.0
license: apache-2.0
short_description: Interactive demos for LLM & agent builders
tags: [llm, agents, mcp, rag, mojo]
fullWidth: true
header: mini
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents/resolve/main/social.png
python_version: "3.12"
---

# 🤖 Algenta for LLM Agents

Interactive demos for LLM and agent builders — real native Mojo kernels and the governed
tool-call surface, running live on this Space's free cpu-basic hardware. Zero API keys needed.

## The tabs

- **🔍 RAG retrieval duel** — one query over a vendored synthetic mini-corpus (320 fully
  synthetic BEIR-scifact-style abstracts, `scripts/gen_corpus.py`, seed 20260920 — **not real
  papers**), ranked side-by-side by `rank_bm25` and `bm25-mojo` (native Mojo kernel). The
  top-10 ordering is asserted identical on every run; per-query latency is measured live
  (median of 7, interleaved), with a retrieval-budget line. RAG isn't dead, your retrieval is slow.
- **🧪 LLM output scorer** — paste a hypothesis and reference(s): instant BLEU + chrF via
  `sacrebleu-mojo` with the full breakdown, cross-checked live against the reference
  `sacrebleu` 2.5.1. Deterministic scoring, bit-exact vs the oracle (verified in the kernel's
  differential tests). **Race the harness** times both packages on a seeded batch — gate
  first, timing second.
- **🛡️ Prompt-injection governance duel** — you play the user (preset red-team attacks or free
  text); a scripted mock agent (**not an LLM**) proposes a risky tool call, and the simulated
  engine — **real API wire shapes, labeled as simulated** — intercepts it at the profile layer
  or denies it by a named policy gate (`idempotency` / `confidence` / `risk_floor`), or
  returns a signed execution receipt.
- **🔌 MCP playground** — `algenta-mcp` as a real MCP server: the real 140-tool registry
  (vendored from the published algenta-mcp 1.0.17 package), the JSON-RPC
  `initialize` / `tools/list` frames as a client sees them, and a call runner for read-only
  demo tools against the simulated engine. Install snippets for Claude Desktop / Cursor / Codex
  included.
- **📚 Examples library** — `algenta-sdk` quickstart (pip/npm), the ten framework integrations
  (LangChain, LlamaIndex, pydantic-ai, MAF, Haystack, LiteLLM, Ray Serve, vLLM, Vercel AI SDK,
  n8n) with per-framework installs, the Mojo kernel quickstart, both sister Spaces, and the
  self-host CTA (Algenta Community license).

## Honesty rules (same as the Speed Arena)

- correctness gate before timing; a failed gate holds the run — no number is shown
- seeded corpora and batches; seeds printed on the cards
- median-of-N timings with the machine disclosed on every card (never copied from a README)
- native-kernel check: if a wheel's native Mojo kernel did not load, the measurement is
  **held** — the pure-Python fallback is never benchmarked as "mojo"
- simulated engine paths are labeled as simulated; no LLM benchmarks are claimed anywhere
- failures surface as held cards with the reason — never tracebacks

## Where the wheels come from

Both kernel wheels install from the public
[arena-wheels-v0.1.0 release](https://github.com/thyn-ai/mojo-kernels/releases/tag/arena-wheels-v0.1.0)
of [thyn-ai/mojo-kernels](https://github.com/thyn-ai/mojo-kernels) (Apache-2.0): `bm25-mojo`
(one of the original 12 arena wheels) and `sacrebleu-mojo` (built by the repo's own CI —
`ci-sacrebleu`, run 35536440577, main @ `69512862` — and attached to the same release;
SHA-256 `0d82fbbc…26c657`, recorded in `wheels/SHA256SUMS.txt`).

## Links

- Kernels: [github.com/thyn-ai/mojo-kernels](https://github.com/thyn-ai/mojo-kernels)
- SDK: [github.com/thyn-ai/algenta-sdk](https://github.com/thyn-ai/algenta-sdk) ·
  Integrations: [github.com/thyn-ai/algenta-integrations](https://github.com/thyn-ai/algenta-integrations)
- MCP server: [algenta-mcp on PyPI](https://pypi.org/project/algenta-mcp/) · Registry entry
  `io.github.thyn-ai/algenta`
- Sister Spaces: [⚡ Speed Arena](https://huggingface.co/spaces/thyn-ai/algenta-speed-arena) ·
  [🛡️ governed tool calls](https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls)

Attribution: **Algenta**. The Algenta engine is proprietary; everything demoed here runs on
open-source packages (Apache-2.0) plus a clearly-labeled simulated engine.
