---
title: Algenta
emoji: ⚡
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
license: apache-2.0
short_description: The governed decision engine, at machine speed — live
tags: [mojo, agents, mcp, llm, benchmark]
fullWidth: true
header: mini
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta/resolve/main/social.png
---

# ⚡ Algenta — the governed decision engine, at machine speed

The flagship Space for the whole Algenta platform. Every live number here is computed at run time
by the real artifacts — kernels raced in a dedicated arena interpreter, the signed runtime
executing in-process, the 140-tool MCP registry imported from the published package. Nothing is
canned; where a capability can't run inside a free Space, the tab says so and gives you the exact
install line instead.

## The six tabs

- **Overview** — the product story in 20 seconds: live-computed hero metrics (44 kernel
  accelerators, 10 framework integrations, 140 MCP tools, 22 live LLM modules, 643-module
  runtime catalog), the three CTAs, and the product map (SDK → integrations → MCP → engine,
  Community license).
- **Speed Arena** — 8 headline benchmark duels from the proven
  [Speed Arena](https://huggingface.co/spaces/thyn-ai/algenta-speed-arena) harness (bm25 three-way,
  volatility3 hive walk, pefile checksum, croniter, ruptures, pykalman, pool scan, oletools):
  correctness gate first, seeded corpora, median-of-5, hardware disclosed — every number published
  is a configuration where the Algenta kernel won, measured live (the harness sweeps each duel's
  configurations and shows the best win on this run).
  Duel cells execute in a dedicated CPython 3.12 interpreter — the pinned incumbents
  (ruptures<3.14, numba) can't share the main app's Python 3.14, which the signed runtime requires.
- **LLM Modules** — real signed-runtime executions (`algenta-runtime-native` via the proven
  llm-modules pattern): tokenize, mini-KB retrieval, and the attention-lab parity run.
- **Governed Agents** — profiles → log → approve → receipt. An engine adapter selects the backend:
  with the `ALGENTA_API_KEY` Space secret set, the same UI runs against a real tenant through
  `algenta-sdk`; otherwise it runs a deterministic demo engine with the production API's wire
  shapes — **labeled as such on the tab**.
- **SDK Hub** — every package as a card: `algenta-sdk` (Python/TypeScript), all 10 integrations,
  `algenta-mcp`, `algenta-runtime-native`, and the mojo-kernels top-10 by measured speedup.
- **MCP** — the 140-tool surface with real metadata imported live from the published
  `algenta-mcp` package, plus install and client-config snippets.

## Honesty rules

Correctness gate before timing · seeded data · median-of-5 with the machine disclosed on every
card · a fallback is never benchmarked as "mojo" · hosted-only capabilities are install lines,
never fake interactives · the demo engine is always labeled · no tracebacks — failures surface as
toast warnings and error cards with the reason.

## Links

- SDK: [github.com/thyn-ai/algenta-sdk](https://github.com/thyn-ai/algenta-sdk) ·
  [PyPI](https://pypi.org/project/algenta-sdk/) · [npm](https://www.npmjs.com/package/algenta-sdk)
- Integrations: [github.com/thyn-ai/algenta-integrations](https://github.com/thyn-ai/algenta-integrations)
- Kernels: [github.com/thyn-ai/mojo-kernels](https://github.com/thyn-ai/mojo-kernels) ·
  [arena-wheels release](https://github.com/thyn-ai/mojo-kernels/releases/tag/arena-wheels-v0.1.0)
- MCP: [algenta-mcp on PyPI](https://pypi.org/project/algenta-mcp/) · registry entry
  `io.github.thyn-ai/algenta`
- Docs: [docs.algenta.ai](https://docs.algenta.ai)
- Deep-dive satellites: [Speed Arena](https://huggingface.co/spaces/thyn-ai/algenta-speed-arena) ·
  [LLM Modules](https://huggingface.co/spaces/thyn-ai/algenta-llm-modules) ·
  [For LLM Agents](https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents) ·
  [Governed Tool Calls](https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls)

Attribution: **Algenta** · Apache-2.0 (engine kernels ship as signed wheels under the Algenta
Community license).
