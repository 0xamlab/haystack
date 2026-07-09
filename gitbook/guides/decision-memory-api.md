---
icon: wand-magic-sparkles
description: Drive the full Algenta decisions API — plan, log, execute, and delete decisions — and call the one-line product endpoints for decision, agent, optimize, retrieve, and forecast.
---

# Drive decisions through the API

Algenta exposes decisions at two altitudes. The **decisions lifecycle** under `/v1/decisions` lets you generate a structured plan, log the decision you made, execute it to a webhook, record the real outcome, and delete it. The **one-call product endpoints** (`/v1/decision`, `/v1/agent/run`, `/v1/optimize`, `/v1/retrieve`, `/v1/forecast`) wrap the engine behind a single business-shaped request so you can get an answer without touching simulation internals. This guide walks both.

You need an API key (see [Authentication](../authentication.md)) exported as `$ALGENTA_API_KEY`, and a running engine — the hosted API at `https://api.algenta.ai` or a self-hosted server at `http://localhost:8000`.

{% hint style="info" %}
For the focused *log → record outcome → review* tutorial that closes the feedback loop and feeds calibration, see [Log decisions and record outcomes](decision-memory.md). This page is the wider API surface, including planning, webhook execution, and the product endpoints.
{% endhint %}

## The decisions lifecycle

{% stepper %}
{% step %}
### Plan a decision

`POST /v1/decisions/plan` runs the same validated request contract as `/v1/simulate` but returns only the compact `DecisionPlan` — the recommended action, expected value, confidence, risk, and rationale — without the full envelope. It is the LLM- and dashboard-friendly summary.

{% tabs %}
{% tab title="cURL" %}
```bash title="POST /v1/decisions/plan"
curl -sS -X POST "https://api.algenta.ai/v1/decisions/plan" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "scenario": {
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 30000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    },
    "runs": 10000,
    "seed": 42
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="plan_decision.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

plan = client.plan_decision({
    "mode": "auto",
    "scenario": {
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 30000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    "runs": 10000,
    "seed": 42,
})
print(plan.recommended_action, plan.expected_value, plan.confidence)
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="planDecision.ts"
const resp = await fetch("https://api.algenta.ai/v1/decisions/plan", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
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
  }),
});
const plan = await resp.json();
console.log(plan.recommended_action, plan.expected_value, plan.confidence);
```
{% endtab %}
{% endtabs %}

The `200` `DecisionPlan` carries `recommended_action`, `options`, `expected_value`, `confidence`, `rationale`, a `risk` object (`p5`, `p95`, `probability_of_loss`), and an `integrity` object. Once your org has recorded outcomes, the returned `confidence` is calibrated and a `calibration` summary is attached.
{% endstep %}

{% step %}
### Log the decision

`POST /v1/decisions` records the action you chose. Only `chosen_action` is required; logging `expected_value` is what lets the engine compute a delta later, and an optional `run_id` binds the record to the simulation that produced it. The call returns `201 Created` with the new decision `id`.

{% tabs %}
{% tab title="cURL" %}
```bash title="POST /v1/decisions"
curl -sS -X POST "https://api.algenta.ai/v1/decisions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "context": "Q3 pricing change for the Pro tier",
    "chosen_action": "raise_price_10pct",
    "options_considered": ["hold", "raise_price_10pct", "raise_price_20pct"],
    "expected_value": 142000,
    "confidence": 0.78,
    "risk_p5": -8000,
    "risk_p95": 210000,
    "risk_pol": 0.12
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="log_decision.py"
decision = client.log_decision({
    "context": "Q3 pricing change for the Pro tier",
    "chosen_action": "raise_price_10pct",
    "options_considered": ["hold", "raise_price_10pct", "raise_price_20pct"],
    "expected_value": 142000,
    "confidence": 0.78,
    "risk_p5": -8000,
    "risk_p95": 210000,
    "risk_pol": 0.12,
})
print(decision.id)
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="logDecision.ts"
const resp = await fetch("https://api.algenta.ai/v1/decisions", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    context: "Q3 pricing change for the Pro tier",
    chosen_action: "raise_price_10pct",
    expected_value: 142000,
    confidence: 0.78,
  }),
});
const decision = await resp.json();
console.log(decision.id);
```
{% endtab %}
{% endtabs %}

Export the returned `id` as `$DECISION_ID`. The record also pins `policy_snapshot_id`, `schema_snapshot_id`, and `manifest_version`, which is what makes it auditable later.
{% endstep %}

{% step %}
### Execute the decision to a webhook

`POST /v1/decisions/{id}/execute` fires the logged decision to an external HTTPS webhook, turning it into an automated action. The webhook receives the full decision context and integrity hashes; the response code and status are persisted back onto the record.

{% tabs %}
{% tab title="cURL" %}
```bash title="POST /v1/decisions/{id}/execute"
curl -sS -X POST "https://api.algenta.ai/v1/decisions/$DECISION_ID/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://ops.example.com/hooks/pricing",
    "timeout_seconds": 10,
    "metadata": {"channel": "pricing-bot"}
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="execute_decision.py"
import os, requests

resp = requests.post(
    f"https://api.algenta.ai/v1/decisions/{os.environ['DECISION_ID']}/execute",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "webhook_url": "https://ops.example.com/hooks/pricing",
        "timeout_seconds": 10,
    },
)
receipt = resp.json()
print(receipt["execution_status"], receipt["response_code"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="executeDecision.ts"
const resp = await fetch(
  `https://api.algenta.ai/v1/decisions/${process.env.DECISION_ID}/execute`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      webhook_url: "https://ops.example.com/hooks/pricing",
      timeout_seconds: 10,
    }),
  },
);
const receipt = await resp.json();
console.log(receipt.execution_status, receipt.response_code);
```
{% endtab %}
{% endtabs %}

The `200` `ExecutionReceipt` returns `execution_status` (`delivered` or `failed`), `response_code`, `executed_at`, and a `payload_summary`. Execution passes through your org's safety gates: a decision below `min_confidence` or beyond `risk_floor` is blocked with `409` and an `execution_blocked_*` code. Pass `force: true` to re-fire an already-delivered decision, or `override_safety: true` to bypass the confidence and risk gates for one call. See [Configure the execution policy](execution-policy.md).
{% endstep %}

{% step %}
### Record the actual outcome

When the real number is known, close the loop with `PATCH /v1/decisions/{id}/outcome`. The engine sets `outcome_recorded_at`, computes `outcome_delta = actual_outcome - expected_value`, and refreshes your org's confidence calibration.

{% tabs %}
{% tab title="cURL" %}
```bash title="PATCH /v1/decisions/{id}/outcome"
curl -sS -X PATCH "https://api.algenta.ai/v1/decisions/$DECISION_ID/outcome" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"actual_outcome": 131500, "outcome_notes": "Lower conversion than modeled."}'
```
{% endtab %}

{% tab title="Python" %}
```python title="record_outcome.py"
updated = client.record_outcome(
    decision.id,
    actual_outcome=131500,
    outcome_notes="Lower conversion than modeled.",
)
print(updated.outcome_delta)  # -10500
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="recordOutcome.ts"
const resp = await fetch(
  `https://api.algenta.ai/v1/decisions/${process.env.DECISION_ID}/outcome`,
  {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ actual_outcome: 131500 }),
  },
);
const updated = await resp.json();
console.log(updated.outcome_delta); // -10500
```
{% endtab %}
{% endtabs %}
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — you generated a `DecisionPlan`, logged a decision (`201`), executed it to a webhook (`200`, `execution_status: "delivered"`), and recorded its outcome so `outcome_delta` is populated (here `131500 - 142000 = -10500`).
{% endhint %}

## Read and manage the log

`GET /v1/decisions` returns the org's decision history, most recent first, with pagination (`page`, `limit`) and a `with_outcome_only` filter. `GET /v1/decisions/{id}` reads one; `DELETE /v1/decisions/{id}` deletes one.

{% code title="list, read, delete" %}
```bash
# List only decisions that already have an outcome recorded.
curl -sS "https://api.algenta.ai/v1/decisions?with_outcome_only=true&limit=20" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# Read a single record.
curl -sS "https://api.algenta.ai/v1/decisions/$DECISION_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# Delete a record — returns 204 No Content.
curl -sS -X DELETE "https://api.algenta.ai/v1/decisions/$DECISION_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

The list response carries `decisions[]`, `total`, `page`, `limit`, and `pages`.

## The one-call product API

These endpoints hide the engine behind a single business-shaped request. Each returns a `latency_ms` and a stable id, and each is metered like any other engine call.

| Endpoint | Ask | Key request fields | Key response fields |
| --- | --- | --- | --- |
| `POST /v1/decision` | "What should I do?" | `inputs[]`, `objective`, `risk_tolerance`, `scenarios`, `engine` | `action`, `confidence`, `reasoning`, `why[]`, `expected_outcome`, `downside_risk`, `upside_potential`, `probability_of_loss` |
| `POST /v1/agent/run` | "Do this task." | `task`, `context`, `tools[]`, `max_steps`, `output_format` | `run_id`, `status`, `result`, `steps[]`, `tools_used[]` |
| `POST /v1/optimize` | "Find the best value." | `objective`, `variables[]` (`min`, `max`), `constraints[]`, `iterations`, `engine` | `optimal_values`, `objective_value`, `improvement_vs_midpoint`, `constraints_satisfied` |
| `POST /v1/retrieve` | "Search my knowledge." | `query`, `documents[]` or `collection_id`, `top_k`, `rerank` | `results[]` (`rank`, `relevance_score`, `snippet`), `total_searched` |
| `POST /v1/forecast` | "What will happen?" | `metric`, `history[]`, `horizon`, `seasonality`, `confidence_level` | `baseline`, `forecast_mean`, `total_change_pct`, `periods[]` |

A worked example of the flagship endpoint — describe your inputs and get an action back:

{% tabs %}
{% tab title="cURL" %}
```bash title="POST /v1/decision"
curl -sS -X POST "https://api.algenta.ai/v1/decision" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {"name": "revenue", "value": 120000, "low": 80000, "high": 180000, "unit": "USD"},
      {"name": "cost",    "value": 70000,  "low": 50000, "high": 100000, "unit": "USD"}
    ],
    "objective": "maximize_value",
    "risk_tolerance": "medium",
    "scenarios": 10000
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="decision.py"
import os, requests

resp = requests.post(
    "https://api.algenta.ai/v1/decision",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "inputs": [
            {"name": "revenue", "value": 120000, "low": 80000, "high": 180000, "unit": "USD"},
            {"name": "cost", "value": 70000, "low": 50000, "high": 100000, "unit": "USD"},
        ],
        "objective": "maximize_value",
        "risk_tolerance": "medium",
        "scenarios": 10000,
    },
)
answer = resp.json()
print(answer["action"], answer["confidence"], answer["why"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="decision.ts"
const resp = await fetch("https://api.algenta.ai/v1/decision", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    inputs: [
      { name: "revenue", value: 120000, low: 80000, high: 180000, unit: "USD" },
      { name: "cost", value: 70000, low: 50000, high: 100000, unit: "USD" },
    ],
    objective: "maximize_value",
    risk_tolerance: "medium",
    scenarios: 10000,
  }),
});
const answer = await resp.json();
console.log(answer.action, answer.confidence, answer.why);
```
{% endtab %}
{% endtabs %}

The `action` is `proceed`, `pause`, or `reject`, with a plain-English `reasoning` string and three crisp `why` bullets. The remaining four endpoints follow the same one-request shape:

{% code title="the other four product endpoints" %}
```bash
# Forecast a metric from history.
curl -sS -X POST "https://api.algenta.ai/v1/forecast" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -H "Content-Type: application/json" \
  -d '{"metric": "monthly_revenue", "history": [100, 110, 121, 133], "horizon": 6}'

# Optimize variables against an objective.
curl -sS -X POST "https://api.algenta.ai/v1/optimize" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -H "Content-Type: application/json" \
  -d '{"objective": "maximize profit", "variables": [{"name": "price", "min": 20, "max": 60}], "iterations": 2000}'

# Search documents (inline mode).
curl -sS -X POST "https://api.algenta.ai/v1/retrieve" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -H "Content-Type: application/json" \
  -d '{"query": "refund policy", "documents": [{"id": "d1", "content": "Refunds are issued within 30 days."}], "top_k": 3}'

# Run an agent task.
curl -sS -X POST "https://api.algenta.ai/v1/agent/run" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -H "Content-Type: application/json" \
  -d '{"task": "Summarize the attached revenue figures and flag risks", "max_steps": 8}'
```
{% endcode %}

## Troubleshooting

{% hint style="warning" %}
**Execute returns `409 execution_blocked_confidence` or `execution_blocked_risk_floor`.** The decision failed a safety gate. Raise the logged `confidence`/`expected_value`, relax the policy, or pass `override_safety: true` for a one-time bypass. See [Configure the execution policy](execution-policy.md).
{% endhint %}

{% hint style="info" %}
**`404 Decision not found`.** The log is scoped to your org and workspace. Confirm the `id` came from a `POST /v1/decisions` made with the same key and was not already deleted. See [API errors](../api/errors.md).
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Close the feedback loop</strong></td><td>The focused log → outcome → review tutorial that feeds calibration.</td><td><a href="decision-memory.md">decision-memory.md</a></td></tr>
<tr><td><strong>Configure the execution policy</strong></td><td>Set the safety gates that guard webhook execution.</td><td><a href="execution-policy.md">execution-policy.md</a></td></tr>
<tr><td><strong>Decision memory concept</strong></td><td>Why the engine records decisions and learns from outcomes.</td><td><a href="../concepts/decision-memory.md">../concepts/decision-memory.md</a></td></tr>
</tbody></table>
