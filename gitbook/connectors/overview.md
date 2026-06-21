---
icon: plug
description: Connectors are configured, testable connections to your external data — databases, warehouses, object storage, REST APIs, and files — that back a governed source the engine can query.
---

# Connectors

A **connector** is a configured connection to an external system that backs a [source](../concepts/governed-data.md). You register it once with the credentials and location of your data, Algenta tests that the connection is reachable, and from then on the engine reads from it under a typed, [governed-data](../concepts/governed-data.md) contract — never copying your warehouse, never reaching beyond what you configured.

Connectors are the *capability* of the data plane: you point Algenta at a table, an object, or an API, and the [capability plane](../concepts/capability-plane.md) handles fetch, schema discovery, and field mapping. The credentials you supply are encrypted at rest, scoped to your organization, and used only to serve your own queries.

## What a connector is

Every connector has three things:

* A **type** — for example `postgres`, `snowflake`, `clickhouse`, `s3`, or `rest_api`.
* A **config** — a JSON object whose fields depend on the type (a `connection_string` and `query` for SQL, a `bucket` and `key` for object storage, a `url` and `data_path` for REST).
* A **status** — `untested` when first created, `live` once a real connection succeeds, or `error` with a message when it fails.

You can list every supported type at runtime:

```bash
curl -s https://api.algenta.ai/v1/connectors/types \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

## Categories

Algenta groups connector types into five families. Pick the one that matches where your data lives.

| Category | What it reaches | Types |
| --- | --- | --- |
| **Database** | Operational SQL and NoSQL stores | `postgres`, `mysql`, `mssql`, `sqlite`, `redis`, `neo4j`, `elasticsearch` |
| **Warehouse** | Analytical columnar engines | `snowflake`, `bigquery`, `clickhouse`, `redshift` |
| **Object storage** | Cloud blob stores | `s3`, `gcs`, `azure` |
| **REST** | Any HTTP/JSON API | `rest`, `rest_api` |
| **File** | Uploaded or inline CSV, TSV, JSON, Excel, Parquet | `file` |

Object-storage and file connectors share the same parsers, so a Parquet object in `s3` and an uploaded Parquet file land in the engine identically. SQL databases and warehouses share the same `connection_string` + `query` shape — the difference is the DSN scheme.

## The lifecycle: create, test, browse, connect

A connector moves through four steps before the engine reads a single row. The full walkthrough lives in [Connect your data](../guides/connect-data.md); the short version:

1. **Create** — `POST /v1/connectors` with a `name`, `connector_type`, and `config`. The connector is stored with status `untested`.
2. **Test** — `POST /v1/connectors/{id}/test` opens a real connection (`SELECT 1` for SQL, a `HEAD` for object storage, a sample fetch for REST). On success the status flips to `live`.
3. **Browse** — `GET /v1/connectors/{id}/browse` lists the tables, datasets, or objects the connection exposes. A connector must be `live` before you can browse it.
4. **Connect** — onboard the selected table or object as a source so the engine can query it under a contract.

```bash
# 1. Create
curl -s -X POST https://api.algenta.ai/v1/connectors \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analytics-warehouse",
    "connector_type": "postgres",
    "config": {
      "connection_string": "postgresql+asyncpg://user:pass@host:5432/analytics",
      "query": "SELECT * FROM revenue_by_region"
    }
  }'

# 2. Test (status -> live)
curl -s -X POST https://api.algenta.ai/v1/connectors/$CONNECTOR_ID/test \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# 3. Browse the schema
curl -s https://api.algenta.ai/v1/connectors/$CONNECTOR_ID/browse \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

You can also test or browse a config **inline** — without saving it — by posting it to `POST /v1/connectors/test` or `POST /v1/connectors/browse`. Inline previews are rate limited, so create a saved connector for any production workflow.

## Pick your source

Each guide below walks one source end to end — the exact config fields, a tested example, and the browse output you should expect.

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Snowflake</strong></td><td>Connect a Snowflake warehouse with a snowflake:// DSN, account, and warehouse.</td><td><a href="snowflake.md">snowflake.md</a></td></tr>
<tr><td><strong>BigQuery</strong></td><td>Query a BigQuery dataset through a service-account credential.</td><td><a href="bigquery.md">bigquery.md</a></td></tr>
<tr><td><strong>ClickHouse</strong></td><td>Reach a ClickHouse cluster over HTTP(S) with a clickhouse:// DSN.</td><td><a href="clickhouse.md">clickhouse.md</a></td></tr>
<tr><td><strong>REST API</strong></td><td>Pull JSON from any HTTP endpoint, with a data_path and bounded pagination.</td><td><a href="rest-api.md">rest-api.md</a></td></tr>
</tbody>
</table>

## Reference and concepts

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Connectors reference</strong></td><td>Every connector type, its config fields, and the test, browse, and connect endpoints.</td><td><a href="reference.md">reference.md</a></td></tr>
<tr><td><strong>Connect your data</strong></td><td>The full create to query walkthrough — register a connector and onboard a source.</td><td><a href="../guides/connect-data.md">../guides/connect-data.md</a></td></tr>
<tr><td><strong>Governed data</strong></td><td>How a connector backs a source the engine queries under a typed, auditable contract.</td><td><a href="../concepts/governed-data.md">../concepts/governed-data.md</a></td></tr>
</tbody>
</table>

## Next steps

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Run your first query</strong></td><td>Once a source is onboarded, ask the engine an exact, deterministic question.</td><td><a href="../guides/first-query.md">../guides/first-query.md</a></td></tr>
<tr><td><strong>Governed query</strong></td><td>Query with field hints and operators so results stay deterministic and auditable.</td><td><a href="../guides/governed-query.md">../guides/governed-query.md</a></td></tr>
<tr><td><strong>API reference</strong></td><td>The full /v1 surface, including every connectors endpoint and payload.</td><td><a href="../api/reference.md">../api/reference.md</a></td></tr>
</tbody>
</table>

If a connector reports `error` after a test, the message names the cause — bad credentials, an unreachable host, or a blocked egress destination. See [Troubleshooting](../troubleshooting.md) for the common failures and the shortest fix for each.
