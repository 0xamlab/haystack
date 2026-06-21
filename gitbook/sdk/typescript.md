---
icon: js
---

# TypeScript SDK

The `algenta-sdk` package is the official TypeScript and JavaScript client for Algenta. It gives you a single `AlgentaClient` for the hosted control plane and self-hosted engines, a `Runtime` class for local and self-hosted execution, and exported contract constants so your code can stay in lockstep with the API. It runs on Node.js 18+ and modern browsers, uses `fetch` with no required dependencies, and ships full type definitions. This page is the reference: imports, configuration, every method group, and copy-pasteable examples.

## Install

```bash
npm install algenta-sdk
```

```bash
pnpm add algenta-sdk
```

```bash
yarn add algenta-sdk
```

The package is ESM-first and ships its own types. `main`, `module`, and `types` all resolve from `dist/`, so it works the same whether you import or require it.

## Quick start

```ts
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

### Compatibility names

`AlgentaClient` is the canonical export. The same class is also exported as `DecisionEngineClient` and `CodnaClient` (with matching `AlgentaClientConfig` / `DecisionEngineClientConfig` / `CodnaClientConfig` types) so older integrations keep working. All three are the same constructor.

{% hint style="info" %}
Methods are camelCase, but request bodies and query parameters stay snake_case. You call `getDatasetSummary(...)`, `queryWithMetadata(...)`, and `querySqlReport(...)`, and the payloads you pass and receive use fields like `dataset_id`, `source_name`, `metric_column`, and `max_rows`. This mirrors the HTTP contract exactly.
{% endhint %}

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

The governed filter contract supports `eq`, `gt`, `gte`, `lt`, `lte`, `in`, `is_null`, and `is_not_null`. Filters apply to normalized rows before aggregation and are valid across SQL and non-SQL backends.

### SQL report

`querySqlReport` runs a read-only SQL report over one or more governed datasets, each given an alias.

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

| Method | HTTP |
| --- | --- |
| `queryWithMetadata(request)` | `POST /v1/query` (returns `{ data, metadata, headers }`) |
| `queryBatch({ defaults, queries })` | `POST /v1/query/batch` |
| `querySqlReport({ sources, sql, max_rows })` | `POST /v1/query/sql-report` |

The equivalent raw HTTP call:

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

`listMcpProviders()` is a convenience filter over `listCapabilityProviders()`, and `listSkills()` is `listCapabilities({ kinds: ["skill"] })`. There are also full binding lifecycle methods (`createCapabilityBinding`, `testCapabilityBinding`, `discoverCapabilityBinding`, `startCapabilityAuthorization`, `completeCapabilityAuthorization`) plus `enableSkill` / `disableSkill` helpers.

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

{% hint style="info" %}
`self_hosted` mode requires an explicit `baseUrl` and throws `RuntimeConfigurationError` (`self_hosted_base_url_required`) without one. Private profiles fail closed: the runtime never silently falls back to Algenta cloud.
{% endhint %}

### Runtime introspection (`_runtime_class.ts`)

These methods read the engine's signed runtime manifest and validation artifacts. They require API transport (`api` or `self_hosted`); calling them in `local` mode throws `local_mode_not_supported`.

```ts
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

Each response is validated against the runtime-proof contract. An invalid or tampered payload raises `RuntimeValidationError` (`invalid_runtime_contract_payload`) rather than returning unverified data.

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

On Node, the device id is derived from the machine id (`/etc/machine-id` on Linux), the hostname, or a persisted install id under `~/.algenta/runtime/install_id`. In the browser it is generated once and stored in `localStorage`. You can override it with the `ALGENTA_DEVICE_ID` (or legacy `DE_DEVICE_ID`) environment variable, or by passing `X-Algenta-Device-Id` in `defaultHeaders`:

```ts
const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  defaultHeaders: { "X-Algenta-Device-Id": "my-stable-device-id-0001" },
});
```

The hostname is never sent in clear text; only a hash is. When the control plane returns a device-binding token, the client persists it and replays it on subsequent requests automatically.

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
