I now have everything confirmed: `AgentPlugin` is the public alias for `AgentExtension`, the `done` event carries `reason`/`text`/`iterations`/`usage`, `ToolCallRecord` gives the file-edit evidence (via `name`+`input` for `editor`/`apply_patch`), and `send`/`runTurn` returns `Promise<AgentResult | undefined>`. I have enough to write the authoritative reference.

# Cline SDK Interface Reference — Algenta Repositories Agent-Core Adapter

> Scope: the exact surface the `agent-core` adapter (`cline-adapter.ts`) must call to run a headless, auto-approved, single-shot agent task against any provider, with exploration tools blocked and an evidence bundle injected. Every signature below is copied from the vendored SDK under `agent-core/vendor/cline/sdk/`. Paths are relative to that root unless noted.

---

## 0. Package layout & imports

```
agent-core/vendor/cline/sdk/packages/
  core/    -> "@cline/core"   (ClineCore, LocalRuntimeHost, CoreSessionService, RuntimeCapabilities, AgentPlugin)
  llms/    -> "@cline/llms"   (provider catalog, getProviderCollection, createHandler, ProviderConfig)
  shared/  -> "@cline/shared" (AgentResult, AgentEvent, ToolPolicy, AgentPlugin hooks, ToolCallRecord)
  agents/  -> "@cline/agents" (agent runtime; policy resolution)
```

Public barrel: `packages/core/src/index.ts`. Notable re-exports verified there:
- `export { ClineCore } from "./ClineCore"` (line 162)
- `export * as Llms from "@cline/llms"` (line 7) → call as `Llms.getProviderCollection(...)`, `Llms.createHandler(...)`
- `export { AgentExtension as AgentPlugin }` (line 13) — **`AgentPlugin` is the public alias of `AgentExtension`**
- `export type { RuntimeCapabilities }`, `export { LocalRuntimeHost }` (lines 359, 368)

Typical import for the adapter:
```typescript
import { ClineCore, type AgentPlugin, type RuntimeCapabilities, Llms } from "@cline/core";
import type {
  AgentResult, AgentEvent, AgentFinishReason, ToolCallRecord, ToolPolicy,
} from "@cline/shared";
```

---

## 1. Headless lifecycle

The intended embedder path is `ClineCore.create() → subscribe() → start() → (await completion) → dispose()`. `ClineCore` wraps a `LocalRuntimeHost` + `CoreSessionService` for you when `backendMode:"local"`.

### 1.1 `ClineCore.create()`
`packages/core/src/ClineCore.ts:189`

```typescript
static async create(options: ClineCoreOptions = {}): Promise<ClineCore>
```

`ClineCoreOptions` (`packages/core/src/cline-core/types.ts:168`) — fields the adapter uses:

```typescript
interface ClineCoreOptions {
  clientName?: string;                 // SDK consumer id, e.g. "algenta-agent-core"
  backendMode?: RuntimeHostMode;       // "auto" | "local" | "hub" | "remote"; USE "local"
  capabilities?: RuntimeCapabilities;  // approval callback + tool-executor overrides (see §4)
  toolPolicies?: AgentConfig["toolPolicies"];  // instance-wide default tool policies (see §4)
  logger?: BasicLogger;
  telemetry?: ITelemetryService;       // omit -> no-op
  fetch?: typeof fetch;                // applied to local sessions only
  prepare?: (input: ClineCoreStartInput)
    => Promise<StartSessionBootstrap | undefined> | StartSessionBootstrap | undefined;
  // ...automation, hub, remote, distinctId, messagesArtifactUploader, sessionService (not needed for local headless)
}
```

`backendMode:"local"` forces always-in-process execution (no hub/websocket). This is the mode the adapter must use.

### 1.2 `start()`
`packages/core/src/ClineCore.ts:252` (two overloads)

```typescript
start(input: StartSessionInput): Promise<StartSessionResult>
start(input: ClineCoreStartInput): Promise<StartSessionResult>
```

**Critical semantic (verified at `ClineCore.ts:252-296`):** `start()` resolves as soon as the session is *launched*, not when the agent finishes. It returns `StartSessionResult` immediately; the run proceeds asynchronously. To observe completion you must either subscribe to the `done`/`ended` event (§2.3) or use the synchronous `send()` turn API (§2.4).

`StartSessionInput` (`packages/core/src/runtime/host/runtime-host.ts:100`):
```typescript
interface StartSessionInput {
  config: RuntimeSessionConfig;        // provider/model/systemPrompt/tool flags (transport-safe; see §1.5)
  source?: SessionSource;              // e.g. "chat" | "terminal" | "restart"
  prompt?: string;                     // the task to run
  interactive?: boolean;               // SET false for headless
  sessionMetadata?: Record<string, unknown>;
  initialMessages?: LlmsProviders.Message[];
  userImages?: string[];
  userFiles?: string[];
  localRuntime?: LocalRuntimeStartOptions;   // local bootstrap: hooks, logger, telemetry, extraTools, plugins
  capabilities?: RuntimeCapabilities;        // per-session override
  toolPolicies?: AgentConfig["toolPolicies"];// per-session override (see §4)
}
```

`ClineCoreStartInput` (`packages/core/src/cline-core/types.ts:127`) is the richer overload that carries the full `CoreSessionConfig` (with local-only callbacks/hooks):
```typescript
interface ClineCoreStartInput extends Omit<StartSessionInput, "config" | "localRuntime"> {
  config: CoreSessionConfig;                 // full config incl. hooks, extensions, plugins
  localRuntime?: LocalRuntimeStartOptions;
}
```

`StartSessionResult` (`runtime-host.ts:184`):
```typescript
interface StartSessionResult {
  sessionId: string;        // <- this is your agent_run_id
  manifest: SessionManifest;
  manifestPath: string;     // <session>/manifest.json on disk
  messagesPath: string;     // <session>/messages.json on disk
  result?: AgentResult;     // populated only on rare synchronous completion; do NOT rely on it
}
```

### 1.3 `subscribe()`
`packages/core/src/ClineCore.ts:542`

```typescript
subscribe(
  listener: (event: CoreSessionEvent) => void,
  options?: RuntimeHostSubscribeOptions,  // { sessionId?: string }
): () => void                              // returns unsubscribe
```
Subscribe *before* `start()` so you don't miss early events. Filter with `{ sessionId }` once you have it, or subscribe globally and match `payload.sessionId`.

### 1.4 `dispose()`
`packages/core/src/ClineCore.ts:374`

```typescript
async dispose(reason?: string): Promise<void>
```
Idempotent. Shuts down automation, closes the runtime host, tears down active sessions/bootstraps. Always call in a `finally`.

### 1.5 `RuntimeSessionConfig` vs `CoreSessionConfig`
`StartSessionInput.config` is the **transport-safe** `RuntimeSessionConfig` (`runtime-host.ts:59`) — it is `CoreSessionConfig` minus local-only callback keys and minus `checkpoint.createCheckpoint`/`compaction.compact`. For local headless you can pass the full `CoreSessionConfig` via the `ClineCoreStartInput` overload (so `hooks`, `extensions`, `extraTools`, `logger` are honored).

`CoreSessionConfig` (`packages/core/src/types/config.ts:168`) — the fields the adapter sets:
```typescript
interface CoreSessionConfig extends CoreModelConfig, CoreRuntimeFeatures, /* ...workspace, prompt, execution */ {
  sessionId?: string;
  workspaceRoot?: string;        // repo root
  systemPrompt: string;          // REQUIRED
  hooks?: AgentHooks;            // beforeTool/beforeModel etc. (see §4)
  logger?: BasicLogger;
  telemetry?: ITelemetryService;
  extraTools?: AgentTool[];      // inject custom tools
  pluginPaths?: string[];        // load AgentPlugins from disk (file:line config.ts:202)
  extensions?: AgentConfig["extensions"];  // in-memory plugins/extensions (config.ts:203)
  execution?: AgentConfig["execution"];    // maxIterations, etc.
  checkpoint?: CoreCheckpointConfig;
  compaction?: CoreCompactionConfig;
  skills?: string[];
  workspaceMetadata?: string;
  // ...
}
```
`CoreModelConfig` (`config.ts:24`):
```typescript
interface CoreModelConfig {
  providerId: string;            // e.g. "anthropic", "gemini"
  modelId: string;               // e.g. "claude-opus-4-1"
  apiKey?: string;
  baseUrl?: string;
  headers?: Record<string, string>;
  providerConfig?: ProviderConfig;
  knownModels?: Record<string, ModelInfo>;
  thinking?: boolean;
  reasoningEffort?: ProviderConfig["reasoningEffort"];  // "low"|"medium"|"high"|"xhigh"
}
```
`CoreRuntimeFeatures` (`config.ts:42`):
```typescript
interface CoreRuntimeFeatures {
  enableTools: boolean;
  enableSpawnAgent: boolean;
  enableAgentTeams: boolean;
  disableMcpSettingsTools?: boolean;
  yolo?: boolean;
}
```

### 1.6 CLI alternative: `CoreSessionService` + `ChatStartSessionRequest`
The CLI does not use `ClineCore`; it drives a `LocalRuntimeHost` directly and persists via `CoreSessionService`.

`CoreSessionService` (`packages/core/src/session/services/session-service.ts:263`):
```typescript
class CoreSessionService extends UnifiedSessionPersistenceService {
  constructor(
    store: SqliteSessionStore,
    options?: { sessionArtifactsDir?: string; messagesArtifactUploader?: SessionMessagesArtifactUploader; logger?: BasicLogger },
  );
  createRootSession(input: CreateRootSessionInput): void;
}
```

`ChatStartSessionRequest` (`packages/shared/src/rpc/runtime.ts:34`), the wire-level request the CLI builds:
```typescript
interface ChatStartSessionRequest extends ChatRuntimeConfig {
  sessionId?: string;
  workspaceRoot: string;
  provider: string;
  model: string;
  source?: string;
  interactive?: boolean;
}
interface ChatRuntimeConfig extends SessionPromptConfig {   // runtime.ts:9
  cwd?: string;
  apiKey?: string;
  enableTools: boolean;
  enableSpawn?: boolean;
  enableTeams?: boolean;
  autoApproveTools?: boolean;            // <- headless auto-approve switch (see §2.5)
  timeoutSeconds?: number;
  toolPolicies?: SessionExecutionConfig["toolPolicies"];
  // ...missionStepInterval, toolExecutors, configExtensions
}
```
**Recommendation for the adapter: use `ClineCore.create({ backendMode:"local" })`.** It instantiates the `SqliteSessionStore`/`CoreSessionService`/`LocalRuntimeHost` for you. Drop to the `CoreSessionService` path only if you need to own persistence.

---

## 2. Running a task to completion

### 2.1 Working directory
Set both:
- `config.workspaceRoot` = the repo root (`CoreSessionConfig.workspaceRoot`).
- For the CLI path, `ChatRuntimeConfig.cwd` and `ChatStartSessionRequest.workspaceRoot`. In `CoreSessionConfig`, `cwd` is carried via the workspace-config mixin; set `workspaceRoot` and the tools resolve relative paths against it.

### 2.2 Task input
- `prompt` (on `StartSessionInput`) is the task text. The CLI also exposes `SendSessionInput.prompt` for subsequent turns.
- `mode`: `AgentMode` is `"act" | "plan" | "yolo"`. Use `"act"` for a normal headed-less change run, `"yolo"` only when you also want auto-approve presets (see `ToolPresets.yolo`, `packages/core/src/extensions/tools/presets.ts:20`).
- `enableTools: true`, `enableSpawnAgent: false`, `enableAgentTeams: false` for a single-agent run.

### 2.3 Awaiting completion via events (the headless pattern with `start()`)
`CoreSessionEvent` union (`packages/core/src/types/events.ts:66`):
```typescript
type CoreSessionEvent =
  | { type: "chunk"; payload: SessionChunkEvent }
  | { type: "agent_event"; payload: { sessionId: string; event: AgentEvent; teamAgentId?: string; teamRole?: "lead" | "teammate" } }
  | { type: "team_progress"; payload: SessionTeamProgressEvent }
  | { type: "pending_prompts"; payload: SessionPendingPromptsEvent }
  | { type: "pending_prompt_submitted"; payload: SessionPendingPromptSubmittedEvent }
  | { type: "session_snapshot"; payload: SessionSnapshotEvent }
  | { type: "ended"; payload: SessionEndedEvent }       // { sessionId; reason: string; ... }
  | { type: "hook"; payload: SessionToolEvent }
  | { type: "status"; payload: { sessionId: string; status: string } };
```
The terminal agent signal is `agent_event` with an inner `AgentDoneEvent` (`packages/shared/src/agents/types.ts:169`):
```typescript
interface AgentDoneEvent extends AgentEventMetadata {
  type: "done";
  reason: AgentFinishReason;   // "completed"|"max_iterations"|"aborted"|"mistake_limit"|"error"
  text: string;                // final assistant text
  iterations: number;
  usage?: LegacyAgentUsage;
}
interface AgentErrorEvent {    // types.ts:181
  type: "error"; error: Error; recoverable: boolean; iteration: number;
}
```
`AgentFinishReason` (`packages/shared/src/agents/types.ts`):
```typescript
type AgentFinishReason = "completed" | "max_iterations" | "aborted" | "mistake_limit" | "error";
```
So the adapter wraps `start()` + `subscribe()` in a promise that resolves on the inner `done` event (or `ended`) — see §5.

### 2.4 Awaiting completion via `send()` (synchronous turn API)
`packages/core/src/ClineCore.ts:311` — `send` is literally `RuntimeHost["runTurn"]`:
```typescript
send(input: SendSessionInput): Promise<AgentResult | undefined>
```
`SendSessionInput` (`runtime-host.ts:192`):
```typescript
interface SendSessionInput {
  sessionId: string;
  prompt: string;
  mode?: AgentMode;                       // "act"|"plan"|"yolo"
  userImages?: string[];
  userFiles?: string[];
  delivery?: "queue" | "steer";
  timeoutMs?: number;
}
```
This **does** await the turn and returns `AgentResult`. A common headless pattern: `start({ ..., prompt: undefined, interactive:false })` to create the session, then `await send({ sessionId, prompt: task })` to run-and-await in one call. Either pattern (events or `send`) is valid; the §5 sketch uses the event pattern because it also streams progress to the NDJSON sidecar.

### 2.5 Auto-approve (the headless switch)
Two equivalent ways:
- **High level:** `ChatRuntimeConfig.autoApproveTools: true` (CLI path). 
- **Policy level (ClineCore path):** set `toolPolicies` with a wildcard, `{ "*": { autoApprove: true } }`. With no `requestToolApproval` callback and `autoApprove:true`, tools run without prompting. See §4.

### 2.6 Reading status / result
After completion, build the result from the `AgentResult` (`packages/shared/src/agents/types.ts:600`):
```typescript
interface AgentResult {
  text: string;
  usage: LegacyAgentUsage;          // { inputTokens, outputTokens, cacheReadTokens?, cacheWriteTokens?, totalCost? } (types.ts:546)
  messages: MessageWithMetadata[];
  toolCalls: ToolCallRecord[];
  iterations: number;
  finishReason: AgentFinishReason;
  model: { id: string; provider: string; info?: ModelInfo };
  startedAt: Date; endedAt: Date; durationMs: number;
}
```
If you used the event pattern (no `AgentResult` in hand), read it from the host:
- `await cline.readMessages(sessionId)` → `Message[]` (full transcript)
- `await cline.getAccumulatedUsage(sessionId)` → `SessionUsageSummary | undefined`. Shape (`packages/core/src/types/sessions.ts:9,28`): `{ leadUsage?, aggregateUsage?: { inputTokens; outputTokens; totalCost? } }`. `aggregateUsage` includes subagents (verified `ClineCore.ts:317`).
- `await cline.get(sessionId)` → `SessionRecord | undefined` (status, provider, model, cwd).

### 2.7 Which files changed
There is no single `result.filesChanged` field. Derive it from `ToolCallRecord[]` (`packages/shared/src/llms/tools.ts`):
```typescript
interface ToolCallRecord {
  id: string; name: string; input: unknown; output: unknown;
  error?: string; durationMs: number; startedAt: Date; endedAt: Date;
}
```
File mutations come from the write tools (§3): `editor`, `apply_patch`. Extract paths from each record where `name === "editor" || name === "apply_patch"` (and treat a non-empty `error` as a failed edit). This mirrors how compaction tracks `modifiedFiles` (`packages/core/src/extensions/context/compaction-shared.ts:23,388`). If you also enabled checkpoints, `session_snapshot` events / `restore` carry per-checkpoint file state.

---

## 3. ANY-provider support

### 3.1 Built-in provider list
`packages/llms/src/providers/ids.ts:8` — `BUILT_IN_PROVIDER` enum (exact ids):
```
anthropic, claude-code, cline,
openai-compatible, openai-native, openai-codex, openai-codex-cli, opencode,
bedrock, vertex, gemini,
ollama, lmstudio,
deepseek, xai, together, fireworks, groq, poolside, cerebras, sambanova,
nebius, baseten, requesty, litellm, huggingface, vercel-ai-gateway, v0,
aihubmix, hicap, nousResearch, huawei-cloud-maas, wandb, xiaomi, kilo,
zai, zai-coding-plan,
qwen, qwen-code, doubao, mistral, moonshot, asksage, minimax, dify, oca, sapaicore,
openrouter
```
`type ProviderId = BuiltInProviderId | (string & {})` (`packages/llms/src/providers/config.ts:33`) — any string is accepted (custom handlers). Aliases normalized via `normalizeProviderId()`: `openai → openai-compatible`, `togetherai → together`, `sap-ai-core → sapaicore`.

### 3.2 ProviderConfig / AuthConfig
`ProviderConfig` (`packages/llms/src/providers/config.ts:282`) extends `AuthConfig`, `EndpointConfig`, `ModelConfig`, `ReasoningConfig`, etc.
```typescript
interface AuthConfig {                          // config.ts:70
  apiKey?: string;
  accessToken?: string;
  refreshToken?: string;
  accountId?: string;
  oauthPath?: string;
}
interface ProviderConfig extends AuthConfig, EndpointConfig, ModelConfig, ReasoningConfig, /* ... */ {
  providerId: ProviderId;
  modelId: string;                              // from ModelConfig
  baseUrl?: string;                             // from EndpointConfig
  headers?: Record<string, string>;
  routingProviderId?: ProviderId;               // reuse a built-in's runtime behavior under a custom id
  capabilities?: ProviderCapability[];
  thinking?: boolean;
  reasoningEffort?: "low" | "medium" | "high" | "xhigh";
  abortSignal?: AbortSignal;
  // ...logger, extensionContext, codex/claudeCode/opencode opts
}
```
The serializable/persisted form is `ProviderSettings` (`packages/core/src/services/llms/provider-settings.ts:136`) with nested `AuthSettings` (`provider-settings.ts:55`):
```typescript
interface AuthSettings { apiKey?; accessToken?; refreshToken?; expiresAt?; accountId? }
```
Convert with `toProviderConfig(settings)` (`provider-settings.ts:198`).

### 3.3 Model id format
| Provider class | Format | Example |
|---|---|---|
| Anthropic / OpenAI direct | bare id | `claude-opus-4-1`, `gpt-4o` |
| Aggregators (openrouter, cline) | `provider/model` | `anthropic/claude-sonnet-4.6` |
| Regional / namespaced | bare or `Vendor/Model` | `qwen-plus-latest`, `Qwen/Qwen3.5-...` |
| Bedrock | AWS model arn-style | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Local (ollama/lmstudio) | user/discovery | (dynamic) |

### 3.4 Resolving API keys from `.env`
`getProviderCollection()` (`packages/llms/src/providers/model-registry.ts:56`):
```typescript
function getProviderCollection(providerId: string): Promise<ModelCollection | undefined>
function getProviderCollectionSync(providerId: string): ModelCollection | undefined
```
`ModelCollection.provider.env` (`packages/llms/src/catalog/types.ts:92`) is the ordered list of env var names for that provider's key (sourced from `BuiltinSpec.apiKeyEnv`, `packages/llms/src/providers/builtins.ts:48`):
```typescript
type ModelCollection = {
  provider: { id; name; defaultModelId; client; env?: string[]; /* ... */ };
  models: Record<string, ModelInfo>;
};
```
Examples: `anthropic → ["ANTHROPIC_API_KEY"]`, `gemini → ["GOOGLE_GENERATIVE_AI_API_KEY","GEMINI_API_KEY"]`, `openai-native → ["OPENAI_API_KEY"]`, `openrouter → ["OPENROUTER_API_KEY"]`.

So `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` are auto-picked up by walking `collection.provider.env` against `process.env`:
```typescript
const collection = await Llms.getProviderCollection(Llms.normalizeProviderId(provider));
const apiKey = (collection?.provider.env ?? []).map((k) => process.env[k]).find(Boolean);
const modelId = model ?? collection?.provider.defaultModelId;
```

### 3.5 Selecting provider + model + apiKey at start
Put them on `config` (`CoreModelConfig`) in the `start()` call:
```typescript
config: {
  providerId: provider, modelId, apiKey,
  systemPrompt, enableTools: true, enableSpawnAgent: false, enableAgentTeams: false,
  // baseUrl/headers optional; thinking/reasoningEffort optional
}
```
(If you need a handler outside a session, `Llms.createHandler(config)` / `Llms.createHandlerAsync(config)` from `packages/llms/src/providers.ts:70`.)

---

## 4. Tool control

### 4.1 Built-in tool names
`packages/core/src/extensions/tools/definitions.ts`:

| Tool name | Class | Purpose |
|---|---|---|
| `read_files` | exploration | read files/line ranges |
| `search_codebase` | exploration | regex search across repo |
| `run_commands` | exec | shell (also Windows variant) |
| `fetch_web_content` | exploration | fetch URLs |
| `apply_patch` | **write** | apply unified diffs |
| `editor` | **write** | create/insert/replace/view |
| `skills` | exec | invoke configured skills |
| `ask_question` | interactive | ask 2–5 option follow-up |
| `submit_and_exit` | control | final submission + exit |

Presets in `packages/core/src/extensions/tools/presets.ts:20`: `act`, `plan` (read-only), `search` (`read_files`+`search_codebase`), `minimal`, `yolo` (auto-approve all).

### 4.2 `toolPolicies` (auto-approve + suppression)
`ToolPolicy` (`packages/shared/src/llms/tools.ts:7`):
```typescript
interface ToolPolicy {
  enabled?: boolean;      // default true; false => tool cannot run at all (suppression)
  autoApprove?: boolean;  // default true; false => requires approval callback
}
```
`AgentConfig.toolPolicies` (`packages/shared/src/agents/types.ts:783`) is `Record<string, ToolPolicy>` plus an optional `requestToolApproval` callback. Resolution merges wildcard then tool-specific (`packages/agents/src/agent-runtime.ts:100`):
```typescript
{ ...(policies?.["*"] ?? {}), ...(policies?.[toolName] ?? {}) }
```
Headless auto-approve + block exploration tools via policy:
```typescript
const toolPolicies = {
  "*":                 { enabled: true,  autoApprove: true },   // headless default
  "read_files":        { enabled: false },                      // block exploration
  "search_codebase":   { enabled: false },
  "fetch_web_content": { enabled: false },
  "ask_question":      { enabled: false },                      // no interactivity
};
```

### 4.3 `RuntimeCapabilities` (approval + executor swap)
`packages/core/src/runtime/capabilities/runtime-capabilities.ts:4`:
```typescript
interface RuntimeCapabilities {
  toolExecutors?: Partial<ToolExecutors>;     // swap built-in implementations
  requestToolApproval?: (req: ToolApprovalRequest) => Promise<ToolApprovalResult> | ToolApprovalResult;
}
```
`ToolExecutors` keys (`packages/core/src/extensions/tools/types.ts:198`): `readFile, search, bash, webFetch, editor, applyPatch, skills, askQuestion, submit`. For pure headless, omit `requestToolApproval` and rely on `autoApprove:true`.

### 4.4 `AgentPlugin.beforeTool` — hard-block + inject evidence
`AgentPlugin` is the public alias of `AgentExtension` (`packages/core/src/index.ts:13`; def `packages/shared/src/agents/types.ts:489`):
```typescript
interface AgentExtension /* = AgentPlugin */ {
  name: string;
  manifest: PluginManifest;          // { capabilities: ["hooks", "tools", ...] }
  hooks?: AgentExtensionHooks;       // = Partial<AgentRuntimeHooks>
  setup?: (api: AgentExtensionApi, ctx: AgentExtensionContext) => void | Promise<void>;
}
```
Hook bag `AgentRuntimeHooks` (`packages/shared/src/agent.ts:333`): `beforeRun, afterRun, beforeModel, afterModel, beforeTool, afterTool, onEvent`.

`beforeTool` is in the execution path — returning `{ skip:true }` means the call **literally never runs** (`packages/shared/src/agent.ts:291`):
```typescript
interface AgentBeforeToolContext { snapshot; tool: AgentTool; toolCall: AgentToolCallPart; input: unknown }
interface AgentBeforeToolResult { skip?: boolean; stop?: boolean; reason?: string; input?: unknown }
```
Reference implementation: `examples/plugins/env-blocker.ts` blocks `read_files`/`run_commands` by inspecting `toolCall.toolName` + `input` and returning `{ skip:true, reason }`.

**Evidence injection** belongs in `beforeModel` (modify `systemPrompt` / append messages) — see `agent.ts` `beforeModel` returning `AgentBeforeModelResult`. Combine: `beforeTool` blocks exploration so the agent must consume your injected bundle; `beforeModel` injects it. Register the plugin on `config.extensions` (in-memory, `config.ts:203`) or `config.pluginPaths` (from disk, `config.ts:202`).

> Note: `toolPolicies` (§4.2) and the `beforeTool` hook are complementary. Policies are config-level gates; the hook is a runtime guarantee that also lets you mutate `input` and tailor the `reason` the model sees. Use both — policy `enabled:false` to suppress, hook as belt-and-suspenders + to nudge the model toward the evidence bundle.

---

## 5. `cline-adapter.ts` — concrete sketch

```typescript
// agent-core/src/cline-adapter.ts
import { ClineCore, Llms, type AgentPlugin, type RuntimeCapabilities } from "@cline/core";
import type {
  CoreSessionEvent, AgentEvent, AgentResult, AgentFinishReason, ToolCallRecord, ToolPolicy,
} from "@cline/shared";

export interface RunAgentArgs {
  working_dir: string;          // repo root
  task_spec: string;            // the prompt
  injected_context: string;     // evidence bundle (markdown/text)
  limits?: { maxIterations?: number; timeoutMs?: number };
  provider: string;             // "anthropic" | "gemini" | ...
  model?: string;               // optional; defaults to provider defaultModelId
}

export interface RunAgentResult {
  status: "completed" | "max_iterations" | "aborted" | "mistake_limit" | "error";
  agent_run_id: string;         // = sessionId
  text: string;
  iterations: number;
  files_changed: string[];
  usage?: { inputTokens: number; outputTokens: number; totalCost?: number };
  error?: string;
}

const WRITE_TOOLS = new Set(["editor", "apply_patch"]);
const EXPLORATION_TOOLS = ["read_files", "search_codebase", "fetch_web_content", "ask_question"];

export async function runAgent(args: RunAgentArgs): Promise<RunAgentResult> {
  // 1) Resolve provider/model/key from .env via the SDK catalog (§3.4)
  const providerId = Llms.normalizeProviderId(args.provider);
  const collection = await Llms.getProviderCollection(providerId);
  const apiKey = (collection?.provider.env ?? []).map((k) => process.env[k]).find(Boolean);
  const modelId = args.model ?? collection?.provider.defaultModelId;
  if (!modelId) throw new Error(`No model for provider ${providerId}`);
  if (!apiKey) throw new Error(`No API key in .env for ${providerId} (tried ${collection?.provider.env?.join(", ")})`);

  // 2) Tool policy: auto-approve everything, hard-suppress exploration (§4.2)
  const toolPolicies: Record<string, ToolPolicy> = { "*": { enabled: true, autoApprove: true } };
  for (const t of EXPLORATION_TOOLS) toolPolicies[t] = { enabled: false };

  // 3) Plugin: block exploration tools (defense-in-depth) + inject evidence (§4.4)
  const evidencePlugin: AgentPlugin = {
    name: "algenta-evidence",
    manifest: { capabilities: ["hooks"] },
    hooks: {
      beforeModel: async ({ request }) => ({
        ...request,
        systemPrompt:
          `${request.systemPrompt}\n\n[EVIDENCE BUNDLE — authoritative; do not explore the repo]\n${args.injected_context}`,
      }),
      beforeTool: async ({ toolCall }) =>
        EXPLORATION_TOOLS.includes(toolCall.toolName)
          ? { skip: true, reason: `Blocked ${toolCall.toolName}: use the injected evidence bundle.` }
          : undefined,
    },
  };

  // 4) Headless local instance (no approval callback => autoApprove governs) (§1.1, §4.3)
  const capabilities: RuntimeCapabilities = {};   // omit requestToolApproval
  const cline = await ClineCore.create({
    clientName: "algenta-agent-core",
    backendMode: "local",
    toolPolicies,
    capabilities,
  });

  // 5) Subscribe BEFORE start; resolve on inner AgentDoneEvent / error / ended (§2.3)
  const toolCalls: ToolCallRecord[] = [];
  let unsubscribe = () => {};
  const done = new Promise<{ reason: AgentFinishReason; text: string; iterations: number }>((resolve, reject) => {
    unsubscribe = cline.subscribe((evt: CoreSessionEvent) => {
      if (evt.type === "agent_event") {
        const a: AgentEvent = evt.payload.event;
        if (a.type === "content_end" && a.contentType === "tool" && a.toolName) {
          toolCalls.push({
            id: a.toolCallId ?? "", name: a.toolName, input: undefined,
            output: a.output, error: a.error, durationMs: a.durationMs ?? 0,
            startedAt: new Date(), endedAt: new Date(),
          });
        }
        if (a.type === "done")  resolve({ reason: a.reason, text: a.text, iterations: a.iterations });
        if (a.type === "error") reject(a.error);
      }
      // optional: forward evt to NDJSON sidecar stream here
    });
  });

  // 6) Start the run (returns immediately; run proceeds async) (§1.2)
  const started = await cline.start({
    config: {
      providerId, modelId, apiKey,
      workspaceRoot: args.working_dir,
      systemPrompt: "You are Algenta's repository agent. Apply the requested change.",
      enableTools: true, enableSpawnAgent: false, enableAgentTeams: false,
      execution: args.limits?.maxIterations ? { maxIterations: args.limits.maxIterations } : undefined,
      extensions: [evidencePlugin],     // in-memory plugin (config.ts:203)
    },
    source: "terminal",
    prompt: args.task_spec,
    interactive: false,
    toolPolicies,
  });
  const agent_run_id = started.sessionId;

  // 7) Await completion (+ timeout), then read result/usage/files (§2.6, §2.7)
  try {
    const fin = await withTimeout(done, args.limits?.timeoutMs);
    const usage = await cline.getAccumulatedUsage(agent_run_id);
    const filesChanged = filesFromToolCalls(toolCalls);
    return {
      status: fin.reason, agent_run_id, text: fin.text, iterations: fin.iterations,
      files_changed: filesChanged,
      usage: usage?.aggregateUsage && {
        inputTokens: usage.aggregateUsage.inputTokens,
        outputTokens: usage.aggregateUsage.outputTokens,
        totalCost: usage.aggregateUsage.totalCost,
      },
    };
  } catch (err) {
    await cline.abort(agent_run_id).catch(() => {});
    return { status: "error", agent_run_id, text: "", iterations: 0, files_changed: [], error: String(err) };
  } finally {
    unsubscribe();
    await cline.dispose("run_complete");   // §1.4 — idempotent
  }
}

function filesFromToolCalls(calls: ToolCallRecord[]): string[] {
  const paths = new Set<string>();
  for (const c of calls) {
    if (!WRITE_TOOLS.has(c.name) || c.error) continue;
    const inp = c.input as any;
    for (const p of [inp?.path, inp?.file, ...(Array.isArray(inp?.files) ? inp.files : [])]) {
      if (typeof p === "string") paths.add(p);
    }
  }
  return [...paths];
}

function withTimeout<T>(p: Promise<T>, ms?: number): Promise<T> {
  if (!ms) return p;
  return Promise.race([p, new Promise<T>((_, r) => setTimeout(() => r(new Error("timeout")), ms))]);
}
```

> **Alternative completion strategy (simpler, fewer events):** skip the `done`-event promise and instead `start({ ..., prompt: undefined })` then `const result = await cline.send({ sessionId, prompt: args.task_spec, mode: "act", timeoutMs })` — `send` returns `AgentResult` directly (§2.4), giving you `result.toolCalls` (with full `input`, so `filesFromToolCalls` is exact), `result.finishReason`, and `result.usage` without subscribing. Use the event pattern above when the NDJSON `/run` sidecar must stream incremental progress; use `send` when it only needs the final record.

---

### Quick file-path index
- `ClineCore` (create/start/subscribe/send/dispose/getAccumulatedUsage/readMessages): `packages/core/src/ClineCore.ts`
- Start input/result, `RuntimeSessionConfig`, `SendSessionInput`: `packages/core/src/runtime/host/runtime-host.ts`
- `ClineCoreOptions`, `ClineCoreStartInput`, `RestoreInput/Result`: `packages/core/src/cline-core/types.ts`
- `CoreSessionConfig`/`CoreModelConfig`/`CoreRuntimeFeatures`: `packages/core/src/types/config.ts`
- Events union: `packages/core/src/types/events.ts`
- `CoreSessionService`: `packages/core/src/session/services/session-service.ts`
- `ChatStartSessionRequest`/`ChatRuntimeConfig`: `packages/shared/src/rpc/runtime.ts`
- `AgentResult`/`AgentEvent`/`AgentDoneEvent`/`AgentFinishReason`/`LegacyAgentUsage`: `packages/shared/src/agents/types.ts`
- `ToolCallRecord`/`ToolPolicy`/`ToolApprovalRequest`: `packages/shared/src/llms/tools.ts`
- Hook bag + `beforeTool`/`beforeModel` contexts: `packages/shared/src/agent.ts`
- `AgentPlugin`/`AgentExtension`: `packages/shared/src/agents/types.ts` (alias re-export `packages/core/src/index.ts:13`)
- Built-in tools + presets: `packages/core/src/extensions/tools/definitions.ts`, `.../presets.ts`
- `RuntimeCapabilities`/`ToolExecutors`: `packages/core/src/runtime/capabilities/runtime-capabilities.ts`, `packages/core/src/extensions/tools/types.ts`
- Provider ids/config/builtins/catalog/registry: `packages/llms/src/providers/{ids,config,builtins,model-registry}.ts`, `packages/llms/src/catalog/types.ts`
- `ProviderSettings`/`AuthSettings`/`toProviderConfig`: `packages/core/src/services/llms/provider-settings.ts`
- Plugin reference: `examples/plugins/env-blocker.ts`