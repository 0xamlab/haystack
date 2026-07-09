---
icon: diagram-project
description: Python SDK reference for decision memory and product intelligence — log_decision, record_outcome, execute_decision, plus product_decision, product_optimize, and product_forecast.
---

# Decisions and products

These methods record decisions in [decision memory](../../concepts/decision-memory.md) and drive product-level intelligence (decision, optimize, retrieve, forecast). They are available on both `AlgentaClient` and `AsyncAlgentaClient` (await the async calls). The product methods take a request dict; the decision-memory methods take a decision id plus typed keyword arguments.

## Method reference

| Method | Purpose |
| --- | --- |
| `product_decision(request)` | Make a product-level decision (`ProductDecisionResult`). Posts to `/v1/decision`. |
| `product_agent_run(request)` | Run a product agent workflow (`ProductAgentRunResult`). Posts to `/v1/agent/run`. |
| `product_optimize(request)` | Optimize a product objective (`ProductOptimizeResult`). Posts to `/v1/optimize`. |
| `product_retrieve(request)` | Retrieve ranked product results for a query (`ProductRetrieveResult`). Posts to `/v1/retrieve`. |
| `product_forecast(request)` | Forecast product metrics over future periods (`ProductForecastResult`). Posts to `/v1/forecast`. |
| `log_decision(request)` | Record a decision in decision memory (`DecisionLogResult`). Posts to `/v1/decisions`. |
| `list_decisions(*, page=None, limit=None, page_size=None, with_outcome_only=None)` | List recorded decisions (`DecisionListResult`). Reads `/v1/decisions`. |
| `get_decision(decision_id)` | Fetch a single recorded decision (`DecisionLogResult`). Reads `/v1/decisions/{decision_id}`. |
| `record_outcome(decision_id, *, actual_outcome, outcome_notes=None)` | Attach the realized outcome to a decision (`DecisionLogResult`). Posts to `/v1/decisions/{decision_id}/outcome`. |
| `execute_decision(decision_id, *, webhook_url, timeout_seconds=10.0, force=False, override_safety=False, metadata=None)` | Execute a recorded decision via a webhook and return a receipt (`ExecutionReceiptResult`). Posts to `/v1/decisions/{decision_id}/execute`. |
| `delete_decision(decision_id)` | Delete a recorded decision. Sends `DELETE /v1/decisions/{decision_id}`. |

## Example: log a decision and record its outcome

```python title="decision_memory.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

# Record a decision.
logged = client.log_decision(
    {
        "chosen_action": "Scale checkout service",
        "expected_value": 42000,
        "context": "Checkout p95 latency at 820ms",
    }
)

# Later, attach what actually happened.
updated = client.record_outcome(
    logged.id,
    actual_outcome=39500,
    outcome_notes="Latency improved; revenue slightly below forecast.",
)

# Review decisions that already have an outcome.
history = client.list_decisions(with_outcome_only=True, limit=20)
for decision in history.decisions:
    print(decision.id, decision.chosen_action)
```

## Example: forecast product metrics

```python title="product_forecast.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

forecast = client.product_forecast(
    {
        "product_id": "sku-1042",
        "metric": "units_sold",
        "horizon": 6,
    }
)
for period in forecast.periods:
    print(period.period, period.forecast)
```

## Related pages

{% content-ref url="../../guides/decision-memory.md" %}
[decision-memory.md](../../guides/decision-memory.md)
{% endcontent-ref %}

{% content-ref url="../../concepts/decision-memory.md" %}
[decision-memory.md](../../concepts/decision-memory.md)
{% endcontent-ref %}

{% content-ref url="simulations-and-queries.md" %}
[simulations-and-queries.md](simulations-and-queries.md)
{% endcontent-ref %}
