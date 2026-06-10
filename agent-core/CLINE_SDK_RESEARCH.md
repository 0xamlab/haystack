# Cline Framework — Research Report (embedding Cline as the SDK head, Algenta engine behind)

> Method: deep-research harness — 22 sources fetched across 6 angles, 106 claims extracted,
> 25 adversarially verified (3-vote, need 2/3 refutes to kill), **22 confirmed / 3 killed**.
> Verification date **2026-06-10**. Confidence is "high" only where corroborated by Cline
> primary docs **and** repo source code. Claims marked ⚠️ are vendor self-assertion or
> unverified and called out explicitly.

## TL;DR
The Cline SDK is a viable agent **head** for an embedded, on-prem autonomous fixer. Cline 2.0
abstracts its harness into an **Apache-2.0 npm SDK** (`@cline/sdk` → `@cline/core` + `@cline/agents`
+ `@cline/llms` + `@cline/shared`), with two runtime layers (low-level `Agent`, high-level
`ClineCore`) and a **`local` in-process backend mode**. A private engine plugs in via **two seams**:
a **model seam** (`ApiHandler` + `llms.registerHandler(...)`) and an **engine/tool seam**
(`createTool` with `lifecycle.completesRun`). **Genuine air-gapped operation requires a local
model (Ollama/LM Studio) or your private engine** — Cline's "code never leaves" guarantees are
scoped to Cline-the-vendor; inference still routes to whatever provider you configure.

---

## 1. Architecture & SDK layout — *high (code-verified)*
- Public entry **`@cline/sdk`** re-exports `@cline/core`; `@cline/agents` (stateless loop) and
  `@cline/llms` (model gateway) are for lower-level control; `@cline/shared` = utilities.
- Install is **local**: `npm install @cline/sdk`. `npm i -g @cline` installs the **CLI**, not the SDK.
- **Two runtime layers:** `Agent` (`run()`/`continue()`, `createTool`, `subscribe`) and
  `ClineCore` (`create / start / send / subscribe / dispose / getAccumulatedUsage` + `list/get/readMessages/abort/stop/delete`).
- **Four backend modes:** `auto | local | hub | remote`. **`local` = "always use local in-process
  execution and local storage"** — the air-gapped deployment mode.
- Sources: cline.bot/blog/introducing-cline-sdk, docs.cline.bot/sdk/{overview,clinecore}, apps/examples, npm `@cline/sdk` (0.0.x).

## 2. Cline Core, gRPC & interfaces — *high; gRPC flagged unstable*
- **Cline Core = standalone Node process exposing a gRPC API**; multiple frontends attach at once
  and consume a **subscription stream of state + LLM messages** (custom UIs: Slack/Discord/web).
- ⚠️ **gRPC is not stable/versioned** — Cline: "full gRPC documentation coming soon… still sanding
  off rough edges." **Build on `@cline/sdk`/`ClineCore`, not raw gRPC.**
- **Headless CLI for CI/CD:** JSON output, pipeable I/O, exit codes, auto-approve (`-y/--yolo/--no-interactive`),
  parallel agents each in their own **git worktree**.
- Sources: cline.ghost.io/cline-cli-my-undying-love-of-cline-core, README, cline.bot/cli.

## 3. SDK capabilities — *high (code-verified)*
- **`createTool`** (Zod schemas) + **`lifecycle: { completesRun: true }`** to terminate the loop —
  verified in `apps/examples/code-review-bot` (`submit_review`).
- **Multi-agent / subagents** (each own model/tools/prompts); `multi-agent` example = 4 specialists
  via `Promise.all` + per-agent `subscribe()` → synthesizer → SSE. ⚠️ ships via a **bundled in-box
  plugin**; example is a `maxIterations:1` demo.
- **Plugins/hooks:** `beforeRun/afterRun/beforeModel/afterModel/beforeTool/afterTool/onEvent` —
  extend "without forking the runtime."
- **`getAccumulatedUsage(sessionId)`** → per-session token/cost totals (includes subagents).
- Sources: apps/examples/{code-review-bot,multi-agent}, docs.cline.bot/sdk/{plugins,guides/building-an-agent}.

## 4. 🔑 Private-engine seam — *high (code-verified)*
> "Provider logic lives in `@cline/llms`… To add a new custom provider, implement an **`ApiHandler`**
> and register it with **`llms.registerHandler("my-provider", handler)`**." `registerHandler` is a
> confirmed exported symbol in `sdk/packages/llms`. Sources: cline.bot/blog, sdk/ARCHITECTURE.md.

**Two plug points:** the **model seam** (`ApiHandler`/`registerHandler` — the LLM/engine that
produces turns) and the **engine/tool seam** (`createTool` — Algenta triage + Mojo sim as tools).

## 5. BYOM — *high*
- Anthropic, OpenAI, Google/Vertex, AWS Bedrock, Mistral, Azure, LiteLLM, OpenRouter (200+),
  OpenAI-compatible (vLLM/Together/Fireworks), and **local Ollama + LM Studio**.
- Ollama config: provider "Ollama", `http://localhost:11434`, choose model. vLLM via the generic
  OpenAI-compatible spec (no named built-in).
- Sources: README, docs.cline.bot/running-models-locally/ollama, docs.ollama.com/integrations/cline.

## 6. Privacy / on-prem — *strong but SCOPED*
- **Verified:** no RAG/embeddings/vector DB (filesystem + AST + ripgrep); **repositories never
  indexed or cached** by Cline; **code/prompts never used by Cline to train**; telemetry
  anonymous/opt-out, excludes code/paths/args/conversation/credentials.
- ⚠️ **Load-bearing caveat — 3 broader claims REFUTED 0-3:** these guarantees are scoped to
  **Cline-the-vendor**. Inference routes to whatever provider you configure; under BYO-key the
  provider's terms govern. **True zero-egress requires a local model (Ollama/LM Studio) or your
  private engine via `registerHandler`.** Cline *enables* air-gapped; the SDK doesn't *guarantee* it.
- Sources: cline.ghost.io/introducing-cline-for-enterprise, docs.cline.bot/enterprise-solutions/overview,
  docs.cline.bot/more-info/telemetry, cline.bot/blog/why-cline-doesnt-index-your-codebase.

## 7. Enterprise & licensing — *high*
- **Apache-2.0** open-source core (`© 2026 Cline Bot Inc.`) vs a separate **Cline Enterprise** tier
  (governance, centralized inference control, BYO-inference: Bedrock/Vertex/Azure/Anthropic/OpenAI/
  Cerebras/**any OpenAI-compatible**). ⚠️ Enterprise pages **don't** name Ollama/LM Studio/OpenRouter.
- Sources: github.com/cline/cline (LICENSE), cline.ghost.io/introducing-cline-for-enterprise.

## ⚠️ Flagged — NOT verified against a primary source
- **"1M-token context" and "Memory Bank"** Cline-vs-Cursor claims **did not survive verification** — unverified.
- A direct primary-sourced **Cline-vs-Cursor** comparison (pricing/autonomy/control) **is unsupported** by this evidence set.
- **Killed (refuted):** "SDK powered by the same engine as CLI/Kanban/VS Code/JetBrains" (1-2);
  "Cline Enterprise processes everything client-side / never uploads code" (0-3, ×2).
- **Maturity:** SDK ~4 weeks old (May 2026), **pre-1.0 (`v0.0.x`)** — signatures/packaging may shift.

## Open questions (resolve before committing the integration)
1. `local` backend mode's exact **no-egress runtime contract** (telemetry/licensing/model-catalog refresh; can all be disabled?).
2. **Stability/versioning** of the gRPC API and pre-1.0 `@cline/sdk` — embedder breakage risk.
3. The exact **`ApiHandler` interface contract** a private engine must implement (streaming, tool-call format, usage reporting for `getAccumulatedUsage`).
4. Concrete **Enterprise audit/governance** feature list and whether audit logs emit from `@cline/core` or only the hosted/Enterprise layer.

## What this means for embedding Cline as the head with Algenta behind
1. **Use both seams:** register Algenta (or a local model) as an `ApiHandler` via `registerHandler` (model side) **and** expose triage + Mojo-sim as `createTool` tools with `completesRun` (engine side).
2. **`backendMode:"local"` + Ollama/LM Studio BYOM** = a genuinely zero-egress autonomous fixer; maps 1:1 onto Algenta `self_hosted/air_gapped`.
3. **Build on `@cline/sdk`/`ClineCore`**, not raw gRPC (unstable).
4. **`getAccumulatedUsage`** gives the real token/cost numbers the stub can't.
5. Pin a **vendored `@cline/sdk` version** (pre-1.0 churn) and gate live agentic runs behind explicit env.

## Sources (primary unless noted)
cline.bot/blog/introducing-cline-sdk-the-upgraded-agent-runtime · docs.cline.bot/sdk/{overview,clinecore,plugins,guides/building-an-agent} · github.com/cline/cline (+ sdk/ARCHITECTURE.md, apps/examples, LICENSE) · cline.ghost.io/{cline-cli-my-undying-love-of-cline-core,introducing-cline-for-enterprise} · docs.cline.bot/{running-models-locally/ollama,enterprise-solutions/overview,more-info/telemetry} · cline.bot/blog/why-cline-doesnt-index-your-codebase · README · npm @cline/sdk. Secondary/blog: itnext.io (Building an Agent with the Cline SDK), morphllm/augmentcode/nimbalyst comparisons (used only where primary unavailable; comparative claims unverified).
