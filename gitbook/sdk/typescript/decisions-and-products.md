---
icon: scale-balanced
description: TypeScript SDK methods for decision memory (log, list, outcome, execute, delete) and the high-level product endpoints for decision, optimize, retrieve, forecast, and agent runs.
---

# Decisions and products

These `AlgentaClient` methods cover two families: **decision memory** — persisting the decisions you make and the outcomes you observe (`logDecision`, `listDecisions`, `getDecision`, `recordOutcome`, `executeDecision`, `deleteDecision`) — and the high-level **product endpoints** that wrap common workflows (`productDecision`, `productOptimize`, `productForecast`, `productRetrieve`, `productAgentRun`). Method names are `camelCase`; bodies stay `snake_case`.

## Decision memory methods

Log a decision when you make it, then record the real outcome later so the engine can learn. `logDecision` requires only `chosen_action`; `recordOutcome` requires `actual_outcome`.

```typescript title="decision_memory.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });

// 1. Record the decision you made.
const logged = await client.logDecision({
  chosen_action: "launch_now",
  context: "Q3 product launch",
  options_considered: ["launch_now", "wait_a_quarter"],
  expected_value: 142000,
  confidence: 0.81,
  rationale: "Upside outweighs the delay risk.",
});

// 2. Later, attach the observed outcome.
const withOutcome = await client.recordOutcome(logged.id, {
  actual_outcome: 137500,
  outcome_notes: "Slightly under forecast; supply delay.",
});
console.log(withOutcome.id, withOutcome.actual_outcome);

// 3. Browse decisions that already have an outcome.
const page = await client.listDecisions({ page: 1, limit: 25, with_outcome_only: true });
console.log(page);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `logDecision(request)` | `POST /v1/decisions` | `request` is a `LogDecisionRequest`; only `chosen_action` is required. |
| `listDecisions(options?)` | `GET /v1/decisions` | Paginate with `page`, `limit`, `page_size`; `with_outcome_only` filters to decisions with a recorded outcome. |
| `getDecision(decisionId)` | `GET /v1/decisions/{id}` | Fetch one logged decision. |
| `recordOutcome(decisionId, request)` | `PATCH /v1/decisions/{id}/outcome` | `request` is a `RecordOutcomeRequest` (`actual_outcome`, `outcome_notes`). |
| `executeDecision(decisionId, request)` | `POST /v1/decisions/{id}/execute` | `request` is an `ExecuteDecisionRequest`; `webhook_url` is required. |
| `deleteDecision(decisionId)` | `DELETE /v1/decisions/{id}` | Removes a logged decision. |

{% hint style="warning" %}
`executeDecision` posts to a `webhook_url` you supply. Set `timeout_seconds` for slow endpoints, and only pass `force` or `override_safety` when you intend to bypass the engine's safety checks.
{% endhint %}

## Product methods

The product endpoints are self-contained wrappers over common decision workflows — you pass a domain-shaped request and get a domain-shaped response, no scenario wiring required.

```typescript title="products.ts"
// A decision from labeled inputs.
const decision = await client.productDecision({
  inputs: [
    { name: "revenue", value: 140000, low: 80000, high: 200000, unit: "USD" },
    { name: "cost", value: 65000, low: 40000, high: 90000, unit: "USD" },
  ],
  objective: "maximize_net_value",
  risk_tolerance: "balanced",
  scenarios: 10000,
});
console.log(decision);

// A forecast from a metric history.
const forecast = await client.productForecast({
  metric: "weekly_active_users",
  history: [1200, 1315, 1402, 1490, 1555],
  horizon: 4,
  seasonality: true,
  confidence_level: 0.9,
});
console.log(forecast);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `productDecision(request)` | `POST /v1/decision` | `inputs` is an array of `{ name, value, low?, high?, unit? }`; add `objective`, `risk_tolerance`, `scenarios`. |
| `productOptimize(request)` | `POST /v1/optimize` | `objective` plus `variables` (`{ name, min, max, step? }`); optional `constraints`, `iterations`. |
| `productForecast(request)` | `POST /v1/forecast` | `metric` and a numeric `history`; optional `horizon`, `seasonality`, `confidence_level`. |
| `productRetrieve(request)` | `POST /v1/retrieve` | `query` plus inline `documents` or a `collection_id`; optional `top_k`, `rerank`. |
| `productAgentRun(request)` | `POST /v1/agent/run` | `task` to run through the tool loop; optional `context`, `tools`, `max_steps`, `output_format`. |

### Optimize over bounded variables
`productOptimize` searches a bounded variable space for the value of the `objective`. Each variable declares `min`/`max` (and optional `step`); constraints are expressions with an optional `required` flag.

```typescript
const optimized = await client.productOptimize({
  objective: "maximize_net_value",
  variables: [
    { name: "unit_price", min: 9, max: 19, step: 1, unit: "USD" },
    { name: "ad_spend", min: 0, max: 50000, step: 5000 },
  ],
  constraints: [{ expression: "ad_spend <= 0.2 * revenue", required: true }],
  iterations: 500,
});
console.log(optimized);
```

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Simulate and query</strong></td><td>Run Monte Carlo decisions and governed data queries.</td><td><a href="simulations-and-queries.md">simulations-and-queries.md</a></td></tr>
<tr><td><strong>Use the LLM surface</strong></td><td>Chat, embeddings, tokenization, and model discovery.</td><td><a href="llm.md">llm.md</a></td></tr>
<tr><td><strong>Set up the client</strong></td><td>Install, configure, and handle errors.</td><td><a href="overview.md">overview.md</a></td></tr>
</tbody></table>
