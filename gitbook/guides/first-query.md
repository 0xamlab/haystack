---
icon: magnifying-glass
description: Run your first governed query against a registered dataset and read the deterministic result, using HTTP, the de CLI, or the Python SDK.
---

# Make your first query

By the end of this page you will have sent one governed query to a dataset and read back a deterministic result — an aggregated value with the column the engine resolved, its confidence, and the plan it executed. A governed query is structured intent (which dataset, which metric, which aggregation), never raw natural language; the engine resolves it under a typed contract so the same inputs always return the same answer. Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and at least one registered dataset visible to your key. If you have no dataset yet, connect one first; the rest of this page assumes a dataset is already queryable.

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every tool below picks them up from the environment. Use `https://api.algenta.ai` for Algenta cloud, or your own origin (for example `http://localhost:8000`) for a self-hosted deployment.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

Both lines should print without error, and the base URL should match the deployment you intend to query.
{% endstep %}

{% step %}
### Find a dataset to query

A query is scoped to one registered dataset by its `dataset_id`. List the datasets your key can see and copy one ID.

```bash title="List datasets"
curl -s "$ALGENTA_BASE_URL/v1/data" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response lists visible datasets, each with a `dataset_id`. Pick one and note its ID for the next step. If the list is empty, your key has no datasets yet — connect one before continuing.
{% endstep %}

{% step %}
### Send the query

Send structured intent to `POST /v1/query` (OpenAPI tag **Semantic Query**). Beginner queries use the **hint** form: name the dataset, describe the metric by its structural `role` plus an optional `hint` word, and pick an `aggregation` (`sum`, `avg`, `count`, `max`, or `min`). The engine resolves the best matching column for you. Replace `$DATASET_ID` with the ID from the previous step.

{% tabs %}
{% tab title="HTTP" %}
```bash title="POST /v1/query"
curl -s -X POST "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "'"$DATASET_ID"'",
    "metric": { "role": "derived_measure", "hint": "revenue" },
    "aggregation": "sum"
  }'
```

A `200` response with a JSON body that includes `result` and `resolved_column` means the query executed. A `4xx` body carries an error `code` and `message` (see [API errors](../api/errors.md)).
{% endtab %}

{% tab title="de CLI" %}
The `de` CLI sends governed queries from a JSON request file. A single query is one entry in a batch. Save the request, then run it.

```bash title="first-query.json"
cat > first-query.json <<'JSON'
{
  "queries": [
    {
      "key": "first",
      "request": {
        "dataset_id": "DATASET_ID",
        "metric": { "role": "derived_measure", "hint": "revenue" },
        "aggregation": "sum"
      }
    }
  ]
}
JSON
```

```bash title="de data query-batch"
de data query-batch first-query.json
```

The command prints one row per query key. A `Status` of `ok` with a non-null `rows` count means the query executed; `error` prints the failure `code` and `message`.
{% endtab %}

{% tab title="Python" %}
```python title="first_query.py"
import os

from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url=os.environ["ALGENTA_BASE_URL"],
)

result = client.query(
    {
        "dataset_id": os.environ["DATASET_ID"],
        "metric": {"role": "derived_measure", "hint": "revenue"},
        "aggregation": "sum",
    }
)

print(result.result, result.resolved_column, result.confidence)
```

Running the script prints three values without raising. A raised `ValidationError` or `AuthenticationError` means the request or key needs fixing before you continue.
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Read the result

Inspect the response body. Every governed query returns the same `QueryResponse` shape. The fields you care about first are:

| Field | What it tells you |
| --- | --- |
| `result` | The aggregated value the engine computed. |
| `result_type` | The shape of `result` (for example a scalar or a grouped table). |
| `resolved_column` | The exact column the engine matched to your metric role. |
| `resolved_source` | The dataset or source the value came from. |
| `confidence` | How sure the resolver is about the column match (0.0 to 1.0). |
| `row_count` | How many rows the aggregation covered. |
| `plan` | The ordered, human-readable steps the engine ran. |
| `latency_ms` | Server-side execution time for the query. |

Confirm `result` is populated and `resolved_column` is the column you expected. If `confidence` is below `0.7` or `ambiguous` is `true`, the engine matched more than one plausible column — inspect `candidates` and re-run with an exact `source_name` plus `metric_column` once you know the schema.
{% endstep %}
{% endstepper %}

## Expected result

You have run one governed query end to end. The HTTP call, the `de data query-batch` command, and the Python SDK each return the same `QueryResponse`: a populated `result`, the `resolved_column` and `resolved_source` the engine chose, a `confidence` score, a non-zero `row_count`, and a `plan` listing the executed steps. Because the query is deterministic, repeating it with the same dataset and intent returns the same `result` and the same `plan_hash`.

## Troubleshooting

{% hint style="warning" %}
**Empty dataset list or `404` on the dataset.** Your key cannot see the dataset you referenced. Re-run the list step in this page and copy a `dataset_id` that actually appears, or connect a dataset first.
{% endhint %}

{% hint style="info" %}
**`result` is `null` or `confidence` is low.** The hint form could not confidently resolve a column. Change the `metric.hint` to a word closer to the user's question, or switch to the exact form (`source_name` + `metric_column`) after reading the dataset schema. See [Run a governed query](governed-query.md) for the exact-spec path.
{% endhint %}

## Next

{% content-ref url="governed-query.md" %}
[governed-query.md](governed-query.md)
{% endcontent-ref %}

{% content-ref url="../sdk/python.md" %}
[python.md](../sdk/python.md)
{% endcontent-ref %}
