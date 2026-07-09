---
icon: dice
description: Python SDK reference for the simulation and query methods — simulate, resolve, query, query_batch, verify, recommend, score, compare, and plan_decision.
---

# Simulations and queries

These methods run Monte Carlo simulations and governed queries against the Algenta engine. They are available on both `AlgentaClient` and `AsyncAlgentaClient` (await the async calls). Simulation and recommendation methods take keyword arguments; the query methods take a request dict and, where noted, merge extra keyword arguments into the body. See [API overview](../../api/overview.md) for the underlying HTTP contract and [Simulation models](../../concepts/simulation-models.md) for the distributions.

## Method reference

| Method | Purpose |
| --- | --- |
| `simulate(**kwargs)` | Run a Monte Carlo simulation and return a `DecisionEnvelope`. Posts to `/v1/simulate`. |
| `resolve(request=None, **kwargs)` | Resolve a partial or natural-language hint into a typed, executable plan (`ResolveResult`). Posts to `/v1/resolve`. |
| `query(request=None, **kwargs)` | Run a governed exact query and return matching rows (`QueryResult`). Posts to `/v1/query`. |
| `query_with_metadata(request=None, **kwargs)` | Like `query`, plus execution metadata (request id, timing) and response headers (`QueryWithMetadataResult`). Posts to `/v1/query`. |
| `query_batch(request)` | Run several governed queries in one round trip (`QueryBatchResult`). Posts to `/v1/query/batch`. |
| `query_sql_report(request)` | Run a read-only SQL-style report over a dataset (`QuerySqlReportResult`). Posts to `/v1/query/sql-report`. |
| `plan_decision(request)` | Turn a goal and context into a structured decision plan (`DecisionPlanResult`). Posts to `/v1/decisions/plan`. |
| `verify(request=None, **kwargs)` | Check a claim against governed data and return a verdict (`VerifyResult`). Posts to `/v1/verify`. |
| `explain(request=None, **kwargs)` | Run a query and annotate the resolved plan so you can see how the answer was produced (`ExplainResult`). |
| `recommend(actions, **kwargs)` | Rank candidate actions against an objective. Posts to `/v1/recommend`. |
| `score(request, scoring_weights=None)` | Score a scenario or action set, optionally with custom weights. Posts to `/v1/score`. |
| `batch(items)` | Run a list of simulation requests together. Posts to `/v1/batch`. |
| `compare(scenarios, **kwargs)` | Compare multiple scenarios side by side. Posts to `/v1/compare`. |

{% hint style="info" %}
`plan_decision` lives on this surface (it turns intent into a plan) while the decision-memory methods that record and replay decisions live in [Decisions and products](decisions-and-products.md).
{% endhint %}

## Example: simulate a scenario

```python title="simulate.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

envelope = client.simulate(
    mode="auto",
    simulation_model="monte_carlo",
    scenario={
        "name": "Product launch decision",
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 40000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    runs=10000,
)

print(envelope.recommended_action, envelope.confidence)
print(envelope.metrics.expected_value)
```

## Example: resolve, query, and batch

```python title="query.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

# Resolve a hint into a typed plan, then run a query with metadata.
plan = client.resolve({"dataset_id": "$DATASET_ID", "metric": {"hint": "revenue"}})

result = client.query_with_metadata(
    {
        "dataset_id": "$DATASET_ID",
        "metric": {"hint": "revenue"},
        "aggregation": "sum",
    }
)
print(result.metadata.request_id, result.data)

# Run several governed queries in one round trip.
batch = client.query_batch(
    {
        "queries": [
            {"dataset_id": "$DATASET_ID", "metric": {"hint": "revenue"}, "aggregation": "sum"},
            {"dataset_id": "$DATASET_ID", "metric": {"hint": "orders"}, "aggregation": "count"},
        ]
    }
)
print(batch.results)
```

## Related pages

{% content-ref url="../../guides/simulate.md" %}
[simulate.md](../../guides/simulate.md)
{% endcontent-ref %}

{% content-ref url="../../guides/governed-query.md" %}
[governed-query.md](../../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="decisions-and-products.md" %}
[decisions-and-products.md](decisions-and-products.md)
{% endcontent-ref %}
