---
title: Algenta Governed Agent — Real LLM
emoji: 🧠
colorFrom: gray
colorTo: indigo
sdk: docker
license: apache-2.0
short_description: Live open-weights LLM, real kernels, real governance
fullWidth: true
header: mini
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta-governed-agent/resolve/main/social.png
tags:
  - llm
  - agents
  - mcp
  - governance
  - mojo
---

# Algenta Governed Agent — Real LLM

A live **open-weights LLM — Qwen3-4B-Instruct-2507, genuinely generating every token,
streamed from HF Inference Providers** (provider `nscale`, billed to the `thyn-ai` org,
greedy decoding) — calling **real kernel-backed tools** through **real Algenta governance**
running locally in this Space. Zero mocks, zero scripts, zero canned output.

## The loop (streamed live into the chat)

1. **Tool selection** — the model picks one tool from a profile-filtered list; output in
   JSON mode, parsed and validated against each tool's JSON schema, with **one retry** that
   feeds the validation error back to the model (both attempts shown).
2. **Real tool execution** — local in this Space (measured, backend labeled):
   - `search_corpus` — BM25 over **4,422 real English Wikipedia lead-extract passages**
     (CC BY-SA 4.0, per-passage title + URL attribution) via the **bm25_mojo** Mojo kernel,
     indexed live at every boot (measured index time shown in the badge row);
   - `score_answer` — corpus BLEU + chrF via **sacrebleu_mojo**, cross-checked live against sacrebleu 2.5.1;
   - `simulate` — M/M/1 queue discrete-event simulation on the signed **algenta-runtime-native** runtime
     (the runtime's only simulation scenario — see the decision note below);
   - `recommend` — governed recommendation + policy-gate preview (real wire shapes);
   - `execute_action` — the three named policy gates (**idempotency**, **confidence**,
     **risk_floor**) → HMAC-signed receipt or a structured denial naming the gate.
3. **Answer composition** — the same model writes the final answer grounded on the real
   tool result, **streamed token-by-token**, anchored by a deterministic outcome line
   computed from that result. General questions (greetings, explanations, weather) are
   answered directly and conversationally — tools only fire when the question maps to
   the real corpus, a real scenario, text scoring, or a governed action.

The **governance profile** is yours: `observe` / `govern` / `execute` / `full` decide which
tools are even model-facing. `force` / `override_safety` are operator-only and stripped
from the model-facing schema. Every outcome lands in the session **audit log**, and every
receipt can be verified with the per-session key shown there.

## Simulation — what the signed runtime really offers (audited, documented)

We audited the full signed-runtime catalog (643 modules / ~6,000 functions, listed live via
`MojoRuntime.list_modules()` on 2026-09-21) for a financial what-if scenario: the
`simulation` module is a queue discrete-event engine only (`mm1_simulate`, `create_sim`,
`schedule_event`, …); there is **no** cash-flow, Monte-Carlo-business, runway, or
growth-what-if module (`finance`/`accounting` are point-functions needing inputs — current
revenue, principal — that a chat question doesn't supply; `forecasting.*` needs a historical
series). So `simulate` keeps its one genuinely-computed scenario — the **M/M/1 queue** — and
financial what-ifs are carried by the **abstain path** (the engine declines plainly rather
than fabricate a scenario). Honesty over feature count.

## Why provider inference (measured, not marketing)

This Space previously ran Qwen2.5-1.5B-Instruct (GGUF Q4_K_M) on free HF **cpu-basic**.
Measured live on the deployed Space (2026-09-21): **331 s cold, 232 s warm for one short
turn** (tool selection 141 s at 0.57 tok/s, composition 90 s at 2.78 tok/s). No amount of
prewarming fixes a 2-vCPU decode floor.

The demo now streams inference from HF Inference Providers (org-billed) while **governance,
kernels, gates and receipts still run locally in this Space on every turn**. Measured live
on the deployed Space the same day, client-side over the public internet:

| turn | first visible token | full governed turn | streamed frames |
|---|---|---|---|
| retrieval (BM25 + cited answer) | ~0.83 s | 4.65 s | 51 |
| scoring (BLEU/chrF + oracle) | ~1.08 s | 4.47 s | 48 |
| risk_floor denial | ~1.07 s | 2.24 s | 22 |

Per-call model TTFT 0.5–0.75 s, decode 38–198 tok/s (shown live in every trace). A
byte-exact, fully offline reproduction path (the pinned GGUF) is documented in the
*Run it yourself* tab.

## The curated presets (all live-verified on every deploy)

| preset | what it proves |
|---|---|
| **Kármán vortex street** | retrieval over the real Wikipedia corpus, cited by title + URL |
| **Transformer paper** | retrieval hits "Attention Is All You Need" / "Transformer (deep learning)", cited |
| **queue simulation** | real M/M/1 run on the signed runtime from grounded rates (5/min vs 10/min) + closed-form cross-check |
| **score a summary** | candidate-vs-reference BLEU/chrF on sacrebleu_mojo, bit-exact vs the oracle |
| **action approved** | execute_action through all three gates → HMAC-signed receipt (verify it in the Audit tab) |
| **⛔ denied at gate** | risk_floor denial naming the gate — the governance contract, visibly enforced |

`scripts/verify_remote.py` runs every preset plus the regression set (empty submit, "hi",
weather, the revenue-question fabrication guard) against the live Space on each deploy.

## Honesty labels

- **The engine refuses to fabricate inputs.** Every numeric tool argument must be grounded
  in your message (after `10k`→10000, `$15k`→15000, `5%`→5 or 0.05 normalization) or equal a
  documented schema default disclosed as defaulted. Un-grounded numbers are rejected with
  feedback, retried once, then the turn **abstains with an honest composed decline** — never
  a fabricated run, never a held card. Ask for a revenue what-if and the agent declines
  plainly (the runtime's `simulation` module is M/M/1 queues only — verified, not assumed).
- **Demo inference runs on HF Inference Providers** (serverless, org-billed) — disclosed
  in the UI header, badges, and every run footer. The boot sequence probes the provider
  with a real generation and reports its measured TTFT; if inference is unreachable the
  turn is **held with the real error** — there is no fallback text.
- Greedy decoding is requested (temperature 0); providers do not expose a seed, so
  byte-exact reproduction is the local GGUF path. Governance semantics are deterministic
  local code on both paths.
- The corpus is **REAL**: 4,422 English Wikipedia lead-extract passages (curated categories —
  fluid dynamics, machine learning, spaceflight, biology, quantum mechanics, history — plus
  anchor articles), licensed **CC BY-SA 4.0** with per-passage title + URL attribution;
  fetched 2026-09-21 via the public MediaWiki API (`scripts/build_corpus.py`, deterministic
  sampling).
- Kernel backends are reported per call: native Mojo on this Space's linux/x86_64 image;
  a pure-Python fallback would be labeled, never passed off as "mojo".
- Receipts are integrity receipts: `execute_action` performs no external side effect; the
  governance decision is the artifact.

## Links

- Kernels: [thyn-ai/mojo-kernels](https://github.com/thyn-ai/mojo-kernels) (release `arena-wheels-v0.1.0`)
- SDK / MCP: [algenta-sdk](https://pypi.org/project/algenta-sdk/) · [algenta-mcp](https://pypi.org/project/algenta-mcp/) (MCP Registry: `io.github.thyn-ai/algenta`)
- Model: [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) (Apache-2.0, open weights)
- Sister Spaces: [Speed Arena](https://huggingface.co/spaces/thyn-ai/algenta-speed-arena) ·
  [LLM Agents](https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents) ·
  [LLM Modules Live](https://huggingface.co/spaces/thyn-ai/algenta-llm-modules) ·
  [Governed tool calls](https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls)

Attribution: **Algenta** · Apache-2.0
