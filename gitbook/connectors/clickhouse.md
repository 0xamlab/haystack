---
icon: database
description: Connect ClickHouse to Algenta as a governed connector. Configure host, port, database, user, password, and secure, then test, browse, connect, and query.
---

# Connect ClickHouse

This task walks you through wiring a ClickHouse cluster into Algenta as a `clickhouse` connector. You create the connector with its real config fields, run a live connection test, browse the tables it exposes, and run a governed query against it.

ClickHouse is a SQL connector under the hood — Algenta speaks to it over the native HTTP interface using the `clickhouse-connect` client. Everything you store stays a [governed data](../concepts/governed-data.md) source: the engine queries it under a typed, validated contract.

## Before you start

- A reachable ClickHouse endpoint (host, HTTP port, and credentials). The default HTTP port is `8123` for plaintext and `8443` when TLS is enabled.
- An Algenta API key. See [Authentication](../authentication.md) for how to obtain and send it.
- The self-hosted engine running on `http://localhost:8000`, or the hosted API at `https://api.algenta.ai`.

{% hint style="info" %}
The ClickHouse connector requires the `clickhouse-connect` package on the engine host. If it is missing, the connection test returns an `invalid_config` failure telling you to install it.
{% endhint %}

## Config fields

The `clickhouse` connector accepts these fields in `config`. They map directly to the ClickHouse client the engine builds.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | Yes | `localhost` | ClickHouse hostname or IP. |
| `port` | No | `8123` (or `8443` when `secure`) | HTTP interface port. |
| `database` | No | `default` | Target database. |
| `user` | No | `default` | Username. `username` is accepted as an alias. |
| `password` | No | empty | Password for the user. |
| `secure` | No | `false` | Use TLS (HTTPS). Accepts `true`/`1`/`yes`/`on`. |

{% hint style="info" %}
Instead of the discrete fields you may pass a single `connection_string` (or `url`) of the form `clickhouse://user:password@host:port/database?secure=true`. The engine parses it into the same fields; a `clickhouses://` or `https://` scheme implies `secure=true`. If you set both, the explicit fields win.
{% endhint %}

## 1. Create the connector

Send the config to `POST /v1/connectors`. New connectors start in the `untested` status until you run a test.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Events warehouse",
    "connector_type": "clickhouse",
    "config": {
      "host": "clickhouse.internal",
      "port": 8443,
      "database": "analytics",
      "user": "reader",
      "password": "'"$ALGENTA_CLICKHOUSE_PASSWORD"'",
      "secure": true
    }
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

resp = httpx.post(
    f"{os.environ['ALGENTA_API_URL']}/v1/connectors",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "name": "Events warehouse",
        "connector_type": "clickhouse",
        "config": {
            "host": "clickhouse.internal",
            "port": 8443,
            "database": "analytics",
            "user": "reader",
            "password": os.environ["ALGENTA_CLICKHOUSE_PASSWORD"],
            "secure": True,
        },
    },
    timeout=30,
)
resp.raise_for_status()
connector = resp.json()
print(connector["id"], connector["status"])
```
{% endtab %}
{% endtabs %}

The response is the connector record. Keep `id` — every step below uses it.

```json
{
  "id": "a1b2c3d4-0000-0000-0000-000000000000",
  "name": "Events warehouse",
  "connector_type": "clickhouse",
  "status": "untested",
  "visibility": "private",
  "last_tested_at": null,
  "error_message": null,
  "created_at": "2026-06-21T12:00:00Z"
}
```

## 2. Test the connection

Run `POST /v1/connectors/{connector_id}/test`. The engine opens a real ClickHouse client and runs `SELECT 1`. On success the connector flips to `live`; on failure it goes to `error` and records the reason.

```bash
curl -sS -X POST \
  "$ALGENTA_API_URL/v1/connectors/$ALGENTA_CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** The connector flips to `live`, and a successful test reports the resolved host, port, and database:

```json
{
  "success": true,
  "message": "ClickHouse connection successful (clickhouse.internal:8443/analytics)",
  "latency_ms": 41,
  "status": "live",
  "error_type": null,
  "recoverable": null
}
```

{% hint style="warning" %}
If you want to validate config before saving anything, post the same `connector_type` and `config` to `POST /v1/connectors/test`. Inline previews are rate limited — create and reuse a saved connector for production workflows.
{% endhint %}

## 3. Browse the schema

Once the connector is `live`, list its tables with `GET /v1/connectors/{connector_id}/browse`. Browsing a connector that has not been tested returns a `409 not_connected` — run the test first.

```bash
curl -sS \
  "$ALGENTA_API_URL/v1/connectors/$ALGENTA_CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

```json
{
  "connector_type": "clickhouse",
  "items": [
    {"name": "events", "type": "table"},
    {"name": "users", "type": "table"}
  ],
  "total": 2,
  "message": "Found 2 browsable ClickHouse tables",
  "labels": {},
  "discovery": {}
}
```

Use the `items` to pick the table (or build the SQL) you will query.

## 4. Query the connector

A `clickhouse` connector backs a [governed data](../concepts/governed-data.md) source. Point a source selection at a table, or supply a `SELECT` query. The SQL connector reads `query` and an optional `limit`; the engine wraps your query and applies the limit so results stay bounded.

{% hint style="info" %}
ClickHouse selections are quoted with backticks per the ClickHouse SQL dialect, and `limit` is applied as a top-level `LIMIT`. Pass a plain `SELECT` — the engine does the wrapping.
{% endhint %}

For the full governed-query flow — typed contracts, field hints, and operators — see [Run a governed query](../guides/governed-query.md). For the connector and query endpoint shapes, see the [API reference](../api/reference.md).

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `invalid_config` mentioning `clickhouse-connect` | The client library is not installed on the engine host. |
| Test fails with a connection error | Wrong `host`/`port`, or `secure` mismatched with the port (use `8443` for TLS, `8123` for plaintext). |
| `409 not_connected` on browse | The connector is not `live` yet — run the test first. |
| Blocked by privacy policy | The ClickHouse host is not in the egress allowlist for the engine. |

## Next steps

* [Run a governed query](../guides/governed-query.md) — the full typed-contract query flow against your new source.
* [Connectors overview](overview.md) — the lifecycle across every connector type.
* [Snowflake](snowflake.md) and [BigQuery](bigquery.md) — the other warehouse connectors.
* [Connectors reference](reference.md) — every type, config field, and endpoint.
* [Troubleshooting](../troubleshooting.md) — diagnose a failed test or blocked egress.
