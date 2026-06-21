---
icon: js
description: Use Algenta from TypeScript or JavaScript — install the SDK, authenticate, and call the engine with a typed client. Includes runnable examples.
---

# TypeScript SDK

The `algenta-sdk` package is the official TypeScript and JavaScript client for Algenta. It gives you a single `AlgentaClient` for the hosted control plane and self-hosted engines, a `Runtime` class for local and self-hosted execution, and exported contract constants so your code can stay in lockstep with the API. It runs on Node.js 18+ and modern browsers, uses `fetch` with no required dependencies, and ships full type definitions. This page is the reference: imports, configuration, every method group, and copy-pasteable examples.

{% hint style="info" %}
The package is ESM-first and ships its own types. `main`, `module`, and `types` all resolve from `dist/`, so it works the same whether you import or require it.
{% endhint %}

## Install

{% tabs %}
{% tab title="npm" %}
```bash
npm install algenta-sdk
```
{% endtab %}

{% tab title="pnpm" %}
```bash
pnpm add algenta-sdk
```
{% endtab %}

{% tab title="yarn" %}
```bash
yarn add algenta-sdk
```
{% endtab %}
{% endtabs %}

## Quick start

The client reads your API key from `config.apiKey` first, then `ALGENTA_API_KEY`, then the legacy `DE_API_KEY`. Set it once in the environment and the example below runs end to end.

```ts title="quickstart.ts"
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({ apiKey, baseUrl: "https://api.algenta.ai" });

const datasets = await client.listDatasets({ search: "nps_scores", compact: true });
const datasetId = datasets.datasets[0].dataset_id;

const summary = await client.getDatasetSummary(datasetId);
console.log(summary.dataset_id, summary.name);
```

{% hint style="info" %}
`https://api.algenta.ai` is also exported as `DEFAULT_BASE_URL`. If you omit `baseUrl`, the client resolves the default for you. Pass an explicit `baseUrl` when you talk to a self-hosted engine.
{% endhint %}

## Configuration

`new AlgentaClient(config)` accepts an `AlgentaClientConfig`:

| Option | Type | Default | Notes |
| --- | --- | --- | --- |
| `apiKey` | `string` | `process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY` | Required. Read from the environment if not passed. |
| `baseUrl` | `string` | `DEFAULT_BASE_URL` (`https://api.algenta.ai`) | Override for self-hosted engines. |
| `timeout` | `number` | SDK default | Per-request timeout in milliseconds (`AbortController`). |
| `maxRetries` | `number` | SDK default | Retries with exponential backoff; honors `Retry-After` on 429. |
| `defaultHeaders` | `Record<string, string>` | `{}` | Merged into every request. |

The API key resolves from `config.apiKey` first, then `ALGENTA_API_KEY`, then the legacy `DE_API_KEY`. If none is set, the constructor throws with guidance instead of failing silently.

```ts
const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY,
  baseUrl: process.env.ALGENTA_BASE_URL ?? "https://api.algenta.ai",
  timeout: 30_000,
  maxRetries: 3,
});
```

{% hint style="success" %}
Methods are camelCase, but request bodies and query parameters stay snake_case. You call `getDatasetSummary(...)`, `queryWithMetadata(...)`, and `querySqlReport(...)`, and the payloads you pass and receive use fields like `dataset_id`, `source_name`, `metric_column`, and `max_rows`. This mirrors the HTTP contract exactly.
{% endhint %}

{% expandable title="Compatibility names for older integrations" %}
`AlgentaClient` is the canonical export. The same class is also exported as `DecisionEngineClient` and `CodnaClient` (with matching `AlgentaClientConfig` / `DecisionEngineClientConfig` / `CodnaClientConfig` types) so older integrations keep working. All three are the same constructor.
{% endexpandable %}

## Exports

```ts
import {
  AlgentaClient,
  DEFAULT_BASE_URL,
  PRIMARY_DATA_QUERY_CONTRACT,
  CAPABILITY_PLANE_CONTRACT,
  CONTRACT_VERSION,
  type QueryFilterSpec,
} from "algenta-sdk";
```

The barrel exports the client and runtime classes, their error types, and the generated contract constants:

| Export | What it is |
| --- | --- |
| `AlgentaClient`, `DecisionEngineClient`, `CodnaClient` | The HTTP client class (same constructor). |
| `Runtime`, `RuntimeError`, `RuntimeConfigurationError`, `RuntimeValidationError` | Runtime class for local / self-hosted use. |
| `MojoRuntime`, `libraries` | Runtime-library entrypoint and catalog. |
| `DecisionEngineError`, `AuthenticationError`, `RateLimitError`, `ValidationError`, `NotFoundError`, `ServerError` | Client error hierarchy. |
| `MojoExecutionError`, `MojoFunctionNotRegisteredError`, `MojoModuleNotRegisteredError`, `MojoRuntimeConfigurationError`, `MojoRuntimeError` | Runtime-library error types. |
| `DEFAULT_BASE_URL`, `MCP_ENDPOINT`, `MCP_TOOLS_ENDPOINT`, `CONTRACT_VERSION`, `BRAND` | Endpoint and version constants. |
| `API_KEY_PREFIX_LIVE`, `API_KEY_PREFIX_TEST`, `AUTH_SCHEME`, `PLAN_LIMITS`, `INTEGRATIONS` | Contract metadata. |
| `PRIMARY_DATA_QUERY_CONTRACT`, `CAPABILITY_PLANE_CONTRACT` | Machine-readable maps of endpoints, methods, CLI commands, and MCP tools. |
| `type QueryFilterSpec` and all other types | Full request/response type surface. |

`PRIMARY_DATA_QUERY_CONTRACT` is generated alongside the engine, so it always names the current method per surface. For example:

```ts
import { PRIMARY_DATA_QUERY_CONTRACT } from "algenta-sdk";

PRIMARY_DATA_QUERY_CONTRACT.direct_sdk.typescript.query_with_metadata_method; // "queryWithMetadata"
PRIMARY_DATA_QUERY_CONTRACT.api.query_sql_report_endpoint;                    // "/v1/query/sql-report"
```

## Data: datasets and contract

```ts
// List governed datasets. `search` narrows; `compact` returns lighter rows.
const datasets = await client.listDatasets({ search: "nps_scores", compact: true });

// Per-dataset schema summary.
const summary = await client.getDatasetSummary(datasets.datasets[0].dataset_id);

// Machine-readable platform contract (endpoints, methods, enums).
const contract = await client.getContract();
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `listDatasets({ search, compact, status, sourceName, page, limit })` | `GET /v1/data` | `sourceName` maps to `source_name`; `compact` sends `compact=1`. |
| `getDataset(datasetId)` | `GET /v1/data/{id}` | Full dataset detail. |
| `getDatasetSummary(datasetId)` | `GET /v1/data/{id}/summary` | Schema, fields, row counts. |
| `getContract()` | `GET /v1/meta/contract` | Falls back to `/openapi.json` if the contract endpoint is absent. |

## Querying

The query family is the governed data path. Bodies stay snake_case.

### Single query with metadata

`queryWithMetadata` returns `{ data, metadata, headers }` so you get the response alongside its execution metadata and raw headers.

{% tabs %}
{% tab title="TypeScript" %}
```ts
const result = await client.queryWithMetadata({
  source_name: "nps_scores",
  metric_column: "nps_score",
  group_column: "origin_airport_code",
  aggregation: "avg",
});

console.log(result.data);      // the query response
console.log(result.metadata);  // execution metadata (latency, plan, etc.)
console.log(result.headers);   // raw response headers
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/query \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "nps_scores",
    "metric_column": "nps_score",
    "group_column": "origin_airport_code",
    "aggregation": "avg"
  }'
```
{% endtab %}
{% endtabs %}

### Batch query

`queryBatch` runs several keyed queries in one round trip, with optional shared `defaults`.

```ts
const batch = await client.queryBatch({
  defaults: {
    dataset_id: "ds_nps_scores",
    order: "desc",
    limit: 100,
  },
  queries: [
    { key: "avg_nps", request: { metric_column: "nps_score", aggregation: "avg" } },
    { key: "responses", request: { metric_column: "response_id", aggregation: "count" } },
  ],
});
```

The optional `defaults.filter` accepts a `QueryFilterSpec`:

```ts
import type { QueryFilterSpec } from "algenta-sdk";

const filter: QueryFilterSpec = {
  time_filter: "last_90_days",
  conditions: [
    { column: "region", op: "in", values: ["EU", "NA"] },
    { column: "nps_score", op: "gte", value: 0 },
  ],
};
```

{% expandable title="Supported filter operators" %}
The governed filter contract supports `eq`, `gt`, `gte`, `lt`, `lte`, `in`, `is_null`, and `is_not_null`. Filters apply to normalized rows before aggregation and are valid across SQL and non-SQL backends.
{% endexpandable %}

### SQL report

`querySqlReport` runs a read-only SQL report over one or more governed datasets, each given an alias.

{% tabs %}
{% tab title="TypeScript" %}
```ts
const report = await client.querySqlReport({
  sources: [
    { dataset_id: "ds_nps_scores", alias: "nps" },
    { dataset_id: "ds_flights", alias: "flights" },
  ],
  sql: `
    SELECT flights.origin_airport_code, AVG(nps.nps_score) AS avg_nps
    FROM nps JOIN flights ON nps.flight_id = flights.flight_id
    GROUP BY flights.origin_airport_code
  `,
  max_rows: 500,
});

console.log(report.columns, report.row_count, report.truncated);
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/query/sql-report \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [{ "dataset_id": "ds_nps_scores", "alias": "nps" }],
    "sql": "SELECT AVG(nps.nps_score) AS avg_nps FROM nps",
    "max_rows": 500
  }'
```
{% endtab %}
{% endtabs %}

| Method | HTTP |
| --- | --- |
| `queryWithMetadata(request)` | `POST /v1/query` (returns `{ data, metadata, headers }`) |
| `queryBatch({ defaults, queries })` | `POST /v1/query/batch` |
| `querySqlReport({ sources, sql, max_rows })` | `POST /v1/query/sql-report` |

## Capability plane

The capability plane is how the engine discovers, routes, and executes tools, skills, and MCP capabilities.

```ts
// Plan which capability should handle an intent.
const plan = await client.routeCapabilities({
  query: "summarize the latest incident report",
});

// Inspect one capability, with its instruction body.
const capability = await client.getCapability(plan.capability_id, {
  includeInstruction: true,
});

// Execute it.
const execution = await client.executeCapability({
  capability_id: capability.capability_id,
  inputs: {},
});
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `routeCapabilities(request)` | `POST /v1/capabilities/route` | Returns a `CapabilityRoutePlan`. |
| `getCapability(id, { includeInstruction })` | `GET /v1/capabilities/{id}` | `includeInstruction` sends `include_instruction=1`. |
| `executeCapability(request)` | `POST /v1/capabilities/execute` | Runs the selected capability. |
| `listCapabilities({ kinds, providerIds, bindingIds })` | `GET /v1/capabilities` | Filter by kind, provider, or binding. |
| `recordCapabilityOutcome(request)` | `POST /v1/capabilities/outcomes` | Feed results back for learning. |

### Providers, skills, and MCP

```ts
const providers = await client.listCapabilityProviders(); // GET /v1/capability-providers
const skills = await client.listSkills();                 // listCapabilities({ kinds: ["skill"] })
const mcp = await client.listMcpProviders();              // providers where provider_type === "mcp_provider"
```

`listMcpProviders()` is a convenience filter over `listCapabilityProviders()`, and `listSkills()` is `listCapabilities({ kinds: ["skill"] })`.

{% expandable title="Binding lifecycle and skill toggle helpers" %}
There are also full binding lifecycle methods (`createCapabilityBinding`, `testCapabilityBinding`, `discoverCapabilityBinding`, `startCapabilityAuthorization`, `completeCapabilityAuthorization`) plus `enableSkill` / `disableSkill` helpers.
{% endexpandable %}

## The Runtime class

`Runtime` is the entrypoint for self-hosted and local execution. It wraps the same HTTP client but adds mode-awareness, contract validation, and signed runtime-proof checks. It is exported directly:

```ts
import { Runtime } from "algenta-sdk";
```

| Mode | Meaning | Requirements |
| --- | --- | --- |
| `local` | In-process execution; the default. | No network for the local query path. |
| `api` | Hosted control plane over HTTP. | `apiKey` (env or config). |
| `self_hosted` | Your own engine over HTTP. | `apiKey` and an explicit `baseUrl`. |

```ts
// Self-hosted engine.
const runtime = new Runtime({
  mode: "self_hosted",
  baseUrl: "https://engine.internal.example.com",
  apiKey: process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY,
});

// Hosted control plane.
const hosted = new Runtime({ mode: "api", apiKey: process.env.ALGENTA_API_KEY });

// Local (default).
const local = new Runtime();
```

{% hint style="warning" %}
`self_hosted` mode requires an explicit `baseUrl` and throws `RuntimeConfigurationError` (`self_hosted_base_url_required`) without one. Private profiles fail closed: the runtime never silently falls back to Algenta cloud.
{% endhint %}

### Runtime introspection

These methods read the engine's signed runtime manifest and validation artifacts. They require API transport (`api` or `self_hosted`); calling them in `local` mode throws `local_mode_not_supported`.

```ts title="_runtime_class.ts"
const manifest = await runtime.getRuntimeManifest();            // GET /v1/runtime/manifest
const modules = await runtime.getRuntimeModules();              // GET /v1/admin/runtime/modules
const benchmarks = await runtime.getRuntimeBenchmarks();        // GET /v1/admin/runtime/benchmarks
const validation = await runtime.getRuntimeReleaseValidation(); // GET /v1/admin/runtime/validation
```

| Method | HTTP | Purpose |
| --- | --- | --- |
| `getRuntimeManifest()` | `GET /v1/runtime/manifest` | Signed manifest of the active runtime build. |
| `getRuntimeModules()` | `GET /v1/admin/runtime/modules` | Registered runtime-library modules. |
| `getRuntimeBenchmarks()` | `GET /v1/admin/runtime/benchmarks` | Published runtime benchmarks. |
| `getRuntimeReleaseValidation()` | `GET /v1/admin/runtime/validation` | Release-validation proof. |

{% hint style="success" %}
Each response is validated against the runtime-proof contract. An invalid or tampered payload raises `RuntimeValidationError` (`invalid_runtime_contract_payload`) rather than returning unverified data.
{% endhint %}

The Runtime also re-exposes the data and capability surface (`getContract`, `listDatasets`, `getDatasetSummary`, `queryWithMetadata`, `queryBatch`, `querySqlReport`, `routeCapabilities`, `executeCapability`, and more), delegating to the underlying client when in `api` or `self_hosted` mode.

## Device-binding headers

Every request carries automatic device-binding headers, computed by `resolveClientDeviceHeaders` (`client_device_headers.ts`). These let the control plane recognize and bind a stable device without you wiring anything up.

| Header | Value |
| --- | --- |
| `X-Algenta-SDK-Version` | The SDK user agent / version. |
| `X-Algenta-Device-Id` | A stable, derived device id (16-64 chars). |
| `X-Algenta-Platform` | OS platform (Node) or `navigator.platform` (browser). |
| `X-Algenta-Platform-Version` | Node version, when available. |
| `X-Algenta-Hostname-Hash` | FNV-1a hash of the hostname seed (never the raw hostname). |

{% expandable title="How the device id is derived and how to override it" %}
On Node, the device id is derived from the machine id (`/etc/machine-id` on Linux), the hostname, or a persisted install id under `~/.algenta/runtime/install_id`. In the browser it is generated once and stored in `localStorage`. You can override it with the `ALGENTA_DEVICE_ID` (or legacy `DE_DEVICE_ID`) environment variable, or by passing `X-Algenta-Device-Id` in `defaultHeaders`:

```ts
const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  defaultHeaders: { "X-Algenta-Device-Id": "my-stable-device-id-0001" },
});
```
{% endexpandable %}

{% hint style="info" %}
The hostname is never sent in clear text; only a hash is. When the control plane returns a device-binding token, the client persists it and replays it on subsequent requests automatically.
{% endhint %}

## Errors

All client errors extend `DecisionEngineError` and carry a normalized `errorCode`, `statusCode`, and `details`.

```ts
import {
  AlgentaClient,
  AuthenticationError,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "algenta-sdk";

try {
  await client.getDatasetSummary("does-not-exist");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.error("Not found:", err.errorCode);
  } else if (err instanceof RateLimitError) {
    console.error("Rate limited; retry after", err.retryAfter, "seconds");
  } else if (err instanceof AuthenticationError) {
    console.error("Check your API key");
  } else if (err instanceof ValidationError) {
    console.error("Invalid request:", err.details);
  }
}
```

| Error | HTTP status | Retried automatically |
| --- | --- | --- |
| `AuthenticationError` | 401 | No |
| `NotFoundError` | 404 | No |
| `ValidationError` | 422 | No |
| `RateLimitError` | 429 | Yes, honoring `Retry-After` |
| `ServerError` | 5xx | Yes, with exponential backoff |
| `DecisionEngineError` | other | Base class |

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ALGENTA_API_KEY` | Primary API key. |
| `DE_API_KEY` | Legacy fallback for the API key. |
| `ALGENTA_DEVICE_ID` / `DE_DEVICE_ID` | Override the derived device id. |
| `ALGENTA_RUNTIME_DIR` | Directory for the persisted install id (defaults to `~/.algenta/runtime`). |

{% hint style="info" %}
Set credentials in the environment rather than hard-coding them. The client and runtime both read `ALGENTA_API_KEY` first and `DE_API_KEY` as a fallback, so the same shell setup works across the SDK, CLI, and Python SDK.
{% endhint %}

## Agent runs

Agent runs drive a task through the engine's tool loop with deterministic, replayable checkpoints. You create a run, watch its events stream in, approve or resume it when it pauses for a gated action, and fork or replay it from any checkpoint. Every run carries a `request_hash` so the same task against the same snapshots is reproducible. See the [agent runs guide](../guides/agent-runs.md) for the full lifecycle.

```ts title="agent_run.ts"
const run = await client.createAgentRun({
  task: "Summarize the latest incident report and propose a remediation",
  max_steps: 8,
  approval_mode: "auto",
  start_paused: false,
});

// Stream events as the run progresses.
for await (const message of client.streamAgentRunEvents(run.run_id)) {
  if (message.type === "agent.run.completed") {
    console.log("done:", message.status);
    break;
  }
  console.log(message.event?.event_type, message.event?.summary);
}

// Read the final state, including request_hash and decision_hash.
const finished = await client.getAgentRun(run.run_id);
console.log(finished.status, finished.request_hash);
```

When a run pauses for a gated action, advance it with `approveAgentRun` (or override with `resumeAgentRun`); stop it early with `cancelAgentRun`. Branch a new run from a checkpoint with `forkAgentRun`, or re-execute deterministically from one with `replayAgentRun`.

```ts
await client.approveAgentRun(run.run_id);          // approve the pending action
await client.resumeAgentRun(run.run_id);           // continue a paused run
await client.cancelAgentRun(run.run_id);           // stop the run

const branch = await client.forkAgentRun(run.run_id, { checkpoint_id: "ckpt_3" });
const replay = await client.replayAgentRun(run.run_id, { checkpoint_id: "ckpt_3" });
```

{% hint style="info" %}
`forkAgentRun` and `replayAgentRun` take an optional `checkpoint_id`. Omit it (or pass `null`) to fork or replay from the latest checkpoint.
{% endhint %}

| Method | HTTP | Notes |
| --- | --- | --- |
| `createAgentRun(request)` | `POST /v1/agent/runs` | `request` is an `AgentRunCreateRequest` (`task`, `max_steps`, `approval_mode`, `tools`, `start_paused`). |
| `getAgentRun(runId)` | `GET /v1/agent/runs/{id}` | Current run state, including `request_hash`. |
| `streamAgentRunEvents(runId, { limit })` | `GET /v1/agent/runs/{id}/events?stream=true` | Async generator of `agent.run.event` / `agent.run.completed` messages. |
| `approveAgentRun(runId)` | `POST /v1/agent/runs/{id}/approve` | Approve a pending gated action. |
| `resumeAgentRun(runId)` | `POST /v1/agent/runs/{id}/resume` | Continue a paused run. |
| `cancelAgentRun(runId)` | `POST /v1/agent/runs/{id}/cancel` | Stop the run. |
| `forkAgentRun(runId, { checkpoint_id })` | `POST /v1/agent/runs/{id}/fork` | New run branched from a checkpoint. |
| `replayAgentRun(runId, { checkpoint_id })` | `POST /v1/agent/runs/{id}/replay` | Deterministic re-execution from a checkpoint. |

## Async jobs

Long-running simulations run as async jobs: you submit a `SimulateRequest`, get back a `job_id` and `poll_url`, then poll until the result is ready. `pollJob` is the convenience wrapper that polls `getJob` for you and returns the result once the job completes. An optional `callbackUrl` lets the engine deliver a webhook instead of (or alongside) polling. See the [async jobs guide](../guides/async-jobs.md).

**Expected result:** `submitJob` returns a `JobSubmitResponse` with `job_id`, `status: "queued"`, and a `poll_url`.

```ts title="async_job.ts"
const job = await client.submitJob(
  {
    mode: "auto",
    scenario: {
      name: "pricing",
      variables: {
        unit_price: { low: 9, high: 19, description: "candidate list price" },
        units_sold: { low: 1000, high: 5000 },
      },
      objective: "maximize_net_value",
    },
    runs: 10_000,
    seed: 42,
  },
  "https://example.com/algenta/webhook", // optional callback_url
);

console.log(job.job_id, job.status, job.poll_url);

// Block until the job finishes (or check progress manually).
const result = await client.pollJob(job.job_id, { timeoutMs: 60_000, pollIntervalMs: 1_000 });
console.log(result);
```

To poll by hand, read the status with `getJob`, fetch the payload with `getJobResult` once `status === "completed"`, browse history with `listJobs`, and stop in-flight work with `cancelJob`.

```ts
const status = await client.getJob(job.job_id);
if (status.status === "completed") {
  const payload = await client.getJobResult(job.job_id);
  console.log(payload);
}

const page = await client.listJobs({ page: 1, limit: 25, status: "queued" });
await client.cancelJob(job.job_id);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `submitJob(request, callbackUrl?)` | `POST /v1/jobs` | `request` is a `SimulateRequest`; `callbackUrl` maps to `callback_url`. |
| `getJob(jobId)` | `GET /v1/jobs/{id}` | Job status (`job_id`, `run_id`, `status`). |
| `getJobResult(jobId)` | `GET /v1/jobs/{id}/result` | The completed result payload. |
| `pollJob(jobId, { timeoutMs, pollIntervalMs })` | polls `GET /v1/jobs/{id}` | Resolves to the result once the job completes. |
| `listJobs({ page, limit, status })` | `GET /v1/jobs/list` | Paginated job history, filterable by status. |
| `cancelJob(jobId)` | `POST /v1/jobs/{id}/cancel` | Cancels a queued or running job. |

## Repository intelligence

Repository intelligence turns a code repository into governed, queryable evidence. You snapshot the repo, triage an issue against it to get ranked evidence, query the symbol graph, simulate a candidate decision plan, and apply the result as a patch, branch, or pull request. Start by checking which languages the engine supports with `getRepositoryIntelligenceCapabilities`. See the [repository intelligence guide](../guides/repository-intelligence.md).

```ts title="repository_intelligence.ts"
const capabilities = await client.getRepositoryIntelligenceCapabilities();
console.log(capabilities.supported_languages.length, capabilities.support_progress.progress_label);

// 1. Snapshot the repository.
const snapshot = await client.createRepositorySnapshot("repo_42", {
  ref: "main",
  include_patterns: ["src/**"],
  max_files: 5_000,
});

// 2. Triage an issue into ranked evidence.
const triage = await client.triageRepository("repo_42", {
  snapshot_id: snapshot.snapshot_id,
  signals: {
    issue_text: "Null pointer when the cart is empty at checkout",
    failing_tests: ["test_checkout_empty_cart"],
  },
  max_evidence_items: 20,
});

// 3. Walk the symbol graph around a file or symbol.
const graph = await client.queryRepositoryGraph("repo_42", {
  snapshot_id: snapshot.snapshot_id,
  symbol_name: "checkout",
  direction: "both",
  max_depth: 2,
});

// 4. Simulate a decision plan, then 5. apply it as a pull request.
const decision = await client.simulateRepository("repo_42", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: "plan_7",
  runs: 256,
});

const applied = await client.applyRepository("repo_42", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: "plan_7",
  simulation_id: decision.simulation_id,
  mode: "remote_pr",
  write_permission: true,
  pull_request_title: "Fix empty-cart checkout crash",
});

console.log(triage.evidence?.length, graph.nodes?.length, applied.pull_request_url);
```

{% hint style="warning" %}
`applyRepository` with `mode: "remote_pr"` (or `"local_branch"`) writes to your repository. It requires `write_permission: true` and a `simulation_id` from a prior `simulateRepository` call. Use `mode: "patch_only"` to get the `.diff` without writing anything.
{% endhint %}

| Method | HTTP | Notes |
| --- | --- | --- |
| `getRepositoryIntelligenceCapabilities()` | `GET /v1/repositories/capabilities` | Supported languages and support progress. |
| `createRepositorySnapshot(repositoryId, request)` | `POST /v1/repositories/{id}/snapshots` | `request` is a `RepositorySnapshotCreateRequest`. |
| `triageRepository(repositoryId, request)` | `POST /v1/repositories/{id}/triage` | Ranked evidence from `signals` (`issue_text`, `failing_tests`, `changed_files`). |
| `queryRepositoryGraph(repositoryId, request)` | `POST /v1/repositories/{id}/graph-query` | Symbol/file graph; `direction` is `inbound`, `outbound`, or `both`. |
| `simulateRepository(repositoryId, request)` | `POST /v1/repositories/{id}/simulate` | Returns a `DecisionEnvelope` for a `decision_plan_id`. |
| `applyRepository(repositoryId, request)` | `POST /v1/repositories/{id}/apply` | `mode` is `patch_only`, `local_branch`, or `remote_pr`. |

## Related pages

{% content-ref url="../authentication.md" %}
[authentication.md](../authentication.md)
{% endcontent-ref %}

{% content-ref url="python.md" %}
[python.md](python.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}

{% content-ref url="../self-hosting.md" %}
[self-hosting.md](../self-hosting.md)
{% endcontent-ref %}
