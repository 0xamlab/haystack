---
icon: plug
description: Register an external source as a saved connector, test it, browse its schema, and onboard a dataset so the engine can query it under a typed contract.
---

# Connect a data source

By the end of this page you will have registered an external system (a SQL database, a warehouse, an object store, or a REST API) as a saved **connector**, confirmed it reaches the source with a real connection test, browsed the tables or objects it exposes, and turned one of them into a queryable **dataset**. Once connected, the data becomes [governed data](../concepts/governed-data.md): the engine queries it under a typed, validated contract, so results stay deterministic and auditable. Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and credentials for the source you want to connect. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every tool below picks them up from the environment.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

Both lines should print without error, and the base URL should match the deployment you intend to use.
{% endstep %}

{% step %}
### List the connector types the engine supports

Ask the engine which connector types it accepts. Pick the type that matches your source — for example `postgres`, `snowflake`, `bigquery`, `s3`, `gcs`, `azure`, `rest`, or `sqlite`.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response is a JSON object with a `types` array, for example `{"types": ["azure", "bigquery", "postgres", "rest", "s3", ...]}`. The connector type you choose decides which fields belong in `config` in the next step.
{% endstep %}

{% step %}
### Create a saved connector

`POST /v1/connectors` stores the connection name, type, and credentials and returns the connector with `status: "untested"`. The `config` fields depend on the connector type. A Postgres connector takes `host`, `port`, `database`, `user`, `password`, and optional `ssl_mode`; an `s3` connector takes `bucket`, `region`, `access_key_id`, and `secret_access_key`; a `rest` connector takes `base_url` plus an optional `auth_type` (`none`, `bearer`, `api_key`, or `basic`).

```bash title="Create a Postgres connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales DB",
    "connector_type": "postgres",
    "config": {
      "host": "db.internal.example.com",
      "port": 5432,
      "database": "sales",
      "user": "analytics",
      "password": "<DB_PASSWORD>",
      "ssl_mode": "require"
    }
  }'
```

The response includes the connector `id`, `connector_type`, and `status` (initially `untested`). Copy the `id` — the next steps use it. Save it to a variable:

```bash title="Capture the connector id"
export CONNECTOR_ID="<id from the response>"
```

{% hint style="info" %}
Credentials are encrypted at rest. The connector object never returns your `config` back to you — only its name, type, status, and last test result.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt and flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test before you browse.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

A successful response looks like `{"success": true, "status": "ok", "latency_ms": 42, "message": "PostgreSQL connection successful (...)"}`. On failure, `success` is `false` and `error_type` plus `recoverable` tell you whether to fix credentials and retry. The connector's stored `status` is now `live`.
{% endstep %}

{% step %}
### Browse what the connector exposes

`GET /v1/connectors/{id}/browse` lists the tables, objects, or datasets the live connector can see, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response has `connector_type`, an `items` array (each entry is a browsable table, file, or dataset), a `total`, a `message`, and `discovery` metadata. Note the name of the table or object you want to query.
{% endstep %}

{% step %}
### Connect a dataset from the source

`POST /v1/data/connect` ties together a connection and a selection (a table, SQL query, or object path) and registers the result as a queryable dataset. You can reference a saved connector by `connection_id`, or supply the connection inline with `connection_type`, `provider`, and `connection_config`. The broad `connection_type` is one of `database`, `api`, `object_storage`, or `file_upload`.

```bash title="Connect a dataset from the saved connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"database\",
    \"provider\": \"postgres\",
    \"dataset_name\": \"sales_orders\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"table\": \"orders\"},
    \"visibility\": \"private\"
  }"
```

When the selection fully identifies one table, the response has `status: "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. If the connection resolves to more than one table, the response is `status: "needs_selection"` with a `choices` array and a `connection_id` to reuse — pick one `selection` from `choices` and call `/v1/data/connect` again with that `connection_id` and `selection`. A bad credential or unreachable host returns `status: "failed"` with a message.
{% endstep %}

{% step %}
### Confirm the dataset is registered

List the datasets your key can see and confirm the new one appears.

```bash title="List datasets"
curl -s "$ALGENTA_BASE_URL/v1/data" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Your new dataset should be present with the `dataset_name` you chose and a non-zero `column_count`. Copy its `dataset_id` — that is what you pass to a query.
{% endstep %}
{% endstepper %}

## Expected result

You have a saved connector with `status: "live"`, a browse listing of what it exposes, and a registered dataset that appears in `GET /v1/data` with a `dataset_id` and a profiled schema. The dataset is now governed data: the engine will resolve queries against it under a typed contract, and the same intent against the same dataset returns the same deterministic answer. You are ready to run a query against it.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK. Use whichever fits your workflow — all three hit the identical API.

### de CLI

The CLI reads JSON request bodies from a file (the same shapes shown above) and runs the connect flow interactively when you omit the file.

```bash title="Connectors and datasets with the de CLI"
# Saved connectors
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors list                      # list saved connectors
de connectors test $CONNECTOR_ID       # run a real connection health check
de connectors browse $CONNECTOR_ID     # browse a live connector's schema

# Datasets
de data connect connect.json            # POST /v1/data/connect from a JSON body
de data connect                         # interactive connect flow (prompts for fields)
de data list                            # list registered datasets
```

`de data connect` with no file walks you through connection type, provider, credentials, and selection, then handles the `needs_selection` choice prompt for you.

### Python SDK

The synchronous client mirrors the endpoints one to one. Read your key from the environment.

```python title="Connect a data source with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

# 1. Create a saved connector
connector = client.create_connector(
    name="Sales DB",
    connector_type="postgres",
    config={
        "host": "db.internal.example.com",
        "port": 5432,
        "database": "sales",
        "user": "analytics",
        "password": os.environ["DB_PASSWORD"],
        "ssl_mode": "require",
    },
)

# 2. Test it (must be live before browsing)
test = client.test_connector(connector.id)
assert test.success, test.message

# 3. Browse what it exposes
browse = client.browse_connector(connector.id)
print(browse.total, "items")

# 4. Connect a dataset from a selection
result = client.connect_data(
    connection_type="database",
    provider="postgres",
    dataset_name="sales_orders",
    connection_id=connector.id,
    selection={"table": "orders"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

{% hint style="warning" %}
**`409 not_connected` when browsing.** The connector is not `live`. Run `POST /v1/connectors/{id}/test` (or `de connectors test <id>`) first; only a connector that passes its test can be browsed.
{% endhint %}

{% hint style="warning" %}
**Test fails with `error_type: "permission"` or a privacy-policy message.** The destination host or bucket is outside the egress allowlist for your deployment. Confirm the host, port, region, or `endpoint_url` in your `config`, and that the destination is permitted by your deployment's egress policy. See [Configuration](../configuration.md).
{% endhint %}

{% hint style="info" %}
**`status: "needs_selection"` from `/v1/data/connect`.** The connection resolved to more than one table, file, or object. Re-call `/v1/data/connect` with the returned `connection_id` and one `selection` from the `choices` array. The interactive `de data connect` flow prompts you for the choice automatically.
{% endhint %}

{% hint style="info" %}
**No external system handy?** You can onboard inline data directly with `POST /v1/datasets/onboard`, passing `records` (a list of row dicts), `csv` (raw CSV text with a header row), or `columns` (column names only). The engine profiles the schema and returns a queryable dataset without a connector.
{% endhint %}

## Next

{% content-ref url="first-query.md" %}
[first-query.md](first-query.md)
{% endcontent-ref %}

{% content-ref url="../concepts/governed-data.md" %}
[governed-data.md](../concepts/governed-data.md)
{% endcontent-ref %}
