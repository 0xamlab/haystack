---
sidebar_position: 2
slug: /sdks/typescript
---

# TypeScript SDK

Use the TypeScript SDK after the service is already running.

Start with [Quickstart](/quickstart), then authenticate with [API Authentication](/api-reference/authentication).

## Install

```bash
npm install algenta-sdk
```

`AlgentaClient` is the preferred public name. `DecisionEngineClient` remains available as a compatibility alias.

## API keys

```typescript
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "http://localhost:8000",
});

const created = await client.createApiKey({
  label: "mission-runtime",
  expires_at: "2028-05-19T00:00:00Z",
  device_limit: 3,
});
const identity = await client.me();
const usage = await client.usage();
const limits = await client.limits();
const keys = await client.listApiKeys();

console.log(created.raw_key);
console.log(created.key_prefix);
console.log(created.device_limit);
console.log(created.expires_at);
console.log(identity.email);
console.log(usage.billing_period, usage.quota_used_pct);
console.log(limits.plan, limits.rate_limit_per_minute);
console.log(keys.length);
```

The `raw_key` value is returned only once on creation. Store it, along with
`id`, `key_prefix`, `device_limit`, and `expires_at`, before revoking or
rotating the previous key.

## Provider-backed LLM models

Configure provider-backed models through `ALGENTA_LLM_PROVIDER_MODELS_JSON`.
Each entry must declare `id`, `backend`, `model_name`, `base_url`, and
`api_key_env` unless the backend explicitly allows local no-auth access.
Use `model_name` as the canonical upstream model field. Legacy `upstream_model`
is still accepted for backward compatibility.
`capabilities` is optional; when omitted, the runtime defaults to the full
capability set supported by that backend.

Supported backends:

- `openai_compatible`
- `openai`
- `anthropic` for chat-completions only
- `ollama` for local chat-completions and embeddings, with optional `api_key_env`
- `google_genai` for Gemini chat-completions and embeddings
- `mistral` for Mistral chat-completions and embeddings
- `cohere` for Cohere V2 chat-completions and embeddings
- `groq` for Groq chat-completions
- `xai` for xAI chat-completions and embeddings
- `router` for deterministic ordered multi-provider routing over `targets`

```bash
export ALGENTA_LLM_PROVIDER_MODELS_JSON='[
  {
    "id": "provider.openai-gpt-4o-mini",
    "backend": "openai",
    "model_name": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
    "chat_timeout_seconds": 12.5,
    "embedding_timeout_seconds": 9.0
  },
  {
    "id": "provider.ollama-gemma3",
    "backend": "ollama",
    "model_name": "gemma3",
    "base_url": "http://127.0.0.1:11434"
  },
  {
    "id": "provider.google-gemini-flash",
    "backend": "google_genai",
    "model_name": "gemini-2.0-flash",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "api_key_env": "GOOGLE_API_KEY"
  },
  {
    "id": "provider.mistral-small",
    "backend": "mistral",
    "model_name": "mistral-small-latest",
    "base_url": "https://api.mistral.ai/v1",
    "api_key_env": "MISTRAL_API_KEY"
  },
  {
    "id": "provider.command-a",
    "backend": "cohere",
    "model_name": "command-a-03-2025",
    "base_url": "https://api.cohere.com",
    "api_key_env": "COHERE_API_KEY"
  },
  {
    "id": "provider.groq-llama",
    "backend": "groq",
    "model_name": "llama-3.3-70b-versatile",
    "base_url": "https://api.groq.com/openai/v1",
    "api_key_env": "GROQ_API_KEY"
  },
  {
    "id": "provider.xai-grok",
    "backend": "xai",
    "model_name": "grok-4.3",
    "base_url": "https://api.x.ai/v1",
    "api_key_env": "XAI_API_KEY"
  },
  {
    "id": "provider.router-fast-chat",
    "backend": "router",
    "capabilities": ["chat_completions"],
    "targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"],
    "fallback_policy": "retryable_only",
    "fallback_on": ["provider_rate_limited", "provider_timeout"],
    "timeout_seconds": 18.0,
    "max_attempts": 2
  },
  {
    "id": "provider.router-split",
    "backend": "router",
    "capabilities": ["chat_completions", "embeddings"],
    "chat_targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"],
    "embedding_targets": ["provider.openai-gpt-4o-mini"],
    "chat_fallback_policy": "retryable_only",
    "chat_fallback_on": ["provider_rate_limited"],
    "embedding_fallback_policy": "disabled",
    "embedding_fallback_on": ["provider_backend_error"],
    "chat_max_attempts": 2,
    "embedding_max_attempts": 1
  }
]'
```

After registration, use `client.listModels()` to verify the catalog and route
requests through `client.chatCompletions(...)`, `client.responses(...)`, or
`client.embeddings(...)` when the selected backend supports that capability.
Router entries omit transport fields and fail over across ordered `targets`
only when a target returns retryable provider transport/backend errors.
Use `chat_targets` and `embedding_targets` when chat and embeddings should route
through different ordered provider lists. Use shared `fallback_policy` to govern
all routed capabilities, or `chat_fallback_policy` / `embedding_fallback_policy`
to override failover behavior per capability. Use shared `fallback_on`, or
`chat_fallback_on` / `embedding_fallback_on`, to restrict which retryable
provider error codes may trigger failover. Use shared `max_attempts` to cap the
routed attempt budget across all capabilities, or `chat_max_attempts` /
`embedding_max_attempts` to bound retries per capability. Use shared
`timeout_seconds`, or `chat_timeout_seconds` / `embedding_timeout_seconds`, to
set provider HTTP timeouts; router aliases can use the same fields to override
the timeout budget applied to their routed targets. Use `header_envs` to require
additional upstream headers from environment variables; `listModels()` exposes
only the required header names under `required_provider_headers`. The same
catalog entry also exposes `chat_required_provider_headers`,
`embedding_required_provider_headers`, `chat_provider_auth_env_vars`,
`embedding_provider_auth_env_vars`, `chat_provider_auth_configured`,
`embedding_provider_auth_configured`, plus the aggregate
`provider_auth_env_vars` and `provider_auth_configured`, so self-hosted
deployments can verify the full provider auth contract without leaking secret
values. Router-backed entries also expose `resolved_routing_targets`,
`resolved_chat_routing_targets`, and `resolved_embedding_routing_targets` so the
catalog shows the flattened leaf providers that execution can actually select.

Use `client.me()`, `client.usage()`, `client.limits()`, and
`client.distributions()` / `client.templates()` for the hosted distribution and template catalogs,
`client.getBillingInfo()` for the hosted account/control-plane read surfaces,
`client.updateMe({ name, org_name })` for the hosted identity/profile update surface,
`client.createBillingCheckout({ plan })` / `client.createBillingPortal()` for
billing-session handoff, `client.refreshCredits({ device_id, billing_period, credits_used })`
for one runtime credit-batch refresh request, and `client.listApiKeys()` / `client.revokeApiKey(keyId)`
for deterministic key inventory and rotation.
Use `client.listTeamMembers({ page, limit })`, `client.inviteTeamMember({ email, role })`,
`client.updateTeamMemberRole(userId, role)`, and `client.removeTeamMember(userId)`
for the hosted team-governance surface.
Use `client.getAuditLogs({ ... })` and `client.getAuditLogArtifacts({ ... })`
for lineage-aware audit review, including immutable content-hash-backed
artifacts, and `client.listExecutionPolicySnapshots()` for stored
execution-policy lineage.

If you set an explicit `device_limit`, that cap also applies to ordinary hosted
API traffic for the key. The TypeScript SDK sends the stable device headers
automatically, including device ID, platform, and hostname hash, and persists
the hosted device binding token for repeated same-device requests. Set
`ALGENTA_DEVICE_ID` or `DE_DEVICE_ID` only when you need a deterministic
service identity across restarts.

## Simulate

```typescript
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "http://localhost:8000",
});

const result = await client.simulate({
  mode: "auto",
  scenario: {
    variables: {
      revenue: { low: 80000, high: 200000 },
      cost: { low: 30000, high: 90000 },
    },
    objective: "maximize_net_value",
  },
  runs: 10000,
  seed: 42,
});

console.log(result.recommended_action);
```

## Async jobs

```typescript
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "http://localhost:8000",
});

const job = await client.submitJob({
  mode: "auto",
  scenario: {
    variables: {
      revenue: { low: 80000, high: 200000 },
      cost: { low: 30000, high: 90000 },
    },
    objective: "maximize_net_value",
  },
  runs: 10000,
  seed: 42,
});

const status = await client.getJob(job.job_id);
if (status.status === "completed") {
  const result = await client.getJobResult(job.job_id);
  console.log(result);
} else if (status.status === "queued" || status.status === "running") {
  const result = await client.pollJob(job.job_id, {
    timeoutMs: 60_000,
    pollIntervalMs: 2_000,
  });
  console.log(result);
} else {
  await client.cancelJob(job.job_id);
}

const webhook = await client.testWebhookDelivery("https://example.test/webhook");
console.log(webhook.status_code, webhook.message);

const trigger = await client.registerTrigger({
  name: "Revenue alert",
  condition: {
    source_id: "src_orders",
    metric_hint: "revenue",
    threshold: 200000,
    direction: "above",
    aggregation: "sum",
  },
  simulation_template: {
    mode: "auto",
    scenario: {
      variables: { revenue: { low: 100000, high: 250000 } },
      objective: "maximize_net_value",
    },
  },
});
const paused = await client.pauseTrigger(trigger.trigger_id, { paused: true });
console.log(paused.status);
```

The direct client also exposes the deterministic utility-model helper lane,
including:

- `client.resolveArtifactBridge({ repo_id, filename, revision, local_files_only })`

## Decision runtime helpers

```typescript
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "http://localhost:8000",
});

const recommendation = await client.recommend(
  [
    {
      name: "expand",
      request: {
        mode: "expert",
        runs: 250,
        simulation: {
          variables: [{ name: "outcome", distribution: "fixed", params: { value: 140000 } }],
          objective_function: "outcome",
        },
      },
    },
    {
      name: "hold",
      request: {
        mode: "expert",
        runs: 250,
        simulation: {
          variables: [{ name: "outcome", distribution: "fixed", params: { value: 90000 } }],
          objective_function: "outcome",
        },
      },
    },
  ],
  { runs: 250, seed: 42 },
);

const score = await client.score(
  {
    mode: "expert",
    runs: 250,
    simulation: {
      variables: [{ name: "outcome", distribution: "normal", params: { mean: 100, std: 10 } }],
      objective_function: "outcome",
    },
  },
  { expected_value: 0.7, downside_risk: 0.3 },
);

const batch = await client.batch([
  {
    mode: "expert",
    runs: 100,
    simulation: {
      variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
      objective_function: "outcome",
    },
  },
  {
    mode: "expert",
    runs: 100,
    simulation: {
      variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
      objective_function: "outcome",
    },
  },
]);

const compared = await client.compare([
  {
    name: "base",
    request: {
      mode: "expert",
      runs: 150,
      simulation: {
        variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
        objective_function: "outcome",
      },
    },
  },
  {
    name: "stretch",
    request: {
      mode: "expert",
      runs: 150,
      simulation: {
        variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
        objective_function: "outcome",
      },
    },
  },
]);

const logged = await client.logDecision({
  chosen_action: "expand",
  context: "Launch planning",
  expected_value: 128000,
});
const decisions = await client.listDecisions({ page: 1, limit: 20, with_outcome_only: true });
const fetchedDecision = await client.getDecision(logged.id);
const recordedOutcome = await client.recordOutcome(logged.id, {
  actual_outcome: 141000,
  outcome_notes: "Launch outperformed baseline",
});
const executionReceipt = await client.executeDecision(logged.id, {
  webhook_url: "https://hooks.example.test/decision",
  timeout_seconds: 15,
});
await client.deleteDecision(logged.id);

console.log(recommendation.recommended_action);
console.log(score.score);
console.log(batch.total);
console.log(compared.winner);
console.log(decisions.total);
console.log(fetchedDecision.chosen_action);
console.log(recordedOutcome.outcome_delta);
console.log(executionReceipt.execution_status);
```

## Discovery and governed query helpers

```typescript
import { AlgentaClient, type QueryFilterSpec } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "http://localhost:8000",
});

const datasets = await client.listDatasets({
  search: "orders",
  status: "ready",
  sourceName: "warehouse_postgres",
  compact: true,
});
const summary = await client.getDatasetSummary(datasets.datasets[0].dataset_id);
const completedOrders: QueryFilterSpec = {
  time_filter: "last_year",
  conditions: [{ dimension_hint: "status", op: "eq", value: "completed" }],
};

const query = await client.queryWithMetadata({
  dataset_id: datasets.datasets[0].dataset_id,
  filter: completedOrders,
  metric: { role: "metric", hint: "gross_revenue" },
  aggregation: "sum",
});

const batch = await client.queryBatch({
  defaults: { dataset_id: datasets.datasets[0].dataset_id, filter: completedOrders },
  queries: [
    { key: "completed_orders", request: { metric: { role: "metric", hint: "order_count" }, aggregation: "sum" } },
    { key: "monthly_completed_orders", request: { metric: { role: "metric", hint: "order_count" }, aggregation: "sum", group_by: ["order_month"], limit: 12, order: "desc" } },
  ],
});

const report = await client.querySqlReport({
  sources: [{ dataset_id: datasets.datasets[0].dataset_id, alias: "orders" }],
  sql: "select order_month, gross_revenue from orders",
  max_rows: 100,
});

const previewTest = await client.previewTestConnector({
  connector: { type: "rest", url: "https://example.test/orders.json", data_path: "items" },
});
const previewBrowse = await client.previewBrowseConnector({
  connector: { type: "rest", url: "https://example.test/orders.json", data_path: "items" },
});

console.log(previewTest.status);
console.log(previewBrowse.items.slice(0, 1));

const savedConnector = await client.createConnector({
  name: "orders-rest",
  connector_type: "rest",
  description: "Managed REST connector for orders",
  config: { url: "https://example.test/orders.json", data_path: "items" },
});
const testedConnector = await client.testConnector(savedConnector.id);
const browsedConnector = await client.browseConnector(savedConnector.id);
const updatedConnector = await client.updateConnector(savedConnector.id, {
  description: "Managed REST connector for refreshable orders",
});

const created = await client.connectData({
  connection_type: "api",
  provider: "rest",
  dataset_name: "orders-refreshable",
  description: "Refreshable orders dataset",
  connection_config: { url: "https://example.test/orders.json", data_path: "items" },
});

const refreshed = await client.refreshDataset(created.dataset_id);
const detail = await client.getDataset(created.dataset_id);

console.log(
  testedConnector.status,
  browsedConnector.total,
  updatedConnector.description,
  refreshed.status,
  detail.dataset.dataset_id,
);
```

## Unified capability plane

Use the capability-plane methods when you want one customer-agnostic discovery
and routing surface across connectors, MCP providers, prompt-skills, native
tools, and runtime libraries.

```typescript
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "http://localhost:8000",
});

const providers = await client.listCapabilityProviders();
const skills = await client.listSkills();
const mcpProviders = await client.listMcpProviders();

const route = await client.routeCapabilities({
  objective: "Escalate the production incident and use the right tool",
  kinds: ["skill", "mcp_tool", "native_tool"],
  artifact_affinities: ["incident"],
  tags: ["incident", "escalation"],
});

const selected = await client.getCapability(route.selected_capability_id);
console.log(route.kind, route.execution_owner, route.selected_capability_id);
console.log(selected.name, selected.required_policy);
console.log(providers[0]?.provider_id, skills.length, mcpProviders.length);

if (route.kind !== "skill") {
  const execution = await client.executeCapability({
    capability_id: route.selected_capability_id,
    input: { ticket_id: "INC-123" },
  });
  console.log(execution.status, execution.execution_owner);
}
```

These route and execution methods are the same public control-plane contract
used by hosted, self-hosted, and hybrid customer apps. Use
`listCapabilityBindings(...)`, `createCapabilityBinding(...)`,
`previewTestCapabilityBinding(...)`, `previewDiscoverCapabilityBinding(...)`,
`startCapabilityAuthorization(...)`, and `completeCapabilityAuthorization(...)`
when you need to manage the binding lifecycle explicitly before routing.

## Repository intelligence

```typescript
const snapshot = await client.createRepositorySnapshot("repo_123", {
  ref: "main",
  include_patterns: ["apps/**", "packages/**", "tests/**"],
  exclude_patterns: ["**/node_modules/**", "**/dist/**"],
  max_files: 20000,
});

const triage = await client.triageRepository("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  signals: {
    issue_text: "Production regression after the latest deploy",
    diagnostics: [
      {
        path: "apps/api_server/services/repository_intelligence.py",
        line: 2047,
        severity: "error",
        message: "Repository analysis is missing patch impact metadata.",
      },
    ],
    failing_tests: ["tests/test_repository_intelligence_service.py::test_simulate_requires_patch_impact"],
    changed_files: ["apps/api_server/services/repository_intelligence.py"],
    workspace_context: ["incident-1842", "jira-912"],
  },
  max_evidence_items: 12,
  token_budget: 4000,
});

const planRevision = await client.createRepositoryDecisionPlan("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
  model: "gpt-5.1",
});

const simulation = await client.simulateRepository("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: planRevision.decision_plan_id,
  runs: 5000,
  seed: 42,
});

const patchOnly = await client.applyRepository("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: planRevision.decision_plan_id,
  simulation_id: String(simulation.validated_inputs?.simulation_id),
  mode: "patch_only",
});

console.log(planRevision.decision_plan.repository_analysis?.patch_impact_report_ref);
console.log(simulation.recommended_action, simulation.score_breakdown);
console.log(patchOnly.patch);
```

`createRepositoryDecisionPlan(...)` creates the immutable stored revision behind
`POST /v1/repositories/{repository_id}/decision-plans`. The SDK keeps the method
singular as a verb while the API stays plural as a resource.

If you want a fully local self-hosted repository planner, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`.
That planner is explicit and bounded; it currently supports deterministic
Python return-literal mismatch repairs and fails closed with
`repository_local_planner_unsupported` when the evidence bundle does not match
that contract.

Every stored repository `DecisionPlan` also records planner provenance in
`decision_plan.repository_analysis` through `planner_model_id`,
`planner_execution_mode`, and `planner_provider_backend`.

Use these surfaces as follows:

- `getContract()` when you need the live machine-readable Codna contract from the running service
- `getRuntimeManifest()`, `getRuntimeModules()`, `getRuntimeBenchmarks()`, and `getRuntimeReleaseValidation()` when you need the signed runtime proof surfaces from the running service
- `getRuntimeBenchmarks()` also includes benchmark-class `evidence_paths`, so benchmark claims retain concrete artifact linkage rather than only code and description labels
- `getRuntimeBenchmarks()` currently exposes the quality-gate benchmark classes `B6` checkpoint and replay overhead, `B7` MCP tool latency, `B9` RAG retrieval quality and latency, and `B10` decision workflow completion latency
- `B10` is currently backed by the Repository Intelligence workflow artifact at `build/repository_intelligence_benchmark.json`
- `getRuntimeBenchmarks()` currently exposes the quality-gate SLO budgets `mcp_call_first_party`, `decision_plan_creation`, and `replay`
- `listAgentRuns({ ... })` for paginated persisted agent-run inventory with lineage-aware filters
- `listAgentRunCheckpoints(runId)` and `queryAgentRunCheckpoints({ ... })` for checkpoint inspection and cross-run checkpoint discovery
- `listAgentRunMissionEvents(runId, { limit })` and `queryAgentRunMissionEvents({ ... })` for canonical mission-event inspection
- `listAgentRunTelemetry(runId, { limit })` and `queryAgentRunTelemetry({ ... })` for persisted runtime telemetry inspection
- `replayAgentRun(runId, { checkpoint_id })` and `forkAgentRun(runId, { checkpoint_id })` for deterministic replay and branch-from-checkpoint flows
- `getAuditLogs({ ... })`, `getAuditLogArtifacts({ ... })`, and `listExecutionPolicySnapshots()` for control-plane lineage, immutable audit artifacts, and policy snapshot review
- `createConnector(...)`, `getConnector(...)`, `updateConnector(...)`, `testConnector(...)`, `browseConnector(...)`, and `deleteConnector(...)` for the saved connector lifecycle
- `createRepositorySnapshot(...)` and `getRepositorySnapshot(...)` for immutable repository snapshot lineage
- `triageRepository(...)` for deterministic repository narrowing into a bounded workspace evidence bundle
- `queryRepositoryGraph(...)` for dependency, dependent, and change-risk graph inspection from a snapshot or workspace evidence bundle
- `createRepositoryDecisionPlan(...)` for stored immutable repository `DecisionPlan` revisions with `repository_analysis`
- `simulateRepository(...)` for policy-gated repository risk simulation with populated `decision_plan` and `score_breakdown`
- `applyRepository(...)` for `patch_only`, `local_branch`, or `remote_pr` application after simulation passes the apply gate
- `listDatasets(..., compact: true)` and `getDatasetSummary()` for low-token dataset discovery
- `previewTestConnector({ connector })` and `previewBrowseConnector({ connector })` for one-shot inline connector validation before saving a reusable connector or starting an import
- `connectData(...)`, `getDataset(...)`, `refreshDataset(...)`, and `deleteDataset(...)` for the refreshable dataset lifecycle
- `queryWithMetadata()` when you need stable request/cost/latency metadata
- `queryBatch()` for multiple governed exact queries in one API call
- `querySqlReport()` for read-only wide reports over already authorized datasets
- `QueryFilterSpec` / `QueryFilterCondition` for deterministic `status`,
  `category`, boolean, numeric, or null filters without inventing private
  request shapes

These filters follow a **record-filter contract**, not SQL clauses. The same
payload is meant to work for SQL-backed datasets, Redis and other non-SQL sources,
and normalized file-backed datasets.

The package root also exports the shared public contract constants:

```typescript
import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from "algenta-sdk";

console.log(DEFAULT_BASE_URL);
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint);
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.query_batch_endpoint);
console.log(PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract.type_behavior.numeric);
```

## Local consumer sync checklist

If a local app still only exposes a pagination-only `listDatasets(...)` shape,
it is using a stale `algenta-sdk` build or a vendored copy that has not been
synced yet.

1. Rebuild the package from the repo root:

```bash
pnpm build
```

If you only want the SDK package build without the gateway package, the
package-local form still works:

```bash
pnpm --dir packages/ts-sdk build
```

2. Restart the consuming app or dev server after the build completes.
3. Verify the local package now exposes:
   - `getContract()`
   - `listAgentRuns({ status, request_hash, policy_snapshot_id, schema_snapshot_id, page, limit })`
   - `listAgentRunCheckpoints(runId)`
   - `queryAgentRunCheckpoints({ status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, checkpoint_id, page, limit })`
   - `listAgentRunMissionEvents(runId, { limit })`
   - `queryAgentRunMissionEvents({ status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, event_type, page, limit })`
   - `listAgentRunTelemetry(runId, { limit })`
   - `queryAgentRunTelemetry({ status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, telemetry_kind, module_name, page, limit })`
   - `getAuditLogs({ page, limit, ...filters })`
   - `getAuditLogArtifacts({ page, limit, ...filters, content_hash })`
   - `listExecutionPolicySnapshots()`
   - `listDatasets({ search, status, sourceName, page, limit, compact })`
   - `getDatasetSummary(datasetId)`
   - `queryWithMetadata(request)`
   - `queryBatch(request)`
   - `querySqlReport(request)`

## Local runtime libraries

```typescript
import { libraries } from "algenta-sdk";

const catalog = await libraries({
  mode: "local",
  tcpAddress: process.env.ALGENTA_DAEMON_TCP ?? "127.0.0.1:50099",
});

const modules = catalog.listModules();
const sample = await catalog.ab_testing.sample_size_proportion({
  p1: 0.10,
  p2: 0.12,
  alpha: 0.05,
  power: 0.8,
});

console.log(modules.length, sample);
```

Use `AlgentaClient` for the running service and `libraries()` only for the local daemon-backed Mojo catalog.

This surface is local/runtime-backed in this rollout. Customer apps and other
external clients can execute runtime-owned Mojo libraries without importing
source files, but they must run the local Codna runtime daemon first.

## Optional local runtime

The local runtime and development CLI remain available through `algenta-core`, but they are secondary to the running service.

For the unified capability plane, local runtime execution only supports
`client_managed` capabilities. `algenta_managed` capabilities remain
discoverable and routable in local mode, but execution fails closed until you
switch back to the running Codna service.
