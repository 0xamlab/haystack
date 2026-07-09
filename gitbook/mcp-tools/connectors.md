---
icon: plug
description: MCP reference for Algenta connector tools — create, inspect, test, browse, update, and delete saved data connectors, plus preview inline definitions.
---

# Connector tools

A connector is a saved, reusable definition of a connection to an external system — a database, a warehouse, object storage, a REST API, or a file source. These MCP tools manage the connector lifecycle: create and save a config, run a real connectivity test, browse its schema, update or delete it, and list what you have. Two preview variants test or browse an inline definition without persisting it. Every tool maps one-to-one to a `/v1` endpoint.

{% hint style="info" %}
For the everyday path — connect a source and get a queryable `dataset_id` in one step — use `connect_data` on the [Data and ingest tools](data.md) page. Reach for these connector tools when you want to explicitly manage saved, reusable connectors. For the full list of `connector_type` values and their config fields, see the [Connectors reference](../connectors/reference.md).
{% endhint %}

## The connector lifecycle

A new connector starts `untested`; a successful test moves it to `live`, a failed one to `error`. Browsing requires a `live` connector, and editing `config` resets it to `untested`.

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `list_connectors` | List saved connectors; filter by status. | `status` (`untested` / `live` / `error` / `all`), `page`, `limit`. |
| `create_connector` | Create and save one connector config for later onboarding, health checks, and browsing. | `name` (required), `connector_type` (required); `config`, `description`, `visibility` (`private` / `organization` / `public`). |
| `get_connector` | Fetch one saved connector by id. | `connector_id` (required). |
| `update_connector` | Update a saved connector's name, description, visibility, or config. | `connector_id` (required) + at least one of `name` / `description` / `visibility` / `config`. |
| `test_connector` | Run a real connectivity test for a saved connector and persist its `live`/`error` status. | `connector_id` (required). |
| `browse_connector` | Browse a saved `live` connector to discover files, tables, endpoints, or items. | `connector_id` (required). |
| `preview_test_connector` | Test an inline connector definition without saving it. | `connector_type` (required), `config`. |
| `preview_browse_connector` | Browse an inline connector definition without saving it. | `connector_type` (required), `config`. |
| `delete_connector` | Delete one saved connector by id. | `connector_id` (required). |

## Method and endpoint

Because each tool is a one-to-one wrapper, you can reproduce any call against the raw endpoint.

| Tool | Method | Endpoint |
| --- | --- | --- |
| `list_connectors` | `GET` | `/v1/connectors` |
| `create_connector` | `POST` | `/v1/connectors` |
| `get_connector` | `GET` | `/v1/connectors/{connector_id}` |
| `update_connector` | `PATCH` | `/v1/connectors/{connector_id}` |
| `test_connector` | `POST` | `/v1/connectors/{connector_id}/test` |
| `browse_connector` | `GET` | `/v1/connectors/{connector_id}/browse` |
| `preview_test_connector` | `POST` | `/v1/connectors/test` |
| `preview_browse_connector` | `POST` | `/v1/connectors/browse` |
| `delete_connector` | `DELETE` | `/v1/connectors/{connector_id}` |

## Worked examples

### Preview a config, then save it

Validate a config without persisting anything with `preview_test_connector`, then commit it with `create_connector`. This is the test-before-save pattern; inline previews are rate limited, so save and reuse a connector for production workflows.

```json title="preview_test_connector (tool arguments)"
{
  "connector_type": "postgres",
  "config": {
    "host": "db.internal",
    "port": 5432,
    "database": "analytics",
    "user": "reader",
    "password": "$ALGENTA_DB_PASSWORD"
  }
}
```

```json title="create_connector (tool arguments)"
{
  "name": "analytics-pg",
  "connector_type": "postgres",
  "config": {
    "host": "db.internal",
    "port": 5432,
    "database": "analytics",
    "user": "reader",
    "password": "$ALGENTA_DB_PASSWORD"
  },
  "visibility": "organization"
}
```

The equivalent HTTP calls:

```bash title="preview then create via HTTP"
curl -s "$ALGENTA_BASE_URL/v1/connectors/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "connector_type": "postgres", "config": { "host": "db.internal", "port": 5432, "database": "analytics", "user": "reader", "password": "'"$ALGENTA_DB_PASSWORD"'" } }'

curl -s "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "name": "analytics-pg", "connector_type": "postgres", "config": { "host": "db.internal", "port": 5432, "database": "analytics", "user": "reader", "password": "'"$ALGENTA_DB_PASSWORD"'" }, "visibility": "organization" }'
```

### Test a saved connector, then browse it

A saved connector must pass `test_connector` (moving it to `live`) before `browse_connector` can enumerate its tables, files, or endpoints.

```json title="test_connector (tool arguments)"
{ "connector_id": "$CONNECTOR_ID" }
```

```bash title="test then browse via HTTP"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -X POST

curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

{% hint style="warning" %}
`browse_connector` requires a `live` connector. If you browse an `untested` or `error` connector, the endpoint responds with `409 not_connected` — run `test_connector` first and confirm it passes.
{% endhint %}

### List only live connectors

Filter the list to connectors that last tested successfully.

```json title="list_connectors (tool arguments)"
{ "status": "live", "limit": 25 }
```

```bash title="list_connectors via HTTP"
curl -s "$ALGENTA_BASE_URL/v1/connectors?page=1&limit=25" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '.connectors[] | select(.status == "live") | .id'
```

## Related pages

{% content-ref url="../connectors/reference.md" %}
[../connectors/reference.md](../connectors/reference.md)
{% endcontent-ref %}

{% content-ref url="data.md" %}
[data.md](data.md)
{% endcontent-ref %}

{% content-ref url="../guides/connect-data.md" %}
[../guides/connect-data.md](../guides/connect-data.md)
{% endcontent-ref %}
