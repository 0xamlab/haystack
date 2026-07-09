---
icon: magnifying-glass
description: MCP reference for Algenta query tools — governed exact queries, multi-metric batches, and constrained read-only SQL reports over your authorized datasets.
---

# Query tools

Algenta exposes three governed query surfaces as MCP tools. `query_data` runs a single governed exact query; `query_batch` runs several in one API call; `query_sql_report` runs a constrained read-only SQL rowset for wide reports that do not fit the exact-query surface. Convert the user's question into a structured intent — a metric role, an aggregation, dimensions to group by, and filters — and let the engine resolve column meaning from the data's mathematical and statistical structure. Every tool maps one-to-one to a `/v1` endpoint.

{% hint style="warning" %}
Do not write SQL or guess column names for `query_data` or `query_batch`. The governed filter is a record-predicate contract over normalized rows, not a SQL predicate language, so it applies equally to SQL databases, Redis snapshots, files, and API-fed data. Only reach for `query_sql_report` when you genuinely need a wide read-only rowset.
{% endhint %}

## The query tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `query_data` | Run one governed exact query over a dataset from a structured intent. | `dataset_id` (or `sources`); `metric.role`, `aggregation`, `group_by`, `filter`, `limit`, `order`. |
| `query_batch` | Run several governed exact queries in one call, with optional shared defaults. | `queries` (required, each `key` + `request`); `defaults` (`dataset_id`, `filter`, `limit`, `order`). |
| `query_sql_report` | Run a constrained read-only SQL rowset over authorized datasets. | `sources` (required, each `dataset_id` + optional `alias`), `sql` (required), `max_rows`. |

## Structured query vocabulary

`query_data` (and each item in `query_batch`) is built from a small, fixed vocabulary. Pick the structural `metric.role`, an aggregation, dimensions, and filters — the engine resolves the actual columns.

### Metric roles

| Role | Use for |
| --- | --- |
| `derived_measure` | The main financial/operational aggregate (revenue, spend, value). |
| `base_measure` | Counts, quantities, discrete amounts. |
| `unit_measure` | Per-unit prices and rates. |
| `ratio` | Percentages, margins, fill rates (0–1 range). |
| `component` | A contributing part of a derived measure. |
| `identifier` | A key or identifier column. |
| `metric` | Let the engine pick the best numeric column. |

### Aggregation, order, and filters

| Field | Accepted values |
| --- | --- |
| `aggregation` | `sum` (default), `avg`, `count`, `max`, `min`. |
| `order` | `desc` (default), `asc`. |
| `filter.time_filter` | `last_quarter`, `this_quarter`, `last_month`, `this_month`, `last_year`, `this_year`. |
| `filter.conditions[].op` | `eq`, `in`, `gt`, `gte`, `lt`, `lte`, `is_null`, `is_not_null`. |

Each filter condition names either an exact `column` or a `dimension_hint` (a semantic label when the column is not yet known), plus an `op` and a `value` (or `values` for `in`).

## Method and endpoint

Because each tool is a one-to-one wrapper, you can reproduce any call against the raw endpoint.

| Tool | Method | Endpoint |
| --- | --- | --- |
| `query_data` | `POST` | `/v1/query` |
| `query_batch` | `POST` | `/v1/query/batch` |
| `query_sql_report` | `POST` | `/v1/query/sql-report` |

## Worked examples

### A single governed exact query

Ask for total completed revenue by region last quarter, top five. The tool arguments an MCP host sends:

```json title="query_data (tool arguments)"
{
  "dataset_id": "$DATASET_ID",
  "metric": { "role": "derived_measure", "hint": "revenue" },
  "aggregation": "sum",
  "group_by": ["region"],
  "filter": {
    "time_filter": "last_quarter",
    "conditions": [
      { "dimension_hint": "status", "op": "eq", "value": "completed" }
    ]
  },
  "order": "desc",
  "limit": 5
}
```

The equivalent HTTP call:

```bash title="query_data via HTTP"
curl -s "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "dataset_id": "'"$DATASET_ID"'",
        "metric": { "role": "derived_measure", "hint": "revenue" },
        "aggregation": "sum",
        "group_by": ["region"],
        "filter": { "time_filter": "last_quarter", "conditions": [ { "dimension_hint": "status", "op": "eq", "value": "completed" } ] },
        "order": "desc",
        "limit": 5
      }'
```

A representative response records exactly what the engine resolved and executed:

```json title="representative response"
{
  "decision_path": "governed_exact",
  "validated": true,
  "clarification_required": false,
  "confidence": 0.97,
  "resolved_column": "amount",
  "resolved_role": "derived_measure",
  "resolved_source": "orders",
  "row_count": 3,
  "result": [
    { "region": "emea", "value": 128400.0 },
    { "region": "amer", "value": 96550.0 }
  ],
  "request_id": "req_..."
}
```

{% hint style="info" %}
When `clarification_required` is `true` or `confidence` is below `0.85`, the response includes a `candidates` list and a note instead of a confident result. Surface the candidates and ask the user to clarify the intended field or join — never fabricate a column name. A pre-execution rejection is reported in `rejection_reason`.
{% endhint %}

### Several metrics in one call

`query_batch` runs multiple exact queries together. `defaults` are merged into each item's `request` before execution.

```json title="query_batch (tool arguments)"
{
  "defaults": {
    "dataset_id": "$DATASET_ID",
    "filter": { "time_filter": "last_quarter" }
  },
  "queries": [
    { "key": "revenue", "request": { "metric": { "role": "derived_measure", "hint": "revenue" }, "aggregation": "sum" } },
    { "key": "orders",  "request": { "metric": { "role": "base_measure" }, "aggregation": "count" } }
  ]
}
```

The response keys each result by its `key`:

```json title="representative response"
{
  "request_id": "req_...",
  "results": [
    { "key": "revenue", "data": { "confidence": 0.96, "result": [ { "value": 224950.0 } ] }, "error": null },
    { "key": "orders",  "data": { "confidence": 0.98, "result": [ { "value": 1840 } ] }, "error": null }
  ]
}
```

### A wide read-only SQL report

`query_sql_report` accepts a single `SELECT`/`WITH` statement over the datasets you list under `sources`, each optionally aliased for the SQL.

```json title="query_sql_report (tool arguments)"
{
  "sources": [ { "dataset_id": "$DATASET_ID", "alias": "orders" } ],
  "sql": "SELECT region, count(*) AS n FROM orders GROUP BY region ORDER BY n DESC",
  "max_rows": 100
}
```

```json title="representative response"
{
  "columns": ["region", "n"],
  "rows": [ ["emea", 640], ["amer", 512] ],
  "row_count": 2,
  "truncated": false,
  "request_id": "req_...",
  "latency_ms": 18
}
```

When `truncated` is `true`, the SQL report guardrails capped the rowset — tighten the SQL or lower `max_rows`.

## Related pages

{% content-ref url="data.md" %}
[data.md](data.md)
{% endcontent-ref %}

{% content-ref url="../concepts/governed-data.md" %}
[../concepts/governed-data.md](../concepts/governed-data.md)
{% endcontent-ref %}

{% content-ref url="../guides/governed-query.md" %}
[../guides/governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}
