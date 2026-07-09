---
icon: chart-line
description: TypeScript SDK methods for Monte Carlo simulation, decision planning, recommendation, scoring, and the governed query family, each with its HTTP route.
---

# Simulations and queries

These methods live on `AlgentaClient` and cover two families from the simulation and query surface: running decisions under uncertainty (`simulate`, `planDecision`, `recommend`, `score`, `batch`, `compare`) and reading governed data (`resolve`, `query`, `queryWithMetadata`, `verify`, `queryBatch`, `querySqlReport`, `explain`). Method names are `camelCase`; bodies stay `snake_case`.

## Simulation methods

A `SimulateRequest` in `auto` mode describes a scenario with named `variables` (each a `low`/`high` range) and an `objective`, and the engine returns a `DecisionEnvelope` with the expected value, percentiles, and a recommended action.

```typescript title="simulate.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });

// Run one decision.
const envelope = await client.simulate({
  mode: "auto",
  scenario: {
    name: "Product launch decision",
    variables: {
      revenue: { low: 80000, high: 200000 },
      cost: { low: 40000, high: 90000 },
    },
    objective: "maximize_net_value",
  },
  runs: 10000,
  seed: 42,
});
console.log(envelope.recommended_action, envelope.confidence);

// Compare two named scenarios in one call.
const comparison = await client.compare(
  [
    { name: "launch_now", request: { mode: "auto", scenario: { variables: { revenue: { low: 80000, high: 200000 } }, objective: "maximize_net_value" } } },
    { name: "wait_a_quarter", request: { mode: "auto", scenario: { variables: { revenue: { low: 60000, high: 150000 } }, objective: "maximize_net_value" } } },
  ],
  { runs: 5000, seed: 42 },
);
console.log(comparison);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `simulate(request)` | `POST /v1/simulate` | Runs one `SimulateRequest`; returns a `DecisionEnvelope`. |
| `planDecision(request)` | `POST /v1/decisions/plan` | Returns a structured `DecisionPlanResponse` for the same request shape. |
| `recommend(actions, options?)` | `POST /v1/recommend` | `actions` is an array of `{ name, request }`; `options` sets `{ runs, seed }`. |
| `score(request, scoringWeights?)` | `POST /v1/score` | Scores one request; `scoringWeights` maps to `scoring_weights`. |
| `batch(items)` | `POST /v1/batch` | Runs an array of `SimulateRequest` in one call; returns a `BatchResult`. |
| `compare(scenarios, options?)` | `POST /v1/compare` | `scenarios` is an array of `{ name, request }`; `options` sets `{ runs, seed }`. |

{% hint style="info" %}
`recommend` and `compare` share the same shape — an array of named requests plus optional `{ runs, seed }`. Use `recommend` to pick a single best action and `compare` to rank named scenarios side by side.
{% endhint %}

## Query methods

The query family is the governed data path: deterministic, typed reads over onboarded datasets. `queryWithMetadata` returns `{ data, metadata, headers }` so you get the response alongside its execution metadata and raw headers; `querySqlReport` runs a read-only SQL report over one or more aliased datasets.

```typescript title="query.ts"
// Aggregate one metric, with execution metadata.
const result = await client.queryWithMetadata({
  source_name: "nps_scores",
  metric_column: "nps_score",
  group_column: "origin_airport_code",
  aggregation: "avg",
});
console.log(result.data, result.metadata, result.headers);

// Read-only SQL report across two aliased datasets.
const report = await client.querySqlReport({
  sources: [
    { dataset_id: "ds_nps_scores", alias: "nps" },
    { dataset_id: "ds_flights", alias: "flights" },
  ],
  sql: "SELECT flights.origin_airport_code, AVG(nps.nps_score) AS avg_nps FROM nps JOIN flights ON nps.flight_id = flights.flight_id GROUP BY 1",
  max_rows: 500,
});
console.log(report.columns, report.row_count, report.truncated);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `resolve(request)` | `POST /v1/resolve` | Resolves a query hint to a concrete source/column plan. |
| `query(request)` | `POST /v1/query` | Runs a governed query; returns a `QueryResponse`. |
| `queryWithMetadata(request)` | `POST /v1/query` | Same call, returning `{ data, metadata, headers }`. |
| `verify(request)` | `POST /v1/verify` | Verifies a query resolves and validates before you run it. |
| `queryBatch(request)` | `POST /v1/query/batch` | Runs keyed `queries` with optional shared `defaults`. |
| `querySqlReport(request)` | `POST /v1/query/sql-report` | Read-only SQL over aliased `sources`; `max_rows` caps output. |
| `explain(request)` | `POST /v1/query` | Runs the query and returns an `ExplainResponse` (source set, join path, plan hash). |

{% hint style="success" %}
Governed queries are deterministic: the same request against the same dataset returns the same rows in the same order. Use `verify` (or `explain`) to check the resolved plan before running a query for the first time.
{% endhint %}

{% expandable title="Batch queries with shared defaults" %}
`queryBatch` runs several keyed queries in one round trip. Shared `defaults` (`dataset_id`, `filter`, `limit`, `order`) apply to every query unless overridden.

```typescript
const batch = await client.queryBatch({
  defaults: { dataset_id: "ds_nps_scores", order: "desc", limit: 100 },
  queries: [
    { key: "avg_nps", request: { metric_column: "nps_score", aggregation: "avg" } },
    { key: "responses", request: { metric_column: "response_id", aggregation: "count" } },
  ],
});
console.log(batch);
```
{% endexpandable %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Log decisions and call products</strong></td><td>Persist decision memory and use the product endpoints.</td><td><a href="decisions-and-products.md">decisions-and-products.md</a></td></tr>
<tr><td><strong>Run a governed query end to end</strong></td><td>Onboard data and query it under a typed contract.</td><td><a href="../../guides/governed-query.md">../../guides/governed-query.md</a></td></tr>
<tr><td><strong>Set up the client</strong></td><td>Install, configure, and handle errors.</td><td><a href="overview.md">overview.md</a></td></tr>
</tbody></table>
