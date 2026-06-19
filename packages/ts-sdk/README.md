# algenta-sdk

TypeScript and JavaScript SDK for Algenta public data, query, and simulation APIs.

## Install

```bash
npm install algenta-sdk
```

## Root Contract Exports

```ts
import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from "algenta-sdk";

console.log(DEFAULT_BASE_URL);
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint);
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.query_batch_endpoint);
console.log(PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract.operators.scalar);
```

## Unified Capability Plane

```ts
const route = await client.routeCapabilities({
  objective: "Investigate the latest checkout incident and route me to the right specialist path.",
  kinds: ["dataset", "skill", "mcp_tool", "runtime_library"],
  artifact_affinities: ["incident"],
  tags: ["incident", "triage"],
});

const capability = await client.getCapability(route.selected_capability_id, {
  includeInstruction: true,
});
const execution = await client.executeCapability({
  capability_id: route.selected_capability_id,
  binding_id: route.selected_binding_id,
  input: {
    objective: "Investigate the latest checkout incident and route me to the right specialist path.",
    requested_output: "instruction_bundle",
  },
});

const providers = await client.listCapabilityProviders();
const skills = await client.listSkills();
const mcpProviders = await client.listMcpProviders();
```

The direct client now exposes a single customer-agnostic capability plane over
data connectors, MCP providers, skills, native tools, and runtime libraries.
Execution ownership remains authoritative: `algenta_managed` capabilities must
execute through the Algenta service, while local runtime adapters only execute
`client_managed` capabilities and fail closed otherwise.
Checked-in request artifacts and runnable examples live in
`examples/capability-plane/` and `examples/langgraph/capability_router.py`.

## Direct Client Flow

```ts
import { AlgentaClient, type QueryFilterSpec } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "https://api.codna.ai",
});

const datasets = await client.listDatasets({ search: "orders", compact: true });
const contract = await client.getContract();
const summary = await client.getDatasetSummary(datasets.datasets[0].dataset_id);
const completedOrders: QueryFilterSpec = {
  time_filter: "last_year",
  conditions: [{ dimension_hint: "status", op: "eq", value: "completed" }],
};

const query = await client.queryWithMetadata({
  dataset_id: summary.dataset_id,
  filter: completedOrders,
  metric: { hint: "gross_revenue" },
  aggregation: "sum",
});

const batch = await client.queryBatch({
  defaults: {
    dataset_id: summary.dataset_id,
    filter: completedOrders,
  },
  queries: [
    {
      key: "completed_orders",
      request: {
        metric: { hint: "order_count" },
        aggregation: "sum",
      },
    },
    {
      key: "monthly_completed_orders",
      request: {
        metric: { hint: "order_count" },
        aggregation: "sum",
        group_by: ["order_month"],
        limit: 12,
        order: "desc",
      },
    },
  ],
});

const report = await client.querySqlReport({
  sources: [{ dataset_id: summary.dataset_id, alias: "orders" }],
  sql: "SELECT order_month, gross_revenue FROM orders ORDER BY order_month DESC LIMIT 12",
  max_rows: 100,
});
```

## Connectors + Refreshable Dataset Flow

```ts
const previewTestedConnector = await client.previewTestConnector({
  connector_type: "rest",
  config: {
    url: "https://example.test/orders.json",
    data_path: "items",
  },
});
const previewBrowsedConnector = await client.previewBrowseConnector({
  connector_type: "rest",
  config: {
    url: "https://example.test/orders.json",
    data_path: "items",
  },
});

const savedConnector = await client.createConnector({
  name: "orders-rest",
  connector_type: "rest",
  description: "Managed REST connector for orders",
  config: {
    url: "https://example.test/orders.json",
    data_path: "items",
  },
});

const connectorDetail = await client.getConnector(savedConnector.id);
const updatedConnector = await client.updateConnector(savedConnector.id, {
  description: "Managed REST connector for refreshable orders",
});
const testedConnector = await client.testConnector(savedConnector.id);
const browsedConnector = await client.browseConnector(savedConnector.id);

const created = await client.connectData({
  connection_type: "api",
  provider: "rest",
  dataset_name: "orders-refreshable",
  description: "Refreshable orders dataset",
  connection_config: {
    url: "https://example.test/orders.json",
    data_path: "items",
  },
});

const refreshed = await client.refreshDataset(created.dataset_id);
const datasetDetail = await client.getDataset(created.dataset_id);

await client.deleteDataset(created.dataset_id);
await client.deleteConnector(savedConnector.id);
```

## Repository Intelligence Flow

```ts
const snapshot = await client.createRepositorySnapshot("repo_123", {
  ref: "main",
  include_patterns: ["apps/**", "packages/**", "tests/**"],
  exclude_patterns: ["**/node_modules/**", "**/dist/**"],
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
});

const planRevision = await client.createRepositoryDecisionPlan("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
  model: "gpt-5.1",
});

const graph = await client.queryRepositoryGraph("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
  file_path: "apps/api_server/services/repository_intelligence.py",
  max_depth: 2,
  max_nodes: 64,
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
console.log(graph.top_change_risk_files[0]?.file_path);
console.log(simulation.recommended_action, simulation.score_breakdown);
console.log(patchOnly.patch);
```

`createRepositoryDecisionPlan(...)` creates the immutable stored revision behind
`POST /v1/repositories/{repository_id}/decision-plans`. The SDK keeps the method
singular as a verb while the API stays plural as a resource.

For a fully local self-hosted repository planner, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`.
That planner is explicit and bounded; it currently supports deterministic
Python return-literal mismatch repairs and fails closed with
`repository_local_planner_unsupported` outside that contract.

Every stored repository `DecisionPlan` records planner provenance in
`decision_plan.repository_analysis` through `planner_model_id`,
`planner_execution_mode`, and `planner_provider_backend`.

`query()` remains available and unchanged when you only need the governed query body.

Use `https://api.codna.ai` only in Cloud Managed. `ALGENTA_DEPLOYMENT_MODE=self_hosted`
and `ALGENTA_DEPLOYMENT_MODE=air_gapped` must point `baseUrl` at your own
self-hosted service and fail closed instead of silently falling back to
Codna cloud.

`client.getContract()` also handles older self-hosted nodes that still return
`404` for `/v1/meta/contract` by falling back to `/openapi.json` and reading
`x-primary-data-query-contract`.

For formal runtime-proof surfaces, the client also exposes:

- `client.getRuntimeManifest()`
- `client.getRuntimeModules()`
- `client.getRuntimeBenchmarks()`
- `client.getRuntimeReleaseValidation()`

`client.getRuntimeBenchmarks()` includes benchmark-class `evidence_paths`, so
the typed runtime-proof surface carries concrete benchmark artifact linkage
instead of only benchmark codes and descriptions.
It currently publishes quality-gate benchmark classes `B6` checkpoint and
replay overhead, `B7` MCP tool latency, `B9` RAG retrieval quality and
latency, and `B10` decision workflow completion latency, plus quality-gate SLO
budgets `mcp_call_first_party`, `decision_plan_creation`, and `replay`.
`B10` is currently backed by the Repository Intelligence workflow artifact at
`build/repository_intelligence_benchmark.json`.

For the current plan-aligned utility and agent surfaces, the direct client also exposes:

- `client.listModels()`
- `client.resolveArtifactBridge({ repo_id, filename, revision, local_files_only })`
- `client.tokenize({ input, model })`
- `client.countTokens({ input, model })`
- `client.chatCompletions({ messages, model })`
- `client.streamChatCompletions({ messages, model })`
- `client.responses({ input, model, dimensions })`
- `client.streamResponses({ input, model, dimensions })`
- `client.embeddings({ input, model, dimensions })`
- `client.embeddingSimilarity({ left, right, model })`
- `client.rerank({ query_embedding, documents, model, top_n })`
- `client.planDecision(request)`
- `client.logDecision(request)`
- `client.listDecisions({ page, limit, with_outcome_only })`
- `client.getDecision(decisionId)`
- `client.recordOutcome(decisionId, { actual_outcome, outcome_notes })`
- `client.executeDecision(decisionId, { webhook_url, timeout_seconds })`
- `client.deleteDecision(decisionId)`
- `client.createAgentRun(request)`
- `client.listAgentRuns({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id })`
- `client.getAgentRun(runId)`
- `client.getAgentRunEvents(runId, { limit })`
- `client.streamAgentRunEvents(runId, { limit })`
- `client.listAgentRunCheckpoints(runId)`
- `client.queryAgentRunCheckpoints({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, checkpoint_id })`
- `client.listAgentRunMissionEvents(runId, { limit })`
- `client.queryAgentRunMissionEvents({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, event_type })`
- `client.listAgentRunTelemetry(runId, { limit })`
- `client.queryAgentRunTelemetry({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, telemetry_kind, module_name })`
- `client.replayAgentRun(runId, { checkpoint_id })`
- `client.forkAgentRun(runId, { checkpoint_id })`
- `client.resumeAgentRun(runId)`
- `client.cancelAgentRun(runId)`
- `client.approveAgentRun(runId)`
- `client.getAuditLogs({ page, limit, actor_email, action, resource_type, result, policy_snapshot_id, schema_snapshot_id, manifest_version, request_hash })`
- `client.getAuditLogArtifacts({ page, limit, actor_email, action, resource_type, result, policy_snapshot_id, schema_snapshot_id, manifest_version, request_hash, content_hash })`
- `client.listExecutionPolicySnapshots()`
- `client.createRepositorySnapshot(...)`
- `client.getRepositorySnapshot(...)`
- `client.triageRepository(...)`
- `client.createRepositoryDecisionPlan(...)`
- `client.simulateRepository(...)`
- `client.applyRepository(...)`
- `client.recommend(actions, { runs, seed })`
- `client.score(request, { expected_value, downside_risk })`
- `client.batch(items)`
- `client.compare(scenarios, { runs, seed })`

## Provider-Backed LLM Registry

Provider-backed LLM models are configured through `ALGENTA_LLM_PROVIDER_MODELS_JSON`.
Each entry must declare `id`, `backend`, `model_name`, `base_url`, and `api_key_env`
unless the backend explicitly allows local no-auth access.
Use `model_name` as the canonical upstream model field. Legacy `upstream_model`
is still accepted for backward compatibility.
`capabilities` is optional; when omitted, the runtime defaults to the full
capability set supported by that backend.

Supported backends:

- `openai_compatible` for OpenAI-style chat-completions and embeddings endpoints
- `openai` for the native OpenAI chat/responses and embeddings surface
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
    "id": "provider.anthropic-sonnet",
    "backend": "anthropic",
    "model_name": "claude-3-5-sonnet-latest",
    "base_url": "https://api.anthropic.com/v1",
    "api_key_env": "ANTHROPIC_API_KEY"
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

Once registered, provider-backed models appear in `client.listModels()` and can
be used through `client.chatCompletions(...)`, `client.responses(...)`, and
`client.embeddings(...)` when that backend supports the requested capability.
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

The governed filter model is a **record-filter contract** over normalized rows,
not SQL. Use `QueryFilterSpec` / `QueryFilterCondition` for deterministic exact
slices that also stay valid for Redis and other non-SQL sources. The
machine-readable operator families and validation rules are published under
`PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract`.

## Public Methods

Direct client calls use the same names under `client.*`, including
`client.me()`, `client.usage()`, `client.limits()`, `client.listApiKeys()`,
`client.createApiKey({ label, expires_at, device_limit })`, and
`client.revokeApiKey(keyId)`.

- `listDatasets({ search, status, sourceName, page, limit, compact })`
- `getContract()`
- `getRuntimeManifest()`
- `getRuntimeModules()`
- `getRuntimeBenchmarks()`
- `getRuntimeReleaseValidation()`
- `listModels()`
- `resolveArtifactBridge({ repo_id, filename, revision, local_files_only })`
- `tokenize({ input, model })`
- `countTokens({ input, model })`
- `chatCompletions({ messages, model })`
- `streamChatCompletions({ messages, model })`
- `responses({ input, model, dimensions })`
- `streamResponses({ input, model, dimensions })`
- `embeddings({ input, model, dimensions })`
- `embeddingSimilarity({ left, right, model })`
- `rerank({ query_embedding, documents, model, top_n })`
- `planDecision(request)`
- `logDecision(request)`
- `listDecisions({ page, limit, with_outcome_only })`
- `getDecision(decisionId)`
- `recordOutcome(decisionId, { actual_outcome, outcome_notes })`
- `executeDecision(decisionId, { webhook_url, timeout_seconds })`
- `deleteDecision(decisionId)`
- `me()`
- `usage()`
- `limits()`
- `listApiKeys()`
- `createApiKey({ label, expires_at, device_limit })`
- `revokeApiKey(keyId)`
- `submitJob(request, callbackUrl?)`
- `getJob(jobId)`
- `getJobResult(jobId)`
- `refreshCredits({ device_id, billing_period, credits_used })`
- `ingestMeteringEvents({ device_id, events })`
- `distributions()`
- `templates()`
- `listJobs({ page, limit, status })`
- `cancelJob(jobId)`
- `pollJob(jobId, { timeoutMs, pollIntervalMs })`
- `testWebhookDelivery(callbackUrl)`
- `registerTrigger({ name, condition, simulation_template, webhook_url, execution_webhook_url, auto_execute, description })`
- `listTriggers({ status, page, limit })`
- `fireTrigger(triggerId, { force })`
- `pauseTrigger(triggerId, { paused })`
- `deleteTrigger(triggerId)`
- `listDevices({ page, limit })`
- `revokeDevice(registrationId)`
- `createAgentRun(request)`
- `listAgentRuns({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id })`
- `getAgentRun(runId)`
- `getAgentRunEvents(runId, { limit })`
- `streamAgentRunEvents(runId, { limit })`
- `listAgentRunCheckpoints(runId)`
- `queryAgentRunCheckpoints({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, checkpoint_id })`
- `listAgentRunMissionEvents(runId, { limit })`
- `queryAgentRunMissionEvents({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, event_type })`
- `listAgentRunTelemetry(runId, { limit })`
- `queryAgentRunTelemetry({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, telemetry_kind, module_name })`
- `replayAgentRun(runId, { checkpoint_id })`
- `forkAgentRun(runId, { checkpoint_id })`
- `resumeAgentRun(runId)`
- `cancelAgentRun(runId)`
- `approveAgentRun(runId)`
- `getAuditLogs({ page, limit, actor_email, action, resource_type, result, policy_snapshot_id, schema_snapshot_id, manifest_version, request_hash })`
- `getAuditLogArtifacts({ page, limit, actor_email, action, resource_type, result, policy_snapshot_id, schema_snapshot_id, manifest_version, request_hash, content_hash })`
- `listExecutionPolicySnapshots()`
- `recommend(actions, { runs, seed })`
- `score(request, { expected_value, downside_risk })`
- `batch(items)`
- `compare(scenarios, { runs, seed })`
- `listConnectors({ page, limit })`
- `createConnector({ name, connector_type, description, config })`
- `getConnector(connectorId)`
- `updateConnector(connectorId, { description, config })`
- `testConnector(connectorId)`
- `browseConnector(connectorId)`
- `deleteConnector(connectorId)`
- `previewTestConnector({ connector })`
- `previewBrowseConnector({ connector })`
- `connectData({ connection_type, provider, dataset_name, description, connection_config })`
- `getDataset(datasetId)`
- `getDatasetSummary(datasetId)`
- `refreshDataset(datasetId)`
- `deleteDataset(datasetId)`
- `queryWithMetadata(request)`
- `queryBatch(request)`
- `querySqlReport(request)`
- `simulate(request)`

## Decision Runtime Helpers

```ts
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
  baseUrl: "https://api.codna.ai",
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

console.log(recommendation.recommended_action, score.score, batch.total, compared.winner);
```

The package exports `QueryFilterSpec` and `QueryFilterCondition` from the root
type surface, so callers can build deterministic exact-query filters without
inventing private request shapes.

## Local Consumer Sync Checklist

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
   - `listDatasets({ search, status, sourceName, page, limit, compact })`
   - `listConnectors({ page, limit })`
   - `createConnector({ name, connector_type, description, config })`
   - `getConnector(connectorId)`
   - `updateConnector(connectorId, { description, config })`
   - `testConnector(connectorId)`
   - `browseConnector(connectorId)`
   - `deleteConnector(connectorId)`
   - `previewTestConnector({ connector })`
   - `previewBrowseConnector({ connector })`
   - `connectData({ connection_type, provider, dataset_name, description, connection_config })`
   - `getDataset(datasetId)`
   - `getContract()`
   - `getRuntimeManifest()`
   - `getRuntimeModules()`
   - `getRuntimeBenchmarks()`
   - `getRuntimeReleaseValidation()`
   - `listModels()`
   - `tokenize({ input, model })`
   - `countTokens({ input, model })`
   - `chatCompletions({ messages, model })`
   - `streamChatCompletions({ messages, model })`
   - `responses({ input, model, dimensions })`
   - `streamResponses({ input, model, dimensions })`
   - `embeddings({ input, model, dimensions })`
   - `embeddingSimilarity({ left, right, model })`
   - `rerank({ query_embedding, documents, model, top_n })`
   - `planDecision(request)`
   - `me()`
   - `usage()`
   - `limits()`
   - `listApiKeys()`
   - `createApiKey({ label, expires_at, device_limit })`
   - `revokeApiKey(keyId)`
   - `submitJob(request, callbackUrl?)`
   - `getJob(jobId)`
   - `getJobResult(jobId)`
   - `cancelJob(jobId)`
   - `pollJob(jobId, { timeoutMs, pollIntervalMs })`
   - `createAgentRun(request)`
   - `getAgentRun(runId)`
   - `getAgentRunEvents(runId, { limit })`
   - `streamAgentRunEvents(runId, { limit })`
   - `resumeAgentRun(runId)`
   - `cancelAgentRun(runId)`
   - `approveAgentRun(runId)`
   - `getDatasetSummary(datasetId)`
   - `refreshDataset(datasetId)`
   - `deleteDataset(datasetId)`
   - `queryWithMetadata(request)`
   - `queryBatch(request)`
   - `querySqlReport(request)`

## Runtime and Local Libraries

```ts
import { Runtime, libraries } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const rt = new Runtime({
  mode: "self_hosted",
  apiKey,
  baseUrl: "http://localhost:8000",
});

const models = await rt.listModels();
const tokenized = await rt.tokenize({ input: "alpha beta" });
const usage = await rt.usage();
const recommendation = await rt.recommend(
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

const catalog = await libraries({ mode: "local" });

console.log(usage.billing_period, usage.quota_used_pct);
```

`Runtime` uses the governed hosted or self-hosted data/query surface. Use
Cloud Managed URLs only with `mode: "api"`. `mode: "self_hosted"` and private profiles must point `baseUrl` at your own self-hosted service and fail closed instead of silently falling back to Codna cloud. In `mode: "api"` or `mode: "self_hosted"`, it now forwards the plan-aligned helper routes too:

- `rt.listModels()`
- `rt.resolveArtifactBridge({ repo_id, filename, revision, local_files_only })`
- `rt.tokenize({ input, model })`
- `rt.countTokens({ input, model })`
- `rt.chatCompletions({ messages, model })`
- `rt.streamChatCompletions({ messages, model })`
- `rt.responses({ input, model, dimensions })`
- `rt.streamResponses({ input, model, dimensions })`
- `rt.embeddings({ input, model, dimensions })`
- `rt.embeddingSimilarity({ left, right, model })`
- `rt.rerank({ query_embedding, documents, model, top_n })`
- `rt.planDecision(request)`
- `rt.me()`
- `rt.updateMe({ name: "Mission Ops", org_name: "Mission Control" })`
- `rt.usage()`
- `rt.limits()`
- `rt.getBillingInfo()`
- `rt.createBillingCheckout({ plan })`
- `rt.createBillingPortal()`
- `rt.refreshCredits({ device_id, billing_period, credits_used })`
- `rt.ingestMeteringEvents({ device_id, events })`
- `rt.listTeamMembers({ page, limit })`
- `rt.inviteTeamMember({ email, role })`
- `rt.updateTeamMemberRole(userId, role)`
- `rt.removeTeamMember(userId)`
- `rt.getAuditLogs({ page, limit })`
- `rt.getAuditLogArtifacts({ page, limit, actor_email, action, resource_type, result, policy_snapshot_id, schema_snapshot_id, manifest_version, request_hash, content_hash })`
- `rt.getExecutionPolicy()`
- `rt.listExecutionPolicySnapshots()`
- `rt.listApiKeys()`
- `rt.createApiKey({ label, expires_at, device_limit })`
- `rt.revokeApiKey(keyId)`
- `rt.submitJob(request, callbackUrl?)`
- `rt.getJob(jobId)`
- `rt.getJobResult(jobId)`
- `rt.listJobs({ page, limit, status })`
- `rt.cancelJob(jobId)`
- `rt.pollJob(jobId, { timeoutMs, pollIntervalMs })`
- `rt.testWebhookDelivery(callbackUrl)`
- `rt.registerTrigger({ name, condition, simulation_template, webhook_url, execution_webhook_url, auto_execute, description })`
- `rt.listTriggers({ status, page, limit })`
- `rt.fireTrigger(triggerId, { force })`
- `rt.pauseTrigger(triggerId, { paused })`
- `rt.deleteTrigger(triggerId)`
- `rt.createAgentRun(request)`
- `rt.listAgentRuns({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id })`
- `rt.getAgentRun(runId)`
- `rt.getAgentRunEvents(runId, { limit })`
- `rt.streamAgentRunEvents(runId, { limit })`
- `rt.listAgentRunCheckpoints(runId)`
- `rt.queryAgentRunCheckpoints({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, checkpoint_id })`
- `rt.listAgentRunMissionEvents(runId, { limit })`
- `rt.queryAgentRunMissionEvents({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, event_type })`
- `rt.listAgentRunTelemetry(runId, { limit })`
- `rt.queryAgentRunTelemetry({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, telemetry_kind, module_name })`
- `rt.replayAgentRun(runId, { checkpoint_id })`
- `rt.forkAgentRun(runId, { checkpoint_id })`
- `rt.listConnectors({ page, limit })`
- `rt.createConnector({ name, connector_type, description, config })`
- `rt.getConnector(connectorId)`
- `rt.updateConnector(connectorId, { description, config })`
- `rt.testConnector(connectorId | { type, url, data_path })`
- `rt.browseConnector(connectorId | { type, url, data_path })`
- `rt.deleteConnector(connectorId)`
- `rt.connect(source?, { name?, description?, connectorId?, connector?, selection?, datasetName?, persist?, visibility?, connectionName? })`
- `rt.getDataset(datasetId)`
- `rt.getDatasetSummary(datasetId)`
- `rt.refreshDataset(datasetId)`
- `rt.deleteDataset(datasetId)`
- `rt.resumeAgentRun(runId)`
- `rt.cancelAgentRun(runId)`
- `rt.approveAgentRun(runId)`
- `rt.recommend(actions, { runs, seed })`
- `rt.score(request, { expected_value, downside_risk })`
- `rt.batch(items)`
- `rt.compare(scenarios, { runs, seed })`
- `rt.logDecision(request)`
- `rt.listDecisions({ page, limit, with_outcome_only })`
- `rt.getDecision(decisionId)`
- `rt.recordOutcome(decisionId, { actual_outcome, outcome_notes })`
- `rt.executeDecision(decisionId, { webhook_url, timeout_seconds })`
- `rt.deleteDecision(decisionId)`

`libraries()` remains the local/runtime-backed Mojo catalog.

## Docs

- [Algenta TypeScript docs](https://docs.algenta.ai/sdks/typescript)
- [Direct API client guide](https://docs.algenta.ai/direct-api-client)
