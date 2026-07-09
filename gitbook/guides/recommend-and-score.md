---
icon: ranking-star
description: Compare named actions and get a ranked recommendation, score a single scenario with custom weights, run many simulations at once, and compare scenarios side by side.
---

# Recommend, score, and compare decisions

Once you can simulate one scenario, these four endpoints turn simulations into a decision. `POST /v1/recommend` runs several named actions and returns the best one with a rationale. `POST /v1/score` scores a single scenario with weights you choose. `POST /v1/batch` runs many simulations in one request. `POST /v1/compare` puts scenarios side by side with deltas versus the winner. Every action or item is a normal [simulation request](simulate.md) (auto or expert), and all of them run in parallel on the engine.

## Before you start

You need:

- An API key sent as `Authorization: Bearer $ALGENTA_API_KEY` on a verified account.
- One or more simulation requests. The examples use auto mode (`low`/`high` bounds); expert mode works everywhere a request is accepted.

{% hint style="info" %}
The Python and TypeScript pattern is identical for all four endpoints: `POST` the JSON body shown in each section to the endpoint path with the `Authorization` header. The Recommend section below shows all three languages; the others show the request and response.
{% endhint %}

## Recommend an action

Submit 2–10 named actions. The engine ranks them by expected value and returns the top one as `recommended_action`, with a structured `decision_plan` that is the best entry point for dashboards and LLMs.

{% tabs %}
{% tab title="cURL" %}
```bash title="recommend.sh"
curl -sS -X POST "https://api.algenta.ai/v1/recommend" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "actions": [
      {"name": "launch_now", "request": {"mode": "auto", "scenario": {
        "variables": {"revenue": {"low": 80000, "high": 200000}, "cost": {"low": 40000, "high": 90000}},
        "objective": "maximize_net_value"}}},
      {"name": "wait_a_quarter", "request": {"mode": "auto", "scenario": {
        "variables": {"revenue": {"low": 60000, "high": 240000}, "cost": {"low": 35000, "high": 70000}},
        "objective": "maximize_net_value"}}}
    ],
    "runs": 10000
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="recommend.py"
import os
import requests

BASE = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")

resp = requests.post(
    f"{BASE}/v1/recommend",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "actions": [
            {"name": "launch_now", "request": {"mode": "auto", "scenario": {
                "variables": {"revenue": {"low": 80000, "high": 200000}, "cost": {"low": 40000, "high": 90000}},
                "objective": "maximize_net_value"}}},
            {"name": "wait_a_quarter", "request": {"mode": "auto", "scenario": {
                "variables": {"revenue": {"low": 60000, "high": 240000}, "cost": {"low": 35000, "high": 70000}},
                "objective": "maximize_net_value"}}},
        ],
        "runs": 10000,
    },
)
resp.raise_for_status()
result = resp.json()
print(result["recommended_action"], result["confidence"], result["rationale"])
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="recommend.ts"
const base = process.env.ALGENTA_API_URL ?? "https://api.algenta.ai";

const res = await fetch(`${base}/v1/recommend`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    actions: [
      { name: "launch_now", request: { mode: "auto", scenario: {
        variables: { revenue: { low: 80000, high: 200000 }, cost: { low: 40000, high: 90000 } },
        objective: "maximize_net_value" } } },
      { name: "wait_a_quarter", request: { mode: "auto", scenario: {
        variables: { revenue: { low: 60000, high: 240000 }, cost: { low: 35000, high: 70000 } },
        objective: "maximize_net_value" } } },
    ],
    runs: 10000,
  }),
});
if (!res.ok) throw new Error(`recommend failed: ${res.status}`);
const result = await res.json();
console.log(result.recommended_action, result.confidence);
```
{% endtab %}
{% endtabs %}

The `200` `RecommendResponse` ranks every action and names the winner:

```json title="recommend-response.json"
{
  "recommended_action": "launch_now",
  "confidence": 0.71,
  "rationale": "'launch_now' ranked #1 with expected value 74213.5 and 82% probability of positive outcome.",
  "action_results": [
    {"name": "launch_now", "rank": 1, "expected_value": 74213.5, "probability_of_loss": 0.18, "score": 0.71, "envelope": { "…": "full DecisionEnvelope" }},
    {"name": "wait_a_quarter", "rank": 2, "expected_value": 61044.2, "probability_of_loss": 0.24, "score": 0.64, "envelope": { "…": "full DecisionEnvelope" }}
  ],
  "total_actions": 2,
  "decision_plan": { "recommended_action": "launch_now", "confidence": 0.71, "expected_value": 74213.5, "options": ["…ranked options…"] }
}
```

Each `ActionResult` includes the full `DecisionEnvelope`, its `rank`, `expected_value`, `probability_of_loss`, and a composite `score` (0–1). `decision_plan` folds all of that into one structured summary with per-option risk (p5/p95/probability of loss) and integrity hashes.

## Score a single scenario

`/v1/score` runs one simulation and scores it with a weighted blend of expected value and downside risk. Omit `scoring_weights` to use the default `{"expected_value": 0.6, "downside_risk": 0.4}` (weights should sum to `1.0`).

```bash title="score.sh"
curl -sS -X POST "https://api.algenta.ai/v1/score" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"mode": "auto", "scenario": {
      "variables": {"revenue": {"low": 80000, "high": 200000}, "cost": {"low": 40000, "high": 90000}},
      "objective": "maximize_net_value"}},
    "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3}
  }'
```

```json title="score-response.json"
{
  "envelope": { "…": "full DecisionEnvelope" },
  "score": 0.68,
  "score_breakdown": {
    "expected_value_component": 0.42,
    "downside_risk_component": 0.26,
    "expected_value_weight": 0.7,
    "downside_risk_weight": 0.3
  }
}
```

## Compare scenarios side by side

`/v1/compare` runs 2–10 named scenarios and returns each one with its delta versus the winning scenario, so you can build a comparison table directly from the response.

```bash title="compare.sh"
curl -sS -X POST "https://api.algenta.ai/v1/compare" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": [
      {"name": "conservative", "request": {"mode": "auto", "scenario": {
        "variables": {"revenue": {"low": 70000, "high": 120000}}, "objective": "maximize_revenue"}}},
      {"name": "aggressive", "request": {"mode": "auto", "scenario": {
        "variables": {"revenue": {"low": 50000, "high": 220000}}, "objective": "maximize_revenue"}}}
    ]
  }'
```

```json title="compare-response.json"
{
  "winner": "aggressive",
  "margin": {"expected_value_delta": 12500.0, "probability_of_loss_delta": -0.04, "score_delta": 0.0},
  "scenarios": [
    {"name": "conservative", "envelope": { "…": "…" }, "delta_vs_best": {"expected_value_delta": -12500.0, "probability_of_loss_delta": 0.04, "score_delta": 0.0}},
    {"name": "aggressive", "envelope": { "…": "…" }, "delta_vs_best": {"expected_value_delta": 0.0, "probability_of_loss_delta": 0.0, "score_delta": 0.0}}
  ]
}
```

## Run a batch

`/v1/batch` runs 1–100 simulation requests in one call. Partial failures are allowed — a failed item carries `success: false` and an `error` string instead of an envelope.

```bash title="batch.sh"
curl -sS -X POST "https://api.algenta.ai/v1/batch" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"mode": "auto", "scenario": {"variables": {"revenue": {"low": 80000, "high": 200000}}, "objective": "maximize_revenue"}},
      {"mode": "expert", "simulation": {"variables": [{"name": "x", "distribution": "normal", "params": {"mean": 100, "std": 10}}], "objective_function": "x"}, "runs": 20000}
    ]
  }'
```

```json title="batch-response.json"
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {"index": 0, "success": true, "envelope": { "…": "…" }, "error": null},
    {"index": 1, "success": true, "envelope": { "…": "…" }, "error": null}
  ]
}
```

{% hint style="success" %}
**Expected result** — `/v1/recommend` returns a `recommended_action` with a rationale and every action ranked; `/v1/score` returns a `score` in `0`–`1` with a `score_breakdown`; `/v1/compare` names a `winner` with per-scenario deltas; `/v1/batch` returns `succeeded + failed == total`.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Log the decision</strong></td><td>Record the recommendation and its later outcome.</td><td><a href="decision-memory.md">decision-memory.md</a></td></tr>
<tr><td><strong>Run a what-if sweep</strong></td><td>See how sensitive the winner is to one variable.</td><td><a href="what-if.md">what-if.md</a></td></tr>
<tr><td><strong>Simulate a scenario</strong></td><td>The single-simulation request behind every action.</td><td><a href="simulate.md">simulate.md</a></td></tr>
</tbody></table>
