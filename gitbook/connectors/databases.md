---
icon: database
description: Connect a database directly to Algenta — the engine reads your tables under a governed contract, never copies them, and keeps credentials encrypted at rest.
---

# Connect a database

Algenta connects **directly** to your database. You register the connection once, Algenta opens a real connection to verify it, and from then on the engine reads your tables under a typed, [governed contract](../concepts/governed-data.md) — it never copies your database, never reaches beyond what you configured, and stores your credentials encrypted at rest. This page walks the direct-connection flow end to end for any supported SQL database or warehouse.

{% hint style="info" %}
This is direct connectivity over the database's own wire protocol — not a sync, not an export, and not a third-party bridge. The engine queries your data in place, scoped to your organization. For the full connector model across all source types (object storage, REST, files), see [Connectors overview](overview.md).
{% endhint %}

## Supported databases

| Family | Types |
| --- | --- |
| Relational | `postgres`, `mysql`, `mssql`, `sqlite` |
| Warehouse | `snowflake`, `bigquery`, `clickhouse`, `redshift` |
| Graph, cache & search | `neo4j`, `redis`, `elasticsearch` |

All SQL databases accept either a single `connection_string` DSN or discrete `host` / `port` / `database` / `user` / `password` fields. For the exact config fields per type, see the [Connectors reference](reference.md); for worked, source-specific walkthroughs see [Snowflake](snowflake.md), [BigQuery](bigquery.md), and [ClickHouse](clickhouse.md).

## Connect it in four steps

A database moves through **create → test → browse → connect** before the engine reads a row. The example uses `postgres`; every SQL type follows the same shape.

{% stepper %}
{% step %}
### Create the connector

`POST /v1/connectors` stores the connection with status `untested`. Keep the returned `id` — every step below uses it.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analytics-pg",
    "connector_type": "postgres",
    "config": {
      "connection_string": "postgresql://reader:'"$ALGENTA_DB_PASSWORD"'@db.internal:5432/analytics"
    }
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

api_url = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
resp = httpx.post(
    f"{api_url}/v1/connectors",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "name": "analytics-pg",
        "connector_type": "postgres",
        "config": {
            "host": "db.internal",
            "port": 5432,
            "database": "analytics",
            "user": "reader",
            "password": os.environ["ALGENTA_DB_PASSWORD"],
        },
    },
)
resp.raise_for_status()
print(resp.json()["id"], resp.json()["status"])  # "untested"
```
{% endtab %}

{% tab title="CLI" %}
```bash
de connectors create connector.json     # POST /v1/connectors from a JSON body
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` opens a **real** connection and runs `SELECT 1`. On success the status flips to `live`; on failure it goes to `error` with a message.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** The connector flips to `live` and the response reports the reachable database, e.g. `{"success": true, "status": "live", "message": "Connection successful"}`. A connector must be `live` before you can browse it.
{% endstep %}

{% step %}
### Browse the schema

`GET /v1/connectors/{id}/browse` lists the tables the connection exposes, so you can pick what to onboard.

```bash
curl -sS "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endstep %}

{% step %}
### Connect a table as a dataset

`POST /v1/data/connect` ties the connection to a selection — a table or a SQL query — and registers it as a queryable [dataset](../help/glossary.md). Reference the saved connector by `connection_id`.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"connection_id": "'"$CONNECTOR_ID"'", "selection": {"table": "revenue_by_region"}}'
```

A fully-identified table returns `status: "ready"` with a `dataset_id` and a `schema_summary`. With that `dataset_id` you run deterministic, schema-checked queries through `POST /v1/query`.
{% endstep %}
{% endstepper %}

{% hint style="info" %}
Editing a connector's `config` resets it to `untested` and clears the previous error — re-run the test before browsing again. You can also validate a config without saving it via `POST /v1/connectors/test`. See the [Connect a data source](../guides/connect-data.md) guide for the full walkthrough.
{% endhint %}

## Next steps

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}

{% content-ref url="../guides/connect-data.md" %}
[connect-data.md](../guides/connect-data.md)
{% endcontent-ref %}

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="overview.md" %}
[overview.md](overview.md)
{% endcontent-ref %}
