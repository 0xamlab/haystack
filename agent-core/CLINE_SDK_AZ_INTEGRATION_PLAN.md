# Cline SDK A–Z Integration Plan — Cline as the head, Algenta as the engine behind

> Status: **proposal for review** (no code yet). Principle: drive the agent loop with the
> vendored Apache-2.0 Cline SDK end to end; plug the Algenta engine (180-language repo
> intelligence + the Mojo decision engine + the capability plane) **behind** it as tools,
> hooks, and MCP — not a re-implementation. Boundary stays self-hosted HTTP
> (see `project_sdk_transport_boundary`): Cline (Node head) calls the Algenta engine over
> the local `/v1/repositories` + capability-plane API; no cloud.

## 1. Where we are (honest baseline)

- **Vendored SDK present:** `agent-core/vendor/cline/sdk/packages/{core,llms,shared,agents,sdk}` (real `@cline/core`, `@cline/llms`, `@cline/shared`, `@cline/agents`).
- **Adapter written, single-agent slice:** `vendor/cline/algenta/adapter.ts` correctly does `ClineCore.create({backendMode:"local", toolPolicies}) → start() → send() → dispose()`, resolves provider/model/key via `Llms.getProviderCollection`, extracts `usage` + `filesChanged` from `AgentResult.toolCalls`. Real server `vendor/cline/algenta/run-server.ts` wires `runAgent → POST /run` (run with `bun`).
- **But the RUNNING path is the stub:** `agent-core/package.json` `"start":"node run-server.mjs"` → `run-server.mjs` is a model-less stub (appends a marker, reports `tokens:0`). `node_modules` not installed; the TS server isn't built. So `verified_agentic` → `ALGENTA_AGENT_CORE_URL` currently hits the **stub**, and G0 arms A/C measure nothing real.
- **Surface used: ~5%.** No `createTool`, no `subscribe()` streaming, no plugins/hooks, no multi-agent (`enableSpawnAgent`/`enableAgentTeams` = false), no MCP, no sessions/checkpoints, no `getAccumulatedUsage`.

## 2. Full Cline SDK surface (what "A–Z" means) — with exact refs

From `agent-core/CLINE_SDK_INTERFACE.md` (signatures copied from the vendored SDK) + docs:

- **`ClineCore` lifecycle:** `create(options)` · `start(input)` (resolves at *launch*, not completion — `ClineCore.ts:252`) · `send({sessionId,prompt,mode,timeoutMs})` → `AgentResult` (awaits the turn) · `abort` · `stop` · `delete` · `dispose(reason?)`.
- **Sessions:** `list` · `get` · `readMessages` · **`getAccumulatedUsage(sessionId)`** → `{aggregateUsage:{inputTokens,outputTokens,totalCost}}` (includes subagents, `ClineCore.ts:317`).
- **Events:** `subscribe(listener,{sessionId?})` → stream of `AgentRuntimeEvent` (`assistant-text-delta`, tool calls, `done` w/ `reason/text/iterations/usage`, `ended`). Subscribe **before** `start()`.
- **`start().config`:** `providerId, modelId, apiKey, systemPrompt, cwd, workspaceRoot, enableTools, enableSpawnAgent, enableAgentTeams, execution.maxIterations`; `pluginPaths?` to load `AgentPlugin`s from disk.
- **Tools:** `toolPolicies` (`{ "*":{autoApprove:true}, <tool>:{enabled:false} }`); `capabilities.requestToolApproval`; built-ins (files/editor/apply_patch, shell, search/read/list, web/fetch).
- **Custom tools:** `createTool({name, description, inputSchema: zod, lifecycle?: {completesRun?:true}, execute})` (`@cline/agents`).
- **Plugins/Hooks:** `AgentPlugin` (alias of `AgentExtension`), `HookControl` (`@cline/shared`) — pre/post tool + lifecycle hooks.
- **Providers:** `@cline/llms` `getProviderCollection`, `createHandler`, gateway, `resolveProviderModelCatalogKeys`.
- **Multi-agent:** parallel `Agent` instances (`run/continue/abort/subscribe/restore/snapshot`) + synthesizer; `enableSpawnAgent`/`enableAgentTeams`.
- **MCP:** MCP servers exposed as agent tools.

Reference example apps (the patterns we adopt):
- **code-review-bot** ≈ our autonomous fixer: custom `createTool`s (`add_review_finding`, `submit_review` w/ `completesRun:true`) + event filtering by tool name.
- **multi-agent:** N specialists in parallel (`Promise.all` + per-agent `subscribe`) → synthesizer.
- **cli-agent:** `run`/`continue` multi-turn + `createTool` shell + delta streaming.

## 3. The Algenta engine behind Cline (the contracts)

Custom tools run **inside the Node agent-core** and call the Algenta engine over the
self-hosted HTTP API (`ALGENTA_ENGINE_URL` → the FastAPI `/v1/repositories/*` +
`/v1/capability-*`). The agent calls Algenta tools instead of blind exploration.

| Cline mechanism | Tool/hook | Algenta engine behind | HTTP |
|---|---|---|---|
| `createTool` `localize` | input `{issue, changed_files?}` → bounded evidence bundle (files+symbols+snippets) | 180-lang **triage** | `POST /v1/repositories/{id}/triage` |
| `createTool` `graph_query` | input `{file?,symbol?}` → dependents/blast-radius | dependency graph | `POST /v1/repositories/{id}/graph-query` |
| `createTool` `simulate_patch` **`completesRun:true`** | input `{decision_plan_id|patch}` → DecisionEnvelope (recommended_action, confidence, risk) — **gates submission** | **Mojo engine** `0.7.0-mojo-parallel` | `POST /v1/repositories/{id}/simulate` |
| `AgentPlugin` post-edit hook | after each `editor`/`apply_patch`, run sim + enforce calibrated-risk floor; veto on regression | Mojo sim + policy | same |
| MCP server | the capability plane as MCP tools (`rt.list_capability_providers/execute_capability`) | capability plane | `/v1/capability-*` |
| `getAccumulatedUsage` | real token/cost out of every run | — | — |

Tool result shape (NDJSON streamed to Python): `{tool, ok, summary, evidence_ref, tokens?}`.
`simulate_patch` returns `{recommended_action, confidence, risk, engine_version, execution_ms}`;
the agent is instructed to call it before `submit_fix` and only submit on `apply_patch`.

### 3.1 Two integration seams (research-confirmed — see `CLINE_SDK_RESEARCH.md`)

Deep research on the real SDK surfaced a **second, cleaner plug point** this plan originally
missed. There are **two** seams, and we use both:

- **Model seam — `ApiHandler` + `llms.registerHandler("algenta", handler)`** (`@cline/llms`).
  This is the documented way to add a custom provider: implement an `ApiHandler` and register it.
  Use it to put **Algenta's model/engine (or a local BYOM model) behind the loop as the provider** —
  cleaner than tunnelling the model through a tool.
- **Engine/tool seam — `createTool`** (above): the repo-intelligence **triage** + **Mojo sim** +
  graph as agent tools, with `completesRun` gating apply.

Build on the documented **`@cline/sdk` / `ClineCore`** surface, **not raw gRPC** — research flagged
gRPC as not-yet-stable/versioned ("docs coming soon"). `@cline/sdk` is **pre-1.0 (`v0.0.x`)**, so
pin a vendored version and expect signature churn. Capture real usage with **`getAccumulatedUsage`**.

## 3.5 Deployment & privacy posture — Cline on-prem ⟷ Algenta self-hosted

Cline's on-prem story is the same boundary Algenta already enforces, which is why this
integration is a fit rather than a compromise:

- **Air-gapped / VPC / on-prem:** Cline deploys inside a VPC, air-gapped, or on-prem.
  Maps 1:1 to Algenta `ALGENTA_DEPLOYMENT_MODE=self_hosted|air_gapped` (the
  `self_hosted_private_runtime_without_commercial_plane` entitlement, fail-closed egress).
- **Client-side execution:** Cline processes code locally — the codebase is never uploaded,
  cached, or indexed by external servers. Matches "no cloud" (`project_sdk_transport_boundary`):
  the agent-core head, the Algenta engine, and the Mojo sim all run on the box.
- **No external training:** prompts/data never train public models — consistent with the
  private-profile red lines.
- **BYOM / local models (the air-gapped win):** Cline's `@cline/llms` catalog supports
  **local runtimes (Ollama, LM Studio)** alongside cloud providers. The adapter already
  resolves provider/model/key from the catalog, so selecting a local provider gives a
  **fully air-gapped autonomous fixer**: local model → Cline head → Algenta tools
  (triage + Mojo sim) → all loopback, zero network. Cloud providers (Anthropic, etc.)
  remain a config switch for non-air-gapped tiers.
- **Interfaces:** beyond IDE extensions, Cline exposes a terminal UI, a scriptable **CLI**
  (CI/CD), and **gRPC** APIs, and supports custom UIs (Slack/Discord/dashboards). Our
  HTTP/NDJSON `/run` sidecar is one such surface; the CLI/gRPC paths are available for
  CI-driven `/repositories` runs without standing up the HTTP server.
- **Enterprise (governance/audit):** centralized infra control + audit trails map onto the
  capability plane's `audit_events` + the calibrated-risk/provenance gates (Phase 2/3).

**Implication for the plan:** provider selection is parameterized end to end — `localize`
and `simulate_patch` (the Algenta engine) are provider-agnostic, and the agent's *model*
is a deployment choice (local BYOM for air-gapped, cloud for managed). G0 should record the
provider/model so token/cost numbers are attributed per tier.

## 4. Phased plan (file-by-file)

### Phase 0 — Foundation: run the real head + real telemetry
**Goal:** replace the stub with the real Cline server; capture real usage + stream events.
- `agent-core/vendor/cline/` — `bun install` + `bun run build` (builds `@cline/*` workspaces). *(verify build succeeds; ~minutes)*
- `agent-core/package.json` — `"start": "bun vendor/cline/algenta/run-server.ts"` (retire `run-server.mjs` to `run-server.stub.mjs`, kept for offline contract tests).
- `agent-core/vendor/cline/algenta/run-server.ts` — already wires `runAgent`; add `subscribe()` → forward `assistant-text-delta` + `tool_call`/`tool_result` + `done` as NDJSON frames (streaming, not just final).
- `agent-core/vendor/cline/algenta/adapter.ts` — switch completion to the **event pattern** (`subscribe` before `start`, resolve on `done`/`ended`); call `getAccumulatedUsage(sessionId)` to fill `usage` authoritatively (don't rely on `send().usage`).
- `apps/api_server/services/repository_intelligence_agent_core_client.py` — parse streamed NDJSON frames; surface `usage{input,output,totalCost}` + `tool_calls` + `turns` into telemetry (`record_tokens`, `agent_turns`, `agent_tool_calls_by_name`).
- `agent-core/vendor/cline/algenta/adapter.ts` + env — provider/model from `ALGENTA_AGENT_PROVIDER` / `ALGENTA_AGENT_MODEL` via the `@cline/llms` catalog (default `anthropic`; set `ollama`/`lmstudio` for **air-gapped BYOM**). Provider/model recorded in telemetry.
- `scripts/g0_token_benchmark.py` — record provider/model per arm so tokens/cost are attributed per tier; once the sidecar is real, arms A/C produce real numbers.
- **Exit:** real Cline run on a fixture (cloud and a local-BYOM smoke); G0 A vs C with real tokens/turns/resolution (the comparison we owe).

### Phase 1 — Engine behind: Algenta custom tools
**Goal:** the agent calls Algenta instead of exploring.
- `agent-core/vendor/cline/algenta/tools/localize.ts` — `createTool` → `POST {ALGENTA_ENGINE_URL}/v1/repositories/{id}/triage`.
- `agent-core/vendor/cline/algenta/tools/graph_query.ts` — `createTool` → `/graph-query`.
- `agent-core/vendor/cline/algenta/tools/simulate_patch.ts` — `createTool` `lifecycle:{completesRun:true}` → `/simulate` (Mojo); returns the gate.
- `agent-core/vendor/cline/algenta/adapter.ts` — register the tools; system prompt: "call `localize` then edit, call `simulate_patch` before finishing; submit only if `recommended_action==apply_patch`."
- `apps/api_server/services/repository_intelligence_verified_agentic.py` — pass `repository_id` + `ALGENTA_ENGINE_URL` so the tools can call back; keep exploration suppressed (tools replace it).
- **Exit:** a fix where the agent localizes via triage + verifies via Mojo, with the sim gating submission.

**Pinned attach mechanism (from vendored source — `ClineCore` path).** Custom tools do NOT
go on `start().config` directly; they attach through an `AgentExtension` (= `AgentPlugin`)
loaded from disk via `config.pluginPaths`:
```ts
// algenta/tools.ts
import { createTool } from "@cline/sdk"; import { z } from "zod";
export const localize = createTool({
  name: "localize", description: "Triage the repo to a bounded evidence bundle.",
  inputSchema: z.object({ issue: z.string(), changed_files: z.array(z.string()).optional() }),
  execute: async (i) => httpPost(`${ENGINE}/v1/repositories/${REPO}/triage`, ...),
});
export const simulatePatch = createTool({
  name: "simulate_patch", description: "Verify the patch via the Mojo engine.",
  inputSchema: z.object({ decision_plan_id: z.string().optional() }),
  lifecycle: { completesRun: true },                 // Q2: returning don't-apply ENDS the run, no submit
  execute: async (i) => httpPost(`${ENGINE}/v1/repositories/${REPO}/simulate`, ...),
});
// algenta/algenta-plugin.ts
import type { AgentPlugin } from "@cline/core"; import { localize, simulatePatch, graphQuery } from "./tools";
const plugin: AgentPlugin = { name: "algenta-engine",
  setup(api) { api.registerTool(localize); api.registerTool(simulatePatch); api.registerTool(graphQuery); } };
export default plugin;
// adapter.ts (start config, only when ENGINE url is set):
//   pluginPaths: [resolve(__dirname, "algenta-plugin.ts")]
```
`createTool` = `{ name, description, inputSchema (Zod|JSON-schema), execute(input, ctx) => Promise, lifecycle?: { completesRun? } }` (shared/tools/create.ts). `AgentExtension.setup(api)` → `api.registerTool(tool)` (plugin-tools.ts:117). Tools call the engine over **loopback HTTP** (Q1) → `ENGINE = ALGENTA_ENGINE_URL`, `REPO` from the run payload. Additive: no `ALGENTA_ENGINE_URL` ⇒ no `pluginPaths` ⇒ current behavior unchanged.

### Phase 2 — Govern + verify: plugins/hooks
- `agent-core/vendor/cline/algenta/plugins/mojo_gate.ts` — `AgentPlugin` post-`apply_patch` hook → run sim, veto (`HookControl`) if it regresses or breaches the calibrated-risk floor.
- `agent-core/package.json` start → `pluginPaths` includes the gate.
- **Exit:** apply is provably sim-gated inside the agent loop (provenance red line holds).

### Phase 3 — Capability plane as MCP
- Expose `/v1/capability-*` as an MCP server the agent can mount (read-only providers/bindings + `execute_capability` for `client_managed`).
- **Exit:** the agent can discover/execute governed capabilities through Cline's MCP path.

### Phase 4 — Multi-agent panel (scale)
- `enableAgentTeams` / parallel `Agent`s: localize · fix · verify specialists → synthesizer (multi-agent example pattern); reconcile to one calibrated decision.
- **Exit:** harder bugs solved by a panel; still one provenance-gated apply.

## 5. Verification (per phase)
- **G0 (`scripts/g0_token_benchmark.py`):** A (vanilla explore) vs C (Algenta tools + suppressed exploration) on real Cline — gate **C ≤ 0.25× A tokens, resolution within 5pp**. Report tokens/turns/wall-clock/resolution + expected cost.
- **Real-repo probe (`benchmarks/repository_intelligence_real_repo_probe.py`):** unchanged for the deterministic pipeline; agentic tier now exercises real Cline.
- **Contract tests:** keep the hermetic `verified_agentic` test green (stub server retained for offline CI); add a real-server smoke gated on `bun` + key presence (skip when absent, per the integration-test conftest).
- **Red lines:** calibrated-risk + provenance gates enforced by the Phase-2 hook; Cline attribution internal-only; no cloud egress (self-hosted boundary).
- **Air-gapped BYOM smoke:** run the full fixer with a local model (Ollama/LM Studio) + `ALGENTA_DEPLOYMENT_MODE=air_gapped`; assert resolution with **zero external network egress** (privacy-guard denies non-loopback) — proves the fully-private autonomous tier.

## 6. Risks / open questions
- **Build:** `bun run build` of the vendored SDK must succeed on this toolchain (node 23 / bun 1.3.14). If it fails, Phase 0 is blocked — fix before anything else.
- **Tool callback boundary:** tools call the FastAPI engine over loopback HTTP — needs the api_server running (or an in-process shim for tests). Decide: always-HTTP vs in-process for CI.
- **`completesRun` semantics:** confirm a `completesRun` tool that returns "do not apply" cleanly ends the run without a bad edit.
- **Token attribution:** `getAccumulatedUsage.aggregateUsage` includes subagents — use it (not `send().usage`) once multi-agent lands.
- **Cost:** real LLM calls on every agentic run; keep the G0 suite small + gate live runs behind explicit env.

### Research-grounded caveats (from `CLINE_SDK_RESEARCH.md`, verified 2026-06-10)
- **Privacy is scoped to Cline-the-vendor.** "Code never leaves / never indexed or cached / not used
  for training" holds for Cline, but **inference routes to whatever provider you configure**. Three
  blanket "everything client-side" claims were **refuted 0-3**. **Zero-egress requires BYOM local
  model (Ollama/LM Studio) or the Algenta engine via `registerHandler`** — design the air-gapped tier
  around that, not around Cline's posture alone.
- **`local` backend no-egress contract is unconfirmed** — verify telemetry/licensing/model-catalog
  refresh can all be disabled before claiming air-gapped.
- **gRPC unstable + SDK pre-1.0** — embed via `@cline/sdk`/`ClineCore`, pin the version, expect churn.
- **`ApiHandler` contract not fully extracted** — confirm the streaming/tool-call/usage surface a
  private engine must implement for `registerHandler` + `getAccumulatedUsage` before Phase 1.
- **Unverified, do not cite as fact:** the "1M-token context" / "Memory Bank" Cline-vs-Cursor claims
  did not survive verification.
