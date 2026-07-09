---
icon: database
description: MCP reference for Algenta data tools — onboard and train datasets, run the high-level connection flow, register sources, and ingest tables to a simulation.
---

# Data and ingest tools

These MCP tools cover the full data lifecycle: register and train datasets for semantic querying, run the high-level connection flow that produces a reusable `dataset_id`, do advanced source registration with schema and join-key discovery, and one-shot ingest of tabular data into a ready-to-run simulation. Most users only need the connection flow (`connect_data`, `list_data`, `get_data_schema`); the `register_source` family is for advanced schema profiling. Every tool maps one-to-one to a `/v1` endpoint.

{% hint style="info" %}
Work low-token first. Use `list_data(search=..., compact=true)` to find a dataset, `get_data_summary(dataset_id)` to check it, and only then `get_data_schema(dataset_id)` for the full payload. This keeps discovery cheap before you commit tokens to a schema.
{% endhint %}

## Dataset lifecycle

Register a dataset and manage its semantic-training state. Onboarding profiles column roles automatically and starts background training; queries work immediately via a fallback model and improve once schema-specific training completes.

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `onboard_dataset` | Register a dataset for semantic querying and start background training. | One of `columns` / `records` / `csv`; optional `name`, `domain_aliases`, `async_train`. |
| `list_datasets` | List registered datasets and their model tier; deterministic lexical search + compact mode. | `search`, `status`, `source_name`, `compact`, `page`, `limit`. |
| `get_dataset_status` | Live training status and model tier for one dataset (`none` / `base` / `schema`). | `dataset_id` (required). |
| `retrain_dataset` | Re-trigger semantic training after schema or alias changes. | `dataset_id` (required), `epochs`. |

## The connection flow

The high-level path for connecting a data source and getting a reusable dataset. When a connection resolves to more than one table, file, or endpoint, `connect_data` returns `status: needs_selection` with a `choices` list — call it again with the returned `connection_id` and your chosen `selection`.

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `connect_data` | Connect a source once, pick a table/file/endpoint, and get a reusable `dataset_id`. | `dataset_name` (required); `connector` envelope or inline `records` / `csv` / `json_str` / `url`; `connection_id`, `selection`, `visibility`. |
| `list_data` | List datasets visible to the current user; search + compact for low-token discovery. | `search`, `status`, `source_name`, `compact`, `page`, `limit`. |
| `get_data_summary` | Low-token selection summary for a saved dataset before loading the full schema. | `dataset_id` (required). |
| `get_data_schema` | Full schema: columns, roles summary, formulas, and query hints. | `dataset_id` (required). |
| `refresh_data` | Refresh a saved dataset from its original database/API/object-store origin. | `dataset_id` (required). |
| `disconnect_data` | Delete a saved dataset and disconnect it from future use. | `dataset_id` (required). |

## Sources and schema discovery

Advanced tools that register a source and return full schema profiling — every column's type, cardinality, and fill rate — plus detected formula relationships (`A×B≈C`) and automatic join keys to every already-registered source. A registered source is queryable by name via `query_data`.

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `register_source` | Advanced. Register a source for full schema profiling, formula detection, and join-key detection. | `source` (required, with `name` + one of `records` / `csv` / `json_str` / `url` / `connection`); `description`. |
| `list_sources` | Advanced. List registered sources with schema summaries. | `page`, `limit`. |
| `get_source_schema` | Advanced. Full schema for one source: column types, cardinality, fill rates, formulas, join keys. | `source_id` (required). |

## Ingest to simulation

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `ingest_data` | Auto-map tabular data to a simulation payload (distributions, polarity, units, objective); optionally run it immediately. | `tables` (required); `run_simulation`, `runs`, `domain`. |

## Method and endpoint

Because each tool is a one-to-one wrapper, you can reproduce any call against the raw endpoint.

| Tool | Method | Endpoint |
| --- | --- | --- |
| `onboard_dataset` | `POST` | `/v1/datasets/onboard` |
| `list_datasets` | `GET` | `/v1/datasets` |
| `get_dataset_status` | `GET` | `/v1/datasets/{dataset_id}/status` |
| `retrain_dataset` | `POST` | `/v1/datasets/{dataset_id}/retrain` |
| `connect_data` | `POST` | `/v1/data/connect` |
| `list_data` | `GET` | `/v1/data` |
| `get_data_summary` | `GET` | `/v1/data/{dataset_id}/summary` |
| `get_data_schema` | `GET` | `/v1/data/{dataset_id}` |
| `refresh_data` | `POST` | `/v1/data/{dataset_id}/refresh` |
| `disconnect_data` | `DELETE` | `/v1/data/{dataset_id}` |
| `register_source` | `POST` | `/v1/sources/register` |
| `list_sources` | `GET` | `/v1/sources` |
| `get_source_schema` | `GET` | `/v1/sources/{source_id}` |
| `ingest_data` | `POST` | `/v1/ingest` |

## Worked examples

### Connect a dataset from inline records

`connect_data` with inline `records` performs a direct upload and returns a reusable `dataset_id`. The tool arguments an MCP host sends:

```json title="connect_data (tool arguments)"
{
  "dataset_name": "Q3 orders",
  "records": [
    { "order_id": 1, "region": "emea", "amount": 1200, "status": "completed" },
    { "order_id": 2, "region": "amer", "amount": 890, "status": "refunded" }
  ]
}
```

A representative response for a direct upload:

```json title="representative response"
{
  "status": "ready",
  "dataset_id": "ds_...",
  "connection_type": "file_upload",
  "visibility": "private",
  "refreshable": false,
  "latency_ms": 42
}
```

If instead the source resolves to several tables or files, the response is `status: "needs_selection"` with a `choices` list and a `connection_id`. Call `connect_data` again with that `connection_id` and the chosen `selection` to finish.

The equivalent HTTP call:

```bash title="connect_data via HTTP"
curl -s "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "dataset_name": "Q3 orders",
        "records": [
          { "order_id": 1, "region": "emea", "amount": 1200, "status": "completed" },
          { "order_id": 2, "region": "amer", "amount": 890, "status": "refunded" }
        ]
      }'
```

### Discover a dataset cheaply, then read its summary

Chain low-token discovery: filter with `list_data`, then pull the compact summary before the full schema.

```json title="list_data (tool arguments)"
{ "search": "orders", "compact": true, "limit": 10 }
```

```bash title="list_data then get_data_summary via HTTP"
curl -s "$ALGENTA_BASE_URL/v1/data?search=orders&compact=true&limit=10" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '.datasets[].dataset_id'

curl -s "$ALGENTA_BASE_URL/v1/data/$DATASET_ID/summary" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

A `get_data_summary` response carries just enough to decide whether to load the schema:

```json title="representative response"
{
  "dataset_id": "ds_...",
  "name": "Q3 orders",
  "status": "ready",
  "source_names": ["orders"],
  "row_count": 12840,
  "column_count": 9,
  "query_hints": ["revenue by region", "completed orders by month"]
}
```

### Ingest tables and run a simulation in one call

`ingest_data` auto-maps tabular data to a simulation payload; set `run_simulation` to `true` to execute immediately.

```json title="ingest_data (tool arguments)"
{
  "tables": [
    {
      "name": "launch",
      "records": [
        { "revenue": 180000, "cost": 90000, "units": 1200 },
        { "revenue": 210000, "cost": 95000, "units": 1400 }
      ]
    }
  ],
  "run_simulation": true,
  "runs": 10000,
  "domain": "finance"
}
```

```json title="representative response"
{
  "fields_detected": 3,
  "records_analyzed": 2,
  "objective_function": "maximize_net_value",
  "variables": [
    { "name": "revenue", "polarity": "positive" },
    { "name": "cost", "polarity": "negative" }
  ],
  "simulation_result": {
    "recommended_action": "proceed",
    "confidence": 0.91,
    "expected_value": 108000.0,
    "probability_of_loss": 0.04,
    "scenarios_run": 10000
  },
  "latency_ms": 61
}
```

## Related pages

{% content-ref url="query.md" %}
[query.md](query.md)
{% endcontent-ref %}

{% content-ref url="connectors.md" %}
[connectors.md](connectors.md)
{% endcontent-ref %}

{% content-ref url="../guides/connect-data.md" %}
[../guides/connect-data.md](../guides/connect-data.md)
{% endcontent-ref %}
