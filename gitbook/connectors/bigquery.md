---
icon: database
description: Connect Google BigQuery to Algenta — create a bigquery connector with project and service-account credentials, test it, browse datasets, and run a governed query.
---

# Connect BigQuery

This guide creates a **`bigquery`** connector, tests the connection, browses the project's datasets and tables, registers a table as a dataset, and runs a governed query against it. A connector is a configured connection to an external system; it backs a queryable source or dataset.

BigQuery reaches Algenta through the standard connector lifecycle: **create → test → browse → connect → query**. A connector must pass its `/test` before you can browse it, and you register a dataset before you query.

## Before you start

You need:

* An Algenta API key (see [Authentication](../authentication.md)).
* A Google Cloud project ID.
* A service account JSON key with read access to the BigQuery datasets you want to query (the `BigQuery Data Viewer` and `BigQuery Job User` roles cover read and query).

Export your key so the examples can read it.

```bash
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_API_URL="https://api.algenta.ai"
```

{% hint style="info" %}
BigQuery support requires the `google-cloud-bigquery` library on the server. A self-hosted deployment that is missing it returns a clear `invalid_config` message asking you to install it. Algenta's hosted API ships with it preinstalled.
{% endhint %}

## Config fields

The `bigquery` connector reads these `config` keys:

| Field | Required | Description |
| --- | --- | --- |
| `project_id` | Yes | The Google Cloud project that owns the datasets, for example `my-analytics-project`. |
| `service_account_json` | For private projects | The service account key — either the inline JSON string or the parsed JSON object. Authenticates the connection. |
| `connection_string` | Alternative | A `bigquery://PROJECT_ID` DSN. Supply this instead of `project_id` if you prefer a single DSN; the project is parsed from it. |

If you provide neither `service_account_json` nor `connection_string`, the connector falls back to the server's ambient Google credentials (for example a workload identity attached to the deployment). On most setups you should pass an explicit service account.

{% hint style="warning" %}
`service_account_json` is a credential. Store it in the connector's `config` (it is encrypted at rest) — never paste it into a query, a log line, or a shared notebook.
{% endhint %}

## Create the connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Pass the service account JSON as a string in `config.service_account_json`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Analytics BigQuery",
    "connector_type": "bigquery",
    "config": {
      "project_id": "my-analytics-project",
      "service_account_json": "{\"type\":\"service_account\",\"project_id\":\"my-analytics-project\", ... }"
    }
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

api_url = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}

with open("service-account.json", encoding="utf-8") as handle:
    service_account = handle.read()  # read the JSON key as a string

resp = httpx.post(
    f"{api_url}/v1/connectors",
    headers=headers,
    json={
        "name": "Analytics BigQuery",
        "connector_type": "bigquery",
        "config": {
            "project_id": "my-analytics-project",
            "service_account_json": service_account,
        },
    },
)
resp.raise_for_status()
connector = resp.json()
connector_id = connector["id"]
print(connector["status"])  # "untested"
```
{% endtab %}
{% endtabs %}

The response includes the `id` you use for the test, browse, and connect steps.

## Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt: it lists one dataset in the project. On success the connector flips to `live`; on failure it flips to `error` with a message. Browsing requires a `live` connector, so always test first.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** The connector flips to `live`, and a successful response reports the reachable project:

```json
{
  "success": true,
  "message": "BigQuery accessible (project: my-analytics-project)",
  "latency_ms": 412,
  "status": "live"
}
```

If credentials are wrong or the project is unreachable, `success` is `false`, `status` is `error`, and `message` describes the failure. See [Errors](../api/errors.md) for the failure-type taxonomy.

{% hint style="success" %}
You can test a connector without saving it first. `POST /v1/connectors/test` takes an inline `{ "connector_type": "bigquery", "config": { ... } }` body and returns the same result — handy for validating credentials before you commit them. Inline previews are rate limited; use a saved connector for production workflows.
{% endhint %}

## Browse datasets and tables

`GET /v1/connectors/{id}/browse` lists the datasets and tables visible to the connector. Browsing returns `409 not_connected` unless the connector is `live`, so run `/test` first.

```bash
curl -sS "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response lists the queryable entities the project exposes:

```json
{
  "connector_type": "bigquery",
  "items": [
    {"name": "sales.orders"},
    {"name": "sales.customers"},
    {"name": "marketing.events"}
  ],
  "total": 3,
  "message": "Found 3 tables.",
  "labels": {"entity_noun": "dataset", "entity_noun_plural": "datasets"},
  "discovery": {}
}
```

BigQuery tables are addressed as `DATASET.TABLE` (for example `sales.orders`). Pick one to register as a dataset in the next step.

## Connect a dataset

`POST /v1/data/connect` ties a connection to a selection — a table or a SQL query — and registers the result as a queryable dataset (governed data). Reference the saved connector by `connection_id`, and name the table in `selection`.

{% tabs %}
{% tab title="By table" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "'"$CONNECTOR_ID"'",
    "selection": {"table": "sales.orders"}
  }'
```
{% endtab %}

{% tab title="By SQL query" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "'"$CONNECTOR_ID"'",
    "selection": {
      "sql_query": "SELECT order_id, total, region FROM sales.orders"
    }
  }'
```
{% endtab %}
{% endtabs %}

When the selection fully identifies one table, the response has `status: "ready"` with a `dataset_id` and a `schema_summary` (row and column counts):

```json
{
  "status": "ready",
  "dataset_id": "ds_8f2c1a",
  "connection_id": "cn_5b0e44",
  "schema_summary": {"rows": 128400, "columns": 9}
}
```

If the connection resolves to more than one table, the response is `status: "needs_selection"` with a `choices` array and a `connection_id` to reuse — pick one `selection` from `choices` and call `/v1/data/connect` again with that `connection_id`.

## Query the dataset

With a `dataset_id` you run a deterministic, schema-checked query through `POST /v1/query`. This is the governed-query path: results are validated against the inferred schema and are reproducible.

```python
import os

import httpx

api_url = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}

resp = httpx.post(
    f"{api_url}/v1/query",
    headers=headers,
    json={
        "dataset_id": "ds_8f2c1a",
        "select": ["region", "total"],
        "filters": [{"field": "region", "op": "eq", "value": "EMEA"}],
        "limit": 100,
    },
)
resp.raise_for_status()
print(resp.json()["rows"])
```

See [Run a governed query](../guides/governed-query.md) for the full query grammar (select, filters, operators, aggregation), and [First query](../guides/first-query.md) for an end-to-end walk-through.

## Using a DSN instead of a project ID

If you maintain connection strings centrally, supply `connection_string` instead of `project_id`. Algenta parses the project from the `bigquery://` DSN.

```json
{
  "name": "Analytics BigQuery",
  "connector_type": "bigquery",
  "config": {
    "connection_string": "bigquery://my-analytics-project",
    "service_account_json": "{ ... }"
  }
}
```

The DSN must name a project (`bigquery://PROJECT_ID`). A connector with neither `connection_string` nor `project_id` is rejected with `missing_connection_string`.

## Troubleshooting

* **`409 not_connected` when browsing.** The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed.
* **`invalid_config` mentioning `google-cloud-bigquery`.** A self-hosted server is missing the BigQuery client library. Install it with `pip install google-cloud-bigquery` and restart the API.
* **Test fails with a credentials or permission error.** Confirm the service account JSON is valid and that it has read access (`BigQuery Data Viewer`) plus query permission (`BigQuery Job User`) on the target datasets.
* **`missing_connection_string`.** Neither `project_id` nor `connection_string` was supplied. Provide one of them in `config`.
* **`BigQuery blocked by privacy policy`.** The deployment's egress policy disallows reaching `bigquery.googleapis.com`. An operator must allow that destination for customer connectors. See [Troubleshooting](../troubleshooting.md).

## Next steps

* [Connectors overview](overview.md) — the connector lifecycle across all types.
* [Connect data](../guides/connect-data.md) — the create → test → browse → connect flow in depth.
* [Snowflake connector](snowflake.md) and [ClickHouse connector](clickhouse.md) — other warehouse connectors.
* [Governed data](../concepts/governed-data.md) — what a dataset and a governed query are.
* [API reference](../api/reference.md) — every connector endpoint.