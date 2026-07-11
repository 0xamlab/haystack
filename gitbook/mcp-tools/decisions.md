---
icon: scale-balanced
description: MCP reference for Algenta's decision tools — simulate, recommend, score, compare, the product helpers, and the decision-memory log/outcome loop.
---

# Decision MCP tools

These tools cover Algenta's decisioning lane over MCP: run Monte Carlo simulations, rank options, score and compare scenarios, drive the simplified product helpers, and persist decisions to decision memory so you can close the loop by recording what actually happened. Each tool wraps a single authenticated endpoint under `/v1`.

Configure `algenta-mcp` first — see [MCP server](../sdk/mcp.md). For the modeling background, see [Simulation models & distributions](../concepts/simulation-models.md) and [Decision memory](../concepts/decision-memory.md).

{% hint style="info" %}
Two altitudes are available. `simulate`, `recommend`, `score`, `batch`, and `compare` give you full Monte Carlo control; the `product_*` helpers are one-shot, minimal-setup wrappers for common product jobs. `plan_decision` returns just the structured plan without the full envelope.
{% endhint %}

## Simulate and recommend

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `simulate` | Run a Monte Carlo simulation and return a structured recommendation. | `variables` (required; each `name`, `low`, `high`, optional `mode`); `mode` (`auto`\|`expert`), `objective` (`maximize_net_value`\|`maximize_revenue`\|`minimize_cost`\|`minimize_risk`\|`maximize_score`) for `auto`, `objective_function` for `expert`, `n_simulations` (default 10000) |
| `recommend` | Compare named options and return a ranked recommendation. | `actions` (required; min 2; `name`, `variables`, `objective`); `n_simulations` |
| `score` | Score one simulation request with explicit weights, returning the envelope plus a score breakdown. | `request` (required); `scoring_weights` |
| `batch` | Run multiple simulation requests in one call with per-item success/failure. | `items` (required; min 1) |
| `compare` | Run named scenarios side by side and return the winner plus deltas vs. the best. | `scenarios` (required; min 2; `name`, `request`); `runs`, `seed` |
| `plan_decision` | Build a structured DecisionPlan from a simulation-style request, without the full envelope. | simulation-style payload |

## Product helpers

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `product_decision` | Run the decision helper and return the chosen action plus a risk summary. | `inputs` (required; `value` + optional `low`/`high`); `objective`, `risk_tolerance`, `scenarios`, `engine`, `label` |
| `product_agent_run` | Run the task-execution helper and return a compact task result. | `task` (required); `context`, `tools`, `max_steps`, `output_format` |
| `product_optimize` | Run the optimization helper and return the best variable values. | `objective`, `variables` (required); `constraints`, `iterations`, `engine` |
| `product_retrieve` | Run the retrieval helper over caller-supplied documents or a `collection_id`. | `query` (required); `documents`, `collection_id`, `top_k`, `rerank` |
| `product_forecast` | Run the forecast helper over a historical metric series. | `metric`, `history` (required); `horizon`, `seasonality`, `confidence_level` |

## Decision memory

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `log_decision` | Persist one decision to the audit trail (immutably hashed). | `chosen_action` (required); `run_id`, `context`, `options_considered`, `expected_value`, `confidence`, `rationale`, `risk_p5`, `risk_p95`, `risk_pol`, `request_hash`, `result_hash` |
| `list_decisions` | Retrieve the audit trail, most recent first. | `page`, `limit`, `page_size`, `with_outcome_only` |
| `get_decision` | Fetch one record by id. | `decision_id` (required) |
| `record_outcome` | Record what actually happened; computes `outcome_delta = actual − expected`. | `decision_id`, `actual_outcome` (required); `outcome_notes` |
| `execute_decision` | Dispatch a logged decision to an external webhook and persist the receipt. | `decision_id`, `webhook_url` (required); `timeout_seconds`, `force`, `override_safety`, `metadata` |
| `delete_decision` | Delete one record by id. | `decision_id` (required) |

## Endpoint mapping

| Tool | Method | Endpoint |
|------|--------|----------|
| `simulate` | `POST` | `/v1/simulate` |
| `recommend` | `POST` | `/v1/recommend` |
| `score` | `POST` | `/v1/score` |
| `batch` | `POST` | `/v1/batch` |
| `compare` | `POST` | `/v1/compare` |
| `plan_decision` | `POST` | `/v1/decisions/plan` |
| `product_decision` | `POST` | `/v1/decision` |
| `product_agent_run` | `POST` | `/v1/agent/run` |
| `product_optimize` | `POST` | `/v1/optimize` |
| `product_retrieve` | `POST` | `/v1/retrieve` |
| `product_forecast` | `POST` | `/v1/forecast` |
| `log_decision` | `POST` | `/v1/decisions` |
| `list_decisions` | `GET` | `/v1/decisions` |
| `get_decision` | `GET` | `/v1/decisions/{decision_id}` |
| `record_outcome` | `PATCH` | `/v1/decisions/{decision_id}/outcome` |
| `execute_decision` | `POST` | `/v1/decisions/{decision_id}/execute` |
| `delete_decision` | `DELETE` | `/v1/decisions/{decision_id}` |

## Worked examples

### Run a Monte Carlo simulation

In `auto` mode, `simulate` needs only your `variables` (each a triangular range) and an objective. It returns a recommended action, confidence, and downside/upside percentiles.

{% code title="simulate (tool call)" %}
```json
{
  "name": "simulate",
  "arguments": {
    "mode": "auto",
    "objective": "maximize_net_value",
    "n_simulations": 10000,
    "variables": [
      { "name": "revenue", "low": 80000, "high": 200000 },
      { "name": "cost", "low": 40000, "high": 90000 }
    ]
  }
}
```
{% endcode %}

```bash
curl -sS "$ALGENTA_BASE_URL/v1/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "mode": "auto", "runs": 10000, "scenario": { "variables": { "revenue": { "low": 80000, "high": 200000 }, "cost": { "low": 40000, "high": 90000 } }, "objective": "maximize_net_value" } }'
```

For `expert` mode, pass an explicit `objective_function` expression and include `mode` on each variable so the MCP server can send a valid triangular distribution to `/v1/simulate`.

### Forecast a metric with the product helper

`product_forecast` takes a metric name and a history series and projects it forward.

{% code title="product_forecast (tool call)" %}
```json
{
  "name": "product_forecast",
  "arguments": {
    "metric": "mrr",
    "history": [100, 110, 121, 133],
    "horizon": 3,
    "confidence_level": 0.9
  }
}
```
{% endcode %}

### Log a decision, then close the loop

Persist the chosen action to decision memory, then record the real outcome later. `record_outcome` reports `outcome_delta` so you can measure prediction accuracy over time.

{% code title="log_decision (tool call)" %}
```json
{
  "name": "log_decision",
  "arguments": {
    "chosen_action": "Launch in EU first",
    "context": "Q3 go-to-market sequencing",
    "options_considered": ["Launch in EU first", "Launch in US first"],
    "expected_value": 145000,
    "confidence": 0.72,
    "run_id": "$RUN_ID"
  }
}
```
{% endcode %}

{% code title="record_outcome (tool call)" %}
```json
{
  "name": "record_outcome",
  "arguments": {
    "decision_id": "$DECISION_ID",
    "actual_outcome": 138500,
    "outcome_notes": "Slightly below plan; slower onboarding than modeled."
  }
}
```
{% endcode %}

```bash
curl -sS -X PATCH "$ALGENTA_BASE_URL/v1/decisions/$DECISION_ID/outcome" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "actual_outcome": 138500 }'
```

{% hint style="warning" %}
`execute_decision` dispatches to an external webhook and honors confidence and risk-floor policy gates. `override_safety` bypasses those gates and `force` overrides the idempotency guard — use both only when you understand the consequences.
{% endhint %}

## Related pages

{% content-ref url="../concepts/decision-memory.md" %}
[decision-memory.md](../concepts/decision-memory.md)
{% endcontent-ref %}

{% content-ref url="../guides/run-a-decision.md" %}
[run-a-decision.md](../guides/run-a-decision.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
